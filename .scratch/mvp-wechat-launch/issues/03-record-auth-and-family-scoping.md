# 03: 记录接口接入鉴权与真实家庭

**What to build:** 把「身份」从环境变量换成真实凭证——这是本 spec 的安全底线。抽出一份独立的鉴权依赖（解析 Bearer → 验签验过期 → 查用户表 → 返回当前用户与其家庭），记录路由与鉴权路由共用同一份实现，不在两处各写一遍。记录侧所有接口改为依赖它拿到 `family_id`，删除 `FAMILY_ID` / `USER_ID` 常量以及 compose 里的 `TEST_FAMILY_ID` / `TEST_USER_ID`，`created_by` 写真实用户 ID。数据隔离的验收语言是「两个家庭互相看不见」，这是产品承诺。

鉴权失败语义保持现有文案（客户端与测试都依赖）：

- 缺少或格式不对的 Authorization → 401 `missing_token`「请先登录」
- 签名不合法或已过期 → 401 `invalid_token`「登录已过期，请重新进入」
- 用户已不存在（注销后）→ 401 `invalid_token`「账号已注销」

跨家庭访问一律返回 404 + 现有 not_found 错误码（`baby_not_found` / `record_not_found` / `media_not_found` / `draft_not_found`），不引入 403，不通过错误码泄露别人数据的存在性。

媒体取用方式按 spec 的硬约束落地：`uni.previewImage` / `uni.createInnerAudioContext` 无法设置请求头，因此媒体 GET 保持免 token，以不可猜的 UUID 作能力凭证——URL 只在已鉴权的列表 / 详情响应里下发，上传接口（`uni.uploadFile` 可设 header）走正常 Bearer 鉴权。

**Blocked by:** 01、02（测试要通过真实登录接口拿 token，从而回归网跑的是带凭证的全链路，而不是再造一套测试期身份）

**Status:** done (6061e29)

- [x] 记录、媒体上传、草稿、今日汇总全部接口无 Authorization 时返回 401 `missing_token`「请先登录」 — `tests/test_record_auth.py::test_every_record_side_endpoint_rejects_a_missing_token` 逐一断言 17 个调用（宝宝建 / 列表 / 详情 / 改、媒体上传、语音与拍照草稿、确认草稿、记录增 / 列表 / 详情 / 改 / 删 / 撤销、今日汇总），错误信封 `{code, message}` 与文案逐字比对，并回查「无 token 的那批调用一行数据都没改」
- [x] 篡改签名与过期 token 均返回 401 `invalid_token`「登录已过期，请重新进入」 — `::test_tampered_and_expired_tokens_are_rejected`：改签名位一例；过期一例用真实登录接口签发（把 `TOKEN_TTL_SECONDS` 调成负数），走的是签发 / 验签同一条实现
- [x] 以第二个 openid 登录后交叉访问第一个家庭的宝宝 / 记录 / 媒体 / 草稿，全部 404 且错误码是 not_found 系列，不是 403 — `::test_a_second_family_cannot_reach_the_first_family_data`：`baby_not_found` 8 处（详情 / 改名 / 建记录 / 列表 / 汇总 / 上传 / 建草稿 / 取宝宝），`record_not_found` 4 处（读 / 改 / 删 / 撤销），`draft_not_found`（确认别家草稿）、`media_not_found`（拿别家 media id 建草稿）；另断言别家媒体 URL 不出现在任何带 token 的响应体里，且两个家庭的今日汇总互不串号
- [x] 媒体 GET 无需 token 即可取到文件；该 URL 只在带 token 的响应体里被下发；上传接口无 token 返回 401 — `::test_media_get_is_a_capability_url_while_upload_needs_a_token`：无 header `GET /api/v1/media/{uuid}` → 200，字节与 `content-type` 与上传一致；无 token 上传 → 401；随机 UUID → 404。URL 只在 `app/record/routes.py:51 media_out()` 里生成，调用点只有「上传响应」与「家庭内的记录 / 草稿响应」
- [x] 代码与 compose 中不再出现 `FAMILY_ID` / `USER_ID` / `TEST_FAMILY_ID` / `TEST_USER_ID`，新建记录的 `created_by` 是真实用户 ID — `grep -rn 'TEST_FAMILY_ID\|TEST_USER_ID\|FAMILY_ID\|USER_ID'` 覆盖 `apps/`、`config/`、`docker-compose.yml`、`.env.example`、`Makefile`（排除 `node_modules` / `.venv`）零命中；`.env.example` 与 `docker-compose.yml` 里那两键已删。`created_by` 归属由 `::test_created_by_records_the_real_user_for_manual_and_confirmed_records` 直接读库断言，手工记录与确认草稿两条路径都等于登录返回的 `user_id`（不再是环境变量里的测试用户）
- [x] 原有四个记录场景（十类记录 + 时间线 + 今日汇总 + 编辑 / 删除 / 撤销；语音草稿需确认且保留来源；Provider 失败返回可编辑草稿且不丢媒体；拒绝 payload 类型不匹配与非法上传）改为带 token 调用后全部通过 — `tests/test_records.py` 四个用例断言未改，只是每处调用挂上 `auth` fixture 的 header（并打印失败响应体方便定位）；`test_app_entry.py` 的 `/api/v1/babies` 断言由 200 改为 401 `missing_token`（路由已挂载但入口已鉴权）
- [x] 鉴权依赖只有一份实现，记录路由与鉴权路由共用 — 唯一实现在 `apps/server/app/auth/dependencies.py`，被 `apps/server/app/record/routes.py:17` 与 `apps/server/app/auth/routes.py:13` 引用；`auth/routes.py` 里原有的第二份 `current_user` 与 `_raise` 已删，记录侧的 `error()` 也改为复用同一份 `api_error`（`from ..auth.dependencies import api_error as error`），错误信封只有一处实现

