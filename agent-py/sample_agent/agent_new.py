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
import logging

from copilotkit.crewai import (
    copilotkit_stream, 
    copilotkit_predict_state,
    copilotkit_emit_state,
    copilotkit_exit,
    CopilotKitState
)

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DevRelPublisherFlow")

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
        "description": "Generate a blog post based on the selected topic",
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
    
    # Status and errors
    status: str = ""
    error: str = ""

class DevRelPublisherFlow(Flow[DevRelAgentState]):
    """
    Flow implementation for the DevRel Publisher Agent.
    Handles the process from GitHub repository analysis to content publication.
    """
    
    @start()
    async def input_github_repo(self):
        logger.info("Entered input_github_repo")
        """Entry point: Collect GitHub repository URL."""
        # This node will be called first and waits for user input
        # The state will be updated directly from frontend actions
    
    @router(input_github_repo)
    async def select_date_range(self):
        logger.info("Entered select_date_range")
        """Set hardcoded repository URL and date range."""
        # Hardcode the repository URL and start date
        self.state.repo_url = "https://github.com/crewaiinc/crewai"
        self.state.start_date = "2025-01-01"
        
        # Always proceed to analyze repository
        return "analyze_repository"
    
    @router(select_date_range)
    async def analyze_repository(self):
        logger.info("Entered analyze_repository")
        try:
            owner, repo = extract_repo_info(self.state.repo_url)
            await copilotkit_emit_state({"status": "Fetching pull requests..."})
            # Fetch pull requests only
            prs_endpoint = f"repos/{owner}/{repo}/pulls"
            prs_params = {"state": "all", "sort": "created", "direction": "desc"}
            all_prs = github_api_request(prs_endpoint, prs_params)
            self.state.pull_requests = [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "body": pr.get("body", ""),
                    "created_at": pr["created_at"],
                    "user": pr["user"]["login"]
                }
                for pr in all_prs
                if datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ") >= datetime.strptime(self.state.start_date, "%Y-%m-%d")
            ]
            await copilotkit_emit_state({
                "status": f"Found {len(self.state.pull_requests)} pull requests after {self.state.start_date}"
            })

            # Fetch issues
            issues_endpoint = f"repos/{owner}/{repo}/issues"
            issues_params = {"state": "all", "since": f"{self.state.start_date}T00:00:00Z"}
            self.state.issues = github_api_request(issues_endpoint, issues_params)
            await copilotkit_emit_state({
                "status": f"Found {len(self.state.issues)} issues"
            })

            # Fetch documentation changes (from PRs)
            docs_changes = []
            for pr in self.state.pull_requests:
                # For each PR, fetch the files changed
                pr_files_endpoint = f"repos/{owner}/{repo}/pulls/{pr['number']}/files"
                pr_files = github_api_request(pr_files_endpoint)
                doc_files = [f for f in pr_files if f["filename"].endswith(("CHANGELOG"))]
                if doc_files:
                    docs_changes.append({
                        "pr": pr,
                        "doc_files": doc_files
                    })
            self.state.docs_changes = docs_changes
            await copilotkit_emit_state({
                "status": f"Found {len(self.state.docs_changes)} documentation changes"
            })

            # If we have data, proceed to generate topics
            if (self.state.pull_requests or self.state.issues or self.state.docs_changes):
                return "generate_topics"
            return "input_github_repo"
        except Exception as e:
            self.state.error = str(e)
            raise e
            return "input_github_repo"
    
    @router(analyze_repository)
    async def generate_topics(self):
        logger.info("Entered generate_topics")
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
                        
                        Issues: {json.dumps([{
                            "number": i["number"],
                            "title": i["title"],
                            "state": i["state"],
                            "created_at": i["created_at"]
                        } for i in self.state.issues[:10]])}
                        
                        Pull Requests: {json.dumps([{
                            "number": p["number"],
                            "title": p["title"],
                            "state": p.get("state", "unknown"),
                            "created_at": p["created_at"]
                        } for p in self.state.pull_requests[:10]])}
                        
                        Doc Changes: {json.dumps([{
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
        message = sanitize_tool_call_arguments(message)
        self.state.messages.append(message)
        
        # Process tool calls to extract topics
        if message.get("tool_calls"):
            for tool_call in message.get("tool_calls", []):
                if tool_call["function"]["name"] == "generate_topic":
                    try:
                        arguments_str = tool_call["function"]["arguments"]
                        try:
                            topic_data = json.loads(arguments_str)
                        except json.JSONDecodeError:
                            # Use regex to extract the first {...} block
                            import re
                            match = re.search(r'\{.*?\}', arguments_str, re.DOTALL)
                            if match:
                                clean_json = match.group(0)
                                topic_data = json.loads(clean_json)
                            else:
                                print(f"Warning: Could not extract valid JSON from: {arguments_str}")
                                continue
                        self.state.topics.append(topic_data)
                    except Exception as e:
                        raise e
                        print(f"Error processing tool call: {e}")
        
        # If we have topics, proceed to content generation directly
        if self.state.topics:
            return "generate_content_drafts"
        
        # If no topics were generated, retry
        return "generate_topics"
    
    @router(generate_topics)
    async def generate_content_drafts(self):
        logger.info("Entered generate_content_drafts")
        """
        Generate content drafts based on the first topic.
        Creates drafts for blog posts, code examples, and social media.
        """
        system_prompt = """
        You are a DevRel content creator writing about technical topics.
        Create professional, engaging content for the selected topic.
        Generate content that clearly explains the technical details while
        keeping it accessible to the target audience. Include at least one 
        code snippet to demonstrate examples.
        
        Use the write_content tool to submit your draft.
        """
        
        # Use predictive state updates to show content being generated
        await copilotkit_predict_state({
            "content_drafts": {
                "tool_name": "write_content",
                "tool_argument": "content"
            }
        })
        
        # Automatically select the first topic if available
        if self.state.topics:
            self.state.selected_topic = self.state.topics[0]
            await copilotkit_emit_state({
                "status": f"Selected topic: {self.state.selected_topic.get('title', 'Unknown Topic')}"
            })
        else:
            # Create a default topic if none are available
            self.state.selected_topic = {
                "title": "Recent Repository Updates",
                "description": "Overview of recent changes in the repository",
                "source_type": "pull_request",
                "source_id": self.state.pull_requests[0]["number"] if self.state.pull_requests else "",
                "content_types": ["blog_post"]
            }
            await copilotkit_emit_state({
                "status": "No topics generated. Using default topic."
            })
        
        # Get which content type to generate
        content_type = self.state.selected_topic.get("content_types", ["blog_post"])[0]
        
        # Context from repository data
        context = {}
        source_type = self.state.selected_topic.get("source_type")
        source_id = self.state.selected_topic.get("source_id")
        
        if source_type == "issue" and self.state.issues:
            context = next((i for i in self.state.issues if str(i["number"]) == source_id), self.state.issues[0] if self.state.issues else {})
        elif source_type == "pull_request" and self.state.pull_requests:
            context = next((p for p in self.state.pull_requests if str(p["number"]) == source_id), self.state.pull_requests[0] if self.state.pull_requests else {})
        
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
        message = sanitize_tool_call_arguments(message)
        self.state.messages.append(message)
        
        # Process tool calls to extract content
        if message.get("tool_calls"):
            for tool_call in message.get("tool_calls", []):
                if tool_call["function"]["name"] == "write_content":
                    try:
                        # Get raw arguments string
                        arguments_str = tool_call["function"]["arguments"]
                        try:
                            content_data = json.loads(arguments_str)
                        except json.JSONDecodeError:
                            # Use regex to extract the first {...} block
                            import re
                            match = re.search(r'\{.*?\}', arguments_str, re.DOTALL)
                            if match:
                                clean_json = match.group(0)
                                content_data = json.loads(clean_json)
                            else:
                                print(f"Warning: Could not extract valid JSON from: {arguments_str}")
                                continue
                        self.state.content_drafts[content_type] = content_data.get("content", "")
                        # Also save to content record
                        self.state.content_record = {
                            "channel": content_type,
                            "title": content_data.get("title", f"Article about {self.state.selected_topic.get('title', 'Topic')}"),
                            "summary": content_data.get("summary", ""),
                            "content": content_data.get("content", ""),
                            "type": content_type
                        }
                    except Exception as e:
                        print(f"Error processing tool call: {e}")
                        raise e
                else:
                    raise Exception(f"Unknown tool call: {tool_call}")
        
        # Automatically proceed to content editing
        return "user_edits_content"
    
    @router(generate_content_drafts)
    async def user_edits_content(self):
        logger.info("Entered user_edits_content")
        """
        Automated: Apply any post-processing to content and proceed to save.
        """
        # Skip user edits and automatically proceed to save
        
        # Simply emit state update that we're proceeding
        await copilotkit_emit_state({
            "status": "Content preparation complete. Proceeding to save..."
        })
        
        # Proceed directly to saving
        return "save_to_database"
    
    @router(user_edits_content)
    async def save_to_database(self):
        logger.info("Entered save_to_database")
        """
        Save the final content to the database.
        Inserts a record into the content table.
        """
        try:
            # Use the database helper module to insert content
            from sample_agent.db import insert_content
            
            # Insert the content record and get the ID
            content_id = insert_content(self.state.content_record)
            
            # Check if insert was successful
            if content_id == -1:
                # Database operation failed but we can continue
                self.state.messages = sanitize_all_messages(self.state.messages)
                state_dict = self.state.__dict__ if hasattr(self.state, "__dict__") else dict(self.state)
                await copilotkit_emit_state({
                    **state_dict,
                    "status": "Database not available. Content generated but not saved."
                })
            else:
                # Update state with the new ID
                self.state.content_record["id"] = content_id
                
                # Emit state update with success message
                self.state.messages = sanitize_all_messages(self.state.messages)
                state_dict = self.state.__dict__ if hasattr(self.state, "__dict__") else dict(self.state)
                await copilotkit_emit_state({
                    **state_dict,
                    "status": f"Content saved to database with ID: {content_id}"
                })
            
            return "flow_complete"
            
        except Exception as e:
            # Handle database errors
            self.state.error = str(e)
            
            # Emit state update with error message
            self.state.messages = sanitize_all_messages(self.state.messages)
            state_dict = self.state.__dict__ if hasattr(self.state, "__dict__") else dict(self.state)
            await copilotkit_emit_state({
                **state_dict,
                "status": f"Database error: {str(e)}"
            })
            raise e
            
            # Still proceed to complete the flow
            return "flow_complete"
    
    @listen("flow_complete")
    async def flow_complete(self):
        # Optionally, you can log or print for debugging
        print("FLOW COMPLETE CALLED")

        # 1. Emit the final state (this will send the blog post to the frontend)
        self.state.messages = sanitize_all_messages(self.state.messages)
        state_dict = self.state.__dict__ if hasattr(self.state, "__dict__") else dict(self.state)
        await copilotkit_emit_state(state_dict)

        # 2. Explicitly exit the agent loop (recommended for clean session end)
        await copilotkit_exit()

        # 3. Do not return anything (or return None)
        return None

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
        raise e
        return f"Error: {str(e)}"

tool_handlers = {
    "fetch_github_data": fetch_github_data_handler
}

def sanitize_tool_call_arguments(message):
    """
    For each tool call in the message, ensure the arguments field is a valid JSON object (as a string).
    If not, extract the first JSON object using regex.
    """
    if "tool_calls" in message:
        for tool_call in message["tool_calls"]:
            args_str = tool_call["function"]["arguments"]
            try:
                # Try to parse as is
                json.loads(args_str)
            except json.JSONDecodeError:
                # Extract first {...} block
                match = re.search(r'\{.*?\}', args_str, re.DOTALL)
                if match:
                    clean_json = match.group(0)
                    tool_call["function"]["arguments"] = clean_json
                else:
                    # If no valid JSON, set to empty object
                    tool_call["function"]["arguments"] = "{}"
    return message

# Utility to sanitize all messages in a list
def sanitize_all_messages(messages):
    return [sanitize_tool_call_arguments(m) for m in messages]
