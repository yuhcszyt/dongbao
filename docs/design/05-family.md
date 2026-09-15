# SPEC 05｜多用户、数据隔离与家庭共享

> Phase 5\
> 状态：架构边界先确定，Phase 4 完成后实施

## 1. Scope

-   用户登录
-   Family
-   FamilyMember
-   邀请
-   家庭角色
-   共享宝宝
-   数据隔离
-   成员记录来源
-   成员移除
-   基础审计
-   多宝宝基础支持

## 2. 核心原则

安全边界是 `family_id`，业务对象同时绑定 `baby_id`。

客户端传来的 `family_id`
不能作为授权依据。服务端必须从登录身份解析当前用户可访问的家庭和宝宝。

## 3. 数据模型

``` text
user
id
display_name
avatar
created_at
```

``` text
family
id
name
owner_user_id
created_at
```

``` text
family_member
id
family_id
user_id
role
status
joined_at
```

``` text
baby
id
family_id
nickname
birthday
sex
...
```

Phase 1～4 已存在的
`baby_record`、media、conversation、cry_analysis、notification
等继续使用 `family_id + baby_id`。

## 4. Roles

MVP 建议只做少量角色：

``` text
owner
admin
member
```

避免一开始做复杂 RBAC。

建议： - owner：家庭所有权、成员管理 - admin：管理成员和宝宝资料 -
member：查看共享宝宝、创建日常记录

高风险操作单独做服务端权限判断，而不是靠按钮隐藏。

## 5. Invitation

``` text
管理员创建邀请
→ invite token / 微信分享
→ 被邀请人登录
→ 查看家庭信息
→ 接受
→ family_member active
```

邀请必须： - 有过期时间 - 可撤销 - 单次使用或受控重复使用 - 不在 URL
中暴露敏感家庭数据

## 6. Isolation

所有 Repository / Service 查询必须带授权后的 family scope。

错误：

``` python
record = await repo.get(record_id)
```

正确语义：

``` python
record = await repo.get_for_family(
    record_id=record_id,
    family_id=auth.family_id,
)
```

任何通过 ID 访问资源的接口都必须验证资源属于当前可访问 family/baby。

## 7. Shared Record

记录保留 `created_by`，时间线可以显示：

``` text
奶奶记录 · 09:30 · 配方奶 180ml
```

业务事实属于宝宝，不属于创建者个人。成员退出家庭后，已创建的宝宝记录默认保留。

## 8. AI 隔离

AI Context Builder 只能加载当前授权 baby 的： - profile - records -
conversations - memory - cry results

禁止跨 family 检索 AI Memory 或私有记录。

RAG 公共知识可以跨家庭共享，但用户私有数据不能进入公共知识索引。

## 9. Media Isolation

对象存储 key 使用不可猜测 ID；下载通过鉴权 API 或短时签名 URL。

不能因为知道 object_key 就永久公开访问。

## 10. Audit

至少记录： - 邀请 - 接受邀请 - 成员角色变化 - 成员移除 -
宝宝删除/关键资料修改

普通喂奶记录无需做重型审计系统。

## 11. Migration

Phase 5 上线前：

``` text
test family / 单用户数据
→ 创建真实 owner user
→ 迁移到真实 family
→ 校验 family_id / baby_id 完整性
→ 启用鉴权
```

必须在开启多用户访问前完成数据回填和隔离测试。

## 12. Security Acceptance

至少测试： - A 家庭不能读取 B 家庭宝宝 - 猜 record_id 无法越权 - 猜
media_id 无法越权 - AI 无法召回其他家庭记录 - 被移除成员立即失去访问权 -
过期邀请不可加入 - member 不能执行 owner-only 操作 -
服务端权限有效，即使客户端按钮被绕过

## 13. Out of Scope

首版不做： - 企业级权限策略编辑器 - 自定义角色 - 跨家庭复杂授权 -
医生/机构账号体系 - 细粒度字段级权限
