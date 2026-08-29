"""任务 3.1：规则文件权威校验的单元测试。

校验清单逐类覆盖：顶层键集合、candidates/fodder 键集合、version、game、name、
candidates 取值域、组/叶子键互斥、字段名合法性（命名空间 + 档案代号）、
运算符与字段类型兼容、exists 无 value、值类型随字段、fodder.strategy 与档案一致。
"""

from pathlib import Path

import pytest

from agent.rule_lambda.profile import GameProfile, load_profile
from agent.rule_lambda.schema import RuleValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def genshin() -> GameProfile:
    return load_profile(REPO_ROOT / "assets/resource/genshin/profile.json")


def make_rule() -> dict:
    """spec §4 示例规则的完整形状（默认双爆规则）。"""
    return {
        "version": 1,
        "game": "genshin",
        "name": "默认双爆规则",
        "candidates": {
            "rarity": [5],
            "slots": [],
            "max_level": 20,
            "respect_lock": True,
        },
        "rule": {
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
        },
        "fodder": {"strategy": "staged_fill", "respect_lock": True},
    }


def expect_error(rule: dict, node_path: str, genshin: GameProfile) -> RuleValidationError:
    with pytest.raises(RuleValidationError) as exc_info:
        validate(rule, genshin)
    error = exc_info.value
    assert error.node_path == node_path, f"node_path={error.node_path!r}, message={error.message!r}"
    if node_path:
        assert node_path in str(error), "错误信息须含节点路径"
    return error


class TestLegalRules:
    def test_spec_example(self, genshin):
        assert validate(make_rule(), genshin) is None

    def test_empty_candidates_arrays_mean_unrestricted(self, genshin):
        rule = make_rule()
        rule["candidates"]["rarity"] = []
        rule["candidates"]["slots"] = []
        assert validate(rule, genshin) is None

    def test_max_level_not_compared_with_profile(self, genshin):
        rule = make_rule()
        rule["candidates"]["max_level"] = 99
        assert validate(rule, genshin) is None

    def test_exists_leaf_without_value(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "sub.crit_rate", "op": "exists"}]}
        assert validate(rule, genshin) is None

    def test_exists_on_string_and_scalar_fields(self, genshin):
        rule = make_rule()
        rule["rule"] = {
            "any": [
                {"field": "slot", "op": "exists"},
                {"field": "level", "op": "exists"},
            ]
        }
        assert validate(rule, genshin) is None

    def test_string_field_equality(self, genshin):
        rule = make_rule()
        rule["rule"] = {
            "all": [
                {"field": "slot", "op": "==", "value": "sands"},
                {"field": "set", "op": "!=", "value": "辰砂往生录"},
            ]
        }
        assert validate(rule, genshin) is None

    def test_scalar_only_tree(self, genshin):
        rule = make_rule()
        rule["rule"] = {
            "all": [
                {"field": "level", "op": "<", "value": 20},
                {"field": "rarity", "op": "==", "value": 5},
                {"field": "substat_count", "op": "!=", "value": 0},
            ]
        }
        assert validate(rule, genshin) is None

    def test_empty_groups_are_legal(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"all": []}, {"any": []}]}
        assert validate(rule, genshin) is None

    def test_deep_nesting_path_format(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"any": [{"all": [{"field": "level", "op": "<", "value": 5}]}]}]}
        assert validate(rule, genshin) is None


class TestTopLevel:
    def test_missing_key(self, genshin):
        rule = make_rule()
        del rule["fodder"]
        expect_error(rule, "", genshin)

    def test_extra_key(self, genshin):
        rule = make_rule()
        rule["rules"] = []
        expect_error(rule, "", genshin)

    def test_not_a_dict(self, genshin):
        with pytest.raises(RuleValidationError) as exc_info:
            validate([1], genshin)
        assert exc_info.value.node_path == ""

    def test_version_two(self, genshin):
        rule = make_rule()
        rule["version"] = 2
        expect_error(rule, "version", genshin)

    def test_version_not_int(self, genshin):
        rule = make_rule()
        rule["version"] = "1"
        expect_error(rule, "version", genshin)

    def test_game_mismatch(self, genshin):
        rule = make_rule()
        rule["game"] = "hsr"
        expect_error(rule, "game", genshin)

    def test_game_not_str(self, genshin):
        rule = make_rule()
        rule["game"] = 123
        expect_error(rule, "game", genshin)

    def test_name_empty(self, genshin):
        rule = make_rule()
        rule["name"] = ""
        expect_error(rule, "name", genshin)

    def test_name_not_str(self, genshin):
        rule = make_rule()
        rule["name"] = 7
        expect_error(rule, "name", genshin)


