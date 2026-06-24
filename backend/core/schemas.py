from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Settings ──
AI_SYSTEM_PROMPT_DEFAULT = """你是小说创作大师。

你博览群书，精通各种流派。你的目标是创作出情节抓人、富有文学性的杰出故事。

---

【多轮交互规则——请严格遵守】

本系统支持多轮工具调用。你需要在多轮回复中逐步完成创作。关键是：

第 1 轮 thinking：制定完整计划。
  列出所有步骤：需要读哪些章节、设什么标题、存什么记忆、正文写什么。
  一次规划清楚，之后不再重复。

后续每轮 thinking：只写两行。
  · 上一步结果摘要（一句话）
  · 下一步要做什么（一句话）
  禁止：重新分析项目背景、重复读已读章节、重复规划。

---

【正文输出铁律——违反则内容丢失】

1. 正文必须用 <starttext{数字}!>正文<!endtext!> 包裹（例如 <starttext1!>...<!endtext!>）。
2. 输出标签后必须调用 rewrite_chapter(chapter_id, content_id) 保存。
   不调用则正文不会被写入章节文件。
3. content 中禁止加任何说明文字（如"现在让我写出..."或"以下是正文："）。
4. 所有确认文字（如"✅ Chapter X complete."）放在 thinking 中。

---

【写作要求】

- 叙事视角、时间地点、风格基调等：根据上下文自行决定，无需追问。
- 角色要立体，情节要有起承转合和至少1个转折。
- 章节字数参考项目设置，无需在 content 中说明。

---

【可用工具】

1. memory_store(key, content, tags?) — 保存跨章节信息
2. memory_read(query) — 搜索记忆，"" 列出全部
3. set_chapter_title(title) — 设置章节标题（标题本身即可，服务器自动补"第X章"前缀）
4. memory_delete(key) — 删除记忆
5. chapter_list() — 列出所有章节
6. chapter_read(chapter_id) — 读取章节正文
7. rewrite_lines(chapter_id, start, end, new) — 局部重写行范围
8. replace_text(chapter_id, old, new) — 替换文本
9. rewrite_chapter(chapter_id, content_id) — 【写新章专用】将 <starttext{id}!>...<!endtext!> 中的正文保存到章节文件

---

【强制流程】

0. chapter_list + chapter_read 检查前两章是否符合大纲
1. set_chapter_title 设标题
2. memory_read("") 管理记忆
3. content 输出 <starttext{id}!>正文<!endtext!>
4. rewrite_chapter(chapter_id, content_id) 保存
5. thinking 中确认完成"""


class AppSettings(BaseModel):
    api_endpoint: str = "https://opencode.ai/zen/v1"
    api_key: str = ""
    model: str = "deepseek-v4-flash-free"
    system_prompt: str = AI_SYSTEM_PROMPT_DEFAULT
    auto_fill: bool = False


# ── Project ──
class ProjectCreate(BaseModel):
    title: str
    author: str = ""
    lang: str = "zh-CN"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    outline: Optional[str] = None
    setting: Optional[str] = None
    words_per_chapter: Optional[int] = None
    expected_chapters: Optional[int] = None


class ProjectResponse(BaseModel):
    id: str
    title: str
    author: str
    lang: str
    outline: str = ""
    setting: str = ""
    chapter_count: int = 0
    words_per_chapter: int = 0
    expected_chapters: int = 0
    created_at: str = ""
    updated_at: str = ""


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


# ── Chapter ──
class ChapterCreate(BaseModel):
    title: str = "未命名章节"
    content: str = ""


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class ChapterResponse(BaseModel):
    id: str
    title: str
    content: str
    order: int


class ChapterReorder(BaseModel):
    chapter_ids: list[str]


# ── AI Writing ──
class WriteRequest(BaseModel):
    messages: list[dict] = Field(..., description="OpenAI 格式消息列表")
    model: Optional[str] = None
    stream: bool = True
    thinking: bool = True
    reasoning_effort: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    project_id: Optional[str] = Field(None, description="项目ID，用于记忆系统")
    chapter_id: Optional[str] = Field(None, description="章节ID，用于set_chapter_title工具更新标题")
