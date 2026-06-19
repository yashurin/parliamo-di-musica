import uuid
from typing import Any

from logging_config import get_logger
from persistence.redis_client import get_redis, ping_redis
from persistence.redis_store import redis_store

logger = get_logger("persistence")


class ChatStore:
    async def initialize(self) -> None:
        await get_redis()
        if not await ping_redis():
            raise ConnectionError("Unable to connect to Redis")
        memory = await redis_store.get_memory_info()
        logger.info(
            "Chat store initialized (Redis memory: %s)",
            memory.get("used_memory_human", "unknown"),
        )

    async def create_thread(self, title: str | None = None, user_id: str | None = None) -> dict[str, Any]:
        thread_id = str(uuid.uuid4())
        now = await redis_store.get_current_timestamp()
        title = title or "New conversation"
        await redis_store.update_thread(
            thread_id,
            name=title,
            user_id=user_id,
            created_at=now,
        )
        return {"id": thread_id, "title": title, "created_at": now, "updated_at": now}

    async def list_threads(self, limit: int = 20, user_id: str | None = None) -> list[dict[str, Any]]:
        if not user_id:
            client = await get_redis()
            thread_keys = []
            async for key in client.scan_iter(match=f"music_ai_chat:thread:*"):
                if key.count(":") == 2:
                    thread_keys.append(key)
            threads = []
            for key in thread_keys[:limit]:
                thread_id = key.split(":")[-1]
                meta = await redis_store.get_thread_meta(thread_id)
                if meta:
                    threads.append(
                        {
                            "id": meta["id"],
                            "title": meta.get("name") or "New conversation",
                            "created_at": meta.get("createdAt"),
                            "updated_at": meta.get("createdAt"),
                        }
                    )
            return sorted(threads, key=lambda t: t.get("updated_at") or "", reverse=True)[:limit]

        thread_ids = await redis_store.list_user_thread_ids(user_id)
        threads = []
        for thread_id in thread_ids[:limit]:
            meta = await redis_store.get_thread_meta(thread_id)
            if meta:
                threads.append(
                    {
                        "id": meta["id"],
                        "title": meta.get("name") or "New conversation",
                        "created_at": meta.get("createdAt"),
                        "updated_at": meta.get("createdAt"),
                    }
                )
        return threads

    async def get_thread_messages(self, thread_id: str) -> list[dict[str, Any]]:
        steps = await redis_store.get_thread_steps(thread_id)
        messages = []
        for step in steps:
            if step.get("type") not in {"user_message", "assistant_message"}:
                continue
            messages.append(
                {
                    "role": "user" if step["type"] == "user_message" else "assistant",
                    "content": step.get("output") or "",
                    "metadata": step.get("metadata"),
                    "created_at": step.get("createdAt"),
                }
            )
        return messages

    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        step_type = "user_message" if role == "user" else "assistant_message"
        await redis_store.save_step(
            {
                "id": str(uuid.uuid4()),
                "threadId": thread_id,
                "type": step_type,
                "name": role,
                "output": content,
                "metadata": metadata or {},
                "createdAt": await redis_store.get_current_timestamp(),
                "parentId": None,
                "streaming": False,
            }
        )

    async def update_thread_title(self, thread_id: str, title: str) -> None:
        await redis_store.update_thread(thread_id, name=title)
        logger.debug("Updated thread %s title to %r", thread_id, title)


chat_store = ChatStore()