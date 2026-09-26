"""Agent 可调用的业务 tools：宝宝数据 + RAG。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..record.models import Baby, BabyRecord
from .embedding import EmbeddingUnavailable, embed_query
from .models import AiMemory, RagChunk, RagDocument, now
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

    def get_recent_sleep(self, days: int = 7, limit: int = 30) -> dict:
        """只查 sleep 记录；表仍是 baby_records，靠 record_type + 复合索引。"""
        self.baby()
        days = max(1, min(int(days), 30))
        limit = max(1, min(int(limit), 50))
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.db.scalars(
            select(BabyRecord)
            .where(
                BabyRecord.baby_id == self.baby_id,
                BabyRecord.family_id == self.family_id,
                BabyRecord.deleted_at.is_(None),
                BabyRecord.record_type == "sleep",
                BabyRecord.occurred_at >= since,
            )
            .order_by(BabyRecord.occurred_at.desc())
            .limit(limit)
        ).all()
        self._last_record_ids = [r.id for r in rows]
        sessions: list[dict] = []
        total_minutes = 0
        for r in rows:
            payload = r.payload if isinstance(r.payload, dict) else {}
            minutes = payload.get("duration_minutes")
            if not isinstance(minutes, (int, float)) and payload.get("start_at") and payload.get("end_at"):
                try:
                    start = datetime.fromisoformat(str(payload["start_at"]).replace("Z", "+00:00"))
                    end = datetime.fromisoformat(str(payload["end_at"]).replace("Z", "+00:00"))
                    minutes = max(0, int((end - start).total_seconds() // 60))
                except (TypeError, ValueError):
                    minutes = None
            if isinstance(minutes, (int, float)):
                total_minutes += int(minutes)
            sessions.append(
                {
                    "id": str(r.id),
                    "occurred_at": r.occurred_at.isoformat(),
                    "duration_minutes": int(minutes) if isinstance(minutes, (int, float)) else None,
                    "start_at": payload.get("start_at"),
                    "end_at": payload.get("end_at"),
                    "note": r.note,
                }
            )
        return {
            "days": days,
            "session_count": len(sessions),
            "total_minutes": total_minutes,
            "sessions": sessions,
        }

    def get_growth_history(self, limit: int = 20) -> dict:
        """只查 growth 记录；按时间倒序，便于看身高体重趋势。"""
        self.baby()
        limit = max(1, min(int(limit), 50))
        rows = self.db.scalars(
            select(BabyRecord)
            .where(
                BabyRecord.baby_id == self.baby_id,
                BabyRecord.family_id == self.family_id,
                BabyRecord.deleted_at.is_(None),
                BabyRecord.record_type == "growth",
            )
            .order_by(BabyRecord.occurred_at.desc())
            .limit(limit)
        ).all()
        self._last_record_ids = [r.id for r in rows]
        points: list[dict] = []
        for r in rows:
            payload = r.payload if isinstance(r.payload, dict) else {}
            points.append(
                {
                    "id": str(r.id),
                    "occurred_at": r.occurred_at.isoformat(),
                    "height_cm": payload.get("height_cm"),
                    "weight_kg": payload.get("weight_kg"),
                    "note": r.note,
                }
            )
        return {
            "point_count": len(points),
            "latest": points[0] if points else None,
            "points": points,
        }

    def search_parenting_knowledge(self, query: str, top_k: int = 5) -> list[dict]:
        try:
            vector = embed_query(query)
        except EmbeddingUnavailable as exc:
            self._last_sources = []
            return [{"error": str(exc)}]
        # 测试 hash 向量分数偏低，允许略降阈值；生产 BGE 用默认 0.25
        threshold = 0.08 if os.environ.get("EMBEDDING_ALLOW_HASH") else 0.25
        hits = search_approved(vector, top_k=top_k, score_threshold=threshold)
        chunks: list[ChunkWithSource] = []
        sources: list[SourceRef] = []
        for hit in hits:
            # 不信任可能过期或写入中断的向量 payload，以数据库审核状态与原文为准。
            stored = self.db.get(RagChunk, UUID(str(hit.id)))
            document = self.db.get(RagDocument, stored.document_id) if stored else None
            if not stored or not document or document.review_status != "approved":
                continue
            chunk = ChunkWithSource(
                chunk_id=stored.id, content=stored.content, title=document.title,
                source_url=document.source_url, publisher=document.publisher,
                published_at=document.published_at,
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

    def search_baby_memory(self, query: str = "", limit: int = 8) -> list[dict]:
        self.baby()
        from .memory_search import search
        return search(self.db, self.family_id, self.baby_id, query, limit)

    def save_baby_memory(self, content: str, category: str | None = None) -> dict:
        """写入跨会话记忆。禁止把单次喂奶量等业务事实整段复制进来。"""
        self.baby()
        text = (content or "").strip()
        if not text:
            return {"error": "empty_memory"}
        if len(text) > 500:
            text = text[:500]
        row = AiMemory(
            family_id=self.family_id,
            baby_id=self.baby_id,
            content=text,
            category=(category or None),
            source="agent",
            created_at=now(),
            updated_at=now(),
        )
        from .memory_search import index_memory
        index_memory(row)
        self.db.add(row)
        self.db.flush()
        return {"id": str(row.id), "content": row.content, "category": row.category}
