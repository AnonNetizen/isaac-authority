# 1000 万内的字段索引与证据候选

按 `INCREMENTAL_UI_10M_OPTIMIZATION_PLAN.md` 顺序实施：字段索引 → 无损证据编码 → 实际前缀比较收费 → 首次失败原因保留。工作上限始终为 10,000,000；没有启动游戏、改变冻结模组源码或写入个人存档。个人配置和主机奖励规则 `personal-settings-authority-hud-v1` 保持。

本阶段完成两个机制的代码及命令行验证，真实初始化仍未通过；不能据此进入真实 HUD、菜单导航或称为联机修复。

## 字段索引

有序哈希索引按键维护。值覆盖保留槽位，存在性变化只更新对应键；数组仍遍历全部原槽位，包括 nil。实际扩容明确重建；Lua 哈希冲突导致节点搬移时，用原槽位和规范键核对并修正地址。访问顺序保持原数组顺序及规范哈希键排序。维护、实际有序比较、存储、复制和清理均计入账本。

新增四个冻结案例，覆盖碰撞搬移、删除重插、数组 nil/混合键、`__newindex` 重定向及缓存方法。与未修改 Lua 对照普通结果和来源；逐次将索引与全量枚举的键和实际地址核对。原 23 项及新 4 项均通过，共 18,005 次来源核对。全部生产者图、对象版本和消费记录与原 1000 万增量 DLL 完全一致；实现维护计数及费用可随 Lua 哈希布局变化，独立记录。

真实 24 项两次复测中，12 个其他功能项通过、6 个安全拒绝正确、6 个实际初始化仍失败。EID 从耗尽 1000 万转为在约 887–889 万时触达旧 65,536 条消费上限，未成为兼容通过。

## 无损证据编码

MCM 原 65,536 次消费约对应 5,005 个稳定描述。稳定部分按完整字节共享，使用记录保留描述编号、epoch、位置及逻辑访问前后值；逻辑事件号仍是原顺序的一基编号。缓存命中只在对象/覆盖版本、完成事件、使用深度及相关生产者版本都满足条件时复用描述。验证模式独立重建预期事件，再逐字段比较；每次使用仍收费。

旧 65,536 **逻辑消费**上限保留在历史 DLL。新候选明确改为 65,536 个物理描述、65,536 个位置和 64 MiB 编码字节，同时每次逻辑消费受固定 1000 万费用约束。没有宣称原逻辑条数限制保持。编码字节按描述规范文本的两份存储与每次 24 字节使用记录核算，不能代表整个进程内存。未知引用、非完整操作数、容量超限都会使存储永久拒绝本上下文后续写入。

报告格式为 `isaac-incremental-versions-5`，通过 `EvidenceEvents` 按原顺序完整展开。字典共享仅是存储规则，不用于证明两个游戏操作语义相同。27 项模型的普通结果、返回来源、完整生产者图，以及展开后全部事件、对象版本和原有计数均与字段索引候选一致。没有删除消费或重新编号生产者。完整模型图及编码证据重复一致，费用账本的差异原样保留。

## 两次修正

初版比较按完整字符串长度保守收费，即使早期字节已不同也收取整串成本，真实运行因此更早耗尽预算。修正版按每个实际访问的 64 字节块先收费，再比较，保持与 `std::string` 的字节序相同。测试包含中文、内嵌零、128/255 字节和长共同前缀，共 81 对比较。

第二个问题是模组捕获异常后再次调用存储，通用“已失败”错误覆盖首次原因。最终版保存首次原因，后续拒绝继续返回该原因；既不继续保存，也不伪造完成结果。

存储本体 8 项测试通过：70,000 次不同使用上下文逐条完整还原、65,536 描述边界、64 MiB 字节边界、未知引用、操作数范围及上下文所有者、上下文隔离、1000 万工作量停止，以及字节序比较。两个缓存结构探针仍在 24 层深度/16384 逻辑访问边界拒绝。

成功上下文的紧凑报告构建收费；已拒绝上下文只导出已捕获的诊断前缀，不恢复执行。CLI 的 JSON 写盘和 Python 外部核对不计作游戏模拟工作量，不代表真实渲染阶段的解码成本已验证。

## 可重复入口

从工作区根目录执行。新输出目录须不存在；实际游戏的图片/字体仅作为本地只读哈希依赖。历史全量 oracle DLL 也必须保留。

