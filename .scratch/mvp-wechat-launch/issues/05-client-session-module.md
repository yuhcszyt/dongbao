# 05: 客户端会话模块与统一网络层

**What to build:** 客户端唯一的「身份」接缝。新增一个纯会话模块，它不导入任何页面组件，可以被 vitest 直接单测，负责：token 持久化、启动时静默登录、给请求附带 `Authorization: Bearer`、401 后重登并最多重放一次原请求、注销后清空本地状态。

启动时序：读取本地 token → 有则先当已登录用 → 首次请求若 401 则重登 → 重登失败则进入「需要重试」的可恢复状态（不白屏、不卡加载）。不做登录页 UI，静默重登是唯一路径。注销后不自动重登，新会话要等下一次冷启动或显式操作，避免「注销即重新注册」的错觉。

统一网络层是所有请求（含 `uni.uploadFile`）带 token 的唯一位置，页面不自己拼 header。H5 等非微信环境没有 `wx.login`，客户端用本机持久化的开发 code 调同一个登录接口——网络层只有一条登录路径，没有环境分支。

**Blocked by:** 02（登录接口契约必须先真实存在，否则「静默登录成功」无法端到端成立）

**Status:** done (本票提交)

- [x] 会话模块可在 vitest 中直接 import 并断言，不依赖任何页面组件或 uni 组件 mock — `apps/client/src/services/session.ts` 是一个纯工厂 `createSession(ports)`（`:87`），存储 / 登录请求 / 登录 code 三件外部事全部从 `SessionPorts`（`:63`）注入；`session.test.ts` 的 13 个用例只 import 这个模块 + 手写桩，`uni` / `wx` 只出现在接线文件 `apps/client/src/services/sessionHost.ts` 的函数体内
- [x] 启动时无本地 token 会静默登录；有本地 token 时先当已登录用，不发多余的登录请求 — `::启动时没有本地 token 会静默登录，并把凭证留在本地`（`session.test.ts:50`）、`::有本地 token 时先当已登录用，不发多余的登录请求`（`:65`，断言登录接口 0 次调用）、`::并发启动只会真的登录一次`（`:78`，`signInOnce()` 复用同一个 in-flight promise，`session.ts:130`）
- [x] 所有 HTTP 请求与文件上传都自动带上 `Authorization: Bearer`，页面代码里不出现手写 header — 凭证只在 `session.ts:166 run()` 里经 `bearer(activeToken())` 交给操作；`api.ts:63`（JSON 请求）、`api.ts:124`（`uni.uploadFile`）、`api.ts:151`（媒体位）三条出口全部走 `session.run`，页面上没有任何 `Authorization` / `Bearer` 字面量
- [x] 请求收到 401 时先重登再重放原请求，且最多重放一次；重放后仍 401 不进入无限循环，而是进入可恢复的「需要重试」状态 — `::请求收到 401 会先重登再原样重放一次，且只重放一次`（`session.test.ts:87`）、`::并发的旧 token 401 只重登一次，后到的那个直接用新 token 重放`（`:101`）、`::重放后仍是 401 不进入无限循环，而是进入可恢复的「需要重试」状态`（`:119`，状态 `needs-retry`）、`::用户点重试后可以恢复到已登录`（`:165`，对应 `session.ts:154 retry()`）
- [x] 重登失败时对外暴露可识别的失败状态与中文提示，而不是抛英文异常或静默吞掉 — `SESSION_MESSAGES`（`session.ts:18`）、`SessionError`（`:24`，带 `code` 与 `reason`，原始错误只留在 `reason` 里）、状态 `anonymous | authenticated | needs-retry | signed-out`（`:13`）；用例 `::重登失败时对外给出可识别的失败状态与中文提示，不透出上游英文错误`（`:139`，断言 message 不含 `request:fail` 而 `reason` 保留原始 `Error`）、`::无本地 token 时登录失败同样进入「需要重试」`（`:157`）、`::非 401 的失败响应原样返回`（`:210`）、`::网络本身抛错时直接抛出，不会误判成凭证过期`（`:221`）、`::本地 token 损坏时当作未登录处理`（`:233`）
- [x] 注销后本地状态被清空，且不会自动重登 — `::注销会清空本地状态，且不会自动重登（要等下一次冷启动）`（`session.test.ts:185`）；`session.ts:160 logout()` 只清本地凭证并把状态置 `signed-out`，不调服务端 `/logout`（与票据 02 的「零存储吊销」一致）
- [x] 非微信环境使用本机持久化的开发 code 走同一个登录接口，网络层无环境分支 — `apps/client/src/services/loginCode.ts:28 createLoginCode`，环境只在 code 来源处判断一次，用例 `loginCode.test.ts:16`（微信直接用 `wx.login` 的 code，不落盘）、`:26`（非微信环境生成本机开发 code 并持久化，同一设备复用）、`:37`（已持久化的复用，不再重新生成）；`sessionHost.ts` 里登录请求与其它请求同一条 `uni.request` 路径，没有 H5 / 小程序分支
- [x] `npm run typecheck` 与 `npm test` 通过 — 见下方 Comments 的回归记录

