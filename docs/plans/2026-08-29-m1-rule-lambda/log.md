# M1 执行日志

## 2026-08-29 · 执行前置
- Tried:  按需求方指令，规划工件先行入库
- Result: 两笔提交——d152565（ADR-0003/0004 + spec 主文档 + CONTEXT.md + AGENTS.md 定案）、
          ed7a03f（M1 计划 design/proposal/三份契约）
- Now:    assets/resource/model/*（OCR 模型二进制）保持未跟踪，不属于规划工件

## 2026-08-29 · Task 2.1
- Tried:  test_model.py 用例 "+ 19" 期望 parse_level 抛 ValueError
- Result: failed——模块约定「先去空白再解析」，去空白后 "+ 19" 即 "+19"，是合法等级文本
- Now:    改用例为 parse_level("+ 19") == 19；实现零改动，37 passed
- Convention: 所有 OCR 文本解析函数一律先 strip_spaces 再解析，含数字内部的空格；
          形状校验错误统一抛 ValueError，值域校验错误（任务 2.2 起）抛
          ArtifactValidationError / ProfileError


## 2026-08-29 · Task 1.1
- Tried:  先写 test/test_smoke.py 再建骨架（TDD 红绿两步）
- Result: 红灯 `ModuleNotFoundError: No module named 'agent.rule_lambda'` → 建骨架后 `1 passed`
- Now:    requirements-dev.txt 钉主版本（pytest>=8,<9 / jsonschema>=4,<5，实装 8.4.2 / 4.26.0）；
          pytest.ini 设 testpaths = test；agent/__init__.py 为空文件保证导入不拉 maa；
          rule_lambda 五文件仅 docstring
- Convention: `python -m pytest` 一律从仓库根运行（cwd 入 sys.path 使 `import agent.rule_lambda`
          可用，裸 `pytest` 无此保证）；导入 agent.rule_lambda 不得连带导入 maa，
          由 test_smoke.py 守卫
