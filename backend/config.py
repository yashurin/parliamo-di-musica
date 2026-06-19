from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://ollama:11434/v1"
    ollama_model: str = "qwen3:8b"
    lastfm_api_key: str = ""
    genius_access_token: str = ""
    musicbrainz_user_agent: str = "MusicAI-Chat/0.1 (contact@example.com)"
    log_level: str = "INFO"
    log_file: str = ""

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    chainlit_auth_secret: str = "change-me-in-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()