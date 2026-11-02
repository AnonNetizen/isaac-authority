# 工具与流程修复记录（2026-11-02）

目的：把这次研究里反复遇到的错误一次性修掉，避免以后重犯。每条都对应到代码/脚本中的实际改动。

## 已修复

| 症状 | 根因 | 修复 |
|---|---|---|
| 构建失败 `LNK1104` / 无法覆盖 `isaac_authority_probe.dll` | 游戏仍在运行，DLL 被加载 | `authority/tools/build.ps1` 启动时检测 `isaac-ng`，默认直接报错并提示先关游戏；确需构建时用 `-AllowGameRunning` |
| 新开关报 `Unknown option` | launcher 的 switches 白名单没跟上 | 已加入 `--state-probe`、`--capture-state`、`--capture-packet`；`run.ps1` 同步加入 `-StateProbe/-CaptureState/-CapturePacket` |
| attach 被拒 `Observer initialization refused: 2` | 同一进程已注入过探针，DLL 常驻到游戏退出 | launcher 现在把 2 映射成明确提示“重启游戏”；同时保留 3/4/5 的具体原因 |
| 调用探针在菜单里测到 0 次调用 / `frame_delta=0` | 菜单不跑 Update；游戏暂停/失焦时帧号不前进 | 探针等待“已进入局内且帧号前进”后才开始计时；`--wait-ms` 默认 600000 |
| state-probe 在菜单抓出空对象 | 菜单里 `Game()`/玩家不可用 | state-probe 现在返回 `reason=not_in_run`，安装器会重置重试标志，等下一次 Lua 回调再抓；不再写假报告并停止 |
| RoomIndex/Stage 误判 | `Level+0x7B2C`、`Level+0x8` 与 Lua 真值偶合 | 已改用两房间对照确认 `Game+0x18304`；代码、分析器、外部采样器、文档全部改为新字段，并标注旧偏移为错误候选 |
| 分析器 `KeyError: level_0x20000_hex` | Level 完整 dump 是 best-effort，可能缺失 | 分析器统一用 `.get()`，缺失时跳过；不再中断 |
| `sample_room_transition.py` 采到错误字段 | 脚本仍读旧候选 | 改为 `room_index=Game+0x18304`、`previous_room_index=+0x18308`、`room_index_copy=+0x1B850` |
| `sample_game_stacks.py` 使用全局进程句柄 | 隐式全局状态，易在并发/复用中出错 | `handle` 改为显式参数传给 `sample_thread`/`sample_once`，删除全局 |
| PowerShell `$pid` 只读 | `$pid` 是自动变量 | 统一用 `$gameProcess` / `$gamePid`（脚本与文档示例） |
| 多行 Python 用 `<<` 输入失败 | PowerShell 不支持 heredoc | 统一用 here-string `$code = @' ... '@ | py -3 -` |
| 等待窗口 120 秒不够 | 用户进局/切前台时间不定 | `--wait-ms` 默认 600000；批处理实验显式传 600000 |
| 编辑 launcher 校验块时破坏 `if` 结构 | 宽泛锚点替换 | 构建 + 原生测试（当前 38 项）会捕获；后续用包含上下文的精确锚点 |
| `--skip-probe` 注入后完全没反应 | launcher 的 `object_probe` 开关漏了 skip，`install_object_probe` 从未调用 | 已把 `--skip-probe` 加入 `object_probe`；重跑后 `skipped_calls=59` |
| skip 报 `candidate_rva is missing` | `--candidate-rva` 只在 call-probe 分支解析 | 现对 call/skip 共用解析；重跑后正常 |
| 跳过实验后看起来“游戏卡死” | 游戏窗口失去焦点，Isaac 自动暂停模拟，帧号不变 | 先检查前台窗口；`GetForegroundWindow` 不是游戏时帧号停滞属正常，不是钩子残留 |
| skip 在 `0x554cd0` 上一直等不到“进局” | 该函数的 `ecx` 不是 Game*，探针用 `ecx+0x264F8` 读帧得到 0 | 帧号/玩家统一从全局 `Game`（`base+0x871678`）读取，不再依赖 `ecx` |
| 跳过 `0x2fadc0` 后角色还能移动 | 它只是帧计数/子更新，不是完整模拟入口 | 改用 `0x554cd0`（`ret 4`）作为跳过目标；位置采样确认位移为 0 |

## 现在的验证入口

```powershell
# 构建 + 原生测试（游戏必须先关闭）
authority\tools\build.ps1 -BuildDirectory build-engine-layout

# 检查 launcher 新开关是否在帮助里
authority\build-engine-layout\Release\isaac-authority.exe --help

# Python 工具语法检查
py -3 -m py_compile authority\tools\sample_room_transition.py authority\tools\analyze_state_offsets.py authority\tools\sample_game_stacks.py
```

## 使用约定

- 每次重建/重新注入前：**正常关闭游戏**。DLL 常驻到进程退出，第二次 attach 会被拒（错误码 2）。
- 探针等待时保持游戏前台；进局后不要马上开暂停菜单。
- `build-engine-layout` 目录当前是研究构建；`--state-probe`/`--call-probe` 都从这里取 DLL。
- 所有偏移以 `AUTHORITY_P1.md` 为准；`HANDOFF_20261102.md` 是会话交接，旧候选已标注错误。
