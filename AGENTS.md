每次完成任务，commit and push 到github上

## 硬性约束：禁止控制本机验证前端界面

验证前端时**禁止以任何方式控制本机去看界面**，包括但不限于：

- 启动浏览器（Chrome / Safari / Playwright / Puppeteer 等）打开 H5 页面并截图
- 使用 AppleScript / `osascript` / `open` / `screencapture` / `cliclick` 等操控本机窗口或模拟点击
- 启动 `dev:h5` / `dev:mp-weixin` 开发服务器后去访问、截屏、录屏
- 打开微信开发者工具、IDE 预览面板或任何 GUI
- 任何“人眼式”验证（看渲染结果、对像素、看动画）

**前端验证只允许这些手段：**

1. 单元测试 — `cd apps/client && npm test`（Vitest）
2. 类型检查 — `cd apps/client && npm run typecheck`（vue-tsc）
3. 构建校验 — `cd apps/client && npm run build:h5`（构建失败即视为错误）
4. 代码级审查 — 读源码、追踪组件树 / props / 响应式依赖 / 条件渲染分支，确认逻辑正确

如需人工目视确认，**停下来向用户说明需要人工确认的点**，由用户自己去操作和查看，不要代为控制本机。

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

### Running with Docker (recommended)

```bash
# Start server + client + postgres
docker compose up

# Run tests (server + client)
docker compose --profile tools run --rm server-test
docker compose --profile tools run --rm client-test

# Build client
docker compose --profile tools run --rm client-build
```

### Server (local)

```bash
cd apps/server
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Client (local)

```bash
cd apps/client
npm install
npm run dev:h5        # H5 dev server (localhost:5173)
npm run dev:mp-weixin  # WeChat Mini Program dev
```

### Testing

```bash
# Server tests
cd apps/server && pytest

# Client tests
cd apps/client && npm test

# Client typecheck
cd apps/client && npm run typecheck
```

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
