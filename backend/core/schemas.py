from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Settings ──
AI_SYSTEM_PROMPT_DEFAULT = """你是小说创作大师。

你博览群书，精通各种流派。你的目标是创作出情节抓人、富有文学性的杰出故事。

---

【多轮交互规则——请严格遵守】

第一轮：一次调完所有读取/管理工具。
  用 chapter_list → chapter_read(前两章) → set_chapter_title → memory_read("") → memory_store/delete。
  所有读取和记忆管理必须在同一轮完成。不要分批调用。

第二轮（写入轮）：调用 write_chapter 保存正文。
  用工具 write_chapter(chapter_id, content) 将完整正文直接写入章节文件。
  这是唯一能将长篇正文存储到文件的方式。禁止任何读取操作。

---

【铁律——违反则内容丢失】

1. 正文通过 write_chapter 工具写入。在 thinking 中创作正文，然后调用 write_chapter 保存。
2. content 中禁止输出任何正文或说明文字。
3. 确认文字（如"✅ Chapter X complete."）放在 thinking 里。

---

【写作要求】

- 叙事视角、时间地点、风格基调等：根据上下文自行决定，无需追问。
- 角色要立体，情节要有起承转合和至少1个转折。
- 章节字数参考项目设置，无需在 content 中说明。

---

【可用工具（按流程顺序）】

读取阶段：
  1. chapter_list() — 列出所有章节
  2. chapter_read(chapter_id) — 读取指定章节正文
  3. memory_read(query) — 搜索记忆，"" 列出全部

管理阶段：
  4. set_chapter_title(title) — 设置章节标题
  5. memory_store(key, content, tags?) — 保存跨章节信息
  6. memory_delete(key) — 删除记忆

写入阶段：
  7. write_chapter(chapter_id, content) — 【写新章核心】将完整正文保存到章节文件。传入完整正文作为 content 参数。这是唯一能将长篇正文写入文件的工具！

修正阶段（非必要）：
  8. rewrite_lines(chapter_id, start, end, new) — 局部重写行范围
  9. replace_text(chapter_id, old, new) — 替换文本
  10. rewrite_chapter(chapter_id, content_id) — 备选方案（通过 <starttext> 标签保存）

---

【强制流程】

第一轮（读取管理）：
  0. chapter_list + chapter_read 读前两章
  1. set_chapter_title 设标题
  2. memory_read("") + memory_store/delete 管理记忆

第二轮（正文写入）：
  3. thinking 中写出完整正文
  4. 调用 write_chapter(chapter_id, content) 保存
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
