# J460 接入说明

新增 `trace_runtime/` 是独立 Windows x86 研究运行时，不属于本节的游戏接入流程。`-TraceResearch` 构建官方 Lua 5.3.3 的原始对照 DLL、插桩 DLL 和命令行运行器；其私有 TValue ABI 禁止与游戏状态混用。`mode=trace` 清单只能由独立运行器执行，游戏批量入口会拒绝。详细挂接点、匹配规则和功能门槛见 [执行依赖研究](EXECUTION_DEPENDENCIES.md)。当前重编译的观察器仅完成本地回归，旧 J460 运行报告不构成新二进制的原生验收。

0.6.0 新增 `resources.cpp` 与编译时资源目录，以及桥接调用前的路径归一化和调用成功后的能力登记。Sprite.SetFrame/GetFrame 按已加载资源和动画帧号限制；重载先撤销旧能力。`--runtime-probe` 必须通过匹配目录的完整资源前置诊断才加载私有模组。[动画与资源记录](RESOURCE_ANIMATION.md) 列出实际范围；未开放包内资源和真实绘制。

0.2.0 新增的单机主机侧影子 Lua 模型是独立的 Python 研究工具，未接入下述原生 DLL。它的 API 重放、候选帧提交和私有状态重建见 [隔离实验记录](ISOLATION.md)，不能据模型通过推断原生游戏可以恢复。

0.3.0 新增 [原生对象桥接](OBJECT_BRIDGE.md) 和 `--object-probe` 独立诊断选项。它在原始 Lua 调用返回后测试两个独立状态，不安装绘制钩子或游戏回调，并在完成后撤销 IAT。原生对象保留在游戏状态，以编号代理访问；世界状态应用尚未实现。

0.4.0 的 `--runtime-probe --runtime-source <源码树>` 使用同一诊断接入点运行 `mod_runtime.cpp` / `research/native_context.lua`。它绑定私有模块加载、回调、配置、输入和金币模型事务，原生 API 采用已验证能力白名单；Sprite.Load 首次实测崩溃后被拒绝，未宣称修复。[运行记录](NATIVE_MOD_RUNTIME.md) 给出实测与边界。该诊断不会注册真实游戏回调或提交原生世界状态。

0.5.0 增加 `--api-probe` 和只读 ItemConfig 代理。API/runtime 诊断必须等正常 MCM/EID 的后段加载标记出现；120 秒没有满足条件则失败并撤销。runtime 先执行同一资源前置检查，成功后才运行私有模组。每次资源调用前写入进度文件。Sprite.Load 仅开放已测菜单资源；只读函数必须是主程序 C 绑定，借用对象仍不能写入，缓存方法按接收者类型及字段名约束。[资源记录](ENGINE_API.md) 说明当前缺口。这些 API 未用于原生战斗和客机状态应用。

当前实现分为四层：`launcher.cpp` 加载观察器，`probe.cpp` 在正确 Lua 状态中接入绘制绑定，`probe.lua` 采集并尝试重放命令，`core.cpp` / `steam.cpp` 验证与传输数据。实体和房间数据只是观察快照，不是原生游戏状态替换。

| 接入点 | 实现及依据 | 限制 |
|---|---|---|
| DLL 加载 | Windows x86 `LoadLibraryW`，随后调用 `IaInitialize`；系统导出使用目标进程对应模块基址和 RVA | 不修改磁盘主程序；超时保留远程参数直到游戏退出 |
| Lua 游戏回调 | 主程序 IAT 的实际 `lua_pcallk`；用受保护、只读的公开 API 检查 Game 帧数与渲染回调表，每秒最多 5 次，成功后安装探针 | 原始调用照常执行；尚未阻止客机模组或战斗逻辑 |
| 绘制入口 | `lua_tocfunction` 取得真实 C 绑定，核对位于已知主程序的可执行页，MinHook 同 ABI `int __cdecl(lua_State*)` | 只覆盖下表绑定，未覆盖原生全局渲染、覆盖动画、着色器等全部入口 |
| 世界采集 | `MC_POST_UPDATE`、`Isaac.GetRoomEntities`、公开玩家/精灵 API | 未覆盖完整原生字段、房间网格、道具全部效果、原生 AI 私有状态 |
| 输入 | 采集 controller 0 的 action 0–15 | 不注入原生第二玩家，不虚拟化任意键、鼠标、摇杆或模组按键 |
| 进度 | 协议事件 ID 的会话内去重队列 | 不写原生存档，没有解锁规则映射和持久事务日志 |

以下 RVA 是实际 Lua C 绑定解析所得的观测结果，**运行时不按这些数字盲目挂钩**。白名单哈希变化则拒绝加载。

| 绑定 | 本机 J460 RVA（十进制） |
|---|---:|
| Isaac.RenderText | 4819088 |
| Sprite.Load | 4887840 |
| Sprite.ReplaceSpritesheet | 4889040 |
| Sprite.Render | 4888464 |
| Sprite.RenderLayer | 4888736 |
| Font.Load | 4885728 |
| Font.DrawString | 4886464 |

本机 `resources/scripts/main.lua` 的 `EndClass` 分派器要求原始方法字段保持 C 函数；直接替换成 Lua 包装函数曾在早期实验的 MCM `Font.Load` 路径触发崩溃。当前生产探针保持这些字段原样，在真实 C 入口执行受保护的观测回调，复原 Lua 栈，再调用原函数一次。字体的 UTF8 / Scaled 兼容函数会转到原始 `DrawString(self,text,x,y,sx,sy,KColor,FontRenderSettings)`。源码内的 Lua `__index` 包装仅作为测试替代，不能证明缓存 C 函数会被捕获。

