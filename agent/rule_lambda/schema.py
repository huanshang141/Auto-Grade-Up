"""规则文件的权威校验。

规则文件是编辑器与决策机构之间的唯一契约，完整形状见设计文档 §4 与
specs/rule-file-format/spec.md。本模块的手写校验是权威实现：非法规则逐类
被拒并定位到节点（node_path，形如 rule.all[0].any[1]），合法规则零误拒；
JSON Schema 导出（见本模块 export_json_schema，任务 5.1）是与编辑器共用的
同源副本，两端等价性由同一批样本双端断言兜底（任务 6.1）。

属性代号与部位代号不固化于代码：校验时从传入的游戏档案读取（ADR-0004）。
整数字段（version、candidates.rarity 元素、candidates.max_level）的「整数」语义
与 JSON Schema 2020-12 对齐——数值部分为整数即整数（1.0 视同 1），布尔不算
——保证手写校验与生成物双端等价无例外（design.md D4，2026-08-29 评审定案）。
"""

from __future__ import annotations

from agent.rule_lambda.profile import GameProfile

# 运算符集合是格式的一部分，固化于代码；「包含」（contains）为预留位，v1 不接受
NUMERIC_OPS: frozenset[str] = frozenset({">", "<", ">=", "<=", "==", "!="})
STRING_OPS: frozenset[str] = frozenset({"==", "!="})
EXISTS: str = "exists"

# 恒存在的标量字段（命名空间表，见 rule-file-format 契约）
_NUMERIC_SCALAR_FIELDS = frozenset({"level", "rarity", "substat_count", "remaining_rolls"})
_STRING_FIELDS = frozenset({"slot", "set"})
_NAMESPACES = ("main", "sub")

_TOP_LEVEL_KEYS = {"version", "game", "name", "candidates", "rule", "fodder"}
_CANDIDATES_KEYS = {"rarity", "slots", "max_level", "respect_lock"}
_FODDER_KEYS = {"strategy", "respect_lock"}


class RuleValidationError(Exception):
    """规则文件非法。node_path 定位出错节点供编辑器跳转，形如 rule.all[0].any[1]。

    顶层错误（如键集合不符）无节点可定位，node_path 为空字符串。
    """

    def __init__(self, message: str, node_path: str = ""):
        self.message = message
        self.node_path = node_path
        super().__init__(f"{message}（位置：{node_path}）" if node_path else message)


