import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from logging_config import get_logger
from persistence.redis_client import get_redis

logger = get_logger("persistence")

KEY_PREFIX = "music_ai_chat"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_score(iso_timestamp: str) -> float:
    try:
        return datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return datetime.now(timezone.utc).timestamp()


def _key(*parts: str) -> str:
    return f"{KEY_PREFIX}:{':'.join(parts)}"


class RedisStore:
    def __init__(self, user_thread_limit: int = 1000) -> None:
        self.user_thread_limit = user_thread_limit

    async def get_current_timestamp(self) -> str:
        return _utc_now()

    # --- Users ---

    async def get_user(self, identifier: str) -> Optional[dict[str, Any]]:
        client = await get_redis()
        raw = await client.get(_key("user", identifier))
        return json.loads(raw) if raw else None

    async def create_user(self, identifier: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        client = await get_redis()
        existing = await self.get_user(identifier)
        if existing:
            existing["metadata"] = metadata or existing.get("metadata", {})
            await client.set(_key("user", identifier), json.dumps(existing))
            return existing

        user = {
            "id": str(uuid.uuid4()),
            "identifier": identifier,
            "createdAt": await self.get_current_timestamp(),
            "metadata": metadata or {},
        }
        await client.set(_key("user", identifier), json.dumps(user))
        logger.debug("Created user %s", identifier)
        return user

    async def get_user_identifier_by_id(self, user_id: str) -> Optional[str]:
        client = await get_redis()
        async for key in client.scan_iter(match=_key("user", "*")):
            raw = await client.get(key)
            if not raw:
                continue
            user = json.loads(raw)
            if user.get("id") == user_id:
                return user.get("identifier")
        return None

    # --- Threads ---

    async def get_thread_meta(self, thread_id: str) -> Optional[dict[str, Any]]:
        client = await get_redis()
        raw = await client.get(_key("thread", thread_id))
        return json.loads(raw) if raw else None

    async def save_thread_meta(self, thread_id: str, meta: dict[str, Any]) -> None:
        client = await get_redis()
        await client.set(_key("thread", thread_id), json.dumps(meta))
        user_id = meta.get("userId")
        if user_id:
            score = _timestamp_score(meta.get("createdAt", _utc_now()))
            await client.zadd(_key("user_threads", user_id), {thread_id: score})

    async def update_thread(
        self,
        thread_id: str,
        *,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        user_identifier: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        created_at: Optional[str] = None,
    ) -> dict[str, Any]:
        existing = await self.get_thread_meta(thread_id) or {
            "id": thread_id,
            "createdAt": created_at or await self.get_current_timestamp(),
            "name": None,
            "userId": None,
            "userIdentifier": None,
            "tags": None,
            "metadata": None,
        }

        if name is not None:
            existing["name"] = name
        elif metadata and "name" in metadata:
            existing["name"] = metadata["name"]

        if user_id is not None:
            existing["userId"] = user_id
        if user_identifier is not None:
            existing["userIdentifier"] = user_identifier
        if metadata is not None:
            existing["metadata"] = metadata
        if tags is not None:
            existing["tags"] = tags
        if created_at is not None:
            existing["createdAt"] = created_at

        await self.save_thread_meta(thread_id, existing)
        return existing

    async def delete_thread(self, thread_id: str) -> None:
        client = await get_redis()
        meta = await self.get_thread_meta(thread_id)
        step_ids = await client.zrange(_key("thread_steps", thread_id), 0, -1)
        element_ids = await client.smembers(_key("thread_elements", thread_id))

        for step_id in step_ids:
            feedback_id = await client.get(_key("step_feedback", step_id))
            if feedback_id:
                await client.delete(_key("feedback", feedback_id))
            await client.delete(_key("step", step_id))
            await client.delete(_key("step_feedback", step_id))

        for element_id in element_ids:
            await client.delete(_key("element", element_id))

        if meta and meta.get("userId"):
            await client.zrem(_key("user_threads", meta["userId"]), thread_id)

        await client.delete(
            _key("thread", thread_id),
            _key("thread_steps", thread_id),
            _key("thread_elements", thread_id),
        )
        logger.info("Deleted thread %s", thread_id)

    async def list_user_thread_ids(self, user_id: str) -> list[str]:
        client = await get_redis()
        return list(
            reversed(
                await client.zrange(
                    _key("user_threads", user_id),
                    -self.user_thread_limit,
                    -1,
                )
            )
        )

    # --- Steps ---

    async def save_step(self, step: dict[str, Any]) -> None:
        client = await get_redis()
        step_id = step["id"]
        thread_id = step["threadId"]
        created_at = step.get("createdAt") or await self.get_current_timestamp()
        step["createdAt"] = created_at

        await client.set(_key("step", step_id), json.dumps(step))
        await client.zadd(
            _key("thread_steps", thread_id),
            {step_id: _timestamp_score(created_at)},
        )

        feedback = step.get("feedback")
        if feedback and feedback.get("id"):
            await self.save_feedback(feedback)

    async def get_step(self, step_id: str) -> Optional[dict[str, Any]]:
        client = await get_redis()
        raw = await client.get(_key("step", step_id))
        return json.loads(raw) if raw else None

    async def delete_step(self, step_id: str) -> None:
        client = await get_redis()
        step = await self.get_step(step_id)
        if not step:
            return

        thread_id = step.get("threadId")
        if thread_id:
            await client.zrem(_key("thread_steps", thread_id), step_id)

        feedback_id = await client.get(_key("step_feedback", step_id))
        if feedback_id:
            await client.delete(_key("feedback", feedback_id))

        await client.delete(_key("step", step_id), _key("step_feedback", step_id))

        element_ids = await client.smembers(_key("step_elements", step_id))
        for element_id in element_ids:
            await client.delete(_key("element", element_id))
            if thread_id:
                await client.srem(_key("thread_elements", thread_id), element_id)
        await client.delete(_key("step_elements", step_id))

    async def get_thread_steps(self, thread_id: str) -> list[dict[str, Any]]:
        client = await get_redis()
        step_ids = await client.zrange(_key("thread_steps", thread_id), 0, -1)
        steps: list[dict[str, Any]] = []
        for step_id in step_ids:
            step = await self.get_step(step_id)
            if step:
                feedback_id = await client.get(_key("step_feedback", step_id))
                if feedback_id:
                    feedback = await self.get_feedback(feedback_id)
                    if feedback:
                        step["feedback"] = feedback
                steps.append(step)
        return steps

    # --- Feedback ---

    async def save_feedback(self, feedback: dict[str, Any]) -> str:
        client = await get_redis()
        feedback_id = feedback.get("id") or str(uuid.uuid4())
        feedback["id"] = feedback_id
        await client.set(_key("feedback", feedback_id), json.dumps(feedback))
        if feedback.get("forId"):
            await client.set(_key("step_feedback", feedback["forId"]), feedback_id)
        return feedback_id

    async def get_feedback(self, feedback_id: str) -> Optional[dict[str, Any]]:
        client = await get_redis()
        raw = await client.get(_key("feedback", feedback_id))
        return json.loads(raw) if raw else None

    async def delete_feedback(self, feedback_id: str) -> bool:
        client = await get_redis()
        feedback = await self.get_feedback(feedback_id)
        if feedback and feedback.get("forId"):
            await client.delete(_key("step_feedback", feedback["forId"]))
        await client.delete(_key("feedback", feedback_id))
        return True

    # --- Elements ---

    async def save_element(self, element: dict[str, Any]) -> None:
        client = await get_redis()
        element_id = element["id"]
        thread_id = element.get("threadId")
        await client.set(_key("element", element_id), json.dumps(element))
        if thread_id:
            await client.sadd(_key("thread_elements", thread_id), element_id)
        if element.get("forId"):
            await client.sadd(_key("step_elements", element["forId"]), element_id)

    async def get_element(self, thread_id: str, element_id: str) -> Optional[dict[str, Any]]:
        client = await get_redis()
        raw = await client.get(_key("element", element_id))
        if not raw:
            return None
        element = json.loads(raw)
        if element.get("threadId") == thread_id:
            return element
        return None

    async def delete_element(self, element_id: str) -> None:
        client = await get_redis()
        raw = await client.get(_key("element", element_id))
        if raw:
            element = json.loads(raw)
            thread_id = element.get("threadId")
            if thread_id:
                await client.srem(_key("thread_elements", thread_id), element_id)
            if element.get("forId"):
                await client.srem(_key("step_elements", element["forId"]), element_id)
        await client.delete(_key("element", element_id))

    async def get_thread_elements(self, thread_id: str) -> list[dict[str, Any]]:
        client = await get_redis()
        element_ids = await client.smembers(_key("thread_elements", thread_id))
        elements: list[dict[str, Any]] = []
        for element_id in element_ids:
            raw = await client.get(_key("element", element_id))
            if raw:
                elements.append(json.loads(raw))
        return elements

    async def build_thread_dict(
        self,
        thread_id: str,
        *,
        include_steps: bool = True,
        include_elements: bool = True,
    ) -> Optional[dict[str, Any]]:
        meta = await self.get_thread_meta(thread_id)
        if not meta:
            return None

        thread = {
            "id": meta["id"],
            "createdAt": meta.get("createdAt"),
            "name": meta.get("name"),
            "userId": meta.get("userId"),
            "userIdentifier": meta.get("userIdentifier"),
            "tags": meta.get("tags"),
            "metadata": meta.get("metadata"),
            "steps": await self.get_thread_steps(thread_id) if include_steps else [],
            "elements": await self.get_thread_elements(thread_id) if include_elements else [],
        }
        return thread

    async def get_memory_info(self) -> dict[str, Any]:
        client = await get_redis()
        info = await client.info("memory")
        return {
            "used_memory_human": info.get("used_memory_human"),
            "used_memory_peak_human": info.get("used_memory_peak_human"),
        }


redis_store = RedisStore()