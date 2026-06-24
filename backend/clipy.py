from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
NOVELS_DIR = BASE_DIR / "novels"
CHATS_DIR = BASE_DIR / "chats"
MEMORIES_DIR = BASE_DIR / "data" / "memories"


def e(s):
    return s if s else "(空)"


def list_projects():
    projects = []
    for d in sorted(NOVELS_DIR.iterdir()):
        pf = d / "project.json"
        if pf.exists():
            p = json.loads(pf.read_text())
            projects.append(p)
    if not projects:
        print("无项目")
        return
    print(f"共 {len(projects)} 个项目：\n")
    for p in projects:
        ch = p.get("chapters", [])
        print(f"  [{p['id']}] {p['title']}")
        print(f"        作者: {p.get('author', '')}  章节: {len(ch)}/{p.get('expected_chapters', '?')}")
        print(f"        大纲: {str(p.get('outline', ''))[:60]}...")
        print()


def show_project(pid):
    pf = NOVELS_DIR / pid / "project.json"
    if not pf.exists():
        print(f"项目 {pid} 不存在")
        return
    p = json.loads(pf.read_text())
    print(f"ID: {p['id']}")
    print(f"标题: {p['title']}")
    print(f"作者: {p.get('author', '')}")
    print(f"章节: {len(p.get('chapters', []))}/{p.get('expected_chapters', '?')}")
    print(f"每章字数: {p.get('words_per_chapter', 0)}")
    print(f"创建时间: {p.get('created_at', '')}")
    print(f"更新时间: {p.get('updated_at', '')}")
    print(f"\n大纲 ({len(p.get('outline', ''))} 字符):")
    print(f"  {p.get('outline', '(无)')[:200]}...")
    print(f"\n设定 ({len(p.get('setting', ''))} 字符):")
    print(f"  {p.get('setting', '(无)')[:200]}...")


def list_chapters(pid):
    pf = NOVELS_DIR / pid / "project.json"
    if not pf.exists():
        print(f"项目 {pid} 不存在")
        return
    p = json.loads(pf.read_text())
    print(f"[{p['title']}] 章节列表：\n")
    for ch in p.get("chapters", []):
        chf = NOVELS_DIR / pid / "chapters" / f"{ch['id']}.md"
        size = len(chf.read_text()) if chf.exists() else 0
        chatf = CHATS_DIR / f"proj_{pid}_ch_{ch['id']}.json"
        has_chat = "💬" if chatf.exists() else " "
        print(f"  {has_chat} {ch['id']}: {ch['title']} ({size} 字符)")


def show_chapter(pid, chid):
    chf = NOVELS_DIR / pid / "chapters" / f"{chid}.md"
    if not chf.exists():
        print(f"章节 {chid} 不存在")
        return
    content = chf.read_text()
    print(f"=== {pid} / {chid} === ({len(content)} 字符)\n")
    print(content if content.strip() else "(空)")


def show_chat(pid, chid=None, raw=False):
    if chid:
        chatf = CHATS_DIR / f"proj_{pid}_ch_{chid}.json"
        if not chatf.exists():
            print(f"对话不存在: proj_{pid}_ch_{chid}.json")
            return
        msgs = json.loads(chatf.read_text())
        _print_chat_messages(msgs, raw)
    else:
        # Show all chats for project
        for f in sorted(CHATS_DIR.glob(f"proj_{pid}_ch_*.json")):
            chid = f.stem.split("_ch_")[1]
            print(f"\n{'='*60}")
            print(f"  第 {chid} 章对话")
            print(f"{'='*60}")
            msgs = json.loads(f.read_text())
            _print_chat_messages(msgs, raw)


def _print_chat_messages(msgs, raw=False):
    tools_run = {}
    for i, m in enumerate(msgs):
        role = m.get("role", "?")
        content = m.get("content", "")
        name = m.get("name", "")
        status = m.get("status", "")
        args = m.get("arguments", "")
        result = m.get("result", "")
        tc = m.get("tool_call_id", "")

        if raw:
            print(f"\n--- [{i}] {role} ---")
            if name:
                print(f"  tool: {name}")
            if content:
                print(f"  content: {content[:500]}")
            if args:
                print(f"  args: {args[:200]}")
            if result:
                print(f"  result: {result[:200]}")
            continue

        # Clean display
        if role == "user":
            txt = content[:300]
            print(f"\n👤 用户说:")
            print(f"   {txt}...")
        elif role == "thinking":
            txt = content[:200]
            print(f"\n🤔 AI思考 ({len(content)} 字符):")
            print(f"   {txt}...")
        elif role == "tool_call":
            tags = ""
            if status == "done":
                r = result[:120]
                tags = f" → {r}"
            print(f"   🛠️ {name}({args[:80]}){tags}")
            if name == "memory_store" and status == "done":
                print(f"      📝 记忆已保存")
            if name == "set_chapter_title" and status == "done":
                print(f"      📖 标题已更新")
        elif role == "ai":
            # Strip thinking from AI content
            txt = content.strip()
            print(f"\n🤖 AI 输出正文 ({len(txt)} 字符):")
            # Check for tags
            tags = re.findall(r"<starttext(\d+)!>(.*?)<!endtext!>", txt, re.DOTALL)
            if tags:
                for cid, body in tags:
                    print(f"\n   📦 标签 #{cid} ({len(body)} 字符):")
                    print(f"   {body[:300]}...")
            else:
                print(f"   ⚠️ 无标签包裹！原始内容：")
                print(f"   {txt[:500]}...")


