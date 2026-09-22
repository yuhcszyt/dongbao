"""育儿问答对外入口。

调用方只需：
    answer, model = run_parenting_agent(scope, message, ...)

内部：未配模型 → fallback；已配 → PydanticAI（parenting_agent）。
"""
from __future__ import annotations

from typing import Any

from .fallback import fallback_without_model
from .parenting_agent import ask, model_configured
from .schemas import ParentingAnswer
from .tools import BabyScope

__all__ = ["ModelUnavailable", "model_configured", "run_parenting_agent"]


class ModelUnavailable(Exception):
    """模型调用失败（网络 / 4xx / 5xx）。路由可转成可读错误。"""


def run_parenting_agent(
    scope: BabyScope,
    message: str,
    history: list[dict[str, str]] | None = None,
    image_data_url: str | None = None,
    trace: dict[str, Any] | None = None,
) -> tuple[ParentingAnswer, str | None]:
    """返回 (answer, model_name)。图片只进入本轮用户消息，不写入正式记录。"""
    bag = trace or {}
    if not model_configured():
        answer = fallback_without_model(scope, message, has_image=bool(image_data_url))
        bag["output"] = {"summary": answer.summary, "sources": len(answer.sources)}
        return answer, None
    try:
        return ask(
            scope,
            message,
            history=history,
            image_data_url=image_data_url,
            trace=bag,
        )
    except Exception as exc:  # noqa: BLE001 — 统一成 ModelUnavailable，便于路由处理
        bag["error"] = str(exc)[:200]
        raise ModelUnavailable(str(exc)[:200]) from exc
