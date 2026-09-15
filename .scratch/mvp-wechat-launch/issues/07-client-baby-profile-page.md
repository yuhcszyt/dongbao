# 07: 宝宝档案页（建档 / 查看 / 编辑）

**What to build:** 让家长第一次进来就知道怎么开始，之后能看能改。按原型 09，但字段范围收敛为昵称、生日、性别三项（与建档一致；原型里的喂养方式与过敏信息不在 MVP 范围）。

无宝宝时是「先认识一下宝宝」建档流程；已建档时是只读展示，未填项显示「待完善」而不是空白；点「编辑」可改昵称、生日、性别并保存。建档与编辑的校验规则必须一致——不会出现「建档要求填生日、编辑却允许清空」。生日不能被填成未来日期，必填项缺失时在提交前就被挡住并给中文提示，而不是提交成功后再报错。保存失败时中文提示且输入内容不被清空。

**Blocked by:** 06（页面与导航骨架必须先就位）

**Status:** done (本票提交)

- [x] 家庭里没有宝宝时，档案页呈现建档流程，只要求昵称、生日、性别三项 —— `apps/client/src/pages/profile/index.vue:30-35`（`!state.baby` → `onboarding`，里面只有一个 `ProfileForm`）；表单只有这三项：`apps/client/src/components/ProfileForm.vue:49-54`，没有原型的喂养方式 / 过敏信息 / 头像
- [x] 生日可通过日期选择填入，性别可选男宝 / 女宝 / 暂不填，未来日期被拒绝 —— 日期选择器 `ProfileForm.vue:50`（`<picker mode="date" :end="today">`），性别三项按钮 `ProfileForm.vue:53`（男宝 / 女宝 / 暂不填），兜底校验 `apps/client/src/features/record/domain.ts:150`（`if (input.birth_date > today) return '生日不能是未来的日期'`）
- [x] 昵称或生日缺失时提交被前端挡住并给出中文提示 —— `ProfileForm.vue:37-43`：先 `validateBabyProfile(profile)`，有问题写 `localError` 并 `return`（不发请求）；文案来自 `domain.ts:146-151`（`请填写宝宝昵称` / `请填写宝宝生日`）
- [x] 建档成功后立即呈现宝宝昵称、月龄与性别，不需要手动刷新 —— `apps/client/src/features/record/store.ts:96`（`state.baby = await api.createBaby(input)`）→ 页面 `v-else` 分支直接读 `state.baby`：`pages/profile/index.vue:41-42`（`orPending(nickname)` + `ageText(birth_date) · genderText(gender)`）
- [x] 已建档时只读展示昵称、生日、性别，未填项显示「待完善」 —— `pages/profile/index.vue:47-49` 三行只读值 + `domain.ts:85`（`orPending`）/ `domain.ts:87`（`genderText` 的 `unknown` → `待完善`）
- [x] 编辑保存后档案页显示新值 —— `store.ts:108-113`（`saveBaby` → `api.updateBaby(...)` 后把返回值写回 `state.baby`，再 `load()` 复核）；`pages/profile/index.vue:16-21` 保存成功才关浮层
- [x] 编辑与建档使用同一套校验（含「生日不可为空、不可为未来日期」）—— 两者共用同一个 `ProfileForm`（`pages/profile/index.vue:35` 建档、`:58` 编辑），校验只有一处入口 `ProfileForm.vue:37`；分流发生在 store：`store.ts:108-109`（`state.baby` 不存在才走 `createBaby`）
- [x] 保存失败时显示中文提示，输入内容保留，可直接重试 —— 提示 `ProfileForm.vue:55-58`（`localError || props.error` + `retryable` 时给「重试」按钮）；失败时页面不关浮层、不重挂表单（`pages/profile/index.vue:18` 的 `return`），`profile` 是表单内本地 `reactive`（`ProfileForm.vue:25-29`），所以输入留在原地
- [x] `npm run typecheck`、`npm test`、`npm run build:h5` 通过 —— `vue-tsc --noEmit` 无输出（通过）；`vitest` 20 passed（domain 4 / loginCode 3 / session 13）；`uni build h5` → `DONE Build complete.`

## Comments

**落点**

- 新增三个 domain 纯函数并配用例：`validateBabyProfile(input, today = nowParts().date)`（`apps/client/src/features/record/domain.ts:146-151`）、`orPending`（`:85`）、`genderText`（`:87`）；用例 `apps/client/src/features/record/domain.test.ts:19-31`（有效输入 / 空昵称 / 空生日 / 未来日期 / 性别不影响结果）。先红后绿：改 `ProfileForm` 前这三个断言是红的，实现后转绿（4 passed）。
- `store` 新增建档与编辑的统一入口 `saveBaby(input)`（`store.ts:108-116`），按「家里有没有宝宝」决定 `updateBaby` 还是 `createBaby`；`createBaby`（`:92-106`）保留原行为。记录页的建档表单也改走同一入口（`apps/client/src/pages/record/index.vue:31`），避免两页两条写路径。
- `ProfileForm` 成为建档与编辑共用的唯一表单，校验只有一处（`ProfileForm.vue:37`），所以不会出现「建档要求生日、编辑允许清空」的分叉。
- 新增档案页三态：建档（`pages/profile/index.vue:30-35`）/ 只读（`:38-52`）/ 编辑浮层（`:55-62`）；浮层里用 `:key="state.baby.updated_at ?? state.baby.id"`（`:58`）让每次打开都是干净的初始值。同一个机制的另一面：保存失败时 `updated_at` 不变 → key 不变 → 输入不会被重挂清掉。
- 记录页把本地那份 `genderText`（原来 `unknown` → 「暂不填写」）删掉，改用 `domain.ts:87` 的共享实现（`pages/record/index.vue:8`），占位文案统一为「待完善」，与票据 07 验收项 5 的措辞一致。

**未采纳 / 范围裁定**

- 不做「编辑未保存就关闭」的二次确认：MVP 未要求，误触重开一次即可；不想让档案页长出第二套确认交互。
- 档案页不放统计 / 收藏 / 头像上传：CONTEXT.md 上线决策把统计与收藏整体推迟，字段范围也只保留三项。
- 建档表单在档案页与记录页都存在（两页都能建档）：票据 06 的验收项要求记录页承载原有全部能力且已勾选，所以本票只把它们收敛到同一入口与同一校验，不删记录页那一份。

**已知遗留（本票不改）**

- 真实微信环境的建档 / 编辑未验，证据全部来自主机闭环（typecheck / vitest / 两端构建）；真机留给人工验收。
- 两轴只读子代理审查（Standards / Spec，固定点 `5705643`）本轮因看门狗（连续 5 分钟无输出）中断：Standards 轴无产出，Spec 轴产出到验收项 2 即断（已读到的两条均为「已满足」，与上表一致）。本票的证据由主代理逐条对照票据与代码给出，两轴复审并入票据 08-10 完成后的整批 review 一起补做并记档。
