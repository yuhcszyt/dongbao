"""Qdrant 客户端：collection 管理与检索。"""
from __future__ import annotations

import logging
import os
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .embedding import COLLECTION, vector_dim

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def qdrant_url() -> str:
    return os.environ.get("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")


def get_qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=qdrant_url(), timeout=10)
    return _client


def reset_qdrant_client() -> None:
    global _client
    _client = None


def ensure_collection(client: QdrantClient | None = None) -> None:
    """保证 collection 存在且维度与当前 embedding 配置一致；不一致则重建。"""
    q = client or get_qdrant()
    dim = vector_dim()
    names = {c.name for c in q.get_collections().collections}
    if COLLECTION in names:
        info = q.get_collection(COLLECTION)
        params = info.config.params.vectors
        size = params.size if hasattr(params, "size") else None
        if size is not None and size != dim:
            logger.warning("Qdrant collection 维度 %s ≠ 配置 %s，重建 %s", size, dim, COLLECTION)
            q.delete_collection(COLLECTION)
        else:
            return
    q.create_collection(
        collection_name=COLLECTION,
        vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
    )


def upsert_chunk(
    chunk_id: UUID,
    vector: list[float],
    *,
    document_id: UUID,
    chunk_index: int,
    content: str,
    title: str,
    source_url: str | None,
    publisher: str,
    published_at: str | None,
    review_status: str,
    client: QdrantClient | None = None,
) -> None:
    q = client or get_qdrant()
    ensure_collection(q)
    q.upsert(
        collection_name=COLLECTION,
        points=[
            qm.PointStruct(
                id=str(chunk_id),
                vector=vector,
                payload={
                    "document_id": str(document_id),
                    "chunk_index": chunk_index,
                    "content": content,
                    "title": title,
                    "source_url": source_url,
                    "publisher": publisher,
                    "published_at": published_at,
                    "review_status": review_status,
                },
            )
        ],
    )


def search_approved(
    vector: list[float],
    *,
    top_k: int = 5,
    score_threshold: float | None = 0.25,
    client: QdrantClient | None = None,
) -> list:
    q = client or get_qdrant()
    ensure_collection(q)
    result = q.query_points(
        collection_name=COLLECTION,
        query=vector,
        query_filter=qm.Filter(
            must=[qm.FieldCondition(key="review_status", match=qm.MatchValue(value="approved"))]
        ),
        limit=top_k,
        score_threshold=score_threshold,
    )
    return list(result.points)


def wipe_collection(client: QdrantClient | None = None) -> None:
    """测试用：删掉 collection 以便重新 seed。"""
    q = client or get_qdrant()
    names = {c.name for c in q.get_collections().collections}
    if COLLECTION in names:
        q.delete_collection(COLLECTION)
