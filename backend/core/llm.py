from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator

import httpx


ModelInfo = dict


# ── Events ──

class ThinkingEvent:
    chunk: str
    def __init__(self, chunk: str): self.chunk = chunk

class ContentEvent:
    chunk: str
    def __init__(self, chunk: str): self.chunk = chunk

class ToolCallEvent:
    tool_call_id: str
    name: str
    arguments: str
    def __init__(self, tool_call_id: str, name: str, arguments: str):
        self.tool_call_id = tool_call_id
        self.name = name
        self.arguments = arguments

class DoneEvent:
    usage: dict | None
    finish_reason: str | None
    def __init__(self, usage: dict | None = None, finish_reason: str | None = None):
        self.usage = usage
        self.finish_reason = finish_reason

class ErrorEvent:
    error: str
    def __init__(self, error: str): self.error = error

StreamEvent = ThinkingEvent | ContentEvent | ToolCallEvent | DoneEvent | ErrorEvent


@dataclass
class LLMConfig:
    api_key: str
    base_url: str = "https://opencode.ai/zen/v1"
    model: str = "deepseek-v4-flash-free"
    timeout: int = 120


@dataclass
class ChatResponse:
    content: str
    reasoning_content: str | None = None
    model: str = ""
    usage: dict | None = None
    finish_reason: str | None = None
    tool_calls: list[dict] | None = None


# ── Tool definitions ──

MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "memory_store",
            "description": "Store cross-chapter persistent information (characters, plot, world rules). Content should start with [ChX] indicating chapter origin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Unique identifier in English/pinyin. Prefix like char_/plot_/rule_"
                    },
                    "content": {
                        "type": "string",
                        "description": "[ChX] Detailed description of the information to remember"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional categorization tags"
                    }
                },
                "required": ["key", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_read",
            "description": "Search stored memories by keyword to retrieve cross-chapter information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keywords to find matching memories. Use empty string to list all."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_set_title",
            "description": "Set the current chapter title BEFORE writing content. Call this first, then write pure chapter body without any title line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The chapter title"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_delete",
            "description": "Delete a memory by its key. Use this to clean up outdated or incorrect memories after reading them all.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The memory key to delete (e.g. char_old, plot_stale)"
                    }
                },
                "required": ["key"]
            }
        }
    }
]


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

    async def list_models(self) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            r = await client.get(
                f"{self.config.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("data", [])

    def _build_body(self, messages: list[dict], stream: bool = False,
                    model: str | None = None, reasoning_effort: str | None = None,
                    max_tokens: int | None = None, temperature: float | None = None,
                    thinking: bool = True, tools: list[dict] | None = None) -> dict:
        body = {
            "model": model or self.config.model,
            "messages": messages,
            "stream": stream,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = tools

        extra = {}
        if thinking is False:
            extra["thinking"] = {"type": "disabled"}
        elif thinking is True:
            extra["thinking"] = {"type": "enabled"}
        if reasoning_effort is not None:
            body["reasoning_effort"] = reasoning_effort
        if extra:
            body["extra_body"] = extra
        return body

    async def chat(self, messages: list[dict], model: str | None = None,
                   reasoning_effort: str | None = None, max_tokens: int | None = None,
                   temperature: float | None = None, thinking: bool = True,
                   tools: list[dict] | None = None) -> ChatResponse:
        body = self._build_body(messages, stream=False, model=model,
                                reasoning_effort=reasoning_effort,
                                max_tokens=max_tokens, temperature=temperature,
                                thinking=thinking, tools=tools)
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            r = await client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers=self._headers, json=body,
            )
            r.raise_for_status()
            data = r.json()
            choice = data["choices"][0]
            msg = choice["message"]
            return ChatResponse(
                content=msg.get("content", ""),
                reasoning_content=msg.get("reasoning_content"),
                model=data.get("model", ""),
                usage=data.get("usage"),
                finish_reason=choice.get("finish_reason"),
                tool_calls=msg.get("tool_calls"),
            )

    async def chat_stream(self, messages: list[dict], model: str | None = None,
                          reasoning_effort: str | None = None,
                          max_tokens: int | None = None, temperature: float | None = None,
                          thinking: bool = True,
                          tools: list[dict] | None = None) -> AsyncIterator[StreamEvent]:
        body = self._build_body(messages, stream=True, model=model,
                                reasoning_effort=reasoning_effort,
                                max_tokens=max_tokens, temperature=temperature,
                                thinking=thinking, tools=tools)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers=self._headers, json=body,
            ) as resp:
                if resp.is_error:
                    err_text = await resp.aread()
                    yield ErrorEvent(error=err_text.decode())
                    return

                usage = None
                finish_reason = None
                # Accumulate tool call chunks across the stream
                tool_call_buffers: dict[int, dict] = {}

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    reason = delta.get("reasoning_content")
                    if reason:
                        yield ThinkingEvent(chunk=reason)

                    content = delta.get("content")
                    if content:
                        yield ContentEvent(chunk=content)

                    # Handle tool calls
                    tool_calls_delta = delta.get("tool_calls")
                    if tool_calls_delta:
                        for tc in tool_calls_delta:
                            idx = tc.get("index", 0)
                            if idx not in tool_call_buffers:
                                tool_call_buffers[idx] = {"id": None, "name": None, "arguments": ""}
                            buf = tool_call_buffers[idx]
                            if tc.get("id"):
                                buf["id"] = tc["id"]
                            if tc.get("function"):
                                fn = tc["function"]
                                if fn.get("name"):
                                    buf["name"] = fn["name"]
                                if fn.get("arguments"):
                                    buf["arguments"] += fn["arguments"]

                    fr = choices[0].get("finish_reason")
                    if fr:
                        finish_reason = fr

                    u = chunk.get("usage")
                    if u:
                        usage = u

                # Emit tool call events if any were accumulated
                if tool_call_buffers:
                    for idx in sorted(tool_call_buffers.keys()):
                        buf = tool_call_buffers[idx]
                        if buf["id"] and buf["name"]:
                            yield ToolCallEvent(
                                tool_call_id=buf["id"],
                                name=buf["name"],
                                arguments=buf["arguments"],
                            )

                yield DoneEvent(usage=usage, finish_reason=finish_reason)


def count_tokens(text: str) -> int:
    return len(text) // 2
