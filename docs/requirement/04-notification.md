# SPEC 04｜信息推送

> Phase 4\
> 依赖：Phase 1～3

## 1. Scope

-   消息中心
-   记录提醒
-   成长阶段提醒
-   疫苗 / 体检提醒
-   数据变化提醒
-   育儿文章推荐
-   Push
-   免打扰
-   去重与频控

## 2. 目标

从"用户主动打开懂宝"升级为"懂宝在合适的时候主动陪伴"，但必须少而有价值。

## 3. Notification Types

``` text
record_reminder
growth_stage
vaccine_checkup
data_change
article_recommendation
system
```

## 4. 触发来源

### 定时

例如每日/每周检查成长阶段、记录缺失、内容推荐。

### 业务事件

例如新记录保存后重新计算某些摘要。

### 受控 AI Insight

AI 只能输出候选 insight，必须经过规则校验后才能形成通知。

## 5. Pipeline

``` text
Schedule / Domain Event
→ Candidate Generator
→ Rule Engine
→ Dedup
→ Frequency Limit
→ Quiet Hours
→ Notification
→ Push Provider
```

MVP
不需要复杂消息队列；后台任务可先使用简单可靠的调度机制。规模增长后再升级。

## 6. 数据模型

``` text
notification
id
family_id
baby_id
type
title
body
payload JSONB
priority
status
scheduled_at
sent_at
read_at
dedup_key
created_at
```

``` text
notification_preference
family_id / user_id
enabled
quiet_hours
type_preferences JSONB
```

Phase 4 单用户测试时可使用 test user；Phase 5 再正式按成员偏好发送。

## 7. 规则

-   相同 dedup_key 在有效窗口内只发送一次
-   夜间默认进入免打扰
-   高价值 \> 高频
-   数据不足不推"异常"
-   不因一天少记录就制造焦虑
-   医疗危险信息不依赖普通营销式 Push 逻辑

## 8. 推荐文章

推荐优先级：

``` text
宝宝客观信息
> 成长阶段
> 近期记录变化
> 最近咨询
> 阅读行为
```

通知必须说明"为什么推荐"。

## 9. API

``` text
GET   /api/v1/notifications
PATCH /api/v1/notifications/{id}/read
GET   /api/v1/notification-preferences
PUT   /api/v1/notification-preferences
POST  /api/v1/push-devices
DELETE /api/v1/push-devices/{id}
```

## 10. Acceptance Criteria

-   消息中心可查看已读/未读
-   相同通知不会重复轰炸
-   支持免打扰
-   用户可关闭通知类型
-   推荐说明依据
-   AI 候选通知必须经过确定性规则
-   Push 失败有状态和重试策略
