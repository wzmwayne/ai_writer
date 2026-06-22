# AI Novel Forge — AGENTS.md

## 项目定位
AI 小说写作工坊。FastAPI 后端 + 原生 JS 前端（桌面 window manager 风格）。存储基于目录镜像 + EPUB 引擎。**无认证**（auth 已移除，面板无权限校验）。

## 环境与启动

```bash
# 直接启动（start.sh 会自动安装依赖，无需手动操作）
bash start.sh

# 或手动:
cd backend && python3 main.py         # uvicorn reload=True
```

- `.env`（已 gitignored）配置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`HOST`、`PORT`
- auth 已移除，无需登录
- 当前环境为 exFAT 文件系统，不支持 symlink，故跳过 venv，直接用 `pip3 install --break-system-packages`
- `start.sh` 依赖 `lsof`/`fuser`/`ss` 查端口，无 root 时可能查不到旧进程
- `python main.py` 入口用 `sys.path.insert(0, ...)` 确保 `backend/` 在 `sys.path` 中，以 `reload=True` 模式启动 uvicorn

## 启动命令（根目录 start.sh）逻辑
1. 清华源安装依赖（`--break-system-packages`），标记 `backend/.deps_ok` 跳过重复安装
2. 创建 `backend/novels/` 数据目录
3. 查杀端口 8000 旧进程
4. `cd backend && python3 main.py`

## 测试

```bash
cd backend

# 完整集成测试（启动服务器 → 全部 API → 关闭）
python3 test_full.py

# 各模块独立测试（都会自启 uvicorn）
python3 test_api.py                   # API 端点测试
python3 test_llm.py --list-models     # LLM 客户端测试
python3 test_llm.py --model <name> [--stream] [--no-think]
```

- 测试脚本都会在内部启动 `uvicorn` 子进程，无需手动启动服务器
- `test_full.py` 会测试 AI 非流式端点（需要有效 API key，否则 FAIL），建议设好 `LLM_API_KEY`
- `test_llm.py` 硬编码了 API key（代码内嵌值），仅供开发调试

## 项目结构要点

```
backend/
├── main.py              # FastAPI 入口（mount 静态文件 + 路由注册）
├── config.py            # load_dotenv + 路径定义（BASE_DIR/NOVELS_DIR/SETTINGS_FILE）
├── core/
│   ├── llm.py           # httpx AI 客户端（流式/非流式 + thinking + tool calling）
│   ├── memory.py        # 项目记忆系统（JSON 文件存储）
│   ├── schemas.py       # Pydantic 模型 + LLM system prompt
│   └── stream_cache.py  # SSE 流缓存（5 分钟 TTL）
├── services/
│   └── epub_engine.py   # 目录镜像 EPUB 引擎（编辑=文件操作，导出=ZIP）
├── api/
│   ├── auth.py          # 已移除，仅留注释
│   ├── projects.py      # 项目 CRUD + 导入/导出
│   ├── chapters.py      # 章节 CRUD + 排序
│   ├── writing.py       # AI 写作（/write SSE 流式, /write/async, /write/non-stream）
│   ├── chat.py          # 聊天历史 CRUD（JSON 文件）
│   ├── memory.py        # 记忆 CRUD API
│   └── settings.py      # settings.json 读写 + 原子写入
└── frontend/
    ├── index.html       # 桌面骨架（JS 窗口管理器）
    ├── css/style.css
    └── js/              # 无框架纯 JS（api.js, auth.js, wm.js, apps.js, app.js）
```

**数据存储（均为文件）：**
- 项目: `backend/novels/{id}/`（`project.json` + `chapters/{id}.md`）
- 设置: `backend/settings.json`（gitignored，通过 `backend/data/` gitignore 规则排除）
- 聊天: `backend/chats/{key}.json`
- 记忆: `backend/data/memories/{project_id}.json`

## API 约定

- 所有路由挂 `/api` 前缀，无认证
- 写入端点（/settings, /chat）使用**原子写入**（tmp + rename）
- AI 流式端点 `/api/write` 返回 SSE（event: content/thinking/tool_status/tool_result/done/error）
- `/api/write/async` 返回 stream_id，通过 `/api/write/recover/{stream_id}?since=N` 轮询
- 项目记忆通过 `project_id` 参数注入，支持 tool calling（memory_store/read/set_title/delete）
- 默认 System Prompt 硬编码在 `core/schemas.py:AI_SYSTEM_PROMPT_DEFAULT`

## 重要约定

- **纯文件存储** — 无需数据库，项目/章节/设置/聊天/记忆均为 JSON 或 Markdown 文件
- **编辑操作直接修改目录文件**，导出时才打包 EPUB ZIP
- 前端**原生 JS** — 无框架、无 CDN，所有 JS 通过独立路由 `/js/{path}` 提供服务
- 添加新 API 路由需要在 `main.py` 注册 `app.include_router()`
- 修改功能时注意 `core/memory.py` 的 tool calling 流程与 `api/writing.py` 的 tool execution 回调链

## 构建/代码检查

- 无构建步骤（纯 Python + 原生 JS）
- 无 lint/typecheck 配置
- 代码风格跟随现有模式（`from __future__ import annotations` 开头的文件较多）
