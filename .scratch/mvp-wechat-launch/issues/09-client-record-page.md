# 09: 记录页（原型 03）

**What to build:** 真正干活的那一页。按原型 03：顶部 7 天日期条 + 可跳任意日期的日期选择器 + 类型筛选（全部 / 喂奶 / 辅食 / 睡眠 / 排便 / 尿布）+ 当日时间线 + 点按编辑 + ＋添加。

切换日期后看到的是**那一天**的时间线，而不是全部记录，这样补记昨天的事才顺手。筛选与日期选择可叠加；筛选到某一类但没有记录时是「还没有这类记录」的空状态，不是一片空白。日期过滤按 spec 的决定走客户端本地日期（不给记录列表接口加 `from` / `to` 参数），这是明确接受的取舍。

记录的十类新增、编辑保存、删除后底部撤销、语音 / 拍照草稿确认后才进时间线、媒体播放与预览都已存在于搬过来的实现里，本票要把它们收进新的页面结构并补齐状态与适老要求。这一页的照护者可能是爷爷奶奶辈，因此日期条与筛选条的点击区必须够大（≥48px 高）、文字够大。

**Blocked by:** 06（页面骨架与搬迁后的记录页由 06 交付）

**Status:** done (本票提交)

- [x] 顶部有 7 天日期条，并能通过日期选择器跳到任意一天 —— `apps/client/src/pages/record/index.vue:125-136`（`day-bar`：`scroll-x` 的 7 天按钮 + `picker mode="date" :end="today"` 的「选日期」）；条带内容来自 `buildDateStrip(7, day)`（`apps/client/src/features/record/domain.ts:126-133`，`dayLabel` 给「今天/昨天/周X」）
- [x] 切换日期后时间线只显示那一天（按客户端本地日期过滤），筛选与日期选择可叠加 —— `apps/client/src/pages/record/index.vue:22-23`：`dayRecords = recordsOnDay(state.records, day.value)` 再叠加 `filter`；`recordsOnDay` 用 `dayKey(occurred_at)` 比较**客户端本地**日期（`domain.ts:135-136`），规则由 `domain.test.ts` 的「时间线只显示选中那一天」覆盖（含 22:30 边界与解析不了的时间）。记录列表接口未加 `from`/`to` —— `apps/client/src/services/api.ts:94` 仍只调 `GET /babies/{id}/records`
- [x] 类型筛选覆盖全部 / 喂奶 / 辅食 / 睡眠 / 排便 / 尿布 —— `apps/client/src/pages/record/index.vue:158` 渲染「全部」+ `RECORD_TYPES` 十类（前六类即票据要求的那六项）
- [x] 筛选到某一类且无记录时显示「还没有这类记录」的空状态 —— `record/index.vue:24` 的 `emptyText`（`all` 时是「这一天还没有记录」，某一类时是「还没有这类记录」），渲染在 `:160`
- [x] 点时间线任意一条进入编辑，保存后列表与首页今日指标同步更新 —— `record/index.vue:57-64`（`saveRecord` → 成功后 `recordStore.load()`，指标与列表一起重取；编辑入口 `:172` 的「修改」）；首页 `apps/client/src/pages/home/index.vue:35` 每次 `onShow` 用 `load(today)` 重新取
- [x] ＋按钮可新增十类记录（喂奶、辅食、睡眠、排便、尿布、哭闹、身高体重、疫苗、用药、自定义）—— 右下角 `＋`（`record/index.vue:177`）按当前筛选的类型调 `openManual()`；表单里 `apps/client/src/components/RecordForm.vue:165-169` 列出全部 `RECORD_TYPES` 十类，仅在编辑既有记录时 `:disabled="lockType"`
- [x] 语音或拍照生成的是待确认草稿，确认后才成为记录，不直接进时间线 —— 沿用 `apps/client/src/components/CapturePanel.vue` 的两阶段流程：`api.draftFromMedia` 只拿草稿，页面只在 `@saved` 时 `recordStore.load()`（`record/index.vue:93-96`），未确认的草稿不进 `state.records`
- [x] 识别未配置或失败时仍给出可手动填写的草稿，且上传的语音 / 照片不丢失
  - **断链已修**：`apps/server/app/record/providers.py:17-19` 的 `_secret()` 原来读的是未定义变量（`NameError: name 'value' is not defined`），现在 `value = os.environ.get(name, "")`，缺凭证时照旧抛 `ProviderUnavailable`，被 `app/record/routes.py:162` 捕获成「保留媒体 + 可编辑草稿」。
  - **新增服务端用例**：`apps/server/tests/test_draft_without_credentials.py`（`:76` 语音、`:96` 拍照），配 `apps/server/tests/providers-no-credentials.toml`（两个 provider 都开启但指向 `unreachable.invalid`，只抽走凭证）。断言 201 + `status == "draft"`（`:39/:55`）+ 媒体仍可取回 + 确认草稿后媒体不丢（`:92`）+ 响应里没有上游错误原文。红→绿记录见下。
  - 未动 provider 的超时 / 签名 / 重试行为。
