# 前端联通、雾紫主题与老人快捷记录

更新：2026-09-23

## 已实现

- 保留页面模块顺序及原生四项导航；使用共享雾紫暖白色值，统一页面、表单、弹层、选中态，重新生成原生导航图标。快捷操作与追问按钮放大，错误状态保留语义颜色。
- 首页及记录页点语音直接录音，说完点“说完了”；点拍照直接打开相机。识别充分则自动保存，不再显示草稿确认表单；成功卡片提供查看、修改和完成。
- 信息不足进入懂宝 AI，通过文字或继续说话补充同一草稿；待补充事项持久化，可重进页面继续。照片、转写、追问和保存摘要进入会话，正式记录可从会话打开修改。
- 同一媒体识别去重，补充请求携带稳定 request_id，保存记录和会话消息同事务提交。取消先查清结果，已保存时明确显示已保存，不谎报取消成功。
- 首页和 AI 页复用录音生命周期；修复重复监听、迟到授权回调、重复提交、上传无超时、发送失败丢输入、旧会话响应覆盖新状态等问题。
- 并发首屏加载共享建档请求，防止重复建档；退出时使旧登录及业务请求失效并清空 AI 缓存。汇总未取到时不伪装为零。
- 小程序构建期拒绝相对接口地址，识别 IPv6 回环地址；H5 上传具备 30 秒超时和中文错误提示。
- 测试使用内存 Qdrant 和禁用外部模型的测试配置，make test 仅需 PostgreSQL 测试容器，不重建镜像。

## 接口与迁移

- 新增 `POST /api/v1/record-drafts/capture`：baby_id、media_id、occurred_at、timezone；返回 needs_input / saved / cancelled、draft_id、conversation_id、question、record、media、transcript。
- 新增 `POST /api/v1/record-drafts/{draft_id}/reply`：request_id，以及 message 或语音 media_id 二选一；同一请求重试不重复落库。
- 新增 `GET /api/v1/record-drafts/pending?baby_id=...`、`POST /api/v1/record-drafts/capture/{media_id}/cancel`、`POST /api/v1/media/{media_id}/transcript`。
- 原有草稿接口保持兼容；自动记录草稿不能绕过新流程调用旧 confirm 接口。
- 迁移 `0007_quick_capture` 为 record_drafts 增加可空 capture_context 和自动采集媒体唯一索引。旧记录不修改。部署新版服务端前，应对目标数据库运行 `alembic upgrade head`；本次仅升级测试库，未部署远端。
- 会话历史的 user structured_payload 新增可选 media/draft_id；原有消息字段兼容。

## 验证证据与边界

- 2026-09-22 本地 `make test`：服务端 **69 passed**（含新增 11 个自动记录测试），当时客户端 89 passed。
- 2026-09-23 收尾后 `make test-client`：类型检查通过，**95 passed**；`npm run build:h5` 通过。
- 覆盖自动保存、照片追问、文字/语音补充、重进恢复、并发去重、事务失败回滚、超时重试、取消、权限错误、H5 迟到授权、账号隔离、日期时区、登出后迟到响应。
- 2026-09-23 重跑 `make test` 被 Docker daemon 不可用阻断；55432 测试库也不可达。此前服务端通过不等于本次重跑成功，见问题 03。
- 本轮未打开浏览器、微信开发者工具或任何前端预览；未截图、未运行前端开发服务器，也未运行小程序构建（遵守本仓库限定的验证手段）。
- 识别回归使用服务替身；未请求真实微信登录、腾讯 ASR 或大模型，不能据此宣称真实识别准确率或真机体验已验收。哭声功能仍为演示。

## 待验收与阻碍

1. [真机权限、相机返回、录音与视觉验收](issues/01-device-acceptance.md)
2. [真实 ASR 与图片识别验收](issues/02-live-recognition.md)
3. [Docker 恢复后重跑服务端回归](issues/03-test-database-offline.md)

原有 .cursor、.cursor-plugin 与部署脚本、环境文件均未修改或纳入本次提交。
