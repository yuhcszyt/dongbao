# ADR 0003：Phase 2 向量库选用 Qdrant

## Status

Accepted（修订：禁用生产 hash embedding）

## Context

产品文档原写 PostgreSQL + pgvector。Phase 2 选用独立向量库 **Qdrant**。
初版曾用本地 hash 伪向量方便 CI，但**不能**作为专业 RAG 的检索质量基础。

## Decision

- 向量检索：Qdrant collection `parenting_knowledge`
- 向量化：腾讯云 TokenHub OpenAI-compatible `/embeddings`（默认 `kinfra-text-embedding-4b`，**2560 维**）
  - 国内 endpoint：`https://tokenhub.tencentmaas.com/v1`
  - 文档：[TokenHub 向量模型](https://cloud.tencent.com/document/product/1823/133515)
- 环境变量：`EMBEDDING_API_KEY`（TokenHub API Key；**不可**用 DeepSeek `MODEL_API_KEY`）
- 未配置 embedding 时：RAG tool 返回明确错误，**不**静默 hash
- 仅 CI：`EMBEDDING_ALLOW_HASH=1` 允许伪向量跑通单测
- 换模型/维度后：`make seed-rag` 重建

## Consequences

- 本地/部署必须配置 embedding 供应商才能得到可靠专业来源
- DeepSeek 只负责聊天；向量是另一条链路
- 与「仅 pgvector / 本地凑合向量」文档不一致：以本 ADR 为准
