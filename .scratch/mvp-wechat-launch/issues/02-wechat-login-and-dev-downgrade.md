# 02: 微信登录接口上线 + 开发降级

**What to build:** 家长侧的第一块地基——凭证签发。客户端拿 `wx.login` 的 code 调 `POST /api/v1/auth/wechat`，服务端用 code 换 openid，首次登录创建一个家庭与一个用户，再次登录复用同一用户，返回 30 天 token 与 `user_id`。契约不变：入参 `code`，出参 `token` + `user_id`。

同时给出开发降级开关：仅当显式设置 `DEV_LOGIN=1` 时跳过 jscode2session，把 code 直接当 openid 用；未设置时保持现有行为（缺 `WECHAT_APPID` / `WECHAT_SECRET` → 502 `wechat_login_failed`）。启动日志必须打印当前处于哪种模式，生产环境默认关闭。

**Blocked by:** 01（登录接口必须先真的被挂载）

**Status:** done (ef710c8)

- [x] 同一 code 调两次登录接口，得到同一个 `user_id`，且两次登录后属于同一家庭 — `tests/test_auth_login.py::test_same_code_logs_into_the_same_user_and_family`：两次 `user_id` 相同，库里恰好 1 个家庭 + 1 个用户，两个 token 的 `fid` 相同
- [x] 两个不同 code 登录得到的 `user_id` 不同、家庭不同 — `::test_different_codes_get_different_users_and_families`：库里 2 个家庭、2 个用户，两个 token 的 `fid` 不同
- [x] 返回的 token 里不含任何明文隐私字段，服务端不持久化会话（不引 Redis、不建会话表） — `::test_token_carries_no_plaintext_privacy_and_login_keeps_no_session`：openid 不出现在 token 里，payload 恰好是 `{uid, fid, exp}`，`exp - now` 落在 30 天；表名里没有 session/token 表，登录只新增 1 家庭 + 1 用户
- [x] 未设置 `DEV_LOGIN` 且缺微信凭证时返回 502 `wechat_login_failed`，文案不含任何上游原始错误细节 — `::test_missing_wechat_credentials_returns_generic_502`（文案里没有 APPID/SECRET 字样）+ `::test_upstream_error_detail_never_reaches_the_client`（上游 `errcode=40029` / 带 rid 的 `errmsg` 都不出现在错误信封里）+ `::test_wechat_unreachable_is_reported_as_wechat_login_failed`；原始细节只进服务端日志（`app/auth/routes.py` `logger.warning`）
- [x] 显式设置 `DEV_LOGIN=1` 后，任意字符串作 code 均可登录成功 — `::test_dev_login_accepts_any_code_without_touching_wechat`（中文、带空格、64 与 128 字符；httpx 被换成会 `AssertionError` 的替身，证明没请求微信）+ `::test_dev_login_still_works_when_the_code_is_longer_than_the_openid_column`（超长 code 摘成 64 字符 openid，两次同 code 仍同一用户，不再 500）
- [x] 启动日志明确打印当前登录模式（真实 / 开发降级） — `app/main.py` lifespan 里 `logger.info(login_mode_message())`；`::test_startup_log_prints_the_mode_even_when_the_host_configures_its_own_loggers` 在干净进程里按 uvicorn 的日志配置（只给自己的 logger 配 handler、root 停在 WARNING）断言 stderr 出现「登录模式：开发降级」/「登录模式：真实微信」且互斥。真实进程复核：`DEV_LOGIN=1 uvicorn app.main:app` 打印 `INFO: 登录模式：开发降级（DEV_LOGIN=1：…生产环境禁止开启）`，默认打印 `INFO: 登录模式：真实微信（jscode2session）`
- [x] 登录接口的失败响应仍是统一错误信封，并带 `request_id` — `::test_missing_wechat_credentials_returns_generic_502` 断言 `error.code == "wechat_login_failed"` 且 `body.request_id == X-Request-ID` 响应头；真实进程 curl 得到 `{"error":{"code":"wechat_login_failed","message":"微信登录失败，请稍后重试"},"request_id":"…"}`
- [x] （附带）只有显式 `DEV_LOGIN=1` 才算开发降级 — `::test_only_explicit_dev_login_one_enables_dev_mode`：`""` / `0` / `true` / `yes` / `2` / `1.0` 一律 502

**验收备注：** 全部清单项到位，无遗留阻塞。`make test` 全绿：服务端 25 passed（其中 `test_auth_login.py` 17）、客户端 `vue-tsc` 无错 + `vitest` 1 passed。

为让「启动日志必须打印」真正成立，多做了两处基础设施（清单外的必要配套）：

- `app/main.py` 的 `configure_app_logging()`：uvicorn / gunicorn 只给自己的 logger 配 handler，应用 logger 会掉进「级别停在 WARNING、又没有 handler」的 root，启动日志静默消失（`lastResort` 只兜 WARNING+）。现在打开应用包 logger（`__package__ == "app"`）的级别，并只在 root 没 handler 时补一个 `StreamHandler`，不动宿主的 root 级别。
- 环境接线：`docker-compose.yml` 的 `x-server-environment` 透传 `WECHAT_APPID` / `WECHAT_SECRET` / `JWT_SECRET`（默认开发值）/ `DEV_LOGIN`（默认空）；`.env.example` 补上 4 个键；`Makefile` `SERVER_ENV` 透传 `DEV_LOGIN`（默认空 = 真实微信，`make DEV_LOGIN=1 dev-server` 才开）；`AGENTS.md` 加《本地登录（无微信凭证）》。

已知判断与遗留（本票未改，留待后续裁决）：

- `request_id` 会原样回显客户端的 `X-Request-ID`（票据 01 的中间件，非本票范围），存在反射输入 / 日志注入面。
- `JWT_SECRET` 在 `app/auth/security.py` 导入时取值，开发默认值 `dongbao-dev-secret` 编译进代码（票据 01 / 安全模块范围）。
- 并发同一 code 登录（两个请求同时走到「建家庭」）会撞 unique openid 得到 500；本票清单只覆盖顺序重复登录。
- `DEV_LOGIN` 容忍首尾空白（`" 1 "` 也算开），比「显式 =1」略宽，是有意为之。
- 「不建会话表」用表名子串扫描断言，是 ADR-0002 的近似表达（若将来出现 `refresh_tokens` 之类合法表会误报）。
