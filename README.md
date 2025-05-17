# HeyDev: Agentic DevRel Publisher

An AI-powered DevRel content publishing system that automatically analyzes GitHub repositories and generates relevant content.

## Features

- **GitHub Repository Analysis**: Automatically extract commits, issues, PRs, and doc changes
- **Topic Generation**: AI-generated content topics based on repository activity
- **Content Creation**: Generate blog posts, code examples, and social media content
- **Human-in-the-Loop**: Interactive UI for selecting topics and editing content
- **Content Storage**: Save finalized content to a PostgreSQL database

## Architecture

The system is built using:
- **Backend**: Python with CrewAI and CopilotKit
- **Frontend**: Next.js with CopilotKit React components
- **Database**: PostgreSQL for content storage

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL database
- OpenAI API key
- GitHub token (optional but recommended)

## Setup

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/heydev.git
cd heydev
```

2. **Setup the backend**

```bash
cd agent
# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
poetry lock && poetry install

# Run FastAPI backend
poetry run demo
```

3. **Setup the frontend**

```bash
# Repo root
npm install
```

4. **Configure environment variables**

Create a `.env` file in the `agent` directory with the following:

```
# OpenAI API Key
OPENAI_API_KEY=sk-your-api-key

# GitHub API Token (optional but recommended to avoid rate limiting)
GITHUB_TOKEN=ghp_your-github-token

# PostgreSQL Database URL
POSTGRESQL_URL=postgresql://username:password@localhost:5432/heydev_db

# Server Port
PORT=8000
```

## Running the Application

1. **Start the backend server**

```bash
cd agent
python -m sample_agent.demo
```

2. **Start the frontend development server**

```bash
cd src
npm run dev
```

3. **Access the application**

Open your browser and navigate to:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Usage

1. Enter a GitHub repository URL
2. Select the start date for analysis
3. Choose from AI-generated content topics
4. Edit and refine the generated content
5. Save and publish the content to your database

## Testing

Run the integration tests:

```bash
cd agent
python -m unittest tests.integration
```

## License

MIT
