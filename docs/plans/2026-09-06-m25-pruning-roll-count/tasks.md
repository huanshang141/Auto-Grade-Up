# M2.5 任务清单

执行模式：plan-contract，一任务一提交，每任务停下汇报。设计依据：同目录 design.md（D1~D8）、discussion.md、ADR-0006 / ADR-0007。

## 1. 档案与数据模型

- [x] 1.1 档案单次强化成长上限表
  Goal:     决策机构可按「星级 × 属性代号」查单次强化成长最大值；缺表在规则校验层与求值层报错。
  Read:     assets/resource/genshin/profile.json（现行键集）
            agent/rule_lambda/profile.py:36-64   （GameProfile 字段）
            agent/rule_lambda/profile.py:67-136  （load_profile 校验结构）
            agent/rule_lambda/profile.py:167-193 （validate_artifact 值域校验）
            docs/plans/2026-09-06-m25-pruning-roll-count/discussion.md（可达性推导公式节）
  Touch:    assets/resource/genshin/profile.json | agent/rule_lambda/profile.py | test/test_profile.py
  Contract:
    档案新键 roll_growth_max：{"5": {<19 代号>: 正数}, "4": {…}}，数值为查证后的单次强化成长最大档位
    （录入前用社区公开的成长档位表查证核对，来源链接记入 log.md）
    GameProfile 增 roll_growth_max: dict[int, dict[str, float]] 与来源路径字段；方法 growth_max(rarity, code) -> float，
    查无此星级 → 抛 ProfileError（消息含星级与代号）
    load_profile 校验：星级键必须可解析为整数且落在 rarity_range 内、代号必须在 stats 内、值必须为正数
    validate 增加：candidates.rarity 元素无表 → RuleValidationError（此校验在 2.1 接线，本任务先备好档案侧数据结构）
  Verify:   python -m pytest test/test_profile.py -q  →  新增断言全绿（表结构、非法键拒绝、growth_max 查询与缺表抛错）
  Done:     原神档案带 4/5 星全 19 代号的上限表；非法档案样例被拒并带路径报错。

- [x] 1.2 词条值对象扩展（roll_count / pending）
  Goal:     词条可携带强化次数（可空）与待激活标记，序列化形状可区分「未知」与「0」。
  Read:     agent/rule_lambda/model.py:16-47  （StatValue / Artifact 定义）
            agent/rule_lambda/model.py:50-117  （from_dict / to_dict / _check_stat）
            agent/rule_lambda/profile.py:167-193（validate_artifact）
            docs/plans/2026-09-06-m25-pruning-roll-count/design.md（D2）
  Touch:    agent/rule_lambda/model.py | agent/rule_lambda/profile.py | test/test_model.py | test/test_profile.py
  Contract:
    StatValue(name, value, roll_count: int | None = None, pending: bool = False)
    to_dict：roll_count 键始终写出（null 或数字）；pending 仅 True 时写出
    from_dict：roll_count 接受键缺省 / null / 非负整数；pending 接受缺省（False）/ 布尔
    validate_artifact：roll_count ∈ [0, ⌈max_level ÷ roll_interval⌉]；pending 为真时 roll_count 必须为 0 或 null
  Verify:   python -m pytest test/test_model.py test/test_profile.py -q  →  全绿
  Done:     旧形状 JSON（无新键）仍可加载；新形状往返（to_dict → from_dict）无损。

## 2. 决策机构

- [x] 2.1 规则文件格式修订（roll_rule / 白名单 / 导出同步）
  Goal:     规则文件支持可选次数规则树；词条字段运算符收紧；Schema 生成物同步。
  Read:     agent/rule_lambda/schema.py:20-31   （命名空间常量与运算符集合）
            agent/rule_lambda/schema.py:60-92   （validate 顶层键校验）
            agent/rule_lambda/schema.py:206-266 （_validate_leaf / _field_kind）
            agent/rule_lambda/schema.py:269-373 （export_json_schema）
            docs/plans/2026-09-06-m25-pruning-roll-count/design.md（D1 / D4 / D5）
            docs/plans/2026-09-06-m25-pruning-roll-count/specs/rule-file-format/spec.md
  Touch:    agent/rule_lambda/schema.py | test/test_schema.py | test/test_export.py | test/test_acceptance.py
  Contract:
    顶层键：rule/fodder 等必填集合不变，roll_rule 可选；出现未知键仍拒绝
    roll_rule 树：结构校验与 rule 同一套；叶子 field 仅接受 roll.<代号>（其他命名空间 → RuleValidationError）；
    节点路径前缀 roll_rule.（如 roll_rule.all[0]）
    字段注册：roll.<代号> 为 number 型；sub.*/roll.* 的运算符集合收紧为 {">", ">=", exists}；
    candidates.rarity 元素查档案上限表缺失 → RuleValidationError
    export_json_schema：roll_rule 可选分支、roll 字段分支、词条分支 op 枚举收紧、roll_rule 内字段枚举限定，全部同步
    version 仍仅接受 1
  Verify:   python -m pytest test/test_schema.py test/test_export.py test/test_acceptance.py -q  →  全绿
  Done:     合法样例（含 roll_rule）双端通过；词条字段用 == / <= 的样例两端一致拒绝。

