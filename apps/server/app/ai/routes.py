from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.dependencies import api_error, current_user
from ..auth.models import User
from ..config import get_config
from ..record.database import get_db
from ..record.models import Baby, MediaAsset
from ..record.storage import media_path
from .agent import run_parenting_agent
from .models import AiConversation, AiMessage, now
from .observability import chat_trace
from .schemas import ChatRequest, ChatResponse, RecordTraceRequest, RecordTraceResponse, ParentingAnswer
from .seed import ensure_seeded
from .tools import BabyScope

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def _baby_or_404(db: Session, baby_id: UUID, family_id: UUID) -> Baby:
    baby = db.scalar(select(Baby).where(Baby.id == baby_id, Baby.family_id == family_id))
    if not baby:
        raise api_error(404, "not_found", "没有找到")
    return baby


def _get_or_create_conversation(db: Session, family_id: UUID, baby_id: UUID, conversation_id: UUID | None) -> AiConversation:
    if conversation_id:
        conv = db.scalar(
            select(AiConversation).where(
                AiConversation.id == conversation_id,
                AiConversation.family_id == family_id,
                AiConversation.baby_id == baby_id,
            )
        )
        if not conv:
            raise api_error(404, "not_found", "没有找到会话")
        return conv
    # 豆包式：复用该宝宝最新会话；没有则新建
    existing = db.scalar(
        select(AiConversation)
        .where(AiConversation.family_id == family_id, AiConversation.baby_id == baby_id)
        .order_by(AiConversation.updated_at.desc())
        .limit(1)
    )
    if existing:
        return existing
    conv = AiConversation(family_id=family_id, baby_id=baby_id, created_at=now(), updated_at=now())
    db.add(conv)
    db.flush()
    return conv


def _image_data_url(db: Session, family_id: UUID, baby_id: UUID, media_id: UUID) -> str:
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.baby_id == baby_id,
            MediaAsset.family_id == family_id,
            MediaAsset.media_type == "image",
        )
    )
    if not media:
        raise api_error(404, "not_found", "没有找到这张图片")
    if not get_config().large_model.supports_vision:
        raise api_error(422, "vision_disabled", "图片识别尚未启用")
    path = media_path(media.object_key)
    if not path.is_file():
        raise api_error(404, "not_found", "图片文件不可用")
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{media.mime_type};base64,{encoded}"


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_seeded(db)
    _baby_or_404(db, body.baby_id, user.family_id)
    message = body.message.strip() or ("请结合这张图片说说" if body.media_id else "")
    if not message:
        raise api_error(422, "validation_error", "请输入问题")
    image_url = _image_data_url(db, user.family_id, body.baby_id, body.media_id) if body.media_id else None
    stored = f"[图片] {message}" if image_url else message

    conv = _get_or_create_conversation(db, user.family_id, body.baby_id, body.conversation_id)
    prior = db.scalars(
        select(AiMessage).where(AiMessage.conversation_id == conv.id).order_by(AiMessage.created_at.desc()).limit(12)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(prior) if m.role in ("user", "assistant")]

    user_msg = AiMessage(conversation_id=conv.id, role="user", content=stored, created_at=now())
    db.add(user_msg)
    db.flush()

    scope = BabyScope(db, user.family_id, body.baby_id)
    with chat_trace(
        family_id=user.family_id,
        baby_id=body.baby_id,
        conversation_id=conv.id,
        message=message,
        has_image=bool(image_url),
    ) as trace:
        answer, model_name = run_parenting_agent(
            scope, message, history=history, image_data_url=image_url, trace=trace
        )

    assistant = AiMessage(
        conversation_id=conv.id,
        role="assistant",
        content=answer.summary,
        structured_payload=answer.model_dump(mode="json"),
        model=model_name,
        created_at=now(),
    )
    db.add(assistant)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant)
    return ChatResponse(conversation_id=conv.id, message_id=assistant.id, answer=answer)


@router.post("/record-trace", response_model=RecordTraceResponse)
def record_trace(body: RecordTraceRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """记一笔确认后写入当前会话。识别已在 RecordDraft 完成；此处只留痕，不再问诊。"""
    _baby_or_404(db, body.baby_id, user.family_id)
    summary = body.summary.strip()
    if not summary:
        raise api_error(422, "validation_error", "缺少记录摘要")
    user_content = f"【日常记录】{summary}"
    answer = ParentingAnswer(
        summary=f"已记下：{summary}",
        related_record_ids=[body.record_id] if body.record_id else [],
    )
    conv = _get_or_create_conversation(db, user.family_id, body.baby_id, None)
    db.add(AiMessage(conversation_id=conv.id, role="user", content=user_content, created_at=now()))
    assistant = AiMessage(
        conversation_id=conv.id,
        role="assistant",
        content=answer.summary,
        structured_payload=answer.model_dump(mode="json"),
        model="record-trace",
        created_at=now(),
    )
    db.add(assistant)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant)
    return RecordTraceResponse(
        conversation_id=conv.id,
        message_id=assistant.id,
        user_content=user_content,
        answer=answer,
    )


@router.post("/conversations/new")
def new_conversation(baby_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """清空对话框：新开一条会话（旧消息保留在库中，前端只跟新 id）。"""
    _baby_or_404(db, baby_id, user.family_id)
    conv = AiConversation(family_id=user.family_id, baby_id=baby_id, created_at=now(), updated_at=now())
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"conversation_id": conv.id}


@router.get("/conversations/active")
def active_conversation(baby_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _baby_or_404(db, baby_id, user.family_id)
    conv = db.scalar(
        select(AiConversation)
        .where(AiConversation.family_id == user.family_id, AiConversation.baby_id == baby_id)
        .order_by(AiConversation.updated_at.desc())
        .limit(1)
    )
    if not conv:
        return {"conversation_id": None, "messages": []}
    messages = db.scalars(select(AiMessage).where(AiMessage.conversation_id == conv.id).order_by(AiMessage.created_at)).all()
    return {
        "conversation_id": conv.id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "structured_payload": m.structured_payload,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }
