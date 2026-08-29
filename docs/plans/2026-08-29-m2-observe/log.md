# M2 执行日志

## 2026-08-29 · Task 1.1
- Tried:  版本对齐核对（契约前置）——MFAAvalonia 最新发布 v2.16.0（2026-08-25），
          其 csproj 钉 Maa.Framework.Runtimes 5.12.3（原生二进制）；PyPI 官方
          Python 绑定发行名为 MaaFw，恰好发布 5.12.3，与打包版本完全一致
          （PyPI 同名包「maa」latest 0.0.3 与框架无关，不可用）；wheel 形如
          py3-none-win_amd64，任意 Python 3 可装（本机 3.13 实装验证）
- Result: 测试先行红灯 ModuleNotFoundError: No module named 'agent.observe'
          → 建骨架后全量 208 passed（基线 207 + 新冒烟 1）；pip install 实装
          MaaFw 5.12.3、Pillow 12.3.0（连带传递依赖 maaagentbinary 1.0.1、
          numpy 2.5.2、strenum 0.4.15）；另以独立进程导入 maa 模块验证绑定可加载
- Now:    requirements-dev.txt 钉 MaaFw==5.12.3（maa 绑定，具体版本）与
          Pillow>=12,<13（钉主版本，任务 4.1 用）；agent/observe.py 与
          agent/textmap.py 仅 docstring，目录与 concept §8 一致；
          test_observe_smoke.py 导入两骨架后断言 "maa" 不在 sys.modules
- Convention: 依赖一律写 PyPI 发行名（MaaFw，导入名为 maa），任务契约行文的
          「maa」即此包；maa-free 红线只约束 agent 模块的导入行为，开发依赖
          装进环境不构成违反，由冒烟测试守卫
