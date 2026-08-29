"""冒烟测试：观测侧骨架（解析核心与对照文档加载器）可导入，且不连带拉入 maa。

断言在独立子进程中做：离线全链路测试（第二层）本就允许导入 maa，同进程
先跑过的测试会污染 sys.modules，子进程保证守卫从干净状态开始（M1 已有
独立进程验证绑定可加载的先例）。
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_import_observe_skeleton_does_not_pull_maa():
    code = (
        "import sys; import agent.observe, agent.textmap; "
        "assert 'maa' not in sys.modules, sorted(m for m in sys.modules if m.startswith('maa'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO_ROOT, timeout=60
    )
    assert result.returncode == 0, result.stderr
