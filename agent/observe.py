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

import re

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

# 强化次数标记字符全集（①~⑳，剥离用）；可出现的只有 ①~⑤（U+2460~2464），
# 按字符映射强化次数 1~5（契约「字段组装规则」）
_ROLL_MARKERS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_ROLL_MARKER_COUNTS = {ch: i + 1 for i, ch in enumerate("①②③④⑤")}

# 待激活标记的书写形态（全角/半角括号、OCR 丢括号），解析时替换为空格保留切分位
_PENDING_MARKS = ("（待激活）", "(待激活)", "待激活")

# 模板通道命中框的 text 为模板文件名（录制脚本标注），编号即次数（①~⑤ → 1~5）
_ROLL_MARK_TEMPLATE = re.compile(r"roll_mark_([1-9])")

# 各读取器的必要区域（缺失或全空 → 读取失败）；stars/lock 为模板匹配区域
_LIST_REQUIRED_REGIONS = ("name", "slot", "main", "level", "substats", "set", "stars")
_ENHANCE_REQUIRED_REGIONS = ("breadcrumb", "main", "level", "substats")
_TEMPLATE_REGIONS = frozenset({"stars", "lock"})

# 行内文字框中心的纵向偏差上界（720 基准）：相邻词条行距约 25~36px
_ROW_CENTER_TOLERANCE = 14

# 数值样片段：数字开头、仅含数字与小数点/千位逗号/百分号；用于成长结算行
# 按「数值个数」判断（契约：不依赖箭头符号的识别结果）
_VALUE_TOKEN = re.compile(r"[0-9][0-9.,%]*")


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


@dataclass
class _SubstatRow:
    """清洗后的一个副词条行：行文本与该行的次数通道读数（M2.5）。

    marker_count：行内带圈字符读数（1~5，无标记为 None）；misread：行首孤立
    短数字（带圈数字的 1 倍整图误读形态）；pending：待激活预览行；
    center：行中心的纵坐标（720 基准，供模板通道按行对齐）。
    """

    text: str
    center: float
    marker_count: int | None
    misread: bool
    pending: bool


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
    待激活预览行入模（pending=True，预览值即解锁后初始值，ADR-0006）；
    副词条 roll_count 恒 None（列表页不显示带圈数字——未知，与 0 是两种状态）。
    硬失败与警告的分界见 observation 契约「未知与缺失语义」。
    无状态：同输入两次调用结果相同，不修改输入。
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
    substats, row_count, _rows, _row_stats = _read_substats(
        recognition, profile, textmap, failures, warnings, confidences, enhance=False
    )
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
    待激活行入模（pending=True）；强化次数由双通道交叉定数（D6/ADR-0007）：
    OCR 通道（放大区域 + 行内同框带圈字符）与模板通道（roll_marks）一致即
    采纳、单侧有值取该侧 + 警告、不一致读取失败、双侧无值即 0。
    无状态：同输入两次调用结果相同。
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
        parts = _split_breadcrumb(crumb, textmap)
        if parts is None:
            failures.append(f"面包屑不含「/」，无法切分部位与圣遗物名：{crumb}")
        else:
            slot_text, name_text = parts
            slot = textmap.slots.get(slot_text)
            if slot is None:
                failures.append(f"部位名未收录对照文档：{slot_text}")
            else:
                fingerprint = {"slot": slot, "name": name_text}

    level = _read_level(recognition, failures, confidences)
    main = _read_main(recognition, textmap, failures, warnings, confidences)
    substats, row_count, rows, row_stats = _read_substats(
        recognition, profile, textmap, failures, warnings, confidences, enhance=True
    )
    cross_warnings, cross_failures = _resolve_roll_counts(rows, recognition, row_stats)
    warnings.extend(cross_warnings)
    failures.extend(cross_failures)

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


