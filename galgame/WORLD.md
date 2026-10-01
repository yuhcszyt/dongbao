# 世界设定

虚构经营层 + 现实公开事业锚点。现实公众人物的作品、活动、访谈语气以各角色 `anchors.md` 为准；私人互动属于本游戏虚构世界。

## 公司（游戏 AU）

见 `company/company.json`。

默认公司名：**星衡影业**（虚构）。

业务：电影、电视剧、综艺、品牌商务、艺人经纪。

说明：现实中刘浩存等艺人的经纪归属以公开报道为准（见角色 anchors）；游戏里「与星衡签约/重点合作」是 AU，用来支撑经营玩法，**不是**对现实公司的断言。

轻量状态服务剧情：资金、口碑、影响力、在办项目、艺人与员工列表。

## 玩家

```yaml
player:
  identity: 娱乐公司老板 / 创始人
```

## 角色槽位

- 核心：刘浩存（`skills/liu-haocun/`，含公开近况 anchors）
- 名册与扩容：`skills/characters/ROSTER.md`
- 新增现实女星流程：`skills/characters/REALITY.md`

```yaml
liu_haocun:
  identity: 重点合作 / 签约女演员（AU）
  relationship_with_player: 老板与艺人
  relationship_stage: S0
  affection: 0
  trust: 5
  comfort: 0
```

## 多角色关系网

合作、朋友、陌生、竞争、不喜欢、欣赏、误会、和解均可。  
禁止全员只围着玩家转。现实人物之间默认先写公开合作关系。

## 项目

见 `projects/projects.json`。

- `source: public` → 对齐公开组讯/定档/宣发
- `source: game_au` → 仅游戏内提案或会议，可失败可搁置

## 开局场景建议（对齐 2026-10 公开近况）

时间：2026 年 10 月 1 日 15:20  
地点：北京 · 星衡影业总部 小会议室  

事由：对齐四季度档期——《美顺与长生》宣发窗口、在拍/刚拍电影的宣传边界、品牌与杂志义务是否过载。刘浩存以工作状态到场；与玩家仍是正式合作关系。
