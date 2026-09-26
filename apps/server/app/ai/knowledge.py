"""运维知识库管理：Postgres 是审核状态与原文的唯一权威来源。"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from .embedding import embed_texts
from .models import RagChunk, RagDocument
from .qdrant_store import ensure_collection, upsert_chunk, wipe_collection


class DocumentInput(BaseModel):
    id: UUID
    title: str = Field(min_length=1, max_length=255)
    source_url: HttpUrl
    publisher: str = Field(min_length=1, max_length=128)
    published_at: date | None = None
    chunks: list[str] = Field(min_length=1, max_length=200)


def import_documents(db: Session, path: Path) -> int:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not 1 <= len(raw) <= 500:
        raise ValueError("文件必须包含 1 至 500 篇文档")
    docs = [DocumentInput.model_validate(item) for item in raw]
    ids = [doc.id for doc in docs]
    if len(set(ids)) != len(ids):
        raise ValueError("文件包含重复文档 ID")
    for doc in docs:
        if not doc.title.strip() or not doc.publisher.strip() or len(str(doc.source_url)) > 512:
            raise ValueError("标题、发布者和来源链接不符合要求")
        if any(not text.strip() or len(text) > 8000 for text in doc.chunks):
            raise ValueError("每个知识片段必须包含 1 至 8000 字")
        if db.get(RagDocument, doc.id):
            raise ValueError(f"文档 {doc.id} 已存在；修订请使用新 ID 并归档旧版")
    for doc in docs:
        db.add(RagDocument(id=doc.id, title=doc.title.strip(), publisher=doc.publisher.strip(), source_url=str(doc.source_url), published_at=doc.published_at, review_status="draft"))
        db.flush()
        db.add_all([RagChunk(document_id=doc.id, content=text.strip(), chunk_index=i) for i, text in enumerate(doc.chunks)])
    db.commit()
    return len(docs)


def index_document(db: Session, doc: RagDocument) -> int:
    chunks = list(db.scalars(select(RagChunk).where(RagChunk.document_id == doc.id).order_by(RagChunk.chunk_index)))
    if not chunks:
        raise ValueError("文档没有知识片段")
    vectors = embed_texts([chunk.content for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("向量服务返回的片段数量不一致")
    ensure_collection()
    for chunk, vector in zip(chunks, vectors):
        upsert_chunk(chunk.id, vector, document_id=doc.id, chunk_index=chunk.chunk_index,
                     content=chunk.content, title=doc.title, source_url=doc.source_url,
                     publisher=doc.publisher, published_at=doc.published_at.isoformat() if doc.published_at else None,
                     review_status="approved")
    return len(chunks)


def review_document(db: Session, document_id: UUID, status: str) -> None:
    if status not in ("approved", "archived"):
        raise ValueError("仅支持 approved 或 archived")
    doc = db.scalar(select(RagDocument).where(RagDocument.id == document_id).with_for_update())
    if not doc:
        raise ValueError("文档不存在")
    if status == "approved":
        # 先索引，再批准；索引部分失败时，数据库仍为草稿，检索不会泄漏。
        index_document(db, doc)
    doc.review_status = status
    db.commit()
    # 归档即时由数据库过滤生效；重建索引时清除遗留向量。


def reindex_knowledge(db: Session, *, reset: bool = False) -> int:
    if reset:
        wipe_collection()
    ensure_collection()
    docs = db.scalars(select(RagDocument).where(RagDocument.review_status == "approved").order_by(RagDocument.id))
    return sum(index_document(db, doc) for doc in docs)


def main():
    parser = argparse.ArgumentParser(description="知识库管理（仅可信运维主机执行）")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    command = commands.add_parser("import")
    command.add_argument("path", type=Path)
    for name in ("approve", "archive", "show"):
        command = commands.add_parser(name)
        command.add_argument("id", type=UUID)
    command = commands.add_parser("reindex")
    command.add_argument("--reset", action="store_true", help="明确重建 Qdrant 集合；保留全部数据库文档")
    args = parser.parse_args()
    from ..record.database import SessionLocal
    with SessionLocal() as db:
        if args.command == "import":
            print(f"已导入 {import_documents(db, args.path)} 篇草稿，请审核来源和内容后 approve")
        elif args.command in ("approve", "archive"):
            review_document(db, args.id, "approved" if args.command == "approve" else "archived")
            print("审核状态已更新")
        elif args.command == "reindex":
            print(f"已重建 {reindex_knowledge(db, reset=args.reset)} 个片段索引")
        else:
            stmt = select(RagDocument).order_by(RagDocument.created_at)
            if args.command == "show":
                stmt = stmt.where(RagDocument.id == args.id)
            for doc in db.scalars(stmt):
                output = {"id": str(doc.id), "title": doc.title, "publisher": doc.publisher, "source_url": doc.source_url, "status": doc.review_status}
                if args.command == "show":
                    output["chunks"] = list(db.scalars(select(RagChunk.content).where(RagChunk.document_id == doc.id).order_by(RagChunk.chunk_index)))
                print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
