# 懂宝｜总体设计

> 版本：v1.2\
> 文档状态：开发基线\
> 产品定位：以宝宝长期数据为上下文的 AI 育儿助手\
> 开发路线：Phase 1～4 已确定；Phase 5 为多用户、数据隔离与家庭共享。

------------------------------------------------------------------------

# 1. 产品与系统目标

懂宝不是单纯的育儿记录 App，也不是普通 ChatGPT 套壳。

系统通过持续沉淀：

-   宝宝基础档案
-   日常记录
-   AI 对话上下文
-   哭声分析结果
-   专业育儿知识
-   推荐与提醒反馈

让 AI 越来越了解当前宝宝，并围绕宝宝真实情况提供：

-   记录辅助
-   AI 育儿问答
-   哭声解释
-   主动提醒
-   个性化内容推荐

核心闭环：

``` text
记录宝宝
  ↓
沉淀宝宝上下文
  ↓
AI 理解宝宝
  ↓
专业回答 / 哭声解释 / 主动提醒
  ↓
继续记录与反馈
```

核心原则：

> 懂宝的价值不在于"能回答问题"，而在于"越来越懂这个宝宝"。

------------------------------------------------------------------------

# 2. 五阶段开发路线

  --------------------------------------------------------------------------------------------------------
  阶段              名称              核心目标                                           当前状态
  ----------------- ----------------- -------------------------------------------------- -----------------
  Phase 1           AI 辅助记录       建档、ASR/Vision、结构化草稿、确认、时间线与统计      已确定

  Phase 2           AI Agent          Context、Memory、Tool Calling、RAG、结构化回答         已确定

  Phase 3           哭声识别          录音、预处理、哭声模型、AI 二次解释                已确定

  Phase 4           信息推送          记录提醒、成长提醒、变化提醒、文章推荐             已确定

  Phase 5           多用户与家庭      用户隔离、Family、家庭成员、共享宝宝、权限与审计   后续实施
  --------------------------------------------------------------------------------------------------------

开发流程：

``` text
Phase Draft
  ↓
Grill
  ↓
to-spec
  ↓
to-tickets
  ↓
implement
  ↓
test / review
```

原则：

-   不一次性把五个阶段全部拆成 tickets。
-   当前只细化正在开发的 Phase。
-   后续阶段提前确定架构边界，但不提前实现。
-   Grill 用于发现真实不确定性，不为了流程强行制造问题。

------------------------------------------------------------------------

# 3. 总体技术栈

## 3.1 客户端

``` text
UniApp
Vue 3
TypeScript
Pinia
SCSS
Vite
```

目标平台：

-   微信小程序
-   H5
-   iOS App
-   Android App

设计原则：

-   移动端优先
-   适老友好
-   高频记录步骤尽可能少
-   不依赖仅 Web 可用的复杂 DOM 能力
-   不依赖复杂手势完成核心操作

------------------------------------------------------------------------

## 3.2 后端

``` text
Python
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
PydanticAI
```

后端采用：

> **模块化单体（Modular Monolith）**

当前不拆微服务。

原因：

-   产品还处于早期
-   业务边界仍会变化
-   单人 / 小团队开发
-   Codex 需要同时理解产品、接口、数据库和 AI
-   拆服务会提前引入部署、RPC、鉴权、链路追踪等复杂度

------------------------------------------------------------------------

## 3.3 数据与基础设施

``` text
PostgreSQL
pgvector
S3 兼容对象存储
FFmpeg
ASR / Vision Provider（Phase 1 起）
Redis（按需求引入）
Langfuse
Docker
Nginx
```

使用策略：

### PostgreSQL

Phase 1 开始即使用。

负责：

-   宝宝
-   记录
-   AI 会话
-   AI Message
-   AI Memory
-   哭声分析
-   推荐
-   Notification
-   Family
-   权限关系

### pgvector

Phase 2 开始使用。

负责：

