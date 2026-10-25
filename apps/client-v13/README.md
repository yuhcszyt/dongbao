# 懂宝 1.3 · 独立微信小程序前端

根据 `docs/prooduct/dongbao-interactive-prototype1.3.html` 实现的 uni-app / Vue 3 / TypeScript 工程。微信小程序优先，同时支持 H5。与 `apps/client` 独立安装、构建和存储，不修改原有客户端、服务端或原型文件。

## 安装与验证

在仓库根目录执行：

```bash
npm ci --prefix apps/client-v13
make test-client CLIENT_DIR=apps/client-v13
npm run build:mp-weixin --prefix apps/client-v13
npm run build:h5 --prefix apps/client-v13
```

不依赖 Docker、数据库或模型凭据。Agent 仅执行类型检查、Vitest、构建和源码审查。

## 用户自行体验小程序

微信开发者工具导入 `apps/client-v13`，根目录的 `project.config.json` 指向 `dist/build/mp-weixin/`。AppID 沿用现有客户端配置；如果当前微信账号没有该 AppID 的开发权限，需要用户替换为自己有权限的 AppID（同时修改 `src/manifest.json`、`project.config.json`）。

需要监听源码变更时，用户可执行：

```bash
cd apps/client-v13
npm run dev:mp-weixin
```

此时在开发者工具中导入 `dist/dev/mp-weixin/`。Agent 不启动开发服务器、不打开开发者工具、不操控浏览器和截图。

## 页面与交互

- 首页：宝宝卡片、AI 观察示例、语音／拍照入口、11 种手动记录、今日时间线。
- AI：发送与回车提交、推荐问题、语音转写演示、会话本地保存。
- 记录：日／周／月、日期前后切换、分类筛选、统计、日期／时间选择器、输入校验。首页与记录共用数据。
- 哭声：30 秒演示计时、提前结束、重新开始、保存与重复保存保护、历史查看。
- 成长：数据／时间线／里程碑、三种示例曲线、记录身高体重、里程碑勾选。
- 发现：分类与关键词共同筛选、文章阅读、收藏、空结果提示。
- 宝宝档案：昵称及各项档案编辑，保存后恢复。
- 我的：收藏、会话、家庭示例、设置、反馈暂存、CSV／JSON 全部记录复制导出。

## 实现边界

这是可运行的**前端交互工程**，不宣称已经接入真实后端。全局展示演示说明：

- AI 问答、语音转写、照片识别、哭声概率、生长曲线与健康观察均是示例。未调用模型、麦克风或远端识别服务。
- 拍照与相册使用 `uni.chooseImage`，真实图片只用于本次本地预览；生成的是固定示例草稿，用户确认才保存。
- 家庭账号、邀请、微信登录、通知、付款和反馈发送尚未接入；不制造“已邀请／已支付／已发送”的成功提示。
- 初次打开生成当天示例记录；后续仅从独立存储键 `dongbao.client-v13.v1` 恢复。清除小程序缓存会删除本地记录，数据导出可用于留存。
- 导出为剪贴板文本（CSV／JSON），不是 PDF 生成或云端下载。
- 八个逻辑页面使用一个原生页面内的响应式视图及自定义底栏切换，后续可在联调阶段拆分路由；返回按钮与底栏均有明确入口。

## 源码

- `src/pages/index/index.vue`：页面、表单与交互状态；仅使用 uni-app API，不依赖 DOM。
- `src/components/RecordTimeline.vue`：共享时间线。
- `src/domain/model.ts`：记录校验、统计、日期范围、存储解码、导出及搜索。
- `src/domain/chart.ts`：内置演示曲线，不请求远端图片。
- `src/theme.css`：从原型迁移的视觉样式及小程序适配。

## 验收边界

自动验证覆盖类型、记录保存恢复、非法输入、空列表、跨月／跨年／闰年、分类搜索、CSV 安全转义和双端构建。未进行界面目视或真机验收。用户需自行确认：布局与底栏安全区、键盘弹起与弹窗滚动、系统相机／相册授权、图表显示、剪贴板导出及重启后的本地数据恢复。
