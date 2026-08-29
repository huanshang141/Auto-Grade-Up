"""数据模型与数值解析。

圣遗物（Artifact）是观测机构的输出、决策机构的输入，唯一形状定义见设计文档 §3：
词条数值按游戏显示值存储；固定值与百分比是两个属性代号（如 atk 与 atk_percent），
模型内不另存是否百分比的标记；「剩余强化次数」不入模型，由求值时推导。

本模块只做形状校验（键名、字段类型、列表结构）；等级、星级、部位、副词条条数
的值域校验由游戏档案驱动的 validate_artifact 承担（见 profile 模块）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatValue:
    """一条词条：属性代号（name）与游戏显示值（value）。"""

    name: str
    value: float


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
        """序列化为设计文档 §3 示例的 JSON 形状。"""
        return {
            "slot": self.slot,
            "rarity": self.rarity,
            "set": self.set,
            "level": self.level,
            "locked": self.locked,
            "main": {"name": self.main.name, "value": self.main.value},
            "substats": [
                {"name": s.name, "value": s.value} for s in self.substats
            ],
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
        main = _check_stat(data["main"], "main")
        if not isinstance(data["substats"], list):
            raise ValueError(
                f"substats 必须是列表，实际为 {type(data['substats']).__name__}"
            )
        substats = [_check_stat(item, f"substats[{i}]") for i, item in enumerate(data["substats"])]

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


def _check_stat(data: dict, label: str) -> StatValue:
    if not isinstance(data, dict):
        raise ValueError(f"{label} 必须是字典，实际为 {type(data).__name__}")
    keys = set(data)
    if keys != {"name", "value"}:
        raise ValueError(f"{label} 的键必须是 {{name, value}}，实际为 {sorted(keys)}")
    if not isinstance(data["name"], str):
        raise ValueError(f"{label}.name 必须是字符串，实际为 {data['name']!r}")
    value = data["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}.value 必须是数字，实际为 {value!r}")
    return StatValue(name=data["name"], value=float(value))


def strip_spaces(text: str) -> str:
    """去除全部空白字符（含全角空格、制表符等）。OCR 可能引入空格差异，先去空白再查对照。"""
    return "".join(ch for ch in text if not ch.isspace())


def parse_stat_value(text: str) -> tuple[float, bool]:
    """解析词条数值文本，返回 (数值, 是否百分比)。

    "5.8%" → (5.8, True)、"117" → (117.0, False)；先去除空白再解析；
    百分比标记按后缀的 % 判断；非法文本抛 ValueError。
    """
    cleaned = strip_spaces(text)
    if cleaned.endswith("%"):
        return (float(cleaned[:-1]), True)
    return (float(cleaned), False)


def parse_level(text: str) -> int:
    """解析强化等级文本。"+19" → 19、"0" → 0；先去除空白再解析；非法文本抛 ValueError。"""
    return int(strip_spaces(text))
