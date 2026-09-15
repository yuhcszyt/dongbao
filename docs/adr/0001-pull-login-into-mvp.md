# ADR 0001: 登录体系提前进入 MVP 范围

- 状态: 已接受（2025-09-15，grill 达成定稿）
- 决策人: 项目负责人 + AI

## 背景

PRD(`docs/requirement/00-dongbao-override.md`)将用户体系/多用户隔离排在 Phase 5，记录功能开发期用硬编码 `FAMILY_ID` 常量代替鉴权。MVP 要上线微信小程序，没有账号意味着：所有用户共享同一份数据，任何人可读写任何人的宝宝记录——安全与隐私上不可接受。

## 决策

把"微信登录 + 家庭数据隔离"从 Phase 5 **提前到 MVP**：

- `wx.login` code → `jscode2session` 换 openid → 登录即注册，无密码无手机号
- 新增 `users`（openid 唯一）、`families` 两张表；`baby/record/media` 的 `family_id` 挂到真实 Family 上
- 删除 `FAMILY_ID`/`USER_ID` 硬编码常量，所有接口经 Bearer token 解析 family_id
- 一个账号一个宝宝：UI 不做多宝宝切换，但 Family/Baby 表结构天然支持 Phase 5 的家庭共享扩展
- 家庭共享/多家长/权限**仍留 Phase 5**，不在本次范围

## 冲突声明

与 PRD Phase 划分冲突的部分：仅"登录+数据隔离"提前。Phase 5 剩余内容（家庭共享、协作记录）不变。

## 后果

- 正面：上线即数据隔离；Family 表先行，Phase 5 平滑扩展
- 代价：微信小程序合规要求随之而来——必须提供注销账号入口（已纳入范围）、隐私政策（已安排起草）
