import logging
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: spotipy.Spotify | None = None


def _get_client() -> spotipy.Spotify:
    global _client
    if _client is not None:
        return _client

    if not settings.spotify_client_id or not settings.spotify_client_secret:
        raise ValueError(
            "Spotify credentials are not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
        )

    auth = SpotifyClientCredentials(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
    )
    _client = spotipy.Spotify(auth_manager=auth)
    return _client


def search_spotify_tracks(query: str, limit: int = 5) -> list[dict[str, Any]]:
    client = _get_client()
    limit = max(1, min(limit, 20))
    results = client.search(q=query, type="track", limit=limit)
    tracks = []
    for item in results.get("tracks", {}).get("items", []):
        tracks.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "artists": [artist["name"] for artist in item.get("artists", [])],
                "album": item.get("album", {}).get("name"),
                "popularity": item.get("popularity"),
                "url": item.get("external_urls", {}).get("spotify"),
            }
        )
    return tracks


def search_spotify_artists(query: str, limit: int = 5) -> list[dict[str, Any]]:
    client = _get_client()
    limit = max(1, min(limit, 20))
    results = client.search(q=query, type="artist", limit=limit)
    artists = []
    for item in results.get("artists", {}).get("items", []):
        artists.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "genres": item.get("genres", []),
                "popularity": item.get("popularity"),
                "url": item.get("external_urls", {}).get("spotify"),
            }
        )
    return artists


def get_track_recommendations(seed_track: str, limit: int = 5) -> list[dict[str, Any]]:
    client = _get_client()
    limit = max(1, min(limit, 20))
    tracks = search_spotify_tracks(seed_track, limit=1)
    if not tracks:
        return []

    seed_track_id = tracks[0]["id"]
    if not seed_track_id:
        return []

    recommendations = client.recommendations(seed_tracks=[seed_track_id], limit=limit)
    output = []
    for item in recommendations.get("tracks", []):
        output.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "artists": [artist["name"] for artist in item.get("artists", [])],
                "album": item.get("album", {}).get("name"),
                "url": item.get("external_urls", {}).get("spotify"),
            }
        )
    return output


def get_track_audio_features(track_query: str) -> dict[str, Any]:
    client = _get_client()
    tracks = search_spotify_tracks(track_query, limit=1)
    if not tracks or not tracks[0].get("id"):
        return {"error": f"No Spotify track found for query: {track_query}"}

    track = tracks[0]
    features = client.audio_features([track["id"]])[0]
    if not features:
        return {"error": f"Audio features unavailable for: {track['name']}"}

    return {
        "track": track["name"],
        "artists": track["artists"],
        "danceability": features.get("danceability"),
        "energy": features.get("energy"),
        "valence": features.get("valence"),
        "tempo": features.get("tempo"),
        "key": features.get("key"),
        "mode": features.get("mode"),
        "acousticness": features.get("acousticness"),
        "instrumentalness": features.get("instrumentalness"),
        "liveness": features.get("liveness"),
        "speechiness": features.get("speechiness"),
    }