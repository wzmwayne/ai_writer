# AI Novel Forge

AI 小说写作工坊 — 跨平台 AI 辅助小说写作工具。

- **后端** Python 3.12+ / FastAPI
- **前端** 原生 JS（桌面 window manager 风格，CDN 无关）
- **存储** 基于目录镜像的 EPUB 引擎（编辑时操作目录，导出时生成 ZIP）
- **AI** 纯 httpx 流式客户端，支持思考链（reasoning_content）

## 快速开始

```bash
# 1. 创建虚拟环境
cd backend
python -m venv ../venv
source ../venv/bin/activate  # Windows: ..\venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
bash start.sh
```

浏览器打开 `http://localhost:8000`。

默认账号：`admin` / `admin123`

## 配置

编辑 `.env`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | — | AI API 密钥 |
| `LLM_BASE_URL` | `https://opencode.ai/zen/v1` | API 地址（OpenAI 兼容） |
| `LLM_MODEL` | `deepseek-v4-flash-free` | 默认模型 |
| `JWT_SECRET` | 见文件 | JWT 签名密钥（生产环境务必修改） |
| `HOST` / `PORT` | `0.0.0.0:8000` | 监听地址 |

## 功能

- **项目管理** 创建、导入/导出 EPUB
- **章节编辑** Markdown 内容，自由编排
- **AI 写作** 流式生成 + 思考链展示
- **模型选择** 多模型切换
- **EPUB 导出** 标准格式，兼容主流阅读器

## 项目结构

```
backend/
├── main.py              # FastAPI 入口
├── config.py            # 配置 + 默认用户初始化
├── .env                 # 环境变量
├── start.sh             # 启动脚本
├── requirements.txt
├── api/
│   ├── auth.py          # JWT 认证
│   ├── projects.py      # 项目 CRUD + 导入导出
│   ├── chapters.py      # 章节 CRUD + 排序
│   └── writing.py       # AI 写作端点（流式/非流式）
├── core/
│   ├── llm.py           # httpx AI 客户端（思考链支持）
│   └── schemas.py       # Pydantic 数据模型
├── services/
│   └── epub_engine.py   # EPUB 读写引擎（目录镜像 + ZIP）
├── frontend/
│   ├── index.html       # 桌面骨架（登录遮罩 + sidebar + taskbar）
│   ├── css/style.css    # 深色主题
│   └── js/
│       ├── api.js       # fetch 封装（自动 token + 401 重定向）
│       ├── auth.js      # 登录表单 UI + API 调用
│       ├── wm.js        # 窗口管理器（拖拽/最小化/最大化/关闭）
│       ├── apps.js      # 应用窗口（项目列表/写作工作区/设置/日志）
│       └── app.js       # 桌面初始化
├── novels/              # 小说数据目录（自动创建）
└── test_full.py         # 集成测试
```

## 测试

```bash
source ../venv/bin/activate
python test_full.py
```

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/register` | 注册 |
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{id}/export` | 导出 EPUB |
| POST | `/api/projects/import` | 导入 EPUB |
| GET | `/api/projects/{id}/chapters` | 章节列表 |
| POST | `/api/projects/{id}/chapters` | 创建章节 |
| POST | `/api/write/stream` | AI 流式写作（SSE） |
| POST | `/api/write/non-stream` | AI 非流式写作 |
| GET | `/api/models` | 可用模型列表 |

完整文档：`http://localhost:8000/docs`（Swagger UI）

## AI 接口

兼容 OpenAI 格式，支持 `reasoning_content`（思考链）。配置 `.env` 中的 `LLM_API_KEY` 和 `LLM_BASE_URL` 即可切换任意兼容的 API 提供商。

## 许可

MIT
