# 观测解析（observation）契约

- 消费者：执行机构（M3，ReadArtifact 接线层）、运行报告（M4，ReadResult 序列化）
- 落地后正本将折叠至 `docs/specs/observation.md`
- 上游约束：`concept.md`（职责分界）、主 spec §6（识别区域）、ADR-0004 / ADR-0005
- 本契约被后续版本静默破坏即视为回归

## 解析核心接口

- 模块 `agent/observe.py`；**禁止导入 maa**（冒烟测试守卫，理由见 `concept.md` §3.1）
- 输入三样：识别结果集、`GameProfile`（M1 产物）、`Textmap`（字段对照文档加载产物）
- 识别结果集：`dict[区域键 → list[文字框]]`；文字框形如
  `{"box": [x, y, w, h], "text": str, "score": float}`（score 0.0~1.0）；
  模板匹配区域（stars/lock）无文字，text 为空串
- `read_list(recognition, profile, textmap) -> ReadResult`：列表页读取器
- `read_enhance(recognition, carried, profile, textmap) -> ReadResult`：强化页读取器；
  `CarriedFields(rarity: int, set: str, locked: bool)` 由控制层从列表初扫传递（ADR-0005）

### 区域键

| 列表页读取器 | 内容 |
| --- | --- |
| `name` | 圣遗物名 |
| `slot` | 部位名 |
| `main` | 主词条行（名+值） |
| `level` | 等级（如 +19） |
| `substats` | 副词条 0~4 行 |
| `set` | 套装名（绿色文字行） |
| `stars` | 星级图标（TemplateMatch） |
| `lock` | 锁定图标（TemplateMatch） |

| 强化页读取器 | 内容 |
| --- | --- |
| `breadcrumb` | 面包屑「部位 / 圣遗物名」 |
| `main` | 主词条行 |
| `level` | 等级 |
| `exp` | 等级内经验进度（如 2900/35575） |
| `substats` | 副词条 0~4 行（强化次数标记被忽略） |
| `mora` | 本次强化摩拉 |
| `fodder_tier` | 素材档位文字（如 4星及以下素材） |

## ReadResult

| 字段 | 语义 |
| --- | --- |
| `ok` | 布尔；failures 非空即 False |
| `artifact` | 圣遗物属性（spec §3 模型）；ok 时必有，否则 None |
| `extras` | 附属读数：强化页含 `exp`、`mora`、`fodder_tier`、`fingerprint`（`{"slot": …, "name": …}`）；列表页可为空 dict |
| `confidences` | 逐字段置信度，取该字段所用文字框分数的最小值 |
| `failures` | 读取失败清单，逐条人类可读 |
| `warnings` | 警告清单（只进报告，不拦截） |

- 无状态：同输入两次调用结果相同；不修改输入
- 解析前置条件：`validate(规则)` 之外的档案已加载；本契约不依赖规则文件

## 字段组装规则

- 列表页：星级 = stars 区域命中数（1~5）；锁定 = lock 区域有命中；其余字段取 OCR
- 强化页：面包屑按「/」切分为部位名与圣遗物名（部位参与组装，两者进 `extras.fingerprint`）；
  等级、主词条、副词条现场读取；rarity / set / locked 取自 CarriedFields
- 词条行解析：行文本切分为（词条名文本，数值文本）——两界面格式分别为「名+值」连写
  （如「暴击率+3.1%」）与「名 值」同行（如「暴击率 3.1%」）；数值经 M1 解析函数
  （先去空白、字符白名单）；词条名经对照文档映射到文字族，双代号族（hp/atk/def）
  按 % 后缀落 `_percent` 代号，单代号族原样
- 强化次数标记（①②③）不参与解析（契约：忽略）

## 未知与缺失语义

- 词条名未收录对照文档 → 名称按 OCR 原文存入 + warning（安全方向：无代号可匹配，判定天然不通过）
- 部位名未收录 → 读取失败
- 必要区域缺失或全部文字框为空 → 读取失败
  （列表页必要：name/slot/main/level/substats/set/stars；强化页必要：breadcrumb/main/level/substats）
- 副词条行数 > `profile.substat_max` → 读取失败
- 副词条代号重复 → 读取失败（2026-08-29 定案）
- 数值解析失败（含全角数字/全角百分号）→ 读取失败（2026-08-29 定案）
- 警告（不拦截）：副词条行数与等级一致性（如 +19 只见 3 行）
- 读取失败时 artifact 为 None；extras/confidences 尽量填充已成功字段

## 识别结果转储（测试夹具格式）

- JSON：`{"<区域键>": [{"box": [x, y, w, h], "text": "…", "score": 0.99}, …]}`
- 来源两类：真实转储（录制脚本对截图夹具跑框架识别产出）+ 构造转储（异常样例手工编写）

## 流水线节点约定

- 节点位于资源包 `pipeline/`；命名 `obs_<reader>_<region>`；OCR 节点 `only_rec` + 精确 roi；
  星级、锁定为 TemplateMatch；节点不含 action 与 next
- 节点名到区域键的映射属于录制脚本与 M3 接线层，不属于解析核心契约
