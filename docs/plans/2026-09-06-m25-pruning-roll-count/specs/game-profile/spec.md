# 游戏档案（game profile）契约

- 消费者：决策机构（字段枚举、值域、剩余强化次数参数、单次强化成长上限）、规则编辑器（M5，字段下拉与校验）、观测机构（M2，对照文档的代号合法性参照）
- 依据：ADR-0004（配置驱动的多游戏架构）
- 本契约被后续版本静默破坏即视为回归

## 文件位置与选中机制

- 每游戏一份，随该游戏资源包分发：`assets/resource/<游戏>/profile.json`（原神为 `assets/resource/genshin/profile.json`）
- 运行器中选择资源包即选择游戏；运行时 agent 从 `PI_RESOURCE` 环境变量（PI v2.5.0 约定，MFAAvalonia 已实现注入）的资源包路径内定位本档案。M1 阶段以文件路径直接加载；环境变量解析属 M3 运行时接线，接口按「传入档案路径」设计，不依赖环境变量即可完整测试

## 文件结构

```jsonc
{
  "version": 1,                    // 仅接受 1
  "game": "genshin",               // 游戏标识；规则文件的 game 字段须与之一致
  "display_name": "原神",
  "stats": ["crit_rate"],          // 属性代号清单（原神 19 个，见 rule-file-format 契约）
  "slots": ["flower"],             // 部位代号清单（原神 5 个）
  "max_level": 20,                 // 等级上限
  "roll_interval": 4,              // 词条变动间隔（原神每 4 级一次）
  "rarity_range": [1, 5],          // 星级范围（含端点）
  "substat_max": 4,                // 副词条上限
  "round_mechanism": "staged_fill",// 回合机制声明；代码只接受已实现的机制
  "roll_growth_max": {             // 单次强化成长上限表（M2.5 新增）
    "5": {"crit_rate": 3.9},       // 星级（字符串数字）→ 属性代号 → 单次强化最大成长值
    "4": {"crit_rate": 3.1}
  }
}
```

- `roll_growth_max` 的星级键必须落在 `rarity_range` 内、属性代号必须在 `stats` 清单内、值必须为正数；允许不覆盖全部星级（原神第一版仅录 4 星与 5 星，1~3 星暂不支持强化）
- 数值为该星级该词条单次强化成长的最大档位（社区整理的公开成长档位表查证录入，剪枝推导只需要上界）

## 校验纪律

- 档案缺失、`version` 不为 1、结构不符、清单为空、`rarity_range` 非法（非二元升序整数组）、`round_mechanism` 为代码不认识的值、`roll_growth_max` 的星级键或属性代号非法或值非正 → 抛错并提示，调用方立即停止
- 规则文件 `game` 与档案 `game` 不一致 → 立即停止（由规则校验函数在持有档案时比对）
- 规则文件 `candidates.rarity` 引用无上限表数据的星级 → 规则校验失败（M2.5 起）；实际圣遗物星级在求值时查表缺失 → `ProfileError` 立即停止
- 字段对照文档映射到档案不存在的代号 → 立即停止（M2 接线，纪律与 spec §4 一致）

## 派生量与值域

- 剩余强化次数 = ⌈(max_level − 等级) ÷ roll_interval⌉，向上取整
- 圣遗物值域校验：等级 ∈ [0, max_level]、星级 ∈ rarity_range、部位 ∈ slots、副词条条数 ≤ substat_max；词条强化次数 ∈ [0, ⌈max_level ÷ roll_interval⌉] 且待激活词条的次数必须为 0（M2.5 起，随词条值对象扩展）

## 编辑与分发

- 档案是数据：修改档案不需要改代码、不需要发版；新游戏立项 = 新档案 + 新资源包 + 该游戏的真机研究
- JSON Schema 导出按档案参数化（见 `docs/specs/rule-file-format.md` 导出命令节）
