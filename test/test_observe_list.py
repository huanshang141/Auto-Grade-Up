"""任务 3.2：列表页读取器的单元测试（内联构造识别结果集样例）。"""

import copy

from agent.observe import read_list
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


def make_box(text, score=0.99, box=None):
    return {"box": box or [0, 0, 100, 20], "text": text, "score": score}


def make_list_recognition():
    """一份合法的列表页识别结果集：5 星 +19、4 条副词条、未锁定。"""
    return {
        "name": [make_box("星落湖之心", 0.97)],
        "slot": [make_box("时之沙", 0.96)],
        "main": [make_box("攻击力 31.5%", 0.95)],
        "level": [make_box("+19", 0.94)],
        "substats": [
            make_box("暴击率+5.8%", 0.93, box=[898, 320, 200, 20]),
            make_box("攻击力+117", 0.92, box=[898, 345, 200, 20]),
            make_box("元素精通+23", 0.91, box=[898, 370, 200, 20]),
            make_box("暴击伤害+12.4%", 0.90, box=[898, 395, 200, 20]),
        ],
        "set": [make_box("辰砂往生录：", 0.89)],
        "stars": [make_box("", 0.88) for _ in range(5)],
        "lock": [],
    }


class TestReadListHappyPath:
    def test_valid_recognition_returns_artifact(self):
        result = read_list(make_list_recognition(), GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.failures == []
        assert result.warnings == []
        assert result.extras == {}
        artifact = result.artifact
        assert artifact.slot == "sands"
        assert artifact.rarity == 5
        assert artifact.set == "辰砂往生录"
        assert artifact.level == 19
        assert artifact.locked is False
        assert artifact.main == StatValue(name="atk_percent", value=31.5)
        assert artifact.substats == [
            StatValue(name="crit_rate", value=5.8),
            StatValue(name="atk", value=117.0),
            StatValue(name="elemental_mastery", value=23.0),
            StatValue(name="crit_dmg", value=12.4),
        ]

    def test_set_name_trailing_colon_stripped(self):
        """套装名行显示带冒号（如「辰砂往生录：」），入模为套装名本身。"""
        result = read_list(make_list_recognition(), GENSHIN_PROFILE, TEXTMAP)
        assert result.artifact.set == "辰砂往生录"

    def test_rarity_counts_star_hits(self):
        recognition = make_list_recognition()
        recognition["stars"] = [make_box("", 0.9) for _ in range(4)]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.artifact.rarity == 4

    def test_lock_hit_sets_locked(self):
        recognition = make_list_recognition()
        recognition["lock"] = [make_box("", 0.95)]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.artifact.locked is True

    def test_confidences_are_min_scores_of_used_boxes(self):
        result = read_list(make_list_recognition(), GENSHIN_PROFILE, TEXTMAP)
        assert result.confidences == {
            "name": 0.97,
            "slot": 0.96,
            "main": 0.95,
            "level": 0.94,
            "substats": 0.90,
            "set": 0.89,
            "stars": 0.88,
        }

    def test_stateless_and_input_untouched(self):
        recognition = make_list_recognition()
        snapshot = copy.deepcopy(recognition)
        first = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        second = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert first == second
        assert recognition == snapshot


class TestReadListPendingActivationRow:
    def test_pending_row_enters_model(self):
        """待激活预览行入模（M2.5）：pending=True、预览值入模、次数恒未知；
        不计入已解锁条数（5 星 +0 解锁 3 条，合法 3~4 条无警告）。"""
        recognition = make_list_recognition()
        recognition["level"] = [make_box("+0", 0.94)]
        recognition["substats"] = [
            make_box("暴击率+5.8%", box=[898, 320, 200, 20]),
            make_box("攻击力+117", box=[898, 345, 200, 20]),
            make_box("元素精通+23", box=[898, 370, 200, 20]),
            make_box("暴击伤害+15.5%（待激活）", box=[898, 395, 200, 20]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.failures == []
        assert result.warnings == []
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=5.8),
            StatValue(name="atk", value=117.0),
            StatValue(name="elemental_mastery", value=23.0),
            StatValue(name="crit_dmg", value=15.5, roll_count=None, pending=True),
        ]

    def test_list_roll_count_always_none(self):
        """列表页不显示带圈数字：roll_count 恒 None（未知，与 0 是两种状态）。"""
        recognition = make_list_recognition()
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert all(s.roll_count is None and s.pending is False for s in result.artifact.substats)


class TestReadListWarnings:
    def test_uncollected_substat_name_stored_as_original(self):
        recognition = make_list_recognition()
        recognition["substats"] = [make_box("歪词条+23")] + recognition["substats"][1:]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0] == StatValue(name="歪词条", value=23.0)
        assert any("歪词条" in w for w in result.warnings)

    def test_uncollected_main_name_stored_as_original(self):
        recognition = make_list_recognition()
        recognition["main"] = [make_box("歪词条 31.5%")]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.main == StatValue(name="歪词条", value=31.5)
        assert any("歪词条" in w for w in result.warnings)

    def test_count_below_expectation_warns(self):
        """5 星 +19 合法行数为 4 条，3 条提示不一致。"""
        recognition = make_list_recognition()
        recognition["substats"] = recognition["substats"][:3]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert any("不一致" in w for w in result.warnings)

    def test_four_star_count_grows_with_level(self):
        """4 星 +8 合法行数为 4 条（+0 为 2 条、此后每经一个变动点解锁一条）。"""
        recognition = make_list_recognition()
        recognition["stars"] = [make_box("", 0.9) for _ in range(4)]
        recognition["level"] = [make_box("+8", 0.94)]
        recognition["substats"] = recognition["substats"][:3]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert any("不一致" in w for w in result.warnings)

    def test_four_star_plus_zero_two_substats_legal(self):
        recognition = make_list_recognition()
        recognition["stars"] = [make_box("", 0.9) for _ in range(4)]
        recognition["level"] = [make_box("+0", 0.94)]
        recognition["substats"] = recognition["substats"][:2]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.warnings == []

    def test_low_rarity_has_no_expectation(self):
        """低稀有度的合法形态未定（补拍未覆盖），不做行数提示。"""
        recognition = make_list_recognition()
        recognition["stars"] = [make_box("", 0.9)]
        recognition["level"] = [make_box("+0", 0.94)]
        recognition["substats"] = recognition["substats"][:2]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.warnings == []


