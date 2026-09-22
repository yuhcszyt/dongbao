"""PydanticAI 育儿 Agent：模型编排与 tool 注册。

职责边界：
- BabyScope（tools.py）= 宝宝数据 / RAG / 记忆的真实实现
- 本模块 = 把工具挂到 Agent，产出 ParentingAnswer
- agent.py = 对外唯一入口（含未配置模型时的降级）
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ImageUrl, ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from ..config import get_config
from .observability import record_generation, record_span
from .prompt import INSTRUCTIONS
from .schemas import ParentingAnswer
from .tools import BabyScope


@dataclass
class ParentingDeps:
    """一次问答的运行依赖：scope 做业务，trace 做观测。"""

    scope: BabyScope
    trace: dict[str, Any] = field(default_factory=dict)


def _api_key() -> str:
    cfg = get_config().large_model
    return os.environ.get(cfg.api_key_env, "").strip() if cfg.api_key_env else ""


def model_configured() -> bool:
    cfg = get_config().large_model
    return bool(cfg.enabled and cfg.base_url and cfg.model and _api_key())


def _chat_model() -> OpenAIChatModel:
    cfg = get_config().large_model
    # DeepSeek 等兼容端点常不支持 OpenAI strict tools；关掉以免拒答
    return OpenAIChatModel(
        cfg.model,
        provider=OpenAIProvider(base_url=cfg.base_url.rstrip("/"), api_key=_api_key()),
        profile=OpenAIModelProfile(openai_supports_strict_tool_definition=False),
        settings=ModelSettings(
            temperature=0.2,
            timeout=cfg.timeout_seconds,
            extra_body={"thinking": {"type": "disabled"}},
        ),
    )


def _build_agent() -> Agent[ParentingDeps, ParentingAnswer]:
    # model 在 ask() 里按当前配置注入，避免 import 时强依赖 API key
    agent: Agent[ParentingDeps, ParentingAnswer] = Agent(
        deps_type=ParentingDeps,
        output_type=ParentingAnswer,
        instructions=INSTRUCTIONS,
    )

    @agent.tool
    def get_baby_profile(ctx: RunContext[ParentingDeps]) -> dict:
        """获取当前宝宝昵称、生日、性别、月龄。"""
        result = ctx.deps.scope.get_baby_profile()
        record_span(ctx.deps.trace, name="tool.get_baby_profile", output={"ok": True})
        return result

    @agent.tool
    def get_recent_records(ctx: RunContext[ParentingDeps], days: int = 7, limit: int = 20) -> list[dict]:
        """获取当前宝宝近几天的记录列表。"""
        result = ctx.deps.scope.get_recent_records(days=days, limit=limit)
        record_span(ctx.deps.trace, name="tool.get_recent_records", input={"days": days, "limit": limit}, output={"count": len(result)})
        return result

    @agent.tool
    def get_daily_feeding(ctx: RunContext[ParentingDeps], day: str | None = None) -> dict:
        """汇总某日已录入的喂养次数与奶量（毫升）。day 为 YYYY-MM-DD，默认今天。"""
        result = ctx.deps.scope.get_daily_feeding(day=day)
        record_span(ctx.deps.trace, name="tool.get_daily_feeding", input={"day": day}, output={"ok": True})
        return result

    @agent.tool
    def get_recent_sleep(ctx: RunContext[ParentingDeps], days: int = 7, limit: int = 30) -> dict:
        """只查询当前宝宝近期睡眠记录（时长、起止），不含其他类型。"""
        result = ctx.deps.scope.get_recent_sleep(days=days, limit=limit)
        record_span(ctx.deps.trace, name="tool.get_recent_sleep", input={"days": days}, output={"sessions": result.get("session_count")})
        return result

    @agent.tool
    def get_growth_history(ctx: RunContext[ParentingDeps], limit: int = 20) -> dict:
        """只查询当前宝宝身高体重历史，按时间倒序。"""
        result = ctx.deps.scope.get_growth_history(limit=limit)
        record_span(ctx.deps.trace, name="tool.get_growth_history", output={"points": result.get("point_count")})
        return result

    @agent.tool
    def search_parenting_knowledge(ctx: RunContext[ParentingDeps], query: str, top_k: int = 5) -> list[dict]:
        """在已审核育儿知识库（向量检索）中搜索专业要点与来源。"""
        result = ctx.deps.scope.search_parenting_knowledge(query=query, top_k=top_k)
        hits = [x for x in result if isinstance(x, dict) and "content" in x]
        record_span(
            ctx.deps.trace,
            name="tool.search_parenting_knowledge",
            input={"query": query},
            output={"hit_count": len(hits), "titles": [x.get("title") for x in hits if x.get("title")][:5]},
        )
        return result

    @agent.tool
    def search_baby_memory(ctx: RunContext[ParentingDeps], query: str = "", limit: int = 8) -> list[dict]:
        """检索该宝宝跨会话长期记忆（偏好、规律）；不是正式记录也不是公共知识库。"""
        result = ctx.deps.scope.search_baby_memory(query=query, limit=limit)
        record_span(ctx.deps.trace, name="tool.search_baby_memory", input={"query": query}, output={"count": len(result)})
        return result

    @agent.tool
    def save_baby_memory(ctx: RunContext[ParentingDeps], content: str, category: str | None = None) -> dict:
        """保存一条跨会话记忆。不要保存单次喂奶毫升等业务事实。"""
        result = ctx.deps.scope.save_baby_memory(content=content, category=category)
        record_span(ctx.deps.trace, name="tool.save_baby_memory", output={"ok": "error" not in result})
        return result

    return agent


# 模块级单例：tools 在装饰时绑定；模型在每次 ask 前按当前配置重建。
_agent = _build_agent()


def history_to_messages(history: list[dict[str, str]] | None) -> list[ModelMessage]:
    """把落库的短历史转成 PydanticAI message_history。"""
    out: list[ModelMessage] = []
    for item in history or []:
        role, content = item.get("role"), item.get("content") or ""
        if role == "user":
            out.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            out.append(ModelResponse(parts=[TextPart(content=content)]))
    return out


def user_prompt(message: str, image_data_url: str | None) -> str | list[str | ImageUrl]:
    if not image_data_url:
        return message
    return [message, ImageUrl(url=image_data_url)]


_LEAK_MARKERS = ("get_", "search_", "save_", "amount_ml", "feeding_ml", "feeding_count", "null", "json", "工具")


def _parent_facing(lines: list[str], limit: int) -> list[str]:
    kept: list[str] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in _LEAK_MARKERS):
            continue
        kept.append(text)
        if len(kept) >= limit:
            break
    return kept


def finalize_answer(scope: BabyScope, answer: ParentingAnswer) -> ParentingAnswer:
    """补全 tool 命中的 sources / record ids，并去掉模型可能虚构的引用和系统痕迹。"""
    answer.reasons = []
    answer.baby_context = []
    answer.actions = _parent_facing(answer.actions, 1)
    answer.watch_for = _parent_facing(answer.watch_for, 1)
    if not answer.watch_for:
        answer.medical_disclaimer = None
    elif not answer.medical_disclaimer:
        answer.medical_disclaimer = "这只是育儿参考，不能代替医生。不放心就去医院看看。"
    if not answer.sources and scope._last_sources:
        answer.sources = list(scope._last_sources)
    if not answer.related_record_ids and scope._last_record_ids:
        answer.related_record_ids = list(scope._last_record_ids)
    allowed = {str(s.chunk_id) for s in scope._last_sources if s.chunk_id}
    if allowed:
        answer.sources = [s for s in answer.sources if s.chunk_id and str(s.chunk_id) in allowed]
    return answer


def ask(
    scope: BabyScope,
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    image_data_url: str | None = None,
    trace: dict[str, Any] | None = None,
) -> tuple[ParentingAnswer, str]:
    """跑一轮 Agent；调用方须保证 model_configured()。"""
    bag = trace if trace is not None else {}
    cfg = get_config().large_model
    deps = ParentingDeps(scope=scope, trace=bag)
    # 每次用当前配置的模型，避免进程内换 key / 模型名失效
    result = _agent.run_sync(
        user_prompt(message, image_data_url),
        deps=deps,
        model=_chat_model(),
        message_history=history_to_messages(history),
    )
    answer = finalize_answer(scope, result.output)
    usage = result.usage
    usage_dict = None
    if usage is not None and usage.has_values():
        usage_dict = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
    record_generation(
        bag,
        name="parenting_answer",
        model=cfg.model,
        input_preview=message,
        output={"summary": answer.summary, "source_count": len(answer.sources)},
        usage=usage_dict,
    )
    bag["output"] = {"summary": answer.summary, "sources": len(answer.sources)}
    return answer, cfg.model
