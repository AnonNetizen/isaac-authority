# 字段与 upvalue 版本研究候选

私有 ABI：`ia-lua533-slice3-ui-incremental-1`；独立入口：`ui-incremental`。
规则仍为 `personal-settings-authority-hud-v1`。只在 Windows x86 命令行私有金币模型中运行，不替换游戏 DLL，不写个人存档，也未接入真实渲染、菜单导航或网络。

后续优化使用独立的 `build-ui-incremental-factored-release/Release`。最新步骤、来源对照、证据展开及性能限制见 [INCREMENTAL_UI_OPTIMIZATION.md](INCREMENTAL_UI_OPTIMIZATION.md)。以下 5M 根缓存及 2M 结果保留为历史基线，不能当作新候选的性能结论。

2026-10-11 用户明确将研究工作上限改为 **5,000,000**。当前构建默认使用 500 万；本文后续的 200 万结果、0.1.3 包和对应命令属于历史基线。原 DLL、清单和包保留，新构建使用 `build-ui-incremental-5m` 和独立输出目录。路径 32、未解析条件 8、基本块 4096、源码大小及对象等其他限制保持原值。加载入口同时核对 DLL 导出的实际工作上限、运行器上限和冻结清单，拒绝混用。

当前 500 万入口（输出目录必须不存在）：

```powershell
pwsh -NoProfile -File authority/tools/build.ps1 -BuildDirectory build-ui-incremental-5m -RuntimeOutputDirectory build-ui-incremental-5m-release/Release -TraceResearch -IncrementalUiResearch -IncrementalWorkLimit 5000000 -SkipTests
python authority/tools/run_incremental_ui.py --binary authority/build-ui-incremental-5m-release/Release --output authority/reports/incremental-5m-repeat --phase all --work-limit 5000000
```

当前 500 万清单为 `ui_incremental_suite_5m_v3.json`，冻结的 MCM/EID 源码、资源和普通功能预期不变。三个原 200 万工作量拒绝输入原样保留，按新上限验证普通 Lua 的成功结果；另加两个 500 万边界拒绝测试。v1 误保留了已在约 317 万内完成的 `work-cap-refusal` 拒绝预期，v2 改了分类但漏改原阴性测试的空返回值占位，原始 Lua 和研究 Lua 都实际返回整数 120000。两次清单的失败记录保留；v3 将该新增功能预期设为参考 Lua 的返回结果，程序源码原样保留。其余 21 项的程序与预期不变，该修正项单独在两种运行时各运行两次。终止拒绝仍须阻止 `pcall` 后继续执行。旧 20 项清单与原模式预期保留，500 万清单共 22 项。

500 万实测：MCM/EID 的 6 项初始化仍耗尽上限，未通过真实初始化门槛。独立进程各 2 次对比的中位耗时，MCM 从 1.18 秒增至 2.13 秒，EID 从 1.32 秒增至 3.07 秒。停止时进程工作集分别约 88 MiB 和 184 MiB；包括报告输出的峰值分别约 191 MiB 和 413 MiB。该数字属于命令行研究环境，时间测到初始化完成或拒绝，不含报告序列化。原始记录为 `reports/ui-incremental-5m-timing/comparison.json`，功能与边界结果见 `reports/ui-incremental-5m-delivery.json`。

## 本轮实现

- 字段使用有类型的键身份；结构、字段和 upvalue 记录版本。别名指向同一对象，闭包连接实际 upvalue。写入沿反向边使缓存失效，旧边保守保留。
- 仅复用完成的根遍历，避免循环中的局部结果冒充完整结果。记录完成事件和复用事件、来源、变量图版本、调用位置及匹配版本，拒绝复用未完成或未来的遍历。
- 覆盖 Lua 快速/慢速表写入、rawset、SETLIST、原生表修改、开放 upvalue 栈赋值、C API setupvalue/join、关闭、搬迁及回收。表扩容使缓存字段地址索引失效；对象内身份防止 GC 重用地址继承旧缓存。
- 同一次来源标记的失效通知批处理；空来源的集合并是已证明的恒等操作，不递归。不是将未知操作判作界面计算。
- 不可变字符串键身份及表字段索引缓存。元数据按有类型的键排序；Lua 的 `pairs`、`next`、实际操作顺序及模组源码不变。索引建立、排序比较、版本维护、失效、传播、缓存证据与初始化都计费。
- 静态潜在赋值保留记录，按需分析控制流上的“读旧值前是否已覆盖或退出”。无后续读取的临时寄存器不提供旧值生产者，记录 `no_read_before_overwrite_or_exit`，保留未知来源标记。逃逸闭包引用的开放 upvalue 仍视为活跃；实际 upvalue 不按临时寄存器处理。分析与缓存查询计费，不扫描全部寄存器的完整矩阵。
- 保留原全量传播为只读核对 oracle。测试模式在同一 VM 中保存来源元数据，执行全量算法、恢复，再执行增量算法逐项比较；额外核对成本仍计费。真实初始化不启用 oracle。

