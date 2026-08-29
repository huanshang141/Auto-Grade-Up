"""观测解析核心（M2）：识别结果集 → 读取结果（ReadResult）。

纯 Python 的「文字之后」全部处理——词条名适配属性代号、数值解析、组装属性
与附属读数（extras）、完整性校验与失败清单。禁止导入 maa：解析核心的输入
输出全是纯数据，一旦导入即被钉在框架部署上，「不连真机验证」随之落空
（理由见 M2 concept.md §3.1，由冒烟测试守卫）。

输入三样：识别结果集（区域键 → 文字框列表）、游戏档案（GameProfile，M1 产物）、
字段对照文档加载产物（Textmap，M2 任务 2.1 交付）。输出读取结果（ReadResult），
含两个读取器（行为契约见 specs/observation/spec.md）：

- 列表页读取器（read_list）
- 强化页读取器（read_enhance，含控制层传递的沿用字段 CarriedFields）
"""

from __future__ import annotations

from agent.rule_lambda.model import parse_stat_value, strip_spaces
from agent.textmap import Textmap

# 固定值与百分比共用一条文字族代号的双代号族：按 % 后缀落 _percent 代号
_DUAL_CODE_FAMILIES = frozenset({"hp", "atk", "def"})

# 强化次数标记（契约：不参与解析）；OCR 可能把它并进行尾或单成一行
_ROLL_MARKERS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def split_stat_text(text: str) -> tuple[str, str]:
    """把一行词条文本切分为（词条名文本，数值文本）。

    两界面行格式分别为「名+值」连写（如「暴击率+3.1%」）与「名 值」同行
    （如「暴击率 3.1%」）；行内无有效数值时抛 ValueError。切分不吞错：全角
    字符不做修正，全角加号仅作为分隔位置、随数值文本留给解析阶段拒绝。
    """
    trimmed = text.strip()
    if not trimmed:
        raise ValueError(f"词条行不含有效数值：{text!r}")
    for separator in ("+", "＋"):
        index = trimmed.find(separator)
        if index != -1:
            name = trimmed[:index].strip()
            value = trimmed[index:].strip()
            if not name or not _has_digit(value):
                raise ValueError(f"词条行不含有效数值：{text!r}")
            return name, value
    index = next((i for i, ch in enumerate(trimmed) if ch.isspace()), -1)
    if index == -1:
        raise ValueError(f"词条行不含有效数值：{text!r}")
    name = trimmed[:index].strip()
    value = trimmed[index:].strip()
    if not name or not _has_digit(value):
        raise ValueError(f"词条行不含有效数值：{text!r}")
    return name, value


def adapt_stat(name_text: str, value_text: str, textmap: Textmap) -> tuple[str, bool]:
    """词条名经对照文档映射为属性代号；返回 (属性代号, 是否已收录)。

    名称先去空白再查对照；hp/atk/def 三族为双代号族，按 % 后缀落
    hp_percent/atk_percent/def_percent，其余族原样。未收录 → (OCR 原文, False)，
    数值合法性由调用方的解析阶段把关；已收录名称的数值解析复用
    model.parse_stat_value（含千位逗号去除与全角拒绝）。
    """
    family = textmap.stats.get(strip_spaces(name_text))
    if family is None:
        return (strip_spaces(name_text), False)
    _, is_percent = parse_stat_value(value_text)
    if family in _DUAL_CODE_FAMILIES and is_percent:
        return (f"{family}_percent", True)
    return (family, True)


def _has_digit(text: str) -> bool:
    """数值文本至少含一个数字字符（全角数字也算，交由白名单拒绝）。"""
    return any(ch.isdigit() for ch in text)
