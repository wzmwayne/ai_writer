from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.schemas import ChapterCreate, ChapterUpdate, ChapterResponse, ChapterReorder
from services import epub_engine as ee

router = APIRouter(prefix="/api/projects/{project_id}/chapters", tags=["chapters"])


@router.get("")
async def list_chapters(project_id: str):
    try:
        chapters = ee.list_chapters(project_id)
    except ValueError:
        raise HTTPException(404, "项目不存在")
    return {"chapters": [ChapterResponse(**c) for c in chapters]}


@router.post("", response_model=ChapterResponse)
async def create_chapter(project_id: str, body: ChapterCreate):
    try:
        ch = ee.add_chapter(project_id, body.title, body.content)
    except ValueError:
        raise HTTPException(404, "项目不存在")
    return ChapterResponse(**ch)


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(project_id: str, chapter_id: str):
    ch = ee.get_chapter(project_id, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    return ChapterResponse(**ch)


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(project_id: str, chapter_id: str, body: ChapterUpdate):
    ch = ee.update_chapter(project_id, chapter_id, body.title, body.content)
    if not ch:
        raise HTTPException(404, "章节不存在")
    return ChapterResponse(**ch)


@router.delete("/{chapter_id}")
async def delete_chapter(project_id: str, chapter_id: str):
    if not ee.delete_chapter(project_id, chapter_id):
        raise HTTPException(404, "章节不存在")
    return {"ok": True}


@router.put("/reorder")
async def reorder_chapters(project_id: str, body: ChapterReorder):
    if not ee.reorder_chapters(project_id, body.chapter_ids):
        raise HTTPException(404, "项目不存在")
    return {"ok": True}
