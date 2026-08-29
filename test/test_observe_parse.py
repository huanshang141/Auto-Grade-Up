"""任务 3.1：词条行切分与代号适配的单元测试。"""

import pytest

from agent.observe import adapt_stat, split_stat_text
from agent.textmap import Textmap

# 与真实对照文档同构的最小对照集
TEXTMAP = Textmap(
    language="zh_cn",
    stats={
        "暴击率": "crit_rate",
        "暴击伤害": "crit_dmg",
        "生命值": "hp",
        "攻击力": "atk",
        "防御力": "def",
        "元素精通": "elemental_mastery",
        "火元素伤害加成": "pyro_dmg_bonus",
    },
    slots={"生之花": "flower", "时之沙": "sands"},
)


class TestSplitStatText:
    def test_connected_format_keeps_plus_prefix(self):
        """列表页「名+值」连写：数值文本保留加号前缀。"""
        assert split_stat_text("暴击率+3.1%") == ("暴击率", "+3.1%")

    def test_same_row_format(self):
        """强化页「名 值」同行：数值文本无加号前缀。"""
        assert split_stat_text("暴击率 3.1%") == ("暴击率", "3.1%")

    def test_space_before_plus(self):
        assert split_stat_text("暴击率 +3.1%") == ("暴击率", "+3.1%")

    def test_outer_whitespace_stripped(self):
        assert split_stat_text("  暴击率 3.1%  ") == ("暴击率", "3.1%")

    def test_full_width_plus_passes_to_value(self):
        """切分不吞错：全角加号作为分隔位置，全角字符留给数值解析阶段拒绝。"""
        assert split_stat_text("暴击率＋3.1%") == ("暴击率", "＋3.1%")

    def test_full_width_digits_pass_to_value(self):
        assert split_stat_text("攻击力＋１９") == ("攻击力", "＋１９")

    def test_flat_value(self):
        assert split_stat_text("攻击力+117") == ("攻击力", "+117")
        assert split_stat_text("攻击力 298") == ("攻击力", "298")

    def test_thousands_separator_stays_in_value(self):
        assert split_stat_text("生命值+3,967") == ("生命值", "+3,967")

    @pytest.mark.parametrize(
        "text", ["", "   ", "暴击率", "＋3.1%", "+3.1%", "暴击率+", "暴击率 ＋"]
    )
    def test_no_valid_value_raises_value_error(self, text):
        with pytest.raises(ValueError):
            split_stat_text(text)


class TestAdaptStat:
    def test_dual_code_family_percent(self):
        assert adapt_stat("生命值", "5.8%", TEXTMAP) == ("hp_percent", True)

    def test_dual_code_family_flat(self):
        assert adapt_stat("攻击力", "+117", TEXTMAP) == ("atk", True)
        assert adapt_stat("防御力", "+19", TEXTMAP) == ("def", True)

    def test_single_code_family_stays_same(self):
        assert adapt_stat("暴击率", "+3.1%", TEXTMAP) == ("crit_rate", True)
        assert adapt_stat("火元素伤害加成", "+10%", TEXTMAP) == ("pyro_dmg_bonus", True)

    def test_uncollected_name_returns_original(self):
        assert adapt_stat("歪词条", "+5", TEXTMAP) == ("歪词条", False)

    def test_name_whitespace_stripped_for_lookup(self):
        assert adapt_stat(" 攻击力", "+117", TEXTMAP) == ("atk", True)

    def test_invalid_value_raises_for_collected_family(self):
        with pytest.raises(ValueError):
            adapt_stat("攻击力", "＋１９", TEXTMAP)

    def test_uncollected_name_does_not_parse_value(self):
        """未收录名称直接返回原文，数值合法性由调用方解析阶段把关。"""
        assert adapt_stat("歪词条", "＋１９", TEXTMAP) == ("歪词条", False)
