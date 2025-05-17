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
from sample_agent.agent import DevRelPublisherFlow
from sample_agent.db import setup_database

# Initialize database tables
setup_database()

app = FastAPI()
sdk = CopilotKitRemoteEndpoint(
    agents=[
        CrewAIAgent(
            name="devrel_publisher",
            description="An agent that analyzes GitHub repos and generates DevRel content.",
            flow=DevRelPublisherFlow(),
        )
    ],
)

add_fastapi_endpoint(app, sdk, "/copilotkit")

def main():
    """Run the uvicorn server."""
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "sample_agent.demo:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )

if __name__ == "__main__":
    main()