def show_memories(pid):
    mf = MEMORIES_DIR / f"{pid}.json"
    if not mf.exists():
        print(f"无记忆（{pid}）")
        return
    mems = json.loads(mf.read_text())
    if not mems:
        print("记忆为空")
        return
    for m in mems:
        tags = f"[{','.join(m.get('tags', []))}]" if m.get("tags") else ""
        print(f"  {m['key']} {tags}")
        print(f"    {m['content'][:200]}...")
        print()


def help():
    print("""
用法:
  clipy projects [--json]                列出所有项目
  clipy project <id> [--json]            查看项目详情
  clipy chapters <project_id> [--json]   列出章节
  clipy chapter <project_id> <ch_id> [--json]  查看章节内容
  clipy chat <project_id> [ch_id] [--json]     查看对话历史 (--json 输出原始JSON)
  clipy memories <project_id> [--json]   查看记忆
  clipy ai-last <project_id> <ch_id>     只看AI最后一次输出原文
  clipy chat-raw <project_id> [ch_id]    原始格式查看对话(旧)
""")


def show_ai_last(pid, chid):
    chatf = CHATS_DIR / f"proj_{pid}_ch_{chid}.json"
    if not chatf.exists():
        print("对话不存在")
        return
    msgs = json.loads(chatf.read_text())
    for m in reversed(msgs):
        if m.get("role") == "ai":
            print(m.get("content", ""))
            return
    print("没有找到AI输出")


def _read_json(path):
    """Read a JSON file and return parsed data."""
    if not path.exists():
        return None
    return json.loads(path.read_text())


if __name__ == "__main__":
    args = sys.argv[1:]
    use_json = "--json" in args
    args = [a for a in args if a != "--json"]

    if not args or args[0] in ("-h", "--help", "help"):
        help()

    elif args[0] == "projects":
        if use_json:
            out = []
            for d in sorted(NOVELS_DIR.iterdir()):
                pf = d / "project.json"
                if pf.exists():
                    out.append(json.loads(pf.read_text()))
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            list_projects()

    elif args[0] == "project" and len(args) >= 2:
        if use_json:
            pf = NOVELS_DIR / args[1] / "project.json"
            data = _read_json(pf)
            print(json.dumps(data, ensure_ascii=False, indent=2) if data else "null")
        else:
            show_project(args[1])

    elif args[0] == "chapters" and len(args) >= 2:
        if use_json:
            pf = NOVELS_DIR / args[1] / "project.json"
            data = _read_json(pf)
            if data:
                print(json.dumps(data.get("chapters", []), ensure_ascii=False, indent=2))
            else:
                print("null")
        else:
            list_chapters(args[1])

    elif args[0] == "chapter" and len(args) >= 3:
        if use_json:
            chf = NOVELS_DIR / args[1] / "chapters" / f"{args[2]}.md"
            print(json.dumps(chf.read_text() if chf.exists() else None, ensure_ascii=False))
        else:
            show_chapter(args[1], args[2])

    elif args[0] == "chat" and len(args) >= 2:
        chid = args[2] if len(args) >= 3 else None
        if use_json:
            if chid:
                chatf = CHATS_DIR / f"proj_{args[1]}_ch_{chid}.json"
                data = _read_json(chatf)
                print(json.dumps(data, ensure_ascii=False, indent=2) if data else "null")
            else:
                out = {}
                for f in sorted(CHATS_DIR.glob(f"proj_{args[1]}_ch_*.json")):
                    chid = f.stem.split("_ch_")[1]
                    out[chid] = json.loads(f.read_text())
                print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            show_chat(args[1], chid, raw=False)

    elif args[0] == "chat-raw" and len(args) >= 2:
        show_chat(args[1], args[2] if len(args) >= 3 else None, raw=True)

    elif args[0] == "memories" and len(args) >= 2:
        if use_json:
            mf = MEMORIES_DIR / f"{args[1]}.json"
            data = _read_json(mf)
            print(json.dumps(data, ensure_ascii=False, indent=2) if data else "[]")
        else:
            show_memories(args[1])

    elif args[0] == "ai-last" and len(args) >= 3:
        show_ai_last(args[1], args[2])

    else:
        help()
