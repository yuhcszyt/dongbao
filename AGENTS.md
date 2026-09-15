每次完成任务，commit and push 到github上

## 硬性约束：禁止控制本机验证前端界面

验证前端时**禁止以任何方式控制本机去看界面**，包括但不限于：

- 启动浏览器（Chrome / Safari / Playwright / Puppeteer 等）打开 H5 页面并截图
- 使用 AppleScript / `osascript` / `open` / `screencapture` / `cliclick` 等操控本机窗口或模拟点击
- 启动 `dev:h5` / `dev:mp-weixin` 开发服务器后去访问、截屏、录屏
- 打开微信开发者工具、IDE 预览面板或任何 GUI
- 任何“人眼式”验证（看渲染结果、对像素、看动画）

**前端验证只允许这些手段：**

1. 单元测试 — `make test-client`（内部是 `npm run typecheck && npm test`，Vitest）
2. 类型检查 — `cd apps/client && npm run typecheck`（vue-tsc）
3. 构建校验 — `cd apps/client && npm run build:h5`（构建失败即视为错误）
4. 代码级审查 — 读源码、追踪组件树 / props / 响应式依赖 / 条件渲染分支，确认逻辑正确

如需人工目视确认，**停下来向用户说明需要人工确认的点**，由用户自己去操作和查看，不要代为控制本机。

## 硬性约束：测试在本地跑，不要为了测试重建 docker 镜像

验证代码一律走主机上的本地闭环：

```bash
make test                                            # 服务端 pytest + 客户端 typecheck/vitest
docker compose --profile tools up -d postgres-test   # 唯一需要的容器（主机 55432）
```

- 日常开发、调试、改 bug、跑单测，**都在主机上跑**，用 `Makefile` 里的目标（`make help` 看全）。
- **禁止**为了跑一遍测试而 `docker compose build` / `run --rm ... --build` / `up --build`：服务端镜像是 `COPY . .`，重建就是几十秒到几分钟一轮。
- 容器只在两处用：`make e2e`（端到端人工验收）与里程碑结束时的 `make docker-test`（容器一致性检查）。
- 依赖安装是一次性动作（`make setup`）：服务端进 `apps/server/.venv`，客户端进 `apps/client/node_modules`。缺依赖就补装，不要退回去用容器跑测试。

## Project Overview

Dongbao (懂宝) is a family-oriented application with a Python/FastAPI backend and a uni-app (Vue 3) frontend targeting both H5 and WeChat Mini Program.

## Tech Stack

**Server** (`apps/server/`):
- Python 3 + FastAPI + Uvicorn
- SQLAlchemy 2.0 + Alembic (migrations)
- PostgreSQL 16 (via psycopg3)
- Pydantic 2
- Tencent Cloud integration (TENCENT_SECRET_ID / TENCENT_SECRET_KEY)
- AI model integration (MODEL_API_KEY)

**Client** (`apps/client/`):
- uni-app 3.0 (Vue 3.5)
- Targets: H5 + WeChat Mini Program (mp-weixin)
- Vite 5 + TypeScript 5.7
- Vitest (unit tests) + vue-tsc (typecheck)

## Project Structure

