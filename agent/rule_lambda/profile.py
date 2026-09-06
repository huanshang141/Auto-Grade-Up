"""游戏档案（game profile）的加载与校验，以及圣遗物值域校验。

游戏档案声明一个游戏的领域参数——属性代号清单、部位代号清单、等级上限、
词条变动间隔、星级范围、副词条上限、回合机制、单次强化成长上限表；是字段、
值域与剩余强化次数公式的唯一来源，代码不硬编码任何游戏数值（ADR-0004）。
每个游戏随其资源包维护一份：assets/resource/<游戏>/profile.json。

档案缺失、结构不符或声明了代码不认识的回合机制 → 抛 ProfileError，
调用方立即停止（与规则文件同一纪律，见设计文档 §4「游戏档案」）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class ProfileError(Exception):
    """游戏档案缺失或非法。message 之外附带档案路径，便于定位。"""

    def __init__(self, message: str, path: str | Path):
        self.message = message
        self.path = str(path)
        super().__init__(f"{message}（档案：{self.path}）")


class ArtifactValidationError(Exception):
    """圣遗物当前属性的值域不符合所属游戏档案的声明。"""


# 代码已实现并认识的回合机制；档案声明此外的值即拒绝
KNOWN_ROUND_MECHANISMS: frozenset[str] = frozenset({"staged_fill"})


@dataclass
class GameProfile:
    """一份已加载的游戏档案。stats/slots 用集合语义参与校验。

    roll_growth_max：单次强化成长上限表（星级 → 属性代号 → 单次强化最大成长值），
    强化剪枝推导的唯一数值输入（ADR-0006）；只录实际可作副词条的属性代号。
    source_path：档案来源路径，支撑查表缺数据时的报错定位。
    """

    version: int
    game: str
    display_name: str
    stats: frozenset[str]
    slots: frozenset[str]
    max_level: int
    roll_interval: int
    rarity_min: int
    rarity_max: int
    substat_max: int
    round_mechanism: str
    roll_growth_max: dict[int, dict[str, float]]
    source_path: str

    def growth_max(self, rarity: int, code: str) -> float:
        """查某星级某属性代号的单次强化成长上限；缺表抛 ProfileError。

        缺数据不做消耗性决策（与档案缺键同一纪律）：错误配置应在校验期拦截，
        运行期查不到表即带着档案路径立即停止（design.md D1）。
        """
        row = self.roll_growth_max.get(rarity)
        if row is None or code not in row:
            raise ProfileError(
                f"档案无 {rarity} 星 {code} 的单次强化成长上限数据（强化剪枝推导需要）",
                self.source_path,
            )
        return row[code]


_PROFILE_KEYS = {
    "version",
    "game",
    "display_name",
    "stats",
    "slots",
    "max_level",
    "roll_interval",
    "rarity_range",
    "substat_max",
    "round_mechanism",
    "roll_growth_max",
}


def load_profile(path: str | Path) -> GameProfile:
    """从 JSON 文件加载游戏档案；缺失或非法时抛 ProfileError（message + 文件路径）。"""
    path = Path(path)
    if not path.is_file():
        raise ProfileError("档案文件不存在", path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f"档案无法读取或解析：{exc}", path) from exc
    if not isinstance(data, dict):
        raise ProfileError(f"档案必须是 JSON 对象，实际为 {type(data).__name__}", path)

    keys = set(data)
    missing = _PROFILE_KEYS - keys
    extra = keys - _PROFILE_KEYS
    if missing:
        raise ProfileError(f"档案缺少键：{sorted(missing)}", path)
    if extra:
        raise ProfileError(f"档案含未知键：{sorted(extra)}", path)

    version = data["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ProfileError(f"version 必须是整数，实际为 {version!r}", path)
    if version != 1:
        raise ProfileError(f"version 仅接受 1，实际为 {version}", path)

    for key in ("game", "display_name"):
        value = data[key]
        if not isinstance(value, str) or not value:
            raise ProfileError(f"{key} 必须是非空字符串，实际为 {value!r}", path)

    _check_code_list(data, "stats", path)
    _check_code_list(data, "slots", path)

    max_level = _check_positive_int(data, "max_level", path)
    roll_interval = _check_positive_int(data, "roll_interval", path)
    substat_max = _check_non_negative_int(data, "substat_max", path)

    rarity_range = data["rarity_range"]
    if (
        not isinstance(rarity_range, list)
        or len(rarity_range) != 2
        or any(isinstance(v, bool) or not isinstance(v, int) for v in rarity_range)
        or rarity_range[0] >= rarity_range[1]
    ):
        raise ProfileError(
            f"rarity_range 必须是二元升序整数组（[最小星级, 最大星级]），实际为 {rarity_range!r}",
            path,
        )

    mechanism = data["round_mechanism"]
    if not isinstance(mechanism, str) or mechanism not in KNOWN_ROUND_MECHANISMS:
        raise ProfileError(
            f"round_mechanism 未知：{mechanism!r}（代码已实现：{sorted(KNOWN_ROUND_MECHANISMS)}）",
            path,
        )

    roll_growth_max = _check_growth_table(data, frozenset(data["stats"]), rarity_range[0], rarity_range[1], path)

    return GameProfile(
        version=version,
        game=data["game"],
        display_name=data["display_name"],
        stats=frozenset(data["stats"]),
        slots=frozenset(data["slots"]),
        max_level=max_level,
        roll_interval=roll_interval,
        rarity_min=rarity_range[0],
        rarity_max=rarity_range[1],
        substat_max=substat_max,
        round_mechanism=mechanism,
        roll_growth_max=roll_growth_max,
        source_path=str(path),
    )


def _check_code_list(data: dict, key: str, path) -> None:
    """校验代号清单（stats/slots）：非空列表、元素为非空字符串、不得重复。"""
    value = data[key]
    if not isinstance(value, list):
        raise ProfileError(f"{key} 必须是列表，实际为 {type(value).__name__}", path)
    if not value:
        raise ProfileError(f"{key} 清单为空", path)
    if len(set(value)) != len(value):
        raise ProfileError(f"{key} 清单含重复代号", path)
    for item in value:
        if not isinstance(item, str) or not item:
            raise ProfileError(f"{key} 的元素必须是非空字符串，实际为 {item!r}", path)


def _check_positive_int(data: dict, key: str, path) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProfileError(f"{key} 必须是正整数，实际为 {value!r}", path)
    return value


def _check_non_negative_int(data: dict, key: str, path) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProfileError(f"{key} 必须是非负整数，实际为 {value!r}", path)
    return value


def _check_growth_table(
    data: dict, stats: frozenset[str], rarity_min: int, rarity_max: int, path
) -> dict[int, dict[str, float]]:
    """校验单次强化成长上限表：星级键可解析为整数且落在档案星级范围内、
    属性代号在档案清单内、值全为正数。允许不覆盖全部星级（缺表在查表时抛错）。
    """
    table = data["roll_growth_max"]
    if not isinstance(table, dict):
        raise ProfileError(
            f"roll_growth_max 必须是对象，实际为 {type(table).__name__}", path
        )
    checked: dict[int, dict[str, float]] = {}
    for star_key, row in table.items():
        star = _parse_star_key(star_key, rarity_min, rarity_max, path)
        if not isinstance(row, dict):
            raise ProfileError(
                f"roll_growth_max 的 {star} 星行必须是对象，实际为 {type(row).__name__}", path
            )
        codes: dict[str, float] = {}
        for code, value in row.items():
            if code not in stats:
                raise ProfileError(
                    f"roll_growth_max 的 {star} 星行含档案清单外的属性代号：{code!r}", path
                )
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ProfileError(
                    f"roll_growth_max 的 {star} 星 {code} 必须是正数，实际为 {value!r}", path
                )
            codes[code] = float(value)
        checked[star] = codes
    return checked


def _parse_star_key(star_key, rarity_min: int, rarity_max: int, path) -> int:
    """星级键是「十进制数字串的整数」：不可解析或越出档案星级范围即拒绝。"""
    if not isinstance(star_key, str) or not star_key.isdecimal():
        raise ProfileError(
            f"roll_growth_max 的星级键必须是数字字符串，实际为 {star_key!r}", path
        )
    star = int(star_key)
    if not rarity_min <= star <= rarity_max:
        raise ProfileError(
            f"roll_growth_max 的星级键超出档案星级范围：{star_key!r}"
            f"（档案范围 [{rarity_min}, {rarity_max}]）",
            path,
        )
    return star


def validate_artifact(artifact, profile: GameProfile) -> None:
    """校验圣遗物当前属性的值域；违规抛 ArtifactValidationError。

    值域由档案声明：等级 ∈ [0, max_level]、星级 ∈ [rarity_min, rarity_max]、
    部位 ∈ slots、副词条条数 ≤ substat_max。字段类型与结构的形状校验由
    model.from_dict 负责，本函数只查值域。
    """
    if not 0 <= artifact.level <= profile.max_level:
        raise ArtifactValidationError(
            f"level 超出档案值域：{artifact.level!r}"
            f"（档案 {profile.game} 范围 [0, {profile.max_level}]）"
        )
    if not profile.rarity_min <= artifact.rarity <= profile.rarity_max:
        raise ArtifactValidationError(
            f"rarity 超出档案值域：{artifact.rarity!r}"
            f"（档案 {profile.game} 范围 [{profile.rarity_min}, {profile.rarity_max}]）"
        )
    if artifact.slot not in profile.slots:
        raise ArtifactValidationError(
            f"slot 不在档案部位清单内：{artifact.slot!r}"
            f"（档案 {profile.game} 部位：{sorted(profile.slots)}）"
        )
    if len(artifact.substats) > profile.substat_max:
        raise ArtifactValidationError(
            f"substats 条数超出档案上限：{len(artifact.substats)}"
            f"（档案 {profile.game} 上限 {profile.substat_max}）"
        )
