# Hindsight 项目与全局经验层

这是一套外部记忆检索与提炼机制，不训练或微调大模型。

## 已核实的原生边界

核实对象是当前运行镜像 `sha256:50311d02b4d5d2b7c5242bd336edf8735df8374eaad496a92f49c83b37d2aa06`，不是网上 latest 文档。

- `/app/api/hindsight_api/api/mcp.py`：`_build_mcp_tool_descriptions` 只把 `HINDSIGHT_API_MCP_INSTRUCTIONS` 追加到 retain/recall 描述。它不执行跨 bank 查询，不触发会话写回。
- `/app/api/hindsight_api/config.py`：`mcp_instructions` 是上述描述配置。
- `/app/api/hindsight_api/mcp_tools.py`：retain 调用 `submit_async_retain`，accepted 不表示完成；recall/reflect 各自只解析一个 bank。必须查 operation 完成状态。
- mental model 原生支持 consolidation 后刷新和 cron，但内容由指定 bank 的 reflect 生成；没有自动跨项目提炼到 `global` 的行为。
- directives 用于影响 bank 内的推理/组织，不是跨 bank 搬运或调度器。
- 原生 document ID + replace 可替换源文档；异步 operation ID 可用于幂等提交；invalidate_memory 可软失效原始事实，并触发派生 observation 重算。
- 原生 `MCPExtension` 与 `OperationValidatorExtension.on_retain_complete` 是代码级扩展入口。本实现使用它们，不复制 39 个工具。

## 实际架构

```text
四客户端 ── 单条 /mcp/ ── GlobalMCP ── 原生 39 工具
                            │ recall/reflect
                            ├─ 当前项目 bank
                            └─ global（跨项目经验）
项目 retain 完成 ── GlobalHooks ── SQLite 来源队列（原数据卷）
                                    │ 每分钟、串行、有锁
                                    ├─ 原生 global 检索候选
                                    ├─ 现有腾讯模型提炼并判断复用
                                    └─ 固定 ID replace 写入 global
```

无需新增代理、数据库服务、容器或本地模型。维持 900m 容器上限和远程 embedding/reranker。每次提炼最多 3 条、每周期最多检查 6 个来源、发布 6 个经验；模型输入截断至 24,000 字符，输出受 token 限制。

项目事实继续留在项目 bank。`global` 专门保存跨项目经验，结构为问题特征、根因、解法、适用条件，附源 bank/document；`default` 只作为未传 `bank_id` 时的未分类兜底，不保存提炼经验。SQLite 只保存提炼后的经验、来源索引和状态，不保存原始日志或 API Key。

## 自动机制与提示的区别

| 行为 | 执行机制 | 保证范围 |
|---|---|---|
| 根据当前目录得出项目名 | 客户端 Agent 或客户端 hook | 远端无法知道本地 cwd；本次仍由 Agent 传 bank_id |
| 项目 + global 召回 | MCP run 包装代码 | 每次 MCP recall/reflect 调用自动执行 |
| 项目经验提炼 | 原生 retain 完成 hook + cron | MCP/REST 成功写入均进入队列；最终一致 |
| 会话开始主动查、结束主动存 | 工具说明建议 | 不保证每个客户端一定调用；严格自动需要各自 hooks |
| 其他项目补充检索 | 本地来源索引筛选 | 仅项目与 global 均零命中、且无查询错误时；最多 2 个其他 bank |
| 重复/更新/撤回 | SQLite + 原生文档 replace/delete | 确定性 ID、来源 hash、失败保持待发布 |

不传 bank_id 时当前 bank 是 `default`，服务端仍会同时参考 `global`，但不会把未分类内容当作全局经验来源。用户无需手工指定项目/global；客户端应从 Git 项目名填写项目 bank，服务端自动加入 global。不会用共享 MCP session 的“最后一个项目”猜测，避免多个客户端交叉污染。

当前仅 MCP 的 recall/reflect 执行联合召回；直接 REST recall、原生 mental model 内部生成仍遵守单 bank 语义。

## 去重、更新和失效

