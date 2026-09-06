"""任务 4.1：条件树求值、可达性语义、缺失语义、空组语义、trace 形状与无状态的单元测试。

M2.5 起词条数值条件按乐观可达值求值（ADR-0006）：test 类 TestReachability 与
TestRollFieldSemantics 覆盖 discussion.md「可达性推导公式节」的每个分支。
"""

import copy
from pathlib import Path

import pytest

from agent.rule_lambda.evaluate import Judgment, evaluate, remaining_rolls
from agent.rule_lambda.model import Artifact, StatValue
from agent.rule_lambda.profile import GameProfile, ProfileError, load_profile

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def genshin() -> GameProfile:
    return load_profile(REPO_ROOT / "assets/resource/genshin/profile.json")


def make_artifact(**overrides) -> Artifact:
    base = dict(
        slot="sands",
        rarity=5,
        set="辰砂往生录",
        level=8,
        locked=False,
        main=StatValue(name="atk_percent", value=31.5),
        substats=[
            StatValue(name="crit_dmg", value=15.5),
            StatValue(name="crit_rate", value=5.8),
        ],
    )
    base.update(overrides)
    return Artifact(**base)


def double_crit_tree() -> dict:
    """spec §4 双爆规则的条件树部分。"""
    return {
        "all": [
            {
                "any": [
                    {"field": "sub.crit_dmg", "op": ">=", "value": 15},
                    {
                        "all": [
                            {"field": "sub.crit_rate", "op": ">=", "value": 8},
                            {"field": "remaining_rolls", "op": ">=", "value": 3},
                        ]
                    },
                ]
            }
        ]
    }


class TestRemainingRolls:
    """原神档案（上限 20、间隔 4）下 0/4/16/17/19/20 各档。"""

    @pytest.mark.parametrize(
        "level, expected",
        [(0, 5), (4, 4), (8, 3), (16, 1), (17, 1), (19, 1), (20, 0)],
    )
    def test_levels(self, genshin, level, expected):
        assert remaining_rolls(make_artifact(level=level), genshin) == expected


