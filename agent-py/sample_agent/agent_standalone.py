"""
DevRel publishing agent that generates content from GitHub repo changes.
Standalone version without CopilotKit dependencies.
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

class DevRelAgentState:
    """
    State definition for the DevRel Publisher Agent.
    Tracks all data through the content generation process.
    """
    def __init__(self):
        # GitHub Repository Data
        self.repo_url = ""
        self.start_date = ""
        
        # Analysis Data
        self.commits = []
        self.issues = []
        self.pull_requests = []
        self.docs_changes = []
        
        # Generated Topics
        self.topics = []
        self.selected_topic = {}
        
        # Content Generation
        self.content_drafts = {
            "blog_post": "",
            "code_example": "",
            "social_media": ""
        }
        
        # Database Record
        self.content_record = {
            "channel": "",
            "title": "",
            "summary": "",
            "content": "",
            "type": ""
        }
        
        # Status and errors
        self.status = ""
        self.error = ""
        
        # For tracking messages
        self.messages = []

class DevRelPublisherFlow(Flow[DevRelAgentState]):
    """
    Flow implementation for the DevRel Publisher Agent.
    Handles the process from GitHub repository analysis to content publication.
    """
    
    @start()
    async def input_github_repo(self):
        """Entry point: Collect GitHub repository URL."""
        # This node will be called first and waits for user input
        # For standalone mode, we can pre-set these values
        return "select_date_range"
    
    @router(input_github_repo)
    async def select_date_range(self):
        """User selects date range for repository analysis."""
        # In standalone mode, use pre-defined values
        self.state.repo_url = "https://github.com/crewaiinc/crewai"
        self.state.start_date = "2025-05-10"
        print(f"Starting analysis for {self.state.repo_url} from {self.state.start_date}")
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
            
            # Show progress
            print("Analyzing repository...")
            
            # Fetch commits
            commits_endpoint = f"repos/{owner}/{repo}/commits"
            commits_params = {"since": f"{self.state.start_date}T00:00:00Z"}
            self.state.commits = github_api_request(commits_endpoint, commits_params)
            
            # Show progress
            print(f"Found {len(self.state.commits)} commits")
            
            # Fetch issues
            issues_endpoint = f"repos/{owner}/{repo}/issues"
            issues_params = {"state": "all", "since": f"{self.state.start_date}T00:00:00Z"}
            self.state.issues = github_api_request(issues_endpoint, issues_params)
            
            print(f"Found {len(self.state.issues)} issues")
            
            # Fetch pull requests
            prs_endpoint = f"repos/{owner}/{repo}/pulls"
            prs_params = {"state": "all"}
            self.state.pull_requests = [
                pr for pr in github_api_request(prs_endpoint, prs_params)
                if datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ") >= datetime.strptime(self.state.start_date, "%Y-%m-%d")
            ]
            
            print(f"Found {len(self.state.pull_requests)} pull requests")
            
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
            
            print(f"Found {len(self.state.docs_changes)} documentation changes")
            
            # If we have data, proceed to generate topics
            if (self.state.commits or self.state.issues or 
                self.state.pull_requests or self.state.docs_changes):
                return "generate_topics"
            
            # If no data found, go back to input
            return "input_github_repo"
            
        except Exception as e:
            # Handle errors
            self.state.error = str(e)
            print(f"Error analyzing repository: {str(e)}")
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
        
        print("Generating content topics...")
        
        # Use AI to analyze the data and generate topics
        response = await completion(
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
            stream=False
        )
        
        message = response.choices[0].message
        self.state.messages.append(message)
        
        # Process tool calls to extract topics
        if message.get("tool_calls"):
            for tool_call in message.get("tool_calls", []):
                if tool_call["function"]["name"] == "generate_topic":
                    try:
                        # Get raw arguments string
                        arguments_str = tool_call["function"]["arguments"]
                        
                        # Clean up potentially malformed JSON - find the first '{' and last '}'
                        start = arguments_str.find('{')
                        end = arguments_str.rfind('}') + 1
                        
                        if start != -1 and end > start:
                            # Extract valid JSON object
                            clean_json = arguments_str[start:end]
                            topic_data = json.loads(clean_json)
                            self.state.topics.append(topic_data)
                            print(f"Generated topic: {topic_data['title']}")
                        else:
                            # Fallback if we can't extract valid JSON
                            print(f"Warning: Could not extract valid JSON from: {arguments_str}")
                    except json.JSONDecodeError as e:
                        print(f"JSON parsing error: {e} in: {tool_call['function']['arguments']}")
                    except Exception as e:
                        print(f"Error processing tool call: {e}")
        
        # If we have topics, proceed to content generation
        if self.state.topics:
            return "generate_content_drafts"
        
        # If no topics were generated, retry
        print("No topics generated, retrying...")
        return "generate_topics"
    
    @router(generate_topics)
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
        
        print("Generating content draft...")
        
        # Get which content type to generate
        self.state.selected_topic = self.state.topics[0]
        content_type = self.state.selected_topic.get("content_types", ["blog_post"])[0]
        
        print(f"Selected topic: {self.state.selected_topic['title']}")
        print(f"Generating content type: {content_type}")
        
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
        response = await completion(
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
            tools=[WRITE_CONTENT_TOOL],
            stream=False
        )
        
        message = response.choices[0].message
        self.state.messages.append(message)
        
        # Process tool calls to extract content
        if message.get("tool_calls"):
            for tool_call in message.get("tool_calls", []):
                if tool_call["function"]["name"] == "write_content":
                    try:
                        # Get raw arguments string
                        arguments_str = tool_call["function"]["arguments"]
                        
                        # Clean up potentially malformed JSON
                        start = arguments_str.find('{')
                        end = arguments_str.rfind('}') + 1
                        
                        if start != -1 and end > start:
                            # Extract valid JSON object
                            clean_json = arguments_str[start:end]
                            content_data = json.loads(clean_json)
                            
                            self.state.content_drafts[content_type] = content_data.get("content", "")
                            
                            # Also save to content record
                            self.state.content_record = {
                                "channel": content_type,
                                "title": content_data.get("title", f"Article about {self.state.selected_topic.get('title', 'Topic')}"),
                                "summary": content_data.get("summary", ""),
                                "content": content_data.get("content", ""),
                                "type": content_type
                            }
                            
                            print(f"Generated content: {content_data.get('title')}")
                            print(f"Summary: {content_data.get('summary')}")
                        else:
                            # Fallback if we can't extract valid JSON
                            print(f"Warning: Could not extract valid JSON from: {arguments_str}")
                    except json.JSONDecodeError as e:
                        print(f"JSON parsing error: {e} in: {tool_call['function']['arguments']}")
                    except Exception as e:
                        print(f"Error processing tool call: {e}")
        
        return "save_to_database"
    
    @router(generate_content_drafts)
    async def save_to_database(self):
        """
        Save the final content to the database.
        Inserts a record into the content table.
        """
        try:
            # Use the database helper module to insert content
            from sample_agent.db import insert_content
            
            print("Saving content to database...")
            
            # Insert the content record and get the ID
            content_id = insert_content(self.state.content_record)
            
            # Update state with the new ID
            self.state.content_record["id"] = content_id
            
            print(f"Content saved with ID: {content_id}")
            
            return "flow_complete"
            
        except Exception as e:
            # Handle database errors
            self.state.error = str(e)
            print(f"Database error: {str(e)}")
            
            return "flow_complete"
    
    @listen("flow_complete")
    async def flow_complete(self):
        """End the flow."""
        print("Flow complete!")
        print(f"Content title: {self.state.content_record['title']}")
        print(f"Content summary: {self.state.content_record['summary']}")
        print("\nContent preview:")
        print(self.state.content_record['content'][:500] + "...")
        print("\nDone!")

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
        return json.dumps({"error": str(e)})

# Main entry point for standalone execution
# async def run_flow():
#     """Run the flow as a standalone process."""
    

if __name__ == "__main__":
    flow = DevRelPublisherFlow()
    # flow.state = DevRelAgentState()
    # await flow.start_flow()
    flow.kickoff()