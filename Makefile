# 本地快速验证：日常迭代不碰 docker，只有 e2e 人工验收与里程碑一致性检查才起容器。
# 用法见 `make help`。
SHELL := /bin/bash

SERVER_DIR := apps/server
CLIENT_DIR := apps/client
PY := $(SERVER_DIR)/.venv/bin/python
PIP := $(SERVER_DIR)/.venv/bin/pip

TEST_DATABASE_URL ?= postgresql+psycopg://dongbao:change-me@localhost:55432/dongbao_test
# 仅服务端进程需要，不进 compose 插值
SERVER_ENV = DATABASE_URL=$(TEST_DATABASE_URL) \
	APP_CONFIG=$(CURDIR)/config/providers.toml \
	MEDIA_ROOT=$(CURDIR)/data/media \
	DEV_LOGIN=$(DEV_LOGIN)

# 开发降级：仅本地/CI 显式 `make DEV_LOGIN=1 ...` 才开；默认空 = 真实微信。
DEV_LOGIN ?=

APP_MODULE ?= app.main:app
PORT ?= 8001

.PHONY: help setup db-up db-wait db-down test test-server test-client typecheck build dev-server e2e docker-test

help:
	@echo "make setup         一次性：建 venv、装 python 与 npm 依赖"
	@echo "make test          本地全量：服务端 pytest + 客户端 typecheck/vitest（自动起测试库）"
	@echo "make test-server   仅服务端：alembic upgrade head + pytest"
	@echo "make test-client   仅客户端 typecheck + vitest"
	@echo "make typecheck     仅 vue-tsc"
	@echo "make build         客户端 h5 + mp-weixin 构建校验"
	@echo "make dev-server    本地 uvicorn --reload（$(APP_MODULE)，端口 $(PORT)）；无微信凭证时加 DEV_LOGIN=1"
	@echo "make db-up         只起测试库（localhost:55432，tmpfs，跑了就丢）"
	@echo "make e2e           docker compose up --build 端到端人工验收"
	@echo "make docker-test   里程碑一致性：容器内带 --build 跑一遍全部测试"

setup:
	python3 -m venv $(SERVER_DIR)/.venv
	$(PIP) install -q -r $(SERVER_DIR)/requirements.txt
	cd $(CLIENT_DIR) && npm install

db-up:
	docker compose --profile tools up -d postgres-test

db-wait:
	@until docker compose --profile tools exec -T postgres-test pg_isready -U dongbao -d dongbao_test >/dev/null 2>&1; do sleep 0.5; done
	@echo "postgres-test ready on localhost:55432"

db-down:
	docker compose --profile tools stop postgres-test

test-server: db-up db-wait
	cd $(SERVER_DIR) && $(SERVER_ENV) .venv/bin/alembic upgrade head
	cd $(SERVER_DIR) && $(SERVER_ENV) .venv/bin/python -m pytest -q

test-client: typecheck
	cd $(CLIENT_DIR) && npm test

typecheck:
	cd $(CLIENT_DIR) && npm run typecheck

build:
	cd $(CLIENT_DIR) && npm run build:h5 && npm run build:mp-weixin

dev-server: db-up db-wait
	cd $(SERVER_DIR) && $(SERVER_ENV) .venv/bin/alembic upgrade head
	cd $(SERVER_DIR) && $(SERVER_ENV) .venv/bin/uvicorn $(APP_MODULE) --reload --port $(PORT)

test: test-server test-client

e2e:
	docker compose up --build

docker-test:
	docker compose --profile tools run --rm --build server-test
	docker compose --profile tools run --rm --build client-test
