from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.dependencies import api_error, current_user
from ..auth.models import User
from ..record.database import get_db
from ..record.models import Baby
from .agent import run_parenting_agent
from .models import AiConversation, AiMessage, now
from .schemas import ChatRequest, ChatResponse
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


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_seeded(db)
    _baby_or_404(db, body.baby_id, user.family_id)
    message = body.message.strip()
    if not message:
        raise api_error(422, "validation_error", "请输入问题")

    conv = _get_or_create_conversation(db, user.family_id, body.baby_id, body.conversation_id)
    prior = db.scalars(
        select(AiMessage).where(AiMessage.conversation_id == conv.id).order_by(AiMessage.created_at.desc()).limit(12)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(prior) if m.role in ("user", "assistant")]

    user_msg = AiMessage(conversation_id=conv.id, role="user", content=message, created_at=now())
    db.add(user_msg)
    db.flush()

    scope = BabyScope(db, user.family_id, body.baby_id)
    answer, model_name = run_parenting_agent(scope, message, history=history)

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
