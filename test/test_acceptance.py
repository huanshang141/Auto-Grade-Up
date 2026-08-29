"""任务 6.1：M1 验收——示例规则、合法/非法样本集与双端一致性。

双端：手写校验（validate，权威实现）与 JSON Schema 生成物
（Draft202012Validator 加载 export_json_schema 的产物，M5 编辑器同源副本）。
每个样本上两端的结论必须一致且符合预期；这是 design.md D4 等价性承诺的
固化测试，也是 spec §14 M1 验收标准「合法样例通过、非法样例被拒绝」的落点。
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agent.rule_lambda.profile import GameProfile, load_profile
from agent.rule_lambda.schema import RuleValidationError, export_json_schema, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
GENSHIN_PROFILE = REPO_ROOT / "assets/resource/genshin/profile.json"
RULES_EXAMPLE = REPO_ROOT / "docs/examples/rules.example.json"
ILLEGAL_DIR = REPO_ROOT / "test/fixtures/rules"


def base_rule(rule: dict) -> dict:
    """补齐一份合法骨架，调用方只需替换 rule/fodder 等目标部分。"""
    return {
        "version": 1,
        "game": "genshin",
        "name": "合法样本",
        "candidates": {"rarity": [5], "slots": [], "max_level": 20, "respect_lock": True},
        "rule": rule,
        "fodder": {"strategy": "staged_fill", "respect_lock": True},
    }


def inline_legal_samples() -> list[tuple[str, dict]]:
    """四份内联合法样本：exists 叶子、两层嵌套、字符串字段相等、仅标量字段。
    （示例规则单独有测试，覆盖空 slots 与多层嵌套两类合法形态。）"""
    return [
        ("exists-leaf", base_rule({"all": [{"field": "sub.crit_rate", "op": "exists"}]})),
        (
            "two-level-nesting",
            base_rule(
                {
                    "all": [
                        {
                            "any": [
                                {"field": "level", "op": "<", "value": 20},
                                {
                                    "all": [
                                        {"field": "substat_count", "op": ">=", "value": 1},
                                        {"field": "remaining_rolls", "op": ">=", "value": 1},
                                    ]
                                },
                            ]
                        }
                    ]
                }
            ),
        ),
        (
            "string-field-equality",
            base_rule(
                {
                    "all": [
                        {"field": "slot", "op": "==", "value": "sands"},
                        {"field": "set", "op": "!=", "value": "黄金剧团"},
                    ]
                }
            ),
        ),
        (
            "scalar-fields-only",
            base_rule(
                {
                    "all": [
                        {"field": "level", "op": "<=", "value": 20},
                        {"field": "rarity", "op": "==", "value": 5},
                        {"field": "substat_count", "op": ">=", "value": 0},
                        {"field": "remaining_rolls", "op": ">=", "value": 1},
                    ]
                }
            ),
        ),
    ]


@pytest.fixture(scope="module")
def genshin() -> GameProfile:
    return load_profile(GENSHIN_PROFILE)


@pytest.fixture(scope="module")
def validator(genshin) -> Draft202012Validator:
    return Draft202012Validator(export_json_schema(genshin))


class TestLegalSamples:
    def test_example_rule(self, genshin, validator):
        """示例规则 = spec §4 双爆规则的代号版：含 game: "genshin"，双端通过
        （其 slots 为空数组、条件树多层嵌套，同时覆盖这两类合法形态）。"""
        example = json.loads(RULES_EXAMPLE.read_text(encoding="utf-8"))
        assert example["game"] == "genshin"
        assert example["name"] == "默认双爆规则"
        assert validate(copy.deepcopy(example), genshin) is None
        assert validator.is_valid(example) is True

    @pytest.mark.parametrize(
        "rule",
        [rule for _, rule in inline_legal_samples()],
        ids=[name for name, _ in inline_legal_samples()],
    )
    def test_inline_legal_passes_both_ends(self, rule, genshin, validator):
        assert validate(copy.deepcopy(rule), genshin) is None
        assert validator.is_valid(rule) is True


class TestIllegalSamples:
    @pytest.mark.parametrize(
        "path", sorted(ILLEGAL_DIR.glob("*.json")), ids=lambda p: p.stem
    )
    def test_rejected_both_ends(self, path, genshin, validator):
        rule = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(RuleValidationError):
            validate(rule, genshin)
        assert validator.is_valid(rule) is False
