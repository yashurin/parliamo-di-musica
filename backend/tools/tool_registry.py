import asyncio
import inspect
import json
from typing import Any, Callable

from logging_config import get_logger
from tools import genius_tool, lastfm_tool, musicbrainz_tool

logger = get_logger("tools")

ToolHandler = Callable[..., Any]

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_musicbrainz_artists",
            "description": "Search for artists on MusicBrainz. Use this for general artist information and to get stable IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Artist name or partial name"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lastfm_similar_artists",
            "description": "Get artists similar to a given artist. Excellent for recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "artist_name": {"type": "string"},
                    "limit": {"type": "integer", "default": 8},
                },
                "required": ["artist_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lastfm_similar_tracks",
            "description": "Find tracks similar to a specific song. Great for 'recommend songs like X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "artist": {"type": "string"},
                    "track": {"type": "string"},
                    "limit": {"type": "integer", "default": 8},
                },
                "required": ["artist", "track"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_genius_lyrics",
            "description": "Fetch lyrics and basic info for a song from Genius.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song_title": {"type": "string"},
                    "artist": {"type": "string", "description": "Optional artist name to improve accuracy"},
                },
                "required": ["song_title"],
            },
        },
    },
]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "search_musicbrainz_artists": musicbrainz_tool.search_artists,
    "get_lastfm_similar_artists": lastfm_tool.get_similar_artists,
    "get_lastfm_similar_tracks": lastfm_tool.get_similar_tracks,
    "get_genius_lyrics": genius_tool.get_lyrics,
}


def get_tool_schemas() -> list[dict[str, Any]]:
    return TOOL_DEFINITIONS


async def execute_tool(name: str, arguments: str | dict[str, Any]) -> str:
    if name not in TOOL_HANDLERS:
        return json.dumps({"error": f"Unknown tool: {name}"})

    if isinstance(arguments, str):
        try:
            parsed_args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return json.dumps({"error": f"Invalid JSON arguments for tool {name}"})
    else:
        parsed_args = arguments

    handler = TOOL_HANDLERS[name]
    logger.debug("Executing tool %s with args %s", name, parsed_args)
    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(**parsed_args)
        else:
            result = await asyncio.to_thread(handler, **parsed_args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(exc)})