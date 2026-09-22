import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ..config import get_config

logger = logging.getLogger(__name__)

class ProviderUnavailable(Exception):
    pass

def _secret(name: str) -> str:
    # 凭证只从环境变量里读：缺了就降级成「已转为手动填写」，而不是抛 NameError 变成 500。
    value = os.environ.get(name, "")
    if not value:
        raise ProviderUnavailable("服务尚未配置，已转为手动填写")
    return value

def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()

# 腾讯一句话识别 VoiceFormat：按实际上传 MIME 映射，避免小程序录 wav / 工具录「伪 mp3」时被配置写死卡死。
MIME_TO_VOICE_FORMAT = {
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
}


async def transcribe_audio(path: Path, mime_type: str) -> str:
    from .audio_convert import NEEDS_WAV_CONVERT, convert_to_asr_wav

    cfg = get_config().tencent_asr
    if not cfg.enabled:
        raise ProviderUnavailable("语音识别尚未启用，已转为手动填写")
    secret_id, secret_key = _secret(cfg.secret_id_env), _secret(cfg.secret_key_env)
    work_path = path
    cleanup: Path | None = None
    voice_format = MIME_TO_VOICE_FORMAT.get(mime_type)
    if not voice_format and mime_type in NEEDS_WAV_CONVERT:
        cleanup = convert_to_asr_wav(path)
        work_path = cleanup
        voice_format = "wav"
    if not voice_format:
        raise ProviderUnavailable("当前录音格式暂不支持识别，已保留录音并转为手动填写")
    try:
        raw = work_path.read_bytes()
    finally:
        if cleanup is not None:
            cleanup.unlink(missing_ok=True)
    body = {
        "ProjectId": 0,
        "SubServiceType": 2,
        "EngSerViceType": cfg.engine_model_type,
        "SourceType": 1,
        "VoiceFormat": voice_format,
        "DataLen": len(raw),
        "Data": base64.b64encode(raw).decode(),
    }
    timestamp = int(datetime.now(timezone.utc).timestamp())
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    host = httpx.URL(cfg.endpoint).host
    service = "asr"
    action = "SentenceRecognition"
    version = "2019-06-14"
    canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = "POST\n/\n\n" + canonical_headers + "\n" + signed_headers + "\n" + hashlib.sha256(payload.encode()).hexdigest()
    scope = f"{date}/{service}/tc3_request"
    string_to_sign = "TC3-HMAC-SHA256\n" + str(timestamp) + "\n" + scope + "\n" + hashlib.sha256(canonical_request.encode()).hexdigest()
    secret_date = _sign(("TC3" + secret_key).encode(), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": cfg.region,
    }
    async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
        response = await client.post(cfg.endpoint, content=payload.encode(), headers=headers)
        response.raise_for_status()
        data = response.json().get("Response", {})
    return transcript_from_tencent_response(data)


def transcript_from_tencent_response(data: dict[str, Any]) -> str:
    """腾讯一句话识别 Response → 转写。空 Result 是没听清，不是配置故障。"""
    error = data.get("Error")
    if error:
        logger.warning("腾讯 ASR 失败：%s", error)
        raise ProviderUnavailable("语音识别暂时失败，已保留录音并转为手动填写")
    result = str(data.get("Result") or "").strip()
    if not result:
        logger.info("腾讯 ASR 空结果 duration_ms=%s", data.get("AudioDuration"))
        raise ProviderUnavailable("没有听清说话，请靠近手机大声说完后再点结束")
    return result

def _json_content(text: str) -> dict[str, Any]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
    value = json.loads(clean)
    if not isinstance(value, dict):
        raise ValueError("model output is not an object")
    return value

DRAFT_SYSTEM_PROMPT = """你是「懂宝」育儿记录助手，只根据家长语音转写或照片，提取一条宝宝日常记录草稿。
规则：
1. 只返回一个 JSON 对象，字段固定为：record_type、occurred_at、payload、note、missing_fields、recognition_warnings。
2. record_type 只能是：feeding、complementary_food、vitamin_ad、sleep、stool、diaper、crying、growth、vaccine、medication、custom。
3. payload.kind 必须与 record_type 完全一致。
4. 维生素 AD / 伊可新等日常滴剂用 vitamin_ad；其它药品用 medication。
5. 看不清的奶量、克数、药量不要猜，写进 missing_fields；可观察信息写进 payload。
6. recognition_warnings 用中文短句说明不确定之处；没有就空数组。
7. occurred_at 不确定时可为 null。非记录内容 record_type 为 null，missing_fields 写 record_type，不要硬凑 custom。
8. 用户提供的参考时间和时区用于解析“昨天”“刚才”；过去时间输出带时区的 ISO 时间。没说时间输出 null。
9. 补充回答与原始内容合并为同一条记录，保留已明确的事实；解决的 missing_fields 和 recognition_warnings 必须移除。
10. payload 格式：feeding {kind, feeding_type: breast/formula/mixed/unknown, amount_ml}；sleep {kind, duration_minutes 或 start_at/end_at}；stool {kind,color,consistency}；diaper {kind,content}；complementary_food {kind,food_name,amount_text}；vitamin_ad {kind,dose_text}；growth {kind,height_cm,weight_kg}；vaccine {kind,name,dose}；medication {kind,name,dosage_text}；crying {kind,duration_minutes,description}；custom {kind,title,details}。不要输出其它字段。
11. 物品照片不能证明宝宝已吃掉或用过；如果事件本身不明确，missing_fields 写 event，追问实际发生了什么。"""

DRAFT_USER_VOICE = "家长语音转写如下，请提取记录草稿 JSON：\n{content}"
DRAFT_USER_PHOTO = "请看这张照片，判断家长想记哪一类宝宝日常（奶瓶/辅食/便便/维生素AD等），提取可观察信息并返回草稿 JSON。禁止编造看不清的数字。"


async def extract_draft(content: str | None = None, image_path: Path | None = None, mime_type: str | None = None) -> dict[str, Any]:
    cfg = get_config().large_model
    if not cfg.enabled:
        raise ProviderUnavailable("智能识别尚未启用，已转为手动填写")
    if image_path and not cfg.supports_vision:
        raise ProviderUnavailable("图片识别尚未启用，已转为手动填写")
    api_key = _secret(cfg.api_key_env)
    if image_path:
        user_text = DRAFT_USER_PHOTO + ("\n补充上下文：\n" + content if content else "")
    else:
        user_text = DRAFT_USER_VOICE.format(content=(content or "").strip() or "（无转写内容）")
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    if image_path:
        encoded = base64.b64encode(image_path.read_bytes()).decode()
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}})
    request = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "thinking": {"type": "disabled"},
    }
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
        response = await client.post(url, json=request, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
    return _json_content(text)
