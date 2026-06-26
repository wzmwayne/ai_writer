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
            "description": "设置任意章节的标题。如果不指定 chapter_id 则默认为当前正在写的章节。提供 chapter_id 也可用于修正其他章节的标题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "章节标题（只需写标题本身，服务器自动补全「第X章」前缀）"
                    },
                    "chapter_id": {
                        "type": "string",
                        "description": "目标章节 ID（如 '0003'）。不传则默认为当前章节。用于修改其他章节标题时指定。"
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
    },
    {
        "type": "function",
        "function": {
            "name": "rewrite_lines",
            "description": "重写指定章节的指定行范围[start_line, end_line)。行号从1开始，end_line不包含。用于局部修改章节内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_id": {
                        "type": "string",
                        "description": "章节 ID（例如 '0003'）"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "起始行号（1-based, inclusive）"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "结束行号（1-based, exclusive）"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "替换后的新正文内容（多行）"
                    }
                },
                "required": ["chapter_id", "start_line", "end_line", "new_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_text",
            "description": "在指定章节中将所有匹配 old_text 的文本替换为 new_text。适合修正错别字、统一术语、修改人名地名等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_id": {
                        "type": "string",
                        "description": "章节 ID（例如 '0003'）"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "要替换的原文本"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "替换后的新文本"
                    }
                },
                "required": ["chapter_id", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rewrite_chapter",
            "description": "【写新章专用】将 <starttext{content_id}!>...<!endtext!> 标签中的正文保存到指定章节。服务器自动在对话中查找标签并提取正文。这是唯一可将长篇正文保存到章节的工具——必须先在上一步输出正文标签（<starttext{content_id}!>正文<!endtext!>），再用此工具保存。注意此工具不会输出新内容到流中，它只是保存之前已输出的正文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_id": {
                        "type": "string",
                        "description": "目标章节 ID（例如 '0003'），必须是已存在的章节"
                    },
                    "content_id": {
                        "type": "string",
                        "description": "正文标签编号。服务器搜索对话中 <starttext{content_id}!>...<!endtext!> 提取正文并写入章节文件。"
                    }
                },
                "required": ["chapter_id", "content_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_chapter",
            "description": "【写新章专用】先在 content 中用 <text!>正文<?text?> 包裹输出正文（用户将看到流式输出），再调用此工具保存。服务器自动从上一轮对话提取标签正文。无标签 = 正文不会被保存。修改现有章节不要用此工具，如需修改请用 rewrite_lines 或 replace_text。误用会导致现有内容被覆盖。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_id": {
                        "type": "string",
                        "description": "目标章节 ID（例如 '0019'），必须是已存在的章节"
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
