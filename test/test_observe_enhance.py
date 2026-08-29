"""任务 3.3：强化页读取器的单元测试（内联构造识别结果集样例）。"""

import copy

from agent.observe import CarriedFields, read_enhance
from agent.rule_lambda.model import StatValue
from agent.rule_lambda.profile import load_profile
from agent.textmap import Textmap

GENSHIN_PROFILE = load_profile("assets/resource/genshin/profile.json")

# 与真实对照文档一致的收录清单（原神），供构造识别结果集与断言
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
TEXTMAP = Textmap(language="zh_cn", stats=dict(GENSHIN_STAT_TEXTS), slots=dict(GENSHIN_SLOT_TEXTS))

CARRIED = CarriedFields(rarity=5, set="辰砂往生录", locked=False)


def make_box(text, score=0.99, box=None):
    return {"box": box or [0, 0, 100, 20], "text": text, "score": score}


def make_enhance_recognition():
    """一份合法的强化页识别结果集：5 星 +19、4 条副词条（名左值右同行格式）。"""
    return {
        "breadcrumb": [make_box("时之沙 / 星落湖之心", 0.97)],
        "main": [make_box("攻击力 31.5%", 0.95)],
        "level": [make_box("+19", 0.94)],
        "exp": [make_box("2900/35575", 0.93)],
        "substats": [
            make_box("暴击率 5.8%", 0.92, box=[800, 210, 200, 20]),
            make_box("攻击力 117", 0.91, box=[800, 245, 200, 20]),
            make_box("元素精通 23", 0.90, box=[800, 281, 200, 20]),
            make_box("暴击伤害 12.4%", 0.89, box=[800, 316, 200, 20]),
        ],
        "mora": [make_box("20000", 0.88)],
        "fodder_tier": [make_box("4星及以下素材", 0.87)],
    }


