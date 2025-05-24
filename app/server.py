"""
Hacker News MCP Server

This server implements a Model Context Protocol (MCP) interface for the Hacker News API.
It supports multiple operational modes including HTTP Streamable, STDIO/MCP, and SSE/MCP.
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import logging

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("hacker-news-mcp")

# Initialize the MCP server
mcp = FastMCP(
    name="Hacker News MCP",
    description="MCP server for accessing Hacker News data and functionality",
)

# Base URL for the Hacker News API
HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"

# API key configuration (optional, for future use)
API_KEY = os.getenv("HN_API_KEY", "")

# Client for making HTTP requests
http_client = httpx.AsyncClient(timeout=30.0)

# ----- Models -----

class Item(BaseModel):
    """Base model for Hacker News items"""
    id: int = Field(description="The item's unique id")
    type: Optional[str] = Field(None, description="The type of item. One of 'job', 'story', 'comment', 'poll', or 'pollopt'")
    deleted: Optional[bool] = Field(None, description="True if the item is deleted")
    by: Optional[str] = Field(None, description="The username of the item's author")
    time: Optional[int] = Field(None, description="Creation date of the item, in Unix Time")
    text: Optional[str] = Field(None, description="The comment, story or poll text. HTML")
    dead: Optional[bool] = Field(None, description="True if the item is dead")
    parent: Optional[int] = Field(None, description="The comment's parent: either another comment or the relevant story")
    poll: Optional[int] = Field(None, description="The pollopt's associated poll")
    kids: Optional[List[int]] = Field(None, description="The IDs of the item's comments, in ranked display order")
    url: Optional[str] = Field(None, description="The URL of the story")
    score: Optional[int] = Field(None, description="The story's score, or the votes for a pollopt")
    title: Optional[str] = Field(None, description="The title of the story, poll or job. HTML")
    parts: Optional[List[int]] = Field(None, description="A list of related pollopts, in display order")
    descendants: Optional[int] = Field(None, description="In the case of stories or polls, the total comment count")

class User(BaseModel):
    """Model for Hacker News user"""
    id: str = Field(description="The user's unique username. Case-sensitive")
    created: Optional[int] = Field(None, description="Creation date of the user, in Unix Time")
    karma: Optional[int] = Field(None, description="The user's karma")
    about: Optional[str] = Field(None, description="The user's optional self-description. HTML")
    submitted: Optional[List[int]] = Field(None, description="List of the user's stories, polls and comments")

class UpdatesResponse(BaseModel):
    """Model for updates response"""
    items: List[int] = Field(description="IDs of changed items")
    profiles: List[str] = Field(description="IDs of changed profiles")

# ----- API Helpers -----

async def fetch_hn_data(endpoint: str, params: Optional[Dict[str, str]] = None) -> Any:
    """
    Fetch data from the Hacker News API.
    
    Args:
        endpoint: The API endpoint to fetch from
        params: Optional query parameters
        
    Returns:
        The JSON response from the API
    """
    url = f"{HN_API_BASE_URL}/{endpoint}"
    try:
        response = await http_client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        raise Exception(f"Failed to fetch data from Hacker News API: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise Exception(f"An unexpected error occurred: {e}")

# ----- Tools -----

@mcp.tool()
async def get_item(id: int) -> Item:
    """
    Get a Hacker News item by its ID.
    
    Args:
        id: The unique ID of the item to retrieve
        
    Returns:
        The item data
    """
    data = await fetch_hn_data(f"item/{id}.json")
    if not data:
        raise Exception(f"Item with ID {id} not found")
    return Item(**data)

@mcp.tool()
async def find_stories_by_title(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Find Hacker News stories that match a title query or keywords.
    
    Args:
        query: The search query to match against story titles
        limit: Maximum number of matching stories to return (default: 5)
        
    Returns:
        List of matching stories with their IDs and titles
    """
    # First get the top and new stories as our search corpus
    top_ids = await fetch_hn_data("topstories.json")
    new_ids = await fetch_hn_data("newstories.json")
    
    # Combine and deduplicate
    all_ids = list(dict.fromkeys(top_ids + new_ids))
    
    # Limit to first 200 stories for performance
    all_ids = all_ids[:200]
    
    # Normalize the query for case-insensitive matching
    query_terms = query.lower().split()
    
    # Store matching stories
    matches = []
    
    for story_id in all_ids:
        if len(matches) >= limit:
            break
            
        try:
            data = await fetch_hn_data(f"item/{story_id}.json")
            
            # Skip if not a story or no title
            if data.get("type") != "story" or not data.get("title"):
                continue
                
            title = data.get("title", "").lower()
            
            # Check if all query terms appear in the title
            if all(term in title for term in query_terms):
                matches.append({
                    "id": story_id,
                    "title": data.get("title"),
                    "url": data.get("url"),
                    "score": data.get("score"),
                    "by": data.get("by"),
                    "time": data.get("time"),
                    "descendants": data.get("descendants")
                })
        except Exception as e:
            logger.error(f"Error checking story {story_id}: {e}")
    
    return matches