class TestEvaluateSemantics:
    def test_double_crit_pass(self, genshin):
        judgment = evaluate(double_crit_tree(), make_artifact(), genshin)
        assert isinstance(judgment, Judgment)
        assert judgment.passed is True

    def test_double_crit_fail(self, genshin):
        """+16 四条全解锁：R=1、U=0、budget=1——暴击伤害 5.0+7.8=12.8 达不到 15。"""
        artifact = make_artifact(
            level=16,
            substats=[
                StatValue(name="crit_dmg", value=5.0),
                StatValue(name="crit_rate", value=2.7),
                StatValue(name="atk", value=16.0),
                StatValue(name="def_percent", value=5.8),
            ],
        )
        judgment = evaluate(double_crit_tree(), artifact, genshin)
        assert judgment.passed is False

    def test_string_equality_uses_game_text(self, genshin):
        tree = {"all": [{"field": "slot", "op": "==", "value": "sands"},
                        {"field": "set", "op": "==", "value": "辰砂往生录"}]}
        assert evaluate(tree, make_artifact(), genshin).passed is True
        tree = {"all": [{"field": "set", "op": "!=", "value": "黄金剧团"}]}
        assert evaluate(tree, make_artifact(), genshin).passed is True

    def test_substat_count(self, genshin):
        tree = {"all": [{"field": "substat_count", "op": "==", "value": 2}]}
        assert evaluate(tree, make_artifact(), genshin).passed is True
        tree = {"all": [{"field": "substat_count", "op": "==", "value": 4}]}
        assert evaluate(tree, make_artifact(), genshin).passed is False

    def test_substat_count_excludes_pending(self, genshin):
        """substat_count 只计已解锁条数（待激活行不计）。"""
        artifact = make_artifact(
            level=0,
            substats=[
                StatValue(name="crit_dmg", value=15.5),
                StatValue(name="crit_rate", value=5.8),
                StatValue(name="atk", value=117.0),
                StatValue(name="hp", value=269.0, pending=True),
            ],
        )
        tree = {"all": [{"field": "substat_count", "op": "==", "value": 3}]}
        assert evaluate(tree, artifact, genshin).passed is True
        tree = {"all": [{"field": "substat_count", "op": "==", "value": 4}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_remaining_rolls_field_uses_computed_value(self, genshin):
        tree = {"all": [{"field": "remaining_rolls", "op": "==", "value": 3}]}
        assert evaluate(tree, make_artifact(level=8), genshin).passed is True

    def test_main_stays_current_value(self, genshin):
        """main.* 维持当前值口径，不做可达重写（ADR-0006 的边界，design.md D4）。"""
        tree = {"all": [{"field": "main.atk_percent", "op": "==", "value": 31.5}]}
        assert evaluate(tree, make_artifact(), genshin).passed is True


class TestReachability:
    """乐观可达值口径（ADR-0006）：discussion.md「可达性推导公式节」逐分支断言。

    基准推导（原神档案）：R = ⌈(20 − 等级) ÷ 4⌉；U = min(4 − 已解锁, R)；
    budget = R − U；5 星暴击伤害单次上限 7.8、生命值 299、暴击率 3.9。
    """

    def test_growth_reaches_threshold_passes(self, genshin):
        # level 8、2 条已解锁：R=3、U=2、budget=1；15.0 + 1×7.8 = 22.8
        artifact = make_artifact(
            substats=[StatValue(name="crit_dmg", value=15.0), StatValue(name="crit_rate", value=5.8)]
        )
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 22.8}]}
        assert evaluate(tree, artifact, genshin).passed is True

    def test_growth_insufficient_prunes(self, genshin):
        # 同上 budget=1：全部投入也只到 22.8，达不到 22.9 → 提前止损
        artifact = make_artifact(
            substats=[StatValue(name="crit_dmg", value=15.0), StatValue(name="crit_rate", value=5.8)]
        )
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 22.9}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_future_unlock_occupies_budget(self, genshin):
        # 只解锁 1 条（构造形态）：U=min(3, 3)=3、budget=0 → 可达值=当前值
        artifact = make_artifact(substats=[StatValue(name="crit_dmg", value=15.0)])
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 15.0}]}
        assert evaluate(tree, artifact, genshin).passed is True
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 15.1}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_four_unlocked_full_budget(self, genshin):
        # +0 四条全解锁（L2 形态）：R=5、U=0、budget=5；5.8 + 5×5.8 = 34.8
        artifact = make_artifact(
            level=0,
            substats=[
                StatValue(name="hp_percent", value=5.8),
                StatValue(name="crit_rate", value=3.1),
                StatValue(name="atk", value=16.0),
                StatValue(name="def_percent", value=5.8),
            ],
        )
        tree = {"all": [{"field": "sub.hp_percent", "op": ">=", "value": 34.8}]}
        assert evaluate(tree, artifact, genshin).passed is True

    def test_pending_preview_value_starts_reachability(self, genshin):
        # L1 形态：+0、3 条解锁 + 1 待激活：R=5、U=min(1, 5)=1、budget=4；
        # 待激活词条当前值即预览值：269 + 4×299 = 1465
        artifact = make_artifact(
            level=0,
            substats=[
                StatValue(name="elemental_mastery", value=23.0),
                StatValue(name="atk_percent", value=4.1),
                StatValue(name="def", value=16.0),
                StatValue(name="hp", value=269.0, pending=True),
            ],
        )
        tree = {"all": [{"field": "sub.hp", "op": ">=", "value": 1465}]}
        assert evaluate(tree, artifact, genshin).passed is True
        tree = {"all": [{"field": "sub.hp", "op": ">=", "value": 1466}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_pending_stat_exists(self, genshin):
        """待激活词条视为存在（词条种类已由游戏预生成）。"""
        artifact = make_artifact(
            level=0,
            substats=[
                StatValue(name="crit_dmg", value=15.5),
                StatValue(name="crit_rate", value=5.8),
                StatValue(name="atk", value=117.0),
                StatValue(name="hp", value=269.0, pending=True),
            ],
        )
        assert evaluate({"all": [{"field": "sub.hp", "op": "exists"}]},
                        artifact, genshin).passed is True

    def test_max_level_zero_budget(self, genshin):
        # +20 满级：R=0 → budget=0 → 可达值=当前值
        artifact = make_artifact(
            level=20,
            substats=[
                StatValue(name="crit_rate", value=6.6),
                StatValue(name="crit_dmg", value=6.2),
                StatValue(name="hp", value=269.0),
                StatValue(name="hp_percent", value=18.1),
            ],
        )
        tree = {"all": [{"field": "sub.crit_rate", "op": ">=", "value": 6.6}]}
        assert evaluate(tree, artifact, genshin).passed is True
        tree = {"all": [{"field": "sub.crit_rate", "op": ">=", "value": 6.7}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_level_between_change_points(self, genshin):
        # +17（变动点之间）：R=1、4 条已解锁 → U=0、budget=1；5.0+7.8=12.8
        artifact = make_artifact(
            level=17,
            substats=[
                StatValue(name="crit_dmg", value=5.0),
                StatValue(name="crit_rate", value=2.7),
                StatValue(name="atk", value=16.0),
                StatValue(name="def_percent", value=5.8),
            ],
        )
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 12.8}]}
        assert evaluate(tree, artifact, genshin).passed is True
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 12.9}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_missing_stat_never_reachable(self, genshin):
        # 目标词条完全不出现（4 条已满且无该代号）→ 缺失 → 条件不通过
        artifact = make_artifact(
            level=16,
            substats=[
                StatValue(name="crit_rate", value=2.7),
                StatValue(name="atk", value=16.0),
                StatValue(name="def_percent", value=5.8),
                StatValue(name="hp_percent", value=4.7),
            ],
        )
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 0}]}
        assert evaluate(tree, artifact, genshin).passed is False
        tree = {"all": [{"field": "sub.crit_dmg", "op": "exists"}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_growth_table_missing_raises_profile_error(self, genshin):
        """求值查上限表缺失（原神 3 星无表数据）→ ProfileError 向上抛。"""
        artifact = make_artifact(rarity=3, substats=[StatValue(name="crit_dmg", value=5.0)])
        tree = {"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 10}]}
        with pytest.raises(ProfileError):
            evaluate(tree, artifact, genshin)


class TestRollFieldSemantics:
    """roll.<代号> 的可达口径与缺失语义（次数规则体系，design.md D5 / D7）。"""

    def test_roll_reachable(self, genshin):
        # roll_count=2、level 8、2 条已解锁：budget=1 → 可达 3
        artifact = make_artifact(substats=[
            StatValue(name="crit_rate", value=5.8, roll_count=2),
            StatValue(name="crit_dmg", value=15.5),
        ])
        tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 3}]}
        assert evaluate(tree, artifact, genshin).passed is True
        tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 4}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_roll_unknown_count_numeric_fails_exists_true(self, genshin):
        """roll_count 为 null（未知）时数值比较不通过、exists 为真。"""
        artifact = make_artifact(substats=[StatValue(name="crit_rate", value=5.8)])
        tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 0}]}
        judgment = evaluate(tree, artifact, genshin)
        assert judgment.passed is False
        leaf = judgment.trace["rule"]["children"][0]
        assert leaf["actual"] == "unknown"
        tree = {"all": [{"field": "roll.crit_rate", "op": "exists"}]}
        assert evaluate(tree, artifact, genshin).passed is True

    def test_roll_missing_stat(self, genshin):
        artifact = make_artifact(substats=[StatValue(name="atk", value=117.0)])
        tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 0}]}
        assert evaluate(tree, artifact, genshin).passed is False
        tree = {"all": [{"field": "roll.crit_rate", "op": "exists"}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_roll_no_growth_table_needed(self, genshin):
        """次数可达值不查成长上限表（3 星圣遗物的 roll 条件仍可求值）。"""
        artifact = make_artifact(
            rarity=3, substats=[StatValue(name="crit_rate", value=5.8, roll_count=1)]
        )
        tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 2}]}
        assert evaluate(tree, artifact, genshin).passed is False  # 未知星级 budget 推导仍成立
        artifact = make_artifact(
            rarity=3,
            level=0,
            substats=[StatValue(name="crit_rate", value=5.8, roll_count=1)],
        )
        # +0：R=5、1 条已解锁 → U=3、budget=2 → 可达 3
        assert evaluate(tree, artifact, genshin).passed is True


