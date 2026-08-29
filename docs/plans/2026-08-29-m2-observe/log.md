# M2 执行日志

## 2026-08-29 · Task 4.3
- Tried:  先读 maa 绑定源码定 API（post_recognition(JRecognitionType, JRecognitionParam,
          BGR ndarray) → TaskJob → task detail → node detail → RecognitionDetail）；
          DbgController 不可用（wheel 未附带 MaaDbgControlUnit 库）→ 直接
          MaaTaskerBindResource 只绑 Resource，离线识别可跑（实测）。转储取
          filtered_results——replace 纠错只作用于该结果集（all 为原始识别）；
          replace 的匹配是正则（首个版本把等级节点的「.」写成正则任意字符，
          「+0」被整串清空，须转义为「\\.」）；build_param 首版漏传 expected，
          套装过滤不生效，靠「探针手工传参有效、录制不生效」定位
- Result: 18 份转储入库；形状断言通过（区域键集合、文字框三键）；解析核心
          对 18 份转储验证 17 张 ok、fig5 按预期失败（素材下拉弹窗遮住主词条名
          与副词条名，5.1 按可见范围放宽）；识别质量异常仅 fig5 fodder_tier 空
- Now:    随录制实测落地的调优（design D4 路径）：多行区域（两界面主词条/副词条、
          列表页套装）退回检测模式 only_rec=false；replace 纠错四处——两个等级节点
          去尾部「.」「。」、列表副词条去行首「·」、强化副词条去 ①~⑤ 与行首
          ①误读的「0」（后随非数字非小数点才删）、面包屑去「。」并归一「／√」
          为「/」；列表套装 roi 上扩覆盖 4 星布局（套装块上移与 5 星第 3/4 副词条
          槽重叠）+ expected 正则滤行 + 读取器取最上一行；契约「流水线节点约定」
          行按此修订；解析核心 _join_text 改为按行分组拼接（修 fig2/fig4 主词条
          名值框高低差导致的顺序颠倒）
- Convention: 读取器归属——fig1/fig3/fig6/fig7 与 L1…L8 走列表页节点，fig2/fig4/fig5
          与 E1…E3 走强化页节点（fig6/fig7 为排序设置截图但面板完整可读，如实入库）；
          maa 版本 5.12.3 打印并记此；真实读数抽验：L5 主词条 3967（千位逗号）、
          L6 四星 2 条副词条 + 套装千岩牢固、L1 第 4 行「生命值+269（待激活）」整行丢弃

## 2026-08-29 · Task 4.2
- Tried:  坐标标定走网格叠加读图（全图 50px 网格 → 右栏 2 倍精细网格 → 挂锁区 8 倍
          像素网格）；挂锁模板首裁偏（带进右侧背景），按像素网格重裁
- Result: observation.json 15 节点（8+7 与区域键一一对应）；stars/lock 模板图自 fig1
          裁剪入库（23×23、26×30，720p 无损缩放链路符合协议要求）；json 结构断言通过
          （节点名清单、13 OCR + 2 TemplateMatch、无 action/next、OCR threshold 0.3）
- Now:    720 基准 roi——列表页 name(885,78,250,38)、slot(885,118,120,32)、
          main(885,175,180,58)、level(885,280,70,30)、substats(898,315,200,102，
          x 从 898 起以避开行首圆点)、set(883,418,140,26)、stars(883,232,130,30)、
          lock(1118,276,34,38，避开右侧星标按钮)；强化页 breadcrumb(90,16,300,30)、
          main(778,150,480,40)、level(778,84,75,32)、exp(1145,94,125,26)、
          substats(775,200,480,142)、mora(780,658,200,36)、fodder_tier(790,498,215,32)
- Convention: 界面事实两则入档——(1) 列表页主词条为名上值下两行、强化页主词条名左值右
          同行且相距约 400px，OCR 均拆成多个文字框，解析核心新增「按纵坐标聚行、按
          阅读序拼接」（行中心距容差 14px），读取器测试补多框成行用例；(2) 摩拉余额在
          右上角、需要摩拉数在强化按钮左侧，单识别区域无法同时覆盖，第一版 mora 区只读
          需要数，主 spec §6 摩拉区行已按此修订

## 2026-08-29 · Task 4.1
- Tried:  UID 定位用右下角裁剪放大读图，两界面位置一致（1080p 原图约 x1697-1860、
          y1055-1074）；幂等以两轮处理后的全量校验和比对验证（一致）
- Result: 18 张夹具入库（fig1…fig7 + L1…L8 + E1…E3），脚本逐张自检尺寸与遮挡区全黑；
          遮挡矩形 720 坐标 (1107,695)-(1275,720)，上方避开「强化」按钮，目检按钮完好、
          UID 不可见；incoming/ 暂存目录入库 .gitkeep、内容 gitignore
- Now:    处理可重复执行：重跑覆盖输出，不改动 reference/
- Convention: 命名口径——pic/ 的「图N-*」主干映射为 figN（与 4.3 转储 fig<N>.json 对齐），
          pic2/ 沿用原名主干

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