```
├── apps/
│   ├── server/           # FastAPI backend
│   │   ├── app/
│   │   │   ├── ai/       # AI integration module
│   │   │   ├── cry/      # Cry/emotion recording module
│   │   │   ├── family/   # Family management module
│   │   │   ├── info/     # Info module
│   │   │   ├── notification/  # Notification module
│   │   │   └── record/   # Business record module (baby profiles, daily records, media, AI draft)
│   │   ├── alembic/      # DB migrations
│   │   ├── tests/        # pytest tests
│   │   └── Dockerfile
│   └── client/           # uni-app frontend
│       ├── src/
│       │   ├── pages/
│       │   ├── components/
│       │   ├── features/
│       │   └── services/
│       └── Dockerfile
├── config/
│   └── providers.toml    # AI provider config
├── data/
│   └── media/            # Media storage (gitignored except .gitkeep)
├── docker-compose.yml    # Full stack orchestration
└── docs/
    └── agents/           # Agent skill configuration
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Client (uni-app)                    │
│  Vue 3 + TypeScript · H5 / WeChat Mini Program           │
│  pages → components → services/api → features/domain     │
└──────────────────────────┬──────────────────────────────┘
                           │ REST /api/v1
┌──────────────────────────▼──────────────────────────────┐
│                   Server (FastAPI)                       │
│  main.py → providers.py → schemas.py → models.py → DB    │
│  Domain modules: record · ai · cry · family · info ·    │
│  notification                                            │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              PostgreSQL 16 + External Services            │
│  Tencent ASR · Large Model (OpenAI-compatible)           │
└─────────────────────────────────────────────────────────┘
```

**Product design:** `docs/prooduct/dongbao-prototype-v1.2.html`

## Development

### Environment Setup

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

Key variables: `DATABASE_URL`, `TENCENT_SECRET_ID`, `TENCENT_SECRET_KEY`, `MODEL_API_KEY`.

### 本地快速验证（默认路径）

日常开发与测试都在主机上跑，不要为了验证而重建镜像。见下方《Testing》。

### 只用于端到端验收的 Docker

`docker compose up` 启动 server + client + postgres，用于人工验收（以及里程碑时的容器一致性检查）。它**不是**日常测试手段。

```bash
make e2e          # 等价于 docker compose up --build
docker compose --profile tools run --rm client-build
```

### Server (local)

```bash
make dev-server   # 起测试库 + alembic upgrade head + uvicorn --reload（端口 8001）
```

手动等价写法（测试库端口 55432）：

```bash
cd apps/server
alembic upgrade head
DATABASE_URL=postgresql+psycopg://dongbao:change-me@localhost:55432/dongbao_test uvicorn app.main:app --reload --port 8000
```

### Client (local)

```bash
cd apps/client
npm install
npm run dev:h5        # H5 dev server (localhost:5173)
npm run dev:mp-weixin  # WeChat Mini Program dev
```

### Testing

默认在**主机上跑**，不要为了跑测试而重建 docker 镜像：

```bash
make setup        # 一次性：建 apps/server/.venv、装 python 与 npm 依赖
make test         # 服务端 pytest + 客户端 typecheck/vitest（自动起测试库）
make test-server  # 仅服务端
make test-client  # 仅客户端
make build        # 客户端 h5 + mp-weixin 构建校验
make help         # 全部目标
```

本地闭环的构成：

- 测试库是 `docker compose` 的 `postgres-test`（`tools` profile，tmpfs，跑了就丢），端口发布到主机 `55432`；
- 服务端用 `apps/server/.venv`（已 gitignore）在主机跑 `alembic upgrade head && pytest`；
- 客户端用主机 `node_modules` 跑 `vue-tsc` / `vitest` / `uni build`。

**只有当以下两种情况才用容器**，避免每改一行就重建镜像：

```bash
make e2e          # docker compose up --build，端到端人工验收
make docker-test  # 里程碑一致性：容器内带 --build 跑一遍全部测试
```

### Docker (端到端验收)

```bash
make e2e   # 等价于 docker compose up --build
```

H5 在 5173，服务端在 8000。

### 前端验证（受限）

见上文《硬性约束：禁止控制本机验证前端界面》。Agent 只能通过 `npm test` / `npm run typecheck` / `npm run build:h5` 和代码级审查验证前端；一律不得启动浏览器、开发服务器或截图来“看界面”。

## Database Migrations

Migrations live in `apps/server/alembic/`. After model changes:

```bash
cd apps/server
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature>/` in this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (one `CONTEXT.md` + `docs/adr/` at the repo root). See `docs/agents/domain.md`.
