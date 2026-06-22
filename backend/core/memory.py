from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "data" / "memories"


def _ensure_project(project_id: str) -> Path:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    f = MEMORY_DIR / f"{project_id}.json"
    if not f.exists():
        f.write_text('{"memories":[]}', encoding="utf-8")
    return f


def _load_project(project_id: str) -> dict:
    f = _ensure_project(project_id)
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {"memories": []}


def _save_project(project_id: str, data: dict):
    f = _ensure_project(project_id)
    tmp = f.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def store_memory(project_id: str, key: str, content: str, tags: list[str] | None = None) -> dict:
    data = _load_project(project_id)
    entry = {
        "id": uuid.uuid4().hex[:16],
        "key": key,
        "content": content,
        "tags": tags or [],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # upsert by key
    for i, m in enumerate(data["memories"]):
        if m["key"] == key:
            data["memories"][i] = entry
            _save_project(project_id, data)
            return entry
    data["memories"].append(entry)
    _save_project(project_id, data)
    return entry


def get_memory(project_id: str, key: str) -> dict | None:
    data = _load_project(project_id)
    for m in data["memories"]:
        if m["key"] == key:
            return m
    return None


def search_memories(project_id: str, query: str = "") -> list[dict]:
    data = _load_project(project_id)
    if not query:
        return data["memories"]
    q = query.lower()
    return [
        m for m in data["memories"]
        if q in m["key"].lower() or q in m["content"].lower() or any(q in t.lower() for t in m.get("tags", []))
    ]


def update_memory_by_id(project_id: str, memory_id: str, key: str | None = None,
                         content: str | None = None, tags: list[str] | None = None) -> dict | None:
    """Update a memory entry by ID. Returns updated entry or None if not found."""
    data = _load_project(project_id)
    for m in data["memories"]:
        if m["id"] == memory_id:
            if key is not None:
                m["key"] = key
            if content is not None:
                m["content"] = content
            if tags is not None:
                m["tags"] = tags
            _save_project(project_id, data)
            return m
    return None


def delete_memory(project_id: str, memory_id: str) -> bool:
    data = _load_project(project_id)
    before = len(data["memories"])
    data["memories"] = [m for m in data["memories"] if m["id"] != memory_id]
    if len(data["memories"]) == before:
        return False
    _save_project(project_id, data)
    return True


def delete_memory_by_key(project_id: str, key: str) -> bool:
    """Delete a memory entry by key. Returns True if found and deleted."""
    data = _load_project(project_id)
    before = len(data["memories"])
    data["memories"] = [m for m in data["memories"] if m["key"] != key]
    if len(data["memories"]) == before:
        return False
    _save_project(project_id, data)
    return True


def format_memories_for_prompt(project_id: str, query: str = "") -> str:
    """Return memories formatted for injection into system prompt."""
    memories = search_memories(project_id, query)
    if not memories:
        return ""
    lines = ["以下是你已知的作品记忆信息："]
    for m in memories:
        tags = f"[{','.join(m['tags'])}] " if m.get("tags") else ""
        lines.append(f"- {tags}{m['key']}：{m['content']}")
    lines.append("")
    return "\n".join(lines)
