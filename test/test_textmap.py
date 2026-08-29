"""任务 2.1：字段对照文档数据文件与加载校验器的单元测试。"""

import json
from pathlib import Path

import pytest

from agent.rule_lambda.profile import load_profile
from agent.textmap import Textmap, TextmapError, load_textmap

REPO_ROOT = Path(__file__).resolve().parents[1]
GENSHIN_PROFILE = REPO_ROOT / "assets/resource/genshin/profile.json"
GENSHIN_TEXTMAP = REPO_ROOT / "assets/resource/genshin/textmap/zh_cn.json"

# 原神对照文档收录清单，与主设计文档 §4 格式示例一致（词条文字族 16 + 部位 5）
GENSHIN_STAT_TEXTS = {
    "暴击率": "crit_rate",
    "暴击伤害": "crit_dmg",
    "生命值": "hp",
    "攻击力": "atk",
    "防御力": "def",
    "元素精通": "elemental_mastery",
    "元素充能效率": "energy_recharge",
    "治疗加成": "healing_bonus",
    "物理伤害加成": "physical_dmg_bonus",
    "火元素伤害加成": "pyro_dmg_bonus",
    "水元素伤害加成": "hydro_dmg_bonus",
    "雷元素伤害加成": "electro_dmg_bonus",
    "冰元素伤害加成": "cryo_dmg_bonus",
    "风元素伤害加成": "anemo_dmg_bonus",
    "岩元素伤害加成": "geo_dmg_bonus",
    "草元素伤害加成": "dendro_dmg_bonus",
}
GENSHIN_SLOT_TEXTS = {
    "生之花": "flower",
    "死之羽": "plume",
    "时之沙": "sands",
    "空之杯": "goblet",
    "理之冠": "circlet",
}


def make_textmap_dict() -> dict:
    """返回一份合法对照文档字典（与原神文档同构），供非法样例改字段用。"""
    return {
        "version": 1,
        "language": "zh_cn",
        "stats": dict(GENSHIN_STAT_TEXTS),
        "slots": dict(GENSHIN_SLOT_TEXTS),
    }


def write_and_load(tmp_path: Path, data, profile, name="zh_cn.json") -> Textmap:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return load_textmap(path, profile)


class TestLoadRealGenshinTextmap:
    """真文件加载即用；收录内容与主设计文档 §4 定稿一致。"""

    def test_real_file_loads(self):
        profile = load_profile(GENSHIN_PROFILE)
        textmap = load_textmap(GENSHIN_TEXTMAP, profile)
        assert isinstance(textmap, Textmap)

    def test_real_file_fields(self):
        profile = load_profile(GENSHIN_PROFILE)
        textmap = load_textmap(GENSHIN_TEXTMAP, profile)
        assert textmap.language == "zh_cn"
        assert textmap.stats == GENSHIN_STAT_TEXTS
        assert len(textmap.stats) == 16
        assert textmap.slots == GENSHIN_SLOT_TEXTS
        assert len(textmap.slots) == 5

    def test_real_file_codes_within_profile(self):
        profile = load_profile(GENSHIN_PROFILE)
        textmap = load_textmap(GENSHIN_TEXTMAP, profile)
        assert set(textmap.stats.values()) <= profile.stats
        assert set(textmap.slots.values()) <= profile.slots


class TestLoadSyntheticTextmap:
    def test_synthetic_legal_loads(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        textmap = write_and_load(tmp_path, make_textmap_dict(), profile)
        assert textmap.language == "zh_cn"
        assert textmap.stats == GENSHIN_STAT_TEXTS
        assert textmap.slots == GENSHIN_SLOT_TEXTS


class TestLoadTextmapRejections:
    """每类非法对照文档逐类被拒，错误类型为 TextmapError 且带文件路径。"""

    def test_missing_file(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        with pytest.raises(TextmapError) as exc_info:
            load_textmap(tmp_path / "no_such_textmap.json", profile)
        assert exc_info.value.path

    def test_invalid_json(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        path = tmp_path / "zh_cn.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(TextmapError):
            load_textmap(path, profile)

    def test_not_a_dict(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        path = tmp_path / "zh_cn.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(TextmapError):
            load_textmap(path, profile)

    def test_missing_key(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        del data["language"]
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_extra_key(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["game"] = "genshin"
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_version_not_one(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["version"] = 2
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_version_not_int(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["version"] = "1"
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_language_not_str(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["language"] = 123
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_empty_language(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["language"] = ""
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_stats_not_dict(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["stats"] = sorted(GENSHIN_STAT_TEXTS)
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_empty_stats(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["stats"] = {}
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_empty_slots(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["slots"] = {}
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_stats_value_not_str(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["stats"]["暴击率"] = 123
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_stats_value_empty_str(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["stats"]["暴击率"] = ""
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_stats_key_empty_str(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        del data["stats"]["暴击率"]
        data["stats"][""] = "crit_rate"
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_slots_value_not_str(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["slots"]["生之花"] = None
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_stat_code_not_in_profile(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["stats"]["暴击率"] = "crit_rat"
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_slot_code_not_in_profile(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["slots"]["生之花"] = "flowerx"
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_stat_code_is_slot_code(self, tmp_path):
        """stats 节映射到部位代号同样被拒：映射值按所属节核对清单。"""
        profile = load_profile(GENSHIN_PROFILE)
        data = make_textmap_dict()
        data["stats"]["暴击率"] = "flower"
        with pytest.raises(TextmapError):
            write_and_load(tmp_path, data, profile)

    def test_error_message_carries_path(self, tmp_path):
        profile = load_profile(GENSHIN_PROFILE)
        path = tmp_path / "zh_cn.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(TextmapError) as exc_info:
            load_textmap(path, profile)
        assert exc_info.value.path == str(path)
        assert str(path) in str(exc_info.value)