@mcp.tool()
async def get_user(id: str) -> User:
    """
    Get a Hacker News user by their ID.
    
    Args:
        id: The unique username of the user to retrieve
        
    Returns:
        The user data
    """
    data = await fetch_hn_data(f"user/{id}.json")
    if not data:
        raise Exception(f"User with ID {id} not found")
    return User(**data)

@mcp.tool()
async def get_max_item_id() -> int:
    """
    Get the current largest item ID.
    
    Returns:
        The maximum item ID
    """
    return await fetch_hn_data("maxitem.json")

@mcp.tool()
async def get_top_stories(limit: Optional[int] = 30) -> List[int]:
    """
    Get the top stories from Hacker News.
    
    Args:
        limit: Maximum number of stories to return (default: 30, max: 500)
        
    Returns:
        List of story IDs
    """
    limit = min(limit, 500)  # Ensure limit doesn't exceed 500
    stories = await fetch_hn_data("topstories.json")
    return stories[:limit]

@mcp.tool()
async def get_new_stories(limit: Optional[int] = 30) -> List[int]:
    """
    Get the newest stories from Hacker News.
    
    Args:
        limit: Maximum number of stories to return (default: 30, max: 500)
        
    Returns:
        List of story IDs
    """
    limit = min(limit, 500)  # Ensure limit doesn't exceed 500
    stories = await fetch_hn_data("newstories.json")
    return stories[:limit]

@mcp.tool()
async def get_best_stories(limit: Optional[int] = 30) -> List[int]:
    """
    Get the best stories from Hacker News.
    
    Args:
        limit: Maximum number of stories to return (default: 30, max: 500)
        
    Returns:
        List of story IDs
    """
    limit = min(limit, 500)  # Ensure limit doesn't exceed 500
    stories = await fetch_hn_data("beststories.json")
    return stories[:limit]

@mcp.tool()
async def get_ask_stories(limit: Optional[int] = 30) -> List[int]:
    """
    Get the latest Ask HN stories.
    
    Args:
        limit: Maximum number of stories to return (default: 30, max: 200)
        
    Returns:
        List of story IDs
    """
    limit = min(limit, 200)  # Ensure limit doesn't exceed 200
    stories = await fetch_hn_data("askstories.json")
    return stories[:limit]

@mcp.tool()
async def get_show_stories(limit: Optional[int] = 30) -> List[int]:
    """
    Get the latest Show HN stories.
    
    Args:
        limit: Maximum number of stories to return (default: 30, max: 200)
        
    Returns:
        List of story IDs
    """
    limit = min(limit, 200)  # Ensure limit doesn't exceed 200
    stories = await fetch_hn_data("showstories.json")
    return stories[:limit]

@mcp.tool()
async def get_job_stories(limit: Optional[int] = 30) -> List[int]:
    """
    Get the latest job stories.
    
    Args:
        limit: Maximum number of stories to return (default: 30, max: 200)
        
    Returns:
        List of story IDs
    """
    limit = min(limit, 200)  # Ensure limit doesn't exceed 200
    stories = await fetch_hn_data("jobstories.json")
    return stories[:limit]

