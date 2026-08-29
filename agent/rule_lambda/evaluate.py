"""条件树求值与判定过程记录（trace）。

依据 ADR-0003：开始强化与继续强化共用同一棵条件树，每次求值只依赖当次输入
——圣遗物当前属性加「剩余强化次数」——不保存任何跨回合、跨圣遗物的历史状态；
同一件圣遗物被重复扫到时按当前属性重新判定，不做去重。

前置条件：传入的条件树已通过 schema.validate；未校验输入的行为未定义，
本模块不重复校验（见任务契约）。求值为纯函数：不修改输入、不读写模块级
可变状态。
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.rule_lambda.model import Artifact
from agent.rule_lambda.profile import GameProfile
from agent.rule_lambda.schema import EXISTS

# 字段缺失哨兵：恒存在字段之外的字段取不到值时使用，不与任何真实值冲突
_MISSING = object()


@dataclass
class Judgment:
    """一次判定的结果：结论与可独立复核的求值过程记录（trace）。"""

    passed: bool
    trace: dict


def remaining_rolls(artifact: Artifact, profile: GameProfile) -> int:
    """剩余强化次数 = ⌈(max_level − 等级) ÷ roll_interval⌉，向上取整。

    等级可能停在词条变动节点之间（如原神 +17 到 +20 仍有一次变动），
    向上取整保证仍计一次变动；参数取自游戏档案（design.md D5）。
    整数实现：-((level − max_level) // interval) 等价于对非负商向上取整。
    """
    return -((artifact.level - profile.max_level) // profile.roll_interval)


def evaluate(rule: dict, artifact: Artifact, profile: GameProfile) -> Judgment:
    """求值条件树，返回判定结果与 trace（与条件树同构的字典树）。"""
    trace = _eval_node(rule, artifact, profile)
    return Judgment(passed=trace["passed"], trace=trace)


def _eval_node(node: dict, artifact: Artifact, profile: GameProfile) -> dict:
    if "all" in node:
        children = [_eval_node(child, artifact, profile) for child in node["all"]]
        return {
            "kind": "all",
            "passed": all(child["passed"] for child in children),
            "children": children,
        }
    if "any" in node:
        children = [_eval_node(child, artifact, profile) for child in node["any"]]
        return {
            "kind": "any",
            "passed": any(child["passed"] for child in children),
            "children": children,
        }
    return _eval_leaf(node, artifact, profile)


def _eval_leaf(node: dict, artifact: Artifact, profile: GameProfile) -> dict:
    field = node["field"]
    op = node["op"]
    actual = _field_value(field, artifact, profile)
    present = actual is not _MISSING

    if op == EXISTS:
        passed = present
    else:
        passed = present and _compare(actual, op, node["value"])

    trace = {"kind": "leaf", "passed": passed, "field": field, "op": op}
    if op != EXISTS:
        trace["value"] = node["value"]
    trace["actual"] = actual if present else "missing"
    return trace


def _field_value(field: str, artifact: Artifact, profile: GameProfile):
    """取字段的当次实际值；main/sub 词条不存在时返回缺失哨兵。

    恒存在字段六个：level/rarity/slot/set/substat_count/remaining_rolls；
    remaining_rolls 由等级与档案参数现场推导，不入数据模型。
    """
    if field == "level":
        return artifact.level
    if field == "rarity":
        return artifact.rarity
    if field == "slot":
        return artifact.slot
    if field == "set":
        return artifact.set
    if field == "substat_count":
        return len(artifact.substats)
    if field == "remaining_rolls":
        return remaining_rolls(artifact, profile)

    namespace, _, code = field.partition(".")
    if namespace == "main":
        # 主词条恰为该代号时存在
        return artifact.main.value if artifact.main.name == code else _MISSING
    if namespace == "sub":
        # 代号重复时取首个匹配；游戏不会产生重复代号，重复属观测异常，
        # 是否在值域校验中拒绝由 M2 接线时定夺
        for substat in artifact.substats:
            if substat.name == code:
                return substat.value
        return _MISSING
    raise ValueError(f"未知字段名：{field!r}（前置条件：字段已经 schema.validate 校验）")


def _compare(actual, op: str, value) -> bool:
    if op == ">":
        return actual > value
    if op == "<":
        return actual < value
    if op == ">=":
        return actual >= value
    if op == "<=":
        return actual <= value
    if op == "==":
        return actual == value
    if op == "!=":
        return actual != value
    raise ValueError(f"未知运算符：{op!r}（前置条件：运算符已经 schema.validate 校验）")
