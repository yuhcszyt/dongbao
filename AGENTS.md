每次完成任务，commit and push 到github上

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
