import logging
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GENIUS_API = "https://api.genius.com"


async def _genius_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.genius_access_token:
        raise ValueError("Genius API token is not configured. Set GENIUS_ACCESS_TOKEN.")

    headers = {"Authorization": f"Bearer {settings.genius_access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{GENIUS_API}{path}", params=params, headers=headers)
        response.raise_for_status()
        return response.json()


async def search_genius_song(query: str, limit: int = 3) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 10))
    data = await _genius_get("/search", {"q": query})
    hits = data.get("response", {}).get("hits", [])[:limit]
    songs = []
    for hit in hits:
        song = hit.get("result", {})
        songs.append(
            {
                "id": song.get("id"),
                "title": song.get("title"),
                "artist": song.get("primary_artist", {}).get("name"),
                "url": song.get("url"),
                "annotation_count": song.get("annotation_count"),
            }
        )
    return songs


async def get_song_lyrics_info(song_query: str) -> dict[str, Any]:
    songs = await search_genius_song(song_query, limit=1)
    if not songs:
        return {"error": f"No Genius song found for: {song_query}"}

    song = songs[0]
    return {
        "title": song["title"],
        "artist": song["artist"],
        "genius_url": song["url"],
        "note": (
            "Full lyrics are not reproduced here for copyright reasons. "
            "Use the Genius URL for the official lyrics page and summarize themes on request."
        ),
        "source": "Genius",
    }