-   RAG Embedding
-   AI Memory 语义检索

不引入独立向量数据库。

### Redis

不是 Phase 1 必选。

仅当实际需要时引入：

-   短时缓存
-   限流
-   临时 Agent Context
-   Phase 4 任务状态
-   推送去重 / 调度辅助

### Object Storage

负责：

-   图片
-   语音记录
-   哭声音频
-   文章资源
-   用户上传文件

数据库只保存 object key 与元数据，不直接保存大文件和 Base64。

------------------------------------------------------------------------

# 4. 总体架构

``` text
┌────────────────────────────────────────────┐
│         UniApp / Vue 3 / TypeScript        │
│                                            │
│ 首页 │ 记录 │ 懂宝 AI │ 我的               │
│      │      │           │                  │
│   语音 / 图片 / 文本 / 哭声录音            │
└──────────────────┬─────────────────────────┘
                   │ HTTPS
                   ▼
┌────────────────────────────────────────────┐
│                 FastAPI                    │
│                                            │
│ Baby                                       │
│ Record ── Speech / Vision / Extraction     │
│ AI     ── Agent / Context / Memory / RAG   │
│ Cry                                        │
│ Notification                               │
│ Family                                     │
└────────┬────────────┬─────────────┬────────┘
         │            │             │
         ▼            ▼             ▼
 PostgreSQL      AI Providers     Object Storage
 + pgvector      │        │        图片 / 音频
                 │        │
          ┌──────┘        └──────────────┐
          ▼                              ▼
  Phase 1: ASR / Vision /         Phase 2: LLM / RAG
           Structured Extraction          PydanticAI Agent
```

Phase 1 的 AI 只服务于“记录理解”：

``` text
Voice → ASR ───────────────┐
                           ├→ Structured Extraction → RecordDraft → 用户确认 → Record
Photo → Vision ────────────┘
```

AI 识别结果只能预填 `RecordDraft`，不得绕过用户确认直接写正式记录。ASR、Vision 与结构化提取通过可替换 Provider/Port 接入，不在业务代码中写死具体厂商。

Phase 2 在此基础上增加完整 Agent 能力：

``` text
User Input
→ Context Builder
→ PydanticAI Agent
→ Tool Calling / RAG
→ Structured Response
```

Phase 2 的语音/图片问题可以复用 Phase 1 已建立的 ASR/Vision 基础能力。

Phase 3：

``` text
Audio
→ FFmpeg
→ Cry Model
→ CryAnalysisResult
→ PydanticAI
→ 结合宝宝上下文解释
```

Phase 4：

``` text
业务事件 / 定时任务
→ Notification Rules
→ Dedup / Frequency Limit
→ Push Provider
```

------------------------------------------------------------------------

# 5. 项目结构与代码组织

懂宝采用 Monorepo。

目标不是追求"看起来正规"，而是让产品文档、Spec、Ticket、前端和后端保持同一上下文，方便
Codex 按 Phase 工作。

推荐仓库结构：

``` text
dongbao/
│
├── apps/
│   ├── client/                 # UniApp 客户端
│   └── server/                 # FastAPI 后端
│
├── docs/
│   ├── product/
│   │   ├── 00-overview.md
│   │   └── 01-prd.md
│   │
│   └── phases/
│       ├── 01-record.md
│       ├── 02-ai.md
│       ├── 03-cry-analysis.md
│       ├── 04-notification.md
│       └── 05-family.md
│
├── specs/                      # to-spec 输出
│
├── tickets/                    # to-tickets 输出
│
├── scripts/
│
├── AGENTS.md
├── README.md
├── .env.example
└── docker-compose.yml
```

## 5.1 Monorepo 原则

前端、后端、文档、Spec、Ticket 放在同一个仓库。

优点：

-   Codex 可以一次理解整个产品上下文
-   前后端接口变更容易同步
-   Spec 与实现保持邻近
-   Phase 开发范围容易控制
-   初期部署和版本管理简单

