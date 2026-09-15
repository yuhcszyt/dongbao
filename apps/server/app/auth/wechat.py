import os

import httpx

class WeChatLoginError(Exception):
    pass

async def code_to_openid(code: str) -> str:
    appid = os.environ.get("WECHAT_APPID", "")
    secret = os.environ.get("WECHAT_SECRET", "")
    if not appid or not secret:
        raise WeChatLoginError("微信登录未配置")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={"appid": appid, "secret": secret, "js_code": code, "grant_type": "authorization_code"},
        )
    data = resp.json()
    openid = data.get("openid")
    if not openid:
        raise WeChatLoginError(str(data.get("errmsg") or "微信登录失败"))
    return str(openid)
