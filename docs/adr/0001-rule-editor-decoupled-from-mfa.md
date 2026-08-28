# 规则 GUI 独立于 MFAAvalonia，以 rules.json 文件解耦

- 状态：accepted（2026-08-28）

MFAAvalonia（MaaFramework 通用 UI）是纯声明式界面——只渲染 interface.json 里的任务与选项，没有插件系统、自定义页面或内嵌 WebView，无法承载结构化条件树编辑器；fork 它则要维护整套 C#/Avalonia 工程，成本不成比例。因此规则编辑器做成独立工具（单文件本地网页），与运行器（MFAAvalonia）、决策机构（Python agent）之间以唯一的规则文件 `config/rules.json` 作为契约：编辑器只读写它，agent 只读它。这样保留 MFAAvalonia 现成的设备连接、任务启动、日志能力，规则可导入导出，GUI 与运行时互不锁死。

## Considered Options

- fork MFAAvalonia 增加自定义页面 —— 拒绝：无扩展点，fork 维护成本不成比例。
- 自研一体化 GUI（编辑器 + 运行器直调 MaaFramework 绑定库）—— 拒绝：需重新实现运行器生态的既有能力，工作量最大。
- 独立编辑器 + MFAAvalonia 运行，规则文件解耦 —— 采纳。

调研依据见 `docs/superpowers/specs/2026-08-28-auto-grade-up-design.md` §9。
