"""把 data/rag/parenting_seed.json 写入 Postgres 并 upsert 到 Qdrant。"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .embedding import EmbeddingUnavailable, embed_texts
from .models import RagChunk, RagDocument, now
from .qdrant_store import ensure_collection, upsert_chunk, wipe_collection

SEED_PATH = Path(__file__).resolve().parents[4] / "data" / "rag" / "parenting_seed.json"


def load_seed_file(path: Path | None = None) -> list[dict]:
    target = path or SEED_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def seed_knowledge(db: Session, *, path: Path | None = None, force: bool = False) -> int:
    """幂等写入：已存在同 id 文档则跳过（force=True 时先删后写）。返回写入的 chunk 数。

    需要可用的远程 embedding（或测试 EMBEDDING_ALLOW_HASH=1）。
    """
    ensure_collection()
    docs = load_seed_file(path)
    written = 0
    for raw in docs:
        doc_id = UUID(raw["id"])
        existing = db.get(RagDocument, doc_id)
        if existing and not force:
            continue
        if existing and force:
            db.delete(existing)
            db.flush()
        published = raw.get("published_at")
        published_at = date.fromisoformat(published) if published else None
        document = RagDocument(
            id=doc_id,
            title=raw["title"],
            source_url=raw.get("source_url"),
            publisher=raw["publisher"],
            published_at=published_at,
            review_status=raw.get("review_status", "approved"),
            created_at=now(),
        )
        db.add(document)
        db.flush()
        texts = list(raw["chunks"])
        vectors = embed_texts(texts)
        for index, (content, vector) in enumerate(zip(texts, vectors)):
            chunk = RagChunk(
                document_id=doc_id,
                content=content,
                chunk_index=index,
                created_at=datetime.now(timezone.utc),
            )
            db.add(chunk)
            db.flush()
            upsert_chunk(
                chunk.id,
                vector,
                document_id=doc_id,
                chunk_index=index,
                content=content,
                title=document.title,
                source_url=document.source_url,
                publisher=document.publisher,
                published_at=published_at.isoformat() if published_at else None,
                review_status=document.review_status,
            )
            written += 1
    db.commit()
    return written


def ensure_seeded(db: Session) -> None:
    """若库中尚无 approved 文档则自动 seed。无 embedding 时跳过（聊天仍可用宝宝 tools）。"""
    has_any = db.scalar(select(RagDocument.id).limit(1))
    if has_any is not None:
        return
    try:
        seed_knowledge(db)
    except EmbeddingUnavailable:
        return


def reseed_all(db: Session) -> int:
    """用当前 embedding 配置重建索引，保留运营导入的文档与审核状态。"""
    from .knowledge import reindex_knowledge

    return reindex_knowledge(db, reset=True)