def _is_rule_integer(value) -> bool:
    """「整数」语义与 JSON Schema 2020-12 对齐：数值部分为整数即整数，布尔不算。

    JSON 只有一种数字类型，1.0 与 1 是同一个数；生成物侧 {"const": 1} 与
    {"type": "integer"} 均接受 1.0，Python 侧必须同样接受，否则浮点整数样本
    两端结论相反（2026-08-29 评审发现的分歧点）。
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and value.is_integer()


def validate(rules: dict, profile: GameProfile) -> None:
    """校验规则文件；合法返回 None，非法抛 RuleValidationError。"""
    if not isinstance(rules, dict):
        raise RuleValidationError(f"规则文件必须是 JSON 对象，实际为 {type(rules).__name__}")

    keys = set(rules)
    missing = _TOP_LEVEL_KEYS - keys
    extra = keys - _TOP_LEVEL_KEYS
    if missing:
        raise RuleValidationError(f"规则文件缺少键：{sorted(missing)}")
    if extra:
        raise RuleValidationError(f"规则文件含未知键：{sorted(extra)}")

    version = rules["version"]
    if not _is_rule_integer(version):
        raise RuleValidationError(f"version 必须是整数，实际为 {version!r}", "version")
    if version != 1:
        raise RuleValidationError(f"version 仅接受 1，实际为 {version}", "version")

    game = rules["game"]
    if not isinstance(game, str) or game != profile.game:
        raise RuleValidationError(
            f"game 须与游戏档案一致：规则为 {game!r}，档案为 {profile.game!r}", "game"
        )

    name = rules["name"]
    if not isinstance(name, str) or not name:
        raise RuleValidationError(f"name 必须是非空字符串，实际为 {name!r}", "name")

    _validate_candidates(rules["candidates"], profile)
    _validate_fodder(rules["fodder"], profile)
    _validate_node(rules["rule"], "rule", profile)


def _validate_candidates(candidates, profile: GameProfile) -> None:
    if not isinstance(candidates, dict):
        raise RuleValidationError(
            f"candidates 必须是对象，实际为 {type(candidates).__name__}", "candidates"
        )
    keys = set(candidates)
    missing = _CANDIDATES_KEYS - keys
    extra = keys - _CANDIDATES_KEYS
    if missing:
        raise RuleValidationError(f"candidates 缺少键：{sorted(missing)}", "candidates")
    if extra:
        raise RuleValidationError(f"candidates 含未知键：{sorted(extra)}", "candidates")

    rarity = candidates["rarity"]
    if not isinstance(rarity, list):
        raise RuleValidationError(
            f"candidates.rarity 必须是数组（空数组表示不限），实际为 {type(rarity).__name__}",
            "candidates.rarity",
        )
    for i, element in enumerate(rarity):
        if not _is_rule_integer(element):
            raise RuleValidationError(
                f"candidates.rarity 的元素必须是整数，实际为 {element!r}",
                f"candidates.rarity[{i}]",
            )
        if not profile.rarity_min <= element <= profile.rarity_max:
            raise RuleValidationError(
                f"candidates.rarity 的元素超出档案星级范围：{element}"
                f"（档案 {profile.game} 范围 [{profile.rarity_min}, {profile.rarity_max}]）",
                f"candidates.rarity[{i}]",
            )

    slots = candidates["slots"]
    if not isinstance(slots, list):
        raise RuleValidationError(
            f"candidates.slots 必须是数组（空数组表示不限），实际为 {type(slots).__name__}",
            "candidates.slots",
        )
    for i, element in enumerate(slots):
        if element not in profile.slots:
            raise RuleValidationError(
                f"candidates.slots 的元素不在档案部位清单内：{element!r}"
                f"（档案 {profile.game} 部位：{sorted(profile.slots)}）",
                f"candidates.slots[{i}]",
            )

    max_level = candidates["max_level"]
    # 不与档案上限比对：超出档案上限无意义但无害（契约原文）
    if not _is_rule_integer(max_level):
        raise RuleValidationError(
            f"candidates.max_level 必须是整数，实际为 {max_level!r}", "candidates.max_level"
        )

    if not isinstance(candidates["respect_lock"], bool):
        raise RuleValidationError(
            f"candidates.respect_lock 必须是布尔值，实际为 {candidates['respect_lock']!r}",
            "candidates.respect_lock",
        )


def _validate_fodder(fodder, profile: GameProfile) -> None:
    if not isinstance(fodder, dict):
        raise RuleValidationError(
            f"fodder 必须是对象，实际为 {type(fodder).__name__}", "fodder"
        )
    keys = set(fodder)
    missing = _FODDER_KEYS - keys
    extra = keys - _FODDER_KEYS
    if missing:
        raise RuleValidationError(f"fodder 缺少键：{sorted(missing)}", "fodder")
    if extra:
        raise RuleValidationError(f"fodder 含未知键：{sorted(extra)}", "fodder")

    strategy = fodder["strategy"]
    if not isinstance(strategy, str) or strategy != profile.round_mechanism:
        raise RuleValidationError(
            f"fodder.strategy 须与档案回合机制一致：规则为 {strategy!r}，"
            f"档案 {profile.game} 声明 {profile.round_mechanism!r}",
            "fodder.strategy",
        )

    if not isinstance(fodder["respect_lock"], bool):
        raise RuleValidationError(
            f"fodder.respect_lock 必须是布尔值，实际为 {fodder['respect_lock']!r}",
            "fodder.respect_lock",
        )


def _validate_node(node, path: str, profile: GameProfile) -> None:
    """递归校验条件树节点；path 为该节点的定位路径（如 rule.all[0].any[1]）。"""
    if not isinstance(node, dict):
        raise RuleValidationError(
            f"条件树节点必须是对象，实际为 {type(node).__name__}", path
        )
    keys = set(node)
    if "all" in keys or "any" in keys:
        if len(keys) != 1:
            raise RuleValidationError(
                f"组节点只能含 all 或 any 之一，不得与叶子键混用，实际键：{sorted(keys)}", path
            )
        kind = "all" if "all" in keys else "any"
        children = node[kind]
        if not isinstance(children, list):
            raise RuleValidationError(
                f"组节点 {kind} 的值必须是数组，实际为 {type(children).__name__}", path
            )
        for i, child in enumerate(children):
            _validate_node(child, f"{path}.{kind}[{i}]", profile)
        return
    _validate_leaf(node, path, profile)


def _validate_leaf(node: dict, path: str, profile: GameProfile) -> None:
    keys = set(node)
    unknown = keys - {"field", "op", "value"}
    if unknown:
        raise RuleValidationError(f"叶子节点含未知键：{sorted(unknown)}", path)
    if "field" not in keys or "op" not in keys:
        raise RuleValidationError("叶子节点必须有 field 与 op", path)

    field = node["field"]
    if not isinstance(field, str):
        raise RuleValidationError(f"field 必须是字符串，实际为 {field!r}", path)
    kind = _field_kind(field, profile, path)

    op = node["op"]
    if not isinstance(op, str):
        raise RuleValidationError(f"op 必须是字符串，实际为 {op!r}", path)
    allowed = (STRING_OPS if kind == "string" else NUMERIC_OPS) | {EXISTS}
    if op not in allowed:
        raise RuleValidationError(
            f"{kind} 字段 {field} 不接受运算符 {op!r}（可接受：{sorted(allowed)}）", path
        )

    if op == EXISTS:
        if "value" in keys:
            raise RuleValidationError("exists 一律不带 value", path)
        return

    if "value" not in keys:
        raise RuleValidationError(f"op 为 {op!r} 的叶子节点必须有 value", path)
    value = node["value"]
    if kind == "string":
        if not isinstance(value, str):
            raise RuleValidationError(
                f"字符串字段 {field} 的 value 必须是字符串，实际为 {value!r}", path
            )
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuleValidationError(
                f"数值字段 {field} 的 value 必须是数字，实际为 {value!r}", path
            )


def _field_kind(field: str, profile: GameProfile, path: str) -> str:
    """字段名 → 值类型（"number" / "string"）；未知字段名抛 RuleValidationError。

    命名空间表：标量字段恒存在；main.<代号>/sub.<代号> 的代号取自游戏档案。
    """
    if field in _STRING_FIELDS:
        return "string"
    if field in _NUMERIC_SCALAR_FIELDS:
        return "number"
    for namespace in _NAMESPACES:
        prefix = namespace + "."
        if field.startswith(prefix):
            code = field[len(prefix):]
            if code in profile.stats:
                return "number"
            raise RuleValidationError(
                f"字段 {field!r} 的属性代号不在档案 {profile.game} 的清单内", path
            )
    raise RuleValidationError(f"未知字段名：{field!r}", path)


def export_json_schema(profile: GameProfile) -> dict:
    """按游戏档案导出规则文件的 JSON Schema（Draft 2020-12），供 M5 编辑器消费。

    与手写 validate() 同源：结构（顶层键集合固定）、game 比对、档案代号枚举与
    candidates 的 slots/rarity 值域、fodder.strategy 枚举（与档案回合机制同源）、
    运算符与字段类型兼容（if/then）、exists 无 value 的形状、值类型随字段。
    所有枚举排序输出，同一档案两次导出结果一致；两端等价性由同一批样本双端
    断言兜底（任务 6.1）。生成物不手工编辑：修改格式或档案后重新导出。
    """
    string_ops = sorted(STRING_OPS | {EXISTS})
    numeric_ops = sorted(NUMERIC_OPS | {EXISTS})
    string_fields = sorted(_STRING_FIELDS)
    scalar_fields = sorted(_NUMERIC_SCALAR_FIELDS)
    main_fields = sorted(f"main.{code}" for code in profile.stats)
    sub_fields = sorted(f"sub.{code}" for code in profile.stats)

    def leaf_branch(fields: list[str], value_schema: dict) -> dict:
        # value 的类型声明必须在分支主体 properties 内（additionalProperties
        # 只认同层声明），exists 不带 value 由 if/then 的存在性约束负责
        return {
            "type": "object",
            "properties": {
                "field": {"enum": fields},
                "op": {"enum": string_ops if value_schema["type"] == "string" else numeric_ops},
                "value": value_schema,
            },
            "required": ["field", "op"],
            "additionalProperties": False,
            "if": {"required": ["op"], "properties": {"op": {"const": EXISTS}}},
            "then": {"not": {"required": ["value"]}},
            "else": {"required": ["value"]},
        }

    number_schema = {"type": "number"}
    string_schema = {"type": "string"}

    def group_branch(key: str) -> dict:
        return {
            "type": "object",
            "properties": {key: {"type": "array", "items": {"$ref": "#/$defs/node"}}},
            "required": [key],
            "additionalProperties": False,
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Auto Grade Up 规则文件（{profile.game}）",
        "type": "object",
        "properties": {
            "version": {"const": 1},
            "game": {"const": profile.game},
            "name": {"type": "string", "minLength": 1},
            "candidates": {
                "type": "object",
                "properties": {
                    "rarity": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                            "minimum": profile.rarity_min,
                            "maximum": profile.rarity_max,
                        },
                    },
                    "slots": {"type": "array", "items": {"enum": sorted(profile.slots)}},
                    # 不与档案上限比对：超出无意义但无害（契约原文）
                    "max_level": {"type": "integer"},
                    "respect_lock": {"type": "boolean"},
                },
                "required": sorted(_CANDIDATES_KEYS),
                "additionalProperties": False,
            },
            "rule": {"$ref": "#/$defs/node"},
            "fodder": {
                "type": "object",
                "properties": {
                    "strategy": {"enum": [profile.round_mechanism]},
                    "respect_lock": {"type": "boolean"},
                },
                "required": sorted(_FODDER_KEYS),
                "additionalProperties": False,
            },
        },
        "required": sorted(_TOP_LEVEL_KEYS),
        "additionalProperties": False,
        "$defs": {
            "node": {
                "oneOf": [
                    {"$ref": "#/$defs/group_all"},
                    {"$ref": "#/$defs/group_any"},
                    {"$ref": "#/$defs/leaf"},
                ]
            },
            "group_all": group_branch("all"),
            "group_any": group_branch("any"),
            "leaf": {
                "oneOf": [
                    leaf_branch(string_fields, string_schema),
                    leaf_branch(scalar_fields, number_schema),
                    leaf_branch(main_fields, number_schema),
                    leaf_branch(sub_fields, number_schema),
                ]
            },
        },
    }