- [x] 2.2 求值语义修正（可达值 / roll 字段 / trace 形状）
  Goal:     词条数值条件按乐观可达值求值，剪枝生效且 trace 可解释。
  Read:     agent/rule_lambda/evaluate.py:20-46  （Judgment / evaluate / remaining_rolls）
            agent/rule_lambda/evaluate.py:84-114 （_field_value）
            agent/rule_lambda/evaluate.py:117-130（_compare）
            docs/plans/2026-09-06-m25-pruning-roll-count/design.md（D3 / D5）
            docs/plans/2026-09-06-m25-pruning-roll-count/specs/judgment/spec.md
  Touch:    agent/rule_lambda/evaluate.py | test/test_evaluate.py
  Contract:
    推导：R = ⌈(max_level − level) ÷ roll_interval⌉；U = min(substat_max − 已解锁条数, R)；budget = R − U
      （已解锁条数 = 非 pending 副词条数；待激活转正计入 U）
    sub.<代号> 实际值 = 词条当前值 + budget × profile.growth_max(rarity, 代号)；待激活词条当前值即预览值
    roll.<代号> 实际值 = 词条 roll_count + budget；roll_count 为 null 或词条缺失 → 缺失语义
    main.*、标量字段维持当前值口径；missing 语义不变（待激活词条视为存在）
    evaluate 增可选参数 roll_rule=None：None → passed 仅由 rule 决定、trace["roll_rule"] 为 null；
      传入 → 两树各求 trace，passed 为两者与合并
    trace：顶层 {"rule": <树>, "roll_rule": <树|null>}；词条命名空间叶子增 derivation
      （sub 为 {"current", "budget", "growth_max"}；roll 为 {"current_rolls", "budget"}）
    求值查上限表缺失（如 3 星）→ ProfileError 向上抛
    现有测试的 trace 形状断言同步更新
  Verify:   python -m pytest test/test_evaluate.py -q  →  全绿（含新增：增长达标继续、全部投入仍不足止损、
            待激活预览值起算、roll 可达、null 次数缺失、白名单外运算符在求值前已被 2.1 拒绝的边界）
  Done:     discussion.md「可达性推导公式节」的每个分支都有对应断言。

## 3. 观测侧

- [x] 3.1 解析核心：待激活入模与强化次数解析
  Goal:     待激活行产出 pending 词条；带圈数字映射为强化次数；误读形态走防御层。
  Read:     agent/observe.py:117-176 （read_list）
            agent/observe.py:178-253 （read_enhance）
            agent/observe.py:350-397 （_read_substats / _clean_substat_rows）
            agent/observe.py:399-432 （_strip_new_marker / _strip_roll_misread / _merge_settlement_row）
            agent/observe.py:462-481 （_substat_count_warning / _legal_substat_counts）
            docs/plans/2026-09-06-m25-pruning-roll-count/specs/observation/spec.md
  Touch:    agent/observe.py | test/test_observe_enhance.py | test/test_observe_list.py | test/test_observe_parse.py
  Contract:
    待激活行（行文本含「（待激活）」）：解析词条名与预览值 → StatValue(pending=True, roll_count=None)，
    不再整行丢弃；不计入已解锁条数、行数校验与一致性警告（_legal_substat_counts 只统计已解锁行）
    带圈字符 ①~⑤（U+2460~2464）出现在行内 → 该行词条 roll_count = 1~5；无标记 → 0；
    read_list 产出的副词条 roll_count 恒 None
    行首孤立短数字（现 _strip_roll_misread 形态）：剥离 + warning + 该行 roll_count = None（未知）
    「新」角标剥离不变；结算行取新值不变
    构造 Artifact 时词条携带 roll_count / pending（依赖 1.2 的模型扩展）
  Verify:   python -m pytest test/test_observe_enhance.py test/test_observe_list.py test/test_observe_parse.py -q  →  全绿
  Done:     E4 形态（四条 ①）、E6 形态（① + ③）、E7 形态（新词条 0 次）、待激活预览值入模，各有断言。

