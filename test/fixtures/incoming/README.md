# 补拍截图投放说明

本目录是补拍截图的暂存区：处理前不入库（目录内容已 gitignore），处理链路
见 `tools/prepare_fixtures.py`（统一 1280×720、涂黑 UID）与
`tools/record_ocr_dumps.py`（录制识别结果转储）。

## 投放方式（需求方）

1. 截图要求与 proposal 补拍清单一致：**列表页**选中目标圣遗物、让右栏显示它
   之后截整屏；**强化页**停在强化标签页截整屏；1280×720 或更高（16:9 即可）。
2. 无需预先处理 UID（处理脚本统一涂黑）；游戏角色名视为公共内容，不遮挡。
3. 文件名延续现有主干惯例，读取器归属按前缀自动判定：
   列表页 `L<编号>_<说明>.png`（如 `L9_list_lock.png`）、
   强化页 `E<编号>_<说明>.png`（如 `E4_enhance_mid_lv.png`）。
4. 放入本目录后知会开发方即可。

## 扩测路径（开发方，接手后执行）

1. 把图从本目录移入 `reference/pic2/`（或按批次新建 `reference/picN/`；
   新建目录时在 `tools/prepare_fixtures.py` 的来源目录清单中加入，
   并按实际张数调整该脚本的张数断言）。
2. 重跑 `python tools/prepare_fixtures.py` → 新夹具入
   `test/fixtures/screenshots/`（自检尺寸与 UID 遮挡）。
3. 重跑 `python tools/record_ocr_dumps.py` → 全部转储重新生成（含新图，
   形状断言自动覆盖）；识别质量异常以脚本输出的异常清单为准。
4. 在 `test/test_observe_e2e.py` 真值表补一行（从截图抄录），跑
   `python -m pytest -q` 全量回归。

## 缺口清单（2026-08-29 盘点，与 log.md 同步）

| 编号 | 缺口形态 | 来源 |
| --- | --- | --- |
| G1 | 锁定样本单一：已锁定仅同一件 5 星死之羽（fig1~fig7），其余全部未锁定 | proposal 补拍清单未把锁定状态列为变量 |
| G2 | 4 星仅 +0 一档（L6、2 词条）；4 星中高等级与强化次数标记无样本 | proposal L6 画面要求只覆盖 +0 |
| G3 | 强化页中高等级无独立样本：除 fig2/fig4/fig5 同件 +19 外全部 +0 | proposal E1~E3 画面要求只覆盖低等级 |
| G4 | 主词条未覆盖族：暴击率、暴击伤害、元素精通、元素充能效率、治疗加成作主词条无样本 | proposal L3/L4/L7 只覆盖 hp/atk/def 百分比与元素伤害杯 |
| G5 | 副词条稀有族：物理伤害加成、元素伤害加成作副词条无样本 | proposal 补拍清单未要求 |
| G6 | 1~3 星低稀有度无样本 | proposal 补拍清单未要求 |
