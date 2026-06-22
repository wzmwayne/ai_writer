from __future__ import annotations

import json
import os
import tempfile

from fastapi import APIRouter

from config import SETTINGS_FILE
from core.schemas import AppSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _atomic_write(path, data: str):
    """Write to temp file then rename for atomicity."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    return json.loads(SETTINGS_FILE.read_text())


def _save_settings(data: dict):
    _atomic_write(SETTINGS_FILE, json.dumps(data, indent=2, ensure_ascii=False))


@router.get("", response_model=AppSettings)
async def get_settings():
    saved = _load_settings()
    defaults = AppSettings()
    merged = {}
    for field in defaults.model_dump():
        if field in saved and saved[field] != "":
            merged[field] = saved[field]
    return AppSettings(**merged)


@router.put("", response_model=AppSettings)
async def update_settings(body: AppSettings):
    _save_settings(body.model_dump())
    return body
