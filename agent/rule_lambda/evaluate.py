"""条件树求值与判定过程记录（trace）。

依据 ADR-0003：开始强化与继续强化共用同一棵条件树，每次求值只依赖当次输入
——圣遗物当前属性加「剩余强化次数」——不保存任何跨回合、跨圣遗物的历史状态；
同一件圣遗物被重复扫到时按当前属性重新判定，不做去重。

词条数值条件的判定口径是乐观可达值（ADR-0006，M2.5 起）：sub.<代号> 与
roll.<代号> 的求值实际值为「剩余变动点全部投入该词条」能达到的上界——
达成无望即提前止损（强化剪枝），推导公式见 _growth_budget。main.* 与标量
字段维持当前值口径（主词条成长是确定性的）。次数规则体系（roll_rule）为
独立顶层键，调用方显式传参：None 表示不求值次数体系（列表初扫），传入时
两棵树都求值、passed 为两者与合并（design.md D5，执行机构持有界面知识）。

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
# 次数未知哨兵：词条存在但 roll_count 为 null（界面不显示该信息）——
# 数值比较按缺失处理（不通过，安全方向），exists 判定为真（design.md D7）
_UNKNOWN = object()


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


def evaluate(rule: dict, artifact: Artifact, profile: GameProfile, roll_rule: dict | None = None) -> Judgment:
    """求值条件树，返回判定结果与 trace。

    trace 顶层为 {"rule": <rule 树的求值 trace>, "roll_rule": <次数树 trace 或 null>}；
    roll_rule 传入时 passed 为两棵树的求值结果取与。
    """
    rule_trace = _eval_node(rule, artifact, profile)
    if roll_rule is None:
        return Judgment(
            passed=rule_trace["passed"],
            trace={"rule": rule_trace, "roll_rule": None},
        )
    roll_trace = _eval_node(roll_rule, artifact, profile)
    return Judgment(
        passed=rule_trace["passed"] and roll_trace["passed"],
        trace={"rule": rule_trace, "roll_rule": roll_trace},
    )


def _growth_budget(artifact: Artifact, profile: GameProfile) -> int:
    """可分配成长次数 = 剩余变动点数 − 未来必解锁数（design.md D3）。

    剩余变动点数 R = ⌈(max_level − 等级) ÷ 间隔⌉；未来必解锁数
    U = min(副词条上限 − 已解锁条数, R)——副词条未满上限时下一个变动点必
    解锁新词条（含待激活词条转正），不扣除会让可达值虚高、剪枝变钝。
    """
    changes = remaining_rolls(artifact, profile)
    unlocked = sum(1 for substat in artifact.substats if not substat.pending)
    future_unlocks = min(profile.substat_max - unlocked, changes)
    return changes - future_unlocks


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

    if op == EXISTS:
        # 存在判断不涉及可达性：待激活词条视为存在（词条种类已由游戏预生成），
        # actual 为当前实际值、不计 derivation
        present = _field_present(field, artifact)
        trace = {"kind": "leaf", "passed": present, "field": field, "op": op}
        if present:
            actual = _current_value(field, artifact, profile)
            trace["actual"] = "unknown" if actual is _UNKNOWN else actual
        else:
            trace["actual"] = "missing"
        return trace

    actual, derivation = _field_value(field, artifact, profile)
    present = actual is not _MISSING
    unknown = actual is _UNKNOWN
    passed = present and not unknown and _compare(actual, op, node["value"])

    trace = {"kind": "leaf", "passed": passed, "field": field, "op": op, "value": node["value"]}
    if unknown:
        trace["actual"] = "unknown"
    else:
        trace["actual"] = actual if present else "missing"
    if derivation is not None:
        trace["derivation"] = derivation
    return trace


def _field_value(field: str, artifact: Artifact, profile: GameProfile):
    """数值字段的求值实际值，返回 (实际值, derivation)。

    标量字段与 main.* 取当前值口径；sub.<代号> 取乐观可达值（当前值 + 可分配
    成长次数 × 档案单次成长上限，待激活词条当前值即预览值）；roll.<代号> 取
    次数可达值（当前强化次数 + 可分配成长次数，次数未知时为 _UNKNOWN 哨兵）。
    词条不存在时为 _MISSING（derivation 为 None）。成长上限查表缺失（如未
    录入的星级）→ ProfileError 向上抛，调用方立即停止。
    """
    if field == "level":
        return artifact.level, None
    if field == "rarity":
        return artifact.rarity, None
    if field == "slot":
        return artifact.slot, None
    if field == "set":
        return artifact.set, None
    if field == "substat_count":
        # 只计已解锁条数（待激活行不计，judgment 契约）
        return sum(1 for s in artifact.substats if not s.pending), None
    if field == "remaining_rolls":
        return remaining_rolls(artifact, profile), None

    namespace, _, code = field.partition(".")
    if namespace == "main":
        # 主词条恰为该代号时存在，成长确定性、维持当前值口径
        if artifact.main.name == code:
            return artifact.main.value, None
        return _MISSING, None
    if namespace in ("sub", "roll"):
        # 代号重复时取首个匹配；游戏不会产生重复代号，重复属观测异常
        stat = next((s for s in artifact.substats if s.name == code), None)
        if stat is None:
            return _MISSING, None
        budget = _growth_budget(artifact, profile)
        if namespace == "sub":
            growth = profile.growth_max(artifact.rarity, code)
            return (
                stat.value + budget * growth,
                {"current": stat.value, "budget": budget, "growth_max": growth},
            )
        if stat.roll_count is None:
            return _UNKNOWN, {"current_rolls": None, "budget": budget}
        return (
            stat.roll_count + budget,
            {"current_rolls": stat.roll_count, "budget": budget},
        )
    raise ValueError(f"未知字段名：{field!r}（前置条件：字段已经 schema.validate 校验）")


def _field_present(field: str, artifact: Artifact) -> bool:
    """exists 判断的存在性：待激活词条视为存在；roll.<代号> 存在性同 sub.<代号>。"""
    if field in ("level", "rarity", "slot", "set", "substat_count", "remaining_rolls"):
        return True
    namespace, _, code = field.partition(".")
    if namespace == "main":
        return artifact.main.name == code
    if namespace in ("sub", "roll"):
        return any(substat.name == code for substat in artifact.substats)
    raise ValueError(f"未知字段名：{field!r}（前置条件：字段已经 schema.validate 校验）")


def _current_value(field: str, artifact: Artifact, profile: GameProfile):
    """exists 叶子的 actual：字段存在时的当前实际值（可达性不参与存在判断）。"""
    if field == "level":
        return artifact.level
    if field == "rarity":
        return artifact.rarity
    if field == "slot":
        return artifact.slot
    if field == "set":
        return artifact.set
    if field == "substat_count":
        return sum(1 for s in artifact.substats if not s.pending)
    if field == "remaining_rolls":
        return remaining_rolls(artifact, profile)
    namespace, _, code = field.partition(".")
    if namespace == "main":
        return artifact.main.value
    stat = next((s for s in artifact.substats if s.name == code), None)
    if namespace == "roll" and stat is not None and stat.roll_count is None:
        return _UNKNOWN
    return stat.value


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
