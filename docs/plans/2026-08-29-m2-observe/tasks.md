# M2 任务清单

> 2026-08-29 制定。上游约束：`concept.md`（职责分界）、`proposal.md`（范围与补拍清单）、`specs/observation/spec.md`（行为契约）。执行模式（plan-contract）：当前会话内执行，**每个任务完成后停下汇报，等指令再继续**。汇报附 Verify 命令真实输出、变更文件、提交哈希与 `log.md` 新增条目；一个任务 = 一个提交（中文 conventional commits）。契约与实际不符时：先改上游工件，记录 `log.md`，停下汇报，不在代码里绕行。

---

## 1. 骨架与依赖

- [x] 1.1 maa 开发依赖与解析核心骨架
  Goal:     maa 绑定就绪（钉版本、版本对齐核对），observe/textmap 骨架可导入，maa 隔离有测试兜底
  Read:     docs/plans/2026-08-29-m2-observe/concept.md:24-46  (§3.1 禁止导入 maa 的理由)
            docs/plans/2026-08-29-m2-observe/design.md:5-14  (D1)
            agent/__init__.py  (M1 空文件先例)
  Touch:    requirements-dev.txt | agent/observe.py | agent/textmap.py | test/test_observe_smoke.py
  Contract:
    requirements-dev.txt: 追加 maa（钉具体版本；先核对 MFAAvalonia 当前发布打包的框架版本，
          结论记 log.md）；追加 Pillow（钉主版本，任务 4.1 用）
    agent/observe.py、agent/textmap.py: 仅 docstring，无实现
    test/test_observe_smoke.py: 导入 agent.observe 与 agent.textmap 后断言 "maa" 不在 sys.modules
  Verify:   python -m pip install -r requirements-dev.txt && python -m pytest -q → 全部通过（含新冒烟）
  Done:     冒烟通过；骨架与 concept §8 目录一致；maa 版本对齐结论在 log.md

---

## 2. 字段对照文档

- [x] 2.1 对照文档数据文件与加载校验器
  Goal:     游戏文字到代号的映射可加载即用；每类非法文档逐类被拒
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:177-212  (§4 字段对照文档段与格式示例)
            docs/plans/2026-08-29-m2-observe/specs/observation/spec.md  (组装规则节)
            agent/rule_lambda/profile.py  (GameProfile；映射目标合法性来源)
  Touch:    assets/resource/genshin/textmap/zh_cn.json | agent/textmap.py | test/test_textmap.py
  Contract:
    数据文件: version=1、language="zh_cn"、stats 16 条（暴击率/暴击伤害/生命值/攻击力/防御力/
          元素精通/元素充能效率/治疗加成/物理伤害加成/七种元素伤害加成）、slots 5 条
          （生之花/死之羽/时之沙/空之杯/理之冠）；映射值与 spec §4 示例一致（stats→文字族代号，
          slots→部位代号）
    @dataclass Textmap: language: str、stats: dict[str, str]、slots: dict[str, str]
    load_textmap(path, profile) -> Textmap: 文件缺失 / JSON 损坏 / 结构不符（键集合固定：
          version/language/stats/slots，缺一多一均非法）/ version ≠ 1 / 清单为空或元素非字符串 /
          映射值不在 profile.stats（stats 节）或 profile.slots（slots 节）→ 抛 TextmapError
          （message + 文件路径）
  Verify:   python -m pytest test/test_textmap.py -q → 全部通过（含真文件加载断言）
  Done:     真文件加载即用；每类非法样例逐类有测试

---

## 3. 解析核心

- [x] 3.1 词条行切分与代号适配
  Goal:     两界面行格式统一解析为（词条名文本，数值文本），并映射到属性代号；未收录走警告路径
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:106-113  (§3 解析约定：去空白、% 后缀)
            docs/plans/2026-08-29-m2-observe/specs/observation/spec.md  (字段组装规则、未知与缺失语义)
            agent/rule_lambda/model.py  (strip_spaces / parse_stat_value——复用，不复制)
  Touch:    agent/observe.py | test/test_observe_parse.py
  Contract:
    split_stat_text(text) -> tuple[str, str]: 「暴击率+3.1%」→("暴击率","+3.1%")、
          「暴击率 3.1%」→("暴击率","3.1%")、行内无有效数值 → ValueError；
          全角字符随白名单在数值解析阶段拒绝，切分不吞错
    adapt_stat(name_text: str, value_text: str, textmap: Textmap) -> tuple[str, bool]:
          名称查对照族；hp/atk/def 三族按 % 后缀落 hp_percent/atk_percent/def_percent，
          其余族原样；数值解析复用 model.parse_stat_value；返回 (属性代号, 是否已收录)；
          未收录 → (OCR 原文, False)
    M1 模块契约修订随本任务落地：数值白名单接受千位分隔符逗号、解析前去逗号
          （model.py + test_model.py 补「3,967」→ 3967.0 用例；先改本契约与 M1 测试再动代码）
  Verify:   python -m pytest test/test_observe_parse.py -q → 全部通过
  Done:     连写与同行两种格式、双代号族/单代号族、未收录名称、全角拒绝均有测试

