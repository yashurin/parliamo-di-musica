import json
import uuid
from datetime import datetime, timezone
from typing import Any

import bcrypt

from logging_config import get_logger
from persistence.redis_client import get_redis

logger = get_logger("persistence")

AUTH_KEY_PREFIX = "music_ai_chat:auth"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _email_key(email: str) -> str:
    return f"{AUTH_KEY_PREFIX}:email:{_normalize_email(email)}"


def _id_key(user_id: str) -> str:
    return f"{AUTH_KEY_PREFIX}:id:{user_id}"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


class UserStore:
    async def register(self, email: str, password: str) -> dict[str, Any]:
        normalized_email = _normalize_email(email)
        client = await get_redis()

        if await client.exists(_email_key(normalized_email)):
            raise ValueError("An account with this email already exists")

        user_id = str(uuid.uuid4())
        record = {
            "id": user_id,
            "email": normalized_email,
            "password_hash": hash_password(password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await client.set(_email_key(normalized_email), json.dumps(record))
        await client.set(_id_key(user_id), normalized_email)
        logger.info("Registered user %s", normalized_email)
        return {"id": user_id, "email": normalized_email}

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        client = await get_redis()
        raw = await client.get(_email_key(email))
        return json.loads(raw) if raw else None

    async def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        user = await self.get_by_email(_normalize_email(email))
        if not user:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user


user_store = UserStore()