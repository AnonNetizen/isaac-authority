# Slice2：状态时点、存储使用版本与延迟分支

这是独立 Windows x86 金币模型研究原型，ABI 为 `ia-lua533-slice-2`。它不附加游戏、不替换游戏 DLL、不操作存档，也不接入 MCM/EID、游戏世界或网络。保留官方 Lua 5.3.3 原始源码、slice1 的源码、冻结清单、DLL 和历史研究包。

本轮按状态查询、使用位置投影、延迟分支的顺序实现。个人配置、位置和输入在个人上下文中求值；已证明的世界贡献在游戏视图中引用主机值。个人随机调用生成表达式，不采样、不报告随机返回值；显示可多次引用已经产生的权威贡献。

## 运行

从工作区构建：

```powershell
.\tools\build.ps1 -TraceResearch -SliceResearch -Slice2Research -BuildDirectory build-slice2 -RuntimeOutputDirectory build-slice2-release/Release
```

单独运行冻结清单（把路径换成自己的绝对路径）：

```powershell
$taskBinary='D:\Coding\ISAAC\authority\build-slice2-release\Release'
$taskGame='E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth'
$taskSource='D:\Coding\ISAAC\authority'
$taskDll=Join-Path $taskBinary 'ia_lua533_slice2.dll'
$taskHash=(Get-FileHash -LiteralPath $taskDll -Algorithm SHA256).Hash.ToLowerInvariant()
& (Join-Path $taskBinary 'authority-slice2-research.exe') --suite $taskDll $taskHash $taskGame $taskSource (Join-Path $taskSource 'research/slice2_suite.json')
```

完整重复验证：

```powershell
$env:PYTHONPATH='D:\Coding\ISAAC\.tools'
py -3 tools/run_slice2_research.py --binary-dir build-slice2-release/Release --game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' --output-dir reports/slice2-verification --regression-lua 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth\Lua5.3.3r.dll'
```

研究包解压后，`bin` 为二进制目录，`source` 为源码目录。可以用相同命令行入口运行 `source/research/slice2_suite.json`。`bundle-manifest.json` 记录每个文件的 SHA256；先校验，再运行。游戏路径只用于核对已冻结枚举等源文件，测试不会启动游戏。退出命令即结束研究运行时，没有有效游戏钩子需要撤销。

## 实现与证明记录

1. `native/mod_runtime_slice2.cpp` 保存帧开始、回调进入/退出、世界调用前后的不可变金币快照及 RNG 哈希。可登记查询只从选定快照求值。回调由冻结函数原型、模组、回调类型、参数、优先级及父上下文定位；多个候选立即拒绝。查询检查公共调用路径和 CFG，未对应的潜在前驱修改导致拒绝，不取最终状态兜底。
2. `slice2_runtime/ia_graph.cpp` 为寄存器、表字段和 upvalue 建立存储版本与消费记录。权威引用携带世界事件、参数、生产者版本、个人存储槽和前后状态锚点。引用相同的变量副本可以拥有不同游戏视图；绑定不向复制来源回写，因此两次贡献交换消费顺序仍各自引用正确结果。不会整张表覆盖个人配置。表或闭包存在多个无法对应的实例时拒绝。
3. 未解析比较生成条件表达式。候选上下文从初始数据及已接受历史重建，验证重建后的绘制、配置及依赖图。每条路径暂存保存、状态和绘制；帧内主机只执行一次，所有候选复用同一权威记录。用原版 Lua 的数值/字符串比较和真值语义核对条件，提交唯一一致且无未解析路径的候选。
4. 拒绝后从检查点历史重建世界、RNG、个人状态、配置和绘制。重复帧直接返回缓存，同编号不同输入/时间拒绝。上限为每帧 32 条尝试路径、8 个未解析条件、合计 2,000,000 条实际探索指令，包含各候选的模组初始化和已接受历史重建。每条路径分别报告重建及本帧成本；图、源码、绘制等既有预算同时生效。

冻结模组文件原样加载。框架 bootstrap 在内存中增加回调边界服务，原始框架文件保持原样，实际执行的 bootstrap 哈希记入每帧报告。源码位置只用于身份和控制流证据，报告不把相同行号、参数或调用次序视为语义一致。

## 验收与能力边界

`slice2_suite.json` 的 42 项案例在独立清单中复用原案例源码。原有 13、31、24 项清单保持原样，分别用其原 ABI 回归。新清单涵盖原有反例、修改前后新增查询、辅助函数查询、双奖励的字段别名/闭包/共享函数/跨帧保存及逆序消费、Lua 真值和数值相等、保存与绘制后的失败恢复、三种预算拒绝、原生查表函数遇到未解析键时的明确拒绝，以及设置值通过条件分支影响界面的用途歧义。歧义检查同时沿数据与控制依赖传播。旧指令钩子可能先于精确探索计数器拒绝，所有已有预算继续生效。

`reports/current/validation.json` 将功能兼容、安全拒绝和事务验证分开；`cases` 下保存逐例完整证据。预期拒绝符合诊断，不算功能兼容通过。设置与奖励用途无法判定的原反例继续拒绝，因此通用隔离门槛仍未通过。

仍不支持从最终贡献逆推中间随机结果、未解析循环边界/表键/原生参数、没有唯一状态锚点的查询、多个无对应证明的堆实例，以及未登记的原生副作用。数据绑定覆盖的是已证明的世界消费值，不证明任意旧模组的语义。有限模型案例通过后，也不能宣称任意旧模组、真实 HUD 或联机已兼容。

本轮历史失败日志保留：第一轮扩展诊断中的真值跳转、历史恢复失败和逆序消费反例，以及对应冻结清单都进入研究包。`slice2-history-index.json` 标明已记录的历史哈希及早期 runner 哈希未记录的限制。当前二进制哈希和最终复现结果以验证报告及包清单为准，不将历史结果归给后来修复的 DLL。
