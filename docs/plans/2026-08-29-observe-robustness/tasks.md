# M2 补强任务清单

> 2026-08-29 制定。上游约束：`proposal.md`（范围）、`design.md`（实现决策
> D1~D6）、`discussion.md`（三轮拷问结论）、`docs/specs/observation.md`
> （强化页的读取时机与行形态节——正本已在拷问轮更新，本变更落地后无折叠
> 差异）。执行模式（plan-contract）：当前会话执行，每个任务完成后停下汇报，
> 等指令再继续；汇报附 Verify 真实输出、变更文件、提交哈希与 log.md 新增
> 条目；一个任务 = 一个提交。契约与实际不符时先改上游工件并记 log，不在
> 代码里绕行。

---

## 1. 截图来源归整与夹具扩展

- [x] 1.1 四个批次目录合并为 reference/pic/，处理脚本扩到 27 张
  Goal:     所有测试与开发用图一个目录管理（需求方定案）；27 张夹具处理入库
  Read:     tools/prepare_fixtures.py:16-24  (来源目录常量与张数断言)
            tools/prepare_fixtures.py:27-32  (fixture_stem：图N 映射 figN、
            其余沿用主干——合并后逻辑不变)
            test/fixtures/incoming/README.md  (扩测路径节、验收记录节)
  Touch:    reference/pic/ | tools/prepare_fixtures.py | test/fixtures/screenshots/ | test/fixtures/incoming/README.md
  Contract:
    pic2/pic3/pic4 的 20 张全部移入 pic/（合并后 27 张：fig1~fig7、
          L1~L8、E1~E3、L9_list_locked_lv20、L10_list_4star_lv16、
          L11_list_crit_dmg_circlet、L12_list_em_sands、
          L13_list_healing_circlet、E4_enhance_lv16_marks、
          E5_enhance_lv8_preview、E6_enhance_lv20_max、
          E7_enhance_lv4_new_stat），删除空的 pic2/pic3/pic4；
          prepare_fixtures.py 只留 pic/ 一个来源常量、张数断言 18 → 27、
          docstring 与打印同步；重跑后 screenshots/ 共 27 张；
          README 中 pic2/pic3/pic4 引用全部改为 pic/、「25 张」口径
          修正为 27；后续批次直接放 pic/，不再开新目录
  Verify:   python tools/prepare_fixtures.py → 自检 27 张；ls reference/pic/*.png | wc -l → 27；
          ls test/fixtures/screenshots/*.png | wc -l → 27；
          ls reference/ → 无 pic2/pic3/pic4
  Done:     单一来源目录、27 张夹具入库、尺寸与 UID 遮挡自检通过、幂等复验一致

---

## 2. 解析核心强化页行清洗

- [x] 2.1 结算形态取新值与「新」角标剥离（仅强化页）
  Goal:     强化页三种新形态可解析；列表页行为不变（异常双数值仍失败）
  Read:     agent/observe.py:325-360  (_read_substats 与 _clean_substat_rows，
            两读取器共用的行清洗层)
            test/test_observe_enhance.py:140-202  (行规则测试类先例)
            test/test_observe_list.py  (列表页失败语义用例的组织方式)
  Touch:    agent/observe.py | test/test_observe_enhance.py | test/test_observe_list.py
  Contract:
    _read_substats 向行清洗层传递读取器模式（强化页/列表页）；强化页清洗：
          行内出现两个完整数值（旧值与新值）取最后一个，判断依据是数值
          个数、不依赖箭头符号；行首「新」角标剥离（与 _ROLL_MARKERS
          剥离同层）；列表页清洗行为与现状完全一致
    测试（强化页）：「防御力 5.8% 11.1%」→ def_percent 11.1；「①暴击率
          3.5% 6.6%」→ crit_rate 6.6（带圈标记先剥离）；「新 攻击力
          4.7%」→ atk_percent 4.7；箭头残留形态（两数值框 + 箭头杂字框
          同行聚组）→ 取新值；单值行回归不变
    测试（列表页）：双数值行 → 读取失败（failures 非空、artifact None）
  Verify:   python -m pytest test/test_observe_enhance.py test/test_observe_list.py -q → 全部通过
  Done:     E5/E6/E7 的行形态在转储单元测试层可解析；列表页失败语义有回归断言

---

## 3. 流水线调整与转储重录

- [ ] 3.1 MAX 纠错与带圈数字保留，27 份转储重录
  Goal:     满级等级可解析；转储保留强化次数标记（M2.5 输入）；27 份转储入库
  Read:     assets/resource/pipeline/genshin/observation.json  (obs_enhance_level
            与 obs_enhance_substats 的 replace 现状)
            tools/record_ocr_dumps.py:104-105  (张数断言)
            docs/plans/2026-08-29-observe-robustness/design.md  (D2、D5)
  Touch:    assets/resource/pipeline/genshin/observation.json | tools/record_ocr_dumps.py | test/fixtures/ocr_dumps/
  Contract:
    obs_enhance_level.replace 追加 ["MAX", ""]（列表页等级节点不动——
          L9 实证列表页无 MAX）；obs_enhance_substats.replace 删除 ①~⑤
          五条、保留 "^0(?=[^0-9.])"（行首 ① 误读 0 的纠错）；录制脚本
          张数断言 18 → 27；重跑生成 27 份转储，E4/E6 的 substats 文本
          可含带圈数字（①③），E6 的 mora 与 fodder_tier 为空（进异常
          清单，预期内并注明）
  Verify:   python tools/record_ocr_dumps.py → 27 份生成且形状断言通过；
          git diff test/fixtures/ocr_dumps 核对变化仅在预期范围
  Done:     27 份真实转储入库；带圈数字进转储；异常清单仅 E6 两项（满级形态）

---

## 4. 九张真值表补行与全量回归

- [ ] 4.1 L9~L13、E4~E7 端到端断言
  Goal:     27 张夹具离线全链路全绿
  Read:     test/test_observe_e2e.py  (LIST_TRUTH 与 ENHANCE_TRUTH 结构、
            recognize fixture、fig5 放宽断言先例)
            test/fixtures/incoming/README.md  (九张验收记录——真值来源)
            docs/plans/2026-08-29-observe-robustness/design.md  (D6 占位约定)
  Touch:    test/test_observe_e2e.py
  Contract:
    LIST_TRUTH 补 5 行（L9~L13，真值从 README 验收记录核对：含 +20 满级、
          4 星 +16 千位逗号 3,571、暴伤/精通/治疗主词条、L13 待激活行）；
          ENHANCE_TRUTH 补 4 行——E4（5 星 +16，暴伤 51.6 主词条，四条
          带 ① 的副词条，exp 280/23500）；E5（4 星 +8，防御 5.8/11.1
          双数值取 11.1，exp 1700/7375）；E6（5 星 +20，充能 51.8，
          ①暴击率 3.5/6.6 取 6.6、③生命 18.1，extras 仅 fingerprint——
          exp/mora/fodder_tier 全缺）；E7（5 星 +4，岩伤 14.9 主词条，
          「新」攻击力 4.7 剥离后 atk_percent，exp 1200/5900）；
          E4/E7 的沿用字段套装传占位字符串并注明未采样（D6），星级
          E7=5（三初始词条 + +4 解锁第 4 条）、E5=4
  Verify:   python -m pytest test/test_observe_e2e.py -q → 27 用例通过；
          python -m pytest -q → 全量通过
  Done:     27 张端到端断言通过；全量测试绿

---

## 5. 收尾

- [ ] 5.1 文档口径收口与归档
  Goal:     README 现行口径与实际一致；变更文件夹归档
  Read:     test/fixtures/incoming/README.md  (缺口清单状态、待补拍节)
            docs/plans/2026-08-29-observe-robustness/tasks.md
  Touch:    test/fixtures/incoming/README.md | docs/plans/2026-08-29-observe-robustness/tasks.md
  Contract:
    README 缺口清单状态更新（G1~G4 已入测）、待补拍 E6 行关闭；tasks.md
          全部勾选；spec 无折叠差异（正本拷问轮已更新，核对一次）；变更
          文件夹移入 docs/plans/archive/（log.md 随文件夹保留）
  Verify:   python -m pytest -q → 全部通过；ls docs/plans/archive/2026-08-29-observe-robustness → 目录在位
  Done:     补强闭环；M2.5 立项的输入（discussion.md、design.md）随档保留
