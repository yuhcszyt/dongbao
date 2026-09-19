# ADR 0003：Phase 2 向量库选用 Qdrant

## Status

Accepted

## Context

产品文档（`00-dongbao-override.md` / `02-ai.md`）原写 PostgreSQL + pgvector，并写明 MVP 不引入独立向量库。
Phase 2 落地时产品决定使用独立向量库 **Qdrant**，与业务 Postgres 分离：元数据仍在 PG（`rag_documents` / `rag_chunks`），向量检索走 Qdrant collection `parenting_knowledge`。

## Decision

- 向量检索：Qdrant（compose 服务 `qdrant` / 测试 `qdrant-test`）
- 知识治理与会话：PostgreSQL
- Agent 侧仅通过 tool `search_parenting_knowledge` 访问知识库
- 无外部 embedding key 时使用本地 hash embed，与 seed 一致，便于 CI

## Consequences

- 本地/CI 需额外启动 Qdrant（`make qdrant-up`，`make test-server` 已串联）
- 与早期「仅 pgvector」文档不一致：以本 ADR 为准
- 运维多一个组件；换 embedding 模型时需重建 collection 向量
