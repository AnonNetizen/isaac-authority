# 稀疏值来源候选：2026-10-17

当前是独立 Windows x86 命令行候选，ABI `ia-lua533-sparse-value-1`。它补上配置值经过运算、复制和闭包后到达世界参数与文字消费处的来源记录；没有实现显示投影，没有修复游戏联机。

## 本轮实现及依据

仅派生保留的私有 Lua 源码，在 `TValue` 中增加本地节点编号。普通值复制、表字段存储、upvalue 关闭及栈移动随值保留编号。类型和值均沿用 Lua 执行；标记不会写入模组 JSON，不包含跨进程指针。

实际 SDK `LoadModData` 的接收者决定存储所有者、槽和内容版本，返回的确切值携带根编号。原样的 J460 Lua 包装经过尾调用后，JSON 解码仍能取得这个编号。解码结果按实际 JSON 指针分别建立字段来源；相同字符串被 Lua 内部驻留时，也不以字符串地址或字节相等混同两个模组的来源。

只有操作数已有来源时才为受支持的算术、拼接、取长度和数值转换建立节点。节点保留有序操作数及使用处；源码位置仅供诊断。没有来源的循环不建立逐指令值图。缓存函数、表别名、rawset、表库复制和共享闭包继续使用值本身的来源，不回读历史审计文件。

根字段标记通过私有元数据入口写入实际字段槽，不额外调用 Lua `rawset`，避免制造第二次逻辑写入。第一轮只标记栈副本，导致字段来源消失；失败记录保留于 `reports/sparse-values-v1/result.json.gz`。修正后的结果另存，不覆盖该失败。

每个上下文最多 4096 个节点、256 个消费记录、1 MiB 序列化证据载荷；容量耗尽明确拒绝，失败后由已有事务重建恢复。1 MiB 指序列化载荷额度，不是整个图的实测内存占用。正式子进程保护仍为 1000 万工作单位、5 秒和 1 GiB 私有内存。没有开启全量初始化追踪、放宽上限或新增资源/研究包解压副本。

## 验证结果

- `research/sparse_value/suite-v2.json` 的 12 个来源、分支诊断和恢复案例通过；每项运行两次私有运行时，并在适用时比较独立原版 Lua。普通返回、文字字节、模型与私有状态一致。包含预期未知、未解析条件及超容量诊断，它们不能计作用户功能兼容通过。
- 原 World View 35 项原清单、原预期回归通过，仍是 24 项普通 API 功能与 11 项预期拒绝；没有改成主机 HUD 预期。
- 冻结的真实 MCM、EID、组合初始化都在同一限制内完成，且与原版 Lua 对照一致。最新私有组合初始化约 0.758 秒、2563525 工作单位、62750720 字节私有内存；这是命令行初始化测量，不是游戏每帧耗时。MCM 有 9 个来源节点及 2 个未登记原生路径记录；EID 本次初始化未调用保存配置的加载入口，来源节点为 0，因此不证明 EID 的配置追踪完整。
- 原两项必过功能清单原样重跑，**均仍失败**：个人关联奖励 HUD 显示 2 而要求 1；相同混合回调在个人环境仍被 `World write requires authority phase` 拒绝。

`reports/sparse-values-source-anchors.json` 从真实失败案例的数据流得到一条来源交集：主机 `coins.add` 参数 1 和个人 HUD 中的 2 都来自实际所有者、槽、内容版本和 JSON 路径一致的字段。这证明来源连通，**不证明两个使用的语义、状态时点或操作对应已经成立**，没有据此改写个人配置或显示。

## 明确未完成的部分

当前观察入口只播种 SDK 配置加载根。个人输入、世界查询、随机结果、原生 userdata 和默认配置字面量的完整来源尚未接入；没有把无来源认定成纯界面。配置编码/重载的完整字段侧车、nil 字段来源、动态索引依赖、原生 API 参数/结果规则和未知原生函数的隐藏副作用仍需补齐。

值生产者编号不能代替字段/upvalue 的完整存储版本。需要把现有精确写屏障接入此图，覆盖常量覆盖、A→B→A、别名和跨帧使用；同源或相同参数都不能直接充当权威操作匹配证据。已带来源的比较留下未解析条件记录，但没有把它传播为完整控制依赖，也没有执行延迟分支投影。世界查询的主客状态时间线仍未解决。

固定容量会拒绝后续增长，并不证明长期可用：当前图尚无活跃根回收，已有 Session 接受历史也会增长。此候选所有 HUD 仍不可发布，菜单用途、绘制完整性、原生世界接管、网络、解锁及双机验收都未完成。没有启动游戏或改动个人存档。

下一步连接字段与 upvalue 写屏障、生产者版本和消费读集合，先让同一字段的历史副本与新值可区分；补齐权威查询时点与控制依赖后，再在消费处执行双视图选择。原两项失败始终作为功能门槛保留。

## 复现

从 `D:\Coding\ISAAC` 执行：

```powershell
python -B authority/sparse_value_runtime/prepare.py
# 用本机 Visual Studio CMake 配置 Win32 并编译 authority/build-sparse-value。
python -B authority/tools/check_sparse_values.py run --output authority/reports/<新的短测目录>
python -B authority/tools/check_sparse_values.py regressions --output authority/reports/<新的回归目录>
python -B authority/tools/check_sparse_values.py real-init --output authority/reports/<新的初始化目录>
python -B authority/tools/check_sparse_required.py --output authority/reports/<新的功能门槛目录>
python -B authority/tools/verify_sparse_values.py
```

`check_sparse_required.py` 当前按功能失败退出 1，这是未通过的验收，不是复现脚本错误。新清单与源码已经冻结，复现无需再次执行 `freeze`。报告均为小型压缩结果，没有新建 ZIP 包或复制游戏图片和字体。
