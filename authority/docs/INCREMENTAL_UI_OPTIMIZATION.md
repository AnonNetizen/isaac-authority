# 500 万内的增量优化

本轮不启动游戏，不改冻结 MCM/EID，不接入绘制和输入。保留个人设置独立和 `personal-settings-authority-hud-v1`。工作上限固定 5,000,000，其余深度、遍历、路径和对象预算保留。

本轮结论：有限模型的标记与聚合、叶缓存、证据共享均通过对照；真实 MCM/EID 六项初始化仍耗尽 500 万，候选未通过真实门槛。减少字段扫描尚未带来整体性能改善，不进入绘制捕获或菜单导航。

最终 DLL SHA-256：`4f29cec6e300906697f488b6828b7e3b17340310abcae25d9c2446170a85150e`。私有 ABI 与模式保留；证据格式为 `isaac-incremental-versions-4`，通过 `cache_sites` 和 `site_ref` 无损展开。

原 5M DLL `5342f69d1d92961c0b088ac1a9a14290a3185edbdd2cc08dee878c9b3d892b29` 和源码已保存到 `reports/ui-incremental-5m-preserved`，逐文件 SHA 记录在 `files.json`。原清单和失败报告保留。

## 第一步：区分覆盖失效与单调增加来源

标记调用只合并来源集合；纯来源增加不能使已经完成的标记失效。对象保留两个版本：完整内容版本供 aggregate 使用；覆盖版本供 mark 使用。实际字段写入、结构变化、upvalue 写入和 join 都增加覆盖版本，并向所有保守父边传播。仅在已审计的 mark 内部 union 和 shape union 中使用单调规则；普通 VM 赋值和指令完成仍按可能覆盖处理，不把它们当成纯来源增加。

复用仍要求同一对象、同一来源集合和同一覆盖版本，并引用完整遍历事件。总版本有变化时明确记录单调来源扩展；聚合结果仍按完整版本失效。未知副作用不享受该规则。预算收费覆盖维护、失效及证据；不删除普通生产者图或重新编号。

先跑旧 15 项和新 4 项来源 oracle：每次传播在同一 VM 与全量算法逐 TValue/shape 比较，再比较未修改 Lua 的返回值、字节和错误。完整图和缓存事件需重复一致。通过后才跑真实 22 项清单的两次完整执行。

## 后续顺序

根据本步账本再决定逐字段覆盖检查点和未改动子结构复用。任何局部复用必须保留别名、循环、结构变化、upvalue、深度和遍历上限证明；不能通过少报工作或调大上限获取通过。真实初始化尚未全部通过时，绘制捕获和菜单导航保持未开始。

## 第二步：完整标量叶结构检查点

第一步的模型对照通过，但真实 MCM/EID 六项仍耗尽 500 万；真实执行没有命中跨来源扩展复用。该候选及源码已独立保存，不能将小模型收益当成真实门槛通过。

第二步只缓存完整访问过的标量表与仅含标量 upvalue 的 Lua 闭包。完成事件记录字段版本、实际 upvalue 身份及其覆盖版本、真实深度和逻辑遍历次数。父结构被其他字段修改后，未改动叶结构可以复用其已完成证据。含子对象的结构、C 闭包和循环中的局部遍历不享受此复用；仍执行计费的完整遍历。别名的第二次访问仍遵守本轮 seen 集合。

复用时检查覆盖版本、来源和完成事件，并把原逻辑访问次数累计到 16,384 上限，按当前嵌套位置重新检查 24 层深度限制。节约的是执行扫描工作，不能缩减逻辑结构规模。建立检查点、查询和证据序列化都入账。额外冻结四个功能反例，要求实际命中叶缓存后与全量算法逐字段比较；深度边界另做未启用 oracle 的参考拒绝对照。

## 第三步：保留全部消费，共享重复位置证据

第二步的 23 项来源对照与两个实际缓存结构边界通过，真实六项仍失败。独立测量发现扫描虽减少，证据记录导致时间和内存上升；未作为性能成功交付。旧叶候选、测试宿主早期失败和边界输入保留。8200 元素会扩容到 16384 个数组槽，首次叶标记本身就超逻辑上限；新独立边界清单改用两个 8192 槽叶结构，每个可完成，组合根为 16387 次访问，仍应拒绝。

