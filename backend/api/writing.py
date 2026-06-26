from __future__ import annotations

import asyncio
import json
import re

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


async def _execute_tool(project_id: str, name: str, args: str, *, chapter_id: str | None = None, messages: list | None = None) -> str:
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
        target_ch_id = (arguments.get("chapter_id") or "").strip() or chapter_id
        # Auto-format title with "第N章" prefix
        corrected = False
        if target_ch_id:
            try:
                from services.epub_engine import list_chapters
                ch_list = list_chapters(project_id)
                for i, ch in enumerate(ch_list):
                    if ch['id'] == target_ch_id:
                        expected = f"第{i + 1}章"
                        # Normalize: strip existing "第X章" prefix (with or without spaces)
                        import re as _re
                        clean = _re.sub(r'^第\s*\d+\s*章\s*', '', title).strip()
                        if clean != title:
                            title = clean
                            corrected = True
                        if not title.startswith(expected) and not title.startswith(expected.replace('第', '第 ')):
                            title = f"{expected} {title}"
                            corrected = True
                        break
            except Exception:
                pass
        global _tool_set_title
        _tool_set_title = title
        if target_ch_id:
            try:
                _update_chapter_title(project_id, target_ch_id, title=title)
            except Exception:
                pass
        msg = f"[set_chapter_title] Chapter {target_ch_id} title set to: {title}"
        if corrected:
            msg += " (已自动纠正标题格式)"
        return msg

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
        content_id = arguments.get("content_id", "").strip()
        if not ch_id or not content_id:
            return "[rewrite_chapter Error: 缺少 chapter_id 或 content_id]"
        # Search messages for <starttext{content_id}!>...<!endtext!>
        body = ""
        patterns = [f"<starttext{content_id}!>(.*?)<!endtext!>", r"<text!>(.*?)<\?text\?>"]
        if messages:
            for msg in reversed(messages):
                text = msg.get("content") or ""
                for pat in patterns:
                    for m in re.finditer(pat, text, re.DOTALL):
                        cand = m.group(1).strip()
                        if len(cand) > len(body):
                            body = cand
                if body:
                    break
        if not body:
            return "[rewrite_chapter Error: 未在对话中找到匹配标签]"
        from services.epub_engine import update_chapter as _update_chapter_content
        result = _update_chapter_content(project_id, ch_id, content=body)
        if result is None:
            return f"[rewrite_chapter Error: 未找到章节 '{ch_id}']"
        return f"[rewrite_chapter] 第 {result.get('order', '?')} 章「{result['title']}」已通过标签 #{content_id} 保存正文"

    elif name == "write_chapter":
        ch_id = arguments.get("chapter_id", "").strip()
        if not ch_id:
            return "[write_chapter Error: 缺少 chapter_id]"
        # Search last 3 assistant messages for <text!>...<?text?> tags
        body = ""
        assistant_count = 0
        if messages:
            for msg in reversed(messages):
                if msg.get("role") != "assistant":
                    continue
                assistant_count += 1
                if assistant_count > 3:
                    break
                text = msg.get("content") or ""
                candidates = []
                for m in re.finditer(r'<text!>(.*?)<\?text\?>', text, re.DOTALL):
                    candidates.append(m.group(1).strip())
                if candidates:
                    body = max(candidates, key=len)
                    break
        if not body:
            return "[write_chapter Error: 未检测到 <text!>...<?text?> 标签。**必须**在 content 中用 <text!>正文<?text?> 包裹正文再调用此工具。示例：content=\"<text!>这是正文内容<?text?>\"，然后调用 write_chapter。标签不可省略。]"
        from services.epub_engine import update_chapter as _update_chapter_content
        result = _update_chapter_content(project_id, ch_id, content=body)
        if result is None:
            return f"[write_chapter Error: 未找到章节 '{ch_id}']"
        return f"[write_chapter] 第 {result.get('order', '?')} 章「{result['title']}」已保存正文（{len(body)} 字）"

    return f"[Tool Error: unknown tool '{name}']"


