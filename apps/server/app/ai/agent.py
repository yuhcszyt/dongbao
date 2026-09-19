"""育儿 Agent：OpenAI-compatible tool calling + 结构化 ParentingAnswer。

DeepSeek 等兼容接口用 httpx 直连（与 record providers 一致），避免强绑特定 Agent SDK。
"""
from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID

import httpx

from ..config import get_config
from .schemas import ParentingAnswer, SourceRef
from .tools import BabyScope

SYSTEM_PROMPT = """你是「懂宝」育儿助手，只服务当前这个宝宝。
规则：
1. 先用工具了解宝宝档案与近期记录；涉及喂养、辅食、睡眠、维生素、就医等专业问题时，必须调用 search_parenting_knowledge。
2. 专业来源只能引用 search_parenting_knowledge 返回的条目，禁止编造书名或链接。
3. 不诊断疾病；危险信号优先建议就医；数据不足要说明。
4. 最终必须输出一个 JSON 对象，字段为：
summary, reasons, baby_context, actions, watch_for, sources, related_record_ids, medical_disclaimer
sources 每项含 title, source_url, publisher, published_at（可 null）, chunk_id（可 null）。
related_record_ids 为用到的记录 id 字符串列表。
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_baby_profile",
            "description": "获取当前宝宝昵称、生日、性别、月龄",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_records",
            "description": "获取当前宝宝近几天的记录列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 7},
                    "limit": {"type": "integer", "default": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_feeding",
            "description": "汇总某日已录入的喂养次数与奶量（毫升）",
            "parameters": {
                "type": "object",
                "properties": {"day": {"type": "string", "description": "YYYY-MM-DD，默认今天"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_parenting_knowledge",
            "description": "在已审核育儿知识库（向量检索）中搜索专业要点与来源",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


class ModelUnavailable(Exception):
    pass


def _api_key() -> str:
    cfg = get_config().large_model
    return os.environ.get(cfg.api_key_env, "").strip() if cfg.api_key_env else ""


def model_configured() -> bool:
    cfg = get_config().large_model
    return bool(cfg.enabled and cfg.base_url and cfg.model and _api_key())


def _dispatch(scope: BabyScope, name: str, arguments: dict[str, Any]) -> Any:
    if name == "get_baby_profile":
        return scope.get_baby_profile()
    if name == "get_recent_records":
        return scope.get_recent_records(days=int(arguments.get("days", 7)), limit=int(arguments.get("limit", 20)))
    if name == "get_daily_feeding":
        return scope.get_daily_feeding(day=arguments.get("day"))
    if name == "search_parenting_knowledge":
        return scope.search_parenting_knowledge(query=str(arguments["query"]), top_k=int(arguments.get("top_k", 5)))
    raise ValueError(f"unknown_tool:{name}")


def _fallback_without_model(scope: BabyScope, message: str) -> ParentingAnswer:
    """无大模型时：仍跑工具，给出可引用的降级卡片。"""
    profile = scope.get_baby_profile()
    knowledge = scope.search_parenting_knowledge(message)
    sources = list(scope._last_sources)
    baby_bits = [f"昵称 {profile.get('nickname')}"]
    if profile.get("age_months") is not None:
        baby_bits.append(f"约 {profile['age_months']} 月龄")
    if knowledge:
        summary = "已检索到相关专业要点；当前未配置大模型，以下为知识摘要，请结合宝宝情况自行判断。"
        reasons = [k["content"][:120] for k in knowledge[:3]]
    else:
        summary = "智能问答大模型未配置。已载入宝宝档案；知识库暂无足够相关条目。"
        reasons = ["请配置 MODEL_API_KEY 后获得完整结构化回答。"]
    return ParentingAnswer(
        summary=summary,
        reasons=reasons,
        baby_context=baby_bits,
        actions=["可继续在记录页补充今日喂养/睡眠", "有危险信号请就医"],
        watch_for=["精神差、呼吸异常、持续高热等"],
        sources=sources,
        related_record_ids=list(scope._last_record_ids),
    )


def _parse_answer(content: str, scope: BabyScope) -> ParentingAnswer:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
        answer = ParentingAnswer.model_validate(data)
    except Exception:
        answer = ParentingAnswer(summary=text[:500] or "暂时无法解析模型回答")
    if not answer.sources and scope._last_sources:
        answer.sources = list(scope._last_sources)
    if not answer.related_record_ids and scope._last_record_ids:
        answer.related_record_ids = list(scope._last_record_ids)
    # 只保留本轮 tool 返回过的来源，防止模型虚构
    allowed = {str(s.chunk_id) for s in scope._last_sources if s.chunk_id}
    if allowed:
        answer.sources = [s for s in answer.sources if s.chunk_id and str(s.chunk_id) in allowed]
    return answer


def run_parenting_agent(scope: BabyScope, message: str, history: list[dict[str, str]] | None = None) -> tuple[ParentingAnswer, str | None]:
    """返回 (answer, model_name)。"""
    if not model_configured():
        return _fallback_without_model(scope, message), None

    cfg = get_config().large_model
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history or []:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": message})

    url = f"{cfg.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    model_name = cfg.model

    with httpx.Client(timeout=cfg.timeout_seconds) as client:
        for _ in range(6):
            payload = {
                "model": model_name,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0.2,
            }
            response = client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise ModelUnavailable(response.text[:200])
            body = response.json()
            choice = body["choices"][0]["message"]
            tool_calls = choice.get("tool_calls") or []
            if tool_calls:
                messages.append(choice)
                for call in tool_calls:
                    fn = call["function"]["name"]
                    raw_args = call["function"].get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        result = _dispatch(scope, fn, args)
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": str(exc)}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                    )
                continue

            content = choice.get("content") or ""
            # 要求 JSON：若还不是，再追一发
            if not content.strip().startswith("{"):
                messages.append(choice)
                messages.append(
                    {
                        "role": "user",
                        "content": "请只输出 ParentingAnswer 的 JSON，不要其他文字。",
                    }
                )
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                }
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"].get("content") or content
            return _parse_answer(content, scope), model_name

    return _fallback_without_model(scope, message), model_name
