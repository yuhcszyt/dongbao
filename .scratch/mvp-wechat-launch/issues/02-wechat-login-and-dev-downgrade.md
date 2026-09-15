# 02: 微信登录接口上线 + 开发降级

**What to build:** 家长侧的第一块地基——凭证签发。客户端拿 `wx.login` 的 code 调 `POST /api/v1/auth/wechat`，服务端用 code 换 openid，首次登录创建一个家庭与一个用户，再次登录复用同一用户，返回 30 天 token 与 `user_id`。契约不变：入参 `code`，出参 `token` + `user_id`。

同时给出开发降级开关：仅当显式设置 `DEV_LOGIN=1` 时跳过 jscode2session，把 code 直接当 openid 用；未设置时保持现有行为（缺 `WECHAT_APPID` / `WECHAT_SECRET` → 502 `wechat_login_failed`）。启动日志必须打印当前处于哪种模式，生产环境默认关闭。

**Blocked by:** 01（登录接口必须先真的被挂载）

**Status:** ready-for-agent

- [ ] 同一 code 调两次登录接口，得到同一个 `user_id`，且两次登录后属于同一家庭
- [ ] 两个不同 code 登录得到的 `user_id` 不同、家庭不同
- [ ] 返回的 token 里不含任何明文隐私字段，服务端不持久化会话（不引 Redis、不建会话表）
- [ ] 未设置 `DEV_LOGIN` 且缺微信凭证时返回 502 `wechat_login_failed`，文案不含任何上游原始错误细节
- [ ] 显式设置 `DEV_LOGIN=1` 后，任意字符串作 code 均可登录成功
- [ ] 启动日志明确打印当前登录模式（真实 / 开发降级）
- [ ] 登录接口的失败响应仍是统一错误信封，并带 `request_id`
