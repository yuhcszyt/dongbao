"""快捷记录：同一媒体串行处理，业务记录与会话消息在一个事务中提交。"""
import asyncio
import json
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.dependencies import api_error, current_user
from ..auth.models import User
from ..ai.models import AiMessage
from ..ai.routes import _get_or_create_conversation
from .database import get_db
from .models import BabyRecord, MediaAsset, RecordDraft, RecordMedia, now
from .providers import ProviderUnavailable, extract_draft, transcribe_audio
from .routes import baby_for, media_out, record_out, RECORD_TYPES
from .schemas import CaptureStart, CaptureReply, CaptureResult, RecordCreate
from .storage import media_path

router = APIRouter(prefix="/api/v1", tags=["quick-capture"])


def owned_media(db, media_id, user, baby_id=None):
    query = select(MediaAsset).where(MediaAsset.id == media_id, MediaAsset.family_id == user.family_id)
    if baby_id:
        query = query.where(MediaAsset.baby_id == baby_id)
    media = db.scalar(query.with_for_update())
    if not media:
        raise api_error(404, "media_not_found", "没有找到这份录音或照片")
    return media


def capture_for(db, media_id):
    return db.scalar(select(RecordDraft).where(RecordDraft.media_id == media_id, RecordDraft.capture_context.is_not(None)))


def result_for(db, draft):
    context = draft.capture_context or {}
    record = db.get(BabyRecord, UUID(context["record_id"])) if context.get("record_id") else None
    media = db.get(MediaAsset, draft.media_id)
    return CaptureResult(
        state="saved" if draft.status == "saved" else "cancelled" if draft.status == "cancelled" else "needs_input",
        draft_id=draft.id, conversation_id=context.get("conversation_id"),
        question=context.get("question", ""), record=record_out(db, record) if record else None,
        media=media_out(media) if media else None, transcript=draft.transcript,
    )


def transcribe(media):
    if media.media_type != "audio":
        raise api_error(422, "audio_required", "请用语音补充这条记录")
    try:
        text = asyncio.run(transcribe_audio(media_path(media.object_key), media.mime_type)).strip()
        if not text:
            raise ValueError("empty transcript")
        return text
    except (ProviderUnavailable, httpx.HTTPError, ValueError, OSError):
        raise api_error(503, "transcription_failed", "这次没听清，请重试或重新说一遍")


@router.post("/media/{media_id}/transcript")
def media_transcript(media_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"transcript": transcribe(owned_media(db, media_id, user))}


QUESTIONS = {
    "record_type": "你想记宝宝的哪件事？比如喝奶、睡觉或换尿布。",
    "amount_ml": "这次喝了多少毫升奶？",
    "duration_minutes": "这次睡了多长时间？",
    "food_name": "这次吃了什么辅食？",
    "color": "便便是什么颜色？", "consistency": "便便是稀的、糊状的，还是成形的？",
    "content": "这次尿布里有尿、便便，还是都有？",
    "name": "请说一下名称。", "title": "请说一下要记的事情。",
    "height_cm": "这次量到的身高或体重是多少？",
    "occurred_at": "这件事是什么时候发生的？",
    "event": "照片里的东西，宝宝已经吃过或用过了吗？请说一下实际发生的事。",
}


def validated_record(extracted, context):
    kind = extracted.get("record_type")
    if kind not in RECORD_TYPES:
        return None, QUESTIONS["record_type"]
    payload = extracted.get("payload")
    if not isinstance(payload, dict):
        return None, "没听完整，请再说一下这件事。"
    missing = extracted.get("missing_fields") or []
    if missing:
        key = str(missing[0]).split(".")[-1]
        return None, QUESTIONS.get(key, "还缺少一些信息，请再说一下这件事的具体情况。")
    if kind == "feeding" and payload.get("feeding_type") != "breast" and payload.get("amount_ml") is None:
        return None, QUESTIONS["amount_ml"]
    if extracted.get("recognition_warnings"):
        return None, "有些内容还不确定，请再说一下具体情况和数量。"
    zone = ZoneInfo(context["timezone"])
    try:
        occurred = datetime.fromisoformat(extracted.get("occurred_at") or context["captured_at"])
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=zone)
        payload = dict(payload)
        for key in ("start_at", "end_at"):
            if payload.get(key):
                stamp = datetime.fromisoformat(payload[key])
                payload[key] = (stamp if stamp.tzinfo else stamp.replace(tzinfo=zone)).isoformat()
        record = RecordCreate(record_type=kind, occurred_at=occurred, payload=payload, note=extracted.get("note"))
        return record, ""
    except ValidationError as exc:
        field = str(exc.errors()[0]["loc"][-1])
        if kind == "sleep": field = "duration_minutes"
        if kind == "growth": field = "height_cm"
        return None, QUESTIONS.get(field, "这次内容还不完整，请再说一下具体情况和数量。")
    except (ValueError, TypeError):
        return None, QUESTIONS["occurred_at"]


def summary_for(record):
    payload = record.payload
    labels = {"feeding": "喂奶", "sleep": "睡眠", "diaper": "换尿布", "stool": "排便", "complementary_food": "辅食", "vitamin_ad": "维生素 AD", "growth": "成长", "vaccine": "疫苗", "medication": "用药", "crying": "哭闹", "custom": "日常"}
    details = []
    for field, unit in (("amount_ml", "毫升"), ("duration_minutes", "分钟"), ("height_cm", "厘米"), ("weight_kg", "公斤")):
        if payload.get(field) is not None: details.append(f"{payload[field]} {unit}")
    for field in ("food_name", "amount_text", "name", "title", "content", "color", "consistency", "dose_text", "dosage_text"):
        if payload.get(field): details.append(str(payload[field]))
    return "已记录：" + labels[record.record_type] + (" · " + "，".join(details) if details else "")