class TestCandidates:
    def test_missing_key(self, genshin):
        rule = make_rule()
        del rule["candidates"]["respect_lock"]
        expect_error(rule, "candidates", genshin)

    def test_extra_key(self, genshin):
        rule = make_rule()
        rule["candidates"]["min_level"] = 0
        expect_error(rule, "candidates", genshin)

    def test_not_a_dict(self, genshin):
        rule = make_rule()
        rule["candidates"] = []
        expect_error(rule, "candidates", genshin)

    def test_rarity_out_of_range_high(self, genshin):
        rule = make_rule()
        rule["candidates"]["rarity"] = [5, 6]
        expect_error(rule, "candidates.rarity[1]", genshin)

    def test_rarity_out_of_range_low(self, genshin):
        rule = make_rule()
        rule["candidates"]["rarity"] = [0]
        expect_error(rule, "candidates.rarity[0]", genshin)

    def test_rarity_element_not_int(self, genshin):
        rule = make_rule()
        rule["candidates"]["rarity"] = ["5"]
        expect_error(rule, "candidates.rarity[0]", genshin)

    def test_slots_unknown_code(self, genshin):
        rule = make_rule()
        rule["candidates"]["slots"] = ["rings"]
        expect_error(rule, "candidates.slots[0]", genshin)

    def test_max_level_not_int(self, genshin):
        rule = make_rule()
        rule["candidates"]["max_level"] = "20"
        expect_error(rule, "candidates.max_level", genshin)

    def test_max_level_float(self, genshin):
        rule = make_rule()
        rule["candidates"]["max_level"] = 20.5
        expect_error(rule, "candidates.max_level", genshin)

    def test_respect_lock_not_bool(self, genshin):
        rule = make_rule()
        rule["candidates"]["respect_lock"] = "yes"
        expect_error(rule, "candidates.respect_lock", genshin)


class TestFodder:
    def test_missing_key(self, genshin):
        rule = make_rule()
        del rule["fodder"]["strategy"]
        expect_error(rule, "fodder", genshin)

    def test_extra_key(self, genshin):
        rule = make_rule()
        rule["fodder"]["min_count"] = 1
        expect_error(rule, "fodder", genshin)

    def test_strategy_mismatch_with_profile(self, genshin):
        rule = make_rule()
        rule["fodder"]["strategy"] = "per_roll"
        expect_error(rule, "fodder.strategy", genshin)

    def test_strategy_not_str(self, genshin):
        rule = make_rule()
        rule["fodder"]["strategy"] = 123
        expect_error(rule, "fodder.strategy", genshin)

    def test_respect_lock_not_bool(self, genshin):
        rule = make_rule()
        rule["fodder"]["respect_lock"] = 1
        expect_error(rule, "fodder.respect_lock", genshin)


class TestConditionTree:
    def test_mixed_group_and_leaf_keys(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [], "field": "level"}
        expect_error(rule, "rule", genshin)

    def test_both_all_and_any(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [], "any": []}
        expect_error(rule, "rule", genshin)

    def test_empty_node(self, genshin):
        rule = make_rule()
        rule["rule"] = {}
        expect_error(rule, "rule", genshin)

    def test_rule_not_a_dict(self, genshin):
        rule = make_rule()
        rule["rule"] = 5
        expect_error(rule, "rule", genshin)

    def test_group_value_not_list(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": {"field": "level", "op": "exists"}}
        expect_error(rule, "rule", genshin)

    def test_child_not_a_dict(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [5]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_unknown_scalar_field(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "damage", "op": ">", "value": 5}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_unknown_stat_code(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "sub.foo", "op": "exists"}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_main_namespace_unknown_code(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "main.foo", "op": "exists"}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_bare_namespace_without_code(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "sub", "op": "exists"}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_string_field_rejects_numeric_op(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "slot", "op": ">=", "value": "sands"}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_exists_rejects_value(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "sub.crit_rate", "op": "exists", "value": 1}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_numeric_field_rejects_string_value(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "level", "op": "==", "value": "5"}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_string_field_rejects_number_value(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "set", "op": "==", "value": 5}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_reserved_contains_operator(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "set", "op": "contains", "value": "剧团"}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_unknown_operator(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "level", "op": "~", "value": 5}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_leaf_missing_value(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "level", "op": ">="}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_leaf_missing_op(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "level", "value": 5}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_leaf_extra_key(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"field": "level", "op": ">=", "value": 5, "note": "x"}]}
        expect_error(rule, "rule.all[0]", genshin)

    def test_nested_path_format(self, genshin):
        rule = make_rule()
        rule["rule"] = {"all": [{"any": [{"field": "nope", "op": "exists"}]}]}
        expect_error(rule, "rule.all[0].any[0]", genshin)

    def test_deep_nested_path_format(self, genshin):
        rule = make_rule()
        rule["rule"] = {
            "all": [
                {"field": "level", "op": "exists"},
                {
                    "any": [
                        {"field": "level", "op": "exists"},
                        {"field": "nope", "op": "exists"},
                    ]
                },
            ]
        }
        expect_error(rule, "rule.all[1].any[1]", genshin)