- [x] 删除一条记录后页面底部立刻可撤销 —— `record/index.vue:174` 的 `undo` 条（`state.deleted` 存在即出现）+ `apps/client/src/features/record/store.ts` 的 `removeRecord` / `restoreRecord` / `dismissUndo`
- [x] 记录里的语音可播放、照片可预览，且鉴权之后仍能正常打开 —— `record/index.vue:78-90`（图片走 `uni.previewImage`，语音走 `uni.createInnerAudioContext`），URL 经 `mediaUrl()` 拼接；媒体 GET 免 token 是 CONTEXT.md 上线决策 12（UUID 即能力凭证）
- [x] 加载中 / 加载失败 / 无数据三种状态都有明确中文提示 —— `正在加载…`（`:109`）、错误横幅 + 「重试」（`:159`）、空状态文案（`:160`）
- [x] 日期条与筛选条点击区高度 ≥48px，文字可读性满足适老要求 —— 日期按钮 `min-height: 62px`（`record/index.vue:227`），筛选按钮 `min-height: 52px` / `font-size: 16px`（`:223`），日期条数字 19px 加粗、星期/今天 14px（`:229-230`）
- [x] `npm run typecheck`、`npm test`、`npm run build:h5` 通过 —— vue-tsc 无输出；vitest `4 files / 31 passed`；`build:h5` → `DONE Build complete.`；服务端 `pytest -q` → `40 passed`

**日期过滤放在客户端的取舍**：`GET /babies/{id}/records` 仍然返回全部记录，记录页在内存里按本地日期分组。spec 已明确接受这个取舍（不给列表接口加 `from` / `to`），MVP 的记录量在一个家庭可接受范围内；它的好处是「补昨天的记录」不需要回源，切换日期是瞬时的。

## Comments

**落点**

- 日期条的日期算术放在 domain 纯函数里，页面只做渲染：`shiftDate`（`domain.ts:105`）、`dayKey`、`dayLabel`（`:113`）、`buildDateStrip`（`:126`）、`recordsOnDay`（`:135`）。这样「今天 / 昨天 / 周X』的边界、跨月、以及 `occurred_at` 解析不了的情况都能用 vitest 钉住，不需要跑界面。
- `pickerValue` 从 `ProfileForm.vue` 提到 `domain.ts:122`，档案页与记录页的日期选择器共用一份取值逻辑（H5 与小程序都把选中值放在 `detail.value`），`domain.test.ts` 覆盖「取不到就当没选」。
- 记录页 `onShow` 现在传当前选中日：`recordStore.load(day.value)`（`record/index.vue:99`），`load(date = state.summaryDate)`（`features/record/store.ts`）。首页则显式传「今天」——记录页停在昨天时，首页的今日指标不能被带偏。
- `＋` 按当前筛选的类型预选（`filter === 'all'` 时用上一次用过的类型），十类仍可在表单内改。

**红→绿（测试先行）**

1. 先写 `domain.test.ts` 的四组断言（日期条 7 天含「今天」标签、跨月位移、按本地日期过滤含 22:30 边界、`pickerValue`），`vitest` 报 `2 files failed / 3 tests failed`（`buildDateStrip`、`recordsOnDay`、`pickerValue`、`timeZoneName` 尚未实现）。
2. 再写服务端用例 `test_draft_without_credentials.py`，未修 `providers.py` 时红得很难看：`apps/server/app/record/providers.py:18` 抛 `NameError: name 'value' is not defined`，经 `app/record/routes.py:160` 的 `transcribe_audio(...)` 冒泡成 500（`routes.py:162` 那组 except 里没有 `NameError`）。这条红正是票据里说的「`make test` 全绿却仍然坏」。
3. 修 `_secret()` 后该用例转绿，服务端 `38 → 40 passed`。

**处置**

- 票据里点的「先修的断链」只动了 `_secret()` 一行；`transcribe_audio` / `extract_draft` 的错误分类、超时、签名逻辑一律没碰（本票范围）。
- 媒体「鉴权之后仍能正常打开」不靠客户端补 token，而是服务端媒体 GET 免 token + UUID 即凭证（CONTEXT.md 上线决策 12）——客户端 `mediaUrl()` 只做基址拼接，没有第二套鉴权路径。
- 适老要求按「点击区 ≥48px」的硬指标落到样式：日期按钮 62px、筛选按钮 52px、＋ 固定按钮 62px；文字最小 14px（日期条星期标签），正文 16px 起。
- 未采纳：给草稿面板再加一条就地重试入口（再点一次录制即可重来，与票据 05 的裁定一致）；把日期条做成「无限横滑」（目前固定 7 天 + 日期选择器跳任意一天，够 MVP 用）。
- 审查：与 07/08 一并在 08–10 完成后的整批两轴复审中复核（本票自身另有一条服务端红→绿证据链）。

---

**两轴复审补齐（2026-09-17，与 07/08/10 合并整批复审）**