def process(db, draft, media, user, text, reply_id=None, reply_media=None):
    context = dict(draft.capture_context)
    turns = list(context.get("turns", []))
    turns.append({"request_id": str(reply_id) if reply_id else "initial", "text": text})
    prompt = json.dumps({"参考时间": context["captured_at"], "时区": context["timezone"], "原始转写": draft.transcript,
                         "上一轮识别": draft.payload, "上一轮追问": context.get("question"), "用户补充": turns}, ensure_ascii=False)
    try:
        extracted = asyncio.run(extract_draft(content=prompt, image_path=media_path(media.object_key) if media.media_type == "image" else None, mime_type=media.mime_type))
        record_input, question = validated_record(extracted, context)
    except (ProviderUnavailable, httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, OSError):
        raise api_error(503, "recognition_failed", "暂时没能识别，请点重试，录音或照片已保留")
    draft.record_type = extracted.get("record_type") if extracted.get("record_type") in RECORD_TYPES else None
    draft.payload = extracted.get("payload") if isinstance(extracted.get("payload"), dict) else {}
    draft.missing_fields = [str(x) for x in extracted.get("missing_fields", [])] if isinstance(extracted.get("missing_fields"), list) else []
    draft.recognition_warnings = [str(x) for x in extracted.get("recognition_warnings", [])] if isinstance(extracted.get("recognition_warnings"), list) else []
    conv = _get_or_create_conversation(db, user.family_id, draft.baby_id, UUID(context["conversation_id"]) if context.get("conversation_id") else None)
    context.update(conversation_id=str(conv.id), question=question, turns=turns)
    source_media = reply_media or media
    db.add(AiMessage(conversation_id=conv.id, role="user", content=text or "[图片记录]", structured_payload={"media": media_out(source_media).model_dump(mode="json"), "draft_id": str(draft.id)}, created_at=now()))
    record_id = None
    if record_input:
        record = BabyRecord(family_id=user.family_id, baby_id=draft.baby_id, source=draft.source, created_by=user.id, **record_input.model_dump(mode="json", exclude={"occurred_at"}), occurred_at=record_input.occurred_at)
        db.add(record)
        db.flush()
        db.add(RecordMedia(record_id=record.id, media_id=media.id))
        record_id = str(record.id)
        context["record_id"] = record_id
        draft.status = "saved"
        draft.occurred_at = record.occurred_at
        answer = summary_for(record)
    else:
        answer = question
    draft.capture_context = context
    db.add(AiMessage(conversation_id=conv.id, role="assistant", content=answer, model="quick-capture", created_at=now(),
                     structured_payload={"summary": answer, "draft_id": str(draft.id), "related_record_ids": [record_id] if record_id else [], "actions": [], "sources": [], "watch_for": []}))
    conv.updated_at = now()
    db.commit()
    return result_for(db, draft)


@router.post("/record-drafts/capture", response_model=CaptureResult)
def capture(body: CaptureStart, user: User = Depends(current_user), db: Session = Depends(get_db)):
    baby_for(db, body.baby_id, user.family_id)
    try: ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError): raise api_error(422, "invalid_timezone", "时区名称无效")
    media = owned_media(db, body.media_id, user, body.baby_id)
    draft = capture_for(db, media.id)
    if draft: return result_for(db, draft)
    transcript = transcribe(media) if media.media_type == "audio" else None
    stamp = body.occurred_at or media.created_at
    if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=ZoneInfo(body.timezone))
    draft = RecordDraft(family_id=user.family_id, baby_id=body.baby_id, media_id=media.id, source="voice" if transcript else "photo", transcript=transcript, status="draft", capture_context={"timezone": body.timezone, "captured_at": stamp.isoformat()})
    db.add(draft)
    db.flush()
    return process(db, draft, media, user, transcript or "[图片记录]")


@router.get("/record-drafts/pending", response_model=list[CaptureResult])
def pending(baby_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    baby_for(db, baby_id, user.family_id)
    drafts = db.scalars(select(RecordDraft).where(RecordDraft.family_id == user.family_id, RecordDraft.baby_id == baby_id, RecordDraft.status == "draft", RecordDraft.capture_context.is_not(None)).order_by(RecordDraft.created_at)).all()
    return [result_for(db, draft) for draft in drafts]


@router.post("/record-drafts/{draft_id}/reply", response_model=CaptureResult)
def reply(draft_id: UUID, body: CaptureReply, user: User = Depends(current_user), db: Session = Depends(get_db)):
    draft = db.scalar(select(RecordDraft).where(RecordDraft.id == draft_id, RecordDraft.family_id == user.family_id, RecordDraft.capture_context.is_not(None)))
    if not draft: raise api_error(404, "draft_not_found", "没有找到待补充记录")
    media = owned_media(db, draft.media_id, user)
    db.refresh(draft)
    context = draft.capture_context
    if draft.status != "draft" or any(t["request_id"] == str(body.request_id) for t in context.get("turns", [])):
        return result_for(db, draft)
    extra = owned_media(db, body.media_id, user, draft.baby_id) if body.media_id else None
    text = transcribe(extra) if extra else body.message.strip()
    return process(db, draft, media, user, text, body.request_id, extra)


@router.post("/record-drafts/capture/{media_id}/cancel", response_model=CaptureResult)
def cancel(media_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    media = owned_media(db, media_id, user)
    draft = capture_for(db, media.id)
    if not draft:
        draft = RecordDraft(family_id=user.family_id, baby_id=media.baby_id, media_id=media.id, source="voice" if media.media_type == "audio" else "photo", capture_context={})
        db.add(draft)
    if draft.status != "saved":
        draft.status = "cancelled"
    db.commit()
    return result_for(db, draft)
