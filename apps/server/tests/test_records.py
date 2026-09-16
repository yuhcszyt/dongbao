from datetime import datetime, timedelta, timezone
from io import BytesIO
import wave

import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

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

PAYLOADS = [
    ("feeding", {"kind": "feeding", "feeding_type": "formula", "amount_ml": 180}),
    ("complementary_food", {"kind": "complementary_food", "food_name": "南瓜泥", "amount_text": "半碗"}),
    ("sleep", {"kind": "sleep", "duration_minutes": 90}),
    ("stool", {"kind": "stool", "color": "黄色", "consistency": "糊状"}),
    ("diaper", {"kind": "diaper", "content": "更换尿布"}),
    ("crying", {"kind": "crying", "duration_minutes": 5, "description": "哄抱后平静"}),
    ("growth", {"kind": "growth", "height_cm": 68.5}),
    ("vaccine", {"kind": "vaccine", "name": "乙肝疫苗", "dose": "第 2 剂"}),
    ("medication", {"kind": "medication", "name": "维生素 D", "dosage_text": "1 滴"}),
    ("custom", {"kind": "custom", "title": "第一次翻身", "details": "自己完成"}),
]

def test_manual_records_timeline_summary_delete_restore_and_edit(auth):
    headers = auth()
    baby_id = create_baby(headers)
    assert client.get("/api/v1/babies", headers=headers).json()[0]["id"] == baby_id
    current = datetime.now(timezone.utc)
    record_ids = []
    for index, (kind, payload) in enumerate(PAYLOADS):
        response = client.post(
            f"/api/v1/babies/{baby_id}/records",
            json={"record_type": kind, "occurred_at": (current - timedelta(minutes=index)).isoformat(), "payload": payload, "note": None},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        record_ids.append(response.json()["id"])

    timeline = client.get(f"/api/v1/babies/{baby_id}/records", headers=headers)
    assert timeline.status_code == 200
    assert [item["record_type"] for item in timeline.json()] == [kind for kind, _ in PAYLOADS]

    local_date = current.astimezone().date().isoformat()
    summary = client.get(f"/api/v1/babies/{baby_id}/daily-summary", params={"date": local_date, "timezone": "Asia/Shanghai"}, headers=headers)
    assert summary.status_code == 200
    assert summary.json()["feeding_ml"] == 180
    assert summary.json()["sleep_minutes"] == 90
    assert summary.json()["diaper_count"] == 1
    assert summary.json()["complementary_food_count"] == 1

    changed = client.put(
        f"/api/v1/babies/{baby_id}/records/{record_ids[0]}",
        json={"occurred_at": current.isoformat(), "payload": {"kind": "feeding", "feeding_type": "formula", "amount_ml": 200}, "note": "补记"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["payload"]["amount_ml"] == 200

    assert client.delete(f"/api/v1/babies/{baby_id}/records/{record_ids[0]}", headers=headers).status_code == 204
    assert len(client.get(f"/api/v1/babies/{baby_id}/records", headers=headers).json()) == 9
    assert client.get(f"/api/v1/babies/{baby_id}/daily-summary", params={"date": local_date, "timezone": "Asia/Shanghai"}, headers=headers).json()["feeding_ml"] == 0
    restored = client.post(f"/api/v1/babies/{baby_id}/records/{record_ids[0]}/restore", headers=headers)
    assert restored.status_code == 200

def test_voice_draft_requires_confirm_and_keeps_source(monkeypatch, auth):
    headers = auth()
    baby_id = create_baby(headers)
    media = client.post(
        "/api/v1/media",
        data={"baby_id": baby_id},
        files={"file": ("ignored-name.wav", wav_file(), "audio/wav")},
        headers=headers,
    )
    assert media.status_code == 201, media.text

    async def fake_transcribe(path, mime_type):
        return "宝宝刚喝了 180 毫升奶"

    async def fake_extract(**kwargs):
        return {"record_type": "feeding", "payload": {"kind": "feeding", "feeding_type": "formula", "amount_ml": 180}, "missing_fields": [], "recognition_warnings": []}

    monkeypatch.setattr("app.record.routes.transcribe_audio", fake_transcribe)
    monkeypatch.setattr("app.record.routes.extract_draft", fake_extract)
    draft = client.post("/api/v1/record-drafts/from-voice", json={"baby_id": baby_id, "media_id": media.json()["id"]}, headers=headers)
    assert draft.status_code == 201, draft.text
    assert draft.json()["payload"]["amount_ml"] == 180
    assert client.get(f"/api/v1/babies/{baby_id}/records", headers=headers).json() == []

    confirmed = client.post(
        f"/api/v1/record-drafts/{draft.json()['id']}/confirm",
        json={"record_type": "feeding", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": draft.json()["payload"], "note": None},
        headers=headers,
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["source"] == "voice"
    assert confirmed.json()["transcript"] == "宝宝刚喝了 180 毫升奶"
    assert len(confirmed.json()["media"]) == 1
    assert client.post(f"/api/v1/record-drafts/{draft.json()['id']}/confirm", json={"record_type": "feeding", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": draft.json()["payload"], "note": None}, headers=headers).status_code == 409

def test_provider_failure_returns_editable_draft_without_losing_media(monkeypatch, auth):
    headers = auth()
    baby_id = create_baby(headers)
    image = b"\x89PNG\r\n\x1a\n" + b"placeholder"
    media = client.post("/api/v1/media", data={"baby_id": baby_id}, files={"file": ("photo.png", image, "image/png")}, headers=headers)
    assert media.status_code == 201

    async def unavailable(**kwargs):
        raise httpx.ConnectError("provider secret must not leak")

    monkeypatch.setattr("app.record.routes.extract_draft", unavailable)
    draft = client.post("/api/v1/record-drafts/from-photo", json={"baby_id": baby_id, "media_id": media.json()["id"]}, headers=headers)
    assert draft.status_code == 201, draft.text
    assert draft.json()["status"] == "draft"
    assert draft.json()["record_type"] is None
    assert "provider secret" not in " ".join(draft.json()["recognition_warnings"])
    assert client.get(media.json()["url"]).status_code == 200
    confirmed = client.post(
        f"/api/v1/record-drafts/{draft.json()['id']}/confirm",
        json={"record_type": "custom", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": {"kind": "custom", "title": "手动补充"}, "note": None},
        headers=headers,
    )
    assert confirmed.status_code == 201
    assert confirmed.json()["source"] == "photo"
    assert confirmed.json()["media"][0]["id"] == media.json()["id"]

def test_create_baby_without_birthday(auth):
    headers = auth()
    omitted = client.post("/api/v1/babies", json={"nickname": "宝宝", "gender": "unknown"}, headers=headers)
    assert omitted.status_code == 201, omitted.text
    assert omitted.json()["nickname"] == "宝宝"
    assert omitted.json()["birth_date"] is None
    explicit_null = client.post("/api/v1/babies", json={"nickname": "宝宝", "gender": "unknown", "birth_date": None}, headers=headers)
    assert explicit_null.status_code == 201, explicit_null.text
    assert explicit_null.json()["birth_date"] is None


def test_rejects_mismatched_payload_and_invalid_upload(auth):
    headers = auth()
    baby_id = create_baby(headers)
    mismatch = client.post(
        f"/api/v1/babies/{baby_id}/records",
        json={"record_type": "feeding", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": {"kind": "diaper", "content": "更换尿布"}},
        headers=headers,
    )
    assert mismatch.status_code == 422
    invalid = client.post("/api/v1/media", data={"baby_id": baby_id}, files={"file": ("fake.png", b"not-png", "image/png")}, headers=headers)
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_media"
    assert invalid.json()["request_id"]


def test_upload_sniffs_wav_when_content_type_is_opaque(auth):
    """微信开发者工具常把录音标成 octet-stream；只要魔数是 WAV 就应收下。"""
    headers = auth()
    baby_id = create_baby(headers)
    response = client.post(
        "/api/v1/media",
        data={"baby_id": baby_id, "duration_ms": "1000"},
        files={"file": ("voice.wav", wav_file(), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["media_type"] == "audio"
    assert body["mime_type"] in {"audio/wav", "audio/x-wav"}
    assert body["duration_ms"] and body["duration_ms"] > 0


def test_upload_mpeg_falls_back_to_reported_duration_when_mutagen_fails(auth, monkeypatch):
    headers = auth()
    baby_id = create_baby(headers)
    # 合法 MPEG 帧同步头，但不是完整可解析文件
    fake_mp3 = bytes([0xFF, 0xFB]) + b"\0" * 64
    monkeypatch.setattr("app.record.routes.MutagenFile", lambda *_a, **_k: None)
    response = client.post(
        "/api/v1/media",
        data={"baby_id": baby_id, "duration_ms": "1500"},
        files={"file": ("voice.mp3", fake_mp3, "audio/mpeg")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["duration_ms"] == 1500
    assert response.json()["mime_type"] == "audio/mpeg"