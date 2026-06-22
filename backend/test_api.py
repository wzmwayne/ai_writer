#!/usr/bin/env python3
import subprocess, time, sys, os, json, httpx
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Start server
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(3)

BASE = "http://localhost:8000"
passed = 0
failed = 0

def test(name, method, path, expected_status=200, json_body=None, parse=None):
    global passed, failed
    try:
        headers = {"Content-Type": "application/json"}
        r = httpx.request(method, f"{BASE}{path}", json=json_body, headers=headers, timeout=10)
        status = "OK" if r.status_code == expected_status else f"FAIL({r.status_code})"
        print(f"  [{status}] {name}")
        if r.status_code != expected_status:
            print(f"    Body: {r.text[:200]}")
            failed += 1
            return None
        passed += 1
        if parse:
            return parse(r.json())
        if r.text:
            return r.json()
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        failed += 1
        return None

print("=" * 50)
print("  API 测试")
print("=" * 50)

# 1. Health
test("健康检查", "GET", "/api/health")

# 2. Create project
pid = test("创建项目", "POST", "/api/projects",
    json_body={"title": "测试小说", "author": "作者"},
    parse=lambda d: d["id"])

if pid:
    # 3. List projects
    test("项目列表", "GET", "/api/projects")

    # 4. Create chapter
    test("创建章节", "POST", f"/api/projects/{pid}/chapters",
        json_body={"title": "第一章", "content": "# 第一章\n\n这是一个测试。"})

    # 5. List chapters
    test("章节列表", "GET", f"/api/projects/{pid}/chapters")

    # 6. Update chapter
    test("更新章节", "PUT", f"/api/projects/{pid}/chapters/0001",
        json_body={"content": "# 第一章\n\n已更新内容。"})

    # 7. AI non-stream
    test("AI 写作(非流式)", "POST", "/api/write/non-stream",
        json_body={"messages": [{"role": "user", "content": "say hi"}],
                   "model": "deepseek-v4-flash-free", "thinking": True})

    # 8. AI streaming (just check first response line)
    test("AI 写作(流式)", "POST", "/api/write",
        json_body={"messages": [{"role": "user", "content": "say hi"}],
                   "model": "deepseek-v4-flash-free", "thinking": True})

    # 9. Export EPUB
    r = httpx.get(f"{BASE}/api/projects/{pid}/export", timeout=10)
    if r.status_code == 200 and len(r.content) > 100:
        epub_path = "/tmp/test_novel.epub"
        with open(epub_path, "wb") as f:
            f.write(r.content)
        epub_size = len(r.content)
        print(f"  [OK] EPUB 导出 ({epub_size} bytes)")
        passed += 1
    else:
        print(f"  [FAIL] EPUB 导出 (status={r.status_code}, size={len(r.content)})")
        failed += 1

    # 10. Models list
    test("模型列表", "GET", "/api/models")

    # 11. Settings
    test("设置加载", "GET", "/api/settings")
    test("设置保存", "PUT", "/api/settings",
        json_body={"api_endpoint": "https://opencode.ai/zen/v1", "api_key": "", "model": "deepseek-v4-flash-free", "system_prompt": ""})

# 12. Settings (no project needed)
test("设置加载(无项目)", "GET", "/api/settings")
test("设置保存(无项目)", "PUT", "/api/settings",
    json_body={"api_endpoint": "https://opencode.ai/zen/v1", "api_key": "", "model": "deepseek-v4-flash-free", "system_prompt": ""})

# 13. Delete project
if pid:
    test("删除项目", "DELETE", f"/api/projects/{pid}")

# Summary
print(f"\n{'='*50}")
print(f"  通过: {passed} / {passed + failed}")
print(f"  失败: {failed}")
print(f"{'='*50}")

proc.terminate()
proc.wait()
sys.exit(0 if failed == 0 else 1)
