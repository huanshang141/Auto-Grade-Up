# M2.5 执行日志

## 2026-09-06 · 计划制定
- Tried:  两轮拷问（discussion.md）收敛设计树后，按 plan-contract 落 proposal / design / specs×4 / tasks
- Result: 计划工件齐备，8 个任务、每组依赖清晰；契约以工作副本模式先行（D8）
- Now:    等待需求方指令开始执行

## 2026-09-06 · 任务 1.1 档案单次强化成长上限表
- Tried:  社区公开成长档位表查证后录入 profile.json，profile.py 增字段、校验与 growth_max 查表方法
- Result: 4/5 星各录 10 个副词条代号；test_profile.py 新增断言全绿，全量 356 项通过
- 数据来源（2026-09-06 查证）：
  - Genshin Impact Wiki（Fandom）Artifact/Stats 词条档位表：5 星各档单次成长值与
    「4 星 = 5 星 × 0.8」的档位关系（https://genshin-impact.fandom.com/wiki/Artifact/Stats）
  - HoYoLab 单次档位帖（5 星暴击率上限 3.9%、暴击伤害上限 7.8%）
    （https://www.hoyolab.com/article/14568945 、https://www.hoyolab.com/article/228385）
  - GameFAQs 帖（4 星攻击力百分比单次 3.3%~4.7%，独立佐证 0.8 倍档）
    （https://gamefaqs.gamespot.com/boards/270518-genshin-impact/79119349）
  - 本项目夹具互证：L6（4 星暴击伤害 5.0）、L10（4 星攻击力 11、元素充能 5.2、
    元素精通 30=14.9+14.9）、E5（4 星暴击伤害 4.4、元素精通 15、防御力 5.8%→11.1%
    = 5.83+5.25）全部落入 0.8 倍档位表
- 偏差记录：tasks.md 1.1 写「19 代号」，实际只录 10 个——查证确认副词条池仅
  hp/atk/def 三族的固定值与百分比、元素精通、元素充能效率、暴击率、暴击伤害
  共 10 个属性；治疗加成与七种伤害加成只能作主词条、永远不会出现在副词条上，
  录入未查证的数字反而制造假数据。缺表查表抛错（growth_max → ProfileError）
  保证万一机制变动时响亮失败。规格工作副本示例值 2.7（5 星最低档）同步勘正为 3.1
- Now:    需求方指令连跑到 4.1，不再逐任务停等（2026-09-06）

## 2026-09-06 · 任务 1.2 词条值对象扩展（roll_count / pending）
- Tried:  StatValue 增 roll_count（可空键、序列化始终写出）与 pending（True 才写出）；
  from_dict 接受新旧两种形状；validate_artifact 增次数值域与待激活互斥校验
- Result: test_model.py 新增 12 项、test_profile.py 新增 7 项全绿；旧形状 JSON
  加载与新形状 JSON 往返均有断言；全量 379 项通过
- 备注:   主词条序列化保持 {name, value}（契约：主词条不带次数字段）；
  spec 示例形状测试随新契约同步更新
- Now:    进入任务 2.1（规则文件格式修订）