async def _run_ai_stream(sid: str, body: WriteRequest):
    """Background task: run AI stream with native tool calling, cache all events."""
    client = _get_client(api_key=body.api_key, base_url=body.api_base)
    messages = _inject_memories(body.messages, body.project_id)
    tools = MEMORY_TOOLS if body.project_id else None

    for _round in range(10):  # max 10 tool call rounds
        pending_tools: list[ToolCallEvent] = []
        reasoning_parts: list[str] = []
        content_parts: list[str] = []

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
                    content_parts.append(event.chunk)
                    stream_cache.append(sid, "content", {"content": event.chunk})
                elif isinstance(event, ToolCallEvent):
                    pending_tools.append(event)
                elif isinstance(event, DoneEvent):
                    if pending_tools:
                        tasks = []
                        for tc in pending_tools:
                            tasks.append(_execute_tool(
                                body.project_id, tc.name, tc.arguments,
                                chapter_id=body.chapter_id, messages=messages))

                            stream_cache.append(sid, "tool_status", {
                                "name": tc.name,
                                "arguments": tc.arguments,
                                "tool_call_id": tc.tool_call_id,
                            })

                        results = await asyncio.gather(*tasks)

                        # Cache tool_result for client display
                        for tc, result in zip(pending_tools, results):
                            stream_cache.append(sid, "tool_result", {
                                "name": tc.name,
                                "arguments": tc.arguments,
                                "result": result,
                                "tool_call_id": tc.tool_call_id,
                            })

                        # Append assistant message with content + tool calls + reasoning
                        assistant_msg: dict = {"role": "assistant"}
                        assistant_msg["content"] = "".join(content_parts) if content_parts else None
                        if reasoning_parts:
                            assistant_msg["reasoning_content"] = "".join(reasoning_parts)
                        api_tool_calls = []
                        for tc in pending_tools:
                            api_tool_calls.append({
                                "id": tc.tool_call_id,
                                "type": "function",
                                "function": {"name": tc.name, "arguments": tc.arguments},
                            })
                        assistant_msg["tool_calls"] = api_tool_calls
                        messages.append(assistant_msg)

                        # Append tool result messages
                        for tc, result in zip(pending_tools, results):
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.tool_call_id,
                                "content": result,
                            })

                        # Switch to write-only mode: remove all tools except rewrite_chapter
                        tools = [t for t in (tools or []) if t["function"]["name"] == "write_chapter"]
                        messages.append({
                            "role": "system",
                            "content": "进入仅写入模式。所有读取工作已完成。现在只允许调用 write_chapter(chapter_id, content) 将正文保存到章节文件。禁止任何读取操作。"
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
        nonlocal messages, tools

        for _round in range(10):
            pending_tools: list[ToolCallEvent] = []
            reasoning_parts: list[str] = []
            content_parts: list[str] = []

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
                    content_parts.append(event.chunk)
                    payload = {"content": event.chunk}
                    stream_cache.append(sid, "content", payload)
                    yield _make_sse("content", payload, sid)
                elif isinstance(event, ToolCallEvent):
                    pending_tools.append(event)
                elif isinstance(event, DoneEvent):
                    if pending_tools:
                        # Execute all tools in parallel
                        tasks = [_execute_tool(
                            body.project_id, tc.name, tc.arguments,
                            chapter_id=body.chapter_id, messages=messages) for tc in pending_tools]
                        results = await asyncio.gather(*tasks)

                        for tc, result in zip(pending_tools, results):
                            stream_cache.append(sid, "tool_status", {
                                "name": tc.name, "arguments": tc.arguments,
                                "tool_call_id": tc.tool_call_id,
                            })
                            yield _make_sse("tool_status", {
                                "name": tc.name, "arguments": tc.arguments,
                                "tool_call_id": tc.tool_call_id,
                            }, sid)

                            stream_cache.append(sid, "tool_result", {
                                "name": tc.name, "arguments": tc.arguments,
                                "result": result, "tool_call_id": tc.tool_call_id,
                            })
                            yield _make_sse("tool_result", {
                                "name": tc.name, "result": result,
                                "tool_call_id": tc.tool_call_id,
                            }, sid)

                        assistant_msg: dict = {"role": "assistant"}
                        assistant_msg["content"] = "".join(content_parts) if content_parts else None
                        assistant_msg["tool_calls"] = [
                            {"id": tc.tool_call_id, "type": "function",
                             "function": {"name": tc.name, "arguments": tc.arguments}}
                            for tc in pending_tools
                        ]
                        if reasoning_parts:
                            assistant_msg["reasoning_content"] = "".join(reasoning_parts)
                        messages.append(assistant_msg)
                        for tc, result in zip(pending_tools, results):
                            messages.append({"role": "tool", "tool_call_id": tc.tool_call_id, "content": result})
                        # Switch to write-only mode
                        tools = [t for t in (tools or []) if t["function"]["name"] == "write_chapter"]
                        messages.append({
                            "role": "system",
                            "content": "进入仅写入模式。所有读取工作已完成。现在只允许调用 write_chapter(chapter_id, content) 将正文保存到章节文件。禁止任何读取操作。"
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
                    result = await _execute_tool(
                        body.project_id, fn["name"], fn["arguments"],
                        chapter_id=body.chapter_id, messages=messages)
                    assistant_msg: dict = {"role": "assistant", "content": resp.content or None, "tool_calls": [tc]}
                    if resp.reasoning_content:
                        assistant_msg["reasoning_content"] = resp.reasoning_content
                    messages.append(assistant_msg)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            # Switch to write-only mode after first tool round
            tools = [t for t in (tools or []) if t["function"]["name"] == "write_chapter"]
            messages.append({
                "role": "system",
                "content": "进入仅写入模式。所有读取工作已完成。现在只允许调用 write_chapter(chapter_id, content) 将正文保存到章节文件。禁止任何读取操作。"
            })
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
