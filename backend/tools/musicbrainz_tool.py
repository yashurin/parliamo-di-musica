import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MUSICBRAINZ_API = "https://musicbrainz.org/ws/2"
USER_AGENT = "ParliamoDiMusica/0.1 (local-music-ai-chat)"


async def _get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    params.setdefault("fmt", "json")
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{MUSICBRAINZ_API}{path}", params=params, headers=headers)
        response.raise_for_status()
        return response.json()


async def search_musicbrainz_artist(name: str, limit: int = 5) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 25))
    data = await _get_json("/artist", {"query": name, "limit": limit})
    artists = []
    for item in data.get("artists", []):
        artists.append(
            {
                "mbid": item.get("id"),
                "name": item.get("name"),
                "type": item.get("type"),
                "country": item.get("country"),
                "disambiguation": item.get("disambiguation"),
                "life_span": item.get("life-span"),
                "tags": [tag["name"] for tag in item.get("tags", [])[:5]],
            }
        )
    return artists


async def get_musicbrainz_artist_details(artist_name: str) -> dict[str, Any]:
    artists = await search_musicbrainz_artist(artist_name, limit=1)
    if not artists:
        return {"error": f"No MusicBrainz artist found for: {artist_name}"}

    artist = artists[0]
    mbid = artist["mbid"]
    if not mbid:
        return {"error": f"Artist found but missing MBID: {artist_name}"}

    releases = await _get_json(f"/release", {"artist": mbid, "limit": 5})
    release_summaries = []
    for release in releases.get("releases", []):
        release_summaries.append(
            {
                "title": release.get("title"),
                "date": release.get("date"),
                "country": release.get("country"),
                "mbid": release.get("id"),
            }
        )

    return {
        "artist": artist,
        "notable_releases": release_summaries,
        "source": "MusicBrainz",
    }