class TestRollRuleInterface:
    """evaluate 第四参 roll_rule：None 只按 rule 求值；传入时两树取与（design.md D5）。"""

    def test_no_roll_rule_trace_top(self, genshin):
        judgment = evaluate(double_crit_tree(), make_artifact(), genshin)
        assert set(judgment.trace) == {"rule", "roll_rule"}
        assert judgment.trace["roll_rule"] is None
        assert judgment.trace["rule"]["kind"] == "all"

    def test_roll_rule_pass_merges_and(self, genshin):
        artifact = make_artifact(substats=[
            StatValue(name="crit_dmg", value=15.5, roll_count=2),
            StatValue(name="crit_rate", value=5.8, roll_count=1),
        ])
        roll_tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 2}]}
        judgment = evaluate(double_crit_tree(), artifact, genshin, roll_tree)
        assert judgment.passed is True
        assert judgment.trace["roll_rule"]["kind"] == "all"
        assert judgment.trace["roll_rule"]["passed"] is True

    def test_roll_rule_fail_blocks_passing_rule(self, genshin):
        artifact = make_artifact(substats=[
            StatValue(name="crit_dmg", value=15.5, roll_count=2),
            StatValue(name="crit_rate", value=5.8, roll_count=1),
        ])
        roll_tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 5}]}
        judgment = evaluate(double_crit_tree(), artifact, genshin, roll_tree)
        assert judgment.passed is False
        assert judgment.trace["rule"]["passed"] is True
        assert judgment.trace["roll_rule"]["passed"] is False

    def test_rule_fail_blocks_passing_roll_rule(self, genshin):
        artifact = make_artifact(substats=[StatValue(name="crit_rate", value=5.8, roll_count=2)])
        roll_tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 2}]}
        tree = {"all": [{"field": "sub.crit_dmg", "op": "exists"}]}
        judgment = evaluate(tree, artifact, genshin, roll_tree)
        assert judgment.passed is False
        assert judgment.trace["rule"]["passed"] is False
        assert judgment.trace["roll_rule"]["passed"] is True

    def test_roll_rule_unknown_count_blocks(self, genshin):
        """次数未知（null）在次数体系下同样不通过（识别异常不静默放行）。"""
        artifact = make_artifact(substats=[StatValue(name="crit_rate", value=5.8)])
        roll_tree = {"all": [{"field": "roll.crit_rate", "op": ">=", "value": 1}]}
        judgment = evaluate({"all": []}, artifact, genshin, roll_tree)
        assert judgment.passed is False


