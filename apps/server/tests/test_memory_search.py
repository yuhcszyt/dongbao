from uuid import UUID
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.auth.models import User
from app.ai.models import AiMemory
from app.ai.tools import BabyScope
from app.ai import memory_search as memory
from app.ai.embedding import EmbeddingUnavailable
from app.record.database import SessionLocal


def scope_for(db, auth, code):
    headers = auth(code)
    response = TestClient(app).post('/api/v1/babies', headers=headers, json={'nickname': code})
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.openid == code))
    return BabyScope(db, user.family_id, UUID(response.json()['id']))


def test_semantic_synonyms_and_family_scope(auth, monkeypatch):
    monkeypatch.setattr(memory, 'embed_texts', lambda texts: [[1., 0.] if '入睡' in text else [0., 1.] for text in texts])
    monkeypatch.setattr(memory, 'embed_query', lambda query: [1., 0.])
    monkeypatch.setattr(memory, 'embedding_configured', lambda: True)
    with SessionLocal() as db:
        a = scope_for(db, auth, 'parent-a')
        b = scope_for(db, auth, 'parent-b')
        saved = a.save_baby_memory('晚上八点入睡')
        a.save_baby_memory('喜欢喝温奶')
        b.save_baby_memory('另一个家庭九点入睡')
        db.commit()
        hits = a.search_baby_memory('夜间休息习惯')
        assert [h['id'] for h in hits] == [saved['id']]
        assert hits[0]['retrieval_mode'] == 'semantic'
        wrong = BabyScope(db, b.family_id, a.baby_id)
        import pytest
        with pytest.raises(ValueError):
            wrong.search_baby_memory('睡眠')


def test_failure_falls_back_and_model_change_excludes_stale_vectors(auth, monkeypatch):
    monkeypatch.setattr(memory, 'embed_texts', lambda texts: [[1., 0.] for _ in texts])
    monkeypatch.setattr(memory, 'embed_query', lambda query: [1., 0.])
    with SessionLocal() as db:
        scope = scope_for(db, auth, 'parent')
        saved = scope.save_baby_memory('晚上入睡需要安抚')
        db.commit()
        monkeypatch.setattr(memory, 'model_key', lambda: 'changed-model')
        assert scope.search_baby_memory('休息习惯') == []
        monkeypatch.setattr(memory, 'embed_query', lambda query: (_ for _ in ()).throw(EmbeddingUnavailable('offline')))
        hits = scope.search_baby_memory('入睡')
        assert hits[0]['retrieval_mode'] == 'keyword'
        assert scope.search_baby_memory('%') == []
        assert scope.search_baby_memory('', limit=0)[0]['retrieval_mode'] == 'recent'
        monkeypatch.setattr(memory, 'embed_texts', lambda texts: (_ for _ in ()).throw(EmbeddingUnavailable('offline')))
        assert scope.save_baby_memory('无向量时仍可保存')['id']
        assert db.get(AiMemory, UUID(saved['id'])).embedding


def test_reindex_old_memories_and_skip_unchanged(auth, monkeypatch):
    monkeypatch.setattr(memory, 'embed_texts', lambda texts: [[1., 0.] for _ in texts])
    with SessionLocal() as db:
        scope = scope_for(db, auth, 'parent')
        row = AiMemory(family_id=scope.family_id, baby_id=scope.baby_id, content='白天小睡规律')
        db.add(row)
        db.commit()
        assert memory.reindex_memories(db) == 1
        assert memory.reindex_memories(db) == 0
        row.content = '规律已变化'
        db.commit()
        assert memory.reindex_memories(db) == 1
