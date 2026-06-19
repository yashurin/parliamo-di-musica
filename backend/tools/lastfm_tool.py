from typing import Any

import pylast

from config import get_settings
from logging_config import get_logger

logger = get_logger("tools")

settings = get_settings()

_lastfm_network: pylast.LastFMNetwork | None = None


def _get_lastfm() -> pylast.LastFMNetwork:
    global _lastfm_network
    if _lastfm_network is None:
        if not settings.lastfm_api_key:
            raise ValueError("Last.fm API key is not configured. Set LASTFM_API_KEY.")
        _lastfm_network = pylast.LastFMNetwork(api_key=settings.lastfm_api_key)
    return _lastfm_network


def get_similar_artists(artist_name: str, limit: int = 8) -> list[dict[str, Any]]:
    """Get similar artists from Last.fm (great for recommendations)."""
    logger.info("Last.fm similar artists artist=%r limit=%d", artist_name, limit)
    network = _get_lastfm()
    try:
        artist = network.get_artist(artist_name)
        similar = artist.get_similar(limit=limit)
        return [{"name": s.item.name, "match": float(s.match)} for s in similar]
    except Exception as e:
        return [{"error": str(e)}]


def get_similar_tracks(artist: str, track: str, limit: int = 8) -> list[dict[str, Any]]:
    logger.info("Last.fm similar tracks artist=%r track=%r limit=%d", artist, track, limit)
    network = _get_lastfm()
    try:
        track_obj = network.get_track(artist, track)
        similar = track_obj.get_similar(limit=limit)
        return [
            {"name": s.item.title, "artist": s.item.artist.name, "match": float(s.match)}
            for s in similar
        ]
    except Exception as e:
        return [{"error": str(e)}]


def get_top_tracks(artist_name: str, limit: int = 10) -> list[dict[str, Any]]:
    network = _get_lastfm()
    try:
        artist = network.get_artist(artist_name)
        top = artist.get_top_tracks(limit=limit)
        return [{"name": t.item.title, "playcount": int(t.weight)} for t in top]
    except Exception as e:
        return [{"error": str(e)}]