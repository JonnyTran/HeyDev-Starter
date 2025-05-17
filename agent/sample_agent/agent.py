"""
DevRel publishing agent that generates content from GitHub repo changes.
"""

import json
import os
import re
import uuid
from datetime import datetime
from typing import List, Dict, Optional, TypedDict, Any
from typing_extensions import Literal

import psycopg2
import requests
from dotenv import load_dotenv
from litellm import completion
from crewai.flow.flow import Flow, start, router, listen

from copilotkit.crewai import (
    copilotkit_stream, 
    copilotkit_predict_state,
    copilotkit_emit_state,
    CopilotKitState
)

# Load environment variables
load_dotenv()

# Tools definition
GITHUB_API_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_github_data",
        "description": "Fetch data from a GitHub repository after a certain date",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "GitHub repository URL"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["commits", "issues", "pull_requests", "docs", "all"],
                    "description": "Type of data to fetch"
                }
            },
            "required": ["repo_url", "start_date", "data_type"]
        }
    }
}

GENERATE_TOPIC_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_topic",
        "description": "Generate a content topic based on repository changes",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title for the content topic"
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of the topic"
                },
                "source_type": {
                    "type": "string",
                    "enum": ["commit", "issue", "pull_request", "docs"],
                    "description": "Source of the topic"
                },
                "source_id": {
                    "type": "string",
                    "description": "ID of the source item"
                },
                "content_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["blog_post", "code_example", "social_media"]
                    },
                    "description": "Types of content suitable for this topic"
                }
            },
            "required": ["title", "description", "source_type", "source_id", "content_types"]
        }
    }
}

WRITE_CONTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "write_content",
        "description": "Generate content based on the selected topic",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The generated content"
                },
                "title": {
                    "type": "string",
                    "description": "Title for the content"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the content"
                }
            },
            "required": ["content", "title", "summary"]
        }
    }
}

# GitHub API helpers
def extract_repo_info(repo_url: str) -> tuple:
    """Extract owner and repo name from GitHub URL."""
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, repo_url)
    if match:
        owner, repo = match.groups()
        return owner, repo
    raise ValueError(f"Invalid GitHub URL: {repo_url}")

