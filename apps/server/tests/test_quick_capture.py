from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.main import app
from app.record.database import SessionLocal
from app.record.models import BabyRecord, RecordDraft
from app.ai.models import AiMessage
from test_records import create_baby, wav_file

client = TestClient(app)


def upload(headers, baby, photo=False):
    file = ("p.png", b"\x89PNG\r\n\x1a\nplaceholder", "image/png") if photo else ("v.wav", wav_file(2), "audio/wav")
    response = client.post('/api/v1/media', headers=headers, data={"baby_id": baby}, files={"file": file})
    assert response.status_code == 201
    return response.json()['id']


def extracted(amount=120):
    return {"record_type": "feeding", "payload": {"kind": "feeding", "amount_ml": amount}, "missing_fields": [], "recognition_warnings": []}


@pytest.fixture
def providers(monkeypatch):
    async def transcribe(*args): return "刚才喝了奶"
    async def extract(**kwargs): return extracted()
    monkeypatch.setattr('app.record.capture.transcribe_audio', transcribe)
    monkeypatch.setattr('app.record.capture.extract_draft', extract)


def start(headers, baby, media, **extra):
    return client.post('/api/v1/record-drafts/capture', headers=headers, json={"baby_id": baby, "media_id": media, **extra})


def test_auto_save_atomic_history_and_concurrent_retry(auth, providers):
    headers = auth()
    baby = create_baby(headers)
    media = upload(headers, baby)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: start(headers, baby, media), range(2)))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    first, second = [r.json() for r in responses]
    assert first['state'] == 'saved'
    assert first['record']['id'] == second['record']['id']
    assert first['record']['transcript'] == '刚才喝了奶'
    history = client.get('/api/v1/ai/conversations/active', params={"baby_id": baby}, headers=headers).json()
    assert len(history['messages']) == 2
    assert history['messages'][0]['structured_payload']['media']['id'] == media
    assert history['messages'][1]['content'] == '已记录：喂奶 · 120 毫升'
    assert history['messages'][1]['structured_payload']['related_record_ids'] == [first['record']['id']]
    assert len(client.get(f'/api/v1/babies/{baby}/records', headers=headers).json()) == 1


@pytest.mark.parametrize('voice_reply', [False, True])
def test_followup_survives_reload_and_reuses_request(auth, providers, monkeypatch, voice_reply):
    headers = auth()
    baby = create_baby(headers)
    media = upload(headers, baby, photo=True)
    count = 0
    async def extract(**kwargs):
        nonlocal count
        count += 1
        return extracted(None if count == 1 else 150)
    monkeypatch.setattr('app.record.capture.extract_draft', extract)
    result = start(headers, baby, media).json()
    assert result['state'] == 'needs_input'
    assert result['question'] == '这次喝了多少毫升奶？'
    restored = client.get('/api/v1/record-drafts/pending', params={"baby_id": baby}, headers=headers).json()
    assert restored[0]['draft_id'] == result['draft_id']
    body = {"request_id": str(uuid4()), **({"media_id": upload(headers, baby)} if voice_reply else {"message": "150毫升"})}
    url = f"/api/v1/record-drafts/{result['draft_id']}/reply"
    saved = client.post(url, json=body, headers=headers)
    assert saved.status_code == 200, saved.text
    replay = client.post(url, json=body, headers=headers)
    assert saved.json()['record']['id'] == replay.json()['record']['id']
    assert count == 2
    history = client.get('/api/v1/ai/conversations/active', params={"baby_id": baby}, headers=headers).json()
    assert len(history['messages']) == 4
    assert client.get('/api/v1/record-drafts/pending', params={"baby_id": baby}, headers=headers).json() == []


def test_failure_rolls_back_then_retries_same_media(auth, providers, monkeypatch):
    headers = auth()
    baby = create_baby(headers)
    media = upload(headers, baby)
    async def unavailable(**kwargs): raise httpx.ConnectError('do not expose secret')
    monkeypatch.setattr('app.record.capture.extract_draft', unavailable)
    response = start(headers, baby, media)
    assert response.status_code == 503
    assert 'secret' not in response.text
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RecordDraft)) == 0
        assert db.scalar(select(func.count()).select_from(BabyRecord)) == 0
        assert db.scalar(select(func.count()).select_from(AiMessage)) == 0
    async def good(**kwargs): return extracted()
    monkeypatch.setattr('app.record.capture.extract_draft', good)
    assert start(headers, baby, media).json()['state'] == 'saved'


def test_transaction_failure_does_not_leave_record_without_message(auth, providers, monkeypatch):
    headers = auth()
    baby = create_baby(headers)
    media = upload(headers, baby)
    from app.record import capture
    def broken_summary(record): raise RuntimeError('simulate failure before history')
    monkeypatch.setattr(capture, 'summary_for', broken_summary)
    with TestClient(app, raise_server_exceptions=False) as failing:
        assert failing.post('/api/v1/record-drafts/capture', headers=headers, json={"baby_id": baby, "media_id": media}).status_code == 500
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BabyRecord)) == 0
        assert db.scalar(select(func.count()).select_from(AiMessage)) == 0


@pytest.mark.parametrize('model_output', [
    {"record_type": None},
    {"record_type": "sleep", "payload": {"kind": "sleep"}},
    {"record_type": "feeding", "payload": {"kind": "feeding", "amount_ml": 9000}},
    {"record_type": "feeding", "payload": {"kind": "feeding", "amount_ml": 120}, "recognition_warnings": ["看不清"]},
])
def test_uncertain_or_invalid_never_auto_saves(auth, providers, monkeypatch, model_output):
    headers = auth(); baby = create_baby(headers); media = upload(headers, baby)
    async def extract(**kwargs): return model_output
    monkeypatch.setattr('app.record.capture.extract_draft', extract)
    result = start(headers, baby, media)
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'needs_input'
    assert client.get(f'/api/v1/babies/{baby}/records', headers=headers).json() == []


def test_cancel_before_capture_and_after_save(auth, providers):
    headers = auth(); baby = create_baby(headers); media = upload(headers, baby)
    cancelled = client.post(f'/api/v1/record-drafts/capture/{media}/cancel', headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert start(headers, baby, media).json()['state'] == 'cancelled'
    other = upload(headers, baby)
    saved = start(headers, baby, other).json()
    late_cancel = client.post(f'/api/v1/record-drafts/capture/{other}/cancel', headers=headers).json()
    assert late_cancel['state'] == 'saved'
    assert late_cancel['record']['id'] == saved['record']['id']


def test_time_zone_and_cross_family_access(auth, providers, monkeypatch):
    headers = auth(); baby = create_baby(headers); media = upload(headers, baby)
    async def extract(**kwargs):
        assert 'Asia/Shanghai' in kwargs['content']
        return {**extracted(), 'occurred_at': '2026-09-21T20:30:00'}
    monkeypatch.setattr('app.record.capture.extract_draft', extract)
    assert start(headers, baby, media, timezone='invalid').status_code == 422
    result = start(headers, baby, media, timezone='Asia/Shanghai').json()
    stamp = datetime.fromisoformat(result['record']['occurred_at'])
    assert stamp.astimezone(timezone.utc).hour == 12
    outsider = auth('another-family')
    assert start(outsider, baby, media).status_code == 404
    assert client.post(f'/api/v1/record-drafts/capture/{media}/cancel', headers=outsider).status_code == 404
    assert client.post(f"/api/v1/record-drafts/{result['draft_id']}/reply", headers=outsider, json={"request_id": str(uuid4()), "message": '150'}).status_code == 404
