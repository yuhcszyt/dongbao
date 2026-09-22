"""Langfuse 观测：有密钥才启用；不写入原图 / 音频等敏感媒体。"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID


def langfuse_enabled() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    )


def _client():
    if not langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse
    except ImportError:
        return None
    return Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"].strip(),
        secret_key=os.environ["LANGFUSE_SECRET_KEY"].strip(),
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
        or "https://cloud.langfuse.com",
    )


@contextmanager
def chat_trace(
    *,
    family_id: UUID,
    baby_id: UUID,
    conversation_id: UUID | None,
    message: str,
    has_image: bool,
) -> Iterator[dict[str, Any]]:
    """yield 可变 bag；退出时 flush。观测失败不影响业务。"""
    bag: dict[str, Any] = {"enabled": False}
    client = _client()
    if not client:
        yield bag
        return
    bag["enabled"] = True
    try:
        trace = client.trace(
            name="ai.chat",
            user_id=str(family_id),
            session_id=str(conversation_id) if conversation_id else None,
            metadata={"baby_id": str(baby_id), "has_image": has_image},
            input={"message": message[:500], "has_image": has_image},
        )
        bag["trace"] = trace
        yield bag
        if "output" in bag:
            trace.update(output=bag["output"])
        if "error" in bag:
            trace.update(level="ERROR", status_message=str(bag["error"])[:300])
    except Exception:  # noqa: BLE001
        yield bag
    finally:
        try:
            client.flush()
        except Exception:  # noqa: BLE001
            pass


def record_generation(
    bag: dict[str, Any],
    *,
    name: str,
    model: str | None,
    input_preview: str,
    output: Any = None,
    usage: dict | None = None,
) -> None:
    if not bag.get("enabled") or "trace" not in bag:
        return
    try:
        bag["trace"].generation(
            name=name,
            model=model,
            input=input_preview[:800],
            output=output,
            usage=usage,
        )
    except Exception:  # noqa: BLE001
        pass


def record_span(
    bag: dict[str, Any],
    *,
    name: str,
    input: Any = None,
    output: Any = None,
    metadata: dict | None = None,
) -> None:
    if not bag.get("enabled") or "trace" not in bag:
        return
    try:
        bag["trace"].span(name=name, input=input, output=output, metadata=metadata or {})
    except Exception:  # noqa: BLE001
        pass