- 同来源内容 hash 不变，不重复提炼；相同主题 key 使用固定 `gm-*` 文档 ID。
- 提炼前在 `global` 做一次原生相似检索，模型只能选择已存在候选 ID，或生成新主题 key。不同措辞的语义去重依赖模型判断，不能承诺绝无重复；可在控制台检查后纠正。
- 同一源文档 replace 后，撤销旧来源关系、重新提炼。多来源经验保留全部来源；正文采用最近一次来源提炼结果，条件不同时应区分主题。
- 来源删除或任一原始事实被 invalidate，周期检查会保守撤回该文档贡献。还有其他来源则重建；没有则删除受管理的全局文档和派生记忆。
- 全局原始事实也可以直接用原生 invalidate_memory 失效。来源恢复后周期检查会重新提炼。
- 源原始事实的手工文本编辑不等价于源文档更新：需要同时 replace 对应源文档，才能触发当前版本的重新提炼。
- 发布失败不会标记完成；相同 ID 重试不增加文档。提炼失败最多 5 次，之后需管理员检查 `sources.error` 并重置 attempts；日志只输出错误类型，避免响应中带敏感内容。
- 元数据修复扫描每周期只轮询一个 bank 的 25 条文档，以时间窗+分页游标补捉 hook 遗漏；不是每次 recall 遍历所有 bank。来源检查轮转，规模增长会增加收敛延迟。
- 提炼历史只保留最近 1,000 条状态/hash。真正不同经验仍会增长；不会声称语义无限去重或自动判定全部知识过时。

## 安全及隔离范围

这是当前单用户、Tailscale 内的部署。没有实现多租户隔离；不要直接用于多个互不信任用户共享 `global` 的环境。

送入提炼模型前过滤常见密钥、密码赋值、邮箱、手机号、IP、用户路径，输出再过滤；模型仅提炼技术经验和工作偏好。正则与模型不能保证识别所有敏感信息，客户端仍必须避免 retain 密钥/隐私。本机制不改变原生 retain 已经调用云模型的事实。

## 文件及运维

- `global_memory.py` → `/opt/hindsight/global_memory.py`，只读挂载到 `/app/api/global_memory.py`。
- `docker-compose.aliedge.yml` → 本机 `~/hindsight/docker-compose.aliedge.yml` 与服务端 `/opt/hindsight/docker-compose.yml`。
- `hindsight-global-memory.cron` → `/etc/cron.d/hindsight-global-memory`。
- `hindsight-global-memory.logrotate` → `/etc/logrotate.d/hindsight-global-memory`。
- 状态：`/home/hindsight/.pg0/global-memory.sqlite3`，位于原 `hindsight_hindsight-data` 数据卷，现有每日 04:00/7 天备份继续涵盖该文件。
- 日志：`/var/log/hindsight-global-memory.log`，每周轮转保留 4 份。

修改前服务端配置、env、备份脚本、crontab 已保存在 `/opt/hindsight/backups/config-before-global-20261024-210117/`，目录仅 root 可读。没有将 env 或任何密码复制进仓库。原有每日备份脚本与 crontab 保持不变。

回滚：移除 `/etc/cron.d/hindsight-global-memory`，从上述备份恢复 compose，执行 `docker compose up -d --no-build --pull never`。不删除数据卷；SQLite 与全局经验可保留用于审计。源码绑挂载发生变化后需重启服务加载新的 MCP/hook 代码；worker 每次直接读取文件。

## 验证

本地主机单测：`python3 -m unittest discover -s deploy/hindsight-memory -p 'test_*.py' -v`。

`e2e.py` 是人工运行的远端验收驱动，使用专属 `gm-e2e-project-a/b`，会调用现有云模型：按 `prepare` → 等待 cron → `query` → `repeat` → 核对统计 → `cleanup` → 等待撤回。不得在这些名字已用于真实项目时运行。

2026-10-24 实测：11 个单测在 `ResourceWarning` 升级为错误后全部通过；远端工具数保持 39；B recall 返回 `[B, global]` 且命中 A 提炼出的 Docker DNS 经验；reflect 返回 `[B, global]` 并正确使用该经验；重复 retain 未新增经验；删除 A/B 后来源撤回，global 回到 0 条；default 清空后仍保留为空 bank。

## 四客户端

已核对 Cursor `~/.cursor/mcp.json`、Codex `~/.codex/config.toml`、WorkBuddy `~/.workbuddy/mcp.json`、Hermes `~/.hermes/config.yaml` 都指向同一 `/mcp/`。地址与连接数不变。

服务端功能部署后立即生效；旧会话应重连 MCP 或新建会话以刷新工具描述和已失效的 MCP session。不要求重启电脑；若客户端没有重连按钮，再重启客户端。未宣称四个 GUI 客户端都已完成实际点击验收。
