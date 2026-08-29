# M2 执行日志

## 2026-08-29 · Task 2.1
- Tried:  测试先行：test_textmap.py 24 例，红灯为 ImportError（骨架无 Textmap）
- Result: 落地数据文件与加载校验器后 test_textmap.py 24 passed、全量 232 passed
- Now:    数据文件 assets/resource/genshin/textmap/zh_cn.json（词条文字族 16 +
          部位 5，与主设计文档 §4 示例一致）；Textmap(language, stats, slots)，
          映射为「文字 → 代号」单向；TextmapError(message, path)，str(exc) 形如
          「……（对照文档：路径）」；校验顺序：文件缺失/损坏 → 对象 → 键集合 →
          version → language → 映射节（非空、键与值非空字符串、值在档案清单内；
          stats 节查 profile.stats、slots 节查 profile.slots，跨节代号被拒）
- Convention: 非法样例经 tmp_path 临时文件构造（任务 Touch 清单不含夹具目录）；
          测试内 GENSHIN_STAT_TEXTS/GENSHIN_SLOT_TEXTS 常量与真实文档断言相等，
          文档改动须同步契约与该常量；language 只做结构校验（非空字符串）不做
          取值校验——语言不符由启动自检的锚点文字识别发现（spec §4）

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
