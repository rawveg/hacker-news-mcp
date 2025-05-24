"""
Tests for the Hacker News MCP Server.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock
import json

from fastmcp import Client
from app.server import mcp, Item, User, UpdatesResponse

# Sample test data
SAMPLE_ITEM = {
    "id": 8863,
    "by": "dhouston",
    "descendants": 71,
    "kids": [8952, 9224, 8917],
    "score": 111,
    "time": 1175714200,
    "title": "My YC app: Dropbox - Throw away your USB drive",
    "type": "story",
    "url": "http://www.getdropbox.com/u/2/screencast.html"
}

SAMPLE_USER = {
    "id": "dhouston",
    "created": 1175714200,
    "karma": 2937,
    "about": "This is a test",
    "submitted": [8863, 8952, 9224]
}

SAMPLE_UPDATES = {
    "items": [8863, 8952, 9224],
    "profiles": ["dhouston", "pg"]
}

SAMPLE_STORIES = [8863, 8952, 9224, 9505, 9671]


@pytest.fixture
def mock_fetch_hn_data():
    """Mock the fetch_hn_data function to return test data."""
    with patch('app.server.fetch_hn_data', new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def client():
    """Create a FastMCP client for testing."""
    return Client(mcp)


@pytest.mark.asyncio
async def test_get_item(client, mock_fetch_hn_data):
    """Test the get_item tool."""
    mock_fetch_hn_data.return_value = SAMPLE_ITEM
    
    async with client:
        result = await client.call_tool("get_item", {"id": 8863})
    
    assert result.id == 8863
    assert result.by == "dhouston"
    assert result.title == "My YC app: Dropbox - Throw away your USB drive"
    mock_fetch_hn_data.assert_called_once_with("item/8863.json")


@pytest.mark.asyncio
async def test_get_user(client, mock_fetch_hn_data):
    """Test the get_user tool."""
    mock_fetch_hn_data.return_value = SAMPLE_USER
    
    async with client:
        result = await client.call_tool("get_user", {"id": "dhouston"})
    
    assert result.id == "dhouston"
    assert result.karma == 2937
    assert len(result.submitted) == 3
    mock_fetch_hn_data.assert_called_once_with("user/dhouston.json")


@pytest.mark.asyncio
async def test_get_max_item_id(client, mock_fetch_hn_data):
    """Test the get_max_item_id tool."""
    mock_fetch_hn_data.return_value = 9130260
    
    async with client:
        result = await client.call_tool("get_max_item_id")
    
    assert result == 9130260
    mock_fetch_hn_data.assert_called_once_with("maxitem.json")


@pytest.mark.asyncio
async def test_get_top_stories(client, mock_fetch_hn_data):
    """Test the get_top_stories tool."""
    mock_fetch_hn_data.return_value = SAMPLE_STORIES
    
    async with client:
        result = await client.call_tool("get_top_stories", {"limit": 3})
    
    assert len(result) == 3
    assert result == SAMPLE_STORIES[:3]
    mock_fetch_hn_data.assert_called_once_with("topstories.json")


@pytest.mark.asyncio
async def test_get_updates(client, mock_fetch_hn_data):
    """Test the get_updates tool."""
    mock_fetch_hn_data.return_value = SAMPLE_UPDATES
    
    async with client:
        result = await client.call_tool("get_updates")
    
    assert len(result.items) == 3
    assert len(result.profiles) == 2
    assert "dhouston" in result.profiles
    mock_fetch_hn_data.assert_called_once_with("updates.json")


@pytest.mark.asyncio
async def test_get_story_with_comments(client, mock_fetch_hn_data):
    """Test the get_story_with_comments tool."""
    # Mock the get_item function to return a story and then comments
    mock_fetch_hn_data.side_effect = [
        SAMPLE_ITEM,  # First call returns the story
        {"id": 8952, "by": "pg", "text": "Comment 1", "type": "comment"},  # Second call returns first comment
        {"id": 9224, "by": "norvig", "text": "Comment 2", "type": "comment"}  # Third call returns second comment
    ]
    
    async with client:
        result = await client.call_tool("get_story_with_comments", {"story_id": 8863, "comment_limit": 2})
    
    assert result["id"] == 8863
    assert result["title"] == "My YC app: Dropbox - Throw away your USB drive"
    assert len(result["fetched_comments"]) == 2
    assert result["fetched_comments"][0]["id"] == 8952
    assert result["fetched_comments"][1]["id"] == 9224


@pytest.mark.asyncio
async def test_item_resource(client, mock_fetch_hn_data):
    """Test the item resource."""
    mock_fetch_hn_data.return_value = SAMPLE_ITEM
    
    async with client:
        result = await client.read_resource("hn://item/8863")
    
    # Extract text content from the resource
    content = json.loads(result[0].text)
    assert content["item"]["id"] == 8863
    assert content["item"]["title"] == "My YC app: Dropbox - Throw away your USB drive"


@pytest.mark.asyncio
async def test_top_stories_resource(client, mock_fetch_hn_data):
    """Test the top stories resource."""
    # First call returns story IDs, subsequent calls return individual stories
    mock_fetch_hn_data.side_effect = [
        SAMPLE_STORIES,  # First call returns the story IDs
        SAMPLE_ITEM,  # Second call returns first story details
        {"id": 8952, "by": "pg", "title": "Story 2", "type": "story"},  # Third call returns second story
        {"id": 9224, "by": "norvig", "title": "Story 3", "type": "story"}  # Fourth call returns third story
    ]
    
    async with client:
        result = await client.read_resource("hn://top/3")
    
    # Extract text content from the resource
    content = json.loads(result[0].text)
    assert len(content["story_ids"]) == 5  # All story IDs
    assert len(content["stories"]) == 3  # Limited to 3 full stories
    assert content["stories"][0]["id"] == 8863