第三步仅把事件中重复的源码、原型、指令及激活上下文存成共享位置表。每个帧的 activation/code 固定，按实际 pc 缓存位置引用；帧重建和尾调用替换创建新的位置缓存。每次消费仍有独立事件编号和位置引用，维护、建立和查询均收费。位置表最多 65536 条；原事件 65536 上限仍保留。

冻结案例通过完整来源 oracle 后，再把新事件全部展开，与旧叶候选逐事件、对象版本、返回来源及完整生产者图比较。不能忽略激活上下文，也不能合并不同位置或删除消费。此步骤通过后再重跑真实清单和同预算测量。

## 命令行入口

以下命令从工作区根目录执行；报告目录必须不存在。游戏资源仍为本地哈希依赖，不随包分发。

```powershell
pwsh -NoProfile -File authority/tools/build.ps1 -BuildDirectory build-ui-incremental-factored -RuntimeOutputDirectory build-ui-incremental-factored-release/Release -TraceResearch -IncrementalUiResearch -IncrementalWorkLimit 5000000 -SkipTests
python authority/tools/run_incremental_ui.py --binary authority/build-ui-incremental-factored-release/Release --output authority/reports/optimization-repeat --phase all --work-limit 5000000 --oracle-manifest authority/research/ui_incremental_oracle_v5.json
python authority/tools/run_incremental_boundaries.py --binary authority/build-ui-incremental-factored-release/Release --output authority/reports/optimization-boundary-repeat
```

`--phase all` 的全量对照还依赖工作区保留的旧 bounded DLL。研究包的独立搬迁复现使用专用入口，输出模型完整图与缓存的比对、真实清单的功能结果及逐文件校验：

```powershell
python authority/tools/reproduce_incremental_optimization.py --archive authority/artifacts/isaac-authority-ui-incremental-0.1.4.zip --output authority/reports/optimization-relocated-repeat
```

研究包是实验候选，初始化门槛未过时不能当作联机修复或可用菜单原型。真实运行的完整失败前缀仍可能受 Lua 遍历顺序影响而不同；不通过重新编号或去掉证据制造相同结果。下一步优先解决按需活跃性分析重复搜索，以及字段索引随结构写入反复重建；继续保留完整来源对照和 500 万上限。

## 验收与实测

新来源清单 22 个功能项和 1 个边界项按预期通过，每轮 2,435 次逐来源核对；C API upvalue 对照一致。两次完整模型图、版本与缓存证据一致。证据共享的全部展开事件与旧叶候选一致。独立 C API 探针验证：缓存叶位于过深位置时拒绝；两个已完成的 8192 槽叶组合后逻辑遍历超过 16384 时拒绝，未绕过结构限制。

真实 22 项清单运行两次：10 个其他功能项通过，6 个 MCM/EID 初始化失败，6 个安全拒绝诊断通过。安全拒绝不计作兼容通过。完整真实失败前缀仍不稳定，仅功能结果重复一致。历史 13、31、24、42、56 共 166 项按原 DLL/原预期回归，完整案例与历史相同；基础检查通过。31 个存档、配置及实验基线审计文件未发生本轮变化，143 个模组 Lua、2 个 J460 脚本和 64 个本地资源哈希一致。

下表是独立进程各两次的中位数，比较未共享证据的叶候选与最终共享位置候选。时间从未追踪的 bootstrap 完成测到初始化拒绝，排除报告序列化。峰值包含研究宿主、资源和报告，并非单独追踪内存，也不是游戏每帧开销。

| 项目 | 叶候选 | 共享位置候选 |
| --- | ---: | ---: |
| MCM 到预算终点 | 3.89 秒 | 3.59 秒 |
| EID 到预算终点 | 5.33 秒 | 5.80 秒 |
| MCM 停止时工作集 / 全程峰值 | 191 / 514 MiB | 170 / 419 MiB |
| EID 停止时工作集 / 全程峰值 | 294 / 770 MiB | 266 / 640 MiB |

证据共享降低了叶候选的内存；EID 耗时未改善且两次样本有波动。原完整根候选的另一批实测约为 MCM 2.10 秒、EID 3.15 秒，仍比当前候选少耗时、少占内存，但也在较早位置拒绝。各候选在不同位置停止，不能将这些数字报告为等工作量加速。完整账本与首个失败位置见 `reports/ui-incremental-optimization-delivery.json`；所有阶段的二进制、失败输入和报告保留。
