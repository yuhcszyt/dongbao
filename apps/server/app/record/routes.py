from datetime import date, datetime, time, timezone
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import os
import wave

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from mutagen import File as MutagenFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_config
from .database import get_db
from .models import Baby, BabyRecord, MediaAsset, RecordDraft, RecordMedia, now
from .providers import ProviderUnavailable, extract_draft, transcribe_audio
from .schemas import BabyCreate, BabyOut, BabyUpdate, DailySummary, DraftConfirm, DraftOut, DraftRequest, MediaOut, RecordCreate, RecordOut, RecordUpdate, RecordType

router = APIRouter()

FAMILY_ID = UUID(os.environ.get("TEST_FAMILY_ID", "00000000-0000-0000-0000-000000000001"))
USER_ID = UUID(os.environ.get("TEST_USER_ID", "00000000-0000-0000-0000-000000000002"))
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/app/data/media"))
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_AUDIO_SECONDS = 60
RECORD_TYPES = {"feeding", "complementary_food", "sleep", "stool", "diaper", "crying", "growth", "vaccine", "medication", "custom"}

def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def baby_for(db: Session, baby_id: UUID) -> Baby:
    baby = db.scalar(select(Baby).where(Baby.id == baby_id, Baby.family_id == FAMILY_ID))
    if not baby:
        raise error(404, "baby_not_found", "没有找到宝宝档案")
    return baby

def record_for(db: Session, baby_id: UUID, record_id: UUID, include_deleted: bool = False) -> BabyRecord:
    query = select(BabyRecord).where(BabyRecord.id == record_id, BabyRecord.baby_id == baby_id, BabyRecord.family_id == FAMILY_ID)
    if not include_deleted:
        query = query.where(BabyRecord.deleted_at.is_(None))
    record = db.scalar(query)
    if not record:
        raise error(404, "record_not_found", "没有找到这条记录")
    return record

def media_out(media: MediaAsset) -> MediaOut:
    return MediaOut(id=media.id, baby_id=media.baby_id, media_type=media.media_type, mime_type=media.mime_type, size_bytes=media.size_bytes, duration_ms=media.duration_ms, url=f"/api/v1/media/{media.id}")

def record_out(db: Session, record: BabyRecord) -> RecordOut:
    media = db.scalars(select(MediaAsset).join(RecordMedia, RecordMedia.media_id == MediaAsset.id).where(RecordMedia.record_id == record.id)).all()
    draft = db.scalar(select(RecordDraft).join(RecordMedia, RecordMedia.media_id == RecordDraft.media_id).where(RecordMedia.record_id == record.id)) if media else None
    return RecordOut.model_validate(record, from_attributes=True).model_copy(update={"media": [media_out(item) for item in media], "transcript": draft.transcript if draft else None})

@router.get("/health")
def health():
    get_config()
    return {"status": "ok"}

@router.post("/api/v1/babies", response_model=BabyOut, status_code=201)
def create_baby(body: BabyCreate, db: Session = Depends(get_db)):
    baby = Baby(family_id=FAMILY_ID, **body.model_dump())
    db.add(baby); db.commit(); db.refresh(baby)
    return baby

@router.get("/api/v1/babies", response_model=list[BabyOut])
def list_babies(db: Session = Depends(get_db)):
    return db.scalars(select(Baby).where(Baby.family_id == FAMILY_ID).order_by(Baby.created_at)).all()

@router.get("/api/v1/babies/{baby_id}", response_model=BabyOut)
def get_baby(baby_id: UUID, db: Session = Depends(get_db)):
    return baby_for(db, baby_id)

@router.patch("/api/v1/babies/{baby_id}", response_model=BabyOut)
@router.put("/api/v1/babies/{baby_id}", response_model=BabyOut)
def update_baby(baby_id: UUID, body: BabyUpdate, db: Session = Depends(get_db)):
    baby = baby_for(db, baby_id)
    for key, value in body.model_dump().items(): setattr(baby, key, value)
    db.commit(); db.refresh(baby)
    return baby

