# 存储版本和实际读取集合：2026-10-17

独立 Windows x86 命令行候选 `ia-lua533-storage-value-1`。它在稀疏值来源之上连接已登记字段、upvalue 的存储版本和实际读取，尚未执行权威 HUD 投影，也不能用于实际联机。

## 实现

复用保留的私有 Lua 库及现有写入、读取、移动和 GC 钩子。只派生一个 `lvm.c`，为算术和拼接补上结果来源完成后的存储收尾；没有复制整套 Lua 源码、游戏资源或旧报告。

字段拥有不复用的表生命周期、字段编号和写入版本；upvalue 拥有不复用的单元编号和写入版本。常量覆盖也生成新版本，A→B→A 不会因数值相等恢复成旧版本。值生产者与存储顺序分开：`args` 是数据输入，`prior_storage_version` 是存储顺序证据，不把历史值冒充新常量的数据来源。

现有 `rawset`、表库写入、共享闭包、开放/关闭 upvalue、栈扩容及弱表清理均接入。读取复用该时刻的存储节点，旧副本保留旧生产者；读同一版本不会重建字段索引。表及单元回收时删除活动索引和槽绑定，历史值节点仍可由旧副本引用。原始指针仅在本进程索引使用，不进入报告或跨进程数据。

每帧单独记录实际读取的已登记字段和单元，检查当前生命周期、写入版本与值版本。读取历史副本不等于再次读取它的原字段，因此修改原字段不会误使该副本的读取记录失效。帧内读到两个版本则明确记录 `mixed`。读取集合不通过扫描所有生产者祖先来重建，也不读取历史审计文件。

帧回执最多 128 份、16384 条依赖，并按提交时载荷计费最多 64 KiB；逐份保留计费大小，淘汰时直接扣除，不重新汇总全部历史记录。过期回执明确拒绝查询。所有记录仍标记 `all_inputs_captured=false`、`cache_reuse_allowed=false`，没有启用自动缓存复用。

固定保护保持 1000 万工作单位、5 秒子进程超时及 1 GiB 私有内存。稀疏图沿用每上下文 4096 节点与 1 MiB 序列化证据额度；活动表/单元各 256、字段 1024。容量错误会在 Lua 之外留下粘滞失败，即使模组 `pcall` 吞掉错误，本帧仍拒绝并重建恢复。

## 验证

最新冻结清单是 `research/storage_value/suite-v5.json`，使用新增的模型测试源码；旧测试源码、清单及实际 MCM/EID 均未修改。

- 28 项版本、读取、GC、恢复及拒绝诊断运行两次，输出和版本证据一致；适用案例与独立原版 Lua 比较。来源初始化记录包含实际数值和类型，不用 nil 占位。私有读取诊断和预期安全拒绝没有被计作原版兼容通过。
- 覆盖字段与 upvalue 的 A→B→A、常量覆盖、rawset、table.insert/remove、共享闭包、开放变量的算术/拼接、栈移动、GC 退役、弱表清理、保存和绘制后失败、重复帧及不同负载拒绝。
- 读取反例覆盖无关字段、实际字段、共享 upvalue、历史副本、帧内混合状态与过期回执。检查读取关系及失效结果，包含“来源在旧字段，但本帧只读取副本”的反例。
- 原 World View 35 项原清单、原预期通过，仍为 24 项普通 API 功能和 11 项预期拒绝。
- 真实 MCM、EID、组合初始化与原版对照通过。最新私有组合约 0.858 秒、2564149 工作单位、62697472 字节私有内存。EID 本次仍未在初始化阶段读取保存配置，不能据此宣称它的配置来源已覆盖。
- 原两个必过功能清单原样执行，**仍均失败**：关联奖励 HUD 仍显示个人 2，要求主机 1；相同混合回调的个人执行仍被 `World write requires authority phase` 拒绝。

首次存储测试报告 `reports/storage-values-v1/result.json.gz` 保留了三个测试驱动失败：事件 1 被通用驱动默认当作权威阶段、漏计空绘制帧、给原版 Lua 错设了私有拒绝预期。修正的是新测试调用与分类，未修改旧反例或模组逻辑。后续各版本保留，最终结果为 `reports/storage-values-v5/result.json.gz`。

## 边界与下一步

只覆盖由配置根或已带来源的值登记的存储，支持整数和字符串键。没有把未登记存储、未知对象或未解析原生操作认作纯界面。字段 nil 的版本可记录，但 nil 值本身尚未完整传播；运行时明确统计该缺口，绝不修改 Lua 共享 nil 哨兵。动态索引、别名用途、默认字面量、随机/输入来源及 userdata 的完整规则仍不完整。

实际读取集合与数据来源图现在分开，但没有覆盖世界查询、个人输入、原生隐藏副作用等所有输入，所以“存储版本仍有效”不是可复用整帧的许可。完整控制依赖、权威状态时间线、配置序列化侧车和双视图求值尚未完成。

回收了活动存储索引，不等于长期内存问题已经解决：历史值节点仍占用固定图容量，Session 仍保留接受历史；活跃值回收、长期检查点及长会话验收没有通过。完整菜单和 HUD、游戏模拟接管、网络、解锁及双机测试仍在后续阶段。

下一步补齐 nil 和世界查询的来源，并记录主机操作前后的状态时点，把已登记存储读取连接到权威引用；不能仅凭字段同名、写入次数或来源交集选择主机值。两个原功能失败持续保留为门槛。

## 入口

从 `D:\Coding\ISAAC` 执行：

```powershell
python -B authority/storage_value_runtime/prepare.py
# 使用本机 Visual Studio CMake 编译 Win32 的 authority/build-storage-value。
python -B authority/tools/check_storage_values.py run --output authority/reports/<新短测目录>
python -B authority/tools/check_storage_values.py regressions --output authority/reports/<新回归目录>
python -B authority/tools/check_storage_values.py real-init --output authority/reports/<新初始化目录>
python -B authority/tools/check_storage_values.py required --output authority/reports/<新功能门槛目录>
python -B authority/tools/verify_storage_values.py
```

`required` 目前按功能失败退出 1。冻结源码已在工作区，无需重新 `freeze`；本阶段没有新建 ZIP、解压副本、启动游戏或改动个人存档。
