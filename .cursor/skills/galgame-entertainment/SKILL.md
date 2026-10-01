---
name: galgame-entertainment
description: >-
  Runs the entertainment-company Galgame (经营 + 多女星关系网) from Markdown/JSON saves.
  Use when the user says 继续刘浩存 Galgame, 继续 Galgame, 开始 Galgame, 玩 Galgame,
  刘浩存剧情, or asks to continue/start the entertainment company romance sim.
---

# 娱乐公司 Galgame（严格加载）

聊天 Galgame。无网页 UI。权威状态在文件，不依赖上下文记忆。

## 触发后必做（严格顺序）

每次用户说「开始 / 继续 Galgame」或点名角色剧情时：

1. 读 [`galgame/GAME.md`](../../../galgame/GAME.md) — 规则与输出格式
2. 读 [`galgame/WORLD.md`](../../../galgame/WORLD.md) — 世界与公司设定
3. 读 [`galgame/saves/current.json`](../../../galgame/saves/current.json) — 当前存档
4. 读 [`galgame/company/company.json`](../../../galgame/company/company.json)
5. 读 [`galgame/projects/projects.json`](../../../galgame/projects/projects.json)
6. 按存档 `active_characters` / 用户点名，读对应角色 Skill（例：[`galgame/skills/liu-haocun/SKILL.md`](../../../galgame/skills/liu-haocun/SKILL.md) 及同目录 `anchors.md` 等）
7. 现实人物：核对 `anchors.md` 是否覆盖近况；过期则先按 [`REALITY.md`](../../../galgame/skills/characters/REALITY.md) 补搜再开演
8. 若 Skill / `GAME.md` / `WORLD.md` 比上次会话更新，**以磁盘最新版为准**
9. 生成一轮剧情（输出格式见 `GAME.md`）
10. 写回 `galgame/saves/current.json`；重大节点可另存 `galgame/saves/history/`
11. 需要时同步 `company.json` / `projects.json`

未完成加载前，禁止开写剧情。事业线必须对齐各角色 `anchors.md` 的公开事实。

## 核心身份（覆盖旧设定）

- 玩家 = 娱乐公司老板 / 创始人
- 刘浩存 = 公司旗下重点女演员
- 初始关系 = 老板与旗下艺人（S0），非恋爱开局
- 事业资源 ≠ 私人关系

旧的「后宫 / 老公 / 自动争宠」设定对本系统无效。本系统权威目录是 `galgame/`，不是 `.scratch/gal-tavern-play/`。

## 新增角色

复制 `galgame/skills/characters/_template/`，改名后填入；在 `WORLD.md` 与存档 `characters` 登记。
