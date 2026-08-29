# M1：决策机构（rule_lambda）落地

- 日期：2026-08-29
- 来源：`docs/superpowers/specs/2026-08-28-auto-grade-up-design.md` §14 里程碑 M1
- 状态：计划已制定，待批准执行；2026-08-29 修订——纳入多游戏架构（ADR-0004）：新增游戏档案任务与契约，校验与求值改为档案驱动，公式参数化文档已落地

## 为什么做

M1 是全部后续里程碑的地基：数据模型被 M2 观测机构消费，规则文件格式被 M5 编辑器消费，求值语义被 M3/M4 消费。它是当前唯一无阻塞的里程碑——不需要游戏窗口、不需要 MaaFramework，pytest 即可完整验收。

## 范围

**做**：

- `agent/rule_lambda/` 纯 Python 包：数据模型（model）、游戏档案加载与校验（profile）、规则文件校验（schema）、条件树求值（evaluate）。
- 原神游戏档案数据文件 `assets/resource/genshin/profile.json`。
- JSON Schema 导出命令（按游戏档案参数化，供 M5 编辑器构建消费）。
- pytest 单元测试与验收样本集；示例规则 `docs/examples/rules.example.json`。
- 文档修订（已完成）：剩余强化次数公式参数化并向上取整，2026-08-29 随多游戏定案写入 spec §4 与 CONTEXT。

**不做**：

- 字段对照文档数据（zh_cn.json，M2）；观测/执行/报告机构（M2–M4）；编辑器（M5）。
- agent 运行时接线（`agent/main.py` 不动，M3 再接；`PI_RESOURCE` 环境变量解析属 M3，档案接口按「传入路径」设计）。
- 星穹铁道、绝区零的档案与交付（架构预留，ADR-0004）。

## 影响

全部为新增文件（`agent/rule_lambda/`、`test/`、`docs/examples/`、`requirements-dev.txt`、`pytest.ini`），仅两处文档修订，不改任何现有代码。

## 验收（与 spec §14 M1 一致）

1. pytest 全部通过。
2. 示例规则与非法样例经通用 JSON Schema 校验器验证生成物：合法通过、非法被拒。
3. 导出命令产出合法生成物。
