import hashlib
import os

import httpx

DEV_LOGIN_ENV = "DEV_LOGIN"

# code 直接当 openid 时的列宽上限，与 users.openid 同宽
DEV_OPENID_MAX_LENGTH = 64

# 客户端统一看到的失败文案：微信侧（或配置缺失）的任何原始细节都不外泄，只进服务端日志。
LOGIN_FAILED_MESSAGE = "微信登录失败，请稍后重试"

class WeChatLoginError(Exception):
    """微信侧失败。message 仅供服务端日志，绝不回给客户端。"""

def dev_login_enabled() -> bool:
    """开发降级只认显式的 DEV_LOGIN=1（容忍首尾空白），其余取值一律视为关闭。"""
    return os.environ.get(DEV_LOGIN_ENV, "").strip() == "1"

def login_mode_message() -> str:
    if dev_login_enabled():
        return f"登录模式：开发降级（{DEV_LOGIN_ENV}=1：跳过 jscode2session，code 直接作为 openid；生产环境禁止开启）"
    return "登录模式：真实微信（jscode2session）"

def _dev_openid(code: str) -> str:
    """开发降级下 code 直接当 openid；超长 code 取摘要，保证「任意字符串都能登录」。"""
    if len(code) <= DEV_OPENID_MAX_LENGTH:
        return code
    return "dev-" + hashlib.sha256(code.encode()).hexdigest()[: DEV_OPENID_MAX_LENGTH - 4]

async def code_to_openid(code: str) -> str:
    if dev_login_enabled():
        return _dev_openid(code)
    appid = os.environ.get("WECHAT_APPID", "")
    secret = os.environ.get("WECHAT_SECRET", "")
    if not appid or not secret:
        raise WeChatLoginError("微信登录未配置：缺少 WECHAT_APPID 或 WECHAT_SECRET")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={"appid": appid, "secret": secret, "js_code": code, "grant_type": "authorization_code"},
            )
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WeChatLoginError(f"微信接口不可用：{exc!r}") from exc
    openid = data.get("openid")
    if not openid:
        raise WeChatLoginError(f"微信拒绝登录：errcode={data.get('errcode')} errmsg={data.get('errmsg')}")
    return str(openid)
