# 强化判定求值语义契约

- 消费者：执行机构（M3，两处调用：列表初扫与每回合后）、报告（M4，消费 trace）
- 依据：ADR-0003（单一规则集与无状态求值）
- 本契约被后续版本静默破坏即视为回归

## 输入与输出

- 输入：条件树（`dict`，格式见 `docs/specs/rule-file-format.md`）+ `Artifact`（数据模型）+ 游戏档案（`GameProfile`，代号与参数来源，见 `docs/specs/game-profile.md`）
- 输出：`Judgment`，含 `passed`（布尔）与 `trace`（字典树）

## 无状态承诺

- 同一输入永远得到同一输出；求值不修改输入、不读写模块级可变状态、不记住任何跨调用历史
- 单件圣遗物被重复求值（重复扫到、报告重放）结果不变

## 剩余强化次数

- `remaining_rolls = ⌈(等级上限 − 等级) ÷ 词条变动间隔⌉`，向上取整——等级可能停在非节点上（如原神 +17 到 +20 仍有一次变动）；参数取自游戏档案（原神为 ⌈(20 − 等级) ÷ 4⌉，见 design.md D5）
- 恒存在，由等级与档案参数现场推导，不入数据模型

## 字段求值规则

- 数值按游戏显示值比较（攻击力 298、暴击率 5.8）
- `slot` 按部位代号精确比较；`set` 按套装名游戏原文精确比较
- `substat_count` = 副词条条数（上限为档案 substat_max，原神为 4）
- `main.<代号>` 取主词条数值；`sub.<代号>` 在副词条中检索该代号

## 缺失语义

- `main.<代号>` 与 `sub.<代号>` 不存在时：任何数值比较结果为不通过（不抛错）；`exists` 判定为假
  - `main.<代号>` 仅当主词条恰为该代号时存在（例：主词条为攻击力百分比的圣遗物上，`main.crit_rate` 缺失）
- 恒存在字段仅六个：`level` `rarity` `slot` `set` `substat_count` `remaining_rolls`，对它们使用 `exists` 恒为真

## 空数组语义

- `all: []` → 通过
- `any: []` → 不通过

## trace 形状

字典树，与条件树同构：

```jsonc
{ "kind": "all", "passed": true, "children": [ /* 子节点 trace */ ] }
{ "kind": "leaf", "passed": false, "field": "sub.crit_rate",
  "op": ">=", "value": 8, "actual": 5.8 }
{ "kind": "leaf", "passed": true, "field": "sub.crit_rate", "op": "exists", "actual": 5.8 }
```

- exists 叶子无 `value` 键；`actual` 为字段存在时的实际数值、缺失时为 `"missing"`
- 每个 `passed` 可由该节点与子节点的记录独立复核——报告里的每个决策可解释、可重放
