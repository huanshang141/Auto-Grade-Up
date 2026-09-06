"""任务 5.1：离线全链路测试——截图夹具 → 框架识别 → 解析核心 → 真值断言。

第二层测试（concept.md §6）：对 27 张截图夹具跑与运行时完全相同的框架识别
（同引擎、同模型、同节点定义——节点参数取 observation.json），识别构造与
录制脚本 tools/record_ocr_dumps.py 是同一份代码（直接复用其常量与函数）；
识别结果集经解析核心两个读取器后逐字段断言。真值表 2026-08-29 逐一从截图
抄录；词条强化次数与待激活标记按 M2.5 双通道交叉后的口径断言（2026-09-06）；
星级、锁定以列表页模板匹配命中为准。

maa 绑定仅经 requirements-dev 引入（解析核心不导入，冒烟测试守卫）。
fig4/fig5 为弹窗遮挡形态（proposal 风险表预登记）：fig4 的素材档位下拉弹窗
不触及右栏词条与摩拉读数，全字段照常断言；fig5 的放入设置弹窗遮住主词条名
与副词条名，按可见范围放宽，见 TestFig5OccludedByPopup 用例内注明。
"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest
from PIL import Image
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker

from agent.observe import CarriedFields, read_enhance, read_list
from agent.rule_lambda.model import StatValue
from agent.rule_lambda.profile import load_profile
from agent.textmap import load_textmap
from tools.record_ocr_dumps import (
    ENHANCE_REGIONS,
    LIST_REGIONS,
    PIPELINE_JSON,
    RESOURCE_DIR,
    SCREENSHOT_DIR,
    check_shape,
    reader_of,
    run_region,
)

PROFILE = load_profile("assets/resource/genshin/profile.json")
TEXTMAP = load_textmap("assets/resource/genshin/textmap/zh_cn.json", PROFILE)

# 素材档位在 6 张强化页夹具中的统一读数；摩拉需要数全部为 0
FODDER_TIER_TEXT = "4星及以下素材"
MORA_PATTERN = r"需要\s*0[,，]?"

# 真值表（2026-08-29 逐一从截图抄录）。列表页：
# (截图主干, 部位, 星级, 套装, 等级, 是否锁定, 主词条, 副词条)
LIST_TRUTH = [
    (
        "fig1",
        "plume",
        5,
        "黄金剧团",
        19,
        True,
        ("atk", 298.0),
        [("crit_rate", 3.1), ("atk_percent", 12.8), ("hp_percent", 11.1), ("crit_dmg", 7.0)],
    ),
    (
        "fig3",
        "plume",
        5,
        "黄金剧团",
        19,
        True,
        ("atk", 298.0),
        [("crit_rate", 3.1), ("atk_percent", 12.8), ("hp_percent", 11.1), ("crit_dmg", 7.0)],
    ),
    (
        "fig6",
        "plume",
        5,
        "黄金剧团",
        19,
        True,
        ("atk", 298.0),
        [("crit_rate", 3.1), ("atk_percent", 12.8), ("hp_percent", 11.1), ("crit_dmg", 7.0)],
    ),
    (
        "fig7",
        "plume",
        5,
        "黄金剧团",
        19,
        True,
        ("atk", 298.0),
        [("crit_rate", 3.1), ("atk_percent", 12.8), ("hp_percent", 11.1), ("crit_dmg", 7.0)],
    ),
    (
        "L1_list_lv0_3sub",
        "goblet",
        5,
        "纺月的夜歌",
        0,
        False,
        ("def_percent", 8.7),
        # 第 4 行「生命值+269（待激活）」为待激活预览行（M2.5 起入模）
        [("elemental_mastery", 23.0), ("atk_percent", 4.1), ("def", 16.0),
         ("hp", 269.0, None, True)],
    ),
    (
        "L2_list_lv0_4sub",
        "goblet",
        5,
        "纺月的夜歌",
        0,
        False,
        ("hp_percent", 7.0),
        # 攻击力百分比与固定值并存（同族双代号合法）
        [("energy_recharge", 4.5), ("atk_percent", 5.8), ("hp", 239.0), ("atk", 19.0)],
    ),
    (
        "L3_list_percent_main",
        "sands",
        5,
        "追忆之注连",
        12,
        False,
        ("atk_percent", 30.8),
        [("crit_rate", 6.2), ("def", 39.0), ("crit_dmg", 5.4), ("atk", 18.0)],
    ),
    (
        "L4_list_elem_goblet",
        "goblet",
        5,
        "影中沉凝的幻灭",
        0,
        False,
        ("pyro_dmg_bonus", 7.0),
        [("elemental_mastery", 16.0), ("def_percent", 7.3), ("energy_recharge", 5.8), ("hp_percent", 4.1)],
    ),
    (
        "L5_list_flat_sub",
        "flower",
        5,
        "追忆之注连",
        16,
        False,
        ("hp", 3967.0),  # 主词条显示「3,967」，千位逗号解析前去除
        [("crit_dmg", 10.9), ("atk", 31.0), ("crit_rate", 6.6), ("energy_recharge", 5.2)],
    ),
    (
        "L6_list_4star",
        "flower",
        4,
        "千岩牢固",
        0,
        False,
        ("hp", 645.0),
        [("atk_percent", 4.2), ("crit_dmg", 5.0)],
    ),
    (
        "L7_list_def",
        "sands",
        5,
        "影中沉凝的幻灭",
        18,
        False,
        ("def_percent", 53.3),
        [("crit_rate", 3.9), ("atk", 27.0), ("def", 42.0), ("elemental_mastery", 40.0)],
    ),
    (
        "L8_list_circlet",
        "circlet",
        5,
        "影中沉凝的幻灭",
        0,
        False,
        ("hp_percent", 7.0),
        # 防御力百分比与固定值并存（同族双代号合法）
        [("crit_dmg", 7.8), ("def_percent", 7.3), ("elemental_mastery", 19.0), ("def", 19.0)],
    ),
    # —— 2026-08-29 第二、三批补拍（真值来源：README 验收记录）——
    (
        "L9_list_locked_lv20",
        "plume",
        5,
        "纺月的夜歌",
        20,
        True,
        ("atk", 311.0),
        # +20 满级形态；列表页无「MAX」标记（仅强化页有）
        [("crit_dmg", 13.2), ("energy_recharge", 10.4), ("hp", 209.0), ("crit_rate", 9.7)],
    ),
    (
        "L10_list_4star_lv16",
        "flower",
        4,
        "教官",
        16,
        True,
        ("hp", 3571.0),  # 4 星主词条也有千位逗号
        # 攻击力百分比与固定值并存（同族双代号合法）
        [("atk", 11.0), ("energy_recharge", 5.2), ("atk_percent", 8.4), ("elemental_mastery", 30.0)],
    ),
    (
        "L11_list_crit_dmg_circlet",
        "circlet",
        5,
        "影中沉凝的幻灭",
        20,
        True,
        ("crit_dmg", 62.2),
        [("atk_percent", 11.1), ("energy_recharge", 9.7), ("crit_rate", 9.7), ("hp_percent", 4.7)],
    ),
    (
        "L12_list_em_sands",
        "sands",
        5,
        "黄金剧团",
        20,
        True,
        ("elemental_mastery", 187.0),
        [("crit_dmg", 7.8), ("crit_rate", 5.4), ("atk", 56.0), ("hp", 418.0)],
    ),
    (
        "L13_list_healing_circlet",
        "circlet",
        5,
        "影中沉凝的幻灭",
        0,
        False,
        ("healing_bonus", 5.4),
        # 生命值百分比与固定值并存；第 4 行「攻击力 4.7%（待激活）」为待激活预览行
        [("hp_percent", 4.7), ("atk", 18.0), ("hp", 209.0),
         ("atk_percent", 4.7, None, True)],
    ),
]

# 真值表（2026-08-29 逐一从截图抄录）。强化页：星级、套装、锁定为沿用字段
# （CarriedFields 由列表初扫传递，ADR-0005）；exp 精确断言，摩拉与素材档位
# 统一断言（见上方常量）。
# (截图主干, 沿用字段, 部位, 圣遗物名, 等级, 主词条, 副词条, exp)
ENHANCE_TRUTH = [
    (
        "fig2",
        CarriedFields(rarity=5, set="黄金剧团", locked=True),
        "plume",
        "黄金飞鸟的落羽",
        19,
        ("atk", 298.0),
        # ②攻击力（同框 Unicode）双通道：模板无 ② 素材 → 单通道降级 + 警告；
        # 生命值 ① 仅模板通道命中（1 倍整图丢框、放大 OCR 亦漏读，fig2 实测）
        [("crit_rate", 3.1, 0, False), ("atk_percent", 12.8, 2, False),
         ("hp_percent", 11.1, 1, False), ("crit_dmg", 7.0, 0, False)],
        "2900/35575",
    ),
    (
        "fig4",
        CarriedFields(rarity=5, set="黄金剧团", locked=True),
        "plume",
        "黄金飞鸟的落羽",
        19,
        ("atk", 298.0),
        # 同 fig2（fig4 的生命值 ① 双通道一致命中，警告仅攻击力一条）
        [("crit_rate", 3.1, 0, False), ("atk_percent", 12.8, 2, False),
         ("hp_percent", 11.1, 1, False), ("crit_dmg", 7.0, 0, False)],
        "2900/35575",
    ),
    (
        "E1_enhance_lv0_3sub",
        CarriedFields(rarity=5, set="影中沉凝的幻灭", locked=False),
        "flower",
        "止于荣礼的缎彩",
        0,
        ("hp", 717.0),
        # 第 4 行「防御力（待激活）6.6%」为待激活预览行（M2.5 起入模）
        [("hp_percent", 4.7, 0, False), ("atk", 16.0, 0, False), ("def", 19.0, 0, False),
         ("def_percent", 6.6, None, True)],
        "0/3000",
    ),
    (
        "E2_enhance_sands",
        CarriedFields(rarity=5, set="影中沉凝的幻灭", locked=False),
        "sands",
        "止于宏伟梦醒的时刻",
        0,
        ("def_percent", 8.7),
        # 第 4 行「攻击力（待激活）18」为待激活预览行
        [("elemental_mastery", 23.0, 0, False), ("energy_recharge", 5.8, 0, False),
         ("hp_percent", 5.8, 0, False), ("atk", 18.0, None, True)],
        "0/3000",
    ),
    (
        "E3_enhance_clean",
        CarriedFields(rarity=5, set="影中沉凝的幻灭", locked=False),
        "flower",
        "止于荣礼的缎彩",
        0,
        ("hp", 717.0),
        [("def", 21.0, 0, False), ("elemental_mastery", 21.0, 0, False),
         ("crit_rate", 3.9, 0, False), ("energy_recharge", 4.5, 0, False)],
        "0/3000",
    ),
    # —— 2026-08-29 第二、三批补拍（真值来源：README 验收记录）——
    (
        "E4_enhance_lv16_marks",
        # 套装名强化页不显示、未从列表页采样——沿字段原样传递、不经校验（design D6）
        CarriedFields(rarity=5, set="（E4 套装未采样）", locked=False),
        "circlet",
        "魔战士的羽面",
        16,
        ("crit_dmg", 51.6),
        # 四条副词条均带强化次数标记 ①（5 星 +16 四次成长各一次）：行内同框、
        # 放大 OCR、模板通道三处一致命中（1 倍整图的丢框与误读形态全部被
        # 双通道修复，M2.5 起无警告）
        [("hp", 508.0, 1, False), ("crit_rate", 5.8, 1, False),
         ("atk_percent", 9.9, 1, False), ("def_percent", 13.9, 1, False)],
        "280/23500",
    ),
    (
        "E5_enhance_lv8_preview",
        CarriedFields(rarity=4, set="教官", locked=False),
        "flower",
        "教官的胸花",
        8,
        ("hp", 2108.0),  # 主词条千位逗号
        # 第 4 行「防御力 5.8% → 11.1% ↑」为成长结算形态，取新值；面包屑分隔符
        # 被 OCR 读丢，按部位名前缀匹配切分（契约修订）
        [("crit_dmg", 4.4, 0, False), ("elemental_mastery", 15.0, 0, False),
         ("hp_percent", 3.7, 0, False), ("def_percent", 11.1, 0, False)],
        "1700/7375",
    ),
    (
        "E6_enhance_lv20_max",
        CarriedFields(rarity=5, set="影中沉凝的幻灭", locked=False),
        "sands",
        "止于宏伟梦醒的时刻",
        20,
        ("energy_recharge", 51.8),
        # ①暴击率「3.5% → 6.6% ↑」结算行取新值、③生命值 18.1%——1 倍整图
        # 误读为「0」「3」的标记由双通道修复（放大 OCR 与模板通道一致命中）；
        # 满级形态 exp 传 None——经验条无数字、素材区整体消失（契约）
        [("crit_dmg", 6.2, 0, False), ("hp", 269.0, 0, False),
         ("crit_rate", 6.6, 1, False), ("hp_percent", 18.1, 3, False)],
        None,
    ),
    (
        "E7_enhance_lv4_new_stat",
        CarriedFields(rarity=5, set="（E7 套装未采样）", locked=False),
        "goblet",
        "绯花之壶",
        4,
        ("geo_dmg_bonus", 14.9),
        # 第 4 行「新攻击力 4.7%」为新解锁词条（「新」角标剥离、次数 0）；星级 5 由
        # 三初始词条 + +4 解锁第 4 条的节奏实证
        [("crit_rate", 2.7, 0, False), ("crit_dmg", 6.2, 0, False),
         ("def", 21.0, 0, False), ("atk_percent", 4.7, 0, False)],
        "1200/5900",
    ),
]

# 交叉警告期望（D6 单通道降级）：夹具 → 该页警告条数（均为「单通道」警告；
# E4/E6 双通道一致无警告，1 倍整图的丢框与误读形态全部被修复）
ENHANCE_CROSS_WARNINGS = {"fig2": 2, "fig4": 1}


@pytest.fixture(scope="module")
def recognize():
    """整模块共享一次资源加载；逐节点识别路径与 tools/record_ocr_dumps.py 相同
    （run_region：双通道区域走放大 OCR 与逐模板标注的专属录制逻辑）。"""
    nodes = json.loads(PIPELINE_JSON.read_text(encoding="utf-8"))
    assert len(nodes) == 17, f"预期 17 个识别节点，实际 {len(nodes)}"

    resource = Resource()
    load = resource.post_bundle(RESOURCE_DIR)
    load.wait()
    assert load.succeeded, "资源加载失败"
    tasker = Tasker()
    assert Library.framework().MaaTaskerBindResource(tasker._handle, resource._handle), "Resource 绑定失败"

    def run(stem: str) -> tuple[str, dict]:
        reader = reader_of(stem)
        regions = LIST_REGIONS if reader == "list" else ENHANCE_REGIONS
        with Image.open(SCREENSHOT_DIR / f"{stem}.png") as im:
            image = np.ascontiguousarray(np.array(im.convert("RGB")))[:, :, ::-1]
        dump: dict[str, list[dict]] = {}
        for region in regions:
            dump[region] = run_region(tasker, image, nodes[f"obs_{reader}_{region}"], region)
        check_shape(dump, regions)
        return reader, dump

    yield run


def assert_stat_rows(actual, expected) -> None:
    """真值行：(名, 值) 为列表页默认形状（roll_count=None、未待激活）；
    (名, 值, roll_count, pending) 显式给出扩展形状。"""
    wanted = []
    for row in expected:
        if len(row) == 2:
            wanted.append(StatValue(name=row[0], value=row[1]))
        else:
            name, value, roll_count, pending = row
            wanted.append(
                StatValue(name=name, value=value, roll_count=roll_count, pending=pending)
            )
    assert actual == wanted


class TestListEndToEnd:
    @pytest.mark.parametrize(
        "stem,slot,rarity,set_name,level,locked,main,substats",
        LIST_TRUTH,
        ids=[row[0] for row in LIST_TRUTH],
    )
    def test_reads_artifact_from_screenshot(
        self, recognize, stem, slot, rarity, set_name, level, locked, main, substats
    ):
        reader, dump = recognize(stem)
        assert reader == "list"
        result = read_list(dump, PROFILE, TEXTMAP)
        assert result.failures == []
        assert result.ok is True
        assert result.warnings == []
        artifact = result.artifact
        assert artifact.slot == slot
        assert artifact.rarity == rarity
        assert artifact.set == set_name
        assert artifact.level == level
        assert artifact.locked is locked
        assert artifact.main == StatValue(name=main[0], value=main[1])
        assert_stat_rows(artifact.substats, substats)
        # 列表页不显示带圈数字：全部词条 roll_count 恒 None（未知）
        assert all(s.roll_count is None for s in artifact.substats)
        assert result.extras == {}
        assert min(result.confidences.values()) >= 0.6


class TestEnhanceEndToEnd:
    @pytest.mark.parametrize(
        "stem,carried,slot,name,level,main,substats,exp",
        ENHANCE_TRUTH,
        ids=[row[0] for row in ENHANCE_TRUTH],
    )
    def test_reads_artifact_from_screenshot(
        self, recognize, stem, carried, slot, name, level, main, substats, exp
    ):
        reader, dump = recognize(stem)
        assert reader == "enhance"
        result = read_enhance(dump, carried, PROFILE, TEXTMAP)
        assert result.failures == []
        assert result.ok is True
        artifact = result.artifact
        assert artifact.slot == slot
        assert artifact.rarity == carried.rarity
        assert artifact.set == carried.set
        assert artifact.level == level
        assert artifact.locked is carried.locked
        assert artifact.main == StatValue(name=main[0], value=main[1])
        assert_stat_rows(artifact.substats, substats)
        if exp is None:
            # 满级强化页（E6）：经验条无数字、素材档位与摩拉区域整体消失
            # （契约），附属读数仅剩指纹
            assert result.extras == {"fingerprint": {"slot": slot, "name": name}}
        else:
            assert result.extras["exp"] == exp
            assert result.extras["fodder_tier"] == FODDER_TIER_TEXT
            assert re.fullmatch(MORA_PATTERN, result.extras["mora"])
            assert result.extras["fingerprint"] == {"slot": slot, "name": name}
        cross = ENHANCE_CROSS_WARNINGS.get(stem, 0)
        if cross:
            assert len(result.warnings) == cross
            assert all("单通道" in w for w in result.warnings)
        else:
            assert result.warnings == []
        assert min(result.confidences.values()) >= 0.6


class TestFig5OccludedByPopup:
    """fig5：放入设置弹窗遮住主词条名与副词条名（proposal 风险表预登记）。

    按可见范围放宽：被弹窗盖住的词条行只剩数值、切分失败，按契约逐行记入
    failures（ok=False、artifact=None）；弹窗外可见的字段（面包屑切分、
    等级、exp、摩拉）仍逐项断言。素材档位下拉框同样被盖住，区域为空。
    """

    def test_visible_fields_read_and_occluded_rows_fail(self, recognize):
        reader, dump = recognize("fig5")
        assert reader == "enhance"
        result = read_enhance(dump, CarriedFields(rarity=5, set="黄金剧团", locked=True), PROFILE, TEXTMAP)
        assert result.ok is False
        assert result.artifact is None
        assert any(f.startswith("主词条行无法解析") for f in result.failures)
        assert sum(f.startswith("副词条行无法解析") for f in result.failures) == 4
        assert result.extras["fingerprint"] == {"slot": "plume", "name": "黄金飞鸟的落羽"}
        assert result.extras["exp"] == "2900/35575"
        assert re.fullmatch(MORA_PATTERN, result.extras["mora"])
        assert "fodder_tier" not in result.extras
        assert result.confidences["breadcrumb"] >= 0.6
        assert result.confidences["level"] >= 0.6