def _split_breadcrumb(crumb: str, textmap: Textmap) -> tuple[str, str] | None:
    """面包屑切分：(部位名文本, 圣遗物名文本)；无法切分返回 None。

    分隔符「/」可辨时按其切分；OCR 把分隔符读丢时（实测形态「生之花
    教官的胸花」）按对照文档的部位名做前缀匹配——部位名收自对照文档，
    匹配不到返回 None（安全方向：读取失败）。
    """
    if "/" in crumb:
        slot_text, _, name_text = crumb.partition("/")
        return slot_text.strip(), name_text.strip()
    matched = next((s for s in textmap.slots if crumb.startswith(s)), None)
    if matched is None:
        return None
    return matched, crumb[len(matched):].strip()


def _record_confidence(confidences: dict, recognition: dict, key: str) -> None:
    """逐字段置信度 = 该区域所用文字框分数的最小值；区域无框则不记。"""
    boxes = recognition.get(key) or []
    if boxes:
        confidences[key] = min(box["score"] for box in boxes)


def _join_text(boxes) -> str:
    """区域内多文字框按行分组、行内按横序、行间按纵序，以空格连接。

    名与值常各成一个文字框：列表页主词条上下两行（名在上、值在下），
    强化页主词条同行左右（名左值右，两框顶略有高低），按此拼接即得行文本。
    """
    texts = []
    for row in _group_rows(boxes):
        texts.extend(
            box.get("text", "")
            for box in sorted(row, key=lambda b: b["box"][0])
            if strip_spaces(box.get("text", ""))
        )
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


def _read_substats(recognition, profile, textmap, failures, warnings, confidences, enhance: bool):
    """解析副词条各行；返回 (StatValue 列表, 已解锁行数, 清洗行清单, 逐行词条对照表)。

    逐行词条对照表（row_stats）与清洗行清单（rows）同长同序：行解析失败处
    为 None（该行已记入 failures），保证强化次数交叉按行对齐不受解析失败影响。
    

    enhance 表示强化页读取器：行清洗层追加「新」角标剥离与成长结算行合并
    （列表页不存在这两种形态，异常双数值行走解析失败，见契约）。roll_count
    先按 OCR 行内通道赋初值（带圈字符映射 1~5、误读 None、无标记 0；列表页
    恒 None），强化页随后由 _resolve_roll_counts 双通道交叉改写。行数校验、
    代号查重与一致性警告只计已解锁行（待激活行不计，M2.5 起）。
    """
    raw_boxes = [b for b in recognition.get("substats") or [] if strip_spaces(b.get("text", ""))]
    if not raw_boxes:
        return [], 0, [], []
    confidences["substats"] = min(box["score"] for box in raw_boxes)

    rows = _clean_substat_rows(_group_rows(raw_boxes), enhance)
    unlocked_rows = [row for row in rows if not row.pending]
    if len(unlocked_rows) > profile.substat_max:
        failures.append(
            f"副词条行数超出档案上限：{len(unlocked_rows)}（档案 {profile.game} 上限 {profile.substat_max}）"
        )

    substats: list[StatValue] = []
    row_stats: list[StatValue | None] = []
    for row in rows:
        stat = _parse_stat_row(row.text, textmap, failures, warnings, "副词条")
        row_stats.append(stat)
        if stat is None:
            continue
        if row.pending:
            # 待激活词条：预览值即解锁后初始值，次数恒未知（尚未强化过）
            stat.pending = True
            stat.roll_count = None
        elif enhance:
            if row.misread:
                stat.roll_count = None
            else:
                stat.roll_count = row.marker_count or 0
        # 列表页不显示带圈数字：roll_count 保持 None（未知）
        substats.append(stat)

    codes = [stat.name for stat in substats if not stat.pending]
    for code in sorted({c for c in codes if codes.count(c) > 1}):
        failures.append(f"副词条代号重复：{code}")

    return substats, len(unlocked_rows), rows, row_stats


