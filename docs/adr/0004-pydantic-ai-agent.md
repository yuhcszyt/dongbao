# ADR 0004：育儿 Agent 用 PydanticAI

## Status

Accepted — 2026-09-20

## Context

Phase 2 设计文档指定 PydanticAI。初版为赶通 DeepSeek tool calling，用 httpx 手写循环。能力齐了之后应回到可读、可维护的 Agent 编排。

## Decision

- **编排**：`pydantic-ai-slim[openai]` 的 `Agent`，`output_type=ParentingAnswer`，tools 经 `RunContext[ParentingDeps]` 调 `BabyScope`。
- **依赖**：只用 slim + openai extra，避免拉全量 `pydantic-ai`（会和现有 FastAPI/starlette 打架）。
- **兼容端点**：DeepSeek 等关闭 `openai_supports_strict_tool_definition`。
- **边界**：
  - `agent.py` — 对外入口 + 降级分流
  - `parenting_agent.py` — PydanticAI 定义
  - `tools.py` — 业务查询（与 SDK 无关）
  - `fallback.py` / `prompt.py` — 降级与指令

## Consequences

- 路由与测试仍只依赖 `run_parenting_agent`；换模型厂商改 `_chat_model()` 即可。
- 未配置 `MODEL_API_KEY` 时行为与之前一致（fallback，不调 SDK）。
