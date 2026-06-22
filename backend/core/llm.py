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
            "description": "存储跨章节持久信息（角色、情节、世界观）。content 应以 [ChX] 开头标明章节来源。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "唯一标识符（英文/拼音）。建议前缀 char_/plot_/rule_"
                    },
                    "content": {
                        "type": "string",
                        "description": "[ChX] 需要记住的信息的详细描述"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选分类标签"
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
            "description": "按关键词搜索已存储的记忆，检索跨章节信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词。使用空字符串（\"\"）列出全部记忆。"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_chapter_title",
            "description": "在写入正文前设置当前章节标题。先调用此工具，然后输出纯净正文（不含标题行）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "章节标题"
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
            "description": "按 key 删除记忆。用于在读取全部记忆后清理过期或错误的条目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "要删除的记忆 key（例如 char_old、plot_stale）"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "chapter_list",
            "description": "列出当前项目的所有章节，返回章节 ID 和标题。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "chapter_read",
            "description": "按章节 ID 读取指定章节的完整内容。先用 chapter_list 获取章节 ID。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_id": {
                        "type": "string",
                        "description": "要读取的章节 ID（例如 '0001'）"
                    }
                },
                "required": ["chapter_id"]
            }
        }
    }
]


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._headers = {"Content-Type": "application/json"}
        if config.api_key:
            self._headers["Authorization"] = f"Bearer {config.api_key}"

    async def list_models(self) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            r = await client.get(
                f"{self.config.base_url.rstrip('/')}/models",
                headers=headers,
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
