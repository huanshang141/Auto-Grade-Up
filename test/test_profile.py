"""任务 2.2：游戏档案加载、档案校验与圣遗物值域校验的单元测试。"""

import json
from pathlib import Path

import pytest

from agent.rule_lambda.model import Artifact, StatValue
from agent.rule_lambda.profile import (
    ArtifactValidationError,
    GameProfile,
    ProfileError,
    load_profile,
    validate_artifact,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GENSHIN_PROFILE = REPO_ROOT / "assets/resource/genshin/profile.json"

# 原神档案清单，与 rule-file-format 契约的代号清单节一致
GENSHIN_STATS = {
    "crit_rate", "crit_dmg",
    "hp", "hp_percent",
    "atk", "atk_percent",
    "def", "def_percent",
    "elemental_mastery",
    "energy_recharge",
    "healing_bonus",
    "physical_dmg_bonus",
    "pyro_dmg_bonus", "hydro_dmg_bonus", "electro_dmg_bonus",
    "cryo_dmg_bonus", "anemo_dmg_bonus", "geo_dmg_bonus", "dendro_dmg_bonus",
}
GENSHIN_SLOTS = {"flower", "plume", "sands", "goblet", "circlet"}


def make_profile_dict() -> dict:
    """返回一份合法档案字典（与原神档案同构），供非法样例改字段用。"""
    return {
        "version": 1,
        "game": "genshin",
        "display_name": "原神",
        "stats": sorted(GENSHIN_STATS),
        "slots": sorted(GENSHIN_SLOTS),
        "max_level": 20,
        "roll_interval": 4,
        "rarity_range": [1, 5],
        "substat_max": 4,
        "round_mechanism": "staged_fill",
        "roll_growth_max": make_growth_table(),
    }


def make_growth_table() -> dict:
    """合法的成长上限表（与原神档案同构的 4/5 星全 10 个副词条代号）。"""
    values = {
        "hp": 299, "atk": 19, "def": 23,
        "hp_percent": 5.8, "atk_percent": 5.8, "def_percent": 7.3,
        "elemental_mastery": 23, "energy_recharge": 6.5,
        "crit_rate": 3.9, "crit_dmg": 7.8,
    }
    four_star = {
        "hp": 239, "atk": 16, "def": 19,
        "hp_percent": 4.7, "atk_percent": 4.7, "def_percent": 5.8,
        "elemental_mastery": 19, "energy_recharge": 5.2,
        "crit_rate": 3.1, "crit_dmg": 6.2,
    }
    return {"5": values, "4": four_star}


def write_and_load(tmp_path: Path, data, name="profile.json") -> GameProfile:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return load_profile(path)


def make_artifact(**overrides) -> Artifact:
    """构造一件值域合法的原神圣遗物，可按字段覆盖。"""
    base = dict(
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
    base.update(overrides)
    return Artifact(**base)


class TestLoadRealGenshinProfile:
    def test_real_file_loads(self):
        profile = load_profile(GENSHIN_PROFILE)
        assert isinstance(profile, GameProfile)

    def test_real_file_fields(self):
        profile = load_profile(GENSHIN_PROFILE)
        assert profile.version == 1
        assert profile.game == "genshin"
        assert profile.display_name == "原神"
        assert profile.stats == frozenset(GENSHIN_STATS)
        assert len(profile.stats) == 19
        assert profile.slots == frozenset(GENSHIN_SLOTS)
        assert len(profile.slots) == 5
        assert profile.max_level == 20
        assert profile.roll_interval == 4
        assert profile.rarity_min == 1
        assert profile.rarity_max == 5
        assert profile.substat_max == 4
        assert profile.round_mechanism == "staged_fill"

    def test_real_profile_source_path_recorded(self):
        profile = load_profile(GENSHIN_PROFILE)
        assert profile.source_path.endswith("profile.json")

    def test_real_growth_table_covers_both_rarities(self):
        """4/5 星全 10 个副词条代号有表；治疗加成与七种伤害加成只作主词条、不进副词条池，无表数据。"""
        profile = load_profile(GENSHIN_PROFILE)
        assert set(profile.roll_growth_max) == {4, 5}
        substat_pool = {
            "hp", "atk", "def", "hp_percent", "atk_percent", "def_percent",
            "elemental_mastery", "energy_recharge", "crit_rate", "crit_dmg",
        }
        assert set(profile.roll_growth_max[5]) == substat_pool
        assert set(profile.roll_growth_max[4]) == substat_pool

    def test_real_growth_max_queries(self):
        profile = load_profile(GENSHIN_PROFILE)
        assert profile.growth_max(5, "crit_rate") == 3.9
        assert profile.growth_max(5, "crit_dmg") == 7.8
        assert profile.growth_max(4, "crit_dmg") == 6.2
        assert profile.growth_max(4, "hp") == 239.0

    def test_growth_max_missing_rarity_raises_with_star_and_code(self):
        profile = load_profile(GENSHIN_PROFILE)
        with pytest.raises(ProfileError) as exc_info:
            profile.growth_max(3, "crit_rate")
        assert "3" in exc_info.value.message and "crit_rate" in exc_info.value.message
        assert exc_info.value.path.endswith("profile.json")

    def test_growth_max_missing_code_raises(self):
        """主词条专属代号（如治疗加成）在档案 stats 内但无副词条成长数据，查表抛错。"""
        profile = load_profile(GENSHIN_PROFILE)
        with pytest.raises(ProfileError) as exc_info:
            profile.growth_max(5, "healing_bonus")
        assert "healing_bonus" in exc_info.value.message

    def test_real_profile_accepts_legal_artifact(self):
        profile = load_profile(GENSHIN_PROFILE)
        assert validate_artifact(make_artifact(), profile) is None


class TestLoadProfileRejections:
    """每类非法档案逐类被拒，错误类型为 ProfileError 且带档案路径。"""

    def test_missing_file(self, tmp_path):
        with pytest.raises(ProfileError) as exc_info:
            load_profile(tmp_path / "no_such_profile.json")
        assert exc_info.value.path

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(ProfileError):
            load_profile(path)

    def test_not_a_dict(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(ProfileError):
            load_profile(path)

    def test_missing_key(self, tmp_path):
        data = make_profile_dict()
        del data["max_level"]
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_extra_key(self, tmp_path):
        data = make_profile_dict()
        data["rarity"] = 5
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_version_not_one(self, tmp_path):
        data = make_profile_dict()
        data["version"] = 2
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_version_not_int(self, tmp_path):
        data = make_profile_dict()
        data["version"] = "1"
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_empty_game(self, tmp_path):
        data = make_profile_dict()
        data["game"] = ""
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_empty_stats(self, tmp_path):
        data = make_profile_dict()
        data["stats"] = []
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_stats_element_not_str(self, tmp_path):
        data = make_profile_dict()
        data["stats"] = sorted(GENSHIN_STATS)[:3] + [42]
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_empty_slots(self, tmp_path):
        data = make_profile_dict()
        data["slots"] = []
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_max_level_not_int(self, tmp_path):
        data = make_profile_dict()
        data["max_level"] = "20"
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_roll_interval_zero(self, tmp_path):
        data = make_profile_dict()
        data["roll_interval"] = 0
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_substat_max_negative(self, tmp_path):
        data = make_profile_dict()
        data["substat_max"] = -1
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    @pytest.mark.parametrize(
        "rarity_range",
        [[5, 1], [1], [1, 2, 3], ["1", "5"], [1.5, 5], [3, 3]],
    )
    def test_illegal_rarity_range(self, tmp_path, rarity_range):
        data = make_profile_dict()
        data["rarity_range"] = rarity_range
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_duplicate_stats_codes(self, tmp_path):
        data = make_profile_dict()
        data["stats"] = ["hp", "hp", "atk"]
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_duplicate_slots_codes(self, tmp_path):
        data = make_profile_dict()
        data["slots"] = ["flower", "flower"]
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_unknown_round_mechanism(self, tmp_path):
        data = make_profile_dict()
        data["round_mechanism"] = "per_roll"
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)


class TestGrowthTableRejections:
    """成长上限表逐类非法样例被拒：星级键、属性代号、数值三道关。"""

    @pytest.mark.parametrize("star_key", ["6", "0", "five", "5.0", "", " "])
    def test_illegal_star_key(self, tmp_path, star_key):
        data = make_profile_dict()
        table = make_growth_table()
        table[star_key] = table.pop("5")
        data["roll_growth_max"] = table
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_star_key_out_of_range_message(self, tmp_path):
        data = make_profile_dict()
        data["roll_growth_max"] = {"6": {"crit_rate": 3.9}}
        path = tmp_path / "profile.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ProfileError) as exc_info:
            load_profile(path)
        assert "星级范围" in exc_info.value.message

    def test_table_not_a_dict(self, tmp_path):
        data = make_profile_dict()
        data["roll_growth_max"] = [["5", "crit_rate"]]
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_row_not_a_dict(self, tmp_path):
        data = make_profile_dict()
        data["roll_growth_max"] = {"5": 3.9}
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_code_not_in_stats(self, tmp_path):
        data = make_profile_dict()
        data["roll_growth_max"] = {"5": {"mana": 10}}
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    @pytest.mark.parametrize("value", [0, -3.9, "3.9", True, None])
    def test_non_positive_or_non_numeric_value(self, tmp_path, value):
        data = make_profile_dict()
        data["roll_growth_max"] = {"5": {"crit_rate": value}}
        with pytest.raises(ProfileError):
            write_and_load(tmp_path, data)

    def test_partial_star_coverage_legal(self, tmp_path):
        """允许不覆盖全部星级（缺表在查表时抛错，档案加载不拦）。"""
        data = make_profile_dict()
        data["roll_growth_max"] = {"5": {"crit_rate": 3.9}}
        profile = write_and_load(tmp_path, data)
        assert profile.growth_max(5, "crit_rate") == 3.9
        with pytest.raises(ProfileError):
            profile.growth_max(4, "crit_rate")


class TestValidateArtifact:
    """值域校验：越界等级、越界星级、未知部位、超限副词条逐类被拒，边界值放行。"""

    @pytest.fixture()
    def profile(self) -> GameProfile:
        return load_profile(GENSHIN_PROFILE)

    def test_legal(self, profile):
        assert validate_artifact(make_artifact(), profile) is None

    @pytest.mark.parametrize("level", [0, 20])
    def test_level_boundary_pass(self, profile, level):
        assert validate_artifact(make_artifact(level=level), profile) is None

    @pytest.mark.parametrize("level", [-1, 21])
    def test_level_out_of_range(self, profile, level):
        with pytest.raises(ArtifactValidationError):
            validate_artifact(make_artifact(level=level), profile)

    @pytest.mark.parametrize("rarity", [1, 5])
    def test_rarity_boundary_pass(self, profile, rarity):
        assert validate_artifact(make_artifact(rarity=rarity), profile) is None

    @pytest.mark.parametrize("rarity", [0, 6])
    def test_rarity_out_of_range(self, profile, rarity):
        with pytest.raises(ArtifactValidationError):
            validate_artifact(make_artifact(rarity=rarity), profile)

    def test_unknown_slot(self, profile):
        with pytest.raises(ArtifactValidationError):
            validate_artifact(make_artifact(slot="rings"), profile)

    def test_substat_max_boundary_pass(self, profile):
        substats = [StatValue(name="crit_rate", value=5.8) for _ in range(4)]
        assert validate_artifact(make_artifact(substats=substats), profile) is None

    def test_too_many_substats(self, profile):
        substats = [StatValue(name="crit_rate", value=5.8) for _ in range(5)]
        with pytest.raises(ArtifactValidationError):
            validate_artifact(make_artifact(substats=substats), profile)


class TestRollCountValueDomain:
    """词条强化次数值域（M2.5）：[0, ⌈max_level ÷ roll_interval⌉]（原神 5），
    待激活词条不得携带正次数；null 与边界值放行。"""

    @pytest.fixture()
    def profile(self) -> GameProfile:
        return load_profile(GENSHIN_PROFILE)

    @pytest.mark.parametrize("roll_count", [None, 0, 5])
    def test_roll_count_boundary_pass(self, profile, roll_count):
        substats = [StatValue(name="crit_rate", value=5.8, roll_count=roll_count)]
        assert validate_artifact(make_artifact(substats=substats), profile) is None

    @pytest.mark.parametrize("roll_count", [-1, 6])
    def test_roll_count_out_of_range(self, profile, roll_count):
        substats = [StatValue(name="crit_rate", value=5.8, roll_count=roll_count)]
        with pytest.raises(ArtifactValidationError):
            validate_artifact(make_artifact(substats=substats), profile)

    @pytest.mark.parametrize("roll_count", [None, 0])
    def test_pending_with_zero_or_null_passes(self, profile, roll_count):
        substats = [StatValue(name="hp", value=269.0, roll_count=roll_count, pending=True)]
        assert validate_artifact(make_artifact(substats=substats), profile) is None

    def test_pending_with_positive_count_rejected(self, profile):
        substats = [StatValue(name="hp", value=269.0, roll_count=2, pending=True)]
        with pytest.raises(ArtifactValidationError) as exc_info:
            validate_artifact(make_artifact(substats=substats), profile)
        assert "待激活" in exc_info.value.args[0]
