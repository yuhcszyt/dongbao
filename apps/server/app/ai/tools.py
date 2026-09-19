"""Agent 可调用的业务 tools：宝宝数据 + RAG。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..record.models import Baby, BabyRecord
from .embedding import embed_query
from .qdrant_store import search_approved
from .schemas import ChunkWithSource, SourceRef


class BabyScope:
    def __init__(self, db: Session, family_id: UUID, baby_id: UUID):
        self.db = db
        self.family_id = family_id
        self.baby_id = baby_id
        self._last_sources: list[SourceRef] = []
        self._last_record_ids: list[UUID] = []

    def baby(self) -> Baby:
        baby = self.db.scalar(select(Baby).where(Baby.id == self.baby_id, Baby.family_id == self.family_id))
        if not baby:
            raise ValueError("baby_not_found")
        return baby

    def get_baby_profile(self) -> dict:
        baby = self.baby()
        age = None
        if baby.birth_date:
            today = date.today()
            months = (today.year - baby.birth_date.year) * 12 + (today.month - baby.birth_date.month)
            if today.day < baby.birth_date.day:
                months -= 1
            age = max(months, 0)
        return {
            "nickname": baby.nickname,
            "birth_date": baby.birth_date.isoformat() if baby.birth_date else None,
            "gender": baby.gender,
            "age_months": age,
        }

    def get_recent_records(self, days: int = 7, limit: int = 20) -> list[dict]:
        self.baby()
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.db.scalars(
            select(BabyRecord)
            .where(
                BabyRecord.baby_id == self.baby_id,
                BabyRecord.family_id == self.family_id,
                BabyRecord.deleted_at.is_(None),
                BabyRecord.occurred_at >= since,
            )
            .order_by(BabyRecord.occurred_at.desc())
            .limit(limit)
        ).all()
        self._last_record_ids = [r.id for r in rows]
        return [
            {
                "id": str(r.id),
                "record_type": r.record_type,
                "occurred_at": r.occurred_at.isoformat(),
                "payload": r.payload,
                "note": r.note,
            }
            for r in rows
        ]

    def get_daily_feeding(self, day: str | None = None) -> dict:
        self.baby()
        tz = ZoneInfo("Asia/Shanghai")
        target = date.fromisoformat(day) if day else datetime.now(tz).date()
        start = datetime(target.year, target.month, target.day, tzinfo=tz).astimezone(timezone.utc)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        rows = self.db.scalars(
            select(BabyRecord).where(
                BabyRecord.baby_id == self.baby_id,
                BabyRecord.family_id == self.family_id,
                BabyRecord.deleted_at.is_(None),
                BabyRecord.occurred_at >= start,
                BabyRecord.occurred_at <= end,
                BabyRecord.record_type == "feeding",
            )
        ).all()
        total_ml = 0
        for r in rows:
            ml = r.payload.get("amount_ml") if isinstance(r.payload, dict) else None
            if isinstance(ml, (int, float)):
                total_ml += int(ml)
        self._last_record_ids = [r.id for r in rows]
        return {"date": target.isoformat(), "feeding_count": len(rows), "feeding_ml": total_ml, "note": "仅统计已录入记录"}

    def search_parenting_knowledge(self, query: str, top_k: int = 5) -> list[dict]:
        vector = embed_query(query)
        hits = search_approved(vector, top_k=top_k)
        chunks: list[ChunkWithSource] = []
        sources: list[SourceRef] = []
        for hit in hits:
            payload = hit.payload or {}
            chunk_id = UUID(str(hit.id))
            published = payload.get("published_at")
            published_at = date.fromisoformat(published) if published else None
            chunk = ChunkWithSource(
                chunk_id=chunk_id,
                content=str(payload.get("content") or ""),
                title=str(payload.get("title") or ""),
                source_url=payload.get("source_url"),
                publisher=str(payload.get("publisher") or ""),
                published_at=published_at,
                score=float(hit.score) if hit.score is not None else None,
            )
            chunks.append(chunk)
            sources.append(
                SourceRef(
                    title=chunk.title,
                    source_url=chunk.source_url,
                    publisher=chunk.publisher,
                    published_at=chunk.published_at,
                    chunk_id=chunk.chunk_id,
                )
            )
        self._last_sources = sources
        return [c.model_dump(mode="json") for c in chunks]
