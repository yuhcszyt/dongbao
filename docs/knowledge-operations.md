# 知识库与宝宝记忆管理

## 公共知识库

仅可信运维主机通过 CLI 操作；没有公开的管理接口。需要数据库环境变量、`APP_CONFIG`，审核发布/重建还需要配置向量模型和 Qdrant。配置方式沿用 `.env.example` 与 `config/providers.toml`。以下命令在 `apps/server` 下执行。

```bash
.venv/bin/python -m app.ai.knowledge import /absolute/path/documents.json
.venv/bin/python -m app.ai.knowledge list
.venv/bin/python -m app.ai.knowledge show 文档UUID
.venv/bin/python -m app.ai.knowledge approve 文档UUID
.venv/bin/python -m app.ai.knowledge archive 文档UUID
.venv/bin/python -m app.ai.knowledge reindex
```

导入文件是 JSON 数组，示例：

```json
[{
  "id": "d67a8932-cb98-4e8a-9775-4cd51d7249d2",
  "title": "资料标题",
  "source_url": "https://example.org/guide",
  "publisher": "原始发布机构",
  "published_at": "2026-09-26",
  "chunks": ["经过人工核对的原文片段"]
}]
```

- 导入始终为草稿，文件中的审核字段不产生批准效力。先 `show` 核对来源、日期、内容和适用范围，再 `approve`。
- 每篇最多 200 个片段，每片段最多 8000 字，一次最多 500 篇。只接受 HTTP(S) 来源地址。工具不抓取网页，也不自动保证来源权威性。
- 重复 ID 拒绝覆盖；修订用新 ID，批准新版后归档旧版。
- 批准时先索引再更新数据库状态，失败可重试；归档以数据库状态立即排除，遗留向量也不会作为答案来源。
- 更换向量模型或维度后显式执行 `reindex --reset`。它重建 Qdrant 集合，但保留数据库中的草稿、已审核文档和归档记录；重建期间公共检索可能暂时不完整，失败可重试。
- 生产不允许 `EMBEDDING_ALLOW_HASH=1`。它仅为测试提供伪向量，不具备语义能力。
- 发布和重建会调用配置的向量服务，可能计费；本次交付仅使用测试替身验证。

## 私有宝宝记忆

`BabyScope.save_baby_memory` 保存偏好/规律时尝试生成向量，失败仍保留文字。向量、模型指纹与内容指纹存于 Postgres `ai_memories`，不会混入公共 Qdrant。

搜索先限定 `family_id + baby_id`，再对最近 500 条当前模型且内容未变的向量计算相似度，返回最多 20 条。工具返回 `retrieval_mode`：`semantic`、`keyword`、`recent`；测试伪向量为 `test_vector`。未配置/服务失败则回退文字搜索；无结果不代表宝宝没有相关偏好。

旧记忆或更换向量模型后，可在可信运维主机显式补建：

```bash
.venv/bin/python -m app.ai.memory_search
```

补建逐条提交，跳过指纹未变的记忆，可中断后重试。它会将记忆文字发送给已配置的向量服务，执行前确认该服务与数据使用安排。单条记忆仍限制 500 字；业务事件应保留在记录模块中。