class TestReadEnhanceHappyPath:
    def test_valid_recognition_returns_artifact_with_carried_fields(self):
        result = read_enhance(make_enhance_recognition(), CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.failures == []
        assert result.warnings == []
        artifact = result.artifact
        assert artifact.slot == "sands"
        assert artifact.rarity == 5
        assert artifact.set == "辰砂往生录"
        assert artifact.locked is False
        assert artifact.level == 19
        assert artifact.main == StatValue(name="atk_percent", value=31.5)
        assert artifact.substats == [
            StatValue(name="crit_rate", value=5.8),
            StatValue(name="atk", value=117.0),
            StatValue(name="elemental_mastery", value=23.0),
            StatValue(name="crit_dmg", value=12.4),
        ]

    def test_extras_hold_auxiliary_readings_and_fingerprint(self):
        result = read_enhance(make_enhance_recognition(), CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.extras == {
            "exp": "2900/35575",
            "mora": "20000",
            "fodder_tier": "4星及以下素材",
            "fingerprint": {"slot": "sands", "name": "星落湖之心"},
        }

    def test_optional_regions_absent_still_ok(self):
        """exp/mora/fodder_tier 非必要区域：缺失时 extras 只缺对应键，读取成功。"""
        recognition = make_enhance_recognition()
        del recognition["exp"], recognition["mora"], recognition["fodder_tier"]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.extras == {"fingerprint": {"slot": "sands", "name": "星落湖之心"}}

    def test_fingerprint_slot_is_adapted_code(self):
        recognition = make_enhance_recognition()
        recognition["breadcrumb"] = [make_box("理之冠 / 另一件圣遗物")]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.extras["fingerprint"] == {"slot": "circlet", "name": "另一件圣遗物"}
        assert result.artifact.slot == "circlet"

    def test_confidences_are_min_scores_of_used_boxes(self):
        result = read_enhance(make_enhance_recognition(), CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.confidences == {
            "breadcrumb": 0.97,
            "main": 0.95,
            "level": 0.94,
            "exp": 0.93,
            "substats": 0.89,
            "mora": 0.88,
            "fodder_tier": 0.87,
        }

    def test_stateless_and_input_untouched(self):
        recognition = make_enhance_recognition()
        snapshot = copy.deepcopy(recognition)
        first = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        second = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert first == second
        assert recognition == snapshot


class TestReadEnhanceRowRules:
    def test_pending_row_dropped_entirely(self):
        """「待激活」预览行整行丢弃（与列表页同规则）。"""
        recognition = make_enhance_recognition()
        recognition["level"] = [make_box("+0", 0.94)]
        recognition["substats"] = [
            make_box("暴击率 5.8%", box=[800, 210, 200, 20]),
            make_box("攻击力 117", box=[800, 245, 200, 20]),
            make_box("元素精通 23", box=[800, 281, 200, 20]),
            make_box("暴击伤害 15.5%（待激活）", box=[800, 316, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert len(result.artifact.substats) == 3
        assert result.warnings == []

    def test_roll_marker_stripped_from_row_tail(self):
        """强化次数标记不参与解析：行尾的 ① 去除后正常切分。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率 5.8% ①", box=[800, 210, 200, 20]),
            make_box("攻击力 117 ②", box=[800, 245, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=5.8),
            StatValue(name="atk", value=117.0),
        ]

    def test_row_reconstructed_from_split_boxes(self):
        """真实行形态：名、值、强化次数标记各为一个文字框，同行按横序拼接后解析。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("①", 0.9, box=[780, 210, 16, 18]),
            make_box("暴击率", 0.9, box=[800, 210, 60, 18]),
            make_box("3.1%", 0.9, box=[1210, 210, 50, 18]),
            make_box("②", 0.9, box=[780, 245, 16, 18]),
            make_box("攻击力", 0.9, box=[800, 245, 60, 18]),
            make_box("12.8%", 0.9, box=[1210, 245, 50, 18]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=3.1),
            StatValue(name="atk_percent", value=12.8),
        ]

    def test_marker_only_box_dropped(self):
        """标记独占文字框（OCR 把 ① 单成一行）整行忽略，不算行数也不算解析失败。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率 5.8%", box=[800, 210, 200, 20]),
            make_box("①", box=[780, 210, 16, 18]),
            make_box("攻击力 117", box=[800, 245, 200, 20]),
            make_box("元素精通 23", box=[800, 281, 200, 20]),
            make_box("暴击伤害 12.4%", box=[800, 316, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert len(result.artifact.substats) == 4
        assert result.warnings == []


class TestReadEnhanceFailures:
    def test_missing_required_region(self):
        recognition = make_enhance_recognition()
        del recognition["breadcrumb"]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any("breadcrumb" in f for f in result.failures)

    def test_unparsable_level(self):
        recognition = make_enhance_recognition()
        recognition["level"] = [make_box("＋19")]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("等级" in f for f in result.failures)

    def test_unparsable_main_value(self):
        recognition = make_enhance_recognition()
        recognition["main"] = [make_box("攻击力 ＋３１")]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("主词条" in f for f in result.failures)

    def test_substat_count_over_max(self):
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率 5.8%", box=[800, 210, 200, 20]),
            make_box("攻击力 117", box=[800, 245, 200, 20]),
            make_box("元素精通 23", box=[800, 281, 200, 20]),
            make_box("暴击伤害 12.4%", box=[800, 316, 200, 20]),
            make_box("生命值 738", box=[800, 351, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("上限" in f for f in result.failures)

    def test_duplicate_code_fails(self):
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率 5.8%", box=[800, 210, 200, 20]),
            make_box("暴击率 6.6%", box=[800, 245, 200, 20]),
            make_box("攻击力 117", box=[800, 281, 200, 20]),
            make_box("元素精通 23", box=[800, 316, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("重复" in f and "crit_rate" in f for f in result.failures)

    def test_uncollected_breadcrumb_slot_fails(self):
        recognition = make_enhance_recognition()
        recognition["breadcrumb"] = [make_box("时之沙x / 星落湖之心")]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any("部位" in f for f in result.failures)

    def test_breadcrumb_without_separator_fails(self):
        recognition = make_enhance_recognition()
        recognition["breadcrumb"] = [make_box("时之沙 星落湖之心")]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("面包屑" in f for f in result.failures)

    def test_uncollected_substat_name_warns_but_reads(self):
        recognition = make_enhance_recognition()
        recognition["substats"] = [make_box("歪词条 23")] + recognition["substats"][1:]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0] == StatValue(name="歪词条", value=23.0)
        assert any("歪词条" in w for w in result.warnings)