```powershell
pwsh -NoProfile -File authority/tools/build.ps1 -BuildDirectory build-ui-incremental-encoded -RuntimeOutputDirectory build-ui-incremental-encoded-v3-release/Release -TraceResearch -IncrementalUiResearch -IncrementalWorkLimit 10000000 -SkipTests
python authority/tools/run_incremental_ui.py --binary authority/build-ui-incremental-encoded-v3-release/Release --output authority/reports/encoded-model-repeat --phase oracle --work-limit 10000000 --oracle-manifest authority/research/ui_incremental_oracle_encoded_v1.json
python authority/tools/verify_compressed_evidence.py --before authority/reports/ui-incremental-index-oracle --after authority/reports/encoded-model-repeat --output authority/reports/encoded-expansion-repeat.json
& authority/build-ui-incremental-encoded-v3-release/Release/authority-incremental-evidence-tests.exe
python authority/tools/run_incremental_boundaries.py --binary authority/build-ui-incremental-encoded-v3-release/Release --output authority/reports/encoded-boundary-repeat --work-limit 10000000 --manifest authority/research/ui_incremental_boundaries_10m_v1.json
python authority/tools/run_incremental_10m_experiment.py --binary authority/build-ui-incremental-encoded-v3-release/Release --output authority/reports/encoded-real-repeat --prior-oracle authority/reports/encoded-model-repeat/oracle-result.json --oracle-manifest authority/research/ui_incremental_oracle_encoded_v1.json
```

## 下一步的依据

修正前缀收费后，MCM 可捕获约 8.3–8.5 万次消费，但仍耗尽工作量；EID 在约 4.68 万次消费时触达新增 64 MiB 编码限制。需要兼容的案例被拒绝仍是失败。两个预算保持，下一步先验证字段版本快照差量，再研究活跃性搜索复用。

EID 一个真实失败前缀包含 2,722 张字段版本图、1,194 张不同完整图，原始图约 29.98 MB，不同整图约 29.79 MB。整图去重只能省约 0.6%，不足以解决瓶颈。下一候选应记录每个对象的不可变版本基点和按键的实际变化，研究可证明的共同增量与稀疏例外；完整展开必须还原每张图的每个键及版本，不根据字段名或数值相同推断游戏用途。不覆盖个人配置，也不改变奖励投影。

各候选的源码与二进制快照分别在 `reports/ui-incremental-10m-original-preserved`、`ui-incremental-index-preserved`、`ui-incremental-encoded-v1-preserved`、`ui-incremental-encoded-v2-preserved`。失败构建和早期边界解析器未兼容新格式的记录保留。真实失败前缀、首次原因及费用可能变化，不作为稳定证据通过。最终实测和审计记录见本轮最终报告；本阶段没有重做整体研究包。

## 最终两轮实测与审计

当前 DLL：`build-ui-incremental-encoded-v3-release/Release/ia_lua533_ui_incremental.dll`，SHA-256 为 `e22618dca10e8e195ebaf51cbf2f39201df81cedc2a2cd91d5c6f0d14e0f13d9`。仍为 Windows x86 私有研究入口，不替换游戏 DLL。

| 冻结初始化案例 | 两轮工作量 | 两轮逻辑消费数 | 结果 |
| --- | --- | --- | --- |
| MCM 中文 | 10,000,000 / 10,000,000 | 84,943 / 84,019 | 工作量耗尽 |
| MCM 英文 | 10,000,000 / 10,000,000 | 83,161 / 84,811 | 工作量耗尽 |
| EID 中文 | 8,811,219 / 8,798,051 | 46,834 / 46,829 | 编码字节容量耗尽 |
| EID 英文 | 8,792,777 / 8,803,906 | 46,834 / 46,834 | 编码字节容量耗尽 |
| 组合中文 | 10,000,000 / 10,000,000 | 85,902 / 85,595 | 工作量耗尽 |
| 组合英文 | 10,000,000 / 10,000,000 | 84,696 / 85,044 | 工作量耗尽 |

24 项清单按原期待执行两轮：12 个其他功能项通过、6 个实际初始化功能项失败、6 个安全案例正确拒绝。未修改参考 Lua 同样执行两轮。功能结果重复一致；MCM 的首次费用失败位置及完整失败前缀仍不稳定，不能报告为真实追踪证据稳定通过。组件的 27 项完整来源/消费对照、8 项存储测试和 2 项结构边界测试均通过。

最终审计重新核对 31 个个人存档和配置原文件，均与本轮开始时相同；143 个模组 Lua、2 个 J460 脚本、64 个本地资源及 74 个官方 Lua 源文件校验通过。四个历史候选快照、历史二进制和原研究包哈希保持。最终汇总为 `reports/ui-incremental-10m-optimization-final.json`，只读存档审计为 `reports/ui-incremental-10m-optimization-save-audit.json`。完整两轮实测为 `reports/ui-incremental-encoded-v3-real/experiment.json`。

结论：字段索引和无损消费编码的组件门槛通过，真实初始化门槛失败。下一阶段应先以字段版本快照差量解决 EID 的物理证据容量问题，再验证活跃性复用对 MCM 的工作量和重复证据稳定性的影响；两者都须先通过完整展开和来源对照，不放宽现有上限。