文本以 `text_hex` 携带原始 Lua 字节，保留旧中文编码和 NUL，不把它们强制当成 UTF8。字体 KColor 的 `Red/Green/Blue/Alpha` 与精灵 Color 的 `R/G/B/A` 分别处理。资源路径尽量转换为游戏根目录下的相对路径，网络验证拒绝父目录与绝对路径。加载前创建的 Font 没有通用可用的文件名获取器，命令会标记 `font_asset_unknown`；当前预览无法重放这一部分，因此 `complete_render_capture=false`。这个缺口算作界面验收失败。

实体 ID 由本地身份与 InitSeed 映射为单调增加整数，采集帧清理消失的实体，关系只引用本帧已知 ID。网络不发送指针，也不复制整块游戏内存；`GetPtrHash` 只用于进程内识别。原生对象中的关联指针、资源缓存和 Lua userdata 都不能直接跨进程恢复。

消息为 CBOR，协议版本 2，字段含 `kind/session/manifest/sequence/frame/player/body`，玩家槽位固定为 capture 0、preview 1。单消息上限 512 KiB，深度 24，命令上限 8192；状态和绘制使用同一可靠通道 197460。暂未实现分片，超限快照会被拒绝或丢弃，不具备大房间支持保证。消息类型包括 hello、world、draw、input、progress；实际观察器目前只交换 world/draw/input，进度事件只在单元测试中生成。

握手核对会话、清单和角色；只接受显式选择的对端。同序号消息去重，新世界观察帧清空旧界面，只有帧号匹配的绘制才能进入预览。3 秒未收到有效消息时暂停逻辑连接，收到后续完整**观察快照**可以继续。它没有暂停实际游戏，不支持进程重启后重置序号，不提供原生世界恢复或主机迁移。去重事件只存在内存中，不能保证跨崩溃的存档结算。

Steam 适配器动态使用已安装的 `SteamNetworkingMessages002`。注入模式等待有效的公开 HSteamUser/HSteamPipe 后取得接口，既不自行初始化游戏 SDK，也不关闭游戏 SDK；独立 `--steam-probe` 只关闭自己初始化的上下文。停止时关闭本实验通道，不关闭整个对端游戏会话。[官方接口说明](https://partner.steamgames.com/doc/api/ISteamNetworkingMessages) 支持可靠/不可靠消息及 P2P，但本原型仅实现可靠研究通道；接口存在不代表双机交换已通过。

撤销时先使 Lua 桥停止，再以 compare-exchange 恢复自己的 IAT 槽，避免覆盖后来安装的别的钩子；检查每个 MinHook 禁用结果。Lua 停止确认允许在没有更新的菜单渲染中执行，回调随后保持惰性，不在遍历回调列表时删除自己。闭包和 trampoline 保留到游戏退出，绝不强制 FreeLibrary。`stopped.json` 的字段来自实际撤销结果；若另一个扩展改动 IAT，标记恢复未完成并记录原因。

`scan_hooks.py` 仅扫描公开 REPENTOGON 版本中已有签名，不安装引擎钩子。固定来源为 [Game.zhl](https://github.com/TeamREPENTOGON/REPENTOGON/blob/9b84409f1c7fa0c50cef5473d7b7a883b94c1b53/libzhl/functions/Game.zhl) 与 [PersistentGameData.zhl](https://github.com/TeamREPENTOGON/REPENTOGON/blob/9b84409f1c7fa0c50cef5473d7b7a883b94c1b53/libzhl/functions/PersistentGameData.zhl)。本机 Game.Update 无匹配、SaveState 有两个匹配；Render、RestoreState、TryUnlock 的唯一匹配仍只是候选，ABI 和对象布局没有在 J460 验证。详情见 `reports/native-signatures.json`。不同版本签名的唯一匹配不能证明可安全调用，SaveState 也不能自动解决指针和私有状态跨进程序列化。

`manifest.py` 对主程序、根目录 DLL、mods 和资源目录文件、探针 DLL 生成规范化哈希，排除本地 `data` 配置与历史备份。它不是已加载模块清单；启用模组集合、第三方注入模块及实际资源解析顺序仍需进一步核对。即使清单相同，也不能据此证明模拟同步或任意模组兼容。
# 当前研究入口

0.8.0 的 `--runtime-suite <冻结清单> --runtime-source <authority 源码目录>` 使用 `runtime_suite.cpp` 顺序建立每例的新私有环境，复用一次资源前置检查。启动器先核对 schema、路径、源码哈希与清单哈希，游戏端再次核对；未知版本或不支持入口明确失败。`ResourceVerificationScope` 跨所有上下文共享一次档案哈希及只读句柄，对象资源能力和动画状态仍各自独立。J460 最终批次的 22 份档案各校验一次，13 个预期结果全部复现，并确认主 Lua 栈恢复和钩子撤销。

`mod_runtime.cpp` 的 StrictReplay 保留逐次操作和参数匹配；Presentation 只在金币模型提交权威写入，个人写入仅记录，返回值修改消费匹配的权威记录。提交前的测试 oracle 不通过则重建私有上下文并重放已接受历史。该候选的通用语义门槛失败，未接入原生实体世界或真实模组渲染回调。[批量记录](RUNTIME_SUITE.md) 给出反例与复现命令。

0.7.0 历史证据见 PERSONAL_INITIALIZATION.md。`--runtime-probe --runtime-source <authority 源码目录>` 及整批诊断都在完成后自动停止并恢复 IAT；不提交原生世界。DLL 保留到正常退出，不在游戏运行时强制卸载。游戏正常退出和退出后的存档审计当前未验证。

