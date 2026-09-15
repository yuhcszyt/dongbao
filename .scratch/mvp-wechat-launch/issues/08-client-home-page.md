# 08: 首页（原型 01）

**What to build:** 家长打开小程序的第一眼要回答「宝宝现在怎么样」。按原型 01：宝宝行（点进宝宝档案页）、问候语、今日记录指标（奶量、睡眠分钟、尿布次数、辅食次数）、快速记录入口、最近 3 条动态（「查看全部」跳记录页）。

今日指标必须明确说明它只代表「已记录的内容」——没记录不代表没发生，家长不该把它当成真实摄入量。指标继续用现有的 `daily-summary?date=&timezone=` 接口，参数携带客户端本地日期与时区，不新增接口。首次进入且家庭里还没有宝宝时，这里要把家长引导到建档。

首页第一目标是「宝宝现在怎么样」，因此 AI 对话、哭声监测、文章推荐、统计图表区块一律不出现。新增、修改、删除、撤销一条记录后，今日指标要自动更新，不需要手动刷新。

**Blocked by:** 06、07（宝宝行要跳档案页，首次进入要引导建档，两者都由 07 交付）

**Status:** done (本票提交)

- [x] 首页展示宝宝行、问候语、今日四项指标、快速记录入口、最近 3 条动态 —— 宝宝行 `apps/client/src/pages/home/index.vue:56-64`；问候语 `:65`（文案来自 `apps/client/src/features/record/domain.ts:205`）；四项指标 `:67-79`；快速记录 `:81-90`；最近 3 条 `:17`（`state.records.slice(0, 3)`）+ `:94-105`
- [x] 点宝宝那一行进宝宝档案页 —— `pages/home/index.vue:56`（`@click="openProfile"`）→ `:26`（档案页不是 tab 页，所以用 `uni.navigateTo`，`switchTab` 会跳不动）
- [x] 点「查看全部」跳记录页 —— `pages/home/index.vue:97` → `:29-32`（`uni.switchTab({ url: '/pages/record/index' })`）
- [x] 今日指标旁明确说明「仅代表已记录内容」—— `pages/home/index.vue:78`：「仅统计已记录内容，没记录不代表没有发生。」
- [x] 快速记录可从首页一键开始：录音、拍照，或直接进入某个记录类型 —— `pages/home/index.vue:86`（语音或拍照 → `{ kind: 'capture' }`，记录页打开录音/拍照面板）、`:88`（六个类型直达新增表单）；接力方式：`apps/client/src/features/record/quickAction.ts`（意图取走即清空）+ 记录页 `apps/client/src/pages/record/index.vue:84-89`（`onShow` 里 `takeQuickAction()` 后开面板 / 开表单）
- [x] 新增 / 修改 / 删除 / 撤销一条记录后回到首页，指标是新的 —— 首页 `onShow` 每次都重新取数（`pages/home/index.vue:35`）；且显式传「今天」：`recordStore.load(today)` → `apps/client/src/features/record/store.ts:69-77`（`load(date = state.summaryDate)`，默认沿用记录页翻到的那天，首页则强制今天），避免记录页停在昨天时把首页也带到昨天。记录页的新增/修改/删除/撤销都走 `load()`（`store.ts:137`（`saveRecord`）、`:153`（`removeRecord`）、`:165`（`restoreRecord`））
- [x] 首页不出现 AI 对话、哭声监测、文章推荐、统计图表区块 —— 页面只渲染上面四块（`pages/home/index.vue:38-105`），没有 AI / 哭声 / 文章 / 图表组件引用
- [x] 家庭里还没有宝宝时，首页引导到建档而不是空白 —— `pages/home/index.vue:47-53`（无宝宝时的引导卡 + 「去建档」按钮 → 档案页）
- [x] `npm run typecheck`、`npm test`、`npm run build:h5` 通过 —— `vue-tsc --noEmit` 无输出；`vitest` 25 passed / 4 files（较上票 +5：`domain.test.ts` 4→7、新增 `quickAction.test.ts` 2）；`uni build h5` → `DONE Build complete.`

## Comments

**落点**

- `daily-summary` 现在带上客户端本地时区：`apps/client/src/services/api.ts:116-123`（`date` + `timezone` 两个参数）。时区名的来源是 `apps/client/src/features/record/domain.ts:217-225` 的 `timeZoneName` / `detectTimeZone`：服务端默认就是 `Asia/Shanghai`，「拿不到时区」时退回同一个默认值，因此行为与不带参数时一致（小程序逻辑层没有 `Intl`，不能假定取得到）。服务的入参由票据 03 定下（`apps/server/app/record/routes.py:233`：`date` 与 `timezone` 两个 query，时区非法回 422「时区名称无效」）。
- 首页展示用的两个纯函数进了 domain 并配用例（`domain.test.ts:35-57`）：`recordTimeText`（`domain.ts:198-203`，记录页那份本地 `timeText` 同时删掉，`pages/record/index.vue:131` 改用共享实现）、`greetingFor`（`domain.ts:205-212`，覆盖 0-23 点，五段文案）。
- 「快速记录」需要跨页传意图，而 `uni.switchTab` 不能带参数：新增 `apps/client/src/features/record/quickAction.ts`（`requestQuickAction` / `takeQuickAction` / `hasQuickAction`，取走即清空）+ 单测 `quickAction.test.ts`（2 例：放/取即清空、带记录类型进表单）。意图只生效一次，回记录页不会重复弹面板。
- 首页 `onShow` 强制按「今天」取指标（`pages/home/index.vue:35` + `store.ts:69`），这是「记录页停在别的日期时首页仍显示今天」的那道保险；票据 09 让记录页按选中日期取指标后，这条保险才开始真正起作用。

**范围裁定**

- 今日指标沿用现有的 `daily-summary` 接口，不新增接口；四项指标就是接口给的四项（奶量 ml / 睡眠分钟 / 尿布次数 / 辅食次数）。
- 问候语用 `greetingFor(本地小时)`，只分时段，不按宝宝档案或天气做个性化（原型 01 的文案「早上好，陪宝宝慢慢长大」作为早间文案保留）。
- 「最近动态」只显示 3 条且点任意一条进记录页（不在首页做编辑 / 删除）——首页是「看」的页面，干活在记录页。

**已知遗留（本票不改）**

- 真实微信环境未验，证据来自主机闭环（typecheck / vitest / build:h5），真机验收留给人工。
- 首页与记录页都会调 `load()`：底部 tab 来回切会各拉一次（没有缓存失效层）。MVP 接受，等有实测的卡顿再加缓存。
