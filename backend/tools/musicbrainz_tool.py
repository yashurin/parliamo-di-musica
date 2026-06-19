from typing import Any

import musicbrainzngs

from config import get_settings
from logging_config import get_logger

logger = get_logger("tools")

settings = get_settings()

_app_name, _version_contact = settings.musicbrainz_user_agent.split("/", 1)
_version = _version_contact.split()[0]
_contact = _version_contact.split("(")[1].rstrip(")")

musicbrainzngs.set_useragent(_app_name, _version, _contact)


def search_artists(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search for artists on MusicBrainz."""
    logger.info("MusicBrainz artist search query=%r limit=%d", query, limit)
    result = musicbrainzngs.search_artists(query=query, limit=limit)
    return result.get("artist-list", [])


def get_artist_by_id(mbid: str) -> dict[str, Any]:
    """Get detailed artist info by MusicBrainz ID."""
    return musicbrainzngs.get_artist_by_id(mbid, includes=["tags", "ratings", "url-rels"])


def search_releases(
    artist_mbid: str | None = None,
    query: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search releases (albums, singles, etc.)."""
    if artist_mbid:
        result = musicbrainzngs.browse_releases(
            artist=artist_mbid,
            limit=limit,
            includes=["artist-credits"],
        )
    else:
        result = musicbrainzngs.search_releases(query=query or "", limit=limit)
    return result.get("release-list", [])