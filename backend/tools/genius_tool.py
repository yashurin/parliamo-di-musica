from typing import Any

import lyricsgenius

from config import get_settings
from logging_config import get_logger

logger = get_logger("tools")

settings = get_settings()

_genius: lyricsgenius.Genius | None = None


def _get_genius() -> lyricsgenius.Genius | None:
    global _genius
    if _genius is None and settings.genius_access_token:
        _genius = lyricsgenius.Genius(
            settings.genius_access_token,
            verbose=False,
            remove_section_headers=True,
        )
    return _genius


def get_lyrics(song_title: str, artist: str | None = None) -> dict[str, Any]:
    """Fetch lyrics and basic annotation info from Genius."""
    logger.info("Genius lyrics lookup title=%r artist=%r", song_title, artist)
    genius = _get_genius()
    if not genius:
        return {"error": "Genius token not configured"}
    try:
        song = genius.search_song(song_title, artist)
        if song:
            lyrics = song.lyrics
            if len(lyrics) > 2000:
                lyrics = lyrics[:2000] + "..."
            return {
                "title": song.title,
                "artist": song.artist,
                "lyrics": lyrics,
                "url": song.url,
            }
        return {"error": "Song not found"}
    except Exception as e:
        return {"error": str(e)}