class TestMissingSemantics:
    """main.<代号> 与 sub.<代号> 缺失同语义：数值比较 False、exists False。"""

    def test_sub_missing_numeric_compare_false(self, genshin):
        artifact = make_artifact(substats=[StatValue(name="atk", value=117.0)])
        tree = {"all": [{"field": "sub.crit_rate", "op": ">=", "value": 0}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_sub_missing_exists_false(self, genshin):
        artifact = make_artifact(substats=[StatValue(name="atk", value=117.0)])
        tree = {"all": [{"field": "sub.crit_rate", "op": "exists"}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_main_missing_numeric_compare_false(self, genshin):
        artifact = make_artifact(main=StatValue(name="crit_rate", value=5.8))
        tree = {"all": [{"field": "main.atk_percent", "op": ">", "value": 0}]}
        assert evaluate(tree, artifact, genshin).passed is False

    def test_main_exists_only_when_exact_code(self, genshin):
        artifact = make_artifact(main=StatValue(name="crit_rate", value=5.8))
        assert evaluate({"all": [{"field": "main.crit_rate", "op": "exists"}]},
                        artifact, genshin).passed is True
        assert evaluate({"all": [{"field": "main.atk_percent", "op": "exists"}]},
                        artifact, genshin).passed is False

    def test_scalar_fields_always_exist(self, genshin):
        artifact = make_artifact()
        for field in ("level", "rarity", "slot", "set", "substat_count", "remaining_rolls"):
            tree = {"all": [{"field": field, "op": "exists"}]}
            assert evaluate(tree, artifact, genshin).passed is True, field


class TestEmptyGroups:
    def test_all_empty_passes(self, genshin):
        assert evaluate({"all": []}, make_artifact(), genshin).passed is True

    def test_any_empty_fails(self, genshin):
        assert evaluate({"any": []}, make_artifact(), genshin).passed is False


class TestTraceShape:
    def test_group_trace_keys(self, genshin):
        trace = evaluate({"all": [{"any": []}]}, make_artifact(), genshin).trace["rule"]
        assert set(trace) == {"kind", "passed", "children"}
        assert trace["kind"] == "all"
        assert set(trace["children"][0]) == {"kind", "passed", "children"}

    def test_numeric_sub_leaf_trace_has_derivation(self, genshin):
        """词条命名空间叶子增 derivation：当前值、可分配成长次数、成长上限。"""
        trace = evaluate({"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 15}]},
                         make_artifact(), genshin).trace["rule"]["children"][0]
        assert set(trace) == {"kind", "passed", "field", "op", "value", "actual", "derivation"}
        assert trace == {
            "kind": "leaf", "passed": True, "field": "sub.crit_dmg",
            "op": ">=", "value": 15, "actual": 23.3,
            "derivation": {"current": 15.5, "budget": 1, "growth_max": 7.8},
        }

    def test_roll_leaf_trace_derivation_shape(self, genshin):
        artifact = make_artifact(substats=[
            StatValue(name="crit_rate", value=5.8, roll_count=2),
            StatValue(name="crit_dmg", value=15.5),
        ])
        trace = evaluate({"all": [{"field": "roll.crit_rate", "op": ">=", "value": 3}]},
                         artifact, genshin).trace["rule"]["children"][0]
        assert trace["actual"] == 3
        assert trace["derivation"] == {"current_rolls": 2, "budget": 1}

    def test_exists_leaf_trace_has_no_value_or_derivation(self, genshin):
        trace = evaluate({"all": [{"field": "sub.crit_rate", "op": "exists"}]},
                         make_artifact(), genshin).trace["rule"]["children"][0]
        assert set(trace) == {"kind", "passed", "field", "op", "actual"}
        assert trace["actual"] == 5.8

    def test_string_leaf_trace_shape(self, genshin):
        trace = evaluate({"all": [{"field": "slot", "op": "==", "value": "sands"}]},
                         make_artifact(), genshin).trace["rule"]["children"][0]
        assert set(trace) == {"kind", "passed", "field", "op", "value", "actual"}
        assert trace["actual"] == "sands"
        assert trace["passed"] is True

    def test_missing_actual_is_missing_string(self, genshin):
        artifact = make_artifact(substats=[])
        trace = evaluate({"all": [{"field": "sub.crit_rate", "op": ">=", "value": 0}]},
                         artifact, genshin).trace["rule"]["children"][0]
        assert trace["actual"] == "missing"
        assert trace["passed"] is False
        assert "derivation" not in trace

    def test_trace_mirrors_tree_structure(self, genshin):
        tree = double_crit_tree()
        trace = evaluate(tree, make_artifact(), genshin).trace["rule"]
        # 同构：组节点 children 数与条件树子节点数一致，叶子 field/op 一致
        assert len(trace["children"]) == len(tree["all"])
        any_trace = trace["children"][0]
        assert any_trace["kind"] == "any"
        assert len(any_trace["children"]) == len(tree["all"][0]["any"])
        leaf = any_trace["children"][0]
        assert leaf["kind"] == "leaf"
        assert leaf["field"] == tree["all"][0]["any"][0]["field"]
        assert leaf["op"] == tree["all"][0]["any"][0]["op"]
        inner_all = any_trace["children"][1]
        assert inner_all["kind"] == "all"
        assert len(inner_all["children"]) == 2

    def test_every_passed_independently_recheckable(self, genshin):
        """组节点的 passed 可由子节点 passed 独立复核（递归到每个组节点）。"""
        tree = {
            "all": [
                {"any": [{"field": "level", "op": "exists"}, {"all": []}]},
                {"any": []},
                {"field": "rarity", "op": "==", "value": 5},
            ]
        }
        trace = evaluate(tree, make_artifact(), genshin).trace["rule"]

        def walk(node: dict, node_trace: dict) -> None:
            if "all" not in node and "any" not in node:
                return
            kind = "all" if "all" in node else "any"
            child_passed = [child["passed"] for child in node_trace["children"]]
            expected = all(child_passed) if kind == "all" else any(child_passed)
            assert node_trace["passed"] == expected, node_trace["kind"]
            for child, child_trace in zip(node[kind], node_trace["children"]):
                walk(child, child_trace)

        walk(tree, trace)


class TestStateless:
    def test_same_input_same_output(self, genshin):
        artifact = make_artifact()
        rule = double_crit_tree()
        first = evaluate(rule, artifact, genshin)
        second = evaluate(rule, artifact, genshin)
        assert first.passed == second.passed
        assert first.trace == second.trace

    def test_inputs_not_modified(self, genshin):
        artifact = make_artifact()
        rule = double_crit_tree()
        artifact_snapshot = copy.deepcopy(artifact.to_dict())
        rule_snapshot = copy.deepcopy(rule)
        evaluate(rule, artifact, genshin)
        assert artifact.to_dict() == artifact_snapshot
        assert rule == rule_snapshot
