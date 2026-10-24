# Hindsight 项目经验与共享 bank

这是一套外部记忆机制，不训练或微调大模型。

## 设计原则

只做 hindsight 不做的那一件事，其余全部交给原生能力。

hindsight 原生已经提供：bank 内 fact extraction、observations（后台 consolidation，自动合并去重、带证据与计数）、mental models（活文档）、tags 过滤、memory defense。这些都不在这里重新实现。

hindsight 明确**不**提供：跨 bank 检索。官方原文 `Isolation is strict: no cross-bank leakage`，`recall` 只接受单个 `bank_id`。所以"项目 A 的经验给项目 B 用"没有官方路径，只能自己搭。

## 已核实的原生边界

核实对象是当前运行镜像 `sha256:50311d02b4d5d2b7c5242bd336edf8735df8374eaad496a92f49c83b37d2aa06`，不是网上 latest 文档。

- `/app/api/hindsight_api/api/mcp.py`：`_build_mcp_tool_descriptions` 只把 `HINDSIGHT_API_MCP_INSTRUCTIONS` 追加到 retain/recall 描述。它不执行跨 bank 查询，不触发会话写回。
- `/app/api/hindsight_api/mcp_tools.py`：retain 调用 `submit_async_retain`，accepted 不表示完成；recall/reflect 各自只解析一个 bank。必须查 operation 完成状态。
- 官方文档：**MCP 端点只写 `/mcp/{bank_id}/`**（one per bank）。`/mcp/` 根路径 + `bank_id` 参数的 multi-bank 模式能用（一套 39 工具服务任意 bank），但未写进文档，属未公开行为。
- 原生 `recall` 支持 `tags` / `tags_match`（any/all/any_strict/all_strict/exact）/ `tag_groups`；`list_tags` 描述里官方举例 `q='project:*'`。即官方推荐的隔离方式是**单 bank + 标签**，不是多 bank。本部署仍按 Git 仓库分 bank（官方 coding-agents 集成同款："a per-repo bank"）。
- mental models 原生支持 consolidation 后刷新和 cron 刷新，但内容由一个 bank 的 reflect 生成；**没有**自动跨项目提炼到 `global` 的行为。
- 原生 `OperationValidatorExtension.on_retain_complete` 是代码级扩展入口。本实现使用它，不复制 39 个工具。

## 实际架构

```text
四客户端 ── 单条 /mcp/ ── 原生 39 工具（不再包装）

写入侧：项目 retain 完成 ── GlobalHooks ── 内联判断 ── 可复用则写入 global
读取侧：客户端需要跨项目经验时，自己再调一次 recall 传 bank_id=global
```

服务端**只**在 retain 落地时工作。没有 cron、没有队列、没有 SQLite、没有 mental model 自动刷新、不包装任何 MCP 工具。

`global` 专门保存跨项目经验，正文是一段完整描述（现象、根因、解法、适用条件），带 `topic:*` 标签与来源 bank/document；`default` 只作为未传 `bank_id` 时的兜底，不保存提炼经验。项目本身的事实继续留在项目 bank。

## 自动机制与提示的区别

| 行为              | 执行机制                | 保证范围                                |
| --------------- | ------------------- | ----------------------------------- |
| 根据当前目录得出项目名     | 客户端 Agent 或客户端 hook | 远端无法知道本地 cwd；目前由 Agent 传 bank_id   |
| 项目经验提炼到 global  | 原生 retain 完成 hook   | MCP/REST 成功写入均触发；内联执行，失败只记日志        |
| 读取跨项目经验         | 客户端主动调 recall       | **不自动附加**；需传 `bank_id=global`       |
| 会话开始主动查、结束主动存   | 工具说明建议              | 不保证每个客户端一定调用；严格自动需要各自 hooks        |

不传 `bank_id` 时落到 `default`，不会把未分类内容当作全局经验来源。用户无需手工指定项目名；客户端应从 Git 仓库名填写 `bank_id`。不会用共享 MCP session 的"最后一个项目"猜测，避免多个客户端交叉污染。

## 开销实测（2026-10-24）

数据来源 `GET /metrics` 的 `hindsight_llm_duration_seconds_count`，按 `scope` 分组。

**闲置 4.5 分钟**（删掉每分钟 cron 之后，9 次采样）：

```
t=30s total=30   t=60s total=30  ...  t=270s total=30
```

