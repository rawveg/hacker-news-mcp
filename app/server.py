"""
Hacker News MCP Server

This server implements a Model Context Protocol (MCP) interface for the Hacker News API.
It supports multiple operational modes including HTTP Streamable, STDIO/MCP, and SSE/MCP.
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Union, Any, Literal
from datetime import datetime
import logging

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import html2text

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
    
class ContentResponse(BaseModel):
    """Model for content response"""
    title: str = Field(description="Title of the content")
    url: str = Field(description="URL of the content")
    content: str = Field(description="Content in text or markdown format")
    content_type: str = Field(description="Type of content (text, markdown, html)")
    story_id: int = Field(description="ID of the Hacker News story")
    by: Optional[str] = Field(None, description="Author of the story")
    time: Optional[int] = Field(None, description="Timestamp of the story")
    score: Optional[int] = Field(None, description="Score of the story")
    descendants: Optional[int] = Field(None, description="Number of comments")
    error: Optional[str] = Field(None, description="Error message if any")

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
async def hn_user_profile_analysis(username: str) -> str:
    """
    Creates a prompt template for the LLM to analyze a Hacker News user's profile.
    
    When a user makes a simple request like:
    "Tell me about HN user 'dang'" or "What topics does 'pg' write about on Hacker News?"
    
    This function extracts the username and creates a detailed prompt template. This
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        username: The username of the Hacker News user to analyze
    """
    # This function is already marked as async, but we need to properly await the get_user call
    user = await get_user(username)
    
    return f"""
    You are analyzing the Hacker News profile for user '{username}'.
    
    User data: {json.dumps(user.model_dump(), indent=2)}
    
    Based on this information, provide a comprehensive analysis of this user's activity, interests, and contributions to Hacker News.
    Consider factors such as:
    - Account age and karma level
    - Types of stories they submit or comment on
    - Common themes or topics in their activity
    - Their communication style and community engagement
    
    Format your response in a clear, organized manner with appropriate headings and bullet points where helpful.
    """

@mcp.prompt()
async def hn_story_content_by_id(story_id: int) -> str:
    """
    Creates a prompt template for the LLM to analyze the full content of a Hacker News story by ID.
    
    When a user makes a simple request like:
    "Show me the article from HN story 12345" or "What's the full content of that post about quantum computing?"
    
    This function fetches the story content and creates a detailed prompt template. This
    template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        story_id: The ID of the Hacker News story to retrieve content for
    """
    story_data = await get_item(story_id)
    content_data = await get_story_content(story_id, format="markdown")
    
    return f"""
    You are analyzing a Hacker News story and its linked content.
    
    ## Story Details
    Title: {story_data.title}
    Posted by: {story_data.by}
    Score: {story_data.score}
    URL: {story_data.url}
    Comments: {story_data.descendants}
    
    ## Article Content
    {content_data.get('content', 'No content available')}
    
    Please provide a comprehensive analysis of this content. Consider:
    - The main points and arguments presented
    - Key facts and information
    - The quality and credibility of the source
    - How this relates to current trends or discussions in technology
    
    Format your response in a clear, organized manner with appropriate headings and sections.
    """

@mcp.prompt()
async def hn_story_content_by_title(title: str) -> str:
    """
    Creates a prompt template for the LLM to analyze the full content of a Hacker News story by title.
    
    When a user makes a simple request like:
    "Show me the full article about quantum computing from HN" or "Get me the content of that story about AI ethics"
    
    This function searches for the story by title, fetches its content, and creates a detailed prompt template.
    This template is what gets sent to the LLM to help it generate a comprehensive response.
    
    Args:
        title: The title or keywords to identify the story
    """
    content_data = await get_story_content_by_title(title, format="markdown")
    
    if content_data.get('error'):
        return f"""
        You were asked to analyze a Hacker News story about "{title}", but no matching story was found.
        
        Please inform the user that you couldn't find a story matching that description and suggest they try:
        1. Using different keywords
        2. Being more specific about the story they're looking for
        3. Providing a story ID if they have it
        """
    
    return f"""
    You are analyzing a Hacker News story and its linked content.
    
    ## Story Details
    Title: {content_data.get('title', 'No title')}
    Posted by: {content_data.get('by', 'Unknown')}
    Score: {content_data.get('score', 'Unknown')}
    URL: {content_data.get('url', 'No URL')}
    Comments: {content_data.get('descendants', 'Unknown')}
    
    ## Article Content
    {content_data.get('content', 'No content available')}
    
    Please provide a comprehensive analysis of this content. Consider:
    - The main points and arguments presented
    - Key facts and information
    - The quality and credibility of the source
    - How this relates to current trends or discussions in technology
    
    Format your response in a clear, organized manner with appropriate headings and sections.
    """

# ----- Advanced Prompt Templates -----

@mcp.prompt()
async def hn_router(query: str) -> str:
    """
    A router prompt that analyzes the user's query and directs it to the appropriate specialized prompt.
    
    When a user makes any Hacker News related query, this function analyzes the intent
    and provides guidance on how to best respond using available tools and data.
    
    Args:
        query: The user's natural language query about Hacker News
    """
    # Get the latest top stories to provide context
    top_stories = await get_top_stories(10)
    story_data = []
    
    for story_id in top_stories[:5]:  # Limit to 5 for performance
        try:
            story = await get_item(story_id)
            story_data.append({
                "id": story_id,
                "title": story.title,
                "score": story.score,
                "by": story.by,
                "descendants": story.descendants
            })
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    return f"""
    You are an expert on Hacker News content and need to analyze the following user query:
    
    USER QUERY: "{query}"  
    
    Current top stories on Hacker News:
    {json.dumps(story_data, indent=2)}
    
    Based on the query, determine the most appropriate way to respond using the Hacker News MCP tools and data.
    
    First, identify the user's intent. Are they looking for:
    1. Information about specific stories (by ID or title)
    2. Content of articles linked from stories
    3. Comments or discussion analysis
    4. User profile information
    5. Trending topics or patterns
    6. Comparisons between stories
    7. Historical data or time-based analysis
    8. Something else (specify)
    
    Then, recommend the best approach to fulfill this request using available tools:
    - For specific stories: Use get_item() or find_stories_by_title()
    - For article content: Use get_story_content() or get_story_content_by_title()
    - For comments: Use get_story_with_comments()
    - For user profiles: Use get_user()
    - For trends: Analyze multiple stories from get_top_stories(), get_new_stories(), etc.
    
    Provide a detailed plan for how to best respond to this query, including which tools to use and how to process and present the information.
    """

@mcp.prompt()
async def hn_compare_stories(story_ids: List[int]) -> str:
    """
    Creates a prompt template for comparing multiple Hacker News stories.
    
    When a user makes a request like:
    "Compare HN stories 12345 and 67890" or "What's the difference between those two quantum computing articles?"
    
    Args:
        story_ids: List of story IDs to compare
    """
    stories_data = []
    
    for story_id in story_ids:
        try:
            story = await get_item(story_id)
            content_data = await get_story_content(story_id, format="markdown")
            
            stories_data.append({
                "id": story_id,
                "title": story.title,
                "by": story.by,
                "score": story.score,
                "url": story.url,
                "descendants": story.descendants,
                "content_excerpt": content_data.get("content", "No content available")[:500] + "..." if content_data.get("content") else "No content available"
            })
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
            stories_data.append({
                "id": story_id,
                "error": str(e)
            })
    
    return f"""
    You are comparing multiple Hacker News stories to identify similarities, differences, and relationships.
    
    ## Stories to Compare:
    {json.dumps(stories_data, indent=2)}
    
    Please provide a comprehensive comparison of these stories, including:
    
    1. **Overview Comparison**:
       - Subject matter and main topics
       - Publication timing and context
       - Popularity metrics (scores, comments)
       
    2. **Content Comparison**:
       - Key arguments or information presented
       - Perspective and approach
       - Quality and depth of coverage
       
    3. **Discussion Comparison**:
       - Types of comments and reactions
       - Community interest patterns
       - Different viewpoints represented
       
    4. **Relationship Analysis**:
       - How these stories relate to each other
       - Whether they represent different perspectives on the same topic
       - Chronological or logical relationships
       
    5. **Synthesis**:
       - What can be learned from examining these stories together
       - Which provides better coverage and why
       - What important context is gained from the comparison
       
    Format your response in a clear, organized manner with appropriate headings and sections.
    """

@mcp.prompt()
async def hn_trend_analysis(days: int = 1, story_type: str = "top", topic: Optional[str] = None) -> str:
    """
    Creates a prompt template for analyzing trends on Hacker News over time.
    
    When a user makes a request like:
    "What's been trending on HN this week?" or "How has discussion about AI changed over the last month?"
    
    Args:
        days: Number of days to analyze
        story_type: Type of stories to analyze (top, new, best, ask, show)
        topic: Optional specific topic to track
    """
    # Get current stories
    current_stories = []
    if story_type == "top":
        current_ids = await get_top_stories(30)
    elif story_type == "new":
        current_ids = await get_new_stories(30)
    elif story_type == "best":
        current_ids = await get_best_stories(30)
    elif story_type == "ask":
        current_ids = await get_ask_stories(30)
    elif story_type == "show":
        current_ids = await get_show_stories(30)
    else:
        current_ids = await get_top_stories(30)
    
    for story_id in current_ids[:15]:  # Limit to 15 for performance
        try:
            story = await get_item(story_id)
            if topic and topic.lower() not in story.title.lower():
                continue
            current_stories.append({
                "id": story_id,
                "title": story.title,
                "score": story.score,
                "by": story.by,
                "time": story.time,
                "descendants": story.descendants
            })
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
    
    # Get historical stories
    historical_stories = []
    if days > 0:
        historical_data = await search_by_date(days_ago=days, limit=30)
        for story in historical_data[:15]:  # Limit to 15 for performance
            if topic and topic.lower() not in story.get("title", "").lower():
                continue
            historical_stories.append(story)
    
    return f"""
    You are analyzing trends on Hacker News over time.
    
    ## Current Stories ({story_type}):
    {json.dumps(current_stories, indent=2)}
    
    ## Historical Stories (from {days} days ago):
    {json.dumps(historical_stories, indent=2)}
    
    {f"## Focused Topic: {topic}" if topic else ""}
    
    Please provide a comprehensive trend analysis, including:
    
    1. **Topic Trends**:
       - What subjects are currently popular vs. {days} days ago
       - New emerging topics or technologies
       - Topics that have decreased in popularity
       
    2. **Engagement Patterns**:
       - Changes in upvoting patterns
       - Changes in comment activity
       - Types of stories getting the most engagement
       
    3. **Content Sources**:
       - Trends in where popular content is coming from
       - New or increasingly popular websites or authors
       
    4. **Community Interests**:
       - Shifts in what the HN community finds interesting
       - Changes in the types of technical topics discussed
       - Any observable changes in community values or priorities
       
    5. **Predictive Insights**:
       - What these trends might suggest about future interests
       - Technologies or topics likely to gain more attention
       - How these trends relate to broader industry movements
       
    Format your response in a clear, organized manner with appropriate headings, bullet points, and if relevant, a summary of the most significant trends observed.
    """

@mcp.prompt()
async def hn_advanced_search(query: str, days: int = 7, min_score: int = 10, min_comments: int = 5) -> str:
    """
    Creates a prompt template for advanced search across Hacker News stories.
    
    When a user makes a request like:
    "Find popular stories about quantum computing with lots of discussion" or 
    "What are the highest-rated AI stories from the past month?"
    
    Args:
        query: Search query for story titles
        days: How many days back to search
        min_score: Minimum score threshold
        min_comments: Minimum comment threshold
    """
    # Search for stories matching the query
    matching_stories = await find_stories_by_title(query, limit=30)
    
    # Get stories from the past X days
    recent_stories = await search_by_date(days_ago=days, limit=50)
    
    # Filter and combine results
    filtered_results = []
    seen_ids = set()
    
    # Process matching stories from title search
    for story in matching_stories:
        story_id = story.get("id")
        if story_id in seen_ids:
            continue
            
        score = story.get("score", 0)
        comments = story.get("descendants", 0)
        
        if score >= min_score and comments >= min_comments:
            filtered_results.append(story)
            seen_ids.add(story_id)
    
    # Process stories from date search
    for story in recent_stories:
        story_id = story.get("id")
        if story_id in seen_ids:
            continue
            
        title = story.get("title", "").lower()
        if query.lower() not in title:
            continue
            
        score = story.get("score", 0)
        comments = story.get("descendants", 0)
        
        if score >= min_score and comments >= min_comments:
            filtered_results.append(story)
            seen_ids.add(story_id)
    
    # Sort by score (descending)
    filtered_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return f"""
    You are providing results for an advanced search across Hacker News stories.
    
    ## Search Parameters:
    - Query: "{query}"  
    - Timeframe: Past {days} days
    - Minimum Score: {min_score}
    - Minimum Comments: {min_comments}
    
    ## Search Results:
    {json.dumps(filtered_results, indent=2)}
    
    Please analyze these search results and provide:
    
    1. **Overview of Results**:
       - Number of matching stories found
       - Quality and relevance of the matches
       - Distribution across the time period
       
    2. **Top Stories Analysis**:
       - Detailed look at the highest-scoring stories
       - What made these stories particularly popular
       - Common themes among popular stories
       
    3. **Discussion Hotspots**:
       - Stories with the most active discussions
       - Types of topics generating the most comments
       - Any controversial or divisive stories
       
    4. **Content Patterns**:
       - Common sources or authors
       - Types of content (tutorials, news, research, etc.)
       - Technical depth and focus areas
       
    5. **Recommendations**:
       - Most valuable stories to read based on the query
       - Different perspectives represented in the results
       - Related topics the user might be interested in
       
    Format your response in a clear, organized manner with appropriate headings and sections. Include direct links to the most relevant stories.
    """

@mcp.prompt()
async def hn_content_filter(story_id: int, filter_type: str = "technical") -> str:
    """
    Creates a prompt template for filtering and extracting specific types of content from stories.
    
    When a user makes a request like:
    "Show me just the technical parts of HN story 12345" or 
    "Extract the code examples from that article about Rust"
    
    Args:
        story_id: The ID of the Hacker News story
        filter_type: Type of content to filter for (technical, code, opinion, summary, etc.)
    """
    # Get the story content
    story_data = await get_item(story_id)
    content_data = await get_story_content(story_id, format="markdown")
    
    filter_instructions = {
        "technical": "Extract and focus on technical details, specifications, methodologies, and implementation information. Filter out opinions, marketing content, and non-technical discussion.",
        "code": "Extract and focus on code examples, programming snippets, APIs, and technical implementations. Format these properly and explain their purpose.",
        "opinion": "Extract and focus on opinions, perspectives, analyses, and subjective assessments. Identify the key viewpoints presented.",
        "summary": "Create a concise summary that captures the essential information in a fraction of the length. Focus on the most important points only.",
        "beginner": "Simplify complex technical concepts for beginners. Explain terminology, provide context, and make the content accessible to non-experts.",
        "critical": "Analyze the content critically, identifying potential flaws, biases, unsupported claims, or limitations in the methodology or conclusions."
    }
    
    instruction = filter_instructions.get(filter_type, "Extract the most relevant and useful information based on the user's request.")
    
    return f"""
    You are filtering and extracting specific content from a Hacker News story.
    
    ## Story Details:
    Title: {story_data.title}
    URL: {story_data.url}
    Posted by: {story_data.by}
    
    ## Content to Filter:
    {content_data.get('content', 'No content available')}
    
    ## Filtering Instructions:
    {instruction}
    
    Please process the content according to the filtering instructions. Maintain the accuracy of the information while focusing on the requested content type. Format your response in a clear, organized manner with appropriate headings and sections.
    """

@mcp.prompt()
async def hn_multi_source_analysis(query: str, sources_count: int = 3) -> str:
    """
    Creates a prompt template for analyzing multiple sources on the same topic from Hacker News.
    
    When a user makes a request like:
    "Compare different perspectives on blockchain from HN" or 
    "What are the various opinions about the new MacBook Pro?"
    
    Args:
        query: The topic to analyze multiple sources for
        sources_count: Number of sources to analyze
    """
    # Find stories matching the query
    matching_stories = await find_stories_by_title(query, limit=sources_count * 2)  # Get extra in case some fail
    
    # Get content for each story
    sources_data = []
    for story in matching_stories[:sources_count]:
        try:
            story_id = story.get("id")
            content_data = await get_story_content(story_id, format="markdown")
            
            if content_data.get("error"):
                continue
                
            sources_data.append({
                "id": story_id,
                "title": story.get("title"),
                "url": story.get("url"),
                "by": story.get("by"),
                "score": story.get("score"),
                "content_excerpt": content_data.get("content", "No content available")[:1000] + "..." if content_data.get("content") else "No content available"
            })
            
            if len(sources_data) >= sources_count:
                break
        except Exception as e:
            logger.error(f"Error processing story {story.get('id')}: {e}")
    
    return f"""
    You are analyzing multiple sources on the topic of "{query}" from Hacker News.
    
    ## Sources to Analyze:
    {json.dumps(sources_data, indent=2)}
    
    Please provide a comprehensive multi-source analysis, including:
    
    1. **Topic Overview**:
       - The key aspects of {query} being discussed
       - Why this topic is relevant or important
       - The context surrounding these discussions
       
    2. **Perspective Comparison**:
       - Different viewpoints represented across sources
       - Areas of agreement and disagreement
       - Unique insights from each source
       
    3. **Evidence & Support**:
       - Types of evidence used across sources
       - Strength of supporting arguments
       - Credibility and expertise factors
       
    4. **Bias Assessment**:
       - Potential biases in each source
       - How these biases affect the presentation
       - Balance of perspectives overall
       
    5. **Synthesis & Conclusion**:
       - Integrated understanding from all sources
       - Most compelling arguments and insights
       - Areas needing further information or research
       
    Format your response in a clear, organized manner with appropriate headings and sections. Aim to provide a balanced and nuanced analysis that helps the user understand the full spectrum of perspectives on this topic.
    """

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

# ----- Content Fetching and Parsing -----

async def fetch_url_content(url: str) -> Dict[str, Any]:
    """
    Fetch content from a URL.
    
    Args:
        url: The URL to fetch content from
        
    Returns:
        Dictionary containing the content and metadata
    """
    try:
        response = await http_client.get(url, follow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        
        if "text/html" in content_type:
            return {
                "content": response.text,
                "content_type": "html",
                "url": str(response.url)
            }
        elif "application/json" in content_type:
            return {
                "content": response.text,
                "content_type": "json",
                "url": str(response.url)
            }
        else:
            return {
                "content": response.text,
                "content_type": "text",
                "url": str(response.url)
            }
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return {
            "content": "",
            "content_type": "error",
            "url": url,
            "error": str(e)
        }

def html_to_markdown(html_content: str) -> str:
    """
    Convert HTML content to Markdown.
    
    Args:
        html_content: HTML content to convert
        
    Returns:
        Markdown formatted content
    """
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_tables = False
    h.body_width = 0  # No wrapping
    return h.handle(html_content)

def extract_main_content(html_content: str) -> str:
    """
    Extract the main content from HTML using BeautifulSoup.
    Attempts to find the main article content and remove navigation, ads, etc.
    
    Args:
        html_content: HTML content to parse
        
    Returns:
        Extracted main content as HTML
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove common non-content elements
        for element in soup.select('nav, header, footer, aside, script, style, iframe, .ads, .navigation, .menu, .sidebar, .comments'):
            element.decompose()
        
        # Try to find the main content
        main_content = None
        for selector in ['article', 'main', '.content', '.post', '.article', '#content', '#main']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # If we found a main content element, return it, otherwise return the body
        if main_content:
            return str(main_content)
        else:
            # If no main content found, return the body without head elements
            if soup.body:
                return str(soup.body)
            return str(soup)
    except Exception as e:
        logger.error(f"Error extracting main content: {e}")
        return html_content