MAGIC = {
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "audio/wav": lambda b: len(b) > 12 and b.startswith(b"RIFF") and b[8:12] == b"WAVE",
    "audio/x-wav": lambda b: len(b) > 12 and b.startswith(b"RIFF") and b[8:12] == b"WAVE",
    "audio/mpeg": lambda b: b.startswith(b"ID3") or (len(b) > 1 and b[0] == 0xFF and b[1] & 0xE0 == 0xE0),
    "audio/mp4": lambda b: len(b) > 12 and b[4:8] == b"ftyp",
    "audio/x-m4a": lambda b: len(b) > 12 and b[4:8] == b"ftyp",
    "audio/webm": lambda b: b.startswith(b"\x1aE\xdf\xa3"),
}
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/webm": ".webm"}

@router.post("/api/v1/media", response_model=MediaOut, status_code=201)
async def upload_media(baby_id: UUID = Form(...), reported_duration_ms: int | None = Form(default=None, alias="duration_ms"), file: UploadFile = File(...), db: Session = Depends(get_db)):
    baby_for(db, baby_id)
    mime = (file.content_type or "").lower()
    if mime not in MAGIC:
        raise error(415, "unsupported_media", "仅支持 JPG、PNG、MP3、M4A 或 WAV")
    limit = MAX_IMAGE_BYTES if mime.startswith("image/") else MAX_AUDIO_BYTES
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise error(413, "media_too_large", "文件过大，请重新选择")
    if not data or not MAGIC[mime](data):
        raise error(422, "invalid_media", "文件内容与格式不符，请重新选择")
    duration_ms = None
    if mime.startswith("audio/"):
        if mime in {"audio/wav", "audio/x-wav"}:
            try:
                with wave.open(BytesIO(data)) as audio:
                    duration_ms = round(audio.getnframes() / audio.getframerate() * 1000)
            except (wave.Error, EOFError, ZeroDivisionError):
                raise error(422, "invalid_audio", "无法读取录音，请重新录制")
        elif mime == "audio/webm":
            duration_ms = reported_duration_ms
            if duration_ms is None or duration_ms <= 0:
                raise error(422, "invalid_audio", "无法读取录音时长，请重新录制")
        else:
            parsed = MutagenFile(BytesIO(data))
            if not parsed or not getattr(parsed, "info", None) or not getattr(parsed.info, "length", None):
                raise error(422, "invalid_audio", "无法读取录音，请重新录制")
            duration_ms = round(parsed.info.length * 1000)
        if duration_ms > MAX_AUDIO_SECONDS * 1000:
            raise error(422, "audio_too_long", f"录音不能超过 {MAX_AUDIO_SECONDS} 秒")
    media_id = uuid4()
    key = f"{media_id.hex[:2]}/{media_id.hex}{EXTENSIONS[mime]}"
    root = MEDIA_ROOT
    target = root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    media = MediaAsset(id=media_id, family_id=FAMILY_ID, baby_id=baby_id, media_type="image" if mime.startswith("image/") else "audio", mime_type=mime, object_key=key, size_bytes=len(data), duration_ms=duration_ms)
    db.add(media)
    try:
        db.commit()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return media_out(media)

@router.get("/api/v1/media/{media_id}")
def read_media(media_id: UUID, db: Session = Depends(get_db)):
    media = db.scalar(select(MediaAsset).where(MediaAsset.id == media_id, MediaAsset.family_id == FAMILY_ID))
    if not media: raise error(404, "media_not_found", "没有找到这个媒体文件")
    root = MEDIA_ROOT.resolve()
    path = (root / media.object_key).resolve()
    if root not in path.parents or not path.is_file(): raise error(404, "media_not_found", "媒体文件不可用")
    return FileResponse(path, media_type=media.mime_type, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})

