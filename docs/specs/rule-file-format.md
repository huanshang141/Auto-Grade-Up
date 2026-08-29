# 规则文件格式（rules.json v1）契约

- 消费者：决策机构校验（M1，权威实现 `agent/rule_lambda/schema.py`）、规则编辑器（M5，消费 JSON Schema 生成物）
- 本契约被后续版本静默破坏即视为回归

## 文件结构

顶层键与类型：

```jsonc
{
  "version": 1,                  // 仅接受 1
  "game": "genshin",             // 游戏标识，须与运行时游戏档案一致
  "name": "默认双爆规则",         // 非空字符串
  "candidates": { /* 见下 */ },
  "rule": { /* 条件树，见下 */ },
  "fodder": { /* 见下 */ }
}
```

- 顶层键集合固定为 `version` `game` `name` `candidates` `rule` `fodder`：缺一或多出未知键均非法
- `candidates`（四键齐全，不可缺省）：
  - `rarity`: 数组，元素在该游戏档案 rarity_range 内（原神为 1–5）；空数组表示不限
  - `slots`: 数组，元素为该游戏档案的部位代号之一；空数组表示不限
  - `max_level`: 整数，仅处理等级低于它的圣遗物（不与档案 max_level 比对，超出档案上限无意义但无害）
  - `respect_lock`: 布尔
- `fodder`（两键齐全，不可缺省）：
  - `strategy`: 字符串，须与游戏档案 round_mechanism 一致（第一版仅 `"staged_fill"`）
  - `respect_lock`: 布尔（声明性字段，游戏机制保证）

## 条件树

- 并且组：`{"all": [子节点, ...]}`；空数组视为通过
- 或者组：`{"any": [子节点, ...]}`；空数组视为不通过
- 叶子：`{"field": <字段名>, "op": <运算符>, "value": <值>}`；`op` 为 `exists` 时**不得**带 `value`
- 组节点与叶子不得混用键（`all`/`any` 与 `field` 互斥，一个节点只能是一种）

## 字段命名空间

| 字段 | 值类型 | 存在性 |
| --- | --- | --- |
| `level` | number | 恒存在 |
| `rarity` | number | 恒存在 |
| `slot` | string（部位代号） | 恒存在 |
| `set` | string（套装名游戏原文） | 恒存在 |
| `substat_count` | number | 恒存在 |
| `remaining_rolls` | number（由等级推导） | 恒存在 |
| `main.<属性代号>` | number | 仅当主词条恰为该代号时存在，其余情况缺失；缺失语义与 `sub.*` 相同 |
| `sub.<属性代号>` | number | 可能缺失 |

未知字段名（不在上表、代号不在清单）一律非法。

## 代号清单（由游戏档案定义）

代号枚举不再固化于代码或格式定义：校验时从游戏档案读取（档案契约见 `docs/specs/game-profile.md`，依据 ADR-0004）。下表为原神档案的现行内容，作为样例与测试基准。

部位代号（5 个）：`flower` `plume` `sands` `goblet` `circlet`。

属性代号（19 个）：`crit_rate` `crit_dmg` `hp` `hp_percent` `atk` `atk_percent` `def` `def_percent` `elemental_mastery` `energy_recharge` `healing_bonus` `physical_dmg_bonus` `pyro_dmg_bonus` `hydro_dmg_bonus` `electro_dmg_bonus` `cryo_dmg_bonus` `anemo_dmg_bonus` `geo_dmg_bonus` `dendro_dmg_bonus`。

「包含」运算符为预留位，v1 不接受。

## 运算符与值的规则

- 数值字段（`level` `rarity` `substat_count` `remaining_rolls` `main.*` `sub.*`）：接受 `> < >= <= == !=`，`value` 必须是数字；接受 `exists`（主/副词条字段用它没有意义但合法）
- 字符串字段（`slot` `set`）：仅接受 `==` `!=` `exists`，`value` 必须是字符串
- `exists` 一律不带 `value`

## 校验纪律

- 解析或校验失败 → 立即停止任务并提示；**不回退默认规则**（消耗性操作绝不带错误规则执行）
- 错误必须携带节点路径，形如 `rule.all[0].any[1]`，供编辑器定位到节点
- `version` 不等于 1 → 非法
- `game` 缺失或与当前游戏档案的 `game` 不一致 → 非法（运行时表现为立即停止）

## JSON Schema 导出命令

- 函数接口：`export_json_schema(profile) -> dict`，`$schema` 为 2020-12 方言；生成物的代号枚举来自传入的游戏档案
- 命令行接口：`python -m agent.rule_lambda export <档案路径> <输出路径>`（`__main__.py` 为唯一命令行入口，为 M3 子命令预留），成功退出码 0 并写出文件
- 生成物必须覆盖：结构（含顶层键集合固定）、game 字段比对、档案代号枚举与 candidates 的 slots/rarity 元素值域、fodder.strategy 枚举（与档案 round_mechanism 同源）、运算符与字段类型兼容（`if/then`）、`exists` 无 `value` 的形状、值类型随字段
- 枚举一律排序输出，保证同一档案两次导出逐字节一致
- 生成物不手工编辑；修改格式或档案数据后重新导出（spec §8 同源方式）
- 等价性保证：同一批合法/非法样本上，Python 校验与通用校验器结论必须一致（固化于 `test/test_acceptance.py`）
