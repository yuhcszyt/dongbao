# 01: 统一服务端入口，接上断链

**What to build:** 服务端回到「一个应用、一个入口」的状态：用 spec 里约定的唯一应用模块作为装配点，创建应用实例、注册 request-id 中间件与 HTTPException / RequestValidationError 异常处理器（保持现有错误信封 `{"error": {"code", "message", "fields"?}, "request_id": ...}` 与 `X-Request-ID` 响应头），并把记录路由与鉴权路由一起挂载上去。此前鉴权路由没有被挂载，等于死代码；三处入口写法也不一致。收口之后，`health`、记录侧全部接口、`POST /api/v1/auth/wechat` 由同一个应用提供，容器启动命令、Dockerfile、本地启动说明三处一致。同时修掉让测试撒谎的三处基础设置：语音与 Provider 失败两个用例 patch 的属性在当前被测模块里根本不存在（符号在别处解析），以及 autogenerate 看不见 `users` / `families`、测试清理 fixture 不覆盖这两张表。

本票是预重构，不改任何接口语义：鉴权仍然未接入记录接口，记录仍用硬编码家庭；记录侧现有行为必须一字不变地继续通过。

**Blocked by:** 无（可立即开始）

**Status:** done (b9849fc)

- [x] 容器与本地启动命令、Dockerfile、本地启动说明统一到同一个应用入口，容器起来后 `health` 可用 — compose `server`/`server-test`、`apps/server/Dockerfile` CMD、`Makefile` `APP_MODULE`、`AGENTS.md` 四处均为 `app.main:app`，仓库内已无 `app.record.main` 引用
- [x] `Makefile` 里 `make dev-server` 的 `APP_MODULE` 默认值一并切到新入口（本地闭环见 AGENTS.md《Testing》）— `Makefile:16` `APP_MODULE ?= app.main:app`
- [x] 记录侧路由成为可挂载的独立路由器，行为与拆分前完全一致（现有记录测试除下述 patch 修正外不改断言即可通过）— `app/record/main.py` → `app/record/routes.py`（`router = APIRouter()`），`test_records.py` 仅动 import / fixture / patch 目标，断言未改
- [x] 鉴权路由被真正挂载：未配置微信凭证时调用登录接口得到 502 `wechat_login_failed`，而不是 404 — `tests/test_app_entry.py::test_single_app_serves_health_record_and_auth_routes`
- [x] 语音草稿与 Provider 失败两个用例 patch 到真正解析 `transcribe_audio` / `extract_draft` 的模块后转绿，且不再依赖不存在的属性 — patch 到 `app.record.routes.*`
- [x] autogenerate 能看见 `families` / `users`（迁移方向不变，本票不新增迁移）— `alembic/env.py:9` `from app.auth import models`；`alembic check` 输出「No new upgrade operations detected」，metadata 含 7 张表
- [x] 测试清理 fixture 覆盖记录侧与鉴权侧全部表，连续两个用例不会撞 unique openid — `tests/conftest.py` autouse，覆盖 RecordMedia/RecordDraft/BabyRecord/MediaAsset/Baby/User/Family
- [x] 客户端与服务端的既有测试命令（`server-test`、`client-test`）在本票后全绿 — `make test`：服务端 `8 passed`（含 test_app_entry 4 + test_records 4），客户端 `vue-tsc` 无错、`vitest` 1 passed

**验收备注：** 全部到位，无遗留。