- [x] 3.2 列表页读取器
  Goal:     列表页识别结果集 → 完整 ReadResult；硬失败与警告按契约分界
  Read:     docs/plans/2026-08-29-m2-observe/specs/observation/spec.md  (契约全文)
            docs/plans/2026-08-29-m2-observe/concept.md:48-72  (§3.1 ReadResult 字段表)
            agent/rule_lambda/model.py  (Artifact.from_dict 复用组装校验)
  Touch:    agent/observe.py | test/test_observe_list.py
  Contract:
    @dataclass ReadResult: ok: bool、artifact: Artifact | None、extras: dict、
          confidences: dict[str, float]、failures: list[str]、warnings: list[str]
    read_list(recognition, profile, textmap) -> ReadResult
    区域键 name/slot/main/level/substats/set/stars/lock；星级 = len(stars 命中)、锁定 = lock 有命中；
    confidences 逐字段取所用文字框 score 最小值；「待激活」行整行丢弃
    硬失败（failures，artifact=None）: 必要区域缺失或全空 / 数值或等级解析异常 / 副词条行数 >
          substat_max / 副词条适配后代号重复（同族固定值与百分比并存合法）/ 部位名未收录
    警告（warnings）: 词条名未收录（原文入模）/ 行数与等级、稀有度的一致性
          （4 星 +0 为 2 条、5 星 +0 为 3~4 条合法）
    无状态：同输入两次调用结果相同
  Verify:   python -m pytest test/test_observe_list.py -q → 全部通过（内联构造转储样例）
  Done:     合法样例字段全对；每类硬失败与警告样例有断言；无状态有断言

- [x] 3.3 强化页读取器
  Goal:     强化页识别结果集 + 沿用字段 → 完整 ReadResult；面包屑指纹入 extras
  Read:     docs/adr/0005-single-boolean-scene-agnostic.md  (字段分工)
            docs/plans/2026-08-29-m2-observe/specs/observation/spec.md  (区域键、CarriedFields)
  Touch:    agent/observe.py | test/test_observe_enhance.py
  Contract:
    @dataclass CarriedFields: rarity: int、set: str、locked: bool
    read_enhance(recognition, carried, profile, textmap) -> ReadResult
    区域键 breadcrumb/main/level/exp/substats/mora/fodder_tier；面包屑按「/」切分
    （左部位、右圣遗物名），部位参与组装、两者入 extras.fingerprint；
    extras 另含 exp（如 "2900/35575" 原样）、mora、fodder_tier；artifact 含 carried 三字段；
    「待激活」行整行丢弃（与列表页同规则）
  Verify:   python -m pytest test/test_observe_enhance.py -q → 全部通过
  Done:     carried 并入、面包屑切分、fingerprint extras、每类硬失败样例均有断言

---

## 4. 夹具与流水线节点

- [x] 4.1 截图夹具处理与入库
  Goal:     7 张现有截图统一为 1280×720、涂黑 UID 后入库；补拍清单待收
  Read:     docs/plans/2026-08-29-m2-observe/proposal.md  (补拍清单表)
            docs/plans/2026-08-29-m2-observe/design.md:60-66  (D7)
  Touch:    tools/prepare_fixtures.py | test/fixtures/screenshots/（7 张） | test/fixtures/incoming/.gitkeep
  Contract:
    prepare_fixtures.py: 读 reference/pic/（7 张）与 reference/pic2/（11 张补拍，2026-08-29 已到位）
          → 缩放到 1280×720 → 涂黑右下角 UID 区域 → 写 test/fixtures/screenshots/
          （fig1…fig7 + L1…L8 + E1…E3，共 18 张，命名沿用来源文件名主干）；不改动 reference/；
          incoming/ 为后续补拍暂存目录（gitignore 其内容，保留目录）
    遮挡范围: 仅 UID（游戏角色名视为公共内容不遮挡，2026-08-29 定案）
  Verify:   python tools/prepare_fixtures.py 后：ls test/fixtures/screenshots → 18 个文件；
          python -c 尺寸断言 1280×720
  Done:     18 张入库、人工抽查无 UID；处理可重复执行（幂等）

- [x] 4.2 流水线观测节点定义（坐标标定）
  Goal:     两界面全部识别区域落成流水线 JSON，坐标从 720 夹具标定
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:231-272  (§6 两张区域表)
            docs/plans/2026-08-29-m2-observe/specs/observation/spec.md  (流水线节点约定节)
            external/maaframework-docs/docs/zh_cn/3.1-任务流水线协议.md:614-656  (OCR 节字段)
  Touch:    assets/resource/pipeline/genshin/observation.json
  Contract:
    节点命名 obs_<reader>_<region>（8 + 7 个，与区域键一一对应）；OCR 节点 only_rec=true +
    精确 roi + threshold（默认 0.3 起）；stars/lock 为 TemplateMatch（template 图路径占位，
    模板图随本任务从夹具裁剪入 assets/resource/image/genshin/）；节点不含 action 与 next；
    坐标一律 720 基准（1280×720）
  Verify:   python -c "import json; d=json.load(open('assets/resource/pipeline/genshin/observation.json', encoding='utf-8')); assert len(d)==15"
          并人工核对节点名清单与区域键一致
  Done:     15 节点齐备；roi 由夹具截图取点（VSCode 插件或读图量取）；模板图入库

