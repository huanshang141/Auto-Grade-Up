"""冒烟测试：agent.rule_lambda 可作为纯包导入，且不连带拉入 maa（spec §12 红线）。"""

import sys


def test_import_rule_lambda_does_not_pull_maa():
    import agent.rule_lambda

    assert "maa" not in sys.modules