def _resolve_roll_counts(rows, recognition: dict, row_stats) -> tuple[list[str], list[str]]:
    """强化次数双通道交叉（D6/ADR-0007）：按行对齐后三态定数，返回 (警告, 失败)。

    OCR 通道取值优先级：放大通道（roll_marks_ocr 的带圈框，实验证实最稳）
    → 行内同框带圈字符；行首短数字误读形态记「读取尝试但不可读」。
    模板通道取该行命中框得分最高者的模板编号。三态：两通道都有值且不一致
    → 读取失败；恰好一侧有值 → 取该侧 + 警告（单通道降级）；两侧都无 → 0
    （roll_marks 区域缺失不拦截，与 mora 同级非必要区域）。
    待激活行不入交叉（次数恒 None）；解析失败行不交叉（读取必然失败）。
    直接改写 row_stats[i].roll_count。
    """
    warnings: list[str] = []
    failures: list[str] = []
    template_aligned = _align_to_rows(recognition.get("roll_marks") or [], rows)
    amplified_aligned = _align_to_rows(recognition.get("roll_marks_ocr") or [], rows)
    for index, row in enumerate(rows):
        if row.pending:
            continue
        stat = row_stats[index]
        if stat is None:
            continue  # 该行解析失败已记 failures，读取必然失败、无需交叉
        ocr_value = _ocr_channel_value(amplified_aligned.get(index), row)
        template_value = _template_channel_value(template_aligned.get(index))
        if ocr_value is not None and template_value is not None:
            if ocr_value == template_value:
                stat.roll_count = ocr_value
            else:
                failures.append(
                    f"强化次数双通道不一致（OCR 读 {ocr_value}、模板读 {template_value}）：{row.text}"
                )
        elif ocr_value is not None:
            stat.roll_count = ocr_value
            warnings.append(
                f"强化次数单通道读数（OCR 读 {ocr_value}、模板通道无值）：{row.text}"
            )
        elif template_value is not None:
            stat.roll_count = template_value
            if row.misread:
                warnings.append(
                    f"强化次数标记被误读为行首孤立数字，取模板通道读数 {template_value}：{row.text}"
                )
            else:
                warnings.append(
                    f"强化次数单通道读数（模板读 {template_value}、OCR 通道无值）：{row.text}"
                )
        elif row.misread:
            # 误读且无模板通道交叉印证 → 记未知（缺失语义：数值比较不通过，D7）
            stat.roll_count = None
            warnings.append(
                f"强化次数标记被误读为行首孤立数字，该词条次数记为未知：{row.text}"
            )
        else:
            stat.roll_count = 0
    return warnings, failures


def _align_to_rows(boxes, rows) -> dict[int, list[dict]]:
    """标记列框按纵向位置对齐到副词条行：框中心与行中心偏差 ≤ 行距容差。"""
    aligned: dict[int, list[dict]] = {}
    for box in boxes:
        center = box["box"][1] + box["box"][3] / 2
        for index, row in enumerate(rows):
            if abs(center - row.center) <= _ROW_CENTER_TOLERANCE:
                aligned.setdefault(index, []).append(box)
                break
    return aligned


def _ocr_channel_value(amplified_boxes, row) -> int | None:
    """OCR 通道该行读数：放大通道带圈框按得分取最高，退化到行内同框带圈字符。"""
    for box in sorted(amplified_boxes or [], key=lambda b: -b["score"]):
        marker = next((ch for ch in box.get("text", "") if ch in _ROLL_MARKER_COUNTS), None)
        if marker is not None:
            return _ROLL_MARKER_COUNTS[marker]
    return row.marker_count


def _template_channel_value(boxes) -> int | None:
    """模板通道该行读数：命中框按得分取最高，模板文件名编号即次数（①~⑤ → 1~5）。"""
    best: tuple[int, float] | None = None
    for box in boxes or []:
        matched = _ROLL_MARK_TEMPLATE.search(box.get("text", ""))
        if matched is None:
            continue
        if best is None or box["score"] > best[1]:
            best = (int(matched.group(1)), box["score"])
    return best[0] if best else None


