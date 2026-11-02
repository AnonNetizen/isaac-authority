# 主机侧原生模组运行环境（0.4.0，2026-10-10）

本文保留 0.4.0 的历史证据。0.5.0 的初始化、精灵加载与 ItemConfig 后续进展见 [资源接入记录](ENGINE_API.md)；完整 MCM/EID 兼容性仍失败。

**有限原型通过；通用旧模组和可玩联机仍未通过。** `mod_runtime.cpp` 已将原生对象桥接与回调、个人配置、输入、世界调用记录连接起来。两个独立 Lua 5.3 状态都在游戏进程的主机线程上运行；世界写入对象仍是两个金币字段的研究模型。真实 J460 的 Font、Vector、KColor 等值对象可以参与模组回调，但没有接管游戏战斗或实体世界。

真实运行摘要见 `reports/j460-mod-runtime.json`，撤销证据见 `reports/j460-mod-runtime-stopped.json`。诊断自动退出后，测试游戏正常关闭。`native_world_committed=false` 和 `playable=false` 是实际范围，不能把模型中的金币提交当作游戏玩家获得金币。

`fixtures/legacy_chaos/main.lua` 保持原始源码，两个环境分别使用 zh / L / x=24 与 en / M / x=124。三帧模型金币为 5、11、19，每帧只提交一次更新写入和一次渲染写入。两个环境各自生成文字命令并保存配置；重复帧不会重复结算。模型随机数和时间结果按调用顺序供影子环境重放，影子环境没有独立执行这些决策。

新增的 `fixtures/native_private_ui/main.lua` 使用普通 RegisterMod、回调、Font、Vector、KColor 和缓存的 Font.GetStringWidth，没有网络适配接口。真实字体测宽为 65；客机个人上下文的按键将位置 124 改为 125，主环境仍是 24。第三帧故意让影子回调在改写 Vector.X 和 SaveData 后额外加金币，该帧被拒绝。重建环境并重放已接受帧后，配置、Vector.X、闭包计数与字体缓存方法恢复；重试输出 zh|3|65 / en|3|65，金币模型为 3。

这些文字命令留在本机报告中，没有在第二台电脑显示，也没有通过 Steam 传输。原生 Font.DrawString、Sprite.Render 等方法目前会被明确拒绝，不向真实游戏画第二份 UI。这一缺口计入兼容性失败。

| 未修改模组 | 本次原生加载探测 | 结论 |
|---|---|---|
| MCM 中文独立版 | 加载了 7 个入口/模块，建立私有回调列表；停在 `Unverified native API: Sprite.Load` | 加载失败，不分派其局内回调；没有验证菜单和配置功能 |
| EID | 加载了入口与 eid_config；停在 `Unsupported boundary: Isaac.GetItemConfig` | 加载失败；没有验证描述、HUD 或道具元数据 |

两份模组源码树在加载前后哈希一致。当前只分别探测了它们，尚未证明 MCM 与 EID 共同完整加载。共享 Lua 全局环境和模块缓存用合成双模组测试验证，不能替代真实模组组合验收。

首次运行 `mod-runtime-j460-20261010-01` 在原生 Sprite_Load 中崩溃，栈指向本机 main.lua:690。该轮没有完成报告或确认 IAT 撤销，记录为失败；故障 DLL 哈希未及时留存。根因尚未确认，不能宣称只是加载时机问题。后续改为已验证方法白名单，并拒绝 Sprite.Load 和其他未验证原生方法；这是安全边界，不是 Sprite.Load 已修复。失败摘要见 `reports/j460-mod-runtime-first-failed.json`。

原生运行环境目前允许已测值对象构造、Vector.Length、Font.Load、Font.GetStringWidth；Font.Load 只允许绝对路径指向已验证字体哈希。其他方法需要单独验证，不能从构造成功推断整类 API 可用。0.3.0 的独立对象诊断仍保留，不能用旧版本实测替代当前完整模组验收。

实现边界如下。

- 模组代码在加载前复制到源快照，并对实际执行的字节计算 SHA256。require/include/dofile 仅解析选定源码树；缺失模块产生可捕获的标准形式错误，支持旧模组的路径发现。源码外路径与未实现 API 属于不可忽略的失败，即使 Lua pcall 捕获它们也不能接受这一帧。
- 每个个人上下文有私有 SaveData 存储、输入、模块缓存和回调列表。同一上下文内多个模组共享全局变量；姓名相同的模组数据仍按 Name 归类，完整游戏存储身份与 API 语义尚未映射。只支持 controller 0 的个人按键/动作子集。
- 主环境记录世界调用的名称、参数和结果，影子环境必须逐项相同。少调用、多调用、参数不同都拒绝候选帧。个人配置影响游戏逻辑的旧模组仍可能不兼容，这一关键门槛没有消失。
- 失败恢复通过销毁上下文、重新加载冻结源码和初始配置，再重放已接受事件；不是复制 Lua 内存、upvalue 或游戏对象内存。原生值对象在重建时重新创建。恢复失败会封闭会话，要求重新启动。
- 候选世界与配置只在内存中提交。没有原生世界事务、持久检查点或崩溃后恢复；不要把 0.2.0 Python 模型的文件检查点能力当作已移植。
- 最多保存 128 个模型帧；单桥最多 2048 个对象、8192 次原生调用。服务数据有深度、数量、字节、返回值和 Lua 栈预留限制。模块执行与回调有指令预算；没有独立 Lua 堆内存上限，这不是安全沙箱。
- 绘制文字保留为 text_hex，支持 NUL 与非 UTF8 原始字节。JSON/配置采用研究用编解码器，完整游戏 json 和任意二进制存储语义尚未验证。

32 份阶段前备份校验通过。首次崩溃后文件哈希没有变化；全部正常运行和退出后的最终审计记录了 stats-plus/save1.dat、Steam 侧 rep+persistentgamedata1.dat 与 remotecache.vdf 三个文件变化。该记录不能推断具体内容、解锁或写入归因。当前文件保留，没有自动回滚用户进度；详见 `reports/mod-runtime-baseline-audit.json`。

```powershell
# 解压研究包根目录；仅测试已安装的已知 J460，游戏应先关闭
.\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' `
  -Mode steam-launch -RuntimeProbe -OutputDirectory '.\runs\runtime-001'

# 不启动游戏的 x86 C API 与金币模型检查
.\bin\authority-runtime-tests.exe '完整游戏目录\Lua5.3.3r.dll' '.\source'
```

诊断没有安装常驻模组或游戏回调，没有安装绘制钩子。完成后检查 stopped.json 的 lua_iat_restored 与 native_binding_hooks_disabled；正常关闭游戏清除驻留 DLL，下次普通启动不加载它。完整联机、真实房间恢复、个人解锁与双机 30 分钟验收仍未完成。
