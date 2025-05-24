<div align="center">

# 🚀 Hacker News MCP Server

**The easiest way to bring real-time Hacker News data and discussion into your LLM, agent, or app workflows.**

[![FastMCP](https://img.shields.io/badge/FastMCP-v2-blue)](https://fastmcp.readthedocs.io/)
[![Hacker News API](https://img.shields.io/badge/Hacker%20News-API-orange)](https://github.com/HackerNews/API)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

<!-- Optionally add a GIF or screenshot here -->
<!-- ![Demo](docs/demo.gif) -->

</div>

---

> **Instantly turn Hacker News into a programmable, conversational knowledge base for your AI agents and apps!**

---

## ✨ Why Use This?

- **Plug-and-play**: Instantly connect LLMs, agents, or chatbots to live Hacker News data and discussions.
- **Flexible**: Use as a local tool, cloud API, or containerized microservice.
- **Natural Language Friendly**: Users can reference stories by title, keywords, or natural language ("What are people saying about quantum computing?").
- **Rich Prompts**: Built-in prompt templates for summaries, trending topics, user analysis, and more.
- **Production Ready**: Robust error handling, health checks, and cloud deployment support out of the box.

---

## 🌟 Features

- ⚡ **Multiple Transport Modes**: STDIO/MCP and SSE/MCP for flexible LLM/agent integration
- 🌐 **REST/OpenAPI Endpoints**: Direct HTTP access with auto-generated docs
- 📰 **Full Hacker News Coverage**: Access stories, comments, users, trending topics, and more
- 🛡️ **Robust Error Handling**: Clear response models and status codes
- 🧩 **Easy Configuration**: Environment variables for API keys, host, and logging
- 🐳 **Container Ready**: Docker & Docker Compose for painless deployment
- ❤️ **Health Monitoring**: Built-in health check endpoint
- 🔒 **CORS Support**: Secure and configurable origins for web integration

---

## 📚 API Endpoints

All endpoints are available by default at `http://localhost:8000` (or your configured host/port).

### 🔎 REST API Endpoints

#### **Stories**
- `GET /api/stories/top?limit=30` — Get top stories
- `GET /api/stories/best?limit=30` — Get best stories
- `GET /api/stories/new?limit=30` — Get newest stories
- `GET /api/stories/ask?limit=30` — Get Ask HN stories
- `GET /api/stories/show?limit=30` — Get Show HN stories
- `GET /api/stories/search?query=YOUR_QUERY&limit=5` — Search for stories by title or keywords
- `GET /api/stories/by-date?days_ago=1&limit=30` — Get stories from N days ago

#### **Story Details**
- `GET /api/item/{item_id}` — Get a Hacker News item by ID
- `GET /api/story/by-title?title=YOUR_TITLE` — Get a story (and comments) by title/keywords
- `GET /api/story/{story_id}/comments?comment_limit=10` — Get a story and its top comments

#### **Users**
- `GET /api/user/{username}` — Get a Hacker News user by username

#### **System & Updates**
- `GET /api/maxitem` — Get the current largest item ID
- `GET /api/updates` — Get latest item and profile changes
- `GET /health` — Health check endpoint
- `GET /sse-info` — Info about the SSE endpoint

#### **SSE & MCP**
- `GET /sse` — Server-Sent Events (SSE) endpoint for MCP protocol

#### **OpenAPI & Docs**
- `GET /docs` — Swagger UI (interactive API docs)
- `GET /openapi.json` — OpenAPI schema (for tool integration)

### 🗣️ Natural Language & Title-Based Queries

You can search and retrieve stories using natural language or keywords, not just numeric IDs!

- **Example:**
    - `GET /api/stories/search?query=quantum computing` — Find stories about quantum computing
    - `GET /api/story/by-title?title=React framework` — Get the latest story and comments about React framework

- **Natural Language-Friendly:**
    - "Tell me about that story on quantum computing from yesterday"
    - "What's the discussion about the new React framework like?"

These queries are handled via `/api/stories/search` and `/api/story/by-title` endpoints.

### 🧑‍💻 Example Usage

**Search for stories by title/keywords:**
```bash
curl "http://localhost:8000/api/stories/search?query=AI+ethics&limit=3"
```
**Get a story and its comments by title:**
```bash
curl "http://localhost:8000/api/story/by-title?title=OpenAI+GPT-4"
```
**Health check:**
```bash
curl "http://localhost:8000/health"
```
**Get top stories:**
```bash
curl "http://localhost:8000/api/stories/top?limit=5"
```

See `/docs` for full interactive documentation and try endpoints live.

---

## 👤 Who Is This For?

- **LLM/AI Agent Developers**: Add real-world, up-to-date news and discussion to your agents.
- **Chatbot Builders**: Power your bots with trending stories and community insights.
- **Researchers & Data Scientists**: Analyze Hacker News trends, user activity, and topic sentiment.
- **Productivity Hackers**: Build custom dashboards, notification bots, or research tools.
- **Anyone who wants to make Hacker News programmable!**

> ℹ️ **Tip:** You don't need to know story IDs—just ask for stories by title, topic, or keywords!

---

## ⚡ Quick Start

> 🛠️ **Install in seconds, run anywhere!**

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/hacker-news-mcp.git
cd hacker-news-mcp

# Install dependencies
pip install -r requirements.txt
```

### 2. Running the Server

```bash
# Run with SSE transport (default, good for web/remote)
python run.py --transport sse --host 127.0.0.1 --port 8000

# Run with STDIO transport (for direct LLM/agent integration)
python run.py --transport stdio

# Optional: Run with custom log level
env LOG_LEVEL=debug python run.py --transport sse
```

### 3. 🚢 Docker Deployment

```bash
# Build and run with Docker
docker build -t hacker-news-mcp .
docker run -p 8000:8000 hacker-news-mcp

# Or use Docker Compose
docker-compose up -d
```

---

## 🛠️ MCP Configuration

> 💡 **Tip:** Works with Claude Desktop, Windsurf, Cursor IDE, and any LLM/agent supporting MCP!

### 🎛️ Claude Desktop Example

**STDIO (Local):**
```json
{
  "name": "Hacker News",
  "command": "python",
  "args": ["/path/to/hacker-news-mcp/run.py", "--transport", "stdio"],
  "env": { "LOG_LEVEL": "info" }
}
```

**SSE (Remote):**
```json
{
  "name": "Hacker News",
  "url": "https://your-deployed-server.com/sse",
  "transport": "sse"
}
```

### 🖥️ Windsurf/Cursor IDE Example

**STDIO (Local):**
```json
{
  "mcpServers": {
    "hackerNews": {
      "command": "python",
      "args": ["/path/to/hacker-news-mcp/run.py", "--transport", "stdio"],
      "env": { "LOG_LEVEL": "info" }
    }
  }
}
```

**SSE (Remote):**
```json
{
  "mcpServers": {
    "hackerNews": {
      "url": "https://your-deployed-server.com/sse",
      "transport": "sse"
    }
  }
}
```

---

## 🧰 Tools, Resources & Prompts

### 🛠️ Available Tools

- 🔎 **Basic Data Retrieval**
  - `get_item(id)`: Get a Hacker News item by ID
  - `get_user(id)`: Get a Hacker News user by ID
  - `get_max_item_id()`: Get the current largest item ID
- 🏆 **Story Listings**
  - `get_top_stories(limit)`: Get top stories
  - `get_best_stories(limit)`: Get best stories
  - `get_new_stories(limit)`: Get newest stories
  - `get_ask_stories(limit)`: Get Ask HN stories
  - `get_show_stories(limit)`: Get Show HN stories
  - `get_job_stories(limit)`: Get job stories
- 💬 **Advanced Story Retrieval**
  - `get_story_with_comments(story_id, comment_limit)`: Get a story with its comments
  - `find_stories_by_title(query, limit)`: Find stories by title or keywords
  - `get_story_by_title(title)`: Find and retrieve a story by its title or keywords with comments
- 🔄 **Other Tools**
  - `get_updates()`: Get latest item and profile changes
  - `search_by_date(days_ago, limit)`: Search for stories from approximately N days ago

### 📦 Resources

- 🧑‍💻 **Item Resources**
  - `hn://item/{id}`: Get item by ID
  - `hn://user/{id}`: Get user by ID
- 📋 **Story Listing Resources**
  - `hn://top/{limit}`: Get top stories
  - `hn://best/{limit}`: Get best stories
  - `hn://new/{limit}`: Get newest stories
  - `hn://ask/{limit}`: Get Ask HN stories
  - `hn://show/{limit}`: Get Show HN stories
  - `hn://jobs/{limit}`: Get job stories

### 🧠 Prompt Templates

> 💡 **Natural Language Friendly:** Users can reference stories by title, keywords, or just ask questions in plain English!

- 📝 **Story Analysis**
  - `hn_story_summary_by_id(story_id)`: Summarize a Hacker News story by ID
  - `hn_story_summary_by_title(title)`: Summarize a Hacker News story by title or keywords
  - `hn_story_summary_detailed_by_id(story_id)`: Detailed analysis by ID
  - `hn_story_summary_detailed_by_title(title)`: Detailed analysis by title
- 📈 **Trending & User Analysis**
  - `hn_trending_topics(limit, story_type)`: Identify trending topics
  - `hn_user_profile_analysis(username)`: Analyze a user's profile and submission history

#### 🗣️ Example User Requests

- "Summarize that HN story about quantum computing"
- "What's trending on Hacker News today?"
- "Tell me about HN user 'dang'"
- "Give me a detailed analysis of the discussion on AI regulation"

> ⚡ **No need for IDs!** Just ask naturally—this server matches your request to the right prompt and tools.

---

## API Documentation

When running with SSE transport, OpenAPI documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Configuration

### Environment Variables

- `HN_API_KEY`: API key for Hacker News (if required in the future)
- `LOG_LEVEL`: Logging level (debug, info, warning, error, critical)
- `FASTMCP_TOOL_ATTEMPT_PARSE_JSON_ARGS`: Set to 1 to enable JSON parsing for tool arguments

## Cloud Deployment

### Google Cloud Run Deployment

1. **Build and Push Docker Image**

```bash
# Build the Docker image
docker build -t gcr.io/your-project-id/hacker-news-mcp .

# Push to Google Container Registry
docker push gcr.io/your-project-id/hacker-news-mcp
```

2. **Deploy to Cloud Run**

```bash
gcloud run deploy hacker-news-mcp \
  --image gcr.io/your-project-id/hacker-news-mcp \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars="LOG_LEVEL=info"
```

3. **Configure MCP Consumers with Cloud Run URL**

After deployment, Cloud Run will provide a URL like `https://hacker-news-mcp-abcdef123-uc.a.run.app`. Use this URL in your MCP configuration:

```json
{
  "name": "Hacker News",
  "url": "https://hacker-news-mcp-abcdef123-uc.a.run.app/sse",
  "transport": "sse"
}
```

### AWS Lambda Deployment

1. **Package the Application**

```bash
# Create a deployment package
zip -r deployment.zip . -x "*.git*" -x "*.pytest_cache*" -x "__pycache__/*"
```

2. **Create Lambda Function with API Gateway**

- Create a Lambda function in the AWS Console
- Upload the deployment.zip package
- Configure an API Gateway trigger
- Set environment variables as needed

3. **Configure MCP Consumers with API Gateway URL**

Use the API Gateway URL in your MCP configuration:

```json
{
  "name": "Hacker News",
  "url": "https://abcdef123.execute-api.us-east-1.amazonaws.com/prod/sse",
  "transport": "sse"
}
```

## Integration Examples

### Python Client

```python
import asyncio
from fastmcp import Client
from fastmcp.client.transports import SSETransport
import json

async def main():
    # Connect to the server
    client = Client(SSETransport("http://localhost:8000/sse"))
    
    async with client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {len(tools)}")
        
        # Get top stories
        top_stories = await client.call_tool("get_top_stories", {"limit": 5})
        story_ids = json.loads(top_stories[0].text)
        print(f"Top stories: {story_ids}")
        
        # Get a specific story
        if story_ids:
            story_result = await client.call_tool("get_item", {"id": story_ids[0]})
            story_data = json.loads(story_result[0].text)
            print(f"Story: {story_data.get('title')}")

if __name__ == "__main__":
    asyncio.run(main())
```

### STDIO Integration

For LLM agents that support STDIO-based MCP servers:

```bash
# Run the server in STDIO mode
python run.py --transport stdio
```

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_server.py
```

### Manual Testing with the Test Client

```bash
# Start the server in one terminal
python run.py --transport sse

# Run the test client in another terminal
python test_client.py
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure the server is running and the port is correct
   - Check firewall settings

2. **Transport Not Supported**
   - Verify you're using a supported transport ("stdio" or "sse")

3. **JSON Parsing Errors**
   - For older LLMs, set `FASTMCP_TOOL_ATTEMPT_PARSE_JSON_ARGS=1`

4. **Missing Dependencies**
   - Run `pip install -r requirements.txt` to ensure all dependencies are installed

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPLv3) - see the LICENSE file for details.

The AGPLv3 is a copyleft license that requires anyone who distributes your code or a derivative work to make the source available under the same terms, and also extends this requirement to users who interact with the software over a network.

## Acknowledgements

- [Hacker News API](https://github.com/HackerNews/API)
- [FastMCP](https://fastmcp.readthedocs.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
