# 新增女星 / 角色步骤

1. 复制 `galgame/skills/characters/_template/` → `galgame/skills/<slug>/`
2. 填完 `SKILL.md` `profile.md` `speech.md` `relationships.md` `scenarios.md`
3. 在 `WORLD.md` 角色槽位加一句登记
4. 在 `saves/current.json` 的 `characters` 增加同结构条目
5. 更新相关角色的 `relationships.md`（互相写一眼）
6. 如需进开局，把 slug 写入 `active_characters`

真人明星：遵守 `GAME.md` 现实人物规则与亲密上限。  
虚构角色：可另标 `fiction: true`；仅虚构可走露骨成人线。