当前不拆：

``` text
dongbao-client
dongbao-server
dongbao-ai
```

除非未来出现真正独立部署和团队边界。

------------------------------------------------------------------------

## 5.2 按业务能力纵向组织

后端不采用全局横向目录：

``` text
controller/
service/
repository/
entity/
dto/
vo/
mapper/
```

而采用业务模块组织：

``` text
modules/
├── baby/
├── record/
├── ai/
├── cry/
├── notification/
└── family/
```

每个模块内部根据真实复杂度决定是否需要：

``` text
models.py
schemas.py
service.py
repository.py
exceptions.py
```

这些内部文件不在总体设计中强制写死。

原则：

> 总体设计确定模块边界，to-spec 决定具体实现结构。

------------------------------------------------------------------------

## 5.3 前端组织原则

前端区分：

``` text
pages/
features/
components/
services/
stores/
```

推荐方向：

``` text
apps/client/src/
│
├── pages/
│   ├── home/
│   ├── record/
│   ├── ai/
│   └── mine/
│
├── features/
│   ├── baby/
│   ├── record/
│   ├── ai/
│   ├── cry/
│   ├── notification/
│   └── family/
│
├── components/
├── services/
├── stores/
├── types/
└── utils/
```

原则：

> 页面负责组合，业务能力放到 feature。

例如语音记录不应全部堆进：

``` text
pages/record/index.vue
```

而应由 `features/record` 承载主要业务能力。

------------------------------------------------------------------------

## 5.4 后端组织原则

推荐方向：

``` text
apps/server/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │
│   ├── modules/
│   │   ├── baby/
│   │   ├── record/
│   │   ├── ai/
│   │   ├── cry/
│   │   ├── notification/
│   │   └── family/
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   ├── storage/
│   │   └── cache/
│   │
│   ├── core/
│   └── shared/
│
├── migrations/
├── tests/
├── pyproject.toml
└── Dockerfile
```

总体设计只确定：

-   模块按业务能力纵向划分
-   Infrastructure 放公共技术实现
-   Core 放全局配置和基础能力
-   Shared 只存真正跨模块共享的内容

不要提前创建大量空目录和未来脚手架。

Phase 1 的 ASR / Vision / 结构化提取建议采用 Port + Adapter：Record 模块定义业务需要的接口，具体第三方 Provider 实现放在 Infrastructure。这样既能在 Phase 1 使用 AI，也不会把 Record 模块绑定到某一家模型厂商。

------------------------------------------------------------------------

## 5.5 Phase 与代码模块对应

``` text
Phase 1 → record + speech/vision/extraction adapters
Phase 2 → ai agent
Phase 3 → cry
Phase 4 → notification
Phase 5 → family
```

同时：

``` text
docs/phases/01-record.md
        ↓
specs/01-record-spec.md
        ↓
tickets/phase-01/
        ↓
apps/client/src/features/record/
apps/server/app/modules/record/
```

这种映射是推荐组织方式，但不是限制 Ticket 只能修改对应模块。

例如 Phase 2 AI 可能需要读取 Baby / Record，但 AI 逻辑本身仍归 AI 模块。

------------------------------------------------------------------------

# 6. 模块边界

## 6.1 Baby

负责宝宝基础档案。

首次建档只要求：

-   昵称
-   生日
-   性别

其他信息按需要补充。

Baby 是多个 Phase 的基础能力，不单独作为开发阶段。

------------------------------------------------------------------------

## 6.2 Record

负责：

-   手动记录
-   快捷记录
-   语音记录与 ASR
-   拍照记录与 Vision
-   结构化信息提取
-   RecordDraft
-   用户确认后落正式 Record
-   时间线
-   统计
-   修改
-   删除
-   撤销

核心规则：

> AI 或多模态识别只能生成 Draft，不能直接写正式宝宝事实。

------------------------------------------------------------------------

