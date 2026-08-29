"""任务 2.1：StatValue/Artifact 数据模型与 OCR 文本解析的单元测试。"""

import json

import pytest

from agent.rule_lambda.model import (
    Artifact,
    StatValue,
    parse_level,
    parse_stat_value,
    strip_spaces,
)


def make_artifact() -> Artifact:
    """构造 spec §3 示例同形的圣遗物。"""
    return Artifact(
        slot="sands",
        rarity=5,
        set="辰砂往生录",
        level=4,
        locked=False,
        main=StatValue(name="atk_percent", value=31.5),
        substats=[
            StatValue(name="crit_rate", value=5.8),
            StatValue(name="atk", value=117.0),
        ],
    )


class TestRoundtrip:
    def test_to_dict_matches_spec_example_keys(self):
        expected = {
            "slot": "sands",
            "rarity": 5,
            "set": "辰砂往生录",
            "level": 4,
            "locked": False,
            "main": {"name": "atk_percent", "value": 31.5},
            "substats": [
                {"name": "crit_rate", "value": 5.8},
                {"name": "atk", "value": 117.0},
            ],
        }
        assert make_artifact().to_dict() == expected

    def test_roundtrip_equal(self):
        artifact = make_artifact()
        assert Artifact.from_dict(artifact.to_dict()) == artifact

    def test_roundtrip_via_json_lossless(self):
        artifact = make_artifact()
        loaded = json.loads(json.dumps(artifact.to_dict()))
        assert Artifact.from_dict(loaded) == artifact

    def test_from_dict_coerces_int_value_to_float(self):
        artifact = Artifact.from_dict(make_artifact().to_dict())
        assert artifact.main.value == 31.5
        assert isinstance(artifact.main.value, float)
        assert all(isinstance(s.value, float) for s in artifact.substats)


class TestParseStatValue:
    def test_percent(self):
        assert parse_stat_value("5.8%") == (5.8, True)

    def test_plain(self):
        assert parse_stat_value("117") == (117.0, False)

    def test_whitespace_stripped_first(self):
        assert parse_stat_value(" 5.8 % ") == (5.8, True)
        assert parse_stat_value("\u3000117\u3000") == (117.0, False)

    def test_zero(self):
        assert parse_stat_value("0") == (0.0, False)

    @pytest.mark.parametrize(
        "text",
        ["", "   ", "%", "5.8%%", "abc", "5.8 percent", "nan", "inf", "-inf",
         "1_9", "１９", "5.8％", "e5", "0x10"],
    )
    def test_invalid_raises_value_error(self, text):
        with pytest.raises(ValueError):
            parse_stat_value(text)


class TestParseLevel:
    def test_plus_prefix(self):
        assert parse_level("+19") == 19

    def test_zero(self):
        assert parse_level("0") == 0

    def test_whitespace_stripped_first(self):
        assert parse_level(" +4 ") == 4
        assert parse_level("+ 19") == 19

    @pytest.mark.parametrize(
        "text", ["", "abc", "19.5", "++1", "1_9", "１９", "inf", "+ 19e2"]
    )
    def test_invalid_raises_value_error(self, text):
        with pytest.raises(ValueError):
            parse_level(text)


class TestStripSpaces:
    def test_no_whitespace_unchanged(self):
        assert strip_spaces("辰砂往生录") == "辰砂往生录"

    def test_removes_all_whitespace(self):
        assert strip_spaces(" 辰砂 往生录 ") == "辰砂往生录"
        assert strip_spaces("atk\tvalue\n") == "atkvalue"

    def test_full_width_space(self):
        assert strip_spaces("\u3000atk\u3000") == "atk"


class TestFromDictShapeValidation:
    """本任务只做形状校验（键名、字段类型、列表结构）；值域校验归任务 2.2。"""

    def test_not_a_dict(self):
        with pytest.raises(ValueError):
            Artifact.from_dict(["slot"])

    def test_missing_key(self):
        data = make_artifact().to_dict()
        del data["locked"]
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_extra_key(self):
        data = make_artifact().to_dict()
        data["percent"] = True
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_rarity_must_be_int(self):
        data = make_artifact().to_dict()
        data["rarity"] = "5"
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_rarity_must_not_be_bool(self):
        data = make_artifact().to_dict()
        data["rarity"] = True
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_level_must_be_int(self):
        data = make_artifact().to_dict()
        data["level"] = 4.0
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_locked_must_be_bool(self):
        data = make_artifact().to_dict()
        data["locked"] = 1
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_slot_must_be_str(self):
        data = make_artifact().to_dict()
        data["slot"] = 3
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_main_wrong_keys(self):
        data = make_artifact().to_dict()
        data["main"] = {"name": "atk_percent"}
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_main_value_must_be_number(self):
        data = make_artifact().to_dict()
        data["main"] = {"name": "atk_percent", "value": "31.5"}
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_substats_must_be_list(self):
        data = make_artifact().to_dict()
        data["substats"] = {"name": "atk", "value": 117}
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_substat_item_wrong_keys(self):
        data = make_artifact().to_dict()
        data["substats"] = [{"name": "atk", "percent": False}]
        with pytest.raises(ValueError):
            Artifact.from_dict(data)

    def test_substat_name_must_be_str(self):
        data = make_artifact().to_dict()
        data["substats"] = [{"name": 1, "value": 117}]
        with pytest.raises(ValueError):
            Artifact.from_dict(data)
