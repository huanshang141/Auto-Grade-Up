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

from dataclasses import dataclass

from agent.rule_lambda.model import (
    Artifact,
    StatValue,
    parse_level,
    parse_stat_value,
    strip_spaces,
)
from agent.rule_lambda.profile import GameProfile
from agent.textmap import Textmap

# 固定值与百分比共用一条文字族代号的双代号族：按 % 后缀落 _percent 代号
_DUAL_CODE_FAMILIES = frozenset({"hp", "atk", "def"})

# 强化次数标记（契约：不参与解析）；OCR 可能把它并进行尾或单成一行
_ROLL_MARKERS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

# 各读取器的必要区域（缺失或全空 → 读取失败）；stars/lock 为模板匹配区域
_LIST_REQUIRED_REGIONS = ("name", "slot", "main", "level", "substats", "set", "stars")
_ENHANCE_REQUIRED_REGIONS = ("breadcrumb", "main", "level", "substats")
_TEMPLATE_REGIONS = frozenset({"stars", "lock"})

# 行内文字框中心的纵向偏差上界（720 基准）：相邻词条行距约 25~36px
_ROW_CENTER_TOLERANCE = 14


@dataclass
class ReadResult:
    """一次读取的整体结果；failures 非空即读取失败（artifact 为 None）。"""

    ok: bool
    artifact: Artifact | None
    extras: dict
    confidences: dict[str, float]
    failures: list[str]
    warnings: list[str]


@dataclass
class CarriedFields:
    """强化页读取器的沿用字段：列表初扫读得，单件强化过程中不可能变化（ADR-0005）。"""

    rarity: int
    set: str
    locked: bool


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


def read_list(recognition: dict, profile: GameProfile, textmap: Textmap) -> ReadResult:
    """列表页读取器：右栏预览识别结果集 → 圣遗物属性。

    星级 = stars 区域命中数；锁定 = lock 区域有命中；其余字段取 OCR。
    「待激活」预览行整行丢弃；硬失败与警告的分界见 observation 契约
    「未知与缺失语义」。无状态：同输入两次调用结果相同，不修改输入。
    """
    failures: list[str] = []
    warnings: list[str] = []
    confidences: dict[str, float] = {}

    for key in _LIST_REQUIRED_REGIONS:
        if _region_empty(recognition.get(key), template=key in _TEMPLATE_REGIONS):
            failures.append(f"必要区域缺失或全空：{key}")

    # 名称：必要区域（确认右栏可见与置信度），圣遗物名不入数据模型
    _record_confidence(confidences, recognition, "name")
    slot = _read_slot(recognition, textmap, failures, confidences)
    level = _read_level(recognition, failures, confidences)
    main = _read_main(recognition, textmap, failures, warnings, confidences)
    substats, row_count = _read_substats(recognition, profile, textmap, failures, warnings, confidences)
    set_name = _read_set(recognition, confidences)

    stars = recognition.get("stars") or []
    if stars:
        _record_confidence(confidences, recognition, "stars")
    rarity = len(stars) if stars else None

    locked = False
    lock_boxes = recognition.get("lock") or []
    if lock_boxes:
        confidences["lock"] = min(box["score"] for box in lock_boxes)
        locked = True

    artifact = None
    if not failures:
        artifact = Artifact(
            slot=slot,
            rarity=rarity,
            set=set_name,
            level=level,
            locked=locked,
            main=main,
            substats=substats,
        )
        count_warning = _substat_count_warning(rarity, level, row_count, profile)
        if count_warning:
            warnings.append(count_warning)

    return ReadResult(
        ok=not failures,
        artifact=artifact,
        extras={},
        confidences=confidences,
        failures=failures,
        warnings=warnings,
    )


