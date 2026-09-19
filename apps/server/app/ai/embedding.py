"""本地 hash embedding：无外部 key 时与 seed / 检索共用同一套向量。"""
from __future__ import annotations

import hashlib
import math
import os

import httpx

from ..config import get_config

COLLECTION = "parenting_knowledge"


def vector_dim() -> int:
    return get_config().embedding.dimensions


def hash_embed(text: str, dim: int | None = None) -> list[float]:
    """字符 / bigram 哈希向量，归一化后可用于 cosine。"""
    size = dim or vector_dim()
    vec = [0.0] * size
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return vec
    for i, ch in enumerate(cleaned):
        if ch.isspace():
            continue
        h = int(hashlib.md5(ch.encode("utf-8")).hexdigest(), 16)
        vec[h % size] += 1.0
        if i + 1 < len(cleaned):
            pair = cleaned[i : i + 2]
            h2 = int(hashlib.md5(pair.encode("utf-8")).hexdigest(), 16)
            vec[h2 % size] += 1.5
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """有配置则调 OpenAI-compatible /embeddings，否则走 hash_embed。"""
    cfg = get_config().embedding
    key = os.environ.get(cfg.api_key_env, "").strip() if cfg.api_key_env else ""
    if cfg.enabled and cfg.base_url and cfg.model and key:
        return _remote_embed(texts, cfg.base_url.rstrip("/"), cfg.model, key, cfg.timeout_seconds, cfg.dimensions)
    return [hash_embed(t, cfg.dimensions) for t in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def _remote_embed(texts: list[str], base_url: str, model: str, api_key: str, timeout: int, dim: int) -> list[list[float]]:
    url = f"{base_url}/embeddings"
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "input": texts},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()["data"]
    data = sorted(data, key=lambda item: item["index"])
    vectors = [item["embedding"] for item in data]
    for vec in vectors:
        if len(vec) != dim:
            raise ValueError(f"embedding 维度 {len(vec)} 与配置 dimensions={dim} 不一致")
    return vectors
