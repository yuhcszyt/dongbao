# 03: 记录接口接入鉴权与真实家庭

**What to build:** 把「身份」从环境变量换成真实凭证——这是本 spec 的安全底线。抽出一份独立的鉴权依赖（解析 Bearer → 验签验过期 → 查用户表 → 返回当前用户与其家庭），记录路由与鉴权路由共用同一份实现，不在两处各写一遍。记录侧所有接口改为依赖它拿到 `family_id`，删除 `FAMILY_ID` / `USER_ID` 常量以及 compose 里的 `TEST_FAMILY_ID` / `TEST_USER_ID`，`created_by` 写真实用户 ID。数据隔离的验收语言是「两个家庭互相看不见」，这是产品承诺。

鉴权失败语义保持现有文案（客户端与测试都依赖）：

- 缺少或格式不对的 Authorization → 401 `missing_token`「请先登录」
- 签名不合法或已过期 → 401 `invalid_token`「登录已过期，请重新进入」
- 用户已不存在（注销后）→ 401 `invalid_token`「账号已注销」

跨家庭访问一律返回 404 + 现有 not_found 错误码（`baby_not_found` / `record_not_found` / `media_not_found` / `draft_not_found`），不引入 403，不通过错误码泄露别人数据的存在性。

媒体取用方式按 spec 的硬约束落地：`uni.previewImage` / `uni.createInnerAudioContext` 无法设置请求头，因此媒体 GET 保持免 token，以不可猜的 UUID 作能力凭证——URL 只在已鉴权的列表 / 详情响应里下发，上传接口（`uni.uploadFile` 可设 header）走正常 Bearer 鉴权。

**Blocked by:** 01、02（测试要通过真实登录接口拿 token，从而回归网跑的是带凭证的全链路，而不是再造一套测试期身份）

**Status:** ready-for-agent

- [ ] 记录、媒体上传、草稿、今日汇总全部接口无 Authorization 时返回 401 `missing_token`「请先登录」
- [ ] 篡改签名与过期 token 均返回 401 `invalid_token`「登录已过期，请重新进入」
- [ ] 以第二个 openid 登录后交叉访问第一个家庭的宝宝 / 记录 / 媒体 / 草稿，全部 404 且错误码是 not_found 系列，不是 403
- [ ] 媒体 GET 无需 token 即可取到文件；该 URL 只在带 token 的响应体里被下发；上传接口无 token 返回 401
- [ ] 代码与 compose 中不再出现 `FAMILY_ID` / `USER_ID` / `TEST_FAMILY_ID` / `TEST_USER_ID`，新建记录的 `created_by` 是真实用户 ID
- [ ] 原有四个记录场景（十类记录 + 时间线 + 今日汇总 + 编辑 / 删除 / 撤销；语音草稿需确认且保留来源；Provider 失败返回可编辑草稿且不丢媒体；拒绝 payload 类型不匹配与非法上传）改为带 token 调用后全部通过，作为「鉴权重构没弄坏原有行为」的回归网
- [ ] 鉴权依赖只有一份实现，记录路由与鉴权路由共用
