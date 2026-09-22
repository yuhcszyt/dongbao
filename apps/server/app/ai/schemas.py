from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    title: str
    source_url: str | None = None
    publisher: str
    published_at: date | None = None
    chunk_id: UUID | None = None


class ParentingAnswer(BaseModel):
    summary: str = Field(description="给家长的一两句口语，温暖具体。禁止工具名、字段名、null、JSON。")
    reasons: list[str] = Field(default_factory=list, description="留空。")
    baby_context: list[str] = Field(default_factory=list, description="留空。不要罗列档案或记录。")
    actions: list[str] = Field(default_factory=list, description="留空。最多一条家长现在能做的小事。")
    watch_for: list[str] = Field(default_factory=list, description="留空。仅有明确危险信号时写一条。")
    sources: list[SourceRef] = Field(default_factory=list, description="仅填写工具返回的文献；没有就空列表，不要解释缺失。")
    related_record_ids: list[UUID] = Field(default_factory=list)
    medical_disclaimer: str | None = None


class ChatRequest(BaseModel):
    baby_id: UUID
    message: str = Field(default="", max_length=2000)
    conversation_id: UUID | None = None
    media_id: UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: ParentingAnswer


class RecordTraceRequest(BaseModel):
    """记一笔确认后写入会话：摘要来自已识别并确认的记录，不再走问答大模型。"""

    baby_id: UUID
    summary: str = Field(min_length=1, max_length=500)
    record_id: UUID | None = None


class RecordTraceResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    user_content: str
    answer: ParentingAnswer


class ChunkWithSource(BaseModel):
    chunk_id: UUID
    content: str
    title: str
    source_url: str | None = None
    publisher: str
    published_at: date | None = None
    score: float | None = None
