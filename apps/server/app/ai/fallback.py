"""无大模型时的降级回答：仍尽量跑档案与知识库工具。"""
from __future__ import annotations

from .schemas import ParentingAnswer
from .tools import BabyScope


def fallback_without_model(scope: BabyScope, message: str, *, has_image: bool = False) -> ParentingAnswer:
    profile = scope.get_baby_profile()
    knowledge = scope.search_parenting_knowledge(message)
    if knowledge and isinstance(knowledge[0], dict) and knowledge[0].get("error"):
        image_note = "已收到图片，但大模型未配置，暂时看不了图。" if has_image else ""
        return ParentingAnswer(
            summary=(
                "已收到图片，但智能问答尚未配置，暂时无法看图。"
                if has_image
                else "智能问答与向量检索尚未完整配置。"
            ),
            reasons=[
                part
                for part in [
                    image_note,
                    str(knowledge[0]["error"]),
                    "聊天需要 MODEL_API_KEY；知识库检索需要 EMBEDDING_API_KEY（与 DeepSeek 聊天 key 分开）。",
                ]
                if part
            ],
            baby_context=[f"昵称 {profile.get('nickname')}"],
            actions=[
                "在 .env 配置腾讯云 TokenHub 的 EMBEDDING_API_KEY 后执行 make seed-rag",
                "配置 MODEL_API_KEY 后获得完整回答",
            ],
            watch_for=[],
            sources=[],
            related_record_ids=[],
        )

    sources = list(scope._last_sources)
    baby_bits = [f"昵称 {profile.get('nickname')}"]
    if profile.get("age_months") is not None:
        baby_bits.append(f"约 {profile['age_months']} 月龄")

    if has_image:
        summary = "已收到图片，但大模型未配置，暂时无法看图。"
        reasons = ["配置 MODEL_API_KEY 后，提问会把图片一并交给支持视觉的模型。"]
    elif knowledge:
        summary = "已用向量库检索到相关专业要点；当前未配置大模型，以下为知识摘要。"
        reasons = [k["content"][:120] for k in knowledge[:3] if "content" in k]
    else:
        summary = "大模型未配置，且知识库暂无足够相关条目。"
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
