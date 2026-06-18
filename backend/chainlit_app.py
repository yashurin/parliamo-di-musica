import json
import logging

import chainlit as cl

from llm.chat_service import (
    ensure_thread,
    load_thread_history,
    persist_exchange,
    stream_chat_response,
)
from persistence.chat_store import chat_store

logger = logging.getLogger(__name__)


@cl.on_chat_start
async def on_chat_start() -> None:
    await chat_store.initialize()
    thread = await chat_store.create_thread()
    cl.user_session.set("thread_id", thread["id"])
    cl.user_session.set("tool_events", [])

    await cl.Message(
        content=(
            "Hello! I'm your local music AI expert. Ask me about artists, tracks, "
            "recommendations, lyrics themes, genres, and more. I can call Spotify, "
            "MusicBrainz, and Genius tools when fresh data helps."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    thread_id = cl.user_session.get("thread_id")
    thread_id = await ensure_thread(thread_id)
    cl.user_session.set("thread_id", thread_id)

    history = await load_thread_history(thread_id)
    tool_events: list[dict[str, str]] = []

    async def on_tool_call(tool_name: str, tool_args: str, tool_call_id: str) -> None:
        pretty_args = tool_args
        try:
            pretty_args = json.dumps(json.loads(tool_args), indent=2)
        except json.JSONDecodeError:
            pass

        async with cl.Step(name=tool_name, type="tool") as step:
            step.input = pretty_args
            step.output = "Running..."
        tool_events.append(
            {
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "arguments": tool_args,
            }
        )

    response_message = cl.Message(content="")
    await response_message.send()

    full_response: list[str] = []
    try:
        async for token in stream_chat_response(
            user_message=message.content,
            history=history,
            on_tool_call=on_tool_call,
        ):
            full_response.append(token)
            await response_message.stream_token(token)
    except Exception as exc:
        logger.exception("Chat failed")
        error_text = f"Sorry, something went wrong while generating a response: {exc}"
        await response_message.stream_token(error_text)
        full_response = [error_text]

    await response_message.update()
    await persist_exchange(
        thread_id=thread_id,
        user_message=message.content,
        assistant_message="".join(full_response),
        tool_events=tool_events or None,
    )