import json
import os

import chainlit as cl
from chainlit.context import context
from chainlit.data import get_data_layer
from chainlit.types import ThreadDict

from auth.user_store import user_store
from config import get_settings
from llm.chat_service import (
    ensure_thread,
    load_thread_history,
    persist_exchange,
    stream_chat_response,
    update_thread_title_from_message,
)
from logging_config import get_logger, setup_logging
from persistence.chat_store import chat_store
from persistence.redis_data_layer import RedisDataLayer

settings = get_settings()
setup_logging(level=settings.log_level, log_file=settings.log_file or None)
logger = get_logger("chainlit")

os.environ.setdefault("CHAINLIT_AUTH_SECRET", settings.chainlit_auth_secret)


@cl.data_layer
def provide_data_layer() -> RedisDataLayer:
    return RedisDataLayer()


@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> cl.User | None:
    await chat_store.initialize()
    user = await user_store.authenticate(username, password)
    if user:
        logger.info("User signed in: %s", user["email"])
        return cl.User(
            identifier=user["email"],
            metadata={"role": "user", "provider": "credentials", "auth_user_id": user["id"]},
        )
    logger.warning("Failed login attempt for email %r", username)
    return None


@cl.on_chat_start
async def on_chat_start() -> None:
    await chat_store.initialize()
    thread_id = context.session.thread_id
    user = cl.user_session.get("user")
    if user:
        data_layer = get_data_layer()
        persisted_user = await data_layer.create_user(user)
        await data_layer.update_thread(
            thread_id=thread_id,
            user_id=persisted_user.id if persisted_user else None,
            name="New conversation",
        )

    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("tool_events", [])
    logger.info("Started new chat thread_id=%s user=%s", thread_id, getattr(user, "identifier", "anonymous"))

    await cl.Message(
        content=(
            "Hello! I'm your local music AI expert. Ask me about artists, tracks, "
            "recommendations, lyrics themes, genres, and more. "
            "Powered by MusicBrainz, Last.fm, and Genius (all local & privacy-friendly)."
        )
    ).send()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    await chat_store.initialize()
    thread_id = thread["id"]
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("tool_events", [])
    logger.info("Resumed chat thread_id=%s steps=%d", thread_id, len(thread.get("steps", [])))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    thread_id = cl.user_session.get("thread_id") or context.session.thread_id
    thread_id = await ensure_thread(thread_id)
    cl.user_session.set("thread_id", thread_id)

    history = await load_thread_history(thread_id, current_user_message=message.content)
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
        logger.info("Processing message in thread_id=%s", thread_id)
        async for token in stream_chat_response(
            user_message=message.content,
            history=history,
            on_tool_call=on_tool_call,
        ):
            full_response.append(token)
            await response_message.stream_token(token)
    except Exception:
        logger.exception("Chat failed for thread_id=%s", thread_id)
        error_text = "Sorry, something went wrong while generating a response."
        await response_message.stream_token(error_text)
        full_response = [error_text]

    await response_message.update()
    await persist_exchange(
        thread_id=thread_id,
        user_message=message.content,
        assistant_message="".join(full_response),
        tool_events=tool_events or None,
    )
    await update_thread_title_from_message(thread_id, message.content)