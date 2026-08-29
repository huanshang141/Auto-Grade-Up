# M1 执行日志

## 2026-08-29 · Task 1.1
- Tried:  先写 test/test_smoke.py 再建骨架（TDD 红绿两步）
- Result: 红灯 `ModuleNotFoundError: No module named 'agent.rule_lambda'` → 建骨架后 `1 passed`
- Now:    requirements-dev.txt 钉主版本（pytest>=8,<9 / jsonschema>=4,<5，实装 8.4.2 / 4.26.0）；
          pytest.ini 设 testpaths = test；agent/__init__.py 为空文件保证导入不拉 maa；
          rule_lambda 五文件仅 docstring
- Convention: `python -m pytest` 一律从仓库根运行（cwd 入 sys.path 使 `import agent.rule_lambda`
          可用，裸 `pytest` 无此保证）；导入 agent.rule_lambda 不得连带导入 maa，
          由 test_smoke.py 守卫