## 6.3 AI

负责：

-   Agent Loop
-   Context Builder
-   Tool Calling
-   RAG
-   Structured Output
-   AI Conversation
-   AI Memory
-   多模态问题理解

AI 模块复用 Phase 1 的 ASR/Vision 基础能力处理多模态问题，但不接管 RecordDraft 的保存规则。

AI 不负责：

-   Phase 1 的记录识别流程与 RecordDraft 保存规则
-   直接 SQL
-   直接业务表写入
-   哭声模型推理
-   确定性业务规则

------------------------------------------------------------------------

## 6.4 Cry

负责：

-   哭声音频
-   FFmpeg 预处理
-   音频质量判断
-   专用 Cry Model
-   模型版本
-   结构化推理结果

PydanticAI 只在模型结果之后负责解释。

------------------------------------------------------------------------

## 6.5 Notification

负责：

-   定时任务
-   业务事件
-   Notification Candidate
-   规则过滤
-   去重
-   频控
-   免打扰
-   Push
-   消息中心

AI 只能生成候选 Insight，最终推送必须经过确定性规则。

------------------------------------------------------------------------

## 6.6 Family

Phase 5 实施。

负责：

-   User
-   Family
-   FamilyMember
-   邀请
-   Role
-   Baby Access
-   Data Isolation
-   Audit

Phase 1～4 只预留数据边界，不提前实现完整权限体系。

------------------------------------------------------------------------

# 7. 数据设计原则

## 7.1 三类数据必须分离

``` text
业务事实
AI Memory
RAG Knowledge
```

示例：

``` text
宝宝生日
→ baby

一次喂奶
→ baby_record

“宝宝通常晚上八点左右入睡”
→ ai_memory

WHO / 专业育儿资料
→ rag_document / rag_chunk
```

不把业务事实全部复制进 AI Memory。

------------------------------------------------------------------------

## 7.2 Record 数据模型

Phase 1 推荐统一：

``` text
baby_record
```

字段：

``` text
id
family_id
baby_id
record_type
occurred_at
source
payload JSONB
note
created_by
created_at
updated_at
deleted_at
```

使用 JSONB 是为了降低 MVP 的表数量。

Python 层通过 Pydantic Discriminated Union 保证不同 Record Type
的字段正确。

当未来某类数据出现明显独立查询/统计需求时，再考虑拆专门表。

------------------------------------------------------------------------

## 7.3 family_id / baby_id

从 Phase 1 开始：

-   Baby 相关业务数据预留 `family_id`
-   所有宝宝业务数据必须绑定 `baby_id`

Phase 1～4 可以使用 test family/test user。

Phase 5 再正式启用真实用户和鉴权。

------------------------------------------------------------------------

## 7.4 Media

统一媒体元数据：

``` text
media_asset
```

至少包括：

``` text
id
family_id
baby_id
object_key
media_type
mime_type
size
duration
created_at
```

禁止：

-   Base64 长期存数据库
-   客户端自由决定对象存储路径
-   永久公开 URL 作为隐私媒体访问方式

------------------------------------------------------------------------

# 8. Phase 1｜AI 辅助记录技术边界

Phase 1 的核心目标是：

> 建立“低输入成本 + AI 自动理解 + 人工确认”的宝宝事实数据入口。

实现：

-   Baby Profile
-   Manual Record
-   Quick Record
-   Voice Capture
-   ASR
-   Photo Capture
-   Vision
-   Structured Extraction
-   RecordDraft
-   Confirm
-   Timeline
-   Daily Summary
-   Edit / Delete / Undo
-   Object Storage

核心流程：

``` text
Voice → ASR → transcript ──────────┐
                                   ├→ Structured Extraction → RecordDraft → Confirm → Record
Photo → Vision → observations ────┘
```

Phase 1 中 ASR、Vision 与结构化提取属于 P0，不等待 Phase 2。

但必须保持以下边界：

