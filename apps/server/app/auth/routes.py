import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..erasure import erase_family
from ..record.database import get_db
from .dependencies import api_error, current_user
from .models import Family, User
from .security import issue_token
from .wechat import LOGIN_FAILED_MESSAGE, WeChatLoginError, code_to_openid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["auth"])

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
        raise api_error(502, "wechat_login_failed", LOGIN_FAILED_MESSAGE)
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
    """注销账号：该用户与整个家庭的数据一并消失（旧 token 随即 401，见 dependencies）。"""
    erase_family(db, user.family_id)
