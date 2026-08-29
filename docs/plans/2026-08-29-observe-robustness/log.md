# M2 补强执行日志

> 本文件夹的变更记录；永不删除。计划与决策见 `proposal.md`、`design.md`、
> `tasks.md`，拷问结论见 `discussion.md`。

## 2026-08-29 · Task 1.1
- Tried:  四目录合并一步到位（mv pic2/3/4/*.png pic/ 后 rmdir），处理脚本
          只改来源常量与断言、fixture_stem 逻辑不动（「图N」映射规则与
          批次无关，合并后依然成立）
- Result: reference/pic/ 27 张（fig1~fig7、L1~L8、E1~E3、L9~L13、E4~E7），
          pic2/pic3/pic4 已删除；重跑处理脚本自检 27 张通过，原 18 张
          夹具逐字节不变（幂等），新增 9 张夹具待入库；README 三处口径
          更新（投放方式、扩测路径、验收记录标题与 E6 行）
- Now:    现行文档的 picN 引用仅剩 tasks/design（任务与决策记录本身）与
          discussion（声明不保持现行口径的历史底稿），均保留原样
- Convention: reference/pic/ 为唯一截图来源目录，后续补拍批次直接放入、
          不再开新目录；扩测时只调整 prepare_fixtures.py 的张数断言