-   ASR 只负责 Speech → Text。
-   Vision 负责从图片提取有依据的观察信息。
-   Structured Extraction 负责把 transcript / observations 转换为 RecordDraft。
-   识别结果只能预填 Draft，不能直接写正式宝宝事实。
-   缺失或不确定字段必须留空 / warning，不允许猜测精确数值。
-   ASR / Vision / Extraction 任一失败时，保留原媒体并降级到人工补充。
-   Provider/模型厂商不得写死在 Record 业务代码中。

如果具体 ASR / Vision Provider 尚未决定，应在 Grill 中标记 `Validation Required`，通过最小 PoC 验证识别效果、延迟、成本与 UniApp/微信小程序接入后形成决策；这不改变 Phase 1 必须交付真实识别能力的产品边界。

Phase 1 不引入：

-   通用 Agent Loop
-   Tool Calling
-   RAG
-   长期 AI Memory
-   通用育儿问答

这些属于 Phase 2。

------------------------------------------------------------------------

# 9. Phase 2｜AI 架构

核心流程：

``` text
User Input
→ Context Builder
→ PydanticAI Agent
→ Tool Call
→ Tool Result
→ Agent
→ ...
→ 无 Tool Call
→ Structured Output
```

Tool Result 必须回给 LLM。

Agent 只有在模型不再调用 Tool 时才结束本轮循环。

首批 Tool：

``` text
get_baby_profile
get_daily_feeding
get_recent_sleep
get_recent_records
get_growth_history
search_parenting_knowledge
```

工具负责确定性能力，Agent 负责：

-   判断是否调用
-   理解返回结果
-   继续推理
-   生成最终回答

------------------------------------------------------------------------

# 10. RAG

MVP：

``` text
PostgreSQL + pgvector
```

流程：

``` text
Question
→ Embedding
→ pgvector Search
→ Chunks + Source Metadata
→ Agent
→ Answer + Sources
```

当前不引入：

-   LangChain
-   LlamaIndex
-   独立向量数据库

除非后续复杂度证明有必要。

------------------------------------------------------------------------

# 11. Phase 3｜哭声识别架构

``` text
录音 / 上传
→ Object Storage
→ FFmpeg
→ Quality Check
→ Cry Model
→ CryAnalysisResult
→ Context Builder
→ PydanticAI
→ 用户结果
```

必须区分：

``` text
Cry Model
负责：音频分析

LLM
负责：解释结果
```

禁止让 LLM 假装自己直接"听懂哭声"。

没有充分模型校准之前，不展示：

``` text
87% 饿了
92% 困了
```

等伪精确指标。

------------------------------------------------------------------------

# 12. Phase 4｜信息推送架构

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

推送来源：

-   记录提醒
-   成长阶段
-   疫苗/体检
-   数据变化
-   文章推荐
-   受控 AI Insight

AI Insight 不能直接 Push。

必须先经过：

-   业务规则
-   去重
-   频控
-   风险检查

------------------------------------------------------------------------

# 13. Phase 5｜多用户与家庭边界

安全边界：

``` text
family_id
```

资源边界：

``` text
baby_id
```

服务端不得信任客户端传入的 family_id 作为授权依据。

Phase 5 后：

``` text
User Identity
→ 可访问 Family
→ 可访问 Baby
→ 查询业务数据
```

数据访问必须在服务端完成 Scope 校验。

例如不允许：

``` python
record = repo.get(record_id)
```

语义应是：

``` python
record = repo.get_for_family(
    record_id=record_id,
    family_id=current_family_id,
)
```

角色首版保持简单：

``` text
owner
admin
member
```

不提前建设复杂 RBAC 权限编辑器。

------------------------------------------------------------------------

# 14. AI 安全与专业边界

懂宝是育儿助手，不是医生。

必须遵守：

-   不做疾病诊断
-   危险信号优先建议就医
-   专业知识尽量展示来源
-   数据不足明确说明
-   不虚构宝宝记录
-   不虚构引用
-   不把相关性包装成因果
-   不用伪精确分数制造可信感

