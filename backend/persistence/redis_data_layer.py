import json
import uuid
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Optional

from chainlit.data.base import BaseDataLayer
from chainlit.data.utils import queue_until_user_message
from chainlit.element import ElementDict
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User

from logging_config import get_logger
from persistence.redis_store import redis_store

if TYPE_CHECKING:
    from chainlit.element import Element

logger = get_logger("persistence")


class RedisDataLayer(BaseDataLayer):
    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        from persistence.redis_client import close_redis

        await close_redis()

    # --- Users ---

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        user = await redis_store.get_user(identifier)
        if not user:
            return None
        return PersistedUser(
            id=user["id"],
            identifier=user["identifier"],
            createdAt=user["createdAt"],
            metadata=user.get("metadata", {}),
        )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        saved = await redis_store.create_user(user.identifier, user.metadata)
        return PersistedUser(
            id=saved["id"],
            identifier=saved["identifier"],
            createdAt=saved["createdAt"],
            metadata=saved.get("metadata", {}),
        )

    # --- Threads ---

    async def get_thread_author(self, thread_id: str) -> str:
        meta = await redis_store.get_thread_meta(thread_id)
        if meta and meta.get("userIdentifier"):
            return meta["userIdentifier"]
        raise ValueError(f"Author not found for thread_id {thread_id}")

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        thread = await redis_store.build_thread_dict(thread_id)
        if not thread:
            return None
        return ThreadDict(**thread)

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> None:
        user_identifier = None
        if user_id:
            user_identifier = await redis_store.get_user_identifier_by_id(user_id)

        await redis_store.update_thread(
            thread_id,
            name=name,
            user_id=user_id,
            user_identifier=user_identifier,
            metadata=metadata,
            tags=tags,
        )
        logger.debug("Updated thread %s", thread_id)

    async def delete_thread(self, thread_id: str) -> None:
        await redis_store.delete_thread(thread_id)

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        if not filters.userId:
            raise ValueError("userId is required")

        thread_ids = await redis_store.list_user_thread_ids(filters.userId)
        threads: list[ThreadDict] = []
        for thread_id in thread_ids:
            thread = await redis_store.build_thread_dict(thread_id, include_elements=False)
            if thread:
                threads.append(ThreadDict(**thread))

        search_keyword = filters.search.lower() if filters.search else None
        feedback_value = int(filters.feedback) if filters.feedback is not None else None

        filtered_threads: list[ThreadDict] = []
        for thread in threads:
            keyword_match = True
            feedback_match = True
            if search_keyword:
                keyword_match = any(
                    search_keyword in (step.get("output") or "").lower()
                    for step in thread["steps"]
                )
            if feedback_value is not None:
                feedback_match = any(
                    step.get("feedback", {}).get("value") == feedback_value
                    for step in thread["steps"]
                    if step.get("feedback")
                )
            if keyword_match and feedback_match:
                filtered_threads.append(thread)

        start = 0
        if pagination.cursor:
            for index, thread in enumerate(filtered_threads):
                if thread["id"] == pagination.cursor:
                    start = index + 1
                    break

        end = start + pagination.first
        paginated_threads = filtered_threads[start:end]
        has_next_page = len(filtered_threads) > end

        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next_page,
                startCursor=paginated_threads[0]["id"] if paginated_threads else None,
                endCursor=paginated_threads[-1]["id"] if paginated_threads else None,
            ),
            data=paginated_threads,
        )

    # --- Steps ---

    @queue_until_user_message()
    async def create_step(self, step_dict: StepDict) -> None:
        await self.update_thread(step_dict["threadId"])
        prepared = self._prepare_step_dict(step_dict)
        await redis_store.save_step(prepared)
        logger.debug("Saved step %s for thread %s", prepared["id"], prepared["threadId"])

    @queue_until_user_message()
    async def update_step(self, step_dict: StepDict) -> None:
        await self.create_step(step_dict)

    @queue_until_user_message()
    async def delete_step(self, step_id: str) -> None:
        await redis_store.delete_step(step_id)

    # --- Feedback ---

    async def upsert_feedback(self, feedback: Feedback) -> str:
        feedback.id = feedback.id or str(uuid.uuid4())
        feedback_dict = asdict(feedback)
        return await redis_store.save_feedback(feedback_dict)

    async def delete_feedback(self, feedback_id: str) -> bool:
        return await redis_store.delete_feedback(feedback_id)

    async def get_favorite_steps(self, user_id: str) -> list[StepDict]:
        return []

    # --- Elements ---

    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        element = await redis_store.get_element(thread_id, element_id)
        return ElementDict(**element) if element else None

    @queue_until_user_message()
    async def create_element(self, element: "Element") -> None:
        if not element.for_id:
            return
        element_dict = element.to_dict()
        element_dict_cleaned = {
            key: value for key, value in element_dict.items() if value is not None
        }
        if "props" in element_dict_cleaned and isinstance(element_dict_cleaned["props"], dict):
            element_dict_cleaned["props"] = json.dumps(element_dict_cleaned["props"])
        await redis_store.save_element(element_dict_cleaned)
        logger.debug("Saved element %s for thread %s", element.id, element.thread_id)

    @queue_until_user_message()
    async def delete_element(self, element_id: str, thread_id: Optional[str] = None) -> None:
        await redis_store.delete_element(element_id)

    def _prepare_step_dict(self, step_dict: StepDict) -> dict[str, Any]:
        prepared = dict(step_dict)
        if "showInput" in prepared:
            prepared["showInput"] = (
                str(prepared["showInput"]).lower()
                if prepared["showInput"] is not None
                else None
            )
        if prepared.get("showInput") in {None, "false"}:
            prepared["input"] = ""
        prepared.setdefault("metadata", prepared.get("metadata") or {})
        prepared.setdefault("output", prepared.get("output") or "")
        prepared.setdefault("input", prepared.get("input") or "")
        return prepared