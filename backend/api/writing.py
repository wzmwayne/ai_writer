from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from core.llm import (
    LLMClient, LLMConfig, LLMClient,
    ThinkingEvent, ContentEvent, ToolCallEvent, DoneEvent, ErrorEvent,
    MEMORY_TOOLS,
)
from core.schemas import WriteRequest
from core.stream_cache import stream_cache
from core.memory import store_memory, search_memories, delete_memory_by_key, format_memories_for_prompt
from services.epub_engine import update_chapter as _update_chapter_title
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

router = APIRouter(prefix="/api", tags=["writing"])

_client_cache: dict[str, LLMClient] = {}


def _get_client(api_key: str | None = None, base_url: str | None = None) -> LLMClient:
    key = api_key or LLM_API_KEY
    url = base_url or LLM_BASE_URL
    cache_id = f"{key}:{url}"
    if cache_id not in _client_cache:
        _client_cache[cache_id] = LLMClient(LLMConfig(api_key=key, base_url=url))
    return _client_cache[cache_id]


def _inject_memories(messages: list[dict], project_id: str | None) -> list[dict]:
    """Inject project memories into the last system message or prepend a new one."""
    if not project_id:
        return messages
    memory_text = format_memories_for_prompt(project_id)
    if not memory_text:
        return messages
    msgs = list(messages)
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "system":
            msgs[i] = dict(msgs[i])
            msgs[i]["content"] = msgs[i]["content"].rstrip() + "\n\n" + memory_text
            return msgs
    msgs.insert(0, {"role": "system", "content": memory_text})
    return msgs


_tool_set_title: str | None = None  # set by set_chapter_title, read by frontend


async def _execute_tool(project_id: str, name: str, args: str, *, chapter_id: str | None = None) -> str:
    """Execute a tool call and return a natural language result string."""
    try:
        arguments = json.loads(args) if args else {}
    except json.JSONDecodeError:
        return '[Tool Error: invalid arguments JSON]'

    if name == "memory_store":
        key = arguments.get("key", "").strip()
        content = arguments.get("content", "").strip()
        tags = arguments.get("tags", [])
        if key and content:
            store_memory(project_id, key, content, tags)
            tag_str = f" (tags: {', '.join(tags)})" if tags else ""
            return f"[memory_store] Stored: {key} = {content}{tag_str}"
        return "[memory_store Error: missing 'key' or 'content']"

    elif name == "memory_read":
        query = arguments.get("query", "")
        results = search_memories(project_id, query)
        if not results:
            return f"[memory_read] No memories found matching: {query}"
        lines = [f"[memory_read] Found {len(results)} memory(s) matching '{query}':"]
        for m in results:
            tag_str = f" [{', '.join(m.get('tags', []))}]" if m.get('tags') else ""
            lines.append(f"  • {m['key']}: {m['content']}{tag_str}")
        return "\n".join(lines)

    elif name == "set_chapter_title":
        title = arguments.get("title", "").strip()
        if not title:
            return "[set_chapter_title Error: missing 'title']"
        global _tool_set_title
        _tool_set_title = title
        # Also update the chapter title in the database if chapter_id is known
        if chapter_id:
            try:
                _update_chapter_title(project_id, chapter_id, title=title)
            except Exception:
                pass
        return f"[set_chapter_title] Chapter title set to: {title}"

    elif name == "memory_delete":
        key = arguments.get("key", "").strip()
        if not key:
            return "[memory_delete Error: missing 'key']"
        found = delete_memory_by_key(project_id, key)
        if found:
            return f"[memory_delete] Deleted: {key}"
        return f"[memory_delete] Key not found: {key}"

    elif name == "chapter_list":
        from services.epub_engine import list_chapters
        chapters = list_chapters(project_id)
        lines = [f"[chapter_list] 共 {len(chapters)} 章："]
        for ch in chapters:
            lines.append(f"  {ch['id']}: {ch['title']}")
        return "\n".join(lines)

    elif name == "chapter_read":
        ch_id = arguments.get("chapter_id", "").strip()
        if not ch_id:
            return "[chapter_read Error: 缺少 chapter_id]"
        from services.epub_engine import get_chapter
        ch = get_chapter(project_id, ch_id)
        if not ch:
            return f"[chapter_read Error: 未找到章节 '{ch_id}']"
        return f"[chapter_read] 第 {ch.get('order', '?')} 章「{ch['title']}」：\n\n{ch.get('content', '')}"

    elif name == "rewrite_lines":
        ch_id = arguments.get("chapter_id", "").strip()
        start = arguments.get("start_line", 0)
        end = arguments.get("end_line", 0)
        new_content = arguments.get("new_content", "")
        if not ch_id or not new_content:
            return "[rewrite_lines Error: 缺少必要参数]"
        from services.epub_engine import rewrite_chapter_lines
        result = rewrite_chapter_lines(project_id, ch_id, int(start), int(end), new_content)
        if result is None:
            return f"[rewrite_lines Error: 未找到章节 '{ch_id}' 或行号无效]"
        return f"[rewrite_lines] 第 {result.get('order', '?')} 章「{result['title']}」行 {start}-{end} 已重写"

    elif name == "replace_text":
        ch_id = arguments.get("chapter_id", "").strip()
        old_text = arguments.get("old_text", "")
        new_text = arguments.get("new_text", "")
        if not ch_id or not old_text:
            return "[replace_text Error: 缺少必要参数]"
        from services.epub_engine import replace_chapter_text
        result = replace_chapter_text(project_id, ch_id, old_text, new_text)
        if result is None:
            return f"[replace_text Error: 未找到章节 '{ch_id}' 或未找到匹配文本]"
        return f"[replace_text] 第 {result.get('order', '?')} 章「{result['title']}」中「{old_text[:20]}」已替换为「{new_text[:20]}」"

    elif name == "rewrite_chapter":
        ch_id = arguments.get("chapter_id", "").strip()
        content = arguments.get("content", "")
        if not ch_id or not content:
            return "[rewrite_chapter Error: 缺少必要参数]"
        from services.epub_engine import update_chapter as _update_chapter_content
        result = _update_chapter_content(project_id, ch_id, content=content)
        if result is None:
            return f"[rewrite_chapter Error: 未找到章节 '{ch_id}']"
        return f"[rewrite_chapter] 第 {result.get('order', '?')} 章「{result['title']}」已全文重写"

    return f"[Tool Error: unknown tool '{name}']"


