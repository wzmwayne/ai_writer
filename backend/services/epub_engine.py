from __future__ import annotations

import json
import uuid
import re
import zipfile
import io
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import markdown as md_lib

from config import NOVELS_DIR, BASE_DIR

_CHATS_DIR = BASE_DIR / "chats"
_MEMORIES_DIR = BASE_DIR / "data" / "memories"


def _project_dir(project_id: str) -> Path:
    return NOVELS_DIR / project_id


def _chapters_dir(project_id: str) -> Path:
    d = _project_dir(project_id) / "chapters"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _images_dir(project_id: str) -> Path:
    d = _project_dir(project_id) / "images"
    d.mkdir(exist_ok=True)
    return d


def _meta_path(project_id: str) -> Path:
    return _project_dir(project_id) / "project.json"


def _md_to_xhtml(md_text: str) -> str:
    html = md_lib.markdown(md_text, extensions=["extra", "codehilite"])
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" type="text/css" href="../styles/epub.css"/>
</head>
<body>
{html}
</body>
</html>"""


def _read_markdown(filepath: Path) -> str:
    if not filepath.exists():
        return ""
    return filepath.read_text(encoding="utf-8")


def _write_markdown(filepath: Path, content: str):
    filepath.write_text(content, encoding="utf-8")


def _chapter_file(project_id: str, chapter_id: str) -> Path:
    return _chapters_dir(project_id) / f"{chapter_id}.md"


def _chapter_id_from_file(fname: str) -> tuple[str, int]:
    stem = Path(fname).stem
    parts = stem.split("_", 1)
    order = int(parts[0]) if parts[0].isdigit() else 0
    return stem, order


def _next_chapter_id(project_id: str) -> str:
    existing = sorted(_chapters_dir(project_id).glob("*.md"))
    if not existing:
        return "0001"
    last = existing[-1].stem
    try:
        num = int(last.split("_")[0]) + 1
    except ValueError:
        num = len(existing) + 1
    return f"{num:04d}"


def _load_meta(project_id: str) -> dict:
    p = _meta_path(project_id)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _save_meta(project_id: str, data: dict):
    _meta_path(project_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


# ── Public API ──

def create_project(title: str, author: str = "", lang: str = "zh-CN") -> dict:
    project_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "id": project_id,
        "title": title,
        "author": author,
        "lang": lang,
        "cover": None,
        "outline": "",
        "setting": "",
        "chapters": [],
        "created_at": now,
        "updated_at": now,
    }
    _project_dir(project_id).mkdir(parents=True, exist_ok=True)
    _save_meta(project_id, meta)
    return meta


def delete_project(project_id: str) -> bool:
    import shutil
    d = _project_dir(project_id)
    if d.exists():
        shutil.rmtree(d)
        return True
    return False


def list_projects() -> list[dict]:
    projects = []
    for d in sorted(NOVELS_DIR.iterdir()):
        if d.is_dir():
            meta = _load_meta(d.name)
            if meta:
                projects.append(meta)
    return sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True)


def get_project(project_id: str) -> Optional[dict]:
    meta = _load_meta(project_id)
    if not meta:
        return None
    meta["chapter_count"] = len(meta.get("chapters", []))
    return meta


def update_project_meta(project_id: str, **kwargs) -> Optional[dict]:
    meta = _load_meta(project_id)
    if not meta:
        return None
    changed = False
    for k, v in kwargs.items():
        if v is not None:
            if k not in meta:
                meta[k] = ''  # 旧项目可能缺少字段
            meta[k] = v
            changed = True
    if changed:
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_meta(project_id, meta)
    return get_project(project_id)


def add_chapter(project_id: str, title: str, content: str = "") -> dict:
    meta = _load_meta(project_id)
    if not meta:
        raise ValueError("项目不存在")

    chapter_id = _next_chapter_id(project_id)
    fname = _chapter_file(project_id, chapter_id)
    _write_markdown(fname, content)

    chapter_entry = {"id": chapter_id, "title": title}
    meta.setdefault("chapters", []).append(chapter_entry)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_meta(project_id, meta)

    return {"id": chapter_id, "title": title, "content": content, "order": len(meta["chapters"])}


def list_chapters(project_id: str) -> list[dict]:
    meta = _load_meta(project_id)
    if not meta:
        raise ValueError("项目不存在")
    chapters = []
    for i, entry in enumerate(meta.get("chapters", [])):
        cid = entry["id"]
        content = _read_markdown(_chapter_file(project_id, cid))
        chapters.append({
            "id": cid,
            "title": entry.get("title", ""),
            "content": content,
            "order": i + 1,
        })
    return chapters


def get_chapter(project_id: str, chapter_id: str) -> Optional[dict]:
    meta = _load_meta(project_id)
    if not meta:
        return None
    for i, entry in enumerate(meta.get("chapters", [])):
        if entry["id"] == chapter_id:
            content = _read_markdown(_chapter_file(project_id, chapter_id))
            return {"id": chapter_id, "title": entry.get("title", ""), "content": content, "order": i + 1}
    return None


def update_chapter(project_id: str, chapter_id: str, title: Optional[str] = None, content: Optional[str] = None) -> Optional[dict]:
    meta = _load_meta(project_id)
    if not meta:
        return None
    for entry in meta.get("chapters", []):
        if entry["id"] == chapter_id:
            if title is not None:
                entry["title"] = title
            if content is not None:
                _write_markdown(_chapter_file(project_id, chapter_id), content)
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_meta(project_id, meta)
            return get_chapter(project_id, chapter_id)
    return None


def delete_chapter(project_id: str, chapter_id: str) -> bool:
    meta = _load_meta(project_id)
    if not meta:
        return False
    chapters = meta.get("chapters", [])
    for i, entry in enumerate(chapters):
        if entry["id"] == chapter_id:
            fp = _chapter_file(project_id, chapter_id)
            if fp.exists():
                fp.unlink()
            chapters.pop(i)
            meta["chapters"] = chapters
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_meta(project_id, meta)
            return True
    return False


def reorder_chapters(project_id: str, chapter_ids: list[str]) -> bool:
    meta = _load_meta(project_id)
    if not meta:
        return False
    existing = {e["id"]: e["title"] for e in meta.get("chapters", [])}
    reordered = []
    for cid in chapter_ids:
        if cid in existing:
            reordered.append({"id": cid, "title": existing[cid]})
    for e in meta.get("chapters", []):
        if e["id"] not in existing:
            reordered.append(e)
    meta["chapters"] = reordered
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_meta(project_id, meta)
    return True


def _export_extra_data(meta: dict, zf: zipfile.ZipFile):
    """Embed project metadata, chats, and memories into the EPUB ZIP."""
    project_id = meta["id"]

    # ── project metadata (extended) ──
    extra_meta = {
        "outline": meta.get("outline", ""),
        "setting": meta.get("setting", ""),
        "words_per_chapter": meta.get("words_per_chapter", 0),
        "expected_chapters": meta.get("expected_chapters", 0),
    }
    zf.writestr("data/project.json", json.dumps(extra_meta, ensure_ascii=False, indent=2))

    # ── chats ──
    _CHATS_DIR.mkdir(parents=True, exist_ok=True)
    for entry in meta.get("chapters", []):
        cid = entry["id"]
        chat_key = f"proj_{project_id}_ch_{cid}"
        chat_path = _CHATS_DIR / f"{chat_key}.json"
        if chat_path.exists():
            zf.write(str(chat_path), f"data/chats/{chat_key}.json")

    # ── memories ──
    _MEMORIES_DIR.mkdir(parents=True, exist_ok=True)
    mem_path = _MEMORIES_DIR / f"{project_id}.json"
    if mem_path.exists():
        zf.write(str(mem_path), "data/memories.json")


def _import_extra_data(project_id: str, zf: zipfile.ZipFile) -> dict:
    """Restore project metadata, chats, and memories from the EPUB ZIP.
    Returns any extra metadata fields that should be merged into the project meta.
    """
    extra_meta = {}

    # ── project metadata ──
    if "data/project.json" in zf.namelist():
        try:
            extra_meta = json.loads(zf.read("data/project.json"))
        except (json.JSONDecodeError, KeyError):
            pass

    # ── chats ──
    for name in zf.namelist():
        if name.startswith("data/chats/") and name.endswith(".json"):
            _CHATS_DIR.mkdir(parents=True, exist_ok=True)
            fname = os.path.basename(name)
            # Rename chat key to match the new project ID
            if fname.startswith("proj_") and "_ch_" in fname:
                parts = fname.split("_ch_")
                old_prefix = parts[0]
                new_prefix = f"proj_{project_id}"
                fname = fname.replace(old_prefix, new_prefix, 1)
            dest = _CHATS_DIR / fname
            content = zf.read(name)
            # atomic write
            fd, tmp = tempfile.mkstemp(dir=str(_CHATS_DIR), suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                os.replace(tmp, dest)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    # ── memories ──
    if "data/memories.json" in zf.namelist():
        _MEMORIES_DIR.mkdir(parents=True, exist_ok=True)
        dest = _MEMORIES_DIR / f"{project_id}.json"
        content = zf.read("data/memories.json")
        fd, tmp = tempfile.mkstemp(dir=str(_MEMORIES_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.replace(tmp, dest)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    return extra_meta


def export_epub(project_id: str) -> bytes:
    meta = _load_meta(project_id)
    if not meta:
        raise ValueError("项目不存在")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")

        container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        zf.writestr("META-INF/container.xml", container)

        book_uuid = str(uuid.uuid4())
        manifest_items = []
        spine_items = []
        nav_points = []

        for i, entry in enumerate(meta.get("chapters", [])):
            cid = entry["id"]
            ctitle = entry.get("title", f"第{i+1}章")
            md_content = _read_markdown(_chapter_file(project_id, cid))
            xhtml_content = _md_to_xhtml(md_content)

            xhtml_path = f"OEBPS/Text/chapter_{cid}.xhtml"
            zf.writestr(xhtml_path, xhtml_content.encode("utf-8"))

            item_id = f"ch_{cid}"
            manifest_items.append(
                f'    <item id="{item_id}" href="Text/chapter_{cid}.xhtml" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'    <itemref idref="{item_id}"/>')
            nav_points.append(f"""    <navPoint id="nav_{item_id}" playOrder="{i+1}">
      <navLabel>
        <text>{ctitle}</text>
      </navLabel>
      <content src="Text/chapter_{cid}.xhtml"/>
    </navPoint>""")

        styles_path = "OEBPS/Styles/epub.css"
        zf.writestr(styles_path, """
