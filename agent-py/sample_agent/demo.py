"""
This serves the DevRel Publisher agent through FastAPI integration.
"""

import os
from dotenv import load_dotenv
load_dotenv() # pylint: disable=wrong-import-position

from fastapi import FastAPI
import uvicorn
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from copilotkit import CopilotKitRemoteEndpoint
from copilotkit.crewai import CrewAIAgent
from sample_agent.db import setup_database
from sample_agent.agent_new import DevRelPublisherFlow

# Initialize database tables
setup_database()

app = FastAPI()
sdk = CopilotKitRemoteEndpoint(
    agents=[
        CrewAIAgent(
            name="sample_agent",
            description="An agent that analyzes GitHub repos and generates DevRel content.",
            flow=DevRelPublisherFlow(),
        )
    ],
)

add_fastapi_endpoint(app, sdk, "/copilotkit")

def main():
    """Run the uvicorn server."""
    try:
        port = int(os.getenv("PORT", "8000"))
        print(f"Starting server on port {port}")
        uvicorn.run(
            "sample_agent.demo:app",
            host="0.0.0.0",
            port=port,
            reload=True,
        )
    except Exception as e:
        print(f"Server startup error: {str(e)}")
        import traceback
        traceback.print_exc()
        
if __name__ == "__main__":
    main()
