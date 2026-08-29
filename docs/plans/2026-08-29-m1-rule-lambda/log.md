# M1 执行日志

## 2026-08-29 · Task 6.1
- Tried:  首版 test_acceptance.py 把示例规则并列进参数化合法样本又另设一条
          身份断言测试，合计 15 passed，与契约 Verify「14 passed」不符
- Result: 拆开——示例规则单独一条测试（含 game/name 身份断言，覆盖空 slots
          与多层嵌套两类合法形态），内联合法样本参数化 4 条，非法夹具参数化
          9 条，合计恰好 14 passed；全量 207 passed
- Now:    合法样本 5（示例、exists 叶子、两层嵌套、字符串相等、仅标量）、
          非法样本 9（未知字段、字符串用数值运算符、exists 带 value、档案外
          代号、version 不为 1、game 错配、节点键混用、数值给字符串、strategy
          非法）；每个样本双端断言（validate 与 Draft202012Validator 结论一致
          且符合预期）；曾疑似 exists_with_value.json 顶层键笔误，经脚本核对
          为误报
- Convention: 非法样本一律单一违规（其余部分合法），保证失败定位干净；
          双端等价以后续新增样本进 test_acceptance.py 为准


## 2026-08-29 · 代码评审轮（子代理评审 + 修复）
- Tried:  子代理逐条契约核对（基线 169 passed），报 0 阻塞、2 主要（M1 浮点整数
          双端分歧、M2 CLI 测试编码脆弱）、6 次要；本人用探针复核 M1 成立
- Result: 按需求方批准全部修复——
          M1：整数字段「整数」语义与 JSON Schema 2020-12 对齐（1.0 视同 1，
          布尔不算，_is_rule_integer），design.md D4 落档；
          M2：run_cli 注入 PYTHONUTF8=1 + errors="replace"；
          次要：布尔 value 用例、解析字符白名单（拒绝 nan/inf/下划线/全角，
          全角归一化留 M2）、档案清单拒绝重复代号、CLI 写文件兜底 OSError、
          ProfileError/load_profile 类型标注、字符串叶子 trace 用例、
          passed 递归复核用例；重复副词条代号取首个匹配写入 docstring，
          值域校验是否拒绝重复留 M2 定夺
- Now:    全量 193 passed；浮点整数六样本探针双端结论全部一致
- Convention: 整数语义对齐决策在 design.md D4；「含数值的 JSON 互换格式」
          后续一律按数学值判整数，勿用裸 isinstance(int)


## 2026-08-29 · Task 5.1
- Tried:  叶子分支把 value 的类型约束只写在 if/then/else 的 else 子模式里，
          分支主体 properties 未声明 value
- Result: failed——additionalProperties: false 只认同层 properties 声明的键，
          带 value 的合法叶子被生成物整体拒绝（13 例中 1 例失败）
- Now:    value 类型声明提升到分支主体 properties（同时满足「值类型随字段」），
          if/then/else 只管存在性（exists 无 value 由 then 的 not-required 负责）；
          修复后 test_export.py 13 passed、全量 169 passed；另做非正式抽查，
          生成物对七类非法样本全拒、合法样本全过
- Convention: JSON Schema 里 additionalProperties: false 的对象，其允许键必须
          全部出现在同层 properties 中，条件性键也一样；后续改生成物结构时
          沿用 test_export 的双端冒烟（合法 + 非法样本）做回归


