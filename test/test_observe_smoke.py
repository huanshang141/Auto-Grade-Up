"""冒烟测试：观测侧骨架（解析核心与对照文档加载器）可导入，且不连带拉入 maa。"""

import sys


def test_import_observe_skeleton_does_not_pull_maa():
    import agent.observe
    import agent.textmap

    assert "maa" not in sys.modules
