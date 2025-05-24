"""
Example client for the Hacker News MCP Server.

This script demonstrates how to connect to and use the Hacker News MCP Server
with different transport protocols.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
import argparse
import logging

from fastmcp import Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("hn-mcp-client")

async def connect_and_list_tools(client: Client) -> List[Dict[str, Any]]:
    """Connect to the server and list available tools."""
    async with client:
        tools = await client.list_tools()
        logger.info(f"Found {len(tools)} tools")
        return [{"name": tool.name, "description": tool.description} for tool in tools]

async def get_top_stories(client: Client, limit: int = 5) -> List[int]:
    """Get top stories from Hacker News."""
    async with client:
        result = await client.call_tool("get_top_stories", {"limit": limit})
        return result

async def get_story_details(client: Client, story_id: int) -> Dict[str, Any]:
    """Get details of a specific story."""
    async with client:
        result = await client.call_tool("get_item", {"id": story_id})
        return result

async def get_story_with_comments(client: Client, story_id: int, comment_limit: int = 5) -> Dict[str, Any]:
    """Get a story with its comments."""
    async with client:
        result = await client.call_tool("get_story_with_comments", {
            "story_id": story_id,
            "comment_limit": comment_limit
        })
        return result

async def get_user_info(client: Client, user_id: str) -> Dict[str, Any]:
    """Get information about a user."""
    async with client:
        result = await client.call_tool("get_user", {"id": user_id})
        return result

async def read_resource(client: Client, resource_uri: str) -> Dict[str, Any]:
    """Read a resource from the server."""
    async with client:
        result = await client.read_resource(resource_uri)
        # Extract text content from the resource
        if result and hasattr(result[0], 'text'):
            return json.loads(result[0].text)
        return {}

async def run_demo(client: Client) -> None:
    """Run a comprehensive demo of the Hacker News MCP Server."""
    try:
        # List available tools
        tools = await connect_and_list_tools(client)
        print("\n=== Available Tools ===")
        for tool in tools:
            print(f"- {tool['name']}: {tool['description']}")
        
        # Get top stories
        print("\n=== Top Stories ===")
        top_stories = await get_top_stories(client, 5)
        print(f"Top story IDs: {top_stories}")
        
        if top_stories:
            # Get details of the first story
            story_id = top_stories[0]
            print(f"\n=== Story Details (ID: {story_id}) ===")
            story = await get_story_details(client, story_id)
            print(f"Title: {story.title}")
            print(f"By: {story.by}")
            print(f"Score: {story.score}")
            print(f"URL: {story.url}")
            
            # Get the story with comments
            print(f"\n=== Story with Comments (ID: {story_id}) ===")
            story_with_comments = await get_story_with_comments(client, story_id, 3)
            print(f"Title: {story_with_comments['title']}")
            print(f"Comments: {len(story_with_comments.get('fetched_comments', []))}")
            
            # Get user info if the story has an author
            if story.by:
                print(f"\n=== User Info (ID: {story.by}) ===")
                user = await get_user_info(client, story.by)
                print(f"Karma: {user.karma}")
                print(f"Created: {user.created}")
                print(f"Submissions: {len(user.submitted or [])} items")
            
            # Read a resource
            print("\n=== Resource Example ===")
            resource_data = await read_resource(client, f"hn://item/{story_id}")
            print(f"Resource data: {json.dumps(resource_data, indent=2)[:200]}...")
            
            # Read top stories resource
            print("\n=== Top Stories Resource ===")
            top_resource = await read_resource(client, "hn://top/3")
            print(f"Top stories: {len(top_resource.get('story_ids', []))}")
            print(f"Full stories: {len(top_resource.get('stories', []))}")
    
    except Exception as e:
        logger.error(f"Error during demo: {e}")
        raise

def main():
    """Main entry point for the client example."""
    parser = argparse.ArgumentParser(description="Hacker News MCP Client Example")
    parser.add_argument("--url", type=str, default="http://localhost:8000/mcp",
                        help="URL for HTTP transport (default: http://localhost:8000/mcp)")
    parser.add_argument("--transport", type=str, default="streamable-http",
                        choices=["streamable-http", "sse", "stdio"],
                        help="Transport protocol to use")
    parser.add_argument("--server-path", type=str, default=None,
                        help="Path to server script for stdio transport")
    
    args = parser.parse_args()
    
    # Create the appropriate client based on transport
    if args.transport == "stdio":
        if not args.server_path:
            print("Error: --server-path is required for stdio transport")
            return
        client = Client(args.server_path)
    else:
        # For HTTP-based transports
        client = Client(args.url)
    
    # Run the demo
    asyncio.run(run_demo(client))

if __name__ == "__main__":
    main()
