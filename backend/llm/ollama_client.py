import json
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

from config import get_settings
from logging_config import get_logger

logger = get_logger("llm")
settings = get_settings()

client = AsyncOpenAI(
    base_url=settings.ollama_base_url,
    api_key="ollama",
)


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.7,
) -> ChatCompletionMessage:
    logger.debug(
        "Ollama chat completion model=%s messages=%d tools=%s",
        settings.ollama_model,
        len(messages),
        bool(tools),
    )
    response = await client.chat.completions.create(
        model=settings.ollama_model,
        messages=messages,
        tools=tools,
        stream=False,
        temperature=temperature,
    )
    return response.choices[0].message


async def stream_chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    logger.debug("Ollama streaming completion model=%s messages=%d", settings.ollama_model, len(messages))
    stream = await client.chat.completions.create(
        model=settings.ollama_model,
        messages=messages,
        tools=tools,
        stream=True,
        temperature=temperature,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


async def test_ollama_connection(prompt: str = "Say hello in one short sentence.") -> str:
    message = await chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return message.content or ""


def message_to_dict(message: ChatCompletionMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": message.role,
        "content": message.content or "",
    }
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    return payload


def serialize_tool_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)