async def make_draft(body: DraftRequest, source: str, expected_media: str, db: Session) -> RecordDraft:
    baby_for(db, body.baby_id)
    media = db.scalar(select(MediaAsset).where(MediaAsset.id == body.media_id, MediaAsset.baby_id == body.baby_id, MediaAsset.family_id == FAMILY_ID))
    if not media or media.media_type != expected_media:
        raise error(404, "media_not_found", "没有找到可用的来源文件")
    path = MEDIA_ROOT / media.object_key
    transcript = None
    warnings: list[str] = []
    extracted: dict = {}
    try:
        if source == "voice": transcript = await transcribe_audio(path, media.mime_type)
        extracted = await extract_draft(content=transcript, image_path=path if source == "photo" else None, mime_type=media.mime_type)
    except (ProviderUnavailable, ValueError, KeyError, IndexError, TypeError, AttributeError, httpx.HTTPError) as exc:
        warnings.append(str(exc) if isinstance(exc, ProviderUnavailable) else "识别暂时失败，已保留来源文件，请手动补充")
    record_type = extracted.get("record_type") if extracted.get("record_type") in RECORD_TYPES else None
    payload = extracted.get("payload") if isinstance(extracted.get("payload"), dict) else ({"kind": record_type} if record_type else {})
    missing = extracted.get("missing_fields") if isinstance(extracted.get("missing_fields"), list) else ([] if record_type else ["record_type"])
    model_warnings = extracted.get("recognition_warnings") if isinstance(extracted.get("recognition_warnings"), list) else []
    draft = RecordDraft(family_id=FAMILY_ID, baby_id=body.baby_id, media_id=body.media_id, record_type=record_type, occurred_at=body.occurred_at or now(), payload=payload, note=extracted.get("note") if isinstance(extracted.get("note"), str) else None, missing_fields=[str(v) for v in missing], source=source, transcript=transcript, recognition_warnings=warnings + [str(v) for v in model_warnings], status="draft")
    db.add(draft); db.commit(); db.refresh(draft)
    return draft

@router.post("/api/v1/record-drafts/from-voice", response_model=DraftOut, status_code=201)
async def draft_voice(body: DraftRequest, db: Session = Depends(get_db)):
    return await make_draft(body, "voice", "audio", db)

@router.post("/api/v1/record-drafts/from-photo", response_model=DraftOut, status_code=201)
async def draft_photo(body: DraftRequest, db: Session = Depends(get_db)):
    return await make_draft(body, "photo", "image", db)

@router.post("/api/v1/record-drafts/{draft_id}/confirm", response_model=RecordOut, status_code=201)
def confirm_draft(draft_id: UUID, body: DraftConfirm, db: Session = Depends(get_db)):
    draft = db.scalar(select(RecordDraft).where(RecordDraft.id == draft_id, RecordDraft.family_id == FAMILY_ID).with_for_update())
    if not draft: raise error(404, "draft_not_found", "没有找到这份草稿")
    if draft.status != "draft": raise error(409, "draft_already_confirmed", "这份草稿已经确认过")
    draft.status = "confirmed"
    record = BabyRecord(family_id=FAMILY_ID, baby_id=draft.baby_id, record_type=body.record_type, occurred_at=body.occurred_at, source=draft.source, payload=body.payload.model_dump(mode="json"), note=body.note, created_by=USER_ID)
    db.add(record); db.flush()
    if draft.media_id: db.add(RecordMedia(record_id=record.id, media_id=draft.media_id))
    draft.status = "saved"
    db.commit(); db.refresh(record)
    return record_out(db, record)

@router.post("/api/v1/babies/{baby_id}/records", response_model=RecordOut, status_code=201)
def create_record(baby_id: UUID, body: RecordCreate, db: Session = Depends(get_db)):
    baby_for(db, baby_id)
    record = BabyRecord(family_id=FAMILY_ID, baby_id=baby_id, record_type=body.record_type, occurred_at=body.occurred_at, source="manual", payload=body.payload.model_dump(mode="json"), note=body.note, created_by=USER_ID)
    db.add(record); db.commit(); db.refresh(record)
    return record_out(db, record)