def read_enhance(
    recognition: dict, carried: CarriedFields, profile: GameProfile, textmap: Textmap
) -> ReadResult:
    """强化页读取器：识别结果集 + 沿用字段 → 圣遗物属性。

    面包屑按「/」切分为部位与圣遗物名（部位参与组装，两者入 extras.fingerprint）；
    等级、主词条、副词条现场读取；rarity/set/locked 取自 CarriedFields。
    exp/mora/fodder_tier 为附属读数（只进报告），原样入 extras，缺失不拦截。
    「待激活」行整行丢弃，与列表页同规则。无状态：同输入两次调用结果相同。
    """
    failures: list[str] = []
    warnings: list[str] = []
    confidences: dict[str, float] = {}

    for key in _ENHANCE_REQUIRED_REGIONS:
        if _region_empty(recognition.get(key), template=False):
            failures.append(f"必要区域缺失或全空：{key}")

    slot = None
    fingerprint = None
    crumb_boxes = [
        b for b in recognition.get("breadcrumb") or [] if strip_spaces(b.get("text", ""))
    ]
    if crumb_boxes:
        confidences["breadcrumb"] = min(box["score"] for box in crumb_boxes)
        crumb = strip_spaces(_join_text(crumb_boxes))
        if "/" in crumb:
            slot_text, _, name_text = crumb.partition("/")
            slot = textmap.slots.get(slot_text)
            if slot is None:
                failures.append(f"部位名未收录对照文档：{slot_text}")
            else:
                fingerprint = {"slot": slot, "name": name_text}
        else:
            failures.append(f"面包屑不含「/」，无法切分部位与圣遗物名：{crumb}")

    level = _read_level(recognition, failures, confidences)
    main = _read_main(recognition, textmap, failures, warnings, confidences)
    substats, row_count = _read_substats(
        recognition, profile, textmap, failures, warnings, confidences
    )

    extras: dict = {}
    for key in ("exp", "mora", "fodder_tier"):
        boxes = [b for b in recognition.get(key) or [] if strip_spaces(b.get("text", ""))]
        if boxes:
            confidences[key] = min(box["score"] for box in boxes)
            extras[key] = _join_text(boxes)
    if fingerprint is not None:
        extras["fingerprint"] = fingerprint

    artifact = None
    if not failures:
        artifact = Artifact(
            slot=slot,
            rarity=carried.rarity,
            set=carried.set,
            level=level,
            locked=carried.locked,
            main=main,
            substats=substats,
        )
        count_warning = _substat_count_warning(carried.rarity, level, row_count, profile)
        if count_warning:
            warnings.append(count_warning)

    return ReadResult(
        ok=not failures,
        artifact=artifact,
        extras=extras,
        confidences=confidences,
        failures=failures,
        warnings=warnings,
    )


def _region_empty(boxes, template: bool) -> bool:
    """必要区域判定：键缺失、无文字框，或（OCR 区域）文字框全部无有效文字。"""
    if not boxes:
        return True
    if template:
        return False
    return not any(strip_spaces(box.get("text", "")) for box in boxes)


def _record_confidence(confidences: dict, recognition: dict, key: str) -> None:
    """逐字段置信度 = 该区域所用文字框分数的最小值；区域无框则不记。"""
    boxes = recognition.get(key) or []
    if boxes:
        confidences[key] = min(box["score"] for box in boxes)


def _join_text(boxes) -> str:
    """区域内多文字框按阅读序（先上后下、先左后右）以空格连接。

    名与值常各成一个文字框：列表页主词条上下两行（名在上、值在下），
    强化页主词条同行左右（名左值右），按此排序拼接即得行文本。
    """
    texts = [
        box.get("text", "")
        for box in sorted(boxes, key=lambda b: (b["box"][1], b["box"][0]))
        if strip_spaces(box.get("text", ""))
    ]
    return " ".join(texts)


def _group_rows(boxes) -> list[list[dict]]:
    """按文字框中心的纵坐标聚行：同行的名、值、强化次数标记各为一个文字框。"""
    ordered = sorted(boxes, key=lambda b: (b["box"][1], b["box"][0]))
    rows: list[list[dict]] = []
    for box in ordered:
        center = box["box"][1] + box["box"][3] / 2
        if rows:
            centers = [b["box"][1] + b["box"][3] / 2 for b in rows[-1]]
            if abs(center - sum(centers) / len(centers)) <= _ROW_CENTER_TOLERANCE:
                rows[-1].append(box)
                continue
        rows.append([box])
    return rows


def _read_slot(recognition, textmap, failures, confidences) -> str | None:
    boxes = [b for b in recognition.get("slot") or [] if strip_spaces(b.get("text", ""))]
    if not boxes:
        return None
    confidences["slot"] = min(box["score"] for box in boxes)
    slot_text = _join_text(boxes)
    slot = textmap.slots.get(strip_spaces(slot_text))
    if slot is None:
        failures.append(f"部位名未收录对照文档：{slot_text}")
    return slot


