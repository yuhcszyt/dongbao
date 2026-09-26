import json
from uuid import uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app.ai.knowledge import import_documents, review_document, reindex_knowledge
from app.ai.models import RagDocument, RagChunk
from app.ai.tools import BabyScope
from app.ai.parenting_agent import finalize_answer
from app.ai.schemas import ParentingAnswer, SourceRef
from app.record.database import SessionLocal


def document_file(tmp_path, **changes):
    raw = {'id': str(uuid4()), 'title': '育儿来源', 'publisher': '公共卫生机构', 'source_url': 'https://example.org/guide', 'chunks': ['宝宝睡眠习惯与温和安抚']}
    raw.update(changes)
    path = tmp_path / 'knowledge.json'
    path.write_text(json.dumps([raw]), encoding='utf-8')
    return path, raw


def test_draft_approve_archive_and_reindex_preserve_documents(tmp_path):
    from uuid import UUID
    path, raw = document_file(tmp_path, review_status='approved')
    with SessionLocal() as db:
        assert import_documents(db, path) == 1
        doc = db.get(RagDocument, UUID(raw['id']))
        assert doc.review_status == 'draft'  # 文件不能自行批准。
        scope = BabyScope(db, uuid4(), uuid4())
        assert scope.search_parenting_knowledge('宝宝睡眠') == []
        review_document(db, doc.id, 'approved')
        assert scope.search_parenting_knowledge('宝宝睡眠')
        review_document(db, doc.id, 'archived')
        assert scope.search_parenting_knowledge('宝宝睡眠') == []  # 向量仍在，也不能检索。
        assert reindex_knowledge(db, reset=True) == 0
        assert db.get(RagDocument, doc.id).review_status == 'archived'
        assert db.scalar(select(RagChunk).where(RagChunk.document_id == doc.id))


def test_failed_index_cannot_publish_partial_document(tmp_path, monkeypatch):
    from app.ai import knowledge
    path, _ = document_file(tmp_path)
    with SessionLocal() as db:
        import_documents(db, path)
        doc = db.scalar(select(RagDocument))
        monkeypatch.setattr(knowledge, 'upsert_chunk', lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('offline')))
        with pytest.raises(RuntimeError):
            review_document(db, doc.id, 'approved')
        db.rollback()
        assert db.get(RagDocument, doc.id).review_status == 'draft'


def test_import_validation_and_duplicates_leave_existing_content(tmp_path):
    path, _ = document_file(tmp_path)
    with SessionLocal() as db:
        import_documents(db, path)
        with pytest.raises(ValueError):
            import_documents(db, path)
        invalid, _ = document_file(tmp_path, chunks=[' '])
        with pytest.raises(ValueError):
            import_documents(db, invalid)
        assert len(list(db.scalars(select(RagDocument)))) == 1


def test_retrieved_sources_use_database_and_reject_forgery(tmp_path, monkeypatch):
    from app.ai import tools
    path, _ = document_file(tmp_path)
    with SessionLocal() as db:
        import_documents(db, path)
        doc = db.scalar(select(RagDocument))
        review_document(db, doc.id, 'approved')
        chunk = db.scalar(select(RagChunk))
        monkeypatch.setattr(tools, 'search_approved', lambda *a, **kw: [SimpleNamespace(id=chunk.id, score=.9, payload={'content': '伪造内容'})])
        scope = BabyScope(db, uuid4(), uuid4())
        assert scope.search_parenting_knowledge('睡眠')[0]['content'] == chunk.content
        answer = ParentingAnswer(summary='回答', sources=[SourceRef(title='伪造标题', publisher='伪造发布者', chunk_id=chunk.id)])
        assert finalize_answer(scope, answer).sources[0].title == doc.title
        scope._last_sources = []
        assert finalize_answer(scope, answer).sources == []