@router.get("/api/v1/babies/{baby_id}/records", response_model=list[RecordOut])
def list_records(baby_id: UUID, record_type: RecordType | None = None, db: Session = Depends(get_db)):
    baby_for(db, baby_id)
    query = select(BabyRecord).where(BabyRecord.baby_id == baby_id, BabyRecord.family_id == FAMILY_ID, BabyRecord.deleted_at.is_(None))
    if record_type: query = query.where(BabyRecord.record_type == record_type)
    records = db.scalars(query.order_by(BabyRecord.occurred_at.desc(), BabyRecord.created_at.desc())).all()
    return [record_out(db, item) for item in records]

@router.get("/api/v1/babies/{baby_id}/records/{record_id}", response_model=RecordOut)
def get_record(baby_id: UUID, record_id: UUID, db: Session = Depends(get_db)):
    baby_for(db, baby_id)
    return record_out(db, record_for(db, baby_id, record_id))

@router.patch("/api/v1/babies/{baby_id}/records/{record_id}", response_model=RecordOut)
@router.put("/api/v1/babies/{baby_id}/records/{record_id}", response_model=RecordOut)
def update_record(baby_id: UUID, record_id: UUID, body: RecordUpdate, db: Session = Depends(get_db)):
    record = record_for(db, baby_id, record_id)
    if record.record_type != body.payload.kind: raise error(422, "payload_kind_mismatch", "记录类型与填写内容不一致")
    record.occurred_at = body.occurred_at; record.payload = body.payload.model_dump(mode="json"); record.note = body.note
    db.commit(); db.refresh(record)
    return record_out(db, record)

@router.delete("/api/v1/babies/{baby_id}/records/{record_id}", status_code=204)
def delete_record(baby_id: UUID, record_id: UUID, db: Session = Depends(get_db)):
    record = record_for(db, baby_id, record_id)
    record.deleted_at = now(); db.commit()

@router.post("/api/v1/babies/{baby_id}/records/{record_id}/restore", response_model=RecordOut)
def restore_record(baby_id: UUID, record_id: UUID, db: Session = Depends(get_db)):
    record = record_for(db, baby_id, record_id, include_deleted=True)
    if record.deleted_at is None: raise error(409, "record_not_deleted", "这条记录没有被删除")
    record.deleted_at = None; db.commit(); db.refresh(record)
    return record_out(db, record)

@router.get("/api/v1/babies/{baby_id}/daily-summary", response_model=DailySummary)
def daily_summary(baby_id: UUID, day: date = Query(alias="date", default_factory=date.today), timezone_name: str = Query("Asia/Shanghai", alias="timezone"), db: Session = Depends(get_db)):
    baby_for(db, baby_id)
    try: zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError: raise error(422, "invalid_timezone", "时区名称无效")
    start = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
    end = datetime.combine(day, time.max, zone).astimezone(timezone.utc)
    records = db.scalars(select(BabyRecord).where(BabyRecord.baby_id == baby_id, BabyRecord.family_id == FAMILY_ID, BabyRecord.deleted_at.is_(None), BabyRecord.occurred_at >= start, BabyRecord.occurred_at <= end)).all()
    feeding = sum(int(r.payload.get("amount_ml") or 0) for r in records if r.record_type == "feeding")
    sleep = 0
    for item in (r for r in records if r.record_type == "sleep"):
        if item.payload.get("duration_minutes") is not None: sleep += int(item.payload["duration_minutes"])
        elif item.payload.get("start_at") and item.payload.get("end_at"):
            sleep += max(0, round((datetime.fromisoformat(item.payload["end_at"]) - datetime.fromisoformat(item.payload["start_at"])).total_seconds() / 60))
    return DailySummary(date=day, timezone=timezone_name, feeding_ml=feeding, sleep_minutes=sleep, diaper_count=sum(r.record_type == "diaper" for r in records), complementary_food_count=sum(r.record_type == "complementary_food" for r in records))