每个上下文生命周期最多 2,000,000 工作单位，32 路径、8 条件、4096 基本块及既有结构限制不变。耗尽是终止性拒绝；内部错误清理可丢弃追踪，之后 Lua 执行仍被阻止。不是完整 UI 帧事务恢复。

## 历史 200 万重复执行

以下是历史命令记录。复现历史版本请使用已校验的 0.1.3 包内源码和程序；当前 500 万构建请使用上方的新目录命令，避免覆盖原输出目录。

```powershell
pwsh -NoProfile -File authority/tools/build.ps1 -BuildDirectory build-ui-incremental -RuntimeOutputDirectory build-ui-incremental-release/Release -TraceResearch -IncrementalUiResearch -SkipTests
python authority/tools/run_incremental_ui.py --binary authority/build-ui-incremental-release/Release --output authority/reports/incremental-repeat-oracle --phase oracle
python authority/tools/run_incremental_ui.py --binary authority/build-ui-incremental-release/Release --output authority/reports/incremental-repeat-real --phase real --prior-oracle authority/reports/incremental-repeat-oracle/oracle-result.json
```

输出目录必须不存在。`--phase real` 检查通过的 oracle 所对应的 DLL 与冻结清单哈希，不能凭旧二进制的结果进入下一步。直接入口沿用 `--suite DLL SHA FROZEN_INPUTS SOURCE MANIFEST`。游戏附加入口拒绝该模式。

## 证据和边界

完整原始值图、缓存事件和预算账本均保留。小模型的生产者图与缓存证据可以一致，而内存布局造成的索引扫描、排序及预算账本可能不同；分别报告，不删除数据来制造全报告相等。

`ui_incremental_oracle_v1.json` 的首次测试误把 40 层尾调用当作栈扩容测试。它触发原有 32 层尾调用限制，原源码及失败报告保留；v2 将其明确作为拒绝诊断，并新增真正的非尾调用扩容案例。v3 再增加活跃局部变量、逃逸 upvalue、表达式临时变量和递归闭包覆盖案例，共 14 个功能案例、1 个拒绝诊断。该拒绝仍不算功能兼容。

0.1.2 包的解压复现发现：`L->top` 在拼接后会恢复到 `CallInfo.top`，其下仍可包含失效临时值；仅检查栈范围不足以证明旧生产者有效。该包、二进制和失败报告保留，不能算复现通过。新版本以控制流有效性分析修复这一错误：15 项模型重复执行的完整值图及缓存证据一致，表扩容案例另外连续运行 20 次一致。预算账本仍记录真实布局成本的差异。

当前仍是完整根缓存，不是已完成的按字段脏集合传播。真实 MCM/EID 初始化门槛未通过时，不能据小模型对照宣称真实模组支持。实际 Lua 遍历导致的不同执行生产者也不能靠重编号、参数相等或字段名字相同强行对应。奖励引用、个人设置隔离和可信真实菜单边界仍需后续功能验收。

当前命令行结果：逐来源核对每轮 1409 次，C API upvalue 对照一致；真实初始化清单的 7 个其他功能项、7 个安全拒绝诊断通过，MCM/EID 的 6 项功能初始化仍耗尽预算。旧 166 项使用原模式、原 DLL 回归，完整案例证据与历史一致。安全拒绝和功能通过分开统计；没有启动游戏或开始绘制捕获与菜单导航。

本地游戏字体和图片不随包分发，只保留原资源哈希、元数据和本地检查入口。研究包只用于复现候选及失败边界，不是可用联机补丁。

研究包搬迁复现入口（输出目录必须不存在，本机游戏资源仍须可访问）：

```powershell
python authority/tools/reproduce_incremental_ui.py --archive authority/artifacts/isaac-authority-ui-incremental-0.1.3.zip --output authority/reports/incremental-package-reproduction
```

它在新目录解压并逐文件校验，用包内二进制和搬迁后的源码重跑两种运行时的 20 项清单、逐来源案例及 C API upvalue 测试。比较完整模型值图及缓存证据，保留原始账本和真实失败前缀的差异；测试后再次检查包内文件。
