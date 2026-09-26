"""私有宝宝记忆向量留在 Postgres，检索前先限定家庭和宝宝。"""
from __future__ import annotations

import hashlib
import math
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import get_config
from .embedding import EmbeddingUnavailable, allow_hash_fallback, embedding_configured, embed_texts, embed_query
from .models import AiMemory


def model_key() -> str:
    cfg = get_config().embedding
    provider = f"{cfg.base_url}|{cfg.model}" if embedding_configured() else "test-hash" if allow_hash_fallback() else "unavailable"
    return hashlib.sha256(f"{provider}|{cfg.dimensions}".encode()).hexdigest()


def content_key(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def index_memory(row: AiMemory) -> bool:
    try:
        vector = embed_texts([row.content])[0]
    except EmbeddingUnavailable:
        return False
    row.embedding = vector
    row.embedding_model = model_key()
    row.embedding_content = content_key(row.content)
    return True


def cosine(left, right) -> float:
    if not left or not right or len(left) != len(right):
        return -1
    try:
        dot = sum(a * b for a, b in zip(left, right))
        norm = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
        result = dot / norm if norm else -1
        return result if math.isfinite(result) else -1
    except (TypeError, ValueError):
        return -1


def search(db: Session, family_id, baby_id, query: str, limit: int) -> list[dict]:
    limit = max(1, min(int(limit), 20))
    query = (query or "").strip()[:500]
    stmt = select(AiMemory).where(AiMemory.family_id == family_id, AiMemory.baby_id == baby_id)
    selected: list[tuple[AiMemory, str]] = []
    if query:
        try:
            vector = embed_query(query)
            # 当前宝宝最多取最近 500 条有效向量；不把其他家庭的记忆送入打分器。
            candidates = db.scalars(stmt.where(AiMemory.embedding_model == model_key()).order_by(AiMemory.updated_at.desc()).limit(500)).all()
            ranked = sorted(((cosine(vector, row.embedding), row) for row in candidates if row.embedding_content == content_key(row.content)), key=lambda pair: pair[0], reverse=True)
            mode = "semantic" if embedding_configured() else "test_vector"
            selected = [(row, mode) for score, row in ranked if score >= 0.25][:limit]
        except EmbeddingUnavailable:
            pass
        if len(selected) < limit:
            # 转义 LIKE 元字符，避免输入 % 被解释为所有记忆。
            lexical = db.scalars(stmt.where(AiMemory.content.contains(query, autoescape=True)).order_by(AiMemory.updated_at.desc()).limit(limit))
            seen = {row.id for row, _ in selected}
            selected.extend((row, "keyword") for row in lexical if row.id not in seen)
    else:
        selected = [(row, "recent") for row in db.scalars(stmt.order_by(AiMemory.updated_at.desc()).limit(limit))]
    return [{"id": str(row.id), "content": row.content, "category": row.category, "source": row.source,
             "updated_at": row.updated_at.isoformat() if row.updated_at else None, "retrieval_mode": mode}
            for row, mode in selected[:limit]]


def reindex_memories(db: Session) -> int:
    count = 0
    # 运维显式执行，支持模型变更和旧记忆补建。失败保留已提交进度，可重试。
    for row in db.scalars(select(AiMemory).order_by(AiMemory.id)).all():
        if row.embedding_model == model_key() and row.embedding_content == content_key(row.content):
            continue
        if not index_memory(row):
            raise EmbeddingUnavailable("记忆索引未完成，请检查向量服务后重试")
        db.commit()
        count += 1
    return count


if __name__ == "__main__":
    from ..record.database import SessionLocal
    with SessionLocal() as session:
        print(f"已更新 {reindex_memories(session)} 条私有记忆索引")
