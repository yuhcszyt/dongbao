"""Phase 2：RAG tool + /ai/chat（无外网大模型时走降级路径）。"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.ai.qdrant_store import ensure_collection
from app.ai.seed import seed_knowledge
from app.ai.tools import BabyScope
from app.main import app
from app.record.database import SessionLocal


def _create_baby(client: TestClient, headers: dict) -> str:
    response = client.post("/api/v1/babies", headers=headers, json={"nickname": "小米粥", "birth_date": "2024-01-15", "gender": "unknown"})
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def test_rag_search_hits_seed_for_feeding_query(auth):
    ensure_collection()
    with SessionLocal() as db:
        written = seed_knowledge(db, force=True)
        assert written > 0
        # 需要一个 baby scope 才能调 tool（检索本身不依赖宝宝，但封装在 BabyScope）
        headers = auth()
        client = TestClient(app)
        baby_id = _create_baby(client, headers)
        from uuid import UUID
        from app.auth.models import User
        from sqlalchemy import select

        user = db.scalar(select(User).limit(1))
        scope = BabyScope(db, user.family_id, UUID(baby_id))
        hits = scope.search_parenting_knowledge("婴儿几个月开始添加辅食", top_k=5)
        assert hits, "辅食相关问题应命中 seed"
        assert any("辅食" in h["content"] or "6" in h["content"] for h in hits)
        assert scope._last_sources
        assert all(s.title for s in scope._last_sources)


def test_chat_without_model_returns_structured_answer(auth):
    headers = auth()
    client = TestClient(app)
    baby_id = _create_baby(client, headers)
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"baby_id": baby_id, "message": "辅食应该什么时候开始添加？"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conversation_id"]
    assert body["answer"]["summary"]
    assert "sources" in body["answer"]
    # 降级路径仍应尽量带上来自知识库的出处
    assert isinstance(body["answer"]["sources"], list)


def test_chat_cross_family_baby_404(auth):
    client = TestClient(app)
    headers_a = auth("openid-a")
    baby_a = _create_baby(client, headers_a)
    headers_b = auth("openid-b")
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers_b,
        json={"baby_id": baby_a, "message": "今天怎么样"},
    )
    assert response.status_code == 404


def test_chat_unknown_baby_404(auth):
    headers = auth()
    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"baby_id": str(uuid4()), "message": "你好"},
    )
    assert response.status_code == 404


def test_active_conversation_and_clear(auth):
    headers = auth()
    client = TestClient(app)
    baby_id = _create_baby(client, headers)
    first = client.post("/api/v1/ai/chat", headers=headers, json={"baby_id": baby_id, "message": "安全睡眠要注意什么"})
    assert first.status_code == 200
    conv_id = first.json()["conversation_id"]
    active = client.get(f"/api/v1/ai/conversations/active?baby_id={baby_id}", headers=headers)
    assert active.status_code == 200
    assert active.json()["conversation_id"] == conv_id
    assert len(active.json()["messages"]) >= 2
    cleared = client.post(f"/api/v1/ai/conversations/new?baby_id={baby_id}", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["conversation_id"] != conv_id
