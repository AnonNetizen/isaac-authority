# 对象与资源契约：第一步结果

独立 Windows x86 入口 `authority-objects.exe --object-suite ROOT MANIFEST CASE boundary` 已补上受控 Sprite、Game 对象。ABI 为 `ia-lua533-model-objects-1`。对象、资源和回归案例达到本轮预期；**真实 MCM/EID 完整初始化仍未通过**，自动投影、菜单导航、绘制重放和联机均未开放。

本轮保持 1000 万工作上限、5 秒子进程超时和 1 GiB 配额。没有启动游戏、改动冻结模组或个人存档，也没有开启全量追踪。旧模组不改、个人配置独立、奖励跟随主机仍是完整目标，不能由本轮的对象测试推导为已满足。

## 实现与边界

每个对象用上下文代次及单调本地编号标识，运行时只保存对应状态。Sprite 没有永久注册表保活；Lua GC 同时撤销状态和已登记 userdata 身份。缓存的原生方法每次检查当前接收者，不能把另一个对象、Game 或普通表当成原对象。Game 在模型内有一个受控句柄；该身份约定尚未在游戏中核对。

Sprite 支持 `Load`、`GetFilename`、`GetDefaultAnimationName`、`GetLayerCount`、`IsLoaded` 的登记模型契约。加载要求明确的布尔图形参数；不支持的签名、资源、字段和方法明确报错。`IsLoaded` 及未加载查询的初始值仅是本轮模型约定，未声称原生等价。`Reset`、播放、图片替换、字段修改、渲染和字体仍未接入。

5 个松散 ANM2 的默认动画、层编号及依赖来自本机原文件，使用 ElementTree 独立提取，并与旧清单核对。18 个原文件合计 418,732 字节，加载前检查全部 SHA256；没有复制资源。两项存储于游戏包中的精灵另列为未支持，没有使用空资源代替。登记后的元数据是固定可信输入，运行时不在每次查询时重新解析 XML。

默认动画和层数的含义参照 [Sprite API](https://wofsauge.github.io/IsaacDocs/rep/Sprite.html)，资源结构参照 [ANM2 格式](https://wofsauge.github.io/IsaacDocs/rep/xml/Anm2_files.html)。Game 的两个只读方法参照 [Game API](https://wofsauge.github.io/IsaacDocs/rep/Game.html)。这些文档及本地 XML 不构成原生画面或所有初始状态的验证。

Game 的帧数、玩家数来自测试清单明确提供的权威场景。场景更新必须使用递增版本；各字段分别递增存储版本，读取记录包含值和字段版本。因此改变玩家数不会使只读帧数的消费者失效，帧数 A→B→A 则会使旧读取失效。没有快照、缺字段或请求未支持世界查询时拒绝，不返回空房间/实体来绕过源码。

Sprite 资源修改同样保留版本；对象读取集合通过代次、对象编号和版本验证。版本查询直接查活动对象索引，不读取历史审计文件或遍历所有对象。回调失败后，沿既有检查点及已接受历史重建对象、个人存储、场景和绘制队列。这里没有实现网络消息去重或双视图投影。

## GC 成本与历史失败

第一次运行在反复 `collectgarbage('collect')` 的压力项触发 5 秒超时。原 Lua 指令与对象销毁计费没有反映完整堆扫描成本。失败报告、三个超时记录、当时二进制哈希及原测试驱动源码均保留。初次未计费对象二进制未单独保留；目前保留的是修复后二进制，不能把历史超时报告说成修复版的执行结果。

修复在 Lua 的函数调用钩子中识别原生 collector 的真实函数身份，缓存函数也会被识别；没有替换 `collectgarbage`。每次显式调用在执行前保守预付 `1 + ceil(当前 Lua 堆字节数 / 64)` 工作单位，所有选项使用同一保守规则。它是新对象候选的资源准入规则，**不是实际扫描量或 CPU 指令的精确测量**。对象终结的计费在安全边界汇总，终结器不跨 Lua GC 抛出 C++ 异常；退出进程时的清理不计入运行报告。

同一冻结压力项现在约 0.15 秒原生执行时间触及工作上限，子进程总时间约 0.22 秒，未提高上限。4096 次有限创建/回收的原生样本约 0.025 秒，结束只保留初始的 3 个对象，回收 4096 个、峰值 36 个。该有限样本不证明任意长期会话内存恒定。

另保留一次测试驱动自身的失败：旧模块的绘制预期只有文本和 X 两列，新驱动一开始误拿三列比较。原始输出与原版 Lua 完全一致；修复比较器支持原清单指定的列数，没有修改冻结预期。修复后原 41 项全部运行。

## 验收记录

| 清单 | 结果 | 范围 |
|---|---|---|
| 对象/资源 37 项 | 达到预期，原版对照及两次候选执行一致 | 含 12 项恢复、5 项进程拒绝；不把拒绝计为功能兼容 |
| collector 契约 4 项 | 达到预期 | 返回值、缓存函数、控制选项和错误字符串与原版 Lua 一致 |
| 冻结模块 41 项 | 达到原预期 | 原 FilepathHelper 路径案例由失败推进为成功；源码未改 |
| 已封存旧回归 153 项 | 达到原模式、原预期 | 包含原本的未解析/拒绝结论，没有升级为兼容通过 |
| 真实初始化 3 项 | 均未通过 | 下一失败入口见下表 |

原版 Lua 对照使用独立原版 VM 和同一登记对象后端，只能验证 Lua 执行及模型结果的一致性，不能验证游戏引擎 ABI、渲染和未覆盖的对象语义。此阶段模型入口与旧默认入口分别保留。

| 真实入口 | 下一停止点 | 累计工作量 | 原生秒数 |
|---|---|---:|---:|
| MCM | 尚不支持注册多个模组 | 10,680 | 0.0185 |
| EID | 原 `eid_config.lua:70` 的 `Keyboard` 枚举缺失 | 141,742 | 0.1920 |
| MCM → EID | 在 MCM 的多个模组注册处停止，未进入 EID | 143,781 | 0.2100 |

这些工作量包含资源和源码校验，不是完整初始化成本。实际 EID 另行独立执行，不被组合的首个失败遮蔽。下一阶段应先建立每个模组各自的注册身份、存储及回调归属，再加载固定 J460 枚举；不能把所有模组的数据写入同一份个人存储，也不能随意给缺失枚举编值。

## 文件与复现

- 代码：`object_runtime/`；固定清单：`research/model_objects*.json` 与 `research/model_objects/`。
- 私有程序及原版对照：`build-model-objects/Release/authority-objects*.exe`。
- 当前结果：`reports/model-objects-v3`、`model-objects-gc-v2`、`model-objects-modules-v2`、`model-objects-real-v1`、`model-objects-regressions-v1`。
- 历史失败和中间验证均只保留压缩报告；没有新增游戏资源或研究 ZIP 副本。清理记录见 `reports/model-objects-final.json`。
- 只读校验：`python -B authority/tools/verify_model_objects.py`。整体 `gate_passed=false` 被保留，校验成功不表示真实模组门槛通过。

先运行 `python -B authority/object_runtime/prepare.py`，用 Visual Studio 18 2026 / Win32 / Release 构建 `authority/object_runtime` 到 `authority/build-model-objects`。构建成功退出后，运行 `python -B authority/tools/run_model_objects.py run --output <新空目录>`；`modules` 和 `real` 分别运行模块与真实源码清单，每个子进程仍有 5 秒超时。
