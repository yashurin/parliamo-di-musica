import asyncio
import inspect
import json
import logging
from typing import Any, Callable

from tools import genius_tool, musicbrainz_tool, spotify_tool

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Any]

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_spotify_tracks",
            "description": "Search Spotify for tracks matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Track or song search query."},
                    "limit": {"type": "integer", "description": "Maximum number of tracks to return.", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_spotify_artists",
            "description": "Search Spotify for artists matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Artist search query."},
                    "limit": {"type": "integer", "description": "Maximum number of artists to return.", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_track_recommendations",
            "description": "Get Spotify track recommendations similar to a seed track query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seed_track": {"type": "string", "description": "Track name or search query to seed recommendations."},
                    "limit": {"type": "integer", "description": "Number of recommendations to return.", "default": 5},
                },
                "required": ["seed_track"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_track_audio_features",
            "description": "Get Spotify audio features for a track (tempo, energy, valence, key, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "track_query": {"type": "string", "description": "Track name or search query."},
                },
                "required": ["track_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_musicbrainz_artist",
            "description": "Search MusicBrainz for artist metadata by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Artist name to search."},
                    "limit": {"type": "integer", "description": "Maximum number of artists to return.", "default": 5},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_musicbrainz_artist_details",
            "description": "Get detailed MusicBrainz artist info including notable releases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "artist_name": {"type": "string", "description": "Artist name to look up."},
                },
                "required": ["artist_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_genius_song",
            "description": "Search Genius for songs (lyrics metadata and URLs). Requires Genius token.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song title and/or artist to search."},
                    "limit": {"type": "integer", "description": "Maximum number of songs to return.", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_song_lyrics_info",
            "description": "Get Genius metadata for a song without reproducing full lyrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song_query": {"type": "string", "description": "Song title and/or artist."},
                },
                "required": ["song_query"],
            },
        },
    },
]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "search_spotify_tracks": spotify_tool.search_spotify_tracks,
    "search_spotify_artists": spotify_tool.search_spotify_artists,
    "get_track_recommendations": spotify_tool.get_track_recommendations,
    "get_track_audio_features": spotify_tool.get_track_audio_features,
    "search_musicbrainz_artist": musicbrainz_tool.search_musicbrainz_artist,
    "get_musicbrainz_artist_details": musicbrainz_tool.get_musicbrainz_artist_details,
    "search_genius_song": genius_tool.search_genius_song,
    "get_song_lyrics_info": genius_tool.get_song_lyrics_info,
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
    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(**parsed_args)
        else:
            result = await asyncio.to_thread(handler, **parsed_args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(exc)})