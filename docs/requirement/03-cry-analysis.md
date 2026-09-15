# SPEC 03｜哭声识别

> Phase 3\
> 依赖：Phase 1、Phase 2

## 1. Scope

-   实时录音
-   上传哭声音频
-   音频预处理
-   音频质量检测
-   Cry Model
-   结构化模型结果
-   PydanticAI 二次解释
-   最近分析历史

## 2. 职责边界

``` text
音频 → Cry Model → 判断音频特征/类别
                     ↓
              CryAnalysisResult
                     ↓
PydanticAI + 宝宝档案/记录 → 给家长解释与排查建议
```

LLM 不直接承担哭声分类模型职责。

## 3. 音频流程

``` text
录音/上传
→ Object Storage
→ FFmpeg 标准化
→ Quality Check
→ Cry Model
→ Result
→ AI Context Builder
→ PydanticAI
→ 用户结果页
```

标准化至少考虑采样率、声道、格式和过短/过长音频。

## 4. 数据模型

``` python
class CryAnalysisResult(BaseModel):
    labels: list[CryLabel]
    audio_quality: str
    model_version: str
    warnings: list[str] = []
```

持久化：

``` text
cry_analysis
id
family_id
baby_id
media_id
model_version
model_result JSONB
ai_explanation JSONB
created_at
```

## 5. UI

录音页： - 大录音按钮 - 点击开始 / 点击结束 - 上传音频 - 最近分析

结果页： - 明确不是医学诊断 - 可能需求 - 其他可能 - 建议先检查 -
相关宝宝记录 - "结合记录问懂宝"

## 6. 结果表达

推荐：

``` text
这段哭声更接近某类特征。
结合宝宝最近记录，可以先检查……
```

禁止：

``` text
宝宝 87% 是饿了
宝宝一定是肚子疼
```

除非未来模型经过充分验证并有明确校准标准，否则 UI 不显示伪精确概率。

## 7. Failure Handling

-   非哭声音频 → 提示无法有效分析
-   音频质量差 → 建议重新录制
-   模型不可用 → 保留音频并允许稍后重试
-   AI 解释失败 → 仍可展示克制的模型结构化结果
-   无近期记录 → 明确"缺少近期记录"

## 8. Acceptance Criteria

-   可录制和上传音频
-   FFmpeg 处理失败有错误状态
-   模型结果包含 model_version
-   AI 只能解释结构化模型结果
-   结果页不做疾病诊断
-   可关联当前宝宝近期记录
-   历史分析可回看
