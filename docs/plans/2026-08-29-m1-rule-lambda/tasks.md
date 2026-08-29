# M1 任务清单

> 2026-08-29 修订：纳入多游戏架构（ADR-0004）。新增任务 2.2（游戏档案加载与原神档案数据）；2.1/3.1/4.1/5.1/6.1 的契约改为档案驱动（校验与求值接受档案参数、导出按档案参数化）；原任务 4.1（剩余强化次数公式文档修订）已随该次定案直接落地 spec 与 CONTEXT，不再单列任务，章节号相应前移。执行模式不变。

执行模式（plan-contract）：当前会话内执行，**每个任务完成后停下汇报，等指令再继续**。汇报必须附 Verify 命令的真实输出、变更文件、提交哈希与 `log.md` 新增条目。一个任务 = 一个提交，提交信息沿用仓库现行风格（中文 conventional commits，如 `feat: 数据模型与数值解析`）。

规则文件格式契约见 `specs/rule-file-format/spec.md`，游戏档案契约见 `specs/game-profile/spec.md`，求值语义契约见 `specs/judgment/spec.md`，三者对任务 2.2/3.1/4.1/5.1/6.1 有约束力。契约与实际不符时：先改上游工件（本清单或 `design.md`），记录 `log.md`，停下汇报，不在代码里绕行。

---

## 1. 骨架与环境

- [x] 1.1 开发环境与包骨架
  Goal:     依赖就绪，`agent/rule_lambda` 可作为纯包导入，maa 隔离有测试兜底
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:407-435  (§13 目录结构)
            agent/main.py:1-26  (现有 agent 运行模型；本任务不接线)
  Touch:    requirements-dev.txt | pytest.ini | agent/__init__.py | agent/rule_lambda/__init__.py | agent/rule_lambda/model.py | agent/rule_lambda/profile.py | agent/rule_lambda/schema.py | agent/rule_lambda/evaluate.py | test/test_smoke.py
  Contract:
    requirements-dev.txt: pytest、jsonschema（钉主版本）
    pytest.ini: testpaths = test
    agent/__init__.py: 空文件（禁止任何导入）
    rule_lambda 五个文件: 仅 docstring，无实现
    test/test_smoke.py: 导入 agent.rule_lambda 后断言 "maa" 不在 sys.modules
  Verify:   python -m pip install -r requirements-dev.txt && python -m pytest -q → 1 passed
  Done:     冒烟测试通过；包结构与 spec §13 一致

---

## 2. 数据模型与游戏档案

- [x] 2.1 数据模型与数值解析（model.py）
  Goal:     定义 Artifact/StatValue 与 OCR 文本解析器，JSON 往返无损；形状校验在模型，值域校验归档案（任务 2.2）
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:87-113  (§3 数据模型与解析约定)
            CONTEXT.md:7-15  (游戏概念术语)
  Touch:    agent/rule_lambda/model.py | test/test_model.py
  Contract:
    @dataclass StatValue:  name: str（属性代号）、value: float
    @dataclass Artifact:   slot: str、rarity: int、set: str、level: int、locked: bool、
                           main: StatValue、substats: list[StatValue]
    Artifact.to_dict()/from_dict(): 键名与 spec §3 示例一致，往返相等
    parse_stat_value(text) -> tuple[float, bool]:  "5.8%"→(5.8, True)、"117"→(117.0, False)；先去空白；非法抛 ValueError
    parse_level(text) -> int:  "+19"→19、"0"→0；非法抛 ValueError
    strip_spaces(text) -> str: 去除全部空白字符
    本任务只做形状校验（字段类型——rarity/level 为 int、键名、列表结构）；等级/星级/部位/条数的值域校验由 validate_artifact(artifact, profile) 承担（任务 2.2），本任务不含
  Verify:   python -m pytest test/test_model.py -q → 全部通过
  Done:     往返、解析、边界（空串、多空格、百分号、类型错误）均有测试

