from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from config import HOST, PORT, BASE_DIR
from api.projects import router as projects_router
from api.chapters import router as chapters_router
from api.writing import router as writing_router
from api.settings import router as settings_router
from api.chat import router as chat_router
from api.memory import router as memory_router

app = FastAPI(
    title="AI Novel Forge",
    version="0.1.0",
    description="AI 小说写作工坊",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(chapters_router)
app.include_router(writing_router)
app.include_router(settings_router)
app.include_router(chat_router)
app.include_router(memory_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve static frontend
frontend_dir = BASE_DIR / "frontend"
frontend_dir.mkdir(exist_ok=True)
app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")


@app.get("/js/{filename:path}")
async def serve_js(filename: str):
    js_file = frontend_dir / "js" / filename
    if not js_file.exists() or not js_file.is_file():
        return Response("", status_code=404)
    content = js_file.read_bytes()
    return Response(content=content, media_type="application/javascript",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    file_path = frontend_dir / "index.html"
    if file_path.exists():
        return FileResponse(str(file_path))
    return JSONResponse({"detail": "Not Found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*50}")
    print(f"  AI Novel Forge 启动...")
    print(f"  地址: http://{HOST}:{PORT}")
    print(f"  文档: http://{HOST}:{PORT}/docs")
    print(f"{'='*50}\n")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
