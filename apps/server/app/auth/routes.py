import logging
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..record.database import get_db
from ..record.models import Baby, BabyRecord, MediaAsset, RecordDraft, RecordMedia
from .models import Family, User
from .security import issue_token, verify_token
from .wechat import LOGIN_FAILED_MESSAGE, WeChatLoginError, code_to_openid

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/app/data/media"))

router = APIRouter(prefix="/api/v1", tags=["auth"])

def _raise(status: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})

def current_user(authorization: str = Header(""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        _raise(401, "missing_token", "请先登录")
    try:
        user_id, _ = verify_token(authorization[7:])
    except ValueError:
        _raise(401, "invalid_token", "登录已过期，请重新进入")
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        _raise(401, "invalid_token", "账号已注销")  # 吊销：用户删了即 401，无需 Redis
    return user

class WeChatLoginIn(BaseModel):
    code: str = Field(min_length=1, max_length=128)

class TokenOut(BaseModel):
    token: str
    user_id: UUID

@router.post("/auth/wechat", response_model=TokenOut)
async def login_wechat(body: WeChatLoginIn, db: Session = Depends(get_db)):
    try:
        openid = await code_to_openid(body.code)
    except WeChatLoginError as exc:
        logger.warning("微信登录失败：%s", exc)  # 原始细节只进日志
        _raise(502, "wechat_login_failed", LOGIN_FAILED_MESSAGE)
    user = db.scalar(select(User).where(User.openid == openid))
    if not user:
        family = Family()
        db.add(family)
        db.flush()
        user = User(openid=openid, family_id=family.id)
        db.add(user)
        db.commit()
    return TokenOut(token=issue_token(user.id, user.family_id), user_id=user.id)

@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    fid = user.family_id
    media_rows = db.scalars(select(MediaAsset).where(MediaAsset.family_id == fid)).all()
    db.execute(delete(RecordMedia).where(RecordMedia.record_id.in_(select(BabyRecord.id).where(BabyRecord.family_id == fid))))
    db.execute(delete(BabyRecord).where(BabyRecord.family_id == fid))
    db.execute(delete(RecordDraft).where(RecordDraft.family_id == fid))
    db.execute(delete(MediaAsset).where(MediaAsset.family_id == fid))
    db.execute(delete(Baby).where(Baby.family_id == fid))
    db.delete(user)
    db.execute(delete(Family).where(Family.id == fid))
    db.commit()
    for media in media_rows:  # 文件留在事务提交后删，失败也不丢数据一致性
        try:
            (MEDIA_ROOT / media.object_key).unlink(missing_ok=True)
        except OSError:
            pass
