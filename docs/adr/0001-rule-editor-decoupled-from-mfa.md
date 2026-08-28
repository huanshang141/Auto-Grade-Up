# 规则 GUI 独立于 MFAAvalonia，以 rules.json 文件解耦

- 状态：accepted（2026-08-28）

MFAAvalonia（MaaFramework 通用界面）是纯声明式界面——只渲染 interface.json 里声明的任务与选项，没有插件系统、自定义页面或内嵌网页容器，无法承载结构化条件树编辑器；fork（复制上游仓库自行维护）它则要维护整套 C#/Avalonia 工程，成本不成比例。因此规则编辑器做成独立工具（单文件本地网页），与运行器（MFAAvalonia）、决策机构（Python agent）之间以唯一的规则文件 `config/rules.json` 作为契约：编辑器只读写它，决策机构只读它。这样保留 MFAAvalonia 现成的设备连接、任务启动、日志能力，规则可导入导出，编辑器与运行时互不绑定。

## Considered Options

- 复制改造 MFAAvalonia 增加自定义页面 —— 拒绝：没有扩展点，维护成本不成比例。
- 自研一体化界面（编辑器与运行器合并，直接调用 MaaFramework 绑定库）—— 拒绝：需要重新实现运行器生态的既有能力，工作量最大。
- 独立编辑器 + MFAAvalonia 运行，规则文件解耦 —— 采纳。

调研依据见 `docs/superpowers/specs/2026-08-28-auto-grade-up-design.md` §9。