@mcp.tool()
async def get_updates() -> UpdatesResponse:
    """
    Get the latest item and profile changes.
    
    Returns:
        Object containing changed items and profiles
    """
    data = await fetch_hn_data("updates.json")
    return UpdatesResponse(**data)

@mcp.tool()
async def get_story_with_comments(story_id: int, comment_limit: int = 10) -> Dict[str, Any]:
    """
    Get a story with its top comments.

    Args:
        story_id: The ID of the story
        comment_limit: Maximum number of top-level comments to include
        
    Returns:
        Story data with comments
    """
    # Get the story
    story = await get_item(story_id)
    story_data = story.model_dump()
    
    # Get comments if present
    comments = []
    if story.kids:
        for kid_id in story.kids[:comment_limit]:
            try:
                comment = await get_item(kid_id)
                comments.append(comment.model_dump())
            except Exception as e:
                logger.error(f"Error fetching comment {kid_id}: {e}")
    
    return {
        "story": story_data,
        "comments": comments
    }

@mcp.tool()
async def get_story_by_title(title: str) -> Dict[str, Any]:
    """
    Find and retrieve a story by its title or keywords, along with its comments.
    
    Args:
        title: The title or keywords to search for
        
    Returns:
        Story data with comments, or None if no matching story is found
    """
    # Find stories matching the title
    matching_stories = await find_stories_by_title(title, limit=1)
    
    if not matching_stories:
        return {
            "found": False,
            "message": f"No stories found matching '{title}'"
        }
    
    # Get the first matching story with comments
    story = matching_stories[0]
    story_with_comments = await get_story_with_comments(story["id"])
    
    return {
        "found": True,
        "story_id": story["id"],
        "title": story["title"],
        **story_with_comments
    }