Spec 轴（`del_mu3bllu8_omp6`）指出四处并已修，Standards 轴（`del_mu3bli1y_qlqz`）两处已修：

- **日期条锚点应是「今天」，不是「选中日」**（Spec 轴必修）：原来 `buildDateStrip(7, day)` 让条随选中日滚动，跳到过去某天后条上就再没有「今天」这一格，没法一下跳回来。现在 `strip = buildDateStrip(7, today.value)`（`record/index.vue:21`），日期条永远锚在今天；选中日可能是条外的一天（用右侧日期选择器跳过去），这时条上不高亮任何一格，但日期选择器与标题都指着那一天。
- **时间线整条可点进编辑**（Spec 轴必修，验收第 5 条原文是「点时间线任意一条进入编辑」，原文只有「修改」按钮）：卡片本体加 `@click="openEdit(record)"`（`record/index.vue:176`），卡内按钮与媒体按钮全部改 `@click.stop`（`:181` / `:184`），避免点按钮顺带打开编辑。
- **一条记录多份媒体时只有第一份能点**（Spec 轴）：`openMedia` 原来写死 `record.media?.[0]`。现在逐份渲染按钮（`record/index.vue:180-182`，`mediaLabel` 负责多份时编号「第 N 份」、单份时沿用「语音来源」），`openMedia(record, media)`（`:84-98`）把整条记录的图片一起交给 `uni.previewImage`（横滑看完），语音播点中的那一份。
- **`today` / `greeting` 跨零点失效**（Spec 轴）：`home/index.vue:15-16` 与 `record/index.vue:18` 原来只在 setup 求值一次。现在都是 `ref`，并在 `onShow` 里重算、顺带把「今天」交给 `load()`；记录页的 `dayText` 也直接复用 `dayLabel(day, today)`，不再自己再判一次「今天」。
- **记录列表失败会跳过指标拉取**（Spec 轴）：见票据 10 的同一处处置（`store.ts:75-84` 两趟并行 + `store.test.ts:112-133` 两条用例）。本票「保存后列表与首页指标同步更新」的可恢复性依赖它。

**第二轮两轴复审（Standards `del_mu3bu415_tibi` / Spec `del_mu3bub3w_9hye`）后并入 `ecd2e71`**

- **`summaryReady` 是从 store 内部状态反推的**（Standards 轴必修）：原来 `state.summaryDate === day && !state.error`，等于把「这段数字是不是这一天的」交给页面自己猜。现在 `summaryReady = recordStore.summaryFor(day.value) !== null`（`record/index.vue:28`），数字只在它真属于这一天时上屏；`loadSummary` 加竞态守卫（`store.ts:60-71`）——连点两个日期、先发的请求后到也不会把数字挂到后一天，用例见 `store.test.ts`。
- **重试要重拉的是「这一天」**（Standards 轴）：`retrySession(day?: string)` 现在接收日期（`store.ts:57-63`），记录页两处重试按钮都传当前选中日（`record/index.vue:172` / `:216`），不再是「重登后拉今天」。
- **建档引导去重**（Standards 轴）：记录页的 `onboarding` 块与 `createProfile` 删掉，换成共用的 `CreateBabyGate`（`record/index.vue:129`），`.onboarding` / `.baby-mark` 样式一并删（`.avatar` 独立成一条规则，记录页的头像在 flex 行里）。
- **快速记录的类型清单写死了「前 6 类」**（Standards 轴）：改用 `domain.ts` 的 `QUICK_RECORD_TYPES`（`record/index.vue:172`）。

**第二轮 Spec 轴（`del_mu3bub3w_9hye`）结论与处置**

- **旧错误文案会挡住新一天已拉到的指标**（Spec 轴，低）→ 已随 `summaryFor` 一并解决：`summaryReady`（`record/index.vue:31`）不再看 `state.error`，新一天的数字照常上屏；错误横幅只描述它自己那次失败（记录列表或指标），请求重试才清。
- **「某一天的时间线而非全部记录」只在 UI 层成立**（Spec 轴，中）→ **未采纳**：本票 What to build 原文写着「日期过滤按 spec 的决定走客户端本地日期（**不给记录列表接口加 `from` / `to` 参数**），这是明确接受的取舍」，服务端 `list_records`（`routes.py:200-206`）只有 `record_type` 一个参数是照着这条决定做的。客户端拉全量后按本地日期过滤（`record/index.vue:26`）是既定设计，不是漏做；记录量真到需要分页时另开票据（服务端加 `date` 参数等价于推翻本票的取舍，得先改 spec）。
- **新用例依赖 Makefile 注入的 `MEDIA_ROOT`**（Spec 轴，低，测试环境一致性）→ 已修：`apps/server/tests/conftest.py` 新增 autouse 夹具 `media_root_in_tmp`（`tmp_path` 下的临时媒体根），裸跑 `pytest tests/test_draft_without_credentials.py -q` 也 2 passed，不再落到容器里的 `/app/data/media`。
