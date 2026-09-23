# 本地快速验证：日常迭代不碰 docker，只有 e2e 人工验收与里程碑一致性检查才起全栈。
# Compose profiles：test（测库）/ obs（Langfuse）/ ci（容器内测）/ weixin（可选）。
# 用法见 `make help`。
SHELL := /bin/bash

SERVER_DIR := apps/server
CLIENT_DIR := apps/client
PY := $(SERVER_DIR)/.venv/bin/python
PIP := $(SERVER_DIR)/.venv/bin/pip

COMPOSE := docker compose
PROFILE_TEST := --profile test
PROFILE_OBS := --profile obs
PROFILE_CI := --profile test --profile ci

TEST_DATABASE_URL ?= postgresql+psycopg://dongbao:change-me@localhost:55432/dongbao_test
QDRANT_URL ?= http://127.0.0.1:6334
SERVER_ENV = DATABASE_URL=$(TEST_DATABASE_URL) \
	APP_CONFIG=$(CURDIR)/config/providers.toml \
	MEDIA_ROOT=$(CURDIR)/data/media \
	CRY_MODEL_PATH=$(CURDIR)/data/models/babycry-v7 \
	QDRANT_URL=$(QDRANT_URL) \
	EMBEDDING_ALLOW_HASH=1 \
	DEV_LOGIN=$(DEV_LOGIN)

DEV_LOGIN ?=
APP_MODULE ?= app.main:app
PORT ?= 8001
# 小程序真机不能走 localhost；未指定时由 Vite 写入电脑局域网 IP。
CLIENT_API_BASE_URL ?=

.PHONY: help setup setup-cry-model \
	docker-ps docker-down docker-down-all \
	db-up db-wait db-down qdrant-up qdrant-wait \
	langfuse-up langfuse-down \
	seed-rag test test-server test-client typecheck build \
	dev-server dev-mp e2e docker-test

help:
	@echo "── 日常（主机）──"
	@echo "make setup          建 venv + 装依赖"
	@echo "make setup-cry-model 下载固定版本的哭声分类模型"
	@echo "make test           服务端 pytest + 客户端 typecheck/vitest"
	@echo "make test-server    仅服务端（自动起 test profile 依赖）"
	@echo "make test-client    仅客户端"
	@echo "make dev-server     本地 uvicorn :$(PORT)（需 DEV_LOGIN=1 才无微信登录）"
	@echo "make dev-mp         小程序编译；自动写入当前局域网 IP（解决 request:fail）"
	@echo "make seed-rag       真 embedding 写入测试 Qdrant"
	@echo ""
	@echo "── Docker 管理 ──"
	@echo "make docker-ps      看本项目容器"
	@echo "make docker-down    停默认 e2e 栈"
	@echo "make docker-down-all 停全部 profile（test/obs/ci/weixin + e2e）"
	@echo "make db-up          起测试库 :55432"
	@echo "make langfuse-up    起 Langfuse UI :3100（profile obs）"
	@echo "make e2e            DEV_LOGIN=1 起验收栈（postgres+qdrant+server+h5）"
	@echo "make docker-test    容器内 --build 跑测（profile ci）"

setup:
	python3 -m venv $(SERVER_DIR)/.venv
	$(PIP) install -q -r $(SERVER_DIR)/requirements.txt
	cd $(CLIENT_DIR) && npm install

setup-cry-model:
	$(PY) $(SERVER_DIR)/scripts/download_cry_model.py --output $(CURDIR)/data/models/babycry-v7

# ── Docker 管理 ──────────────────────────────────────────────────
docker-ps:
	$(COMPOSE) --profile test --profile obs --profile ci --profile weixin ps -a

docker-down:
	$(COMPOSE) down --remove-orphans

docker-down-all:
	$(COMPOSE) --profile test --profile obs --profile ci --profile weixin down --remove-orphans

db-up:
	$(COMPOSE) $(PROFILE_TEST) up -d postgres-test

