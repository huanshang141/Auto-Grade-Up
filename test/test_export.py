"""任务 5.1：JSON Schema 导出（函数 + CLI）的单元测试。

生成物按档案参数化：代号枚举、game 常量、candidates 值域、fodder.strategy
枚举全部来自传入档案；枚举排序输出保证同一档案两次导出逐字节一致；
生成物可被 jsonschema.Draft202012Validator 直接加载。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agent.rule_lambda.profile import GameProfile, load_profile
from agent.rule_lambda.schema import export_json_schema

REPO_ROOT = Path(__file__).resolve().parents[1]
GENSHIN_PROFILE = REPO_ROOT / "assets/resource/genshin/profile.json"
SECOND_PROFILE = REPO_ROOT / "test/fixtures/profiles/second_game.json"


@pytest.fixture(scope="module")
def genshin() -> GameProfile:
    return load_profile(GENSHIN_PROFILE)


@pytest.fixture(scope="module")
def second() -> GameProfile:
    return load_profile(SECOND_PROFILE)


def make_rule() -> dict:
    """一份合法规则（spec §4 双爆规则形状），供生成物冒烟验证。"""
    return {
        "version": 1,
        "game": "genshin",
        "name": "默认双爆规则",
        "candidates": {"rarity": [5], "slots": [], "max_level": 20, "respect_lock": True},
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


def collect_string_enums(node, found):
    """递归收集生成物里全部字符串枚举，供排序断言。"""
    if isinstance(node, dict):
        enum = node.get("enum")
        if isinstance(enum, list) and enum and all(isinstance(e, str) for e in enum):
            found.append(enum)
        for value in node.values():
            collect_string_enums(value, found)
    elif isinstance(node, list):
        for value in node:
            collect_string_enums(value, found)


class TestExportJsonSchema:
    def test_dialect_is_2020_12(self, genshin):
        schema = export_json_schema(genshin)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_two_calls_equal(self, genshin):
        assert export_json_schema(genshin) == export_json_schema(genshin)

    def test_all_string_enums_sorted(self, genshin):
        found = []
        collect_string_enums(export_json_schema(genshin), found)
        assert found, "生成物应含字符串枚举"
        for enum in found:
            assert enum == sorted(enum), enum

    def test_loadable_by_draft202012(self, genshin):
        schema = export_json_schema(genshin)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        assert validator.is_valid(make_rule()) is True

    def test_game_const_from_profile(self, genshin, second):
        assert export_json_schema(genshin)["properties"]["game"]["const"] == "genshin"
        assert export_json_schema(second)["properties"]["game"]["const"] == "second_game"

    def test_strategy_enum_from_profile(self, genshin, second):
        assert export_json_schema(genshin)["properties"]["fodder"]["properties"]["strategy"]["enum"] == ["staged_fill"]

    def test_candidates_value_ranges_from_profile(self, genshin):
        rarity_items = export_json_schema(genshin)["properties"]["candidates"]["properties"]["rarity"]["items"]
        assert rarity_items["minimum"] == 1
        assert rarity_items["maximum"] == 5

    def test_top_level_key_set_fixed(self, genshin):
        schema = export_json_schema(genshin)
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {
            "version", "game", "name", "candidates", "rule", "fodder"
        }

    def test_second_game_enums_differ(self, genshin, second):
        """second_game.json 的 stats 与 slots 至少各一处与原神不同，生成物枚举随之不同。"""
        genshin_enums = []
        collect_string_enums(export_json_schema(genshin), genshin_enums)
        second_enums = []
        collect_string_enums(export_json_schema(second), second_enums)
        assert genshin_enums != second_enums
        second_fields = {field for enum in second_enums for field in enum}
        assert "sub.second_stat" in second_fields
        assert "sub.healing_bonus" not in second_fields
        assert "ring" in second_fields
        assert "circlet" not in second_fields


class TestCli:
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "agent.rule_lambda", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_export_success_writes_file(self, tmp_path):
        out = tmp_path / "generated" / "genshin.schema.json"
        result = self.run_cli("export", str(GENSHIN_PROFILE), str(out))
        assert result.returncode == 0, result.stderr
        assert out.is_file()
        assert json.loads(out.read_text(encoding="utf-8"))["$schema"].endswith("2020-12/schema")

    def test_same_profile_two_runs_byte_identical(self, tmp_path):
        out1 = tmp_path / "a.json"
        out2 = tmp_path / "b.json"
        assert self.run_cli("export", str(GENSHIN_PROFILE), str(out1)).returncode == 0
        assert self.run_cli("export", str(GENSHIN_PROFILE), str(out2)).returncode == 0
        assert out1.read_bytes() == out2.read_bytes()

    def test_second_game_export_differs_from_genshin(self, tmp_path):
        out = tmp_path / "second.json"
        assert self.run_cli("export", str(SECOND_PROFILE), str(out)).returncode == 0
        second_schema = json.loads(out.read_text(encoding="utf-8"))
        text = json.dumps(second_schema, ensure_ascii=False)
        assert '"second_game"' in text
        assert "sub.second_stat" in text
        assert "sub.healing_bonus" not in text
        assert '"ring"' in text
        assert '"circlet"' not in text

    def test_missing_profile_fails_nonzero(self, tmp_path):
        out = tmp_path / "x.json"
        result = self.run_cli("export", str(tmp_path / "nope.json"), str(out))
        assert result.returncode != 0
        assert result.stderr.strip()
        assert not out.exists()
