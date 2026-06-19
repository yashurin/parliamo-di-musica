from typing import Any, AsyncGenerator, Awaitable, Callable

from llm.ollama_client import (
    chat_completion,
    message_to_dict,
    stream_chat_completion,
)
from logging_config import get_logger
from persistence.chat_store import chat_store
from persistence.redis_store import redis_store
from tools.tool_registry import execute_tool, get_tool_schemas

logger = get_logger("llm")

SYSTEM_PROMPT = """You are GrokMusic, a knowledgeable, enthusiastic, and helpful music expert.
You have access to real-time tools for searching music catalogs, getting recommendations,
fetching structured artist metadata, and looking up lyrics information.

Guidelines:
- Be accurate and cite sources when possible (MusicBrainz, Last.fm, Genius).
- Use tools when fresh catalog data, recommendations, or lyrics would improve your answer.
- Handle ambiguity gracefully and ask clarifying questions when needed.
- For lyrics, summarize themes and meaning rather than reproducing full copyrighted lyrics.
- Suggest thoughtful follow-up questions when helpful.

Examples of good tool use:
- "Recommend artists similar to Daft Punk" -> use get_lastfm_similar_artists.
- "Find tracks similar to Get Lucky by Daft Punk" -> use get_lastfm_similar_tracks.
- "Who is Miles Davis?" -> use search_musicbrainz_artists.
- "What is Hotel California about?" -> use get_genius_lyrics, then explain themes.
"""

MAX_TOOL_ROUNDS = 5

ToolCallback = Callable[[str, str, str], Awaitable[None]]


def _build_messages(history: list[dict[str, str]], user_message: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


async def _run_tool_loop(
    messages: list[dict[str, Any]],
    on_tool_call: ToolCallback | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    tools = get_tool_schemas()

    for round_index in range(MAX_TOOL_ROUNDS):
        logger.debug("Tool loop round %d with %d messages", round_index + 1, len(messages))
        assistant_message = await chat_completion(messages=messages, tools=tools, temperature=0.4)
        if not assistant_message.tool_calls:
            if assistant_message.content:
                return messages, assistant_message.content
            messages.append(message_to_dict(assistant_message))
            return messages, None

        messages.append(message_to_dict(assistant_message))
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = tool_call.function.arguments
            logger.info("Calling tool %s", tool_name)
            if on_tool_call:
                await on_tool_call(tool_name, tool_args, tool_call.id)

            tool_result = await execute_tool(tool_name, tool_args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

    logger.warning("Reached max tool rounds (%d)", MAX_TOOL_ROUNDS)
    return messages, None


async def stream_chat_response(
    user_message: str,
    history: list[dict[str, str]] | None = None,
    on_tool_call: ToolCallback | None = None,
) -> AsyncGenerator[str, None]:
    history = history or []
    messages = _build_messages(history, user_message)
    messages, final_content = await _run_tool_loop(messages, on_tool_call=on_tool_call)

    if final_content:
        yield final_content
        return

    async for token in stream_chat_completion(messages=messages, temperature=0.7):
        yield token


async def get_chat_response(
    user_message: str,
    history: list[dict[str, str]] | None = None,
    on_tool_call: ToolCallback | None = None,
) -> str:
    chunks: list[str] = []
    async for token in stream_chat_response(user_message, history, on_tool_call=on_tool_call):
        chunks.append(token)
    return "".join(chunks)


async def ensure_thread(thread_id: str | None) -> str:
    await chat_store.initialize()
    if thread_id:
        return thread_id
    thread = await chat_store.create_thread()
    return thread["id"]


async def persist_exchange(
    thread_id: str,
    user_message: str,
    assistant_message: str,
    tool_events: list[dict[str, str]] | None = None,
) -> None:
    # Chainlit persists user/assistant steps via the data layer; store tool metadata only.
    if tool_events:
        meta = await redis_store.get_thread_meta(thread_id)
        existing_metadata = (meta or {}).get("metadata") or {}
        existing_metadata["last_tool_events"] = tool_events
        await redis_store.update_thread(thread_id, metadata=existing_metadata)
        logger.debug("Stored tool metadata for thread_id=%s", thread_id)


async def update_thread_title_from_message(thread_id: str, user_message: str) -> None:
    meta = await redis_store.get_thread_meta(thread_id)
    if not meta:
        return
    if meta.get("name") and meta["name"] != "New conversation":
        return
    title = user_message.strip()[:60] or "Music chat"
    await chat_store.update_thread_title(thread_id, title)
    logger.debug("Set thread_id=%s title to %r", thread_id, title)


async def load_thread_history(
    thread_id: str,
    current_user_message: str | None = None,
) -> list[dict[str, str]]:
    await chat_store.initialize()
    stored = await chat_store.get_thread_messages(thread_id)
    history = [
        {"role": item["role"], "content": item["content"]}
        for item in stored
        if item["role"] in {"user", "assistant"} and item.get("content")
    ]
    if (
        current_user_message
        and history
        and history[-1]["role"] == "user"
        and history[-1]["content"] == current_user_message
    ):
        history = history[:-1]
    logger.debug("Loaded %d history messages for thread_id=%s", len(history), thread_id)
    return history