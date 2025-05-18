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
from devrel_publisher.agent import DevRelPublisherFlow
from devrel_publisher.db import setup_database

from fastapi.middleware.cors import CORSMiddleware


# Initialize database tables
setup_database()

app = FastAPI()
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# sdk = CopilotKitRemoteEndpoint(
#     agents=[
#         CrewAIAgent(
#             name="devrel_publisher",
#             description="An agent that analyzes GitHub repos and generates DevRel content.",
#             flow=DevRelPublisherFlow(),
#         )
#     ],
# )

# implennt a basic flow


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

# health_endpoint = lambda: {"status": "ok"}

# add_fastapi_endpoint(app, health_endpoint,"/health")

def main():
    """Run the uvicorn server."""
    # port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "devrel_publisher.demo:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

if __name__ == "__main__":
    main()