@page { margin: 5%; }
body { font-family: serif; line-height: 1.8; }
h1 { text-align: center; font-size: 1.6em; margin: 2em 0 1em; }
h2 { font-size: 1.3em; margin: 1.5em 0 0.8em; }
p { text-indent: 2em; margin: 0.5em 0; }
""")
        manifest_items.append(
            '    <item id="css" href="Styles/epub.css" media-type="text/css"/>'
        )

        opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier id="BookId">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>{meta['title']}</dc:title>
    <dc:creator>{meta.get('author', '')}</dc:creator>
    <dc:language>{meta.get('lang', 'zh-CN')}</dc:language>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
{chr(10).join(manifest_items)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_items)}
  </spine>
  <guide>
    <reference type="toc" title="目录" href="toc.ncx"/>
  </guide>
</package>"""
        zf.writestr("OEBPS/content.opf", opf.encode("utf-8"))

        ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_uuid}"/>
  </head>
  <docTitle>
    <text>{meta['title']}</text>
  </docTitle>
  <navMap>
{chr(10).join(nav_points)}
  </navMap>
</ncx>"""
        zf.writestr("OEBPS/toc.ncx", ncx.encode("utf-8"))

        nav_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目录</title></head>
<body>
  <nav epub:type="toc">
    <h1>目录</h1>
    <ol>
{chr(10).join([f'      <li><a href="Text/chapter_{e["id"]}.xhtml">{e.get("title", f"第{i+1}章")}</a></li>' for i, e in enumerate(meta.get("chapters", []))])}
    </ol>
  </nav>
</body>
</html>"""
        zf.writestr("OEBPS/nav.xhtml", nav_xhtml.encode("utf-8"))

        # ── extra companion data ──
        _export_extra_data(meta, zf)

    buf.seek(0)
    return buf.getvalue()


