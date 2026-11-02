# 当前实验进度

最新实验阶段见 [冻结模块入口](docs/FROZEN_MODULE_RESULTS.md)，版本入口为 [frozen_module_candidate_v1.json](research/frozen_module_candidate_v1.json)。这是部分候选，`gate_passed=false`；运行 `python -B authority/tools/verify_frozen_modules.py` 只校验文件及未通过结论。前一已验收候选仍是 [compact_value_candidate_v1.json](research/compact_value_candidate_v1.json)。

写屏障、消费者读取集合和数字依赖索引继续通过回归。直线式模板已绑定实际读取时的值、版本和调用实例，12 项参数复核与原版 Lua 一致；7 项未解析诊断、2 项原生恢复/拒绝、8 项扰动及 129 项回归达到各自预期。调用者生产来源、函数摘要、路径和跨帧来源仍待补齐，缓存和主机投影保持关闭。旧模组不改、个人配置独立、奖励跟随主机的完整目标继续保留。

已封存的稳定读取集合基线仍由 `research/boundary_current.json` 指向；后续实验指针 `research/boundary_next.json` 与本页可以更新，不放入历史不可变文件清单。未启动游戏或验证真实 MCM/EID。

2026-10-16 按用户要求执行了[独立无配额测量](docs/BOUNDARY_UNCAPPED_20261016.md)：百万次读取的可选值观察为 50.02 秒，关闭该观察而保留读取集合为 0.47 秒，结果一致。该样本内存保持较低，CPU 热路径仍需优化。真实 MCM/EID 新架构入口分别缺少模块加载与 Game()，完整初始化未完成。正式上限和候选指针未改。

随后恢复正式上限完成紧凑记录优化：读取时不构造/序列化 JSON，未引用的记录原地更新，已引用记录保留旧版本。2 万次开启观察的配对短样本由约 0.730 秒降到 0.0219 秒，工作计数和输出相同；20 万次约 0.204 秒、460 万工作单位。252 组编码/容量交叉核对及大字符串缩容检查通过；24 项分类验收、8 项扰动拒绝及 129 项回归重复通过。真实 SDK、调用摘要、主机贡献及长期会话历史仍未完成，没有运行新的无配额长测。

新阶段保留原 Lua require、冻结搜索器和主客独立缓存，支持受控 dofile/include；41 项中 32 项模型功能及 8 项恢复/拒绝达到预期，真实 FilepathHelper 的 1 项仍失败。新增关闭上下文的模块审计代次隔离。153 项旧回归通过。MCM 的旧“未知模块”已推进到 filepathhelper.lua:387 的 Sprite()；EID 仍停在 Game()，组合加载未完成。保留全部失败，没有把这项改成预期拒绝，也没有提供空对象通过。