- [ ] 2.2 游戏档案加载与校验（profile.py）+ 原神档案数据
  Goal:     GameProfile 数据结构、加载与校验、Artifact 值域校验；交付原神档案数据文件
  Read:     specs/game-profile/spec.md  (本变更文件夹内，档案契约全文)
            docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:173-175  (属性代号与游戏档案段)
            docs/adr/0004-config-driven-multi-game.md  (多游戏决策)
            specs/rule-file-format/spec.md  (代号清单节：原神 19 + 5 清单)
  Touch:    agent/rule_lambda/profile.py | assets/resource/genshin/profile.json | test/test_profile.py
  Contract:
    @dataclass GameProfile:  version: int、game: str、display_name: str、
                             stats: frozenset[str]、slots: frozenset[str]、
                             max_level: int、roll_interval: int、
                             rarity_min: int、rarity_max: int、
                             substat_max: int、round_mechanism: str
                             （stats/slots 用集合语义做校验；导出生成物时的排序输出由任务 5.1 保证）
    load_profile(path) -> GameProfile:  档案缺失 / version ≠ 1 / 结构不符 / 清单为空 /
                                        rarity_range 非二元升序整数组 / round_mechanism 未知
                                        → 抛 ProfileError（message + 文件路径）
    KNOWN_ROUND_MECHANISMS: frozenset = {"staged_fill"}
    class ArtifactValidationError(Exception):  与 ProfileError 同级的自定义异常，便于 M2/M3 按类型分支
    validate_artifact(artifact, profile) -> None:  level ∈ [0, max_level]、rarity ∈ [rarity_min, rarity_max]、
                                                   slot ∈ slots、len(substats) ≤ substat_max；
                                                   违规抛 ArtifactValidationError
    assets/resource/genshin/profile.json:  game=genshin、display_name=原神、19 属性代号（清单见
                                           rule-file-format 契约）、5 部位代号、max_level=20、
                                           roll_interval=4、rarity_range=[1,5]、substat_max=4、
                                           round_mechanism=staged_fill
  Verify:   python -m pytest test/test_profile.py -q → 全部通过，且测试含对 assets/resource/genshin/profile.json 真文件的加载断言
  Done:     原神档案加载即用；每类非法档案逐类被拒；值域校验覆盖越界等级、越界星级、未知部位、超限副词条

---

## 3. 格式定义与校验

- [ ] 3.1 规则文件校验（schema.py）
  Goal:     权威校验实现：非法规则逐类被拒并定位到节点，合法规则零误拒；代号与值域取自游戏档案
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:115-219  (§4 全节)
            docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:323-337  (§8 编辑器对错误定位的需求)
            specs/rule-file-format/spec.md  (本变更文件夹内，契约全文)
  Touch:    agent/rule_lambda/schema.py | test/test_schema.py
  Contract:
    常量: NUMERIC_OPS、STRING_OPS、EXISTS（运算符集合是格式的一部分，固化于代码）；
          代号枚举不再是常量，从参数档案取
    class RuleValidationError(Exception):  message: str、node_path: str
    validate(rules: dict, profile: GameProfile) -> None:  合法返回 None；非法抛 RuleValidationError
    node_path 形如 "rule.all[0].any[1]"
    校验清单（全部要有对应测试）: 顶层键集合固定（六键——version/game/name/candidates/rule/fodder，
          多一少一均非法）、candidates 四键与 fodder 两键齐全、version==1、game 与 profile.game 一致、
          name 非空 str、candidates 取值域（slots 元素 ∈ 档案 slots、rarity 元素 ∈ 档案 rarity_range、
          max_level 不与档案上限比对）、组/叶子键互斥、字段名合法（命名空间表 + 档案代号）、
          运算符与字段类型兼容、exists 不带 value、数值字段 value 为数字、字符串字段 value 为 str、
          fodder.strategy 仅 "staged_fill"（须与 profile.round_mechanism 一致）
  Verify:   python -m pytest test/test_schema.py -q → 全部通过
  Done:     每类非法样例的错误信息含节点路径；合法样例全部通过；game 错配被拒

---

## 4. 求值

