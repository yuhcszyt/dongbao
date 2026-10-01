# Galgame（娱乐公司经营）

聊天驱动的娱乐圈经营 + 多女星关系网 Galgame。无网页 UI。

## 怎么玩

在 Cursor 对话里说：

- `开始 Galgame`
- `继续 Galgame`
- `继续刘浩存 Galgame`

Agent 会按 `.cursor/skills/galgame-entertainment/SKILL.md` 严格加载本目录文件后开演。

## 目录

| 路径 | 职责 |
|------|------|
| `GAME.md` | 总规则、状态机、输出格式、写回约定 |
| `WORLD.md` | 世界与公司设定、事件池、开局建议 |
| `skills/liu-haocun/` | 刘浩存角色 Skill（含 `anchors.md` 公开近况） |
| `skills/characters/REALITY.md` | 现实女星检索与建卡硬规则 |
| `skills/characters/ROSTER.md` | 角色名册与扩容占位 |
| `skills/characters/_template/` | 新角色模板（含 anchors） |
| `company/company.json` | 轻量公司状态（虚构 AU） |
| `projects/projects.json` | 项目列表（`public` / `game_au`） |
| `saves/current.json` | 当前存档（权威状态） |
| `saves/history/` | 节点备份 |

权威玩法目录是这里，不是 `.scratch/gal-tavern-play/`。