## Comments

2026-09-16 实施与验收记录（agent）。`make test` 全绿：服务端 **38 passed**，客户端 `vue-tsc` 无错 + `vitest` **17 passed**（`session.test.ts` 13 / `loginCode.test.ts` 3 / `domain.test.ts` 1）；`npm run build:h5` 与 `npm run build:mp-weixin` 均通过。

落点：`apps/client/src/services/session.ts`（新增，纯会话模块）、`sessionHost.ts`（新增，uni / wx 接线：存储、登录请求、code 来源）、`loginCode.ts`（新增，开发 code 来源）、`config.ts`（新增，`API_BASE` / `mediaUrl`）、`http.ts`（新增，`isSuccess` 的唯一判定处）、`api.ts`（改造：所有请求与上传都走 `session.run`，不再自己拼 header）、`App.vue`（`onLaunch` 静默 `ensureSession()`）、`pages/index/index.vue`（错误文案与重试入口）、`components/CapturePanel.vue`（`SessionError` 也映射成中文文案）。

两轴代码审查（Standards / Spec 各一个只读 sub-agent，固定点 HEAD = 806bcee，只审本票未提交改动）后已处置：

- **会话失败没有重试入口**（两轴共同指出）：`SESSION_MESSAGES.sessionExpired` 原本是「请重新进入小程序」，而重进小程序正是坏掉的那条路。现在 `pages/index/index.vue` 的 `fail()`（`:32-40`）把「错误来自 `SessionError`」记成 `retryable`，三处错误横幅（`:183` / `:211` / `:237`）据此渲染「重试」按钮 → `retrySession()`（`:67`）先 `session.retry()` 再 `load()`；同时文案改成「登录已过期，请重试」与入口一致。
- **并发的 401 会各登录一次**（Standards 轴）：`run()` 原来直接重登，同一批请求同时撞上过期 token 时会各发一次登录。现在 `run()`（`session.ts:166`）记下发出去时用的那个 token，只有它还是当前的才重登，否则说明别人已经换过 token，直接拿新 token 重放；新增用例 `::并发的旧 token 401 只重登一次`。
- **「2xx 即成功」的尺子散了两处**（Standards 轴）：抽出 `apps/client/src/services/http.ts` 的 `isSuccess`，`api.ts:64/76` 与 `sessionHost.ts:6` 共用；顺手删掉 `api.ts` 对 `SESSION_MESSAGES` 的无用再导出（页面直接 import 类与文案来源，不经过 api）。
- **`SessionError.reason` 形同虚设**（Standards 轴）：`reason` 是排障时唯一能拿到上游英文错误的地方，用例补上断言（`session.test.ts:150-152`：`reason` 是原始 `Error`，message 为 `request:fail timeout`）。
- **注销只清本地、不调服务端 `/logout`**（Standards 轴）：属既定范围。CONTEXT.md 上线决策 11 把「退出登录」整体推迟到 Phase 5，本票只做「注销后本地状态被清空，且不会自动重登」；`logout()` 目前仅测试引用，Phase 5 做退出登录 UI 时再连同服务端 `/logout` 一起接。
- **媒体 GET 免 token**（Spec 轴）：不是本票缺口。票据 03 已裁定并写入 CONTEXT.md 上线决策 12：媒体 URL 永不带 token（UUID 即能力凭证 + `Cache-Control: private`），因此「所有请求都带 Bearer」的例外只有这一类，且由服务端侧保证。
- **整族擦除 vs 只删当前用户**（Spec 轴，属票据 04）：已在票据 04 的结票记录与 `apps/server/app/erasure.py` 的注释里记档（MVP 一户一用户；Phase 5 引入多家长后要改成「只删当前用户，家庭留到最后一个成员注销」）。
- **未采纳**：给 `CapturePanel` 也加重试入口——识别失败的重试就是再点一次录制，面板里的会话错误提示配合首页那个重试按钮已可恢复；等票据 09 把录制拆成独立页时再决定要不要就地重试。把「登录中」也做成 UI 状态同样不做：静默登录就是不要 UI，首屏 `loading` 已经覆盖住这段时间。
- **已知遗留（本票不改）**：真实微信环境（`wx.login` 换 code）未在本票跑，证据全部来自主机闭环（typecheck / vitest / 两端构建），真机登录留给人工验收；票据 02 的服务端 `/logout` 目前没有客户端调用点（见上）。