## 2026-08-29 · Task 4.1
- Tried:  （无失败尝试，一次通过）测试先行：test_evaluate.py 28 例，红灯为导入失败
- Result: 实现 evaluate.py 后 test_evaluate.py 28 passed、全量 156 passed
- Now:    evaluate 的 rule 参数是条件树（rule 键的值），不是整个规则文件
          （judgment 契约输入原文「条件树」）；字段缺失用模块级不可变哨兵
          _MISSING 表示，trace 里落为字符串 "missing"；remaining_rolls 用整数
          向上取整 -((level − max_level) // interval)，无浮点除法；EXISTS 从
          schema 导入（运算符常量单一来源）
- Convention: trace 键按 spec 顺序构造（kind/passed/field/op/[value]/actual），
          报告序列化字节稳定；求值只依赖 schema.validate 过的输入，
          未知字段/运算符抛 ValueError 属防御性兜底，不构成语义


## 2026-08-29 · Task 3.1
- Tried:  （无失败尝试，一次通过）测试先行：test_schema.py 54 例，红灯为导入失败
- Result: 实现 schema.py 后 test_schema.py 54 passed、全量 128 passed
- Now:    运算符常量 NUMERIC_OPS/STRING_OPS/EXISTS 固化于代码（EXISTS 为字符串
          常量 "exists"）；标量字段分 _NUMERIC_SCALAR_FIELDS（level/rarity/
          substat_count/remaining_rolls）与 _STRING_FIELDS（slot/set）两组内部
          常量，main./sub. 代号取自传入档案；RuleValidationError(message,
          node_path)，顶层键集合错误 node_path 为空串（无节点可定位），节点级
          错误一律带路径且 str(exc) 含「（位置：路径）」
- Convention: 校验错误定位统一走 RuleValidationError 的 node_path 属性，
          任务 5.1 导出生成物与任务 6.1 双端断言沿用同一批样例结构


## 2026-08-29 · Task 2.2
- Tried:  （无失败尝试，一次通过）测试先行：test_profile.py 36 例，红灯为导入失败
- Result: 实现 profile.py 与原神档案后 test_profile.py 36 passed、全量 74 passed
- Now:    ProfileError 携带 message + 档案路径；GameProfile.stats/slots 为 frozenset
          （集合语义），rarity_range 二元升序整数组在校验时拆为 rarity_min/rarity_max；
          KNOWN_ROUND_MECHANISMS 目前仅 staged_fill；validate_artifact 只查值域四项
          （等级/星级/部位/副词条条数），词条代号合法性不在其中（契约如此，D7 的
          「不可能组合走缺失语义」也与之呼应）
- Convention: 代号清单的唯一权威是 assets/resource/genshin/profile.json；
          test_profile.py 的 GENSHIN_STATS/GENSHIN_SLOTS 常量与真实档案断言相等，
          档案改动须同步契约与该常量


## 2026-08-29 · 执行前置
- Tried:  按需求方指令，规划工件先行入库
- Result: 两笔提交——d152565（ADR-0003/0004 + spec 主文档 + CONTEXT.md + AGENTS.md 定案）、
          ed7a03f（M1 计划 design/proposal/三份契约）
- Now:    assets/resource/model/*（OCR 模型二进制）保持未跟踪，不属于规划工件

## 2026-08-29 · Task 2.1
- Tried:  test_model.py 用例 "+ 19" 期望 parse_level 抛 ValueError
- Result: failed——模块约定「先去空白再解析」，去空白后 "+ 19" 即 "+19"，是合法等级文本
- Now:    改用例为 parse_level("+ 19") == 19；实现零改动，37 passed
- Convention: 所有 OCR 文本解析函数一律先 strip_spaces 再解析，含数字内部的空格；
          形状校验错误统一抛 ValueError，值域校验错误（任务 2.2 起）抛
          ArtifactValidationError / ProfileError


## 2026-08-29 · Task 1.1
- Tried:  先写 test/test_smoke.py 再建骨架（TDD 红绿两步）
- Result: 红灯 `ModuleNotFoundError: No module named 'agent.rule_lambda'` → 建骨架后 `1 passed`
- Now:    requirements-dev.txt 钉主版本（pytest>=8,<9 / jsonschema>=4,<5，实装 8.4.2 / 4.26.0）；
          pytest.ini 设 testpaths = test；agent/__init__.py 为空文件保证导入不拉 maa；
          rule_lambda 五文件仅 docstring
- Convention: `python -m pytest` 一律从仓库根运行（cwd 入 sys.path 使 `import agent.rule_lambda`
          可用，裸 `pytest` 无此保证）；导入 agent.rule_lambda 不得连带导入 maa，
          由 test_smoke.py 守卫