@mcp.tool()
async def search_by_date(days_ago: int = 1, limit: Optional[int] = 30) -> List[Dict[str, Any]]:
    """
    Search for stories from approximately N days ago.
    
    Args:
        days_ago: Number of days ago to search for
        limit: Maximum number of stories to return
        
    Returns:
        List of stories from that time period
    """
    # Get current max item
    max_id = await get_max_item_id()
    
    # Approximate items per day (very rough estimate)
    items_per_day = 20000
    
    # Estimate the item ID from days_ago
    target_id = max(1, max_id - (days_ago * items_per_day))
    
    # Collect stories around that ID
    stories = []
    checked = 0
    current_id = target_id
    
    # Search in both directions from the estimated ID
    while len(stories) < limit and checked < limit * 10:
        try:
            item = await get_item(current_id)
            if item.type == "story" and not item.deleted and not item.dead:
                stories.append(item.model_dump())
            
            # Alternate between going up and down from the target ID
            if checked % 2 == 0:
                current_id = target_id + (checked // 2) + 1
            else:
                current_id = target_id - (checked // 2) - 1
                
            checked += 1
        except Exception:
            checked += 1
            continue
    
    return stories[:limit]

# ----- Resources -----

@mcp.resource("hn://item/{id}")
async def item_resource(id: int) -> Dict[str, Any]:
    """
    Resource for retrieving a Hacker News item by ID.
    
    Args:
        id: The unique ID of the item
        
    Returns:
        The item data
    """
    item = await get_item(id)
    return {"item": item.model_dump()}

@mcp.resource("hn://user/{id}")
async def user_resource(id: str) -> Dict[str, Any]:
    """
    Resource for retrieving a Hacker News user by ID.
    
    Args:
        id: The unique username of the user
        
    Returns:
        The user data
    """
    user = await get_user(id)
    return {"user": user.model_dump()}

@mcp.resource("hn://top/{limit}")
async def top_stories_resource(limit: int = 30) -> Dict[str, Any]:
    """
    Resource for retrieving the top stories.
    
    Args:
        limit: Maximum number of stories to return
        
    Returns:
        The top stories
    """
    story_ids = await get_top_stories(limit)
    stories = []
    
    for story_id in story_ids[:min(limit, 10)]:  # Limit to 10 full stories to avoid overloading
        try:
            story = await get_item(story_id)
            stories.append(story.model_dump())
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    return {
        "story_ids": story_ids,
        "stories": stories,
    }

@mcp.resource("hn://best/{limit}")
async def best_stories_resource(limit: int = 30) -> Dict[str, Any]:
    """
    Resource for retrieving the best stories.
    
    Args:
        limit: Maximum number of stories to return
        
    Returns:
        The best stories
    """
    story_ids = await get_best_stories(limit)
    stories = []
    
    for story_id in story_ids[:min(limit, 10)]:  # Limit to 10 full stories to avoid overloading
        try:
            story = await get_item(story_id)
            stories.append(story.model_dump())
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    return {
        "story_ids": story_ids,
        "stories": stories,
    }

@mcp.resource("hn://new/{limit}")
async def new_stories_resource(limit: int = 30) -> Dict[str, Any]:
    """
    Resource for retrieving the newest stories.
    
    Args:
        limit: Maximum number of stories to return
        
    Returns:
        The newest stories
    """
    story_ids = await get_new_stories(limit)
    stories = []
    
    for story_id in story_ids[:min(limit, 10)]:  # Limit to 10 full stories to avoid overloading
        try:
            story = await get_item(story_id)
            stories.append(story.model_dump())
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    return {
        "story_ids": story_ids,
        "stories": stories,
    }

@mcp.resource("hn://ask/{limit}")
async def ask_stories_resource(limit: int = 30) -> Dict[str, Any]:
    """
    Resource for retrieving Ask HN stories.
    
    Args:
        limit: Maximum number of stories to return
        
    Returns:
        Ask HN stories
    """
    story_ids = await get_ask_stories(limit)
    stories = []
    
    for story_id in story_ids[:min(limit, 10)]:  # Limit to 10 full stories to avoid overloading
        try:
            story = await get_item(story_id)
            stories.append(story.model_dump())
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    return {
        "story_ids": story_ids,
        "stories": stories,
    }

@mcp.resource("hn://show/{limit}")
async def show_stories_resource(limit: int = 30) -> Dict[str, Any]:
    """
    Resource for retrieving Show HN stories.
    
    Args:
        limit: Maximum number of stories to return
        
    Returns:
        Show HN stories
    """
    story_ids = await get_show_stories(limit)
    stories = []
    
    for story_id in story_ids[:min(limit, 10)]:  # Limit to 10 full stories to avoid overloading
        try:
            story = await get_item(story_id)
            stories.append(story.model_dump())
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    return {
        "story_ids": story_ids,
        "stories": stories,
    }

@mcp.resource("hn://jobs/{limit}")
async def job_stories_resource(limit: int = 30) -> Dict[str, Any]:
    """
    Resource for retrieving job stories.
    
    Args:
        limit: Maximum number of stories to return
        
    Returns:
        Job stories
    """
    story_ids = await get_job_stories(limit)
    stories = []
    
    for story_id in story_ids[:min(limit, 10)]:  # Limit to 10 full stories to avoid overloading
        try:
            story = await get_item(story_id)
            stories.append(story.model_dump())
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    return {
        "story_ids": story_ids,
        "stories": stories,
    }

# ----- Prompts -----

@mcp.prompt()
def hn_story_summary_by_id(story_id: int) -> str:
    """
    Creates a prompt template for the LLM to summarize a Hacker News story by ID.
    
    When a user makes a simple request like:
    "Summarize HN story 12345" or "What's the gist of this thread: https://news.ycombinator.com/item?id=12345"
    this function generates a detailed template that guides the LLM's response.
    
    Note: This is NOT what the user types. The user makes a simple request, and this
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        story_id: The ID of the Hacker News story to summarize
    """
    return f"Please provide a concise summary of Hacker News story {story_id} and its key discussion points. Include the main topic, major perspectives from comments, any consensus or disagreements, and interesting insights."

@mcp.prompt()
def hn_story_summary_by_title(title: str) -> str:
    """
    Creates a prompt template for the LLM to summarize a Hacker News story by title.
    
    When a user makes a simple request like:
    "Summarize that HN story about quantum computing" or 
    "What's the discussion like on the thread about Apple's new AI features?"
    this function generates a detailed template that guides the LLM's response.
    
    Note: This is NOT what the user types. The user makes a simple request, and this
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        title: Keywords or title to identify the story
    """
    return f"Please provide a concise summary of the Hacker News story about '{title}' and its key discussion points. Include the main topic, major perspectives from comments, any consensus or disagreements, and interesting insights."

@mcp.prompt()
def hn_story_summary_detailed_by_id(story_id: int) -> str:
    """
    Creates a detailed prompt template for the LLM to analyze a Hacker News story by ID.
    
    When a user makes a simple request like:
    "Give me a detailed analysis of HN story 12345" or "What's the full breakdown of
    the discussion on this HN post: https://news.ycombinator.com/item?id=12345"
    this function generates a detailed template that guides the LLM's response.
    
    Note: This is NOT what the user types. The user makes a simple request, and this
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        story_id: The ID of the Hacker News story to analyze in detail
    """
    return f"Please provide a comprehensive analysis of Hacker News story {story_id} and its discussion. Include a thorough summary of the content, analysis of major themes in comments, notable expert opinions, points of agreement and disagreement, technical details shared, and relevant context. Organize your response with clear sections."

@mcp.prompt()
def hn_story_summary_detailed_by_title(title: str) -> str:
    """
    Creates a detailed prompt template for the LLM to analyze a Hacker News story by title.
    
    When a user makes a simple request like:
    "I want a detailed breakdown of that HN discussion about blockchain security" or
    "Can you do a comprehensive analysis of the thread on AI regulation?"
    this function generates a detailed template that guides the LLM's response.
    
    Note: This is NOT what the user types. The user makes a simple request, and this
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        title: Keywords or title to identify the story
    """
    return f"Please provide a comprehensive analysis of the Hacker News story about '{title}' and its discussion. Include a thorough summary of the content, analysis of major themes in comments, notable expert opinions, points of agreement and disagreement, technical details shared, and relevant context. Organize your response with clear sections."

@mcp.prompt()
def hn_trending_topics(limit: int = 30, story_type: str = "top") -> str:
    """
    Creates a prompt template for the LLM to identify trending topics on Hacker News.
    
    When a user makes a simple request like:
    "What's trending on Hacker News?" or "What are the main topics on HN today?"
    or "What's popular in Show HN right now?"
    this function generates a detailed template that guides the LLM's response.
    
    Note: This is NOT what the user types. The user makes a simple request, and this
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        limit: The number of stories to analyze (default: 30)
        story_type: The type of stories to analyze (top, new, best, ask, show) (default: top)
    """
    story_type_desc = {
        "top": "top",
        "new": "newest",
        "best": "best",
        "ask": "Ask HN",
        "show": "Show HN"
    }.get(story_type, "top")
    
    return f"Please identify 3-5 major trending topics or themes from the {limit} {story_type_desc} Hacker News stories. For each topic, list the relevant stories and explain why this is trending. Note any significant patterns in the types of stories currently popular."

@mcp.prompt()
def hn_user_profile_analysis(username: str) -> str:
    """
    Creates a prompt template for the LLM to analyze a Hacker News user's profile.
    
    When a user makes a simple request like:
    "Tell me about HN user 'dang'" or "What topics does 'pg' write about on Hacker News?"
    this function generates a detailed template that guides the LLM's response.
    
    Note: This is NOT what the user types. The user makes a simple request, and this
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        username: The username of the Hacker News user to analyze
    """
    return f"Please analyze the Hacker News profile for user '{username}'. Summarize their activity and interests based on submissions and comments, identify key topics they engage with, note any expertise areas they demonstrate, and analyze their interaction style and community engagement. Provide a thoughtful analysis while respecting the user's privacy."

# ----- Lifecycle Management -----

# Setup and teardown functions
async def setup():
    """Setup resources before server starts"""
    logger.info("Setting up Hacker News MCP Server resources")
    # Any initialization code can go here

async def teardown():
    """Clean up resources when server stops"""
    logger.info("Cleaning up Hacker News MCP Server resources")
    # Close the HTTP client
    await http_client.aclose()

# ----- Custom Routes -----

# ----- Health Check Endpoint -----

# We'll implement the health check endpoint when creating the HTTP app
async def health_check():
    """Health check endpoint"""
    # Check if we can connect to the Hacker News API
    try:
        await fetch_hn_data("maxitem.json")
        status = "healthy"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        status = "unhealthy"
    
    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "service": "hacker-news-mcp"
    }

# ----- Server Configuration -----

def main():
    """Main entry point for the server."""
    import argparse
    import asyncio
    import uvicorn
    import threading
    from fastapi import FastAPI
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Hacker News MCP Server")
    parser.add_argument("--transport", type=str, default="sse", 
                        choices=["stdio", "sse"],
                        help="Transport protocol to use (stdio or sse)")
    parser.add_argument("--host", type=str, default="127.0.0.1", 
                        help="Host to bind to (for HTTP transports)")
    parser.add_argument("--port", type=int, default=8000, 
                        help="Port to bind to (for HTTP transports)")
    parser.add_argument("--log-level", type=str, default="info",
                        choices=["debug", "info", "warning", "error", "critical"],
                        help="Logging level")
    
    args = parser.parse_args()
    
    # Set log level
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)
    
    # Run the server with the specified transport
    if args.transport == "stdio":
        # For stdio transport, just run the MCP server directly
        asyncio.run(setup())
        mcp.run(transport="stdio")
        # Call teardown function directly for stdio transport
        asyncio.run(teardown())
    
    elif args.transport == "sse":
        # For SSE transport, we need to set up a FastAPI app
        from fastapi import FastAPI
        from fastapi.openapi.utils import get_openapi
        
        # Run setup
        asyncio.run(setup())
        
        # Create a FastAPI app
        app = FastAPI(
            title="Hacker News API",
            description="API and MCP server for accessing Hacker News data and functionality",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add health check endpoint
        @app.get("/health", tags=["System"], 
                 summary="Health check endpoint",
                 description="Check if the server is healthy and can connect to the Hacker News API")
        async def health_endpoint():
            try:
                max_id = await fetch_hn_data("maxitem.json")
                return {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "service": "hacker-news-mcp",
                    "max_item_id": max_id
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "unhealthy",
                        "timestamp": datetime.now().isoformat(),
                        "service": "hacker-news-mcp",
                        "error": str(e)
                    }
                )
        
        # --- Item Endpoints ---
        @app.get("/api/item/{item_id}", tags=["Items"], response_model=Item,
                summary="Get a Hacker News item by ID",
                description="Retrieve a Hacker News item (story, comment, job, etc.) by its unique ID")
        async def api_get_item(item_id: int):
            return await get_item(item_id)
            
        @app.get("/api/user/{username}", tags=["Users"], response_model=User,
                summary="Get a Hacker News user by username",
                description="Retrieve a Hacker News user profile by their unique username")
        async def api_get_user(username: str):
            return await get_user(username)
            
        @app.get("/api/maxitem", tags=["Items"], 
                summary="Get the maximum item ID",
                description="Get the current largest item ID from Hacker News")
        async def api_get_max_item_id():
            return await get_max_item_id()
            
        # --- Story Listings ---
        @app.get("/api/stories/top", tags=["Stories"], 
                summary="Get top stories",
                description="Get the top stories from Hacker News")
        async def api_get_top_stories(limit: Optional[int] = 30):
            return await get_top_stories(limit)
            
        @app.get("/api/stories/new", tags=["Stories"], 
                summary="Get new stories",
                description="Get the newest stories from Hacker News")
        async def api_get_new_stories(limit: Optional[int] = 30):
            return await get_new_stories(limit)
            
        @app.get("/api/stories/best", tags=["Stories"], 
                summary="Get best stories",
                description="Get the best stories from Hacker News")
        async def api_get_best_stories(limit: Optional[int] = 30):
            return await get_best_stories(limit)
            
        @app.get("/api/stories/ask", tags=["Stories"], 
                summary="Get Ask HN stories",
                description="Get the latest Ask HN stories")
        async def api_get_ask_stories(limit: Optional[int] = 30):
            return await get_ask_stories(limit)
            
        @app.get("/api/stories/show", tags=["Stories"], 
                summary="Get Show HN stories",
                description="Get the latest Show HN stories")
        async def api_get_show_stories(limit: Optional[int] = 30):
            return await get_show_stories(limit)
            
        @app.get("/api/stories/job", tags=["Stories"], 
                summary="Get job stories",
                description="Get the latest job stories from Hacker News")
        async def api_get_job_stories(limit: Optional[int] = 30):
            return await get_job_stories(limit)
            
        # --- Advanced Story Retrieval ---
        @app.get("/api/story/{story_id}/comments", tags=["Stories"], 
                summary="Get a story with comments",
                description="Get a story with its top comments")
        async def api_get_story_with_comments(story_id: int, comment_limit: int = 10):
            return await get_story_with_comments(story_id, comment_limit)
            
        @app.get("/api/stories/search", tags=["Search"], 
                summary="Find stories by title",
                description="Find Hacker News stories that match a title query or keywords")
        async def api_find_stories_by_title(query: str, limit: int = 5):
            return await find_stories_by_title(query, limit)
            
        @app.get("/api/story/by-title", tags=["Search"], 
                summary="Get a story by title",
                description="Find and retrieve a story by its title or keywords, along with its comments")
        async def api_get_story_by_title(title: str):
            return await get_story_by_title(title)
            
        # --- Other Endpoints ---
        @app.get("/api/updates", tags=["Updates"], response_model=UpdatesResponse,
                summary="Get latest updates",
                description="Get the latest item and profile changes from Hacker News")
        async def api_get_updates():
            return await get_updates()
            
        @app.get("/api/stories/by-date", tags=["Search"], 
                summary="Search stories by date",
                description="Search for stories from approximately N days ago")
        async def api_search_by_date(days_ago: int = 1, limit: Optional[int] = 30):
            return await search_by_date(days_ago, limit)
        
        # Register shutdown handler
        @app.on_event("shutdown")
        async def shutdown_event():
            await teardown()
        
        # Customize OpenAPI schema with tags
        def custom_openapi():
            if app.openapi_schema:
                return app.openapi_schema
            openapi_schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            openapi_schema["tags"] = [
                {"name": "Items", "description": "Operations related to Hacker News items (stories, comments, etc.)"},
                {"name": "Users", "description": "Operations related to Hacker News users"},
                {"name": "Stories", "description": "Operations related to story listings and retrieval"},
                {"name": "Search", "description": "Search operations for finding stories"},
                {"name": "Updates", "description": "Operations for getting updates from Hacker News"},
                {"name": "System", "description": "System operations like health checks"}
            ]
            app.openapi_schema = openapi_schema
            return app.openapi_schema
            
        app.openapi = custom_openapi
        
        # Add SSE endpoint information
        @app.get("/sse-info", tags=["System"],
                summary="SSE endpoint information",
                description="Get information about the SSE endpoint for MCP integration")
        async def sse_info():
            return {
                "sse_endpoint": f"http://{args.host}:{args.port}/sse",
                "description": "Server-Sent Events endpoint for MCP integration",
                "usage": "Connect to this endpoint to use the MCP protocol over SSE"
            }
        
        # Create a route for the SSE endpoint
        from starlette.responses import Response
        from starlette.background import BackgroundTask
        
        @app.get("/sse")
        async def sse_endpoint():
            # This is a simple SSE endpoint that FastMCP will use
            return Response(
                content="",
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream",
                }
            )
        
        # Start the FastMCP server in a separate thread
        def run_mcp_server():
            mcp.run(transport="stdio")
        
        # Start the MCP server in a background thread
        mcp_thread = threading.Thread(target=run_mcp_server)
        mcp_thread.daemon = True
        mcp_thread.start()
        
        # Print information about the server
        print(f"Starting Hacker News MCP Server with {args.transport} transport")
        print(f"Server will be available at: http://{args.host}:{args.port}")
        print(f"API documentation: http://{args.host}:{args.port}/docs")
        print(f"SSE endpoint: http://{args.host}:{args.port}/sse")
        
        # Run the FastAPI app with uvicorn
        uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())
    


if __name__ == "__main__":
    main()
