from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from .database import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")

def now() -> datetime:
    return datetime.now(timezone.utc)

class Baby(Base):
    __tablename__ = "babies"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    nickname: Mapped[str] = mapped_column(String(30))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    baby_id: Mapped[UUID] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    media_type: Mapped[str] = mapped_column(String(16))
    mime_type: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(255), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class RecordDraft(Base):
    __tablename__ = "record_drafts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    baby_id: Mapped[UUID] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=True)
    record_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_fields: Mapped[list] = mapped_column(JsonType, default=list)
    source: Mapped[str] = mapped_column(String(16))
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    recognition_warnings: Mapped[list] = mapped_column(JsonType, default=list)
    capture_context: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class BabyRecord(Base):
    __tablename__ = "baby_records"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    baby_id: Mapped[UUID] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    record_type: Mapped[str] = mapped_column(String(32), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JsonType)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

class RecordMedia(Base):
    __tablename__ = "record_media"
    record_id: Mapped[UUID] = mapped_column(ForeignKey("baby_records.id", ondelete="CASCADE"), primary_key=True)
    media_id: Mapped[UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="RESTRICT"), primary_key=True)