def _read_level(recognition, failures, confidences) -> int | None:
    boxes = [b for b in recognition.get("level") or [] if strip_spaces(b.get("text", ""))]
    if not boxes:
        return None
    confidences["level"] = min(box["score"] for box in boxes)
    try:
        return parse_level(_join_text(boxes))
    except ValueError:
        failures.append(f"无法解析等级：{_join_text(boxes)!r}")
        return None


def _read_main(recognition, textmap, failures, warnings, confidences) -> StatValue | None:
    boxes = [b for b in recognition.get("main") or [] if strip_spaces(b.get("text", ""))]
    if not boxes:
        return None
    confidences["main"] = min(box["score"] for box in boxes)
    return _parse_stat_row(_join_text(boxes), textmap, failures, warnings, "主词条")


def _read_substats(recognition, profile, textmap, failures, warnings, confidences):
    """解析副词条各行；返回 (StatValue 列表, 待激活丢弃后的行数)。"""
    raw_boxes = [b for b in recognition.get("substats") or [] if strip_spaces(b.get("text", ""))]
    if not raw_boxes:
        return [], 0
    confidences["substats"] = min(box["score"] for box in raw_boxes)

    rows = _clean_substat_rows(_group_rows(raw_boxes))
    if len(rows) > profile.substat_max:
        failures.append(
            f"副词条行数超出档案上限：{len(rows)}（档案 {profile.game} 上限 {profile.substat_max}）"
        )

    substats = []
    for row in rows:
        stat = _parse_stat_row(row, textmap, failures, warnings, "副词条")
        if stat is not None:
            substats.append(stat)

    codes = [stat.name for stat in substats]
    for code in sorted({c for c in codes if codes.count(c) > 1}):
        failures.append(f"副词条代号重复：{code}")

    return substats, len(rows)


def _clean_substat_rows(row_groups) -> list[str]:
    """行级清洗：行内框按横序拼接，去强化次数标记；「待激活」预览行与标记独占行整行丢弃。"""
    rows = []
    for group in row_groups:
        text = " ".join(box.get("text", "") for box in sorted(group, key=lambda b: b["box"][0]))
        text = "".join(ch for ch in text if ch not in _ROLL_MARKERS)
        if not text.strip() or "待激活" in text:
            continue
        rows.append(text.strip())
    return rows


def _parse_stat_row(row_text, textmap, failures, warnings, label) -> StatValue | None:
    """一行词条 → StatValue；切分或解析异常记入 failures，未收录记入 warnings 并存原文。"""
    try:
        name_text, value_text = split_stat_text(row_text)
        code, collected = adapt_stat(name_text, value_text, textmap)
        value, _ = parse_stat_value(value_text)
    except ValueError:
        failures.append(f"{label}行无法解析：{row_text}")
        return None
    if not collected:
        warnings.append(f"{label}名未收录对照文档，按原文存入：{code}")
    return StatValue(name=code, value=value)


def _read_set(recognition, confidences) -> str | None:
    """套装名取游戏原文（不经对照文档）；显示行的冒号后缀不入模。"""
    boxes = [b for b in recognition.get("set") or [] if strip_spaces(b.get("text", ""))]
    if not boxes:
        return None
    confidences["set"] = min(box["score"] for box in boxes)
    return strip_spaces(_join_text(boxes)).rstrip("：:")


def _substat_count_warning(rarity, level, count, profile) -> str | None:
    """行数与等级、稀有度的一致性提示（不拦截）；低稀有度合法形态未定，不提示。"""
    expectation = _legal_substat_counts(rarity, level, profile)
    if expectation is not None and count not in expectation:
        return f"副词条行数与等级、稀有度不一致：{count} 条（{rarity} 星 +{level}）"
    return None


def _legal_substat_counts(rarity, level, profile):
    """各稀有度在当前等级的合法副词条行数（2026-08-29 补拍核验的界面事实：
    4 星 +0 为 2 条、5 星 +0 为 3~4 条；每经过一个词条变动点解锁一条）。"""
    if rarity == 5:
        if level < profile.roll_interval:
            return frozenset({3, 4})
        return frozenset({4})
    if rarity == 4:
        unlocked = min(level // profile.roll_interval, 2)
        return frozenset({2 + unlocked})
    return None


def _has_digit(text: str) -> bool:
    """数值文本至少含一个数字字符（全角数字也算，交由白名单拒绝）。"""
    return any(ch.isdigit() for ch in text)
