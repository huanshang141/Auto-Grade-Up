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
            StatValue(name="crit_rate", value=5.8, roll_count=0),
            StatValue(name="atk", value=117.0, roll_count=0),
            StatValue(name="elemental_mastery", value=23.0, roll_count=0),
            StatValue(name="crit_dmg", value=12.4, roll_count=0),
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

    def test_main_same_row_boxes_ordered_left_to_right(self):
        """同行名值两框顶略有高低（值框更高）也按横序拼接，不按纵序颠倒。"""
        recognition = make_enhance_recognition()
        recognition["main"] = [
            make_box("298", 0.95, box=[1199, 148, 50, 22]),
            make_box("攻击力", 0.95, box=[798, 152, 60, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.artifact.main == StatValue(name="atk", value=298.0)

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
    def test_pending_row_enters_model(self):
        """待激活预览行入模（M2.5）：pending=True、预览值入模、次数恒未知。"""
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
        assert result.failures == []
        assert result.warnings == []
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=5.8, roll_count=0),
            StatValue(name="atk", value=117.0, roll_count=0),
            StatValue(name="elemental_mastery", value=23.0, roll_count=0),
            StatValue(name="crit_dmg", value=15.5, roll_count=None, pending=True),
        ]

    def test_pending_row_before_value_enters_model(self):
        """E1/E2 实测形态：待激活标记在词条名后、数值在另一框（名左值右聚行）。"""
        recognition = make_enhance_recognition()
        recognition["level"] = [make_box("+0", 0.94)]
        recognition["substats"] = [
            make_box("暴击率 5.8%", box=[800, 210, 200, 20]),
            make_box("攻击力 117", box=[800, 245, 200, 20]),
            make_box("元素精通 23", box=[800, 281, 200, 20]),
            make_box("防御力（待激活）", box=[800, 316, 130, 22]),
            make_box("6.6%", box=[1203, 314, 47, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[-1] == StatValue(
            name="def_percent", value=6.6, roll_count=None, pending=True
        )
        # 一致性行数只计已解锁行：5 星 +0 合法 3~4 条，3 条无警告
        assert result.warnings == []

    def test_roll_marker_sets_roll_count(self):
        """行内带圈数字映射强化次数：①→1、②→2（标记可随名连写或行尾）。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率 5.8% ①", box=[800, 210, 200, 20]),
            make_box("攻击力 117 ②", box=[800, 245, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=5.8, roll_count=1),
            StatValue(name="atk", value=117.0, roll_count=2),
        ]

    def test_no_marker_means_zero(self):
        """强化页无带圈标记的词条 roll_count 为 0（与列表页的未知是两种状态）。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率 5.8%", box=[800, 210, 200, 20]),
            make_box("攻击力 117", box=[800, 245, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=5.8, roll_count=0),
            StatValue(name="atk", value=117.0, roll_count=0),
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
            StatValue(name="crit_rate", value=3.1, roll_count=1),
            StatValue(name="atk_percent", value=12.8, roll_count=2),
        ]

    def test_marker_only_box_merges_into_row(self):
        """标记独占文字框与词条行聚为一行时，为该行提供次数读数（E4 实测形态）；
        构造样例无模板通道，按单通道降级记警告（D6）。"""
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
        assert result.artifact.substats[0].roll_count == 1
        assert result.artifact.substats[1].roll_count == 0
        assert len(result.warnings) == 1
        assert "单通道" in result.warnings[0]


class TestReadEnhanceSettlementAndNewStat:
    """强化页三种新形态（2026-08-29 拷问定案，契约「强化页的读取时机与行形态」）：
    成长结算行取新值、「新」角标剥离；判断依据是数值个数、不依赖箭头符号。"""

    def test_settlement_row_takes_new_value(self):
        """结算行「名 旧值 新值」取新值入模（强化已完成，新值是当前值）。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("防御力", box=[800, 210, 60, 20]),
            make_box("5.8%", box=[900, 210, 50, 20]),
            make_box("11.1%", box=[1210, 210, 50, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.failures == []
        assert result.artifact.substats == [StatValue(name="def_percent", value=11.1, roll_count=0)]

    def test_settlement_row_with_roll_marker_and_arrow_residue(self):
        """带圈数字先提取为次数读数再剥离；箭头被 OCR 读出的杂字框丢弃，仍取最后一个数值。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("①暴击率", box=[800, 210, 70, 20]),
            make_box("3.5%", box=[900, 210, 50, 20]),
            make_box("→", box=[1050, 212, 30, 18]),
            make_box("6.6%", box=[1210, 210, 50, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [StatValue(name="crit_rate", value=6.6, roll_count=1)]

    def test_settlement_row_arrow_misread_as_junk(self):
        """箭头被误读为杂字（如「t」）同样丢弃——判断只看数值个数。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("生命值", box=[800, 210, 60, 20]),
            make_box("3.5%", box=[900, 210, 50, 20]),
            make_box("t", box=[1050, 212, 20, 18]),
            make_box("18.1%", box=[1210, 210, 50, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [StatValue(name="hp_percent", value=18.1, roll_count=0)]

    def test_new_stat_marker_stripped(self):
        """「新」角标（新解锁词条）剥离后按普通单值解析，次数为 0（E7 形态）。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("新", box=[778, 210, 24, 20]),
            make_box("攻击力", box=[810, 210, 60, 20]),
            make_box("4.7%", box=[1210, 210, 50, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.failures == []
        assert result.artifact.substats == [StatValue(name="atk_percent", value=4.7, roll_count=0)]

    def test_new_marker_connected_to_name(self):
        """E7 实测形态：「新」与词条名同框连写（「新攻击力」）。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("新攻击力", box=[775, 210, 73, 23]),
            make_box("4.7%", box=[1210, 210, 50, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [StatValue(name="atk_percent", value=4.7, roll_count=0)]

    def test_roll_marker_misread_as_leading_digit(self):
        """带圈数字被误读为行首短数字（E6 实测形态：①→0、③→3）：剥离、
        次数记 None（未知）+ 警告，绝不把误读数字当真值（design.md D7）。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("0", box=[780, 210, 16, 18]),
            make_box("暴击率", box=[800, 210, 60, 20]),
            make_box("3.5%", box=[900, 210, 50, 20]),
            make_box("6.6%", box=[1210, 210, 50, 20]),
            make_box("3", box=[780, 245, 16, 18]),
            make_box("生命值", box=[800, 245, 60, 20]),
            make_box("18.1%", box=[1210, 245, 50, 20]),
            make_box("攻击力 16", box=[800, 281, 200, 20]),
            make_box("元素精通 23", box=[800, 316, 200, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.failures == []
        assert result.artifact.substats == [
            StatValue(name="crit_rate", value=6.6, roll_count=None),
            StatValue(name="hp_percent", value=18.1, roll_count=None),
            StatValue(name="atk", value=16.0, roll_count=0),
            StatValue(name="elemental_mastery", value=23.0, roll_count=0),
        ]
        assert len(result.warnings) == 2
        assert all("误读" in w for w in result.warnings)

    def test_single_value_row_unchanged(self):
        """静止单值行不受结算清洗影响（回归保护）。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率", box=[800, 210, 60, 20]),
            make_box("3.1%", box=[1210, 210, 50, 20]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats == [StatValue(name="crit_rate", value=3.1, roll_count=0)]


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

    def test_breadcrumb_separator_lost_splits_by_slot_prefix(self):
        """分隔符被 OCR 读丢（E5 实测形态）：按对照文档部位名前缀匹配切分。"""
        recognition = make_enhance_recognition()
        recognition["breadcrumb"] = [make_box("生之花  止于荣礼的缎彩")]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.extras["fingerprint"] == {"slot": "flower", "name": "止于荣礼的缎彩"}
        assert result.artifact.slot == "flower"

    def test_breadcrumb_without_separator_fails(self):
        """前缀匹配不到任何部位名仍读取失败（安全方向不变）。"""
        recognition = make_enhance_recognition()
        recognition["breadcrumb"] = [make_box("止于荣礼的缎彩 生之花")]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert any("面包屑" in f for f in result.failures)

    def test_uncollected_substat_name_warns_but_reads(self):
        recognition = make_enhance_recognition()
        recognition["substats"] = [make_box("歪词条 23")] + recognition["substats"][1:]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0] == StatValue(name="歪词条", value=23.0, roll_count=0)
        assert any("歪词条" in w for w in result.warnings)


class TestRollMarksCrossChannel:
    """双通道交叉三态（D6/ADR-0007）：一致采纳、单侧降级 + 警告、不一致读取
    失败、双侧无值记 0。模板通道命中框 text 为模板文件名（录制脚本标注）。"""

    TMPL_1 = "genshin/roll_mark/roll_mark_1.png"
    TMPL_3 = "genshin/roll_mark/roll_mark_3.png"

    def base_recognition(self):
        """四行副词条（5 星 +19 合法形态），无任何次数标记。"""
        recognition = make_enhance_recognition()
        recognition["substats"] = [
            make_box("暴击率 5.8%", box=[800, 210, 200, 20]),
            make_box("攻击力 117", box=[800, 245, 200, 20]),
            make_box("元素精通 23", box=[800, 281, 200, 20]),
            make_box("暴击伤害 12.4%", box=[800, 316, 200, 20]),
        ]
        return recognition

    def test_channels_agree_adopts_silently(self):
        """行内 ① + 放大通道 ① + 模板通道 roll_mark_1 全一致 → 1，无警告。"""
        recognition = self.base_recognition()
        recognition["substats"][0] = make_box("①暴击率 5.8%", box=[800, 210, 200, 20])
        recognition["roll_marks"] = [make_box(self.TMPL_1, 0.98, box=[776, 207, 22, 22])]
        recognition["roll_marks_ocr"] = [make_box("①", 0.95, box=[776, 207, 22, 22])]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0] == StatValue(name="crit_rate", value=5.8, roll_count=1)
        assert result.warnings == []

    def test_template_only_takes_template_with_warning(self):
        """仅模板通道有值（OCR 整体丢失形态）→ 取模板读数 + 单通道警告。"""
        recognition = self.base_recognition()
        recognition["roll_marks"] = [make_box(self.TMPL_1, 0.98, box=[776, 207, 22, 22])]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0].roll_count == 1
        assert result.artifact.substats[1].roll_count == 0
        assert len(result.warnings) == 1
        assert "单通道" in result.warnings[0] and "模板" in result.warnings[0]

    def test_inline_marker_only_takes_ocr_with_warning(self):
        """仅 OCR 行内有 ②（fig2 实测形态，②模板未入库）→ 取 2 + 单通道警告。"""
        recognition = self.base_recognition()
        recognition["substats"][0] = make_box("②暴击率 5.8%", box=[800, 210, 200, 20])
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0].roll_count == 2
        assert len(result.warnings) == 1
        assert "单通道" in result.warnings[0] and "OCR" in result.warnings[0]

    def test_conflict_fails_the_read(self):
        """两通道都有值且不一致 → 读取失败（识别异常不静默判定）。"""
        recognition = self.base_recognition()
        recognition["substats"][0] = make_box("①暴击率 5.8%", box=[800, 210, 200, 20])
        recognition["roll_marks"] = [make_box(self.TMPL_3, 0.9, box=[776, 207, 22, 22])]
        recognition["roll_marks_ocr"] = [make_box("①", 0.95, box=[776, 207, 22, 22])]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any("双通道不一致" in f and "crit_rate" not in f for f in result.failures)

    def test_amplified_ocr_wins_over_inline_marker(self):
        """放大通道与行内同框读数冲突时取放大通道（实验证实放大后更稳）。"""
        recognition = self.base_recognition()
        recognition["substats"][0] = make_box("③暴击率 5.8%", box=[800, 210, 200, 20])
        recognition["roll_marks_ocr"] = [make_box("①", 0.95, box=[776, 207, 22, 22])]
        recognition["roll_marks"] = [make_box(self.TMPL_1, 0.98, box=[776, 207, 22, 22])]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0].roll_count == 1
        assert result.warnings == []

    def test_misread_row_rescued_by_template(self):
        """行首短数字误读（E6 形态）+ 模板通道命中 → 取模板读数 + 警告。"""
        recognition = self.base_recognition()
        recognition["substats"][0:1] = [
            make_box("0", box=[780, 210, 16, 18]),
            make_box("暴击率", box=[800, 210, 60, 20]),
            make_box("3.5%", box=[900, 210, 50, 20]),
            make_box("6.6%", box=[1210, 210, 50, 20]),
        ]
        recognition["roll_marks"] = [make_box(self.TMPL_1, 0.98, box=[776, 207, 22, 22])]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0] == StatValue(
            name="crit_rate", value=6.6, roll_count=1
        )
        assert len(result.warnings) == 1
        assert "误读" in result.warnings[0]

    def test_both_channels_absent_means_zero(self):
        """两侧都无值 → 0，无警告；roll_marks 区域键整体缺失同样不拦截。"""
        recognition = self.base_recognition()
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert [s.roll_count for s in result.artifact.substats] == [0, 0, 0, 0]
        assert result.warnings == []

    def test_cross_template_hits_take_best_score(self):
        """同一行多模板命中（①③ 图形相近产生交叉命中）取得分最高者。"""
        recognition = self.base_recognition()
        recognition["roll_marks"] = [
            make_box(self.TMPL_1, 0.98, box=[776, 207, 22, 22]),
            make_box(self.TMPL_3, 0.81, box=[776, 207, 22, 22]),
        ]
        result = read_enhance(recognition, CARRIED, GENSHIN_PROFILE, TEXTMAP)
        assert result.ok is True
        assert result.artifact.substats[0].roll_count == 1
