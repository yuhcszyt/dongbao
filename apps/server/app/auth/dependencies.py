"""鉴权依赖的唯一实现：记录侧与鉴权侧共用同一份。

链路固定为「解析 Bearer → 验签验过期 → 查用户表 → 返回当前用户及其家庭」：返回的 `User`
就是「当前用户 + 当前家庭」这一对——`user.family_id` 即当前家庭 ID，记录路由直接用它，
不再多引一层只转发 family_id 的依赖。

家庭归属以**数据库里的 user.family_id** 为准，不信 token 里的 fid——token 只是身份的载体，
换家庭（本 MVP 不做）时无需让旧 token 继续指向旧家庭。
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..record.database import get_db
from .models import User
from .security import verify_token

# 客户端与测试都依赖这些文案，改动即破坏契约
MISSING_TOKEN_MESSAGE = "请先登录"
INVALID_TOKEN_MESSAGE = "登录已过期，请重新进入"
DELETED_ACCOUNT_MESSAGE = "账号已注销"


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def current_user(authorization: str = Header(""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise api_error(401, "missing_token", MISSING_TOKEN_MESSAGE)
    try:
        # token 里的 fid 刻意丢弃：家庭一律回查数据库（见模块 docstring）
        user_id, _claimed_family_id = verify_token(authorization[7:])
    except ValueError:
        raise api_error(401, "invalid_token", INVALID_TOKEN_MESSAGE)
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise api_error(401, "invalid_token", DELETED_ACCOUNT_MESSAGE)  # 注销后旧 token 立即失效
    return user
