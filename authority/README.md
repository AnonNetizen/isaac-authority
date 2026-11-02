# Isaac Authority Research 0.8.0

**当前命令行候选：** [回调读取集合与写屏障修复](docs/BOUNDARY_READ_SET_RESULTS.md)。使用 `python -B authority/tools/verify_boundary_reads.py` 校验、`tools/run_boundary_reads.py` 运行冻结短测；当前指针在 `research/boundary_current.json`。维持 1000 万工作量、每子进程 5 秒。当前仅验证金币模型，缓存复用和自动奖励投影关闭。

**历史入口注意：** 旧 `authority-writes.exe` 的写标签宏重复求值，可能破坏常量初始化并在 GC 时崩溃；保留作离线故障对照。新 `authority-reads.exe` 已修复并增加原版 Lua 对照及确定性 C 探针。下文及旧报告保留历史结论，不代表当前可玩联机已完成。

另已交付独立的 `trace-0.1.0` 执行依赖隔离运行时。它基于固定哈希的官方 Lua 5.3.3，运行金币模型，不替换游戏 DLL；普通 Lua 对照、世界查询时序、动态调用位置、失败恢复及去重可通过命令行重复测试。新增清单保留原有 13 个案例。查询读到最终状态和部分随机错配已修复，个人分支新增返回值调用等 5 个新模式案例仍是兼容失败，因此仍不进入真实菜单/HUD。[运行入口、能力边界与失败结论](docs/EXECUTION_DEPENDENCIES.md)；下文 0.8.0 的 J460 记录属于历史二进制，不认证本次重编译版本。

这是 Repentance+ J460 的**研究原型**，包含 Windows x86 观察器，以及新增的单机主机侧 Lua 隔离模型。观察器采集部分世界状态和绘制命令，包含 Steam 消息适配器和协议测试；隔离模型验证两个个人界面、配置与按键，并只提交一份模型世界修改。当前 `playable=false`：客机模拟隔离、原生世界应用、游戏内每玩家界面隔离和原生进度提交均未实现。不能用它修复官方联机 desync，也不能宣称支持任意模组。

已完成源码、可执行文件、可撤销启动工具、接入点说明、未修改旧模组反例及测试记录。完整主机权威联机尚未完成。研究结论与验收范围见 [可行性报告](docs/FEASIBILITY.md)，工程细节见 [接入说明](docs/INTEGRATION.md)。

0.8.0 增加冻结源码的 `--runtime-suite` 批量入口、每案例新建的私有上下文、共享资源校验及实验性个人呈现模式。金币模型能接受不同个人配置和额外无返回值写入，但读写交错、同参数随机调用的含义不同仍会产生错误界面，通用隔离门槛失败。因此按计划不进入第三阶段的真实 MCM/EID 菜单和 HUD 重放。[批量测试与失败结论](docs/RUNTIME_SUITE.md) 给出复现命令和具体边界。

最终 J460 整批诊断复现全部 13 个预期结果，未修改 MCM/EID 中英文私有初始化与语言查询通过，并确认自动撤销钩子。4 个预期失败仍表示兼容失败，不代表可玩联机已完成。当前版本的实测摘要见 `reports/j460-runtime-suite.json`，撤销证据见同名 `-stopped.json`；285 项本地检查与研究包解压复测另记。游戏正常退出及退出后的存档审计未验证。

0.7.0 的包内资源读取、个人 Options 和私有回调表初始化保留为历史成果。22 份资源在 J460 中通过 35 项前置检查；未修改 MCM/EID 中文与英文完整初始化及语言查询通过。真实菜单/HUD、个人 MCM 配置及双机联机未通过。[初始化记录](docs/PERSONAL_INITIALIZATION.md) 与此前失败报告及二进制哈希均保留。

只有一台电脑也能运行隔离模型，不启动游戏。[隔离实验记录](docs/ISOLATION.md) 说明 Python 模型的范围。0.3.0 加入了真实 J460 [原生对象桥接](docs/OBJECT_BRIDGE.md)，0.4.0 连接了私有回调、配置、按键与金币模型。0.5.0 延后初始化，验证两个私有上下文中的菜单精灵和字体，接入只读道具配置。原始 MCM 越过 Sprite.Load，停在 Sprite.SetFrame；EID 已取得 ItemConfig，停在未验证的图标资源。两项完整兼容性均失败。[资源接入记录](docs/ENGINE_API.md) 给出新证据与边界；[0.4.0 历史记录](docs/NATIVE_MOD_RUNTIME.md) 保留首次崩溃与模型恢复结果。实体世界隔离和可玩联机未通过。

```powershell
# 解压包根目录；Python 3.12 / Lua 5.3
py -3 -m pip install lupa==2.6
py -3 .\source\tools\run_isolation.py --demo --output .\runs\isolation-report.json
py -3 .\source\tests\test_isolation.py
```

**本机已知基线**：v1.9.7.17 / J460，主程序 SHA256 `210cade2a1de98550cef52d012174108189d1a0d3926a22c3a1ec12fb3ae4831`。这是用户已有修改的程序，不能称为纯原版；另一个列入白名单的本地备份哈希为 `7122ac28779925b24e23e2416f231322b1470388bd25e2c08665ad8d53b3ea4f`，未完成同等运行验证。仅版本文字相同而哈希不同也会拒绝注入。

