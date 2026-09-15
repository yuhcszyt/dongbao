# 10: 注销账号（客户端流程）

**What to build:** 微信平台合规要求的入口在客户端落地。家长在宝宝档案页底部找到「注销账号」，点击后先看到二次确认，明确列出会被永久删除、不可恢复的内容：宝宝档案、全部记录、语音和照片。

确认后调用注销接口，服务端照常删干净（由 04 保证），客户端负责收尾：注销完成后回到一个干净的初始状态，**不把用户静默重登成一个新账号**——否则家长会以为注销没生效。注销请求失败时给一句中文提示，账号不会停在「删了一半」的状态。

**Blocked by:** 04、07（需要 04 的真实注销行为与 07 的档案页承载入口）

**Status:** done (本票提交)

- [x] 宝宝档案页底部有「注销账号」入口 —— `apps/client/src/pages/profile/index.vue:74-78`（`danger` 区块：说明文案 + 按钮），样式 `:130-135`
- [x] 点击后先出现二次确认，文案明确列出宝宝档案、全部记录、语音和照片会被永久删除且不可恢复 —— `apps/client/src/pages/profile/index.vue:80-91`：浮层标题「确认注销账号？」、副文案「确认后会立即删除，且不可恢复：」、`danger-list` 逐条列出「宝宝档案（昵称、生日、性别）」「全部记录（…十类，含手动补记）」「已上传的语音和照片」；入口旁也有一句同样的说明（`:76`）
- [x] 需要明确确认才会真正调用注销接口，误触不会执行 —— 点入口只是 `confirmingDelete = true`（`:77`），唯一调 `recordStore.deleteAccount()` 的地方在 `confirmDelete()`（`:31-36`），它只挂在「确认注销，永久删除」按钮上（`:88`）；浮层还提供「取消」（`:90`）
- [x] 注销成功后小程序回到干净的初始状态，不会自动静默重登成新账号 —— `apps/client/src/features/record/store.ts:198-213`：成功后才 `reset()`（`:187-196`，`baby/records/summary/deleted` 全清、`summaryDate` 回到今天）并置 `accountDeleted = true`，再 `session.logout()`（`session.ts:149-156` 进 `signed-out`）；`load()` 开头 `if (state.accountDeleted) return`（`store.ts:75`）让后续进入页面不再触发重登。三个页面都渲染「账号已注销」的终态：档案页 `:42-46`、首页 `home/index.vue:47-52`、记录页 `record/index.vue:111-115`
- [x] 注销请求失败时显示中文提示，账号与本地状态不会被留在半删状态 —— `store.ts:203-206`：`api.deleteAccount()` 抛错时走 `fail(reason)`（`errorText` 只用 `ApiError`/`SessionError` 自带中文，其它给兜底，`store.ts:14-15`）后立刻 `return false`，**本地一项都不动**；档案页收到 `false` 只关浮层（`profile/index.vue:33-34`），`baby` 与登录态原样留着，可以直接再点一次
- [x] 注销后本地状态已被清空（沿用 05 的会话模块行为）—— `reset()` + `session.logout()`（同上）；`store.test.ts:79-95` 断言 `baby/records/summary/deleted` 清空、`logout` 调用一次，`:96-107` 断言注销后再 `load()` 不会重新拉取
- [x] `npm run typecheck`、`npm test`、`npm run build:h5` 通过 —— vue-tsc 无输出；vitest `5 files / 37 passed`（新增 `store.test.ts` 6 条）；`build:h5` → `DONE Build complete.`

## Comments

**落点**

- 注销的「谁来做」分得很干净：`api.deleteAccount()`（`services/api.ts:116-119`，`DELETE /auth/me`，走 `session.run`）只发请求；`recordStore.deleteAccount()`（`store.ts:198-213`）决定「服务端成功才动本地」，页面只负责问一声「确定吗」。因此「失败不停在半删状态」不需要页面配合，是 store 的结构决定的。
- `accountDeleted` 是显式的状态位，不是一个「本地恰好是空的」的推断：注销后 `state.baby === null` 与「新用户还没建档」长得一样，但前者不能去拉数据（`load()` 早退）也不能重登，后者必须去拉。三页的第一屏都按这个状态位渲染「账号已注销」，而不是又回到建档引导。
- 「已注销」不给重试入口：`fail()`（`store.ts:69-73`）给 `retryable` 加了 `reason.code !== 'signed_out'` 的条件——重登已被主动禁止，那个「重试」按钮点下去只会再得到同一句提示。
- 会话模块本身没有改动（`session.logout()` 在票 05 就绪），本票只是第一次把它接到 UI 上。

**测试先行**

