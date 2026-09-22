# Phase 2 完成度清单（给人看）

> 更新日期：2026-09-20  
> 分支：`feat/record-phase1`（下列「本机已写完」的改动**尚未 commit / push**）

对照方式：✅ 代码与单测已有 · ⚠️ 要你本地配一下才真能用 · ❌ 没做 / 明确延后

---

## 1. 本机已写完（测过，未推远程）

| 项 | 状态 | 说明 |
|----|------|------|
| 文字聊天 + 结构化 `ParentingAnswer` | ✅ | `POST /api/v1/ai/chat` |
| 语音提问（ASR → 同一对话框，不写正式记录） | ✅ | 复用 Phase 1 草稿 ASR |
| 图片提问 | ✅ | 上传 media → `media_id`；DeepSeek vision；不自动建记录 |
| Qdrant RAG tool `search_parenting_knowledge` | ✅ | TokenHub embedding 2560 维；seed 约 16 条 |
| AI Memory（Postgres） | ✅ | `ai_memories` + `search/save_baby_memory` |
| `get_recent_sleep` / `get_growth_history` | ✅ | 仍用 `baby_records`，加了复合索引 |
| PydanticAI 重写 | ✅ | `pydantic-ai-slim`；入口 `agent.py`，编排 `parenting_agent.py` |
| Langfuse 观测代码 | ✅ | 无 key 时 no-op；不写原图/音频 |
| Compose 分 profile | ✅ | `test` / `obs` / `ci` / `weixin`；`make docker-ps` 等 |
| 服务端单测 | ✅ | 最近一次 `make test-server`：52 passed |
| 客户端 typecheck + vitest | ✅ | 46 passed |

---

## 2. 要你动手才算「真用上」（不是缺功能）

| 项 | 状态 | 你要做什么 |
|----|------|------------|
| Commit + push 本批改动 | ⚠️ | 改动还在工作区；要我推再说一声 |
| Langfuse 密钥 | ⚠️ | `make langfuse-up` → http://127.0.0.1:3100 创建 key → `.env` 的 `LANGFUSE_*` |
| 正式 Qdrant（`:6333`）向量 | ⚠️ | 测试库 `:6334` 已 seed；e2e/正式栈若空，把 `QDRANT_URL` 指过去再 `make seed-rag` |
| `MODEL_API_KEY` / `EMBEDDING_API_KEY` | ⚠️ | 没配也能聊（降级卡片）；完整回答和真向量检索需要 key |

---

## 3. 明确没做（Phase 2 外或刻意延后）

| 项 | 状态 | 备注 |
|----|------|------|
| 知识库管理后台 / 持续入库 CLI | ❌ | 现在靠 `data/rag/parenting_seed.json` + `make seed-rag` |
| 正版育儿书授权摘录 | ❌ | 现有 WHO/CDC 摘要 + 自建红旗，约 16 chunk |
| Memory 语义向量检索 | ❌ | 当前 Postgres `ILIKE`；产品原写 pgvector 语义，未上 |
| Phase 3 哭声识别 | ❌ | 页面在，后端未接 |
| Phase 4 推送 / 文章推荐 | ❌ | — |
| Phase 5 多家长 / 完整家庭权限 | ❌ | MVP 一户一用户 |
| Redis 会话缓存 | ❌ | 短期历史仍走 Postgres |

---

## 4. 模块怎么读（已落地）

```
apps/server/app/ai/
  agent.py            对外入口 run_parenting_agent
  parenting_agent.py  PydanticAI Agent + tools
  tools.py            BabyScope（档案/记录/RAG/记忆）
  fallback.py         无大模型降级
  prompt.py           系统指令
  observability.py    Langfuse
```

ADR：`docs/adr/0003-qdrant-for-rag.md`、`docs/adr/0004-pydantic-ai-agent.md`

---

## 5. 建议你优先看的「未完成」

若只关心「还差什么」：

1. **工程收尾**：commit / push（否则远程没有图片、Memory、PydanticAI、Langfuse）
2. **观测**：配 Langfuse key（可选）
3. **语料**：知识库后台 / 更多合法条目（产品增强，非阻塞聊天）
4. **下一阶段产品**：哭声 / 推送 / 多家长

不必再做：PydanticAI 重写、睡眠生长专用工具、图片提问、Memory 表（代码侧已齐）。
