"""数据模型与数值解析。

圣遗物（Artifact）是观测机构的输出、决策机构的输入，唯一形状定义见设计文档 §3：
词条数值按游戏显示值存储；固定值与百分比是两个属性代号（如 atk 与 atk_percent），
模型内不另存是否百分比的标记；「剩余强化次数」不入模型，由求值时推导。

词条值对象（StatValue）的 roll_count 与 pending 是 M2.5 起的扩展字段：
roll_count 为词条强化次数（null = 界面不显示该信息，如列表页；0 = 界面无
带圈数字标记——未知与 0 是两种事实，序列化必须可区分，design.md D2）；
pending 为待激活标记（灰色预览行，预览数值即解锁后的初始值）。主词条
不携带这两个信息（界面无此显示），序列化恒为 {name, value}。

本模块只做形状校验（键名、字段类型、列表结构）；等级、星级、部位、副词条
条数与强化次数的值域校验由游戏档案驱动的 validate_artifact 承担（见 profile 模块）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatValue:
    """一条词条：属性代号（name）与游戏显示值（value）。

    roll_count：词条强化次数（可空）；pending：待激活标记。仅副词条携带，
    主词条保持默认值。
    """

    name: str
    value: float
    roll_count: int | None = None
    pending: bool = False


@dataclass
class Artifact:
    """一件圣遗物的当前属性。套装名保留游戏原文，不经字段对照文档。"""

    slot: str
    rarity: int
    set: str
    level: int
    locked: bool
    main: StatValue
    substats: list[StatValue]

    def to_dict(self) -> dict:
        """序列化为设计文档 §3 示例的 JSON 形状。

        副词条的 roll_count 键始终写出（null 或数字，可区分「未知」与「0」）；
        pending 仅 True 时写出（键可省略，省略即已解锁）。主词条不带次数字段。
        """
        return {
            "slot": self.slot,
            "rarity": self.rarity,
            "set": self.set,
            "level": self.level,
            "locked": self.locked,
            "main": {"name": self.main.name, "value": self.main.value},
            "substats": [_stat_to_dict(s) for s in self.substats],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Artifact:
        """从字典构造；键名、字段类型、列表结构不符时抛 ValueError。

        词条数值接受 int 或 float，统一收为 float。
        """
        _ARTIFACT_KEYS = {"slot", "rarity", "set", "level", "locked", "main", "substats"}
        _STAT_KEYS = {"name", "value"}

        if not isinstance(data, dict):
            raise ValueError(f"圣遗物必须是字典，实际为 {type(data).__name__}")

        keys = set(data)
        missing = _ARTIFACT_KEYS - keys
        extra = keys - _ARTIFACT_KEYS
        if missing:
            raise ValueError(f"圣遗物缺少键：{sorted(missing)}")
        if extra:
            raise ValueError(f"圣遗物含未知键：{sorted(extra)}")

        _check_str(data, "slot")
        _check_str(data, "set")
        _check_int(data, "rarity")
        _check_int(data, "level")
        if not isinstance(data["locked"], bool):
            raise ValueError(f"locked 必须是布尔值，实际为 {data['locked']!r}")
        main = _check_stat(data["main"], "main", extended=False)
        if not isinstance(data["substats"], list):
            raise ValueError(
                f"substats 必须是列表，实际为 {type(data['substats']).__name__}"
            )
        substats = [
            _check_stat(item, f"substats[{i}]", extended=True)
            for i, item in enumerate(data["substats"])
        ]

        return cls(
            slot=data["slot"],
            rarity=data["rarity"],
            set=data["set"],
            level=data["level"],
            locked=data["locked"],
            main=main,
            substats=substats,
        )


def _check_str(data: dict, key: str) -> None:
    if not isinstance(data[key], str):
        raise ValueError(f"{key} 必须是字符串，实际为 {data[key]!r}")


def _check_int(data: dict, key: str) -> None:
    value = data[key]
    # 布尔值是 int 的子类，单独排除
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} 必须是整数，实际为 {value!r}")


def _check_stat(data: dict, label: str, extended: bool) -> StatValue:
    """词条形状校验。extended=True（副词条）接受扩展键 roll_count / pending：
    roll_count 缺省或 null 为 None、非负整数为次数本身；pending 缺省为 False、
    布尔为标记本身。extended=False（主词条）键集合固定 {name, value}。"""
    if not isinstance(data, dict):
        raise ValueError(f"{label} 必须是字典，实际为 {type(data).__name__}")
    if extended:
        allowed = {"name", "value", "roll_count", "pending"}
        required = {"name", "value"}
    else:
        allowed = {"name", "value"}
        required = allowed
    keys = set(data)
    if not required <= keys or not keys <= allowed:
        expected = " 至少含 {name, value}、至多含 {name, value, roll_count, pending}" if extended else "必须是 {name, value}"
        raise ValueError(f"{label} 的键{expected}，实际为 {sorted(keys)}")
    if not isinstance(data["name"], str):
        raise ValueError(f"{label}.name 必须是字符串，实际为 {data['name']!r}")
    value = data["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}.value 必须是数字，实际为 {value!r}")

    roll_count = None
    if "roll_count" in data and data["roll_count"] is not None:
        roll_count = data["roll_count"]
        if isinstance(roll_count, bool) or not isinstance(roll_count, int) or roll_count < 0:
            raise ValueError(
                f"{label}.roll_count 必须是 null 或非负整数，实际为 {roll_count!r}"
            )
    pending = data.get("pending", False)
    if not isinstance(pending, bool):
        raise ValueError(f"{label}.pending 必须是布尔值，实际为 {pending!r}")
    return StatValue(name=data["name"], value=float(value), roll_count=roll_count, pending=pending)


def _stat_to_dict(stat: StatValue) -> dict:
    entry: dict = {"name": stat.name, "value": stat.value, "roll_count": stat.roll_count}
    if stat.pending:
        entry["pending"] = True
    return entry


def strip_spaces(text: str) -> str:
    """去除全部空白字符（含全角空格、制表符等）。OCR 可能引入空格差异，先去空白再查对照。"""
    return "".join(ch for ch in text if not ch.isspace())


# 数值解析的字符白名单：拒绝 nan/inf/下划线分隔符等 Python 数字字面量，
# 也拒绝全角数字与全角百分号（2026-08-29 定案：不归一化，直接拒绝）。
# 千位分隔符逗号（如「3,967」）在解析前去除，见 parse_stat_value。
_VALUE_CHARS = frozenset("0123456789.+-")
_LEVEL_CHARS = frozenset("0123456789+-")


def parse_stat_value(text: str) -> tuple[float, bool]:
    """解析词条数值文本，返回 (数值, 是否百分比)。

    "5.8%" → (5.8, True)、"117" → (117.0, False)；先去除空白、再去千位分隔符
    逗号（固定值大数值显示为「3,967」，2026-08-29 补拍核验）再解析；
    百分比标记按后缀的半角 % 判断；字符不在白名单（ASCII 数字、小数点、
    正负号、半角百分号）或为空时抛 ValueError。
    """
    cleaned = strip_spaces(text).replace(",", "")
    if cleaned.endswith("%"):
        body, is_percent = cleaned[:-1], True
    else:
        body, is_percent = cleaned, False
    if not body or any(ch not in _VALUE_CHARS for ch in body):
        raise ValueError(f"无法解析词条数值：{text!r}")
    return (float(body), is_percent)


def parse_level(text: str) -> int:
    """解析强化等级文本。"+19" → 19、"0" → 0；先去除空白再解析；
    字符不在白名单（ASCII 数字、正负号）或为空时抛 ValueError。"""
    cleaned = strip_spaces(text)
    if not cleaned or any(ch not in _LEVEL_CHARS for ch in cleaned):
        raise ValueError(f"无法解析强化等级：{text!r}")
    return int(cleaned)
