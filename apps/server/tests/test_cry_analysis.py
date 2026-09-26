from datetime import timedelta
from io import BytesIO
import wave

from fastapi.testclient import TestClient

import pytest

from app.cry.classifier import CryModelUnavailable, InvalidCryAudio, ensure_audible, is_uncertain, normalize_predictions
from app.main import app
from app.cry.retention import purge_expired_cry_audio
from app.record.database import SessionLocal
from app.record.models import MediaAsset, now


def wav_bytes() -> bytes:
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\x00\x00" * 16_000)
    return stream.getvalue()


RAW = [
    {"label": "hungry", "score": 0.62},
    {"label": "discomfort", "score": 0.16},
    {"label": "tired", "score": 0.11},
    {"label": "belly_pain", "score": 0.07},
    {"label": "burping", "score": 0.04},
]


def create_audio(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    baby = client.post(
        "/api/v1/babies",
        headers=headers,
        json={"nickname": "小宝", "birth_date": None, "gender": "unknown"},
    ).json()
    media = client.post(
        "/api/v1/media",
        headers=headers,
        data={"baby_id": baby["id"], "purpose": "cry_analysis"},
        files={"file": ("cry.wav", wav_bytes(), "audio/wav")},
    ).json()
    return baby["id"], media["id"]


def test_normalize_returns_all_five_categories_in_score_order():
    result = normalize_predictions(list(reversed(RAW)))
    assert [item["category"] for item in result] == [
        "hungry", "discomfort", "tired", "belly_pain", "burping"
    ]
    assert result[0]["label"] == "饥饿"
    assert result[0]["possibility"] == "较可能"
    assert result[-1]["possibility"] == "可能性较低"
    assert not is_uncertain(result)


def test_close_predictions_are_marked_uncertain():
    result = normalize_predictions([
        {"label": "tired", "score": 0.34},
        {"label": "hungry", "score": 0.31},
    ])
    assert is_uncertain(result)


def test_silent_audio_is_rejected_before_classification(tmp_path):
    path = tmp_path / "silence.wav"
    path.write_bytes(wav_bytes())
    with pytest.raises(InvalidCryAudio, match="没有听到清晰声音"):
        ensure_audible(path)


def test_cry_endpoint_returns_five_candidates(monkeypatch, auth):
    client = TestClient(app)
    headers = auth()
    baby_id, media_id = create_audio(client, headers)
    monkeypatch.setattr("app.cry.routes.classify_audio", lambda _path: normalize_predictions(RAW))

    response = client.post(
        "/api/v1/cry-analyses",
        headers=headers,
        json={"baby_id": baby_id, "media_id": media_id},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "experimental"
    assert body["primary_category"] == "hungry"
    assert len(body["candidates"]) == 5
    assert [item["label"] for item in body["candidates"]] == [
        "饥饿", "身体不舒服", "困倦", "腹部不适", "需要拍嗝"
    ]


def test_cry_audio_is_private(auth):
    client = TestClient(app)
    headers = auth()
    _, media_id = create_audio(client, headers)

    response = client.get(f"/api/v1/media/{media_id}")

    assert response.status_code == 404


def test_expired_cry_audio_is_deleted(auth):
    client = TestClient(app)
    headers = auth()
    _, media_id = create_audio(client, headers)
    with SessionLocal() as db:
        media = db.get(MediaAsset, media_id)
        assert media is not None and media.is_private
        assert media.expires_at is not None
        media.expires_at = now() - timedelta(seconds=1)
        db.commit()

    assert purge_expired_cry_audio() == 1
    with SessionLocal() as db:
        assert db.get(MediaAsset, media_id) is None


def test_cry_endpoint_does_not_leak_other_family_audio(monkeypatch, auth):
    client = TestClient(app)
    baby_id, media_id = create_audio(client, auth("owner"))
    monkeypatch.setattr("app.cry.routes.classify_audio", lambda _path: normalize_predictions(RAW))

    response = client.post(
        "/api/v1/cry-analyses",
        headers=auth("other"),
        json={"baby_id": baby_id, "media_id": media_id},
    )

    assert response.status_code == 404


def test_cry_endpoint_reports_unavailable_model(monkeypatch, auth):
    client = TestClient(app)
    headers = auth()
    baby_id, media_id = create_audio(client, headers)

    def unavailable(_path):
        raise CryModelUnavailable("哭声模型尚未安装")

    monkeypatch.setattr("app.cry.routes.classify_audio", unavailable)
    response = client.post(
        "/api/v1/cry-analyses",
        headers=headers,
        json={"baby_id": baby_id, "media_id": media_id},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "cry_model_unavailable"


def test_pure_tone_is_rejected_before_models(tmp_path, monkeypatch):
    import numpy as np
    from app.cry.classifier import classify_audio
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        tone = np.sin(2 * np.pi * 440 * np.arange(32_000) / 16_000)
        audio.writeframes((tone * 10_000).astype("<i2").tobytes())
    monkeypatch.setattr("app.cry.classifier._pipeline", lambda: pytest.fail("must not classify a tone"))
    with pytest.raises(InvalidCryAudio, match="提示音"):
        classify_audio(path)


def test_non_cry_detection_is_required(monkeypatch):
    import numpy as np
    from app.cry.detector import ensure_cry, CRY_LABEL
    monkeypatch.setattr("app.cry.detector.detector_pipeline", lambda: lambda *a, **kw: [
        {"label": "Speech", "score": 0.9}, {"label": CRY_LABEL, "score": 0.01}])
    with pytest.raises(InvalidCryAudio, match="婴儿哭声"):
        ensure_cry(np.zeros(32_000, dtype=np.float32))


def test_detector_checks_later_windows(monkeypatch):
    import numpy as np
    from app.cry.detector import ensure_cry, CRY_LABEL
    results = iter([[{"label": "Music", "score": 0.9}], [{"label": CRY_LABEL, "score": 0.8}]])
    monkeypatch.setattr("app.cry.detector.detector_pipeline", lambda: lambda *a, **kw: next(results))
    ensure_cry(np.zeros(320_000, dtype=np.float32))


def test_invalid_model_scores_are_not_presented_as_certainty():
    with pytest.raises(CryModelUnavailable):
        normalize_predictions([{"label": "hungry", "score": float("nan")}])
