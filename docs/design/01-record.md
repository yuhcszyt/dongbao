# SPEC 01｜AI 辅助记录

> Phase 1\
> 状态：Ready for Grill / validation

## 1. Scope

交付： - 宝宝基础档案 - 快捷/手动记录 - 语音记录 + ASR - 拍照记录 + Vision -
结构化信息提取 - RecordDraft 确认 - 时间线 - 修改 / 删除 / 撤销 - 今日基础汇总 -
媒体上传 - 适老交互

不包含完整 AI 问答、Agent Loop、Tool Calling、RAG、长期 AI Memory、哭声模型、Push、正式多用户登录。

Phase 1 的 AI 只负责“理解输入并预填草稿”：语音/图片识别结果必须先进入 `RecordDraft`，用户确认后才能成为正式 Record。识别服务失败时必须允许退回手动补充，不能阻塞基本记录能力。

## 2. User Stories

-   照护者可以几秒内记录一次喂奶。
-   老人可以点一下语音按钮，说“宝宝刚喝了 180 毫升奶”，系统自动识别并预填 180ml，确认后保存。
-   用户可以拍辅食、奶瓶等，系统使用 Vision 提取可观察信息并预填草稿，确认后保存。
-   家长可以按时间查看记录。
-   错误记录可以修改、删除和撤销。

## 3. UX

``` text
给宝宝记一笔

[语音记录]
点一下，直接说

[拍照记录]
拍食物、奶瓶等

点选记录
喂奶 / 辅食 / 睡眠 / 排便 / 尿布 / 身高体重
```

要求： - 主点击区域 ≥ 48px - 不依赖长按 - 时间默认当前时间 -
不强迫填写非必要字段 - 识别后必须确认 - 保存后提供撤销

## 4. Record Types

`feeding / complementary_food / sleep / stool / diaper / crying / growth / vaccine / medication / custom`

## 5. 数据模型

``` text
baby_record
id UUID
family_id UUID
baby_id UUID
record_type VARCHAR
occurred_at TIMESTAMPTZ
source VARCHAR
payload JSONB
note TEXT NULL
created_by UUID NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ NULL
```

source：`manual / voice / photo / system`

Phase 1 使用固定 test family/test user；`family_id` 为 Phase 5 预留。

## 6. Pydantic Payload

不同记录类型使用 Discriminated Union。示例：

``` python
class FeedingPayload(BaseModel):
    kind: Literal["feeding"]
    feeding_type: Literal["formula", "breast", "unknown"]
    amount_ml: int | None = Field(default=None, ge=0)

class FoodPayload(BaseModel):
    kind: Literal["complementary_food"]
    food_name: str
    amount_text: str | None = None

class SleepPayload(BaseModel):
    kind: Literal["sleep"]
    start_at: datetime | None = None
    end_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
```

## 7. RecordDraft

``` python
class RecordDraft(BaseModel):
    record_type: RecordType | None
    occurred_at: datetime | None
    payload: dict
    note: str | None = None
    missing_fields: list[str] = []
    source: Literal["voice", "photo", "manual"]
    transcript: str | None = None
    recognition_warnings: list[str] = []
```

状态：

``` text
captured → processing → draft → confirmed → saved
```

禁止 `draft → saved` 绕过用户确认。

## 8. 语音记录

Phase 1 基线流程：

``` text
点击开始 → 麦克风 → 再点结束 → 上传
→ ASR → transcript
→ 结构化信息提取
→ 预填 RecordDraft
→ 用户确认 / 修改
→ 保存
```

例如：

``` text
“宝宝刚喝了 180 毫升奶”
→ ASR: 宝宝刚喝了180毫升奶
→ RecordDraft: feeding / amount_ml=180
→ 用户确认
```

规则：

- ASR 是 Phase 1 P0 能力，不等待 Phase 2。
- ASR 只负责 Speech → Text；结构化提取负责 Text → RecordDraft。
- ASR 或结构化提取失败时，保留原录音并退回可编辑草稿/手动补充流程。
- 缺失字段写 `null` / `missing_fields`，不得猜测。
- 原录音、transcript 与记录建立可追溯关联。
- AI 不得绕过确认直接保存正式记录。

## 9. 拍照记录

Phase 1 基线流程：

``` text
拍照/相册 → 上传
→ Vision 分析
→ 结构化信息提取
→ 预填 RecordDraft
→ 用户确认 / 修改
→ 保存
```

规则：

- Vision 是 Phase 1 P0 能力，不等待 Phase 2。
- 只提取图像中有足够依据的可观察信息；不确定字段必须留空或给出 warning。
- 不可靠时不得估算精确克数、奶量、药物剂量等高风险/高精度字段。
- 无法识别时要求用户补充，不编造。
- 图片与记录建立 media relation。
- AI 不得绕过确认直接保存正式记录。

## 9.1 AI Provider 边界

业务层不写死具体模型厂商，Phase 1 至少定义以下能力边界：

``` python
class SpeechRecognitionProvider(Protocol):
    async def transcribe(self, media_id: UUID) -> str: ...

class VisionRecognitionProvider(Protocol):
    async def analyze(self, media_id: UUID) -> dict: ...

class RecordExtractor(Protocol):
    async def extract(self, content: dict) -> RecordDraft: ...
```

建议：Record 模块定义 Port，具体 Provider Adapter 放在 `infrastructure`。厂商、模型、成本与延迟如尚未确定，在 Grill 中标记 `Validation Required`，通过最小 PoC 决策，不改变上述业务边界。

## 10. API

``` text
POST   /api/v1/babies/{baby_id}/records
GET    /api/v1/babies/{baby_id}/records
GET    /api/v1/babies/{baby_id}/records/{record_id}
PATCH  /api/v1/babies/{baby_id}/records/{record_id}
DELETE /api/v1/babies/{baby_id}/records/{record_id}

POST   /api/v1/media
POST   /api/v1/record-drafts/from-voice
POST   /api/v1/record-drafts/from-photo
POST   /api/v1/record-drafts/{draft_id}/confirm

GET    /api/v1/babies/{baby_id}/daily-summary
```

## 11. Media

``` text
media_asset
id
family_id
baby_id
object_key
media_type
mime_type
size
duration_ms
created_at
```

对象存储 key 由服务端控制。

## 12. Acceptance Criteria

-   手动记录可新增、修改、删除、撤销
-   时间线按 occurred_at 正确排序
-   今日汇总只统计有效记录
-   语音可以完成：录音 → ASR → 结构化提取 → 可编辑 RecordDraft
-   图片可以完成：上传 → Vision → 结构化提取 → 可编辑 RecordDraft
-   “宝宝刚喝了 180 毫升奶”一类短语音能自动预填对应记录字段；识别结果仍需用户确认
-   AI 无法确定的字段保持空值 / warning，不编造精确数值
-   ASR / Vision / Extraction 任一失败时，可退回人工补充，不丢失已采集媒体
-   草稿未经确认不能落正式记录
-   老人主流程在识别成功时不要求键盘输入
-   原录音/图片与最终记录可追溯关联
-   刷新后正式记录仍存在
