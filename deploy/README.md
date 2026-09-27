# 懂宝 · 混合部署（腾讯云入口 + 家庭业务机）

微信小程序只访问公网 HTTPS；腾讯云做 Nginx / SSL / Tailscale；FastAPI、Postgres、Qdrant 跑在家庭 Ubuntu。

```text
微信 → https://api.xiaomizhoubaobao.cn → 腾讯云 Nginx
                                         ↓ Tailscale
                                   家庭 Ubuntu :8000
                                   (postgres + qdrant + server)
```

架构说明见 [`docs/deploy-architecture.md`](../docs/deploy-architecture.md)。

## 职责拆分

| 机器 | 跑什么 | 不跑什么 |
|---|---|---|
| 腾讯云 | Nginx、Let’s Encrypt、Tailscale | Docker、业务数据、模型 |
| 家庭 Ubuntu | Docker Compose：postgres / qdrant / server；`data/media`、`data/models` | 公网 80/443 |

生产只开放边缘 `22` / `80` / `443`。Postgres、Qdrant 不映射公网。

## 家庭业务机

```bash
# 仓库根目录
cp .env.example .env   # 填密钥；DEV_LOGIN 留空；JWT_SECRET 换强随机串
mkdir -p data/media data/models
# 哭声模型放到 data/models/babycry-v7 与 data/models/cry-detector
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build
curl -fsS http://127.0.0.1:8000/health
```

`QDRANT_URL` 在 compose 内默认 `http://qdrant:6333`。

## 腾讯云边缘

1. 安装 Tailscale，确认能访问家庭机：`curl -fsS http://100.71.108.114:8000/health`
2. 安装 Nginx + certbot
3. DNS：`api.xiaomizhoubaobao.cn` A → 腾讯云公网 IP
4. 参考 [`nginx.edge.conf.example`](nginx.edge.conf.example)，签发证书后启用 HTTPS
5. `curl -fsS https://api.xiaomizhoubaobao.cn/health`

## 微信侧（HTTPS 通之后）

1. [微信公众平台](https://mp.weixin.qq.com/) → 开发管理 → 开发设置 → **服务器域名**
   - request 合法域名：`https://api.xiaomizhoubaobao.cn`（不要带路径）
2. 本地打包：
   ```bash
   cd apps/client
   VITE_API_BASE_URL=https://api.xiaomizhoubaobao.cn/api/v1 npm run build:mp-weixin
   ```
3. 微信开发者工具打开 `apps/client/dist/build/mp-weixin` → **上传** → 选为体验版

国内机对外服务通常要 ICP 备案；未备案时微信合法域名可能配不上。

## 本机联调 vs 体验版

| | 本机 | 体验版 |
|---|---|---|
| API | 127.0.0.1 / 隧道 | `https://api.xiaomizhoubaobao.cn` |
| 合法域名 | 可勾「不校验」 | **必须**配置 |
| DEV_LOGIN | 仅 H5 可开 | **禁止** |
