from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.memory import (
    store_memory,
    get_memory,
    search_memories,
    delete_memory,
    update_memory_by_id,
    format_memories_for_prompt,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryStoreRequest(BaseModel):
    key: str
    content: str
    tags: list[str] = []


class MemoryUpdateRequest(BaseModel):
    key: str | None = None
    content: str | None = None
    tags: list[str] | None = None


@router.get("/{project_id}/prompt")
async def memory_prompt_text(project_id: str, q: str = Query("", description="搜索关键词")):
    text = format_memories_for_prompt(project_id, q)
    return {"text": text}


@router.get("/{project_id}")
async def list_memories(project_id: str, q: str = Query("", description="搜索关键词")):
    memories = search_memories(project_id, q)
    return {"memories": memories}


@router.get("/{project_id}/{key}")
async def read_memory(project_id: str, key: str):
    m = get_memory(project_id, key)
    if not m:
        raise HTTPException(404, "记忆不存在")
    return m


@router.post("/{project_id}")
async def create_memory(project_id: str, body: MemoryStoreRequest):
    entry = store_memory(project_id, body.key, body.content, body.tags)
    return entry


@router.put("/{project_id}/{memory_id}")
async def edit_memory(project_id: str, memory_id: str, body: MemoryUpdateRequest):
    m = update_memory_by_id(project_id, memory_id, key=body.key, content=body.content, tags=body.tags)
    if not m:
        raise HTTPException(404, "记忆不存在")
    return m


@router.delete("/{project_id}/{memory_id}")
async def remove_memory(project_id: str, memory_id: str):
    if not delete_memory(project_id, memory_id):
        raise HTTPException(404, "记忆不存在")
    return {"ok": True}


