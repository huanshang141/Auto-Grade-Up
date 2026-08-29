"""决策机构命令行入口：python -m agent.rule_lambda <子命令>。

唯一命令行入口；M3 运行时接线时在此追加子命令。子命令失败以非零退出码
结束并向 stderr 写明原因。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent.rule_lambda.profile import ProfileError, load_profile
from agent.rule_lambda.schema import export_json_schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent.rule_lambda", description="决策机构（rule_lambda）命令行"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    export = commands.add_parser("export", help="按游戏档案导出 JSON Schema 生成物")
    export.add_argument("profile", help="游戏档案 JSON 路径")
    export.add_argument("output", help="生成物输出路径")

    args = parser.parse_args(argv)

    if args.command == "export":
        try:
            profile = load_profile(args.profile)
        except ProfileError as exc:
            print(f"游戏档案加载失败：{exc}", file=sys.stderr)
            return 1
        schema = export_json_schema(profile)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return 0
    raise AssertionError(f"不可达的子命令：{args.command}")


if __name__ == "__main__":
    sys.exit(main())
