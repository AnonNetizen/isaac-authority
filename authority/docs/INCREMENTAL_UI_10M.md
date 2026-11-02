# 1000 万上限试验

用户在 2026-10-11 明确要求将上限改为 10,000,000，检查真实 MCM/EID 是否仍超限。本次是独立预算档，不继续修改追踪算法；500 万源码、二进制、清单和 0.1.4 研究包保留。默认构建档仍为 500 万，1000 万须显式指定。

要求继续保留：冻结旧模组源码不变、个人配置独立、奖励跟随主机，以及 `personal-settings-authority-hud-v1`。本次只验证初始化与直接契约调用，不启动游戏，不推进绘制捕获、菜单导航、世界接管或网络。

## 修改范围与验证方式

生成的 Lua 追踪源码逐文件比较，只有 `bounded_cfg.hpp` 中 `work_limit` 的 5,000,000 → 10,000,000 常量不同。私有 ABI `ia-lua533-slice3-ui-incremental-1` 保持，运行入口检查 DLL 导出的实际预算。32 条路径、8 个未解析条件、4096 基本块、16384 逻辑访问、24 层标记深度、65536 证据事件及其他原生能力/资源限制不变。

新冻结真实清单为 `research/ui_incremental_suite_10m_v1.json`。原 22 个案例的源码、选项和检查均保持，原来两项 500 万解析诊断在 1000 万下按未修改 Lua 的原返回值作为功能项。新增两项独立 1000 万解析拒绝测试，各执行四次 2,500,050 个分号的加载，保持单块 4 MiB 上限；被 `pcall` 捕获的预算故障也不得继续执行。

23 个有限模型仍与未修改 Lua、历史全量追踪及同 VM 来源 oracle 对照。两个缓存结构边界仍须拒绝。真实 24 项按原案例分别在独立进程运行，参考 Lua 两次、研究 Lua 两次。逐例执行减少 Python 同时持有整份大型报告的内存，每次仍使用完整相同的模型后端和新上下文；未验证同一宿主中的跨案例状态泄漏。

六个实际初始化案例同时测量从未追踪 bootstrap 完成到初始化成功或首个拒绝的时间、停止时工作集、全过程工作集峰值。每项只有两个样本，排除报告序列化耗时；峰值包含宿主、资源和证据，不代表游戏每帧开销。完整报告与费用账本原样保留，不删除或重新编号生产者以制造稳定证据。

## 可重复命令

从工作区根目录执行，新的输出目录须不存在。冻结游戏资源是本地只读依赖。

```powershell
pwsh -NoProfile -File authority/tools/build.ps1 -BuildDirectory build-ui-incremental-10m -RuntimeOutputDirectory build-ui-incremental-10m-release/Release -TraceResearch -IncrementalUiResearch -IncrementalWorkLimit 10000000 -SkipTests
python authority/tools/run_incremental_ui.py --binary authority/build-ui-incremental-10m-release/Release --output authority/reports/10m-oracle-repeat --phase oracle --work-limit 10000000 --oracle-manifest authority/research/ui_incremental_oracle_10m_v1.json
python authority/tools/run_incremental_boundaries.py --binary authority/build-ui-incremental-10m-release/Release --output authority/reports/10m-boundary-repeat --work-limit 10000000 --manifest authority/research/ui_incremental_boundaries_10m_v1.json
python authority/tools/run_incremental_10m_experiment.py --binary authority/build-ui-incremental-10m-release/Release --output authority/reports/10m-real-repeat --prior-oracle authority/reports/10m-oracle-repeat/oracle-result.json
```

入口先验证对应 DLL、模型清单和预算的通过记录，真实功能失败与安全拒绝分开记录。原始 500 万快照在 `reports/ui-incremental-10m-baseline/files`，包含源码、工具、原清单、二进制及逐文件哈希。个人存档和配置仅作前后哈希审计，不执行恢复或覆盖。

## 实测记录

1000 万仍不足以通过真实初始化。六项各执行两次，结果如下。组合加载按冻结清单先载入 MCM，尚未完成 MCM 初始化便停止，不能据此判定组合中的 EID 已被完整执行。

| 案例 | 两次工作量 | 首个限制 | 初始化到停止时间中位数 |
| --- | --- | --- | ---: |
| MCM 中文 | 7,217,596 / 7,282,505 | 65,536 条证据事件 | 6.14 秒 |
| MCM 英文 | 7,190,479 / 7,277,058 | 65,536 条证据事件 | 6.29 秒 |
| EID 中文 | 10,000,000 / 10,000,000 | 工作量上限 | 9.85 秒 |
| EID 英文 | 10,000,000 / 10,000,000 | 工作量上限 | 10.13 秒 |
| 组合中文 | 7,096,797 / 7,095,838 | 65,536 条证据事件 | 6.18 秒 |
| 组合英文 | 7,203,476 / 7,121,871 | 65,536 条证据事件 | 6.15 秒 |

停止时工作集约 222–238 MiB（MCM/组合）及 317 MiB（EID），全过程峰值约 574–598 MiB 及 824–825 MiB。实际报告含每次测量；这些是命令行研究初始化成本，不是游戏运行一帧的成本。与 500 万停止在不同位置，不能作为等工作量性能对照。

23 项模型、2,435 次来源核对及 C API upvalue 对照通过，两个结构边界仍按预期拒绝。模型普通结果、错误、返回来源、完整生产者图和缓存证据与保存的 500 万版本逐例一致。新真实清单共 24 项：12 个其他功能项通过，6 个真实初始化功能项失败，6 个安全拒绝按预期复现。安全拒绝不计入功能兼容。

每次实际工作账本总和等于 `used`，不超过 1000 万。两个新增解析负例均停在 1000 万，预算故障后阻止进一步执行，`pcall` 不能恢复。143 个模组 Lua、2 个 J460 脚本、64 个本地资源，以及 31 个审计的存档/配置/实验基线文件前后哈希一致。37 个历史保留文件、33 个本轮快照及原 0.1.4 包校验通过。

功能结果可重复，但完整真实报告仍非全部相同；EID 中文两次分别停在字段索引扫描和堆图遍历的计费操作，不把失败入口变化视为稳定证据。第一版批量宿主过于严格，把失败入口变化作为中断条件，停在 EID 中文；该宿主及所有报告保留在 `reports/ui-incremental-10m-real`。修正仅改变报告处理，研究 DLL 不变，随后完整清单重新执行两次。

新的完整结果入口为 `reports/ui-incremental-10m-real-v2/experiment.json`，逐文件和预算档不变性核对为同目录的 `verification.json`；模型结果为 `reports/ui-incremental-10m-oracle/oracle-result.json`；结构边界为 `reports/ui-incremental-10m-boundaries/boundaries.json`。

DLL SHA-256：`859fe205b37c7a4c35bc16f46f224ec3976b35551864dd1fe4a5eca79c0fe140`。冻结清单 SHA-256：`da5339138fb5f610c7216c6da070196b6d09d03f49f70a1283996f1958817f3f`。

账本显示 EID 的字段索引排序占约 356 万（约 35.6%），MCM 的活跃性指令/边搜索占约 294 万（约 40%），并存在独立的证据事件容量瓶颈。后续应分别研究字段索引增量维护、活跃性搜索复用和保留完整消费证明的有界证据表示；本次没有修改这些机制或其他预算。真实初始化全部满足功能要求之前，不能进入真实 HUD 和导航阶段，也不能称为可用联机修复。本轮是独立预算试验，没有改写旧研究包或制作新的整体研究包。
