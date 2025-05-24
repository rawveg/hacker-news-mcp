#!/usr/bin/env python
"""
Simple test client for the Hacker News MCP Server.
"""

import asyncio
import json
from fastmcp import Client
from fastmcp.client.transports import SSETransport

async def test_server():
    """Test the Hacker News MCP Server."""
    # Create a client with SSE transport
    client = Client(SSETransport("http://127.0.0.1:8000/sse"))
    
    try:
        async with client:
            print("Connected to Hacker News MCP Server")
            
            # List available tools
            tools = await client.list_tools()
            print(f"Available tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            # Get max item ID
            max_id = await client.call_tool("get_max_item_id")
            print(f"Max item ID: {max_id}")
            
            # Get top stories
            top_stories = await client.call_tool("get_top_stories", {"limit": 5})
            print(f"Top stories: {top_stories}")
            
            # Get details of the first story
            if top_stories:
                # Extract the story ID from the TextContent object
                story_ids = json.loads(top_stories[0].text)
                if story_ids:
                    story_id = story_ids[0]
                    story_result = await client.call_tool("get_item", {"id": story_id})
                    
                    # Parse the story data from the TextContent object
                    story_data = json.loads(story_result[0].text)
                    print(f"Story: {story_data.get('title', 'No title')}")
                    print(f"By: {story_data.get('by', 'Unknown')}")
                    print(f"Score: {story_data.get('score', 0)}")
                    print(f"URL: {story_data.get('url', 'No URL')}")
                    print(f"Type: {story_data.get('type', 'Unknown')}")
                    print(f"Time: {story_data.get('time', 0)}")
                    
                    # If there are kids (comments), print their count
                    if 'kids' in story_data:
                        print(f"Comments: {len(story_data['kids'])}")
                    else:
                        print("Comments: 0")
            
            # Test resource access
            if top_stories:
                # Extract the story ID from the TextContent object
                story_ids = json.loads(top_stories[0].text)
                if story_ids:
                    story_id = story_ids[0]
                    resource = await client.read_resource(f"hn://item/{story_id}")
                    if resource and hasattr(resource[0], 'text'):
                        resource_data = json.loads(resource[0].text)
                        print(f"\nResource access:")
                        print(f"Item resource for ID {story_id}:")
                        print(json.dumps(resource_data, indent=2)[:200] + "...")
                    else:
                        print("\nResource access: No data returned")
                        
            # Try accessing top stories resource
            top_resource = await client.read_resource("hn://top/3")
            if top_resource and hasattr(top_resource[0], 'text'):
                top_data = json.loads(top_resource[0].text)
                print(f"\nTop stories resource:")
                print(f"Story IDs: {len(top_data.get('story_ids', []))}")
                print(f"Full stories: {len(top_data.get('stories', []))}")
            else:
                print("\nTop stories resource: No data returned")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_server())
