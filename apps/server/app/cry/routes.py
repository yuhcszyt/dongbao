from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.dependencies import api_error, current_user
from ..auth.models import User
from ..record.database import get_db
from ..record.models import MediaAsset
from ..record.routes import baby_for
from ..record.storage import media_path
from .classifier import MODEL_ID, MODEL_REVISION, CryModelUnavailable, InvalidCryAudio, classify_audio, is_uncertain
from .schemas import CryAnalysisRequest, CryAnalysisResponse

router = APIRouter(prefix="/api/v1/cry-analyses", tags=["cry"])


def audio_for(db: Session, media_id: UUID, baby_id: UUID, family_id: UUID) -> MediaAsset:
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.baby_id == baby_id,
            MediaAsset.family_id == family_id,
            MediaAsset.media_type == "audio",
        )
    )
    if not media:
        raise api_error(404, "audio_not_found", "没有找到可分析的录音")
    return media


@router.post("", response_model=CryAnalysisResponse)
async def analyze_cry(
    body: CryAnalysisRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    baby_for(db, body.baby_id, user.family_id)
    media = audio_for(db, body.media_id, body.baby_id, user.family_id)
    path = media_path(media.object_key)
    if not path.is_file():
        raise api_error(404, "audio_not_found", "录音文件已经不可用")
    try:
        candidates = await run_in_threadpool(classify_audio, path)
    except InvalidCryAudio as exc:
        raise api_error(422, "invalid_cry_audio", str(exc)) from exc
    except CryModelUnavailable as exc:
        raise api_error(503, "cry_model_unavailable", str(exc)) from exc

    uncertain = is_uncertain(candidates)
    primary = None if uncertain else candidates[0]["category"]
    summary = "各类声音特征很接近，暂时无法判断" if uncertain else f"声音特征更接近{candidates[0]['label']}"
    return CryAnalysisResponse(
        status="uncertain" if uncertain else "experimental",
        primary_category=primary,
        summary=summary,
        candidates=candidates,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        disclaimer="声音匹配度不等于实际原因发生概率，仅供辅助排查，不用于医疗诊断。",
    )
