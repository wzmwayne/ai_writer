from __future__ import annotations
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile, File

from core.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from services import epub_engine as ee

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects():
    projects = ee.list_projects()
    items = []
    for p in projects:
        items.append(ProjectResponse(
            id=p["id"],
            title=p["title"],
            author=p.get("author", ""),
            lang=p.get("lang", "zh-CN"),
            outline=p.get("outline", ""),
            setting=p.get("setting", ""),
            chapter_count=len(p.get("chapters", [])),
            words_per_chapter=p.get("words_per_chapter", 0) or 0,
            expected_chapters=p.get("expected_chapters", 0) or 0,
            created_at=p.get("created_at", ""),
            updated_at=p.get("updated_at", ""),
        ))
    return ProjectListResponse(projects=items)


def _project_response(meta: dict) -> ProjectResponse:
    return ProjectResponse(
        id=meta["id"],
        title=meta["title"],
        author=meta.get("author", ""),
        lang=meta.get("lang", "zh-CN"),
        outline=meta.get("outline", ""),
        setting=meta.get("setting", ""),
        chapter_count=len(meta.get("chapters", [])),
        words_per_chapter=meta.get("words_per_chapter", 0) or 0,
        expected_chapters=meta.get("expected_chapters", 0) or 0,
        created_at=meta.get("created_at", ""),
        updated_at=meta.get("updated_at", ""),
    )


@router.post("", response_model=ProjectResponse)
async def create_project(body: ProjectCreate):
    meta = ee.create_project(body.title, body.author, body.lang)
    return _project_response(meta)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    meta = ee.get_project(project_id)
    if not meta:
        raise HTTPException(404, "项目不存在")
    return _project_response(meta)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def patch_project(project_id: str, body: ProjectUpdate):
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    meta = ee.update_project_meta(project_id, **kwargs)
    if not meta:
        raise HTTPException(404, "项目不存在")
    return _project_response(meta)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    if not ee.delete_project(project_id):
        raise HTTPException(404, "项目不存在")
    return {"ok": True}


@router.post("/import")
async def import_project(file: UploadFile = File(...)):
    content = await file.read()
    meta = ee.import_epub(content, file.filename or "")
    return _project_response(meta)


@router.get("/{project_id}/export")
async def export_project(project_id: str):
    from fastapi.responses import Response
    try:
        epub_bytes = ee.export_epub(project_id)
    except ValueError:
        raise HTTPException(404, "项目不存在")
    meta = ee.get_project(project_id)
    filename = f"{meta['title']}.epub" if meta else "novel.epub"
    encoded = quote(filename, safe='')
    return Response(
        content=epub_bytes,
        media_type="application/epub+zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
