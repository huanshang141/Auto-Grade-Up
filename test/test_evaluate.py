"""任务 4.1：条件树求值、缺失语义、空组语义、trace 形状与无状态的单元测试。"""

import copy
from pathlib import Path

import pytest

from agent.rule_lambda.evaluate import Judgment, evaluate, remaining_rolls
from agent.rule_lambda.model import Artifact, StatValue
from agent.rule_lambda.profile import GameProfile, load_profile

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
        artifact = make_artifact(substats=[StatValue(name="crit_dmg", value=10.0),
                                           StatValue(name="crit_rate", value=5.0)])
        judgment = evaluate(double_crit_tree(), artifact, genshin)
        assert judgment.passed is False

    def test_numeric_boundaries_inclusive(self, genshin):
        artifact = make_artifact(substats=[StatValue(name="crit_dmg", value=15.0)])
        assert evaluate(double_crit_tree(), artifact, genshin).passed is True
        artifact = make_artifact(substats=[StatValue(name="crit_dmg", value=14.9)])
        assert evaluate(double_crit_tree(), artifact, genshin).passed is False

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

    def test_remaining_rolls_field_uses_computed_value(self, genshin):
        tree = {"all": [{"field": "remaining_rolls", "op": "==", "value": 3}]}
        assert evaluate(tree, make_artifact(level=8), genshin).passed is True


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
        trace = evaluate({"all": [{"any": []}]}, make_artifact(), genshin).trace
        assert set(trace) == {"kind", "passed", "children"}
        assert trace["kind"] == "all"
        assert set(trace["children"][0]) == {"kind", "passed", "children"}

    def test_numeric_leaf_trace_keys(self, genshin):
        trace = evaluate({"all": [{"field": "sub.crit_dmg", "op": ">=", "value": 15}]},
                         make_artifact(), genshin).trace["children"][0]
        assert set(trace) == {"kind", "passed", "field", "op", "value", "actual"}
        assert trace == {"kind": "leaf", "passed": True, "field": "sub.crit_dmg",
                         "op": ">=", "value": 15, "actual": 15.5}

    def test_exists_leaf_trace_has_no_value_key(self, genshin):
        trace = evaluate({"all": [{"field": "sub.crit_rate", "op": "exists"}]},
                         make_artifact(), genshin).trace["children"][0]
        assert set(trace) == {"kind", "passed", "field", "op", "actual"}
        assert trace["actual"] == 5.8

    def test_string_leaf_trace_shape(self, genshin):
        trace = evaluate({"all": [{"field": "slot", "op": "==", "value": "sands"}]},
                         make_artifact(), genshin).trace["children"][0]
        assert set(trace) == {"kind", "passed", "field", "op", "value", "actual"}
        assert trace["actual"] == "sands"
        assert trace["passed"] is True

    def test_missing_actual_is_missing_string(self, genshin):
        artifact = make_artifact(substats=[])
        trace = evaluate({"all": [{"field": "sub.crit_rate", "op": ">=", "value": 0}]},
                         artifact, genshin).trace["children"][0]
        assert trace["actual"] == "missing"
        assert trace["passed"] is False

    def test_trace_mirrors_tree_structure(self, genshin):
        tree = double_crit_tree()
        trace = evaluate(tree, make_artifact(), genshin).trace
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
        trace = evaluate(tree, make_artifact(), genshin).trace

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