def import_epub(file_bytes: bytes, filename: str = "") -> dict:
    project_id = str(uuid.uuid4())[:8]
    pdir = _project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)

    title = Path(filename).stem if filename else "导入的文档"
    author = ""

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        chapter_files = []
        for name in zf.namelist():
            if name.startswith("OEBPS/Text/") and name.endswith(".xhtml"):
                chapter_files.append(name)

        chapter_files.sort()

        chapters_meta = []
        for i, xhtml_path in enumerate(chapter_files):
            content = zf.read(xhtml_path).decode("utf-8")
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
            body_content = body_match.group(1).strip() if body_match else content

            md_content = _xhtml_to_md(body_content)
            cid = f"{i+1:04d}"
            _write_markdown(_chapter_file(project_id, cid), md_content)
            chapters_meta.append({"id": cid, "title": f"第{i+1}章"})

        opf_paths = [n for n in zf.namelist() if n.endswith("content.opf") or n.endswith("package.opf")]
        if opf_paths:
            opf_content = zf.read(opf_paths[0]).decode("utf-8")
            title_m = re.search(r'<dc:title[^>]*>(.*?)</dc:title>', opf_content)
            if title_m:
                title = title_m.group(1)
            author_m = re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', opf_content)
            if author_m:
                author = author_m.group(1)

        now = datetime.now(timezone.utc).isoformat()
        meta = {
            "id": project_id,
            "title": title,
            "author": author,
            "lang": "zh-CN",
            "cover": None,
            "chapters": chapters_meta,
            "created_at": now,
            "updated_at": now,
        }

        # Restore companion data (chats, memories, extended metadata)
        extra_meta = _import_extra_data(project_id, zf)
        for k, v in extra_meta.items():
            if v is not None and v != "":
                meta[k] = v

        _save_meta(project_id, meta)
        return meta


def _xhtml_to_md(html: str) -> str:
    import html as html_mod
    text = html_mod.unescape(html)
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1', text, flags=re.DOTALL)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', text, flags=re.DOTALL)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', text, flags=re.DOTALL)
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