## Comments

2026-09-15 实施与验收记录（agent）。`make test` 全绿：服务端 **31 passed**（其中 `test_record_auth.py` 6、`test_records.py` 4、`test_app_entry.py` 4），客户端 `vue-tsc` 无错 + `vitest` 1 passed。

两轴代码审查（Standards / Spec 各一个只读 sub-agent，固定点 HEAD = 42cd3b5）后已处置：

- 重复的错误信封：`record/routes.py` 的 `error()` 与 `dependencies.py` 的 `api_error()` 本是同一份实现 → 改为 import 别名，删掉重复实现与不再使用的 `HTTPException` 导入（调用点零改动）。
- 媒体决策未入册：`CONTEXT.md` 新增上线决策 **12**（`GET /api/v1/media/{uuid}` 免 token、UUID 即能力凭证、URL 只在带 token 响应里下发、上传走 Bearer；要更严改短时效签名 URL）。
- 未采纳：把「用户 + 家庭」拆成两个依赖 / 再包一层 principal —— 返回的 `User` 就是这一对（`user.family_id` 即当前家庭），多一层只转发 `family_id` 的依赖是中间人；已在 `dependencies.py` docstring 写明。测试助手在两个用例文件里各留一份，换取各自可独立阅读。

**清单内两处表述的裁定（第 3 条 vs 第 4 条）：** 字面上二者不可能同时成立 —— 没有 token 就无法比对家庭。按 spec《媒体文件的取用方式》那句解释（「即媒体 URL 只在『已鉴权的列表 / 详情响应』里被下发，拿到 URL 的人只拿到这一个文件」）与《媒体免 token 的取舍》（「URL 泄露即文件泄露，MVP 接受该风险」）落地为：

- 文件本身 `GET /api/v1/media/{uuid}` 免 token、不做家庭校验 —— UUID 即能力凭证；
- 第 3 条的「媒体」按「带 token 的媒体相关接口」理解：拿别家的 baby / media / draft id 一律 404 且是 not_found 系列，并且任何带 token 的响应体都不下发别家的媒体 URL；
- 覆盖在 `apps/server/tests/test_record_auth.py` 的 `test_a_second_family_cannot_reach_the_first_family_data` 与 `test_media_get_is_a_capability_url_while_upload_needs_a_token`。

**已知判断与遗留（本票未改，留待后续裁决）：**

- **发布顺序硬约束**：`apps/client/src/services/api.ts` 仍不带 `Authorization`，记录接口对它现在全 401 —— 票据 05（客户端会话模块）必须先于任何 H5 / 小程序验收上线。
- 媒体文件 GET 不跟家庭绑定（见上裁定）：知道 UUID 的人只拿到那一个文件，URL 不可枚举；要严格则改短时效签名 URL，只需改下发 URL 一处。
- token 里的 `fid` claim 仍照旧签发但被刻意忽略（家庭一律回查数据库，为将来的换家庭留路）：`dependencies.py` 用 `_claimed_family_id` 显式标注，但该字段本身会让人误以为可信。
- 真实微信登录与真机小程序联调未在本票跑；本票证据全部来自 `make test` 的主机闭环。

## Comments

2026-09-15 实施记录（agent）。清单里第 3 条与第 4 条对媒体文件的表述互相矛盾：第 4 条要求「媒体 GET 无需 token 即可取到文件」，而没有 token 就没法比对家庭。按 spec《媒体文件的取用方式》里那句解释（「即媒体 URL 只在『已鉴权的列表 / 详情响应』里被下发，拿到 URL 的人只拿到这一个文件」）与《媒体免 token 的取舍》（「URL 泄露即文件泄露，MVP 接受该风险」）落地为：

- 文件本身 `GET /api/v1/media/{uuid}` 免 token、不做家庭校验 —— UUID 即能力凭证；
- 第 3 条的「媒体」按「带 token 的媒体相关接口」理解：拿别家的 baby / media / draft id 一律 404 且是 not_found 系列（`baby_not_found` / `media_not_found` / `draft_not_found`），并且任何带 token 的响应体都不下发别家的媒体 URL（URL 只在已鉴权的列表 / 详情里出现）；
- 覆盖在 `apps/server/tests/test_record_auth.py` 的 `test_a_second_family_cannot_reach_the_first_family_data` 与 `test_media_get_is_a_capability_url_while_upload_needs_a_token`。

若要更严（文件 GET 也按家庭校验），后续改为短时效签名 URL 即可，只需改下发 URL 一处（spec 已记）。
