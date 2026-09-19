Status: done
Type: spec
Scope: Phase 2 懂宝 AI（Qdrant RAG tool + 宝宝锚定会话 + 结构化回答 + 语音提问）
Refs: docs/design/02-ai.md、docs/backend-gap.md §1、计划 Phase2 AI RAG

# Phase 2：懂宝 AI Agent + Qdrant 工具化 RAG

## Problem

前端「懂宝 AI」仍是本地演示；服务端无对话、无向量检索、无专业出处。家长无法结合「这个宝宝」的记录与可引用的育儿知识提问。

## Solution

- Postgres：`rag_document` / `rag_chunk`（元数据）+ `ai_conversation` / `ai_message`
- Qdrant：`parenting_knowledge` 向量集合；合法 WHO/CDC 摘要 + 自建红旗 seed
- PydanticAI Agent；知识只经 tool `search_parenting_knowledge`
- `POST /api/v1/ai/chat`；豆包式单会话（一户一宝）；语音 → ASR → 同一 chat（不写 Draft）
- Embedding 配置占位；无 key 时用本地 hash embed + 预计算/即时 hash 向量做检索

## Tickets

01 scratch → 02 infra → 03 seed → 04 rag-tool → 05 chat-api → 06 client-text → 07 client-voice → 08 docs/adr