@mcp.tool()
async def get_story_content(story_id: int, format: Literal["json", "markdown"] = "markdown") -> Dict[str, Any]:
    """
    Get the content of a Hacker News story by fetching its URL.
    
    Args:
        story_id: The ID of the Hacker News story
        format: Output format (json or markdown)
        
    Returns:
        The story content and metadata
    """
    # Get the story details
    try:
        story = await get_item(story_id)
        
        # Check if the story has a URL
        if not story.url:
            return ContentResponse(
                title=story.title or "No title",
                url="",
                content=story.text or "No content available",
                content_type="text",
                story_id=story_id,
                by=story.by,
                time=story.time,
                score=story.score,
                descendants=story.descendants,
                error="Story does not have a URL"
            ).model_dump()
        
        # Fetch the content from the URL
        url_data = await fetch_url_content(story.url)
        
        if url_data.get("content_type") == "error":
            return ContentResponse(
                title=story.title or "No title",
                url=story.url,
                content="",
                content_type="error",
                story_id=story_id,
                by=story.by,
                time=story.time,
                score=story.score,
                descendants=story.descendants,
                error=url_data.get("error", "Failed to fetch content")
            ).model_dump()
        
        # Process the content based on the format
        if url_data.get("content_type") == "html":
            # Extract the main content
            main_content = extract_main_content(url_data["content"])
            
            # Convert to markdown if requested
            if format == "markdown":
                processed_content = html_to_markdown(main_content)
                content_type = "markdown"
            else:
                processed_content = main_content
                content_type = "html"
        else:
            # For non-HTML content, just return as is
            processed_content = url_data["content"]
            content_type = url_data["content_type"]
        
        return ContentResponse(
            title=story.title or "No title",
            url=url_data["url"],
            content=processed_content,
            content_type=content_type,
            story_id=story_id,
            by=story.by,
            time=story.time,
            score=story.score,
            descendants=story.descendants
        ).model_dump()
    
    except Exception as e:
        logger.error(f"Error getting story content for ID {story_id}: {e}")
        return ContentResponse(
            title="Error",
            url="",
            content="",
            content_type="error",
            story_id=story_id,
            error=str(e)
        ).model_dump()