- [x] 4.3 转储录制脚本与真实转储入库
  Goal:     录制脚本走框架识别产出真实转储，形状与解析核心输入契约一致
  Read:     docs/plans/2026-08-29-m2-observe/specs/observation/spec.md  (识别结果转储节)
            docs/plans/2026-08-29-m2-observe/design.md:68-72  (D8)
            external 研究结论（post_recognition(reco_type, reco_param, image)；Tasker 需绑定 Resource）
  Touch:    tools/record_ocr_dumps.py | test/fixtures/ocr_dumps/（18 份 JSON）
  Contract:
    脚本: Resource 加载 assets/resource → Tasker → 对每张夹具逐节点 post_recognition（OCR 与
          TemplateMatch 参数取 observation.json）→ 节点名映射区域键 → 写
          test/fixtures/ocr_dumps/fig<N>.json（{"区域键": [文字框...]}）；脚本内断言转储形状
          （键集合、文字框三键）；打印 maa 版本
  Verify:   python tools/record_ocr_dumps.py → 18 份转储生成且形状断言通过；ls test/fixtures/ocr_dumps → 18 个文件
  Done:     真实转储入库；maa 版本打印并记 log.md；识别质量异常（空区域/低分）如实记录

---

## 5. 全链路验收

- [x] 5.1 离线全链路测试
  Goal:     截图 → 框架识别 → 解析核心 → 断言，端到端通过
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:440  (spec §14 M2 验收)
            docs/plans/2026-08-29-m2-observe/concept.md:100-110  (§6 两层测试)
  Touch:    test/test_observe_e2e.py
  Contract:
    每张夹具：读 PNG（numpy 数组）→ 与 4.3 相同路径跑识别 → read_list / read_enhance →
    断言字段值（真值表写在测试内，18 张逐一从截图抄录：等级、星级、部位、主词条、副词条、
    套装、锁定、extras）；fig4/fig5（弹窗遮挡）按可见范围放宽断言并在测试内注明；maa 仅经
    requirements-dev 引入
  Verify:   python -m pytest test/test_observe_e2e.py -q → 全部通过
  Done:     18 张端到端断言通过；识别质量不达标处记录（replace 调优或该区域退回检测模式）

- [ ] 5.2 断言充实与覆盖缺口标注
  Goal:     现有夹具断言全绿、覆盖范围如实成文；补拍未到的形态记缺口
  Read:     docs/plans/2026-08-29-m2-observe/proposal.md  (补拍清单)
            docs/plans/2026-08-29-m2-observe/log.md  (既有记录)
  Touch:    test/test_observe_e2e.py | test/fixtures/incoming/README.md
  Contract:
    incoming/README.md 写明补拍投放方式（新图放 reference/pic2/ 或新建 picN 目录，重跑
    prepare_fixtures 与录制脚本即可扩测）与缺口清单；缺口清单（强化页中高等级等，如有）
    写入 log.md 并逐条对应来源
  Verify:   python -m pytest -q → 全部通过；ls test/fixtures/incoming/README.md
  Done:     全量测试绿；缺口与补拍编号一一对应、可跟踪

---

## 6. 收尾

- [ ] 6.1 M2 验收对照与契约折叠
  Goal:     M2 验收标准逐条对照达成；行为契约折叠为正本
  Read:     docs/superpowers/specs/2026-08-28-auto-grade-up-design.md:440  (spec §14 M2)
            docs/specs/  (正本惯例)
  Touch:    docs/specs/observation.md | tasks.md 勾选
  Contract:
    重跑每个任务的 Verify；specs/observation/spec.md 折叠为 docs/specs/observation.md
    （删去「落地后折叠」自指行）；对照 M2 验收两条（截图样本回放、字段解析断言全部通过）
    逐条给证据；缺口如实呈现
  Verify:   python -m pytest -q → 全部通过；ls docs/specs/observation.md
  Done:     验收达成或缺口明示；变更文件夹按惯例归档（log.md 永不删除）

---

## 完成动作

全部勾选后：重跑每个任务的 Verify；`specs/observation/spec.md` 折叠进 `docs/specs/` 正本；变更文件夹移入 `docs/plans/archive/`；停下汇报，由需求方决定落地方式。补拍截图到位后的断言充实（不等 M2 收尾也可随时插入：放 incoming → 重跑 4.1/4.3 → 扩 5.1 断言）。
