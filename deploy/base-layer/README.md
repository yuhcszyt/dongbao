# 基础层：知识库 + 外部记忆

给所有 agent（Cursor / Codex / WorkBuddy / Hermes）共用的一套基础服务，跑在 2C2G 上。
这台机器**只做存储和检索，不做任何模型推理**——embedding 全部走 API。

```
Mac / Windows / 家庭机
        │  Tailscale（不出公网）
        ▼
┌─────────────────────────────────────┐
│  2C2G                               │
│  ├─ qdrant  :6333   向量存储         │
│  └─ kb-mcp  :8800   知识库 MCP 服务   │
└─────────────────────────────────────┘
        ▲
        │ 另一套 compose
     hindsight :8888   会话记忆（自动）
```

## 两个东西不是一回事

| | 知识库（本项目） | 外部记忆（hindsight） |
|---|---|---|
| 谁写 | agent 显式调用 `kb_add` | hook 自动抓会话 |
| 谁的活 | 文档、代码片段、踩坑结论 | 对话上下文、偏好 |
| 端口 | 8800 / 6333 | 8888 / 9999 |

## 部署

```bash
cd deploy/base-layer
cp .env.example .env      # 填 EMBEDDING_API_KEY（与 hindsight 同一个 tokenhub key）

# 本机验证（默认只绑 127.0.0.1）
docker compose up -d --build
docker compose exec kb-mcp python selfcheck.py

# 上服务器：先改 .env 里的 bind 为 Tailscale IP，再起
# QDRANT_BIND=100.x.x.x
# KB_BIND=100.x.x.x
```

`selfcheck.py` 会写入两条、检索、列表、再按项目删掉，只碰 `project=__selftest__`，跑完自动清理。

## 客户端配置

一个服务，多个客户端。**不要每端各起一份 stdio 进程**，那样每个客户端都要常驻一份模型和连接。

Cursor / WorkBuddy（`~/.cursor/mcp.json`、`~/.workbuddy/mcp.json`）：

```json
"kb": {
  "url": "http://<tailscale-ip>:8800/mcp"
}
```

Codex（`~/.codex/config.toml`）：

```toml
[mcp_servers.kb]
url = "http://<tailscale-ip>:8800/mcp"
```

Hermes（`~/.hermes/config.yaml`）：

```yaml
mcp_servers:
  kb:
    url: http://<tailscale-ip>:8800/mcp
    enabled: true
```

改完 Hermes 要 `launchctl kickstart -k gui/501/ai.hermes.gateway`。

## collection 怎么分

按**知识域**分，不按 agent 分——agent 会换，知识域不会。

| collection | 放什么 | 谁主要写 |
|---|---|---|
| `kb-docs` | 文档、决策记录、方案 | WorkBuddy / Hermes |
| `kb-code` | 代码片段、踩坑解法 | Cursor / Codex |
| `kb-ops` | 部署、排障、命令 | 所有人 |

同一个 collection 里用 payload 的 `project` 过滤（`kb_search(project="dongbao")`）。

## 坑

- **不要换 embedding 模型而不重建 collection**。维度变了会直接报错（0.6b 是 1024 维，4b 是 2560 维）。
- 服务端不做鉴权，安全性靠 Tailscale。**别把 6333 / 8800 绑到 0.0.0.0 公网 IP**。
- 备份：`qdrant` 用 snapshot API，`docker compose exec qdrant` 或用 cron 拉 `/collections/{name}/snapshots`，落到 COS/OSS，保留 7 天。
- 内存预算：qdrant ≤640M，kb-mcp ≤320M，加系统约 1.1G，2C2G 余量够。