AI 回答应体现：

> "基于宝宝当前信息，我能帮助你判断什么；哪些信息仍然不足。"

------------------------------------------------------------------------

# 15. Observability

AI 侧使用 Langfuse。

记录：

-   Trace
-   LLM Call
-   Tool Call
-   RAG Retrieval
-   Latency
-   Token Usage
-   Error

不直接写入：

-   完整敏感音频
-   私密原图
-   不必要的宝宝隐私全文

普通业务日志与 AI Trace 分开处理。

------------------------------------------------------------------------

# 16. 工程开发原则

## 16.1 不过度设计

决策优先级：

``` text
复用现有能力
>
标准库
>
平台原生能力
>
已有依赖
>
简单清晰实现
>
新增抽象
```

不要提前创建：

-   单实现 Interface
-   为"以后可能"准备的 Factory
-   空的 Repository 层
-   无使用场景的 Event Bus
-   无必要的 Redis
-   无必要的消息队列
-   微服务脚手架

------------------------------------------------------------------------

## 16.2 最小充分验证

简单改动：

``` text
编译 / typecheck / 最相关测试
```

中等改动：

``` text
模块测试
```

复杂链路：

``` text
必要的集成验证
```

不为了"显得完整"运行大量无关测试。

------------------------------------------------------------------------

# 17. 文档职责边界

## 总体设计

负责：

-   产品技术方向
-   技术栈
-   总体架构
-   项目布局
-   模块边界
-   数据原则
-   Phase 依赖
-   跨阶段设计约束

不负责：

-   每个具体 API 的全部字段
-   每张表全部索引
-   每个源码文件名
-   当前 Ticket 的具体实现细节

------------------------------------------------------------------------

## PRD

负责：

-   产品目标
-   用户
-   页面
-   功能
-   产品规则
-   Phase Scope
-   P0/P1
-   Non-goals

------------------------------------------------------------------------

## Phase Draft

负责：

``` text
docs/phases/*
```

作为 Grill / to-spec 的输入。

------------------------------------------------------------------------

## Spec

负责：

``` text
specs/*
```

定义当前 Phase 可直接实现的：

-   User Flow
-   API
-   Schema
-   DB
-   Edge Cases
-   Acceptance Criteria

------------------------------------------------------------------------

## Ticket

负责：

``` text
tickets/*
```

明确：

-   具体 Goal
-   修改范围
-   文件 / Module
-   实现说明
-   验收
-   最小验证
-   依赖关系

------------------------------------------------------------------------

# 18. 最终开发映射

整个项目保持：

``` text
产品设计
   ↓
docs/product
   ↓
docs/phases
   ↓
Grill
   ↓
specs
   ↓
to-tickets
   ↓
tickets
   ↓
implement
   ↓
apps/client + apps/server
```

Phase 与代码：

``` text
Record       → features/record       + modules/record
AI           → features/ai           + modules/ai
Cry          → features/cry          + modules/cry
Notification → features/notification + modules/notification
Family       → features/family       + modules/family
```

这是一致的开发组织原则，而不是强制每个模块必须拥有完全相同的文件结构。

------------------------------------------------------------------------

# 19. 当前基线结论

懂宝当前技术基线：

``` text
产品名：
懂宝

仓库：
dongbao

组织：
Monorepo

前端：
UniApp + Vue3 + TypeScript

后端：
FastAPI + Pydantic + SQLAlchemy

Agent：
PydanticAI

数据库：
PostgreSQL

向量：
pgvector

媒体：
Object Storage

AI Trace：
Langfuse

架构：
Modular Monolith

开发：
Grill → to-spec → to-tickets → implement
```

总体设计只锁定稳定边界。

具体文件、接口实现、Provider 选择和模块内部结构，由每个 Phase 的 Spec
决定。
