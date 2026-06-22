from __future__ import annotations

import json
import os
import re
import tempfile

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import BASE_DIR

router = APIRouter(prefix="/api/chat", tags=["chat"])

CHATS_DIR = BASE_DIR / "chats"
CHATS_DIR.mkdir(exist_ok=True)

_SAFE_KEY = re.compile(r"^[a-zA-Z0-9_-]+$")


class ChatMessages(BaseModel):
    messages: list[dict]


def _key_path(key: str) -> str:
    if not _SAFE_KEY.match(key):
        raise HTTPException(400, "无效的聊天 key")
    return str(CHATS_DIR / f"{key}.json")


def _atomic_write(path, data: str):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@router.get("/{key}")
async def get_chat(key: str):
    path = _key_path(key)
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    return {"messages": data}


@router.put("/{key}")
async def save_chat(key: str, body: ChatMessages):
    path = _key_path(key)
    _atomic_write(path, json.dumps(body.messages, indent=2, ensure_ascii=False))
    return {"ok": True}