@mcp.tool()
async def get_story_content_by_title(title: str, format: Literal["json", "markdown"] = "markdown") -> Dict[str, Any]:
    """
    Get the content of a Hacker News story by title by fetching its URL.
    
    Args:
        title: The title or keywords to search for
        format: Output format (json or markdown)
        
    Returns:
        The story content and metadata
    """
    # Find stories matching the title
    matching_stories = await find_stories_by_title(title, limit=1)
    
    if not matching_stories:
        return ContentResponse(
            title="Not found",
            url="",
            content="",
            content_type="error",
            story_id=0,
            error=f"No stories found matching '{title}'"
        ).model_dump()
    
    # Get the first matching story
    story = matching_stories[0]
    
    # Get the content using the story ID
    return await get_story_content(story["id"], format)

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
        
        # --- Content Endpoints ---
        @app.get("/api/story/{story_id}/content", tags=["Content"], 
                response_model=ContentResponse,
                summary="Get story content",
                description="Get the content of a Hacker News story by fetching its URL")
        async def api_get_story_content(story_id: int, format: str = "markdown"):
            if format not in ["json", "markdown"]:
                format = "markdown"
            return await get_story_content(story_id, format)
        
        @app.get("/api/story/content-by-title", tags=["Content"], 
                response_model=ContentResponse,
                summary="Get story content by title",
                description="Get the content of a Hacker News story by title by fetching its URL")
        async def api_get_story_content_by_title(title: str, format: str = "markdown"):
            if format not in ["json", "markdown"]:
                format = "markdown"
            return await get_story_content_by_title(title, format)
            
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
                {"name": "Content", "description": "Operations for retrieving and parsing content from story URLs"},
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