解压研究包后，在 PowerShell 中使用完整游戏目录。脚本无需永久安装；二进制在 `bin`，源码在 `source`。源码工作目录下的脚本位于 `tools/run.ps1`，可用 `-BinaryDirectory` 选择本地编译产物。

```powershell
# 只检查已知程序哈希
.\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' -Mode check

# 独立检查当前安装的 Steam 消息接口，不测试对端连接
.\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' -Mode steam-probe

# 游戏已关闭时，诊断资源与只读元数据；正常 MCM 和 EID 必须启用
.\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' -Mode steam-launch -ApiProbe -OutputDirectory '.\runs\api-001'

# 在主机进程内诊断原生模组运行环境；包含资源前置检查，自动停止
.\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' -Mode steam-launch -RuntimeProbe -OutputDirectory '.\runs\runtime-001'

# 冻结当前安装的模组源码后，执行整份清单（源码与资源必须和清单匹配）
py -3 .\source\tools\freeze_suite.py --template .\source\research\runtime_suite.template.json --game '完整游戏目录' --research .\source --output .\my-suite.json
.\run.ps1 -Game '完整游戏目录' -Mode attach -ProcessId 12345 -RuntimeSuite .\my-suite.json -OutputDirectory '.\runs\suite-001'

# 推荐：从 Steam 打开游戏，进入种子局，再用实际进程编号加载观察器
Get-Process isaac-ng | Select-Object Id
.\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' -Mode attach -ProcessId 12345 -OutputDirectory '.\runs\local-001'

# 对刚才的同一个目录停止观察
.\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' -Mode stop -OutputDirectory '.\runs\local-001'
```

每次使用新输出目录。停止后查看该目录的 `stopped.json`，核对 `native_binding_hooks_disabled` 和 `lua_iat_restored`；`native.jsonl` 中的 `lua_observer_stopped` 才表示 Lua 回调已确认停止。菜单里可能没有局内回调来确认，正常退出游戏即可清除所有驻留代码。DLL 会保留到进程退出，不能在游戏仍运行时强制卸载它。正常退出游戏后再启动，原型不会自动加载。

`-Mode steam-launch` 可自动通过 Steam 启动并注入。观察器检查公开游戏帧和渲染回调表后才安装 Lua 探针；没有进入一局时 `lua_observer=false` 是正常的。最终运行验证范围以报告为准。当前存在绘制资源不完整等研究缺口，即使 `world_capture` 和 `draw_capture` 为真，仍不是可玩的客机。

启动器不替换游戏程序或现有模组文件。正常游戏和既有模组仍会写自己的存档、配置；研究开始前必须留存备份，实测使用种子局和一次性存档。这里没有自动恢复存档的命令。`source/tools/prepare_baseline.py` 能在游戏关闭时备份文件，并按原始代码哈希与历史补丁的精确内容撤销此前激光补丁；它不会给模组安装新补丁。打包的 `legacy` 文件只用于验证这一历史回滚。

输出包含 `launch.json`、`status.json`、`native.jsonl`、`stopped.json`。`launch.json` 可含对端 Steam ID 和会话标识，原始日志可能包含模组界面文字；默认留在本机。研究包只携带摘要，不包含存档、游戏资源、原始日志、进程转储或 Steam 用户资料。长期观察的 JSON 日志会增长，停止后再归档；尚未实现日志轮转。

双机观察协议的命令接口为 `--role capture|preview --peer <SteamID64> --session <同一会话标识> --manifest <JSON>`。两边同时向指定对端发送 hello，要求相同程序、扩展与模组资源清单；不具备大厅 UI。`preview` 是本地仍在运行游戏模拟的绘制覆盖层，不能用于真正合作。两台电脑的 P2P 交换尚未实测。目前只有一台测试电脑。

```powershell
# 从源码构建；本机使用 Visual Studio 2026 C++ x86 工具与 CMake
.\source\tools\build.ps1
# Lua 检查需要 Python 3.12 与 lupa==2.6（Lua 5.3）
py -3 -m pip install lupa==2.6
py -3 .\source\tools\validate.py --binary-dir .\source\build\Release --lua-runtime '完整游戏目录\Lua5.3.3r.dll' --output .\validation.json
```

自动验证结果记录在 `reports/validation.json`。批量清单中的“预期拒绝已复现”不等于兼容性通过，必须同时看 `presentation_gate_passed`。这些检查不能代替真实双机游戏。第三方依赖与许可证保存在 `source/third_party`，Lupa 需另行安装。Steam API 和原生桥接使用已安装游戏的 DLL，研究包不分发游戏 DLL、字体或枚举源码。
# Slice2 本轮入口

新增独立 `mode=slice2` 与私有 ABI `ia-lua533-slice-2`，用于金币模型的状态快照查询、按存储使用投影及延迟分支探索。见 [执行说明](docs/EXECUTION_SLICE2.md)。旧模式、原有 13/31/24 项清单与 slice1 研究包保留。设置与奖励用途歧义继续拒绝，仍不能宣称通用旧模组隔离或可玩联机。