def github_api_request(endpoint: str, params: Dict = None) -> Dict:
    """Make a request to GitHub API with proper auth and error handling."""
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    base_url = "https://api.github.com"
    response = requests.get(f"{base_url}/{endpoint}", headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
    
    return response.json()

class DevRelAgentState(CopilotKitState):
    """
    State definition for the DevRel Publisher Agent.
    Tracks all data through the content generation process.
    """
    # GitHub Repository Data
    repo_url: str = ""
    start_date: str = ""
    
    # Analysis Data
    commits: List[Dict] = []
    issues: List[Dict] = []
    pull_requests: List[Dict] = []
    docs_changes: List[Dict] = []
    
    # Generated Topics
    topics: List[Dict] = []
    selected_topic: Dict = {}
    
    # Content Generation
    content_drafts: Dict[str, str] = {
        "blog_post": "",
        "code_example": "",
        "social_media": ""
    }
    
    # Database Record
    content_record: Dict[str, str] = {
        "channel": "",
        "title": "",
        "summary": "",
        "content": "",
        "type": ""
    }

class DevRelPublisherFlow(Flow[DevRelAgentState]):
    """
    Flow implementation for the DevRel Publisher Agent.
    Handles the process from GitHub repository analysis to content publication.
    """
    
    @start()
    async def input_github_repo(self):
        """Entry point: Collect GitHub repository URL."""
        # This node will be called first and waits for user input
        # The state will be updated directly from frontend actions
    
    @router(input_github_repo)
    async def select_date_range(self):
        """User selects date range for repository analysis."""
        # This node transitions when user has provided both repo URL and start date
        if self.state.repo_url and self.state.start_date:
            return "analyze_repository"
        return "input_github_repo"
    
    @router(select_date_range)
    async def analyze_repository(self):
        """
        Analyze the GitHub repository data after the start date.
        Fetches commits, issues, PRs, and documentation changes.
        """
        system_prompt = """
        You are a DevRel content expert analyzing a GitHub repository.
        Your job is to fetch and analyze the repository data since a specific date.
        """
        
        try:
            # Extract owner and repo from URL
            owner, repo = extract_repo_info(self.state.repo_url)
            
            # Emit state update to show progress
            await copilotkit_emit_state({
                "status": "Analyzing repository..."
            })
            
            # Fetch commits
            commits_endpoint = f"repos/{owner}/{repo}/commits"
            commits_params = {"since": f"{self.state.start_date}T00:00:00Z"}
            self.state.commits = github_api_request(commits_endpoint, commits_params)
            
            # Emit progress update
            await copilotkit_emit_state({
                "status": f"Found {len(self.state.commits)} commits"
            })
            
            # Fetch issues
            issues_endpoint = f"repos/{owner}/{repo}/issues"
            issues_params = {"state": "all", "since": f"{self.state.start_date}T00:00:00Z"}
            self.state.issues = github_api_request(issues_endpoint, issues_params)
            
            await copilotkit_emit_state({
                "status": f"Found {len(self.state.issues)} issues"
            })
            
            # Fetch pull requests
            prs_endpoint = f"repos/{owner}/{repo}/pulls"
            prs_params = {"state": "all"}
            self.state.pull_requests = [
                pr for pr in github_api_request(prs_endpoint, prs_params)
                if datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ") >= datetime.strptime(self.state.start_date, "%Y-%m-%d")
            ]
            
            await copilotkit_emit_state({
                "status": f"Found {len(self.state.pull_requests)} pull requests"
            })
            
            # Check for documentation changes
            docs_changes = []
            for commit in self.state.commits:
                commit_endpoint = f"repos/{owner}/{repo}/commits/{commit['sha']}"
                commit_data = github_api_request(commit_endpoint)
                
                if "files" in commit_data:
                    doc_files = [f for f in commit_data["files"] 
                               if f["filename"].endswith((".md", ".mdx", ".txt", "CHANGELOG", "README"))]
                    if doc_files:
                        docs_changes.append({
                            "commit": commit,
                            "doc_files": doc_files
                        })
            
            self.state.docs_changes = docs_changes
            
            await copilotkit_emit_state({
                "status": f"Found {len(self.state.docs_changes)} documentation changes"
            })
            
            # If we have data, proceed to generate topics
            if (self.state.commits or self.state.issues or 
                self.state.pull_requests or self.state.docs_changes):
                return "generate_topics"
            
            # If no data found, go back to input
            return "input_github_repo"
            
        except Exception as e:
            # Handle errors
            self.state.error = str(e)
            return "input_github_repo"
    
    @router(analyze_repository)
    async def generate_topics(self):
        """
        Generate content topics based on repository analysis.
        Uses the AI to identify potential topics from the repository data.
        """
        system_prompt = """
        You are a DevRel content strategist. Based on the GitHub repository data,
        generate potential content topics focusing on recent changes,
        new features, bug fixes, or documentation updates.
        
        For each topic, provide:
        1. A compelling title
        2. A brief description
        3. The primary source (commit, issue, PR)
        4. The content types it would work well for (blog, code example, social)
        
        Use the generate_topic tool for each topic you create.
        """
        
        # Use predictive state updates to show topics being generated
        await copilotkit_predict_state({
            "topics": {
                "tool_name": "generate_topic",
                "tool_argument": "title"
            }
        })
        
        # Use AI to analyze the data and generate topics
        response = await copilotkit_stream(
            completion(
                model="openai/gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
                        Here's the GitHub repository data to analyze:
                        
                        Commits: {json.dumps([{
                            "sha": c["sha"],
                            "message": c["commit"]["message"],
                            "date": c["commit"]["author"]["date"]
                        } for c in self.state.commits[:10]])}
                        
                        Issues: {json.dumps([{
                            "number": i["number"],
                            "title": i["title"],
                            "state": i["state"],
                            "created_at": i["created_at"]
                        } for i in self.state.issues[:10]])}
                        
                        Pull Requests: {json.dumps([{
                            "number": p["number"],
                            "title": p["title"],
                            "state": p["state"],
                            "created_at": p["created_at"]
                        } for p in self.state.pull_requests[:10]])}
                        
                        Doc Changes: {json.dumps([{
                            "commit_message": d["commit"]["commit"]["message"],
                            "files": [f["filename"] for f in d["doc_files"]]
                        } for d in self.state.docs_changes[:10]])}
                        
                        Generate 5 compelling content topics based on this data.
                    """}
                ],
                tools=[GENERATE_TOPIC_TOOL],
                stream=True
            )
        )
        
        message = response.choices[0].message
        self.state.messages.append(message)
        
        # Process tool calls to extract topics
        if message.get("tool_calls"):
            for tool_call in message.get("tool_calls", []):
                if tool_call["function"]["name"] == "generate_topic":
                    topic_data = json.loads(tool_call["function"]["arguments"])
                    self.state.topics.append(topic_data)
        
        # If we have topics, proceed to user selection
        if self.state.topics:
            return "user_selects_topic"
        
        # If no topics were generated, retry
        return "generate_topics"
    
    @router(generate_topics)
    async def user_selects_topic(self):
        """
        Human-in-the-loop: User selects a topic.
        This node transitions when user makes a selection.
        """
        # This node represents the state where the frontend displays topics
        # and waits for user selection
        
        # Check if user has selected a topic (will be set via frontend action)
        if self.state.selected_topic:
            return "generate_content_drafts"
            
        # Otherwise remain in this state
        return "user_selects_topic"
    
    @router(user_selects_topic)
    async def generate_content_drafts(self):
        """
        Generate content drafts based on the selected topic.
        Creates drafts for blog posts, code examples, and social media.
        """
        system_prompt = """
        You are a DevRel content creator writing about technical topics.
        Create professional, engaging content for the selected topic.
        Generate content that clearly explains the technical details while
        keeping it accessible to the target audience.
        
        Use the write_content tool to submit your draft.
        """
        
        # Use predictive state updates to show content being generated
        await copilotkit_predict_state({
            "content_drafts": {
                "tool_name": "write_content",
                "tool_argument": "content"
            }
        })
        
        # Get which content type to generate
        content_type = self.state.selected_topic.get("content_types", ["blog_post"])[0]
        
        # Context from repository data
        context = {}
        source_type = self.state.selected_topic.get("source_type")
        source_id = self.state.selected_topic.get("source_id")
        
        if source_type == "commit":
            context = next((c for c in self.state.commits if c["sha"] == source_id), {})
        elif source_type == "issue":
            context = next((i for i in self.state.issues if str(i["number"]) == source_id), {})
        elif source_type == "pull_request":
            context = next((p for p in self.state.pull_requests if str(p["number"]) == source_id), {})
        
        # Generate the content draft
        response = await copilotkit_stream(
            completion(
                model="openai/gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
                        Topic: {self.state.selected_topic['title']}
                        Description: {self.state.selected_topic['description']}
                        Content Type: {content_type}
                        
                        Additional Context:
                        {json.dumps(context)}
                        
                        Please create an engaging {content_type} about this topic.
                    """}
                ],
                tools=[*self.state.copilotkit.actions, WRITE_CONTENT_TOOL],
                stream=True
            )
        )
        
        message = response.choices[0].message
        self.state.messages.append(message)
        
        # Process tool calls to extract content
        if message.get("tool_calls"):
            for tool_call in message.get("tool_calls", []):
                if tool_call["function"]["name"] == "write_content":
                    content_data = json.loads(tool_call["function"]["arguments"])
                    self.state.content_drafts[content_type] = content_data["content"]
                    
                    # Also save to content record
                    self.state.content_record = {
                        "channel": content_type,
                        "title": content_data["title"],
                        "summary": content_data["summary"],
                        "content": content_data["content"],
                        "type": content_type
                    }
        
        return "user_edits_content"
    
    @router(generate_content_drafts)
    async def user_edits_content(self):
        """
        Human-in-the-loop: User edits the generated content.
        This node transitions when user confirms content is ready.
        """
        # This represents the state where frontend displays the content editor
        # The content_record will be updated directly from frontend
        
        # Check if user has confirmed edits
        if "confirmed" in self.state.copilotkit.metadata:
            return "save_to_database"
            
        # Otherwise remain in this state
        return "user_edits_content"
    
    @router(user_edits_content)
    async def save_to_database(self):
        """
        Save the final content to the database.
        Inserts a record into the content table.
        """
        try:
            # Use the database helper module to insert content
            from sample_agent.db import insert_content
            
            # Insert the content record and get the ID
            content_id = insert_content(self.state.content_record)
            
            # Update state with the new ID
            self.state.content_record["id"] = content_id
            
            # Emit state update with success message
            await copilotkit_emit_state({
                "status": f"Content saved to database with ID: {content_id}"
            })
            
            return "flow_complete"
            
        except Exception as e:
            # Handle database errors
            self.state.error = str(e)
            
            # Emit state update with error message
            await copilotkit_emit_state({
                "status": f"Database error: {str(e)}"
            })
            
            return "user_edits_content"
    
    @listen("flow_complete")
    async def flow_complete(self):
        """End the flow."""
        # Cleanup and complete
        pass

# Tool handlers
def fetch_github_data_handler(args):
    """Handler for fetch_github_data tool."""
    try:
        owner, repo = extract_repo_info(args["repo_url"])
        data_type = args["data_type"]
        start_date = args["start_date"]
        
        result = {}
        
        if data_type in ["commits", "all"]:
            commits_endpoint = f"repos/{owner}/{repo}/commits"
            commits_params = {"since": f"{start_date}T00:00:00Z"}
            result["commits"] = github_api_request(commits_endpoint, commits_params)
            
        if data_type in ["issues", "all"]:
            issues_endpoint = f"repos/{owner}/{repo}/issues"
            issues_params = {"state": "all", "since": f"{start_date}T00:00:00Z"}
            result["issues"] = github_api_request(issues_endpoint, issues_params)
            
        if data_type in ["pull_requests", "all"]:
            prs_endpoint = f"repos/{owner}/{repo}/pulls"
            prs_params = {"state": "all"}
            result["pull_requests"] = github_api_request(prs_endpoint, prs_params)
        
        return json.dumps(result)
    
    except Exception as e:
        return f"Error: {str(e)}"

tool_handlers = {
    "fetch_github_data": fetch_github_data_handler
}