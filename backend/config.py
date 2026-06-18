from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://ollama:11434/v1"
    ollama_model: str = "qwen3:8b"
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    genius_access_token: str = ""
    log_level: str = "INFO"
    chat_db_path: str = "/app/data/chat.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()