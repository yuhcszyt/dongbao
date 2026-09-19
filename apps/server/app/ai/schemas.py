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
    summary: str
    reasons: list[str] = Field(default_factory=list)
    baby_context: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    watch_for: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    related_record_ids: list[UUID] = Field(default_factory=list)
    medical_disclaimer: str | None = "本回答仅供育儿参考，不能替代执业医师诊断或处方。如有危险信号请及时就医。"


class ChatRequest(BaseModel):
    baby_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: ParentingAnswer


class ChunkWithSource(BaseModel):
    chunk_id: UUID
    content: str
    title: str
    source_url: str | None = None
    publisher: str
    published_at: date | None = None
    score: float | None = None
