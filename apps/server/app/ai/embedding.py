"""远程 embedding（OpenAI-compatible）。生产禁止静默用本地 hash。"""
from __future__ import annotations

import hashlib
import math
import os

import httpx

from ..config import get_config

COLLECTION = "parenting_knowledge"


class EmbeddingUnavailable(Exception):
    """未配置或调用失败：RAG 不得假装检索成功。"""


def vector_dim() -> int:
    return get_config().embedding.dimensions


def embedding_configured() -> bool:
    cfg = get_config().embedding
    key = os.environ.get(cfg.api_key_env, "").strip() if cfg.api_key_env else ""
    return bool(cfg.enabled and cfg.base_url and cfg.model and key)


def allow_hash_fallback() -> bool:
    """仅 CI / 单测显式打开：EMBEDDING_ALLOW_HASH=1。"""
    return os.environ.get("EMBEDDING_ALLOW_HASH", "").strip() in ("1", "true", "yes")


def hash_embed(text: str, dim: int | None = None) -> list[float]:
    """测试用伪向量，不得用于生产检索。"""
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
    cfg = get_config().embedding
    if embedding_configured():
        key = os.environ[cfg.api_key_env].strip()
        try:
            return _remote_embed(texts, cfg.base_url.rstrip("/"), cfg.model, key, cfg.timeout_seconds, cfg.dimensions)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingUnavailable(f"向量化失败：{exc}") from exc
    if allow_hash_fallback():
        return [hash_embed(t, cfg.dimensions) for t in texts]
    raise EmbeddingUnavailable(
        "未配置向量模型：请设置 EMBEDDING_API_KEY，并在 providers.toml [embedding] 填 base_url / model"
    )


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
    payload = response.json()
    data = sorted(payload["data"], key=lambda item: item["index"])
    vectors = [item["embedding"] for item in data]
    for vec in vectors:
        if dim and len(vec) != dim:
            raise ValueError(f"embedding 维度 {len(vec)} 与配置 dimensions={dim} 不一致（请改 providers.toml）")
    return vectors
