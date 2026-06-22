#!/usr/bin/env python3
"""Full integration test: start server, test API, test frontend"""
import subprocess, time, sys, os, json, httpx
from pathlib import Path

os.chdir(Path(__file__).parent)
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
BASE = "http://localhost:8000"
for _ in range(20):
    try:
        httpx.get(BASE, timeout=3)
        break
    except Exception:
        time.sleep(0.5)
ok = 0
fail = 0

def t(name, fn):
    global ok, fail
    try:
        fn()
        print(f"  [OK] {name}")
        ok += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        fail += 1

def get(path):
    r = httpx.get(f"{BASE}{path}", timeout=15)
    return r

def post(path, data):
    h = {"Content-Type": "application/json"}
    r = httpx.post(f"{BASE}{path}", json=data, headers=h, timeout=15)
    return r

def delete(path):
    r = httpx.delete(f"{BASE}{path}", timeout=15)
    return r

def put(path, data):
    r = httpx.put(f"{BASE}{path}", json=data, headers={"Content-Type": "application/json"}, timeout=15)
    return r

print("="*50)
print("  Full Integration Test")
print("="*50)

# 1. Health
t("Health", lambda: (lambda r: (r.status_code == 200 and r.json()["status"] == "ok") or 1/0)(get("/api/health")))

# 2. Frontend HTML
t("Frontend serves", lambda: (lambda r: (r.status_code == 200 and "Novel Forge" in r.text) or 1/0)(get("/")))

# 3. Settings
t("Settings GET", lambda: (lambda r: (r.status_code == 200) or 1/0)(get("/api/settings")))

# 4. Settings PUT
t("Settings PUT", lambda: (lambda r: (r.status_code == 200 and r.json().get("model") == "test-model") or 1/0)(
    put("/api/settings", {"api_endpoint": "https://opencode.ai/zen/v1", "api_key": "", "model": "test-model", "system_prompt": ""})))
# Restore
put("/api/settings", {"api_endpoint": "https://opencode.ai/zen/v1", "api_key": "", "model": "deepseek-v4-flash-free", "system_prompt": ""})

# 5. Create project
pid = None
def _create_project():
    global pid
    r = post("/api/projects", {"title": "集成测试", "author": "Tester"})
    assert r.status_code == 200
    pid = r.json()["id"]
t("Create project", _create_project)

# 6. Create chapter
cid = None
def _create_chapter():
    global cid
    data = {"title": "第一章", "content": "# 开始\n\n这是一个测试故事。"}
    r = post(f"/api/projects/{pid}/chapters", data)
    assert r.status_code == 200
    cid = r.json()["id"]
t("Create chapter", _create_chapter)

# 7. Get chapter
def _get_chapter():
    r = get(f"/api/projects/{pid}/chapters/{cid}")
    assert r.status_code == 200
    assert "测试故事" in r.json()["content"]
t("Get chapter", _get_chapter)

# 8. Update chapter
def _update_chapter():
    r = put(f"/api/projects/{pid}/chapters/{cid}",
        json={"content": "# 更新\n\n已修改的内容。"})
    assert r.status_code == 200
    assert "已修改" in r.json()["content"]
t("Update chapter", _update_chapter)

# 9. Export EPUB
def _export():
    r = get(f"/api/projects/{pid}/export")
    assert r.status_code == 200, f"Export failed: {r.status_code} {r.text[:300]}"
    assert len(r.content) > 500, f"Content too short: {len(r.content)}"
    assert r.headers["content-type"] == "application/epub+zip"
t("Export EPUB", _export)

# 10. AI non-stream
def _ai():
    r = post("/api/write/non-stream",
        {"messages": [{"role": "user", "content": "hi"}], "model": "deepseek-v4-flash-free"})
    assert r.status_code == 200
    d = r.json()
    assert d.get("content") or d.get("reasoning_content")
t("AI non-stream", _ai)

# 11. List models
def _models():
    r = get("/api/models")
    assert r.status_code == 200
    assert len(r.json()["models"]) > 0
t("List models", _models)

# 12. Delete project
def _delete():
    r = delete(f"/api/projects/{pid}")
    assert r.status_code == 200
t("Delete project", _delete)

print(f"\n{'='*50}")
print(f"  通过: {ok}/{ok+fail}")
print(f"  失败: {fail}")
print(f"{'='*50}")

proc.terminate()
proc.wait()
sys.exit(0 if fail == 0 else 1)