- [ ] 4.1 条件树求值与 trace（evaluate.py）
  Goal:     ADR-0003 的无状态求值语义完整落地，每个判定可解释、可重放；公式按档案参数化
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:214-229  (判定执行时机 + §5)
            docs/adr/0003-single-rule-set-stateless-judgment.md  (无状态与重复扫到语义)
            specs/judgment/spec.md  (本变更文件夹内，契约全文)
  Touch:    agent/rule_lambda/evaluate.py | test/test_evaluate.py
  Contract:
    @dataclass Judgment:  passed: bool、trace: dict
    evaluate(rule: dict, artifact: Artifact, profile: GameProfile) -> Judgment
    remaining_rolls(artifact, profile) -> int = ⌈(profile.max_level − level) / profile.roll_interval⌉
    缺失语义: main.<代号> 与 sub.<代号> 缺失 → 数值比较 False、exists False
    前置条件: rule 已通过 validate（evaluate 不重复校验，未校验输入的行为未定义）
    空数组: all → True、any → False
    trace 节点形状: 见 specs/judgment/spec.md（actual 缺失时为 "missing"；exists 叶子无 value 键）
    无状态: 不修改输入、不读写模块级可变状态
  Verify:   python -m pytest test/test_evaluate.py -q → 全部通过
  Done:     无状态（同输入两次求值结果相同）、缺失（main 与 sub 同语义）、空组、trace 同构、
            remaining_rolls（原神档案下 0/4/16/17/19/20 各档）均有测试

---

## 5. 导出命令

- [ ] 5.1 JSON Schema 导出（schema.py 扩展 + CLI）
  Goal:     导出命令按档案产出合法生成物，语义覆盖度足以拒绝非法样本（M5 编辑器消费）
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:216-219  (版本与校验)
            docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:336  (§8 同源方式)
            docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:440  (M1 验收标准)
            specs/rule-file-format/spec.md  (导出命令接口契约)
  Touch:    agent/rule_lambda/schema.py | agent/rule_lambda/__main__.py | test/fixtures/profiles/second_game.json | test/test_export.py
  Contract:
    export_json_schema(profile: GameProfile) -> dict:  $schema 为 2020-12 方言；代号枚举来自 profile；
                                                       枚举一律排序输出（两次导出逐字节一致）
    CLI:  python -m agent.rule_lambda export <档案路径> <输出路径>
          （__main__.py 为唯一命令行入口，为 M3 子命令预留）；成功退出码 0 并写文件
    生成物覆盖: 结构（顶层键集合固定）、game 字段、档案代号枚举与 candidates slots/rarity 元素值域、
                fodder.strategy 枚举（与档案 round_mechanism 同源）、运算符-字段兼容（if/then）、
                exists 无 value、值类型随字段
    生成物可被 jsonschema.Draft202012Validator 直接加载
  Verify:   python -m pytest test/test_export.py -q → 全部通过（测试内经 subprocess 调 CLI，以原神档案为输入，输出到临时目录）
  Done:     命令可用、生成物合法且加载成功、同一档案两次导出逐字节一致、
            test/fixtures/profiles/second_game.json（stats 与 slots 至少各一处与原神档案不同）
            导出的生成物枚举随之不同

---

## 6. 验收

- [ ] 6.1 示例规则、样本集与双端一致性验收
  Goal:     M1 三条验收标准全部满足，双端等价有测试固化
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:118-148  (§4 示例规则)
            docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:440  (M1 验收标准)
  Touch:    docs/examples/rules.example.json | test/fixtures/rules/ | test/fixtures/profiles/ | test/test_acceptance.py
  Contract:
    示例规则 = §4 双爆规则的代号版（含 game: "genshin"），通过 validate(·, 原神档案)
    样本集: 合法 ≥5（空 slots、exists 叶子、两层嵌套、字符串字段 ==、仅标量字段），
            非法 ≥9（未知字段名、字符串字段用 >=、exists 带 value、档案外代号、version≠1、
            game 错配、节点键混用、数值字段给字符串值、fodder.strategy 非法）
    非法样本放 test/fixtures/rules/，第二档案沿用任务 5.1 创建的 test/fixtures/profiles/second_game.json
    双端断言: 每个样本上 validate(·, 档案) 与 Draft202012Validator(export_json_schema(档案)) 结论一致；
              docs/examples/rules.example.json 同样通过 Draft202012Validator(export_json_schema(原神档案))
  Verify:   python -m pytest test/test_acceptance.py -q → 14 passed；python -m pytest -q → 全部通过
  Done:     验收三条满足：pytest 全绿、合法过/非法拒双端一致、导出合法

---

## 完成动作

全部勾选后：重跑每个任务的 Verify；把 `specs/*/spec.md` 折叠进 `docs/specs/` 正本；本变更文件夹移入 `docs/plans/archive/`（`log.md` 永不删除）；停下汇报，由需求方决定落地方式。