async def _run_ai_stream(sid: str, body: WriteRequest):
    """Background task: run AI stream with native tool calling, cache all events."""
    client = _get_client(api_key=body.api_key, base_url=body.api_base)
    messages = _inject_memories(body.messages, body.project_id)
    tools = MEMORY_TOOLS if body.project_id else None

    for _round in range(10):  # max 10 tool call rounds
        pending_tool: ToolCallEvent | None = None
        reasoning_parts: list[str] = []

        try:
            async for event in client.chat_stream(
                messages=messages,
                model=body.model or None,
                thinking=body.thinking,
                reasoning_effort=body.reasoning_effort,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                tools=tools,
            ):
                if isinstance(event, ThinkingEvent):
                    reasoning_parts.append(event.chunk)
                    stream_cache.append(sid, "thinking", {"reasoning": event.chunk})
                elif isinstance(event, ContentEvent):
                    stream_cache.append(sid, "content", {"content": event.chunk})
                elif isinstance(event, ToolCallEvent):
                    pending_tool = event
                elif isinstance(event, DoneEvent):
                    if pending_tool:
                        tasks = []
                        tool_calls_list = []
                        tc = pending_tool
                        tasks.append(_execute_tool(body.project_id, tc.name, tc.arguments, chapter_id=body.chapter_id))
                        tool_calls_list.append(tc)

                        stream_cache.append(sid, "tool_status", {
                            "name": pending_tool.name,
                            "arguments": pending_tool.arguments,
                            "tool_call_id": pending_tool.tool_call_id,
                        })

                        results = await asyncio.gather(*tasks)

                        # Cache tool_result for client display
                        for tc, result in zip(tool_calls_list, results):
                            stream_cache.append(sid, "tool_result", {
                                "name": tc.name,
                                "arguments": tc.arguments,
                                "result": result,
                                "tool_call_id": tc.tool_call_id,
                            })

                        # Append assistant message with tool calls + reasoning_content
                        assistant_msg: dict = {"role": "assistant", "content": None}
                        if reasoning_parts:
                            assistant_msg["reasoning_content"] = "".join(reasoning_parts)
                        api_tool_calls = []
                        for tc in tool_calls_list:
                            api_tool_calls.append({
                                "id": tc.tool_call_id,
                                "type": "function",
                                "function": {"name": tc.name, "arguments": tc.arguments},
                            })
                        assistant_msg["tool_calls"] = api_tool_calls
                        messages.append(assistant_msg)

                        # Append tool result messages
                        for tc, result in zip(tool_calls_list, results):
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.tool_call_id,
                                "content": result,
                            })

                        break
                    else:
                        stream_cache.append(sid, "done", {"usage": event.usage, "finish_reason": event.finish_reason})
                        stream_cache.mark_done(sid)
                        return
                elif isinstance(event, ErrorEvent):
                    stream_cache.append(sid, "error", {"error": event.error})
                    stream_cache.mark_error(sid, event.error)
                    return
        except Exception as e:
            stream_cache.append(sid, "error", {"error": str(e)})
            stream_cache.mark_error(sid, str(e))
            return
    else:
        # Max rounds reached without finishing
        stream_cache.append(sid, "error", {"error": "max tool call rounds reached"})
        stream_cache.mark_error(sid, "max tool call rounds reached")


@router.post("/write/async")
async def ai_write_async(body: WriteRequest):
    if not body.messages:
        raise HTTPException(400, "messages 不能为空")
    sid = stream_cache.create()
    asyncio.create_task(_run_ai_stream(sid, body))
    return {"stream_id": sid}