db-wait:
	@until $(COMPOSE) $(PROFILE_TEST) exec -T postgres-test pg_isready -U dongbao -d dongbao_test >/dev/null 2>&1; do sleep 0.5; done
	@echo "postgres-test ready on localhost:55432"

qdrant-up:
	$(COMPOSE) $(PROFILE_TEST) up -d qdrant-test

qdrant-wait:
	@until curl -sf http://127.0.0.1:6334/readyz >/dev/null 2>&1; do sleep 0.5; done
	@echo "qdrant-test ready on localhost:6334"

langfuse-up:
	$(COMPOSE) $(PROFILE_OBS) up -d langfuse-db langfuse
	@echo "Langfuse UI: http://127.0.0.1:3100 — 创建 API Key → .env LANGFUSE_*"

langfuse-down:
	$(COMPOSE) $(PROFILE_OBS) stop langfuse langfuse-db

db-down:
	$(COMPOSE) $(PROFILE_TEST) stop postgres-test qdrant-test

seed-rag: db-up db-wait qdrant-up qdrant-wait
	cd $(SERVER_DIR) && set -a && [ -f $(CURDIR)/.env ] && . $(CURDIR)/.env; set +a; \
		DATABASE_URL=$(TEST_DATABASE_URL) APP_CONFIG=$(CURDIR)/config/providers.toml QDRANT_URL=$(QDRANT_URL) \
		.venv/bin/python -c "from app.record.database import SessionLocal; from app.ai.seed import reseed_all; \
		db=SessionLocal(); n=reseed_all(db); print(f'reseeded {n} chunks')"

test-server: db-up db-wait
	cd $(SERVER_DIR) && $(SERVER_ENV) APP_CONFIG=$(CURDIR)/apps/server/tests/providers.toml .venv/bin/alembic upgrade head
	cd $(SERVER_DIR) && $(SERVER_ENV) APP_CONFIG=$(CURDIR)/apps/server/tests/providers.toml .venv/bin/python -m pytest -q

test-client: typecheck
	cd $(CLIENT_DIR) && npm test

typecheck:
	cd $(CLIENT_DIR) && npm run typecheck

build:
	cd $(CLIENT_DIR) && $(if $(strip $(CLIENT_API_BASE_URL)),VITE_API_BASE_URL=$(CLIENT_API_BASE_URL) )npm run build:h5
	cd $(CLIENT_DIR) && $(if $(strip $(CLIENT_API_BASE_URL)),VITE_API_BASE_URL=$(CLIENT_API_BASE_URL) )npm run build:mp-weixin

dev-server: db-up db-wait qdrant-up qdrant-wait
	cd $(SERVER_DIR) && $(SERVER_ENV) .venv/bin/alembic upgrade head
	cd $(SERVER_DIR) && $(SERVER_ENV) QDRANT_URL=http://127.0.0.1:6334 .venv/bin/uvicorn $(APP_MODULE) --reload --host 0.0.0.0 --port $(PORT)

# 小程序必须打电脑局域网 IP；Wi-Fi 一变旧包就会 request:fail。
# 每次用这个目标起编译，避免多个 watcher 抢着把 API 写回过期地址。
dev-mp:
	@IP=$$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null); \
	if [ -z "$$IP" ]; then \
	  IP=$$(python3 -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('192.168.0.1',80));print(s.getsockname()[0]);s.close()"); \
	fi; \
	echo "小程序 API → http://$$IP:$(PORT)/api/v1"; \
	cd $(CLIENT_DIR) && VITE_API_BASE_URL=http://$$IP:$(PORT)/api/v1 npm run dev:mp-weixin

test: test-server test-client

# H5 验收：默认栈，不再顺带起 weixin / langfuse / test 库
e2e:
	DEV_LOGIN=1 $(COMPOSE) up --build

docker-test:
	$(COMPOSE) $(PROFILE_CI) run --rm --build server-test
	$(COMPOSE) $(PROFILE_CI) run --rm --build client-test
