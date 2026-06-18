import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.chat_db_path

    async def initialize(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(id)
                )
                """
            )
            await db.commit()

    async def create_thread(self, title: str | None = None) -> dict[str, Any]:
        thread_id = str(uuid.uuid4())
        now = _utc_now()
        title = title or "New conversation"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (thread_id, title, now, now),
            )
            await db.commit()
        return {"id": thread_id, "title": title, "created_at": now, "updated_at": now}

    async def list_threads(self, limit: int = 20) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM threads
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_thread_messages(self, thread_id: str) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT role, content, metadata, created_at
                FROM messages
                WHERE thread_id = ?
                ORDER BY created_at ASC
                """,
                (thread_id,),
            )
            rows = await cursor.fetchall()

        messages = []
        for row in rows:
            messages.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                    "created_at": row["created_at"],
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
        message_id = str(uuid.uuid4())
        now = _utc_now()
        metadata_json = json.dumps(metadata) if metadata else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (id, thread_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, thread_id, role, content, metadata_json, now),
            )
            await db.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (now, thread_id),
            )
            await db.commit()

    async def update_thread_title(self, thread_id: str, title: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE threads SET title = ?, updated_at = ? WHERE id = ?",
                (title, _utc_now(), thread_id),
            )
            await db.commit()


chat_store = ChatStore()