@router.post("/write")
async def ai_write(body: WriteRequest):
    if not body.messages:
        raise HTTPException(400, "messages 不能为空")

    client = _get_client(api_key=body.api_key, base_url=body.api_base)
    messages = _inject_memories(body.messages, body.project_id)
    tools = MEMORY_TOOLS if body.project_id else None
    sid = stream_cache.create()

    async def event_stream():
        nonlocal messages

        for _round in range(10):
            pending_tool: ToolCallEvent | None = None
            reasoning_parts: list[str] = []

            async for event in client.chat_stream(
                messages=messages,
                model=body.model or None,
                thinking=body.thinking,
                reasoning_effort=body.reasoning_effort,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                tools=tools,
            ):
                if isinstance(event, ThinkingEvent):
                    reasoning_parts.append(event.chunk)
                    payload = {"reasoning": event.chunk}
                    stream_cache.append(sid, "thinking", payload)
                    yield _make_sse("thinking", payload, sid)
                elif isinstance(event, ContentEvent):
                    payload = {"content": event.chunk}
                    stream_cache.append(sid, "content", payload)
                    yield _make_sse("content", payload, sid)
                elif isinstance(event, ToolCallEvent):
                    pending_tool = event
                elif isinstance(event, DoneEvent):
                    if pending_tool:
                        result = await _execute_tool(body.project_id, pending_tool.name, pending_tool.arguments, chapter_id=body.chapter_id)

                        stream_cache.append(sid, "tool_status", {
                            "name": pending_tool.name,
                            "arguments": pending_tool.arguments,
                            "tool_call_id": pending_tool.tool_call_id,
                        })
                        yield _make_sse("tool_status", {
                            "name": pending_tool.name,
                            "arguments": pending_tool.arguments,
                            "tool_call_id": pending_tool.tool_call_id,
                        }, sid)

                        stream_cache.append(sid, "tool_result", {
                            "name": pending_tool.name,
                            "arguments": pending_tool.arguments,
                            "result": result,
                            "tool_call_id": pending_tool.tool_call_id,
                        })
                        yield _make_sse("tool_result", {
                            "name": pending_tool.name,
                            "result": result,
                            "tool_call_id": pending_tool.tool_call_id,
                        }, sid)

                        assistant_msg: dict = {"role": "assistant", "content": None, "tool_calls": [{
                            "id": pending_tool.tool_call_id,
                            "type": "function",
                            "function": {"name": pending_tool.name, "arguments": pending_tool.arguments},
                        }]}
                        if reasoning_parts:
                            assistant_msg["reasoning_content"] = "".join(reasoning_parts)
                        messages.append(assistant_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": pending_tool.tool_call_id,
                            "content": result,
                        })
                        break  # next round
                    else:
                        payload = {"usage": event.usage, "finish_reason": event.finish_reason}
                        stream_cache.append(sid, "done", payload)
                        stream_cache.mark_done(sid)
                        yield _make_sse("done", payload, sid)
                        return
                elif isinstance(event, ErrorEvent):
                    payload = {"error": event.error}
                    stream_cache.append(sid, "error", payload)
                    stream_cache.mark_error(sid, event.error)
                    yield _make_sse("error", payload, sid)
                    return
            else:
                # No break, stream ended without tool call
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _make_sse(event_type: str, data: dict, stream_id: str) -> str:
    data["stream_id"] = stream_id
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/write/recover/{stream_id}")
async def recover_stream(stream_id: str, since: int = Query(-1, ge=-1)):
    result = stream_cache.get_events_since(stream_id, since)
    if result is None:
        raise HTTPException(404, "流不存在或已过期")
    return result


@router.post("/write/non-stream")
async def ai_write_non_stream(body: WriteRequest):
    if not body.messages:
        raise HTTPException(400, "messages 不能为空")
    client = _get_client()
    messages = _inject_memories(body.messages, body.project_id)
    tools = MEMORY_TOOLS if body.project_id else None

    for _round in range(10):
        resp = await client.chat(
            messages=messages,
            model=body.model or None,
            thinking=body.thinking,
            reasoning_effort=body.reasoning_effort,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            tools=tools,
        )
        if resp.tool_calls:
            for tc in resp.tool_calls:
                if tc["type"] == "function":
                    fn = tc["function"]
                    result = await _execute_tool(body.project_id, fn["name"], fn["arguments"], chapter_id=body.chapter_id)
                    assistant_msg: dict = {"role": "assistant", "content": None, "tool_calls": [tc]}
                    if resp.reasoning_content:
                        assistant_msg["reasoning_content"] = resp.reasoning_content
                    messages.append(assistant_msg)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            continue  # next round
        return {
            "content": resp.content,
            "reasoning_content": resp.reasoning_content,
            "model": resp.model,
            "usage": resp.usage,
            "finish_reason": resp.finish_reason,
        }

    return {"error": "max tool call rounds reached"}


@router.get("/models")
async def list_models():
    client = _get_client()
    models = await client.list_models()
    return {"models": models}
