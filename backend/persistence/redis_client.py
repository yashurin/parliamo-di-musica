from typing import Optional

import redis.asyncio as redis

from config import get_settings
from logging_config import get_logger

logger = get_logger("persistence")
settings = get_settings()

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        logger.info(
            "Connecting to Redis at %s:%s (db=%s)",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


async def ping_redis() -> bool:
    client = await get_redis()
    return bool(await client.ping())