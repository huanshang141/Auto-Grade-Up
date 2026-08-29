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
    }


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
