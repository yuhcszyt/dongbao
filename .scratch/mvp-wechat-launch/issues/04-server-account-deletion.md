# 04: 注销账号服务端收口

**What to build:** 微信平台合规硬要求背后的服务端行为：家长注销后，该用户、其家庭、家庭下的宝宝、记录、草稿、媒体记录与磁盘上的媒体文件被真正删除。ADR-0002 的吊销机制在这里兑现——服务端零存储，吊销是「鉴权时查用户表」的副产品：用户行没了，旧 token 立刻失效。

**Blocked by:** 03（需要 03 抽出的共用鉴权依赖，注销接口本身也要鉴权）

**Status:** done (2e2b687)

- [x] `DELETE /me` 带有效 token 调用返回 204 — `tests/test_account_deletion.py::test_deleting_the_account_erases_every_row_of_that_family_and_nothing_else` 断言 204 且响应体为空；`DELETE /api/v1/me` 由 `app/auth/routes.py:47 delete_me()` 提供，它只做一件事：`erase_family(db, user.family_id)`
- [x] 注销后拿旧 token 请求任意接口返回 401 `invalid_token`「账号已注销」 — `::test_the_old_token_stops_working_with_an_account_deleted_message`（`tests/test_account_deletion.py:156`）对四个调用逐一断言状态码与完整错误信封：读宝宝列表、读记录列表、建宝宝、再注销一次；文案来自 `app/auth/dependencies.py`（鉴权时查不到用户行 → 401，ADR-0002 的吊销即查询副产品，服务端不存任何吊销名单）
- [x] 该家庭的宝宝、记录、草稿、媒体行全部查不到 — 同第一个用例：`babies` / `users` / `families` 各 0 行，`baby_records` / `record_drafts` / `media_assets` 按注销前记下的 id 逐批数行 == 0，`record_media` 按 record id 与 media id 两个方向都 == 0；同时断言另一个家庭（第二个 openid）的 `users` / `families` / `babies` 各留 1 行 —— 注销不越过家庭边界
- [x] 该家庭在本地磁盘上的媒体文件已删除 — `::test_media_files_are_removed_from_disk`（`:172`）：先用 `media_path()` 取出该家庭所有媒体文件的落点并断言它们真实存在且位于临时 `MEDIA_ROOT` 下，注销后逐个断言 `not path.exists()`
- [x] 注销后同一 openid 重新登录会得到一个全新家庭与全新用户，看不到任何旧数据 — `::test_signing_in_again_with_the_same_openid_starts_a_blank_account`（`:183`）：重登返回的 `user_id` 与注销前不同、宝宝列表 `[]`、用旧宝宝 id 取详情 404 `baby_not_found`，库里只剩一个新 `users` 行、一个新 `families` 行、0 个 `babies` 行
- [x] 请求过程中失败不会留下「删了一半」的状态（数据一致性优先于文件清理，文件清理失败不应导致接口报错） — 两半分别有用例：`::test_a_failure_before_commit_does_not_leave_a_half_deleted_family`（`:202`）把 `Session.commit` 换成抛 `RuntimeError`，断言 500 且 `users` / `families` / `babies` 一行不少、记录条数不变、旧 token 依然可用；`::test_a_media_file_that_cannot_be_cleaned_does_not_fail_the_request`（`:228`，两参数）分别构造「预期内的 `OSError`」（路径已变成目录）与「意料之外的异常」（清理实现自己抛错），两种都断言 204 + 数据确实已删

## Comments

2026-09-16 实施与验收记录（agent）。`make test` 全绿：服务端 **38 passed**（其中 `test_account_deletion.py` 7，含一个两参数用例），客户端 `vue-tsc` 无错 + `vitest` 16 passed。

落点：`apps/server/app/erasure.py`（新增，唯一知道「一户家庭的数据都由谁持有」的地方）、`apps/server/app/record/storage.py`（新增，媒体文件在磁盘上的唯一落点）、`apps/server/app/auth/routes.py`（`delete_me` 改为一行委派）、`apps/server/app/record/routes.py`（媒体路径改从 `storage` 取）。

两轴代码审查（Standards / Spec 各一个只读 sub-agent，固定点 HEAD = 359a177，只审服务端未提交改动）后已处置：

- **提交后清理仍可能 500**（Spec 轴）：`remove_media_files` 原本只兜 `OSError`，而它在 `db.commit()` 之后调用——任何意料之外的异常都会变成「数据已删、请求报 500」，正是本票第 6 条禁止的状态。改为逐 key 兜 `Exception` 并记日志（坏一个不影响其余清理），并加一条参数化用例把「意料之外的异常」这一路也钉住。
- **`erase_family` 删的是整个家庭的所有用户**（Standards 轴）：与旧实现 `db.delete(user)` 语义不同。按本票原文「该用户、其家庭…被真正删除」与 CONTEXT.md 上线决策 7 落地为「注销 = 擦掉整个家庭」（当前一户一用户，两者等价），函数 docstring 与 CONTEXT.md 决策 7 都写明：Phase 5 引入多家长后要改成「只删当前用户，家庭留到最后一个成员注销」。
- **测试里重复的查询助手**：`_count` 与 `_gone` 合并（`_count` 接受列表即数这批 id 还剩几行），`_family_id_of` 的返回标注从 `object` 改回 `UUID`。
- **`_delete_rows` 名字掩盖了它的第二个输出**：改名 `_purge_family_rows`。
- **测试模块 docstring 与实现不符**：原文写「不碰私有函数」，但失败路径确实替换了 `Session.commit` 与 `media_path`。docstring 改为如实描述「断言只落在 HTTP / 错误信封 / 库里的行 / 磁盘文件上，失败路径靠在模块边界上换掉实现来构造」。
- **未采纳**：把清理失败改成后台任务 / 提交前删文件——前者对 MVP 是多余机制（Speculative Generality），后者会让回滚后的记录指向已消失的文件，比留垃圾更糟；「`erase_family` 只有一个调用点」也保留：它正是本票要的接缝（把擦除逻辑从路由里拿出来），且已被本票的行为用例覆盖。
- **已知遗留（本票不改）**：`media_assets` 行是磁盘文件清单的唯一来源，所以「写完文件、插行之前崩溃」留下的孤儿文件不会被扫掉——本票只承诺删家庭媒体文件，孤儿文件清扫留给后续（需一个按目录反查的清理任务）。
- **依赖媒体路径重构的理由**：`MEDIA_ROOT` 原先在 `record/routes.py` 里 import 时定死，导致测试既不能改落点也没法断言磁盘。抽到 `app/record/storage.py` 并改为按需读环境变量后，`test_account_deletion.py` 才能把落点指到临时目录、直接断言文件。属于为达成第 4 条而必须的改动，不是范围外扩张。
- 真实微信环境下注销未在本票跑；本票证据全部来自 `make test` 的主机闭环。
