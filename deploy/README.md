# 懂宝 · 体验版上云（腾讯云 HTTPS）

目标：手机微信打开**体验版**小程序，语音/拍照打到公网 `https://api.<域名>/api/v1`。

## 你先买这两样

1. **轻量应用服务器**（推荐）
   - 镜像：Ubuntu 22.04 LTS
   - 规格：2 核 2G 起
   - 防火墙放行：22 / 80 / 443
2. **域名**（必须）
   - 解析：`api.<你的域名>` → 服务器公网 IP（A 记录）
   - 国内机器对外服务通常要 **ICP 备案**；未备案时微信合法域名可能配不上。按腾讯云提示备案（几天级）。

买完把下面发我（密码可私聊/打码）：
- 公网 IP
- SSH 用户（一般 `ubuntu` / `root`）
- 域名（例如 `example.com`，我们用 `api.example.com`）
- 备案是否已通过（或进行中）

## 机器上跑什么

本目录配合仓库根的 compose：

```bash
# 在服务器上 clone 本仓库后，于仓库根目录：
cp .env.example .env   # 填密钥；DEV_LOGIN 留空；JWT_SECRET 换强随机串
export DOMAIN=api.你的域名
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build
curl -fsS https://$DOMAIN/health
```

| 服务 | 作用 |
|---|---|
| `postgres` | 业务库 |
| `server` | FastAPI（容器内 8000，不对公网暴露） |
| `caddy` | 80/443，自动签 Let’s Encrypt，反代到 server |

## 微信侧（域名 HTTPS 通了之后）

1. [微信公众平台](https://mp.weixin.qq.com/) → 开发管理 → 开发设置 → **服务器域名**
   - request 合法域名：`https://api.<域名>`（不要带路径）
2. 本地打包：
   ```bash
   cd apps/client
   VITE_API_BASE_URL=https://api.<域名>/api/v1 npm run build:mp-weixin
   ```
3. 微信开发者工具打开 `apps/client/dist/build/mp-weixin` → **上传**
4. 公众平台 → 管理 → 版本管理 → 选开发版本 → **选为体验版**
5. 成员管理里把自己/测试号加成体验成员，扫体验版码

## 本机联调 vs 体验版

| | 本机 | 体验版 |
|---|---|---|
| API | 127.0.0.1 / 隧道 | `https://api.<域名>` |
| 合法域名 | 可勾「不校验」 | **必须**配置 |
| DEV_LOGIN | 仅 H5 可开 | **禁止** |
