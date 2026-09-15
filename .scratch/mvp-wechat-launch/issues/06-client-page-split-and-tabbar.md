# 06: 页面骨架拆分与底部导航

**What to build:** 把现在的单页实现拆成上线版本的三页结构，并搭好导航。现在是首页和记录时间线挤在同一个页面里，档案页没有独立入口，底部也没有 tab。

本票只做结构与搬迁，不做新功能：页面注册首页、记录页、宝宝档案页三个页面；底部 tab 只保留首页与记录，AI tab 隐藏；把现有单页实现整体搬到记录页并保持行为不变，唯一的变化是取数改走统一网络层（带 token）。首页与档案页先是可导航的空壳，等后续票填内容。

这是一次预重构：先让结构就位，后面三张票各自填一页，互不抢同一份页面注册文件。

**Blocked by:** 05（搬迁后的记录页要能带 token 取数，否则搬过去就跑不起来）

**Status:** done (本票提交)

- [x] 三个页面都在页面注册中可见，底部 tab 只有首页与记录，AI tab 不出现 — `apps/client/src/pages.json` 的 `pages` 注册 `pages/home/index`（`:4`）、`pages/record/index`（`:13`）、`pages/profile/index`（`:22`）；`tabBar.list`（`:31`）只有这两项：`pages/home/index`（`:38`，文字「首页」）与 `pages/record/index`（`:42`，文字「记录」）。构建产物 `dist/build/mp-weixin/app.json` 的 `tabBar.list` 同样只有这两项，页面注册三项
- [x] 记录页承载原有全部记录能力（建档、十类记录新增、时间线、编辑、删除撤销、语音与拍照草稿、汇总），行为与拆分前一致 — `apps/client/src/pages/record/index.vue`：建档 `ProfileForm`（`:99`）、语音 / 拍照草稿 `CapturePanel`（`:148`）、十类新增与编辑 `RecordForm`（`:151`，`openManual` / `openEdit` 决定新增或改）、时间线列表（`:129`）、删除与底部撤销（`remove` `:55` / `restore` `:64` / 撤销条 `:144`）、汇总四项（`:105`）。业务逻辑逐行来自原 `apps/client/src/pages/index/index.vue`（已删除），只把状态与取数换成共享 store
- [x] 记录页所有请求走统一网络层，页面内无手写鉴权 header — 页面只调 `recordStore`（`store.ts:64 load` / `:92 createBaby` / `:108 saveRecord` / `:125 removeRecord` / `:137 restoreRecord`），store 只调 `@/services/api` 的 `api.*`，凭证仍只有 `session.run` 一个来源；`grep -rn "Authorization|Bearer" src/pages src/components src/features` 无命中
- [x] 首页与档案页是可导航的空壳页面，不是白屏报错 — `apps/client/src/pages/home/index.vue`（含跳记录页的 `uni.switchTab`）与 `apps/client/src/pages/profile/index.vue`，两者都是正常渲染的说明页，`npm run build:h5` 与 `npm run build:mp-weixin` 均通过
- [x] `npm run typecheck`、`npm test`、`npm run build:h5` 通过 — 见下方 Comments 的回归记录
- [x] 本票不新增记录页的原型 03 形态（日期条、类型筛选等），留给后续票 — 记录页的筛选仍是拆分前的十类横向筛选（`index.vue:127`），没有 7 天日期条、没有日期选择器、没有「全部 / 喂奶 / 辅食 / 睡眠 / 排便 / 尿布」收敛，全部留给票据 09

## Comments

2026-09-16 实施记录（agent）。`npm run typecheck` 无错、`vitest` **17 passed**、`npm run build:h5` 与 `npm run build:mp-weixin` 均通过（服务端本票未改）。

落点：

- `apps/client/src/features/record/store.ts`（新增）：宝宝 / 记录 / 某日汇总的共享状态，加 `load` / `loadSummary` / `retrySession` / `createBaby` / `saveRecord` / `removeRecord` / `restoreRecord` / `reset`。引入它不是为了本票，而是为了不让两页各存一份：票据 08 要求「记录页改一条记录，回到首页今日指标已经是新的」，票据 09 要求「保存后列表与首页今日指标同步更新」，两处都需要单一数据源。
- `apps/client/src/components/ProfileForm.vue`（新增）：把建档表单从单页里抽出来。抽早了不是范围外——它在 `RecordForm` / `CapturePanel` 的同一层（`components/`），且票据 07 的档案页要复用同一套字段与校验；留在记录页里下票就得复制一遍。
- `apps/client/src/pages/record/index.vue`（新增，承载原单页内容）、`pages/home/index.vue`（新增，壳）、`pages/profile/index.vue`（新增，壳）、`pages.json`（三页 + 两项 tabBar）、`src/pages/index/index.vue`（删除）。
- 取数时机从 `onMounted` 改成 `onShow`（`index.vue:87`）：tab 页在切换时不会重新挂载，用 `onMounted` 会让「在别的页改完记录回来看不到」变成新 bug。首次进入与拆分前等价，额外代价是每次切回记录页多一次列表请求。
- 记录页暂时保留了「今日汇总」四项（`index.vue:105`），与本票「保持行为不变」一致；票据 09 按原型 03 收口这一页时，这块要么跟着选中日期走、要么搬去首页，届时一并定。