先写 `apps/client/src/features/record/store.test.ts`（`@/services/api` 整体替身，替身里定义同一份 `ApiError`/`SessionError` 类，保证 store 的 `instanceof` 判断语义不变），其中 3 条注销用例在 `deleteAccount` 还没有实现时就存在；随后补 `accountDeleted` 状态位与 `load()` 早退转绿。用例覆盖：成功清空、成功后不再拉取、失败保持原样、已注销会话不给重试入口、登录过期仍给重试入口、上游英文错误不上屏。

**审查与处置（与 07/08/09 合并为整批两轴复审）**

两轴只读复审（Standards `del_mu3bli1y_qlqz`、Spec `del_mu3bllu8_omp6`）后已处置：

- **注销后 `reset()` 会把 `accountDeleted` 清回 false**（Standards 轴）：`reset()` 是任何调用方都能碰的清理入口，一旦被调到，「已注销」这道屏蔽就无声失效、下一次 `load()` 又会拉取。现在 `reset()` 不再动 `accountDeleted`（`store.ts:190` 起改为注释说明「只由 `deleteAccount()` 置上」），用例侧改为在 `beforeEach` 里显式复原这份冷启动起点（`store.test.ts:69-72`，附原因注释）。
- **「账号已注销」文案三处重复且自相矛盾**（Standards 轴）：原文案写「不会再自动登录」，但冷启动时 `session.restore()` 没有 token 会走 `signInOnce()` 静默新建空账号。抽出 `apps/client/src/components/AccountGone.vue`，首页（`home/index.vue:47`）、档案页（`profile/index.vue:42`）、记录页（`record/index.vue:111`）共用一份，文案改为「宝宝档案、全部记录、语音和照片都已永久删除，旧数据无法恢复。下次进入小程序会开始一个新的空账号。」——把「不会静默重登成新账号」的承诺换成能兑现的那句（票 10 验收第 4 条问的是**注销成功后**回到干净初始状态，这一点由 `session.logout()` + `accountDeleted` 保证）。
- **`loadSummary` 是全 store 唯一没有 `try/catch` 的取数函数**（Standards 轴必修）：promise rejection 无人接，`summaryDate` 已跟手新日期而数字还是旧的。现在 `loadSummary`（`store.ts:60-71`）catch → `fail(reason)` 且 `summaryDate` 保持旧值；记录页用 `summaryReady`（`record/index.vue:28`，`state.summaryDate === day && !state.error`）决定显不显示数字，取不到时显示中文提示而不是假数字。
- **`load()` 里记录列表一失败就跳过指标拉取**（Spec 轴）：旧写法 `state.records = await api.records(...)` 抛出后直接进 catch，首页会在新的一天继续显示上一天的数。现在两趟分开并行走（`store.ts:75-84`，`Promise.all`），任一趟失败都只影响自己：记录失败仍会重新拉指标，指标失败仍然上屏记录；新增两条用例固化（`store.test.ts:112-133`）。
- **未采纳：`ageText` 的空生日文案「生日待完善」**（Spec 轴）：该文案出现在月龄槽位（`{{ ageText(birth_date) }} · {{ genderText(gender) }}`），单独一个「待完善」在那里会读不出是缺哪一项；票 07 的「未填项显示待完善」由档案页三个字段行（`profile/index.vue:47-49` 的 `orPending`）满足，月龄槽位保留更具体的提示。
- **未采纳：让 `deleteAccount()` 绕开会自动重登重放的 `session.run`**（Spec 轴）：注销是要鉴权的删除请求，401 时先重登再删是对的行为（拿不到身份就没法删）；「注销后不会再静默重登」由 `accountDeleted` 早退（`store.ts:75`）与 `session.logout()` 保证，不需要在请求层再开一条旁路。
- **未采纳：注销后跳回首页 / 重新 `reLaunch`**：注册页与首页都已是「已注销」终态，多一次跳转反而像又进了一个新账号。
- **未采纳：在服务端加 `DELETE /auth/me` 的软删除开关**：票 04 已按「永久删除」实现（`apps/server/app/erasure.py`），合规文案与实现一致，不加中间态。
- **已知遗留**：`store.test.ts` 里的 `ApiError` / `SessionError` 仍是替身类（`vi.mock` 工厂内定义），不是真实类；它保证了 `instanceof` 语义一致，但真实类新增字段时不会自动跟上（`session.test.ts` 走的是真实会话模块，能盖住一部分）。真实微信环境下「注销 → 重进小程序」的完整往返只在主机闭环（typecheck / vitest / 构建）验证过，真机往返由人工验收确认（与 02/05 的遗留同类）。
