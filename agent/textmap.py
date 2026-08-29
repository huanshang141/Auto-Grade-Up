"""字段对照文档加载校验器（M2）：游戏界面文字 → 属性/部位代号。

加载并校验对照文档（`assets/resource/<game>/textmap/<language>.json`）：
结构、版本、映射目标须在游戏档案的代号清单内，非法文档立即抛错停止
（与规则文件同一纪律）。观测解析核心用它把 OCR 词条名与部位名适配为
内部代号，使规则字段与游戏语言无关。

格式契约见主设计文档 §4，加载语义与组装规则见 specs/observation/spec.md。
映射是「文字 → 代号」的单向映射，固定值与百分比共用一条文字族代号，由
解析核心按数值后缀的 % 落到具体代号。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agent.rule_lambda.profile import GameProfile


class TextmapError(Exception):
    """字段对照文档缺失或非法。message 之外附带文件路径，便于定位。"""

    def __init__(self, message: str, path: str | Path):
        self.message = message
        self.path = str(path)
        super().__init__(f"{message}（对照文档：{self.path}）")


@dataclass
class Textmap:
    """一份已加载的字段对照文档。stats/slots 为「游戏文字 → 代号」映射。"""

    language: str
    stats: dict[str, str]
    slots: dict[str, str]


_TEXTMAP_KEYS = {"version", "language", "stats", "slots"}


def load_textmap(path: str | Path, profile: GameProfile) -> Textmap:
    """从 JSON 文件加载字段对照文档；缺失或非法时抛 TextmapError（message + 文件路径）。

    校验语义：键集合固定（version/language/stats/slots，缺一多一均非法）；
    version 仅接受 1；两个映射节非空、键与值为非空字符串，且映射值落在档案
    对应的代号清单内（stats 节查 profile.stats，slots 节查 profile.slots）。
    """
    path = Path(path)
    if not path.is_file():
        raise TextmapError("对照文档文件不存在", path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TextmapError(f"对照文档无法读取或解析：{exc}", path) from exc
    if not isinstance(data, dict):
        raise TextmapError(f"对照文档必须是 JSON 对象，实际为 {type(data).__name__}", path)

    keys = set(data)
    missing = _TEXTMAP_KEYS - keys
    extra = keys - _TEXTMAP_KEYS
    if missing:
        raise TextmapError(f"对照文档缺少键：{sorted(missing)}", path)
    if extra:
        raise TextmapError(f"对照文档含未知键：{sorted(extra)}", path)

    version = data["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TextmapError(f"version 必须是整数，实际为 {version!r}", path)
    if version != 1:
        raise TextmapError(f"version 仅接受 1，实际为 {version}", path)

    language = data["language"]
    if not isinstance(language, str) or not language:
        raise TextmapError(f"language 必须是非空字符串，实际为 {language!r}", path)

    stats = _check_section(data, "stats", profile.stats, path)
    slots = _check_section(data, "slots", profile.slots, path)

    return Textmap(language=language, stats=stats, slots=slots)


def _check_section(data: dict, key: str, codes: frozenset[str], path) -> dict[str, str]:
    """校验单个映射节并返回其副本：非空、键值均为非空字符串、值在档案代号清单内。"""
    section = data[key]
    if not isinstance(section, dict):
        raise TextmapError(
            f"{key} 必须是对象（文字 → 代号映射），实际为 {type(section).__name__}", path
        )
    if not section:
        raise TextmapError(f"{key} 映射为空", path)
    for text, code in section.items():
        if not isinstance(text, str) or not text:
            raise TextmapError(f"{key} 的键必须是非空字符串，实际为 {text!r}", path)
        if not isinstance(code, str) or not code:
            raise TextmapError(f"{key} 的映射值必须是非空字符串，实际为 {code!r}", path)
        if code not in codes:
            raise TextmapError(
                f"{key} 的映射值不在档案代号清单内：{text!r} → {code!r}"
                f"（合法代号：{sorted(codes)}）",
                path,
            )
    return dict(section)
