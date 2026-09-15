import base64
import hashlib
import hmac
import json
import os
import time
from uuid import UUID

# ponytail: 开发默认值，生产必须设 JWT_SECRET 环境变量
JWT_SECRET = os.environ.get("JWT_SECRET", "dongbao-dev-secret")
TOKEN_TTL_SECONDS = 30 * 86400

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

def _sign(message: str) -> str:
    return _b64e(hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).digest())

def issue_token(user_id: UUID, family_id: UUID) -> str:
    header = _b64e(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64e(json.dumps({"uid": str(user_id), "fid": str(family_id), "exp": int(time.time()) + TOKEN_TTL_SECONDS}).encode())
    return f"{header}.{payload}.{_sign(f'{header}.{payload}')}"

def verify_token(token: str) -> tuple[UUID, UUID]:
    """验签并检查过期；非法一律 ValueError。吊销靠鉴权时查用户表。"""
    try:
        header, payload, sig = token.split(".")
        if not hmac.compare_digest(_sign(f"{header}.{payload}"), sig):
            raise ValueError
        data = json.loads(_b64d(payload))
        if int(data.get("exp", 0)) < time.time():
            raise ValueError
        return UUID(data["uid"]), UUID(data["fid"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid token") from exc
