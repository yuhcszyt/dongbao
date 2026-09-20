# Dongbao (懂宝)

家庭育儿记录应用：家长用微信小程序记录宝宝的喂养、睡眠、排便等日常，并随时回看当天情况。

## 技术栈

- **服务端** `apps/server/`：Python 3 + FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16
- **客户端** `apps/client/`：uni-app 3（Vue 3 + TypeScript），H5 与微信小程序（mp-weixin）
- **外部服务**：腾讯云语音识别（可选）、OpenAI 兼容大模型（可选，用于语音/照片生成记录草稿）

## 目录

```
apps/server/    FastAPI 服务端（app/ 领域模块、alembic/ 迁移、tests/ pytest）
apps/client/    uni-app 客户端（src/services/features/pages/components、vitest）
config/         providers.toml —— AI / ASR provider 配置
data/media/     媒体文件存储（gitignored）
docs/           产品原型与工程文档
.scratch/       票据与阶段性工作记录
```

## 环境准备

```bash
cp .env.example .env     # 填 DATABASE_URL / TENCENT_SECRET_ID / TENCENT_SECRET_KEY / MODEL_API_KEY
make setup               # 一次性：建 apps/server/.venv、装 python 与 npm 依赖
```

## 本地开发

### 微信小程序（上线路径，优先）

1. 在微信公众平台拿到小程序 `AppID` / `AppSecret`，写入根目录 `.env` 的 `WECHAT_APPID` / `WECHAT_SECRET`（**不要**开 `DEV_LOGIN`）。
2. 把同一 `AppID` 填进 `apps/client/src/manifest.json` → `mp-weixin.appid`，以及 `apps/client/project.config.json` 的 `appid`。
3. 起服务端与小程序构建：

```bash
make dev-server                 # 测试库 + alembic + uvicorn --reload --host 0.0.0.0（8001）；需已配微信凭证
cd apps/client && npm run dev:mp-weixin
```

4. 用微信开发者工具打开 `apps/client`（`miniprogramRoot` 指向 `dist/dev/mp-weixin/`），勾选「不校验合法域名」。
5. 小程序构建会写入电脑**局域网 IP**（`vite` 启动日志里有 `小程序 API → http://x.x.x.x:8001/api/v1`），不会用 localhost。真机与电脑同一 Wi-Fi，且保持「真机调试」为已连接。

### H5（仅联调，不代替小程序）

没有微信凭证时，显式开开发降级（`code` 直接当 openid，仅本地与 CI，生产禁止）：

```bash
DEV_LOGIN=1 make dev-server
cd apps/client && npm run dev:h5   # 5173
```

`make e2e` 会自动带 `DEV_LOGIN=1` 起整套 docker（H5 5173 / 服务端 8000）。

## 测试

测试一律在主机上跑（测试库是 docker 的 `postgres-test`，发布在主机 `55432`）：

```bash
make test         # 服务端 pytest + 客户端 typecheck/vitest
make test-server  # 仅服务端
make test-client  # 仅客户端
make build        # 客户端 h5 + mp-weixin 构建校验
make help         # 全部目标
```

不要为了跑测试而重建镜像（服务端镜像是 `COPY . .`，重建就是几十秒一轮）。容器只在两处用：`make e2e`（H5 人工验收）与 `make docker-test`（里程碑一致性检查）。

## 数据库迁移

```bash
cd apps/server
alembic revision --autogenerate -m "description"
alembic upgrade head
```
