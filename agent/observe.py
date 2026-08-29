"""观测解析核心（M2）：识别结果集 → 读取结果（ReadResult）。

纯 Python 的「文字之后」全部处理——词条名适配属性代号、数值解析、组装属性
与附属读数（extras）、完整性校验与失败清单。禁止导入 maa：解析核心的输入
输出全是纯数据，一旦导入即被钉在框架部署上，「不连真机验证」随之落空
（理由见 M2 concept.md §3.1，由冒烟测试守卫）。

输入三样：识别结果集（区域键 → 文字框列表）、游戏档案（GameProfile，M1 产物）、
字段对照文档加载产物（Textmap，M2 任务 2.1 交付）。输出读取结果（ReadResult），
含两个读取器（行为契约见 specs/observation/spec.md）：

- 列表页读取器（read_list）
- 强化页读取器（read_enhance，含控制层传递的沿用字段 CarriedFields）

M2 任务 3.x 落地实现；本文件当前仅骨架。
"""