class TestReadListMultiBoxRows:
    """真实界面里名与值常各成一个文字框：按纵坐标聚行、按阅读序拼接。"""

    def test_main_stacked_two_lines(self):
        """列表页主词条名在上、值在下（两行两框）。"""
        recognition = make_list_recognition()
        recognition["main"] = [
            make_box("攻击力", 0.95, box=[887, 180, 50, 20]),
            make_box("298", 0.95, box=[887, 200, 60, 30]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.main == StatValue(name="atk", value=298.0)

    def test_substat_name_value_split_boxes(self):
        recognition = make_list_recognition()
        recognition["substats"] = [
            make_box("暴击率", 0.9, box=[900, 320, 60, 16]),
            make_box("+3.1%", 0.9, box=[1100, 320, 60, 16]),
            make_box("攻击力", 0.9, box=[900, 345, 60, 16]),
            make_box("+117", 0.9, box=[1100, 345, 60, 16]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=3.1),
            StatValue(name="atk", value=117.0),
        ]


    def test_set_name_picked_from_topmost_row(self):
        """套装块可能残留纯中文的效果换行（expected 正则滤不掉），最上一行为套装名。"""
        recognition = make_list_recognition()
        recognition["set"] = [
            make_box("中附近的所有角色攻击力", 1.0, box=[905, 443, 176, 16]),
            make_box("千岩牢固:", 0.91, box=[888, 371, 73, 17]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.artifact.set == "千岩牢固"
        assert result.confidences["set"] == 0.91


class TestReadListFailures:
    def test_missing_required_region(self):
        recognition = make_list_recognition()
        del recognition["name"]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any("name" in f for f in result.failures)

    def test_blank_region_counts_as_empty(self):
        recognition = make_list_recognition()
        recognition["set"] = [make_box("   ")]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("set" in f for f in result.failures)

    def test_multiple_missing_regions_listed(self):
        recognition = make_list_recognition()
        del recognition["name"]
        del recognition["slot"]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert len([f for f in result.failures if "必要区域" in f]) == 2

    def test_unparsable_main_value(self):
        recognition = make_list_recognition()
        recognition["main"] = [make_box("攻击力＋３１")]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any("主词条" in f for f in result.failures)

    def test_unparsable_level(self):
        recognition = make_list_recognition()
        recognition["level"] = [make_box("＋19")]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("等级" in f for f in result.failures)

    def test_unparsable_substat_row(self):
        recognition = make_list_recognition()
        recognition["substats"] = [make_box("暴击率+")] + recognition["substats"][1:]
        recognition["substats"][0]["box"] = [898, 320, 200, 20]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("副词条" in f for f in result.failures)

    def test_substat_count_over_max(self):
        recognition = make_list_recognition()
        recognition["substats"] = [
            make_box("暴击率+5.8%", box=[898, 320, 200, 20]),
            make_box("攻击力+117", box=[898, 345, 200, 20]),
            make_box("元素精通+23", box=[898, 370, 200, 20]),
            make_box("暴击伤害+12.4%", box=[898, 395, 200, 20]),
            make_box("生命值+738", box=[898, 420, 200, 20]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("上限" in f for f in result.failures)

    def test_duplicate_code_fails(self):
        recognition = make_list_recognition()
        recognition["substats"] = [
            make_box("暴击率+5.8%", box=[898, 320, 200, 20]),
            make_box("暴击率+6.6%", box=[898, 345, 200, 20]),
            make_box("攻击力+117", box=[898, 370, 200, 20]),
            make_box("元素精通+23", box=[898, 395, 200, 20]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("重复" in f and "crit_rate" in f for f in result.failures)

    def test_same_family_flat_and_percent_coexist(self):
        """同文字族的固定值与百分比是两个代号，并存合法（2026-08-29 补拍核验）。"""
        recognition = make_list_recognition()
        recognition["substats"] = [
            make_box("攻击力+5.8%", box=[898, 320, 200, 20]),
            make_box("攻击力+19", box=[898, 345, 200, 20]),
            make_box("暴击率+3.1", box=[898, 370, 200, 20]),
            make_box("暴击伤害+12.4%", box=[898, 395, 200, 20]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.failures == []

    def test_uncollected_slot_name_fails(self):
        recognition = make_list_recognition()
        recognition["slot"] = [make_box("时之沙x")]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any("部位" in f for f in result.failures)


class TestReadListRejectsSettlementRow:
    """列表页不存在成长结算形态（契约：仅强化页出现）——OCR 异常导致的双
    数值行按读取失败处理，不静默取值（2026-08-29 补强定案）。"""

    def test_double_value_row_fails_in_list_reader(self):
        recognition = make_list_recognition()
        recognition["substats"] = [
            make_box("防御力", box=[898, 320, 60, 20]),
            make_box("5.8%", box=[960, 320, 50, 20]),
            make_box("11.1%", box=[1010, 320, 50, 20]),
        ]
        result = read_list(recognition, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any("副词条" in f for f in result.failures)
