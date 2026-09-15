"""「provider 打开、凭证没配」这条路径：不经任何 patch，走真实 provider 代码。

票据 09 的断链：`app/record/providers.py` 的 `_secret()` 里 `if not value:` 用了一个从未定义的
`value`，于是缺凭证时抛的是 `NameError`（500），而不是「保留媒体 + 可编辑草稿 + 转为手动填写」。
既有用例把 `transcribe_audio` / `extract_draft` 整个 patch 掉了，所以这条路径一直没有覆盖——
本文件补的就是这个盲区，因此**刻意不 patch provider 的任何函数**。
"""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import wave

import pytest
from fastapi.testclient import TestClient

from app.config import get_config
from app.main import app

client = TestClient(app)

# provider 全部打开、凭证全部缺席的配置：端点指向不可达地址，正常路径在发请求前就降级。
NO_CREDENTIALS_CONFIG = Path(__file__).parent / "providers-no-credentials.toml"
ABSENT_CREDENTIAL_ENVS = ("TENCENT_SECRET_ID", "TENCENT_SECRET_KEY", "MODEL_API_KEY")


@pytest.fixture
def providers_without_credentials(monkeypatch):
    """让「provider 已启用」成立、「凭证缺失」也成立，而不是靠环境巧合。"""
    monkeypatch.setenv("APP_CONFIG", str(NO_CREDENTIALS_CONFIG))
    for name in ABSENT_CREDENTIAL_ENVS:
        monkeypatch.delenv(name, raising=False)
    get_config.cache_clear()
    yield
    get_config.cache_clear()


def create_baby(headers: dict) -> str:
    response = client.post("/api/v1/babies", json={"nickname": "安安", "birth_date": "2026-01-01", "gender": "female"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def wav_file(seconds: int = 1) -> bytes:
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000 * seconds)
    return stream.getvalue()


def upload(headers: dict, baby_id: str, name: str, content: bytes, mime: str) -> dict:
    response = client.post("/api/v1/media", data={"baby_id": baby_id}, files={"file": (name, content, mime)}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def assert_graceful_draft(response, expected_media_id: str) -> dict:
    """降级的三条硬要求：201 草稿、来源文件还在、响应里没有上游错误原文。"""
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["record_type"] is None, "缺凭证时不该猜出记录类型"
    assert body["missing_fields"] == ["record_type"], "缺凭证时要留成可手动填写的草稿"
    assert body["recognition_warnings"] and all(warning for warning in body["recognition_warnings"])
    assert "服务尚未配置" in body["recognition_warnings"][0], body["recognition_warnings"]
    # 响应的任何位置都不得出现上游错误的原文（既包括 TypeError/NameError 这类，也包括 provider 地址）。
    for leaked in ("NameError", "Traceback", "unreachable.invalid", "Traceback (most recent call last)"):
        assert leaked not in response.text, f"响应里泄露了上游细节：{leaked}"
    assert body["media_id"] == expected_media_id
    assert client.get(f"/api/v1/media/{expected_media_id}").status_code == 200, "上传的语音/照片不能因为降级而丢失"
    return body


def test_voice_draft_degrades_to_manual_when_credentials_missing(providers_without_credentials, auth):
    headers = auth()
    baby_id = create_baby(headers)
    media = upload(headers, baby_id, "voice.wav", wav_file(), "audio/wav")

    draft = client.post("/api/v1/record-drafts/from-voice", json={"baby_id": baby_id, "media_id": media["id"]}, headers=headers)

    body = assert_graceful_draft(draft, media["id"])
    assert body["transcript"] is None, "没配上凭证时不该有转写文本"
    assert body["source"] == "voice"

    confirmed = client.post(
        f"/api/v1/record-drafts/{body['id']}/confirm",
        json={"record_type": "feeding", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": {"kind": "feeding", "feeding_type": "formula", "amount_ml": 120}, "note": "手动补的"},
        headers=headers,
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["media"][0]["id"] == media["id"], "确认草稿后录音仍挂在记录上"


def test_photo_draft_degrades_to_manual_when_credentials_missing(providers_without_credentials, auth):
    headers = auth()
    baby_id = create_baby(headers)
    media = upload(headers, baby_id, "photo.png", b"\x89PNG\r\n\x1a\n" + b"placeholder", "image/png")

    draft = client.post("/api/v1/record-drafts/from-photo", json={"baby_id": baby_id, "media_id": media["id"]}, headers=headers)

    body = assert_graceful_draft(draft, media["id"])
    assert body["source"] == "photo"
    assert client.get(f"/api/v1/babies/{baby_id}/records", headers=headers).json() == [], "草稿不该直接进时间线"