总量恒定，零增长。

**一次项目 retain 的全链路开销**（重启后干净基线）：

| scope                  | 增量  | 说明                            |
| ---------------------- | --- | ----------------------------- |
| `retain_extract_facts` | +2  | hindsight 固有：项目 bank + global |
| `reflect_tool_call`    | 0   | 已删除 mental model，不再有自动 reflect |
| 桥接层判断（不在指标内）           | +1  | 直连模型，不经过 hindsight metrics    |
| **合计**                 | **3** | 每次写入固定约 3 次调用                 |

**保留 mental model 自动刷新时的对比**：3 次 reflect 产生 20 次 `reflect_tool_call`，平均每次 reflect 约 7 次调用，且每次新经验都会触发。这是它被删除的原因。

结论：开销完全由"你写入了多少记忆"决定，与运行时间无关。空闲时为零。

## 去重、更新和失效

- 提炼前先在 `global` 做一次原生相似检索，并取出已有 `topic:*` 标签交给模型，要求同主题复用已有标签；同主题使用固定 `gm-*` 文档 ID + `update_mode=replace`，因此重复写入不会堆积条目（实测：同一内容 retain 两次，global 仍为 1 条，topic 未漂移）。
- 语义去重最终依赖模型判断 + hindsight 的 observations 合并，不能承诺绝无重复；可在控制台检查后纠正。
- 源文档被删除或任一原始事实被 invalidate，不会撤回已提炼的经验（没有后台扫描）。可用原生 `invalidate_memory` 或删除 `global` 中对应文档手工处理。
- 送入模型前过滤常见密钥、密码赋值、邮箱、手机号、IP、用户路径，输出再过滤；模型仅提炼已验证的技术经验和工作偏好。正则与模型不能保证识别所有敏感信息，客户端仍必须避免 retain 密钥/隐私。
- 提炼失败只打印错误类型，不重试、不落盘；下一次同类 retain 会自然重试。

## 安全及隔离范围

这是当前单用户、Tailscale 内的部署。没有多租户隔离；不要用于多个互不信任用户共享 `global` 的环境。

## 文件及运维

- `global_memory.py` → `/opt/hindsight/global_memory.py`，只读挂载到 `/app/api/global_memory.py`（约 180 行）。
- `docker-compose.aliedge.yml` → 服务端 `/opt/hindsight/docker-compose.yml`。
- **无定时任务**：`hindsight-global-memory.cron` 与 logrotate 已删除。服务端 crontab 只保留原有每日 04:00 的数据卷备份。
- 无 SQLite、无状态文件。旧状态文件已从数据卷清除。

源码挂载变化后需 `docker compose restart hindsight` 才会加载新的 hook 代码（`up -d` 不会重建，因为 compose 本身没变）。

回滚：从 `/opt/hindsight/backups/config-before-global-20261024-210117/` 恢复 compose，执行 `docker compose up -d`。不删除数据卷；`global` 中的经验可保留用于审计。

## 验证

本地单测：`python3 -m unittest discover -s deploy/hindsight-memory -p 'test_*.py' -v`（10 项，`ResourceWarning` 升级为错误后全部通过）。

`e2e.py` 是人工运行的远端验收驱动，使用专属 `gm-e2e-project-a/b`，会调用云模型：按 `prepare` → 等待约 90 秒 → `query` → `repeat` → 核对 `global` 文档数 → `cleanup` → `purge`。不得在这些名字已用于真实项目时运行。

2026-10-24 实测：远端工具数保持 39；项目 A 写入 Docker DNS 排错后，`global` 自动收到 1 条带 `topic:` 标签的经验；重复写入仍为 1 条；`recall` 传 `bank_id=global` 命中，首条 `fact_type=observation`（原生 consolidation 已合并）、reranker 0.998；清理后 `global` 与 `default` 均回到 0 条。

## 四客户端

已核对 Cursor `~/.cursor/mcp.json`、Codex `~/.codex/config.toml`、WorkBuddy `~/.workbuddy/mcp.json`、Hermes `~/.hermes/config.yaml` 都指向同一 `/mcp/`。地址与连接数不变。

服务端配置变更后旧会话应重连 MCP 或新建会话以刷新工具描述。不要求重启电脑；若客户端没有重连按钮，再重启客户端。未宣称四个 GUI 客户端都已完成实际点击验收。
