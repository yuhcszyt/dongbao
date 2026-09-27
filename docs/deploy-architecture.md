# 懂宝部署架构

## 1. 部署目标

懂宝采用「腾讯云公网入口 + 家庭 Ubuntu 业务主机」：

- 微信小程序通过 HTTPS 访问后端
- 腾讯云只负责公网入口、HTTPS 和反向代理
- 懂宝业务服务实际运行在家庭 Ubuntu Server
- 腾讯云和家庭 Ubuntu 之间通过 Tailscale 私网通信
- PostgreSQL、Qdrant 等内部服务不暴露公网
- 架构简单，便于后续整体迁移到云服务器

## 2. 总体架构

```text
                         Internet
                            │
                            │ HTTPS 443
                            ▼
                  ┌──────────────────┐
                  │    腾讯云 VPS     │
                  │ Nginx + SSL      │
                  │ Tailscale        │
                  └────────┬─────────┘
                           │ Tailscale 私网
                           ▼
             ┌────────────────────────────┐
             │      家庭 Ubuntu Server    │
             │ Docker Compose             │
             │ FastAPI :8000              │
             │ PostgreSQL · Qdrant        │
             │ data/media · data/models   │
             └────────────────────────────┘
```

## 3. 请求链路

```text
微信小程序 → https://api.<域名>
         → 腾讯云 Nginx
         → http://<家庭-Tailscale-IP>:8000
         → FastAPI → PostgreSQL / Qdrant / ASR / LLM / Embedding / 本地哭声模型
```

微信小程序不直接访问家庭网络。

## 4. 腾讯云

职责：Nginx、HTTPS/SSL、Tailscale。不运行 FastAPI、PostgreSQL、Qdrant、哭声模型或业务数据。

公网建议只开放：`22`（SSH）、`80`（证书与跳转）、`443`（HTTPS）。

Nginx 将 `https://api.<域名>` 反代到家庭 Tailscale IP 的 `:8000`。配置示例见 [`deploy/nginx.edge.conf.example`](../deploy/nginx.edge.conf.example)。

## 5. 家庭业务服务器

物理：Windows 主机上的 Ubuntu Server VM（或不经过 Windows 的直装 Ubuntu）。

运行：Docker、Docker Compose、Tailscale，以及生产 compose 三容器：

- `server`（FastAPI，宿主机 `8000`）
- `postgres`（不暴露公网）
- `qdrant`（不暴露公网）

媒体与模型：`data/media`、`data/models`（宿主机目录挂载进容器）。当前阶段不引入 MinIO；哭声识别在 FastAPI 容器内加载本地模型。

## 6. 外部 AI 服务

| 能力 | 环境变量 / 配置 |
|---|---|
| LLM | `MODEL_API_KEY` + `config/providers.toml` |
| 腾讯云 ASR | `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY` |
| Embedding | `EMBEDDING_API_KEY` |
| Qdrant | `QDRANT_URL=http://qdrant:6333`（compose 内网） |

生产 `DEV_LOGIN` 必须为空。

## 7. 安全边界

- 公网：仅腾讯云 `443`（及证书用的 `80`）
- 私网：Tailscale → 家庭 `:8000`
- Docker 内网：`postgres:5432`、`qdrant:6333`

## 8. 从零部署顺序

1. 准备家庭 Ubuntu（Docker / Compose / Tailscale）
2. 腾讯云安装 Tailscale、Nginx
3. 域名 A 记录指向腾讯云公网 IP
4. 家庭 clone 仓库、配置 `.env`、准备模型、起 compose
5. 腾讯云确认经 Tailscale 可达 `:8000`，配置 Nginx + HTTPS
6. 微信公众平台配置合法域名并打体验版包

操作步骤见 [`deploy/README.md`](../deploy/README.md)。

## 9. 后续迁云

用户量增加时，可将 FastAPI / PostgreSQL / Qdrant（及对象存储）整体迁到云服务器；小程序仍访问同一 HTTPS 域名，应用接口保持不变。
