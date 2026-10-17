"""知识库 MCP server —— 一个服务，给所有 agent 共用。

存储用 Qdrant，embedding 走 OpenAI 兼容接口（默认腾讯 tokenhub）。
设计取舍见同目录 README.md：
- collection 按知识域分（kb-docs / kb-code / kb-ops），不按 agent 分
- 只做 store / search / delete / list / ingest，不做会话记忆（那是 hindsight 的事）
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import pathlib
import sys
import uuid

import httpx
from mcp.server.mcpserver import MCPServer
from qdrant_client import QdrantClient, models

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("kb-mcp")

QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://tokenhub.tencentmaas.com/v1").rstrip("/")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "kinfra-text-embedding-0.6b")
EMBEDDING_TIMEOUT = float(os.getenv("EMBEDDING_TIMEOUT", "30"))

DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "kb-docs")
ALLOWED_COLLECTIONS = [
    c.strip() for c in os.getenv("ALLOWED_COLLECTIONS", "kb-docs,kb-code,kb-ops").split(",") if c.strip()
]
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "1000"))
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))

mcp = MCPServer("dongbao-kb")
KB_HOST = os.getenv("KB_HOST", "0.0.0.0")
KB_PORT = int(os.getenv("KB_PORT", "8800"))
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30)

_dim_cache: dict[str, int] = {}


class KBError(RuntimeError):
    """给 agent 看的可读错误。"""


def _embed(texts: list[str]) -> list[list[float]]:
    if not EMBEDDING_API_KEY:
        raise KBError("EMBEDDING_API_KEY 未设置，知识库无法生成向量")
    out: list[list[float]] = []
    with httpx.Client(timeout=EMBEDDING_TIMEOUT) as http:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            resp = http.post(
                f"{EMBEDDING_BASE_URL}/embeddings",
                headers={"Authorization": f"Bearer {EMBEDDING_API_KEY}"},
                json={"model": EMBEDDING_MODEL, "input": batch},
            )
            if resp.status_code >= 400:
                raise KBError(f"embedding 调用失败 {resp.status_code}: {resp.text[:300]}")
            payload = resp.json()
            rows = sorted(payload["data"], key=lambda d: d.get("index", 0))
            out.extend([row["embedding"] for row in rows])
    return out


def _ensure_collection(name: str, dim: int) -> None:
    if not qdrant.collection_exists(name):
        qdrant.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
        for field in ("project", "source", "tags"):
            qdrant.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        log.info("created collection %s dim=%s", name, dim)
        return
    info = qdrant.get_collection(name)
    existing = info.config.params.vectors.size
    if existing != dim:
        raise KBError(
            f"collection {name} 维度是 {existing}，当前模型 {EMBEDDING_MODEL} 输出 {dim}。"
            "换模型必须新建 collection 或清空重建。"
        )


def _check_collection(name: str | None) -> str:
    target = name or DEFAULT_COLLECTION
    if target not in ALLOWED_COLLECTIONS:
        raise KBError(f"collection {target} 不在白名单 {ALLOWED_COLLECTIONS} 内")
    return target


def _split(text: str, limit: int) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(para[i : i + limit] for i in range(0, len(para), limit))
            continue
        if len(buf) + len(para) + 2 > limit:
            chunks.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        chunks.append(buf)
    return chunks


def _filter(project: str | None, source: str | None, tags: list[str] | None) -> models.Filter | None:
    must: list[models.Condition] = []
    if project:
        must.append(models.FieldCondition(key="project", match=models.MatchValue(value=project)))
    if source:
        must.append(models.FieldCondition(key="source", match=models.MatchValue(value=source)))
    if tags:
        must.append(models.FieldCondition(key="tags", match=models.MatchAny(any=tags)))
    return models.Filter(must=must) if must else None


def _point_ids(collection: str, project: str) -> list[str]:
    ids: list[str] = []
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            scroll_filter=_filter(project, None, None),
            limit=256,
            offset=offset,
            with_payload=False,
        )
        ids.extend(str(p.id) for p in points)
        if offset is None:
            return ids


@mcp.tool()
def kb_add(
    text: str,
    title: str = "",
    collection: str = "",
    project: str = "",
    tags: list[str] | None = None,
    source: str = "manual",
) -> str:
    """把一段知识存进知识库。

    text 是要记的内容（文档片段、代码、踩坑结论，越自洽越好）；
    title 是一句话标题，方便之后人工辨认；
    collection 默认 kb-docs，代码片段用 kb-code，部署排障用 kb-ops；
    project 填项目名（如 dongbao），之后可按项目过滤检索；
    tags 是自由标签；source 标注来源（cursor / codex / workbuddy / 手工）。
    超过 1000 字的文本会自动切成多个片段存储。
    """
    name = _check_collection(collection or None)
    chunks = _split(text, CHUNK_CHARS)
    if not chunks:
        raise KBError("text 为空，没有可存的内容")
    vectors = _embed(chunks)
    _ensure_collection(name, len(vectors[0]))

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    points = []
    ids = []
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        pid = str(uuid.uuid4())
        ids.append(pid)
        points.append(
            models.PointStruct(
                id=pid,
                vector=vector,
                payload={
                    "text": chunk,
                    "title": title,
                    "project": project,
                    "tags": tags or [],
                    "source": source,
                    "created_at": now,
                    "chunk_index": idx,
                },
            )
        )
    qdrant.upsert(collection_name=name, points=points, wait=True)
    log.info("kb_add collection=%s chunks=%d project=%s", name, len(points), project)
    return f"已存入 {name}：{len(points)} 个片段，ids={ids}"


@mcp.tool()
def kb_search(
    query: str,
    collection: str = "",
    project: str = "",
    tags: list[str] | None = None,
    limit: int = 5,
) -> str:
    """按语义检索知识库，返回最相关的若干片段。

    query 用自然语言描述你要找什么（不是关键词也行）；
    project 可按项目过滤，tags 可按标签过滤（任一命中）；
    返回内容含标题、来源、得分和正文，可直接引用。
    """
    name = _check_collection(collection or None)
    if not qdrant.collection_exists(name):
        return f"{name} 还没有任何内容"
    vector = _embed([query])[0]
    _ensure_collection(name, len(vector))
    result = qdrant.query_points(
        collection_name=name,
        query=vector,
        limit=max(1, min(limit, 20)),
        query_filter=_filter(project or None, None, tags),
        with_payload=True,
    )
    if not result.points:
        return "没有匹配结果"
    blocks = []
    for rank, point in enumerate(result.points, 1):
        p = point.payload or {}
        head = f"[{rank}] score={point.score:.3f} title={p.get('title') or '(无标题)'}"
        meta = f"    project={p.get('project') or '-'} source={p.get('source') or '-'} id={point.id}"
        blocks.append(f"{head}\n{meta}\n{p.get('text', '')}")
    return "\n\n".join(blocks)


@mcp.tool()
def kb_list(collection: str = "", project: str = "", limit: int = 20) -> str:
    """列出知识库里最近的条目（只返回标题和元信息，不含正文）。"""
    name = _check_collection(collection or None)
    if not qdrant.collection_exists(name):
        return f"{name} 还没有任何内容"
    points, _ = qdrant.scroll(
        collection_name=name,
        scroll_filter=_filter(project or None, None, None),
        limit=max(1, min(limit, 100)),
        with_payload=True,
    )
    if not points:
        return "没有条目"
    lines = []
    for p in points:
        payload = p.payload or {}
        title = payload.get("title") or (payload.get("text", "")[:40])
        lines.append(f"- {title} | project={payload.get('project') or '-'} | id={p.id}")
    return "\n".join(lines)


@mcp.tool()
def kb_delete(point_id: str = "", collection: str = "", project: str = "") -> str:
    """删除知识库条目。必须给出 point_id，或给出 project 批量删除该项目全部条目。

    两个都不给时拒绝执行，避免误清空整个 collection。
    """
    name = _check_collection(collection or None)
    if not qdrant.collection_exists(name):
        return f"{name} 不存在"
    if point_id:
        qdrant.delete(collection_name=name, points_selector=models.PointIdsList(points=[point_id]), wait=True)
        return f"已删除 {point_id}"
    if project:
        ids = _point_ids(name, project)
        if not ids:
            return f"{name} 里没有 project={project} 的条目"
        qdrant.delete(collection_name=name, points_selector=models.PointIdsList(points=ids), wait=True)
        return f"已删除 project={project} 的 {len(ids)} 条"
    raise KBError("必须提供 point_id 或 project，拒绝清空整个 collection")


@mcp.tool()
def kb_ingest(
    path: str,
    collection: str = "kb-docs",
    project: str = "",
    glob: str = "**/*.md",
    limit: int = 200,
) -> str:
    """把服务器本地的一个目录批量导入知识库（按文件切成片段）。

    path 是容器内可见的绝对路径，glob 默认只收 markdown；
    project 建议填项目名，方便以后按项目检索或整体删除。
    """
    name = _check_collection(collection)
    root = pathlib.Path(path)
    if not root.exists():
        raise KBError(f"路径不存在：{path}")
    files = [p for p in sorted(root.glob(glob)) if p.is_file()][:limit]
    if not files:
        raise KBError(f"{path} 下没有匹配 {glob} 的文件")
    total = 0
    for file in files:
        try:
            body = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            log.warning("skip non-utf8 file %s", file)
            continue
        rel = str(file.relative_to(root))
        chunks = _split(body, CHUNK_CHARS)
        if not chunks:
            continue
        vectors = _embed(chunks)
        _ensure_collection(name, len(vectors[0]))
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "text": chunk,
                    "title": rel,
                    "project": project,
                    "tags": [],
                    "source": "ingest",
                    "created_at": now,
                    "chunk_index": idx,
                },
            )
            for idx, (chunk, vec) in enumerate(zip(chunks, vectors))
        ]
        qdrant.upsert(collection_name=name, points=points, wait=True)
        total += len(points)
    return f"已导入 {len(files)} 个文件，共 {total} 个片段到 {name}"


def main() -> None:
    transport = os.getenv("KB_TRANSPORT", "streamable-http")
    if "--stdio" in sys.argv:
        transport = "stdio"
    log.info(
        "kb-mcp starting transport=%s qdrant=%s model=%s collections=%s",
        transport,
        QDRANT_URL,
        EMBEDDING_MODEL,
        ALLOWED_COLLECTIONS,
    )
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=transport, host=KB_HOST, port=KB_PORT)


if __name__ == "__main__":
    main()