def _clean_substat_rows(row_groups, enhance: bool) -> list[_SubstatRow]:
    """行级清洗：行内框按横序拼接，产出行文本与次数通道读数（M2.5）。

    带圈数字 ①~⑤ 先提取为行内标记读数、再随全部标记字符剥离；「待激活」
    标记替换为空格（保留名值切分位）、行记 pending；强化页另剥离「新」角标
    （新解锁词条）与行首孤立短数字（标记误读形态，D7），并把成长结算行
    「名 旧值 新值」合并为「名 新值」——新值是当前值，判断依据是数值个数
    （契约「强化页的读取时机与行形态」）。清洗后无有效文字的行（标记独占行、
    箭头杂字行）整行丢弃。
    """
    rows: list[_SubstatRow] = []
    for group in row_groups:
        text = " ".join(box.get("text", "") for box in sorted(group, key=lambda b: b["box"][0]))
        center = sum(b["box"][1] + b["box"][3] / 2 for b in group) / len(group)
        marker_count = next(
            (count for ch, count in _ROLL_MARKER_COUNTS.items() if ch in text), None
        )
        text = "".join(ch for ch in text if ch not in _ROLL_MARKERS)
        pending = False
        for mark in _PENDING_MARKS:
            if mark in text:
                text = text.replace(mark, " ")
                pending = True
                break
        if pending:
            # OCR 丢括号的残形（如「（待激活」）不再构成切分噪音
            text = "".join(ch for ch in text if ch not in "（）()")
        misread = False
        if enhance:
            text = _strip_new_marker(text)
            text, misread = _strip_roll_misread(text)
            text = _merge_settlement_row(text)
        if not text.strip():
            continue
        rows.append(
            _SubstatRow(
                text=text.strip(), center=center,
                marker_count=marker_count, misread=misread, pending=pending,
            )
        )
    return rows


def _strip_new_marker(text: str) -> str:
    """剥离行首「新」角标（新解锁词条的金色标记；词条名本身不含「新」字）。"""
    stripped = text.lstrip()
    return stripped[1:].lstrip() if stripped.startswith("新") else stripped


def _strip_roll_misread(text: str) -> tuple[str, bool]:
    """剥离行首的一至两位孤立数字——强化次数标记的误读形态。

    带圈数字（①③）常被 OCR 误读为「0」「3」：或并入词条名框（行首数字），
    或独立成框与词条行聚组（行首数字 token）。词条名十族均不含数字，行首
    短数字不可能是词条内容；真值不受影响（数字开头的多字符片段如「3,967」
    只出现在数值位置，且此处只剥行首 token）。返回 (剥离后文本, 是否误读)，
    误读行由调用方把次数记 None（未知，design.md D7）。
    """
    tokens = text.split()
    if tokens and tokens[0].isdigit() and len(tokens[0]) <= 2:
        return " ".join(tokens[1:]), True
    return text, False


def _merge_settlement_row(text: str) -> str:
    """成长结算行「名 旧值 新值」合并为「名 新值」。

    行内出现两个及以上数值样片段时，词条名取首个数值之前的片段（箭头
    符号及其误读杂字位于两数值之间，一并丢弃），数值取最后一个——强化
    已完成，新值是当前值。数值个数不足两个（静止单值行）原样返回。
    """
    tokens = text.split()
    value_indexes = [i for i, token in enumerate(tokens) if _VALUE_TOKEN.fullmatch(token)]
    if len(value_indexes) < 2:
        return text
    head = tokens[: value_indexes[0]]
    return " ".join([*head, tokens[value_indexes[-1]]])


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
    """套装名取套装名行（最上一行）的游戏原文，不经对照文档；冒号后缀不入模。

    roi 覆盖两种稀有度的套装块（4 星面板上移），流水线以 expected 正则滤掉
    副词条行与带数字的效果行；纯中文的效果换行可能残留，取最上一行即套装名。
    """
    boxes = [b for b in recognition.get("set") or [] if strip_spaces(b.get("text", ""))]
    if not boxes:
        return None
    name_row = sorted(_group_rows(boxes)[0], key=lambda b: b["box"][0])
    confidences["set"] = min(box["score"] for box in name_row)
    return strip_spaces(" ".join(box.get("text", "") for box in name_row)).rstrip("：:")


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