- [x] 3.2 双通道交叉与流水线节点
  Goal:     强化次数有两个独立识别通道，交叉核对后入模；转储扩展到新通道。
  Read:     assets/resource/pipeline/genshin/observation.json（15 节点参数结构）
            tools/record_ocr_dumps.py:38-68 （区域清单与 build_param）
            tools/record_ocr_dumps.py:94-148（主循环与异常记录）
            docs/adr/0007-dual-channel-roll-mark-recognition.md
            docs/plans/2026-09-06-m25-pruning-roll-count/design.md（D6）
  Touch:    assets/resource/pipeline/genshin/observation.json | tools/record_ocr_dumps.py | agent/observe.py |
            test/test_observe_enhance.py
  Contract:
    新节点 obs_enhance_roll_marks：TemplateMatch，roi = 标记列窄条（约 [770,195,50,150]，以模板命中实测微调），
    template = ["genshin/roll_mark/roll_mark_1.png", …]（素材齐几张贴几张：①③ 先行，②④⑤ 到位后补全），
    threshold 初值 0.8、以 E4/E6/fig2/fig4 实测调整
    录制脚本：强化页区域清单增 roll_marks 与 roll_marks_ocr；roll_marks_ocr 由脚本内裁剪标记列、
    放大 4 倍后跑 OCR 产出（预处理逻辑独立函数，供 M3 CustomRecognition 复刻）；27 张全量重录
    交叉（read_enhance 内）：模板通道命中框按纵向位置对齐词条行；两通道都有值且不一致 → failures；
    恰好一侧有值 → 取该侧 + warning；两侧都无 → 0（roll_marks 区域缺失本身不拦截，与 mora 同级非必要区域）
  Verify:   python tools/record_ocr_dumps.py 2>&1 | tail -5  →  27 份转储含新区域键；
            python -m pytest -q  →  全绿（含构造转储的交叉三态断言）
  Done:     E4/E6 的次数在两通道一致命中；人为构造的不一致样例被读取失败拦截。

## 4. 收口

- [ ] 4.1 端到端真值表扩展
  Goal:     27 张夹具的真值表覆盖 roll_count / pending；全量测试绿。
  Read:     test/test_observe_e2e.py:1-80（LIST_TRUTH / ENHANCE_TRUTH 结构与断言分支）
            test/fixtures/incoming/README.md（夹具验收记录与缺口清单）
            test/fixtures/ocr_dumps/E4_enhance_lv16_marks.json（roll 区域实际产出）
  Touch:    test/test_observe_e2e.py
  Contract:
    真值表扩列：L 系列全部词条 roll_count 为 None、L1 断言待激活行（pending=True, hp 269）；
    E 系列按转储实录断言（E4 四条 1 次、E6 ①=1 与 ③=3、fig2/fig4 的 ② 词条 2 次、E7 解锁词条 0、
    静态页无标记 0）；置信度断言维持既有线
    待激活行断言进入 e2e（L1 之外的待激活样本按转储实际覆盖）
  Verify:   python -m pytest -q  →  全量通过（基线 335 + 新增）
  Done:     真值表与转储逐行互证，无跳过（skip）项。

- [ ] 4.2 契约折叠、设计文档修订与收尾
  Goal:     契约正本切换到 M2.5 口径；主 spec 同步；缺口登记；全量复跑。
  Read:     docs/plans/2026-09-06-m25-pruning-roll-count/specs/（四份工作副本）
            docs/specs/game-profile.md | docs/specs/judgment.md | docs/specs/observation.md | docs/specs/rule-file-format.md
            docs/superpowers/specs/2026-08-28-auto-grade-up-design.md §3 §4 §6 §14
            test/fixtures/incoming/README.md
  Touch:    docs/specs/ 四正本 | 主 spec | test/fixtures/incoming/README.md |
            assets/resource/pipeline/genshin/observation.json（②④⑤ 素材到位时补全 template 数组并重录重验）
  Contract:
    四份工作副本全文覆盖对应正本（单一现行口径）
    主 spec：§3 数据模型示例加 roll_count/pending；§4 规则示例与字段表加 roll_rule、白名单、
    可达性语义描述（示例规则的语义描述同步改写）；§6 观测加双通道与待激活；§14 M2.5 行对照验收结果
    README 缺口清单：④⑤ 模板素材待补、4 星 2 词条初始形态待 M3 补样、CustomRecognition 放大通道真机接线属 M3
  Verify:   python -m pytest -q  →  全绿；grep -n "整行丢弃\|忽略\|备选" docs/specs/observation.md → 无旧口径残留
  Done:     正本、主 spec、README 三处口径一致；归档准备就绪（归档动作在汇报后按指示执行）。

## 素材依赖与等待项

- 模板图 ②④⑤ 由需求方按 discussion.md「模板素材规格」提供；3.2 以 ①③ 先行验证双通道，4.2 补全。
- 若收尾时素材未到位：按上述登记缺口收尾，双通道完整验证顺延，不阻塞 M2.5 其余验收。
