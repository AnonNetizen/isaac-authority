# P0 引擎接管验证：第一次 in-run 布局探针记录（2026-11-01）

目标：在不修改游戏代码、不写内存的前提下，拿到 J460 本机 exe 上 `Game` 对象的原生指针与
vtable，为定位 `Game.Update` 的 vtable 槽和 ABI 做准备。当前只完成第一次只读快照，
**`Game.Update` 仍未定位，不能据此 hook 或宣称可玩**。

## 方法

- 新增只读探针 `--layout-probe`（`authority/native/probe.cpp`，构建于 `build-engine-layout`）：
  在真实 Lua 状态中执行 `return Game()` 与 `return Isaac.GetPlayer(0)`，用 `lua_topointer`
  取 userdata 地址，读取前 64 字节及候选对象指针/候选 vtable 槽，输出 `engine-layout.json`。
- 探针不创建 native hook、不调用引擎函数、不写内存；结果只含模块相对 RVA 和函数字节。
- 存档在实验前已备份并逐文件校验：
  `D:\Coding\ISAAC\backups\rep-plus-20261101-220246`。

## 已确认的事实

1. **主菜单不执行 Lua pcall**：标题画面下探针 `lua_calls=0`，布局探针不触发；
   必须进入一局后 attach。已在一局内成功触发并写出 `engine-layout.json`
   （本机运行目录 `authority/runs/layout-20261101-3`）。
2. **REPENTOGON 的 X-macro 签名在这台被修改的 exe 上不可靠**：
   - `Game.Update` 原签名 0 匹配；
   - `Game.Render` 的“唯一候选”RVA `0x406c20` 在整个文件里没有任何绝对引用，不能当作 Render；
   - 一个 40/41 字节吻合的 `Game.Update` 候选 RVA `0x305c0`，反汇编后是处理浮点/计时的小函数，
     无调用者，已排除。
3. **userdata 载荷没有直接给出 vtable**：
   - `Game` 与 `Player0` 的 userdata 载荷首 dword 都是 `0x013a53c8`（`.rdata`），不是类 vtable；
     其后再往后是堆指针、小整数等，形态更像 Lua 包装器/值数组，而不是 `Game*`。
   - 尝试把该 dword 当 vtable 读取时 0 槽有效，说明它不是 vtable，或布局与假设不同。
   - 探针返回后 Lua GC 会复用 userdata 块，事后再从外部读同一地址会读到别的对象，
     因此**不能**用事后外部读取推断布局；必须在探针内一次性记录。

## 下一步（迭代 2，需要重启游戏以清除旧驻留 DLL）

1. 升级 `--layout-probe`，额外记录：
   - `lua_tocfunction` 得到的 `Game` 全局函数、`Isaac.GetPlayer` 的 RVA 与前 64 字节；
   - userdata 的 metatable 类型名（`__name`）与 `tostring()` 结果；
   - 同时用 `lua_touserdata` 与 `lua_topointer` 取地址，比较二者差异；
   - 更多候选偏移（0x00–0x200）及对象指针的两级解引用。
2. 反汇编 `Game()` 的 C 绑定，找出它读取的 `Game` 单例全局地址（`mov eax, ds:...`），
   从该全局读出 `Game*`，再读 `[Game*]` 的 vtable。
3. 扫描 vtable 槽，逐槽记录函数 RVA/字节；用“每帧调用频率 + `ecx` 等于 Game 指针”
   做动态验证，确认 `Game.Update` 后再谈 hook。
4. 双机验收前，所有步骤仍保持只读、失败即停、存档备份不变。

## 运行入口

```powershell
# 构建（新增的 layout-probe 在其中）
authority\tools\build.ps1 -BuildDirectory build-engine-layout -SkipTests

# 游戏已在某一局内时（旧探针未驻留的干净进程）：
authority\tools\run.ps1 -Game 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth' `
  -Mode attach -ProcessId <PID> -LayoutProbe `
  -BinaryDirectory authority\build-engine-layout\Release `
  -OutputDirectory authority\runs\layout-<new>
```

当前程序状态：游戏停在一局内、旧探针 DLL 已驻留但已停止（`stopped.json` 已写出），
不影响游戏运行；下一次迭代前请正常退出游戏清除驻留 DLL。

## 迭代 2 结果（2026-11-01，同一次 in-run 抓取 + 静态调用图）

第二次布局抓取（`authority/runs/layout-20261101-4`）增加了 C 函数地址、metatable、`tostring`
和 256 字节 userdata 快照，得到以下可复核结论：

1. **`Game()` 绑定 C 函数 = RVA `0x498e70`**。它创建 8 字节 userdata：
   `payload[0]` = 静态 metatable key（运行时 `0x013a53c8`），`payload[4]` = `Game*`；
   这解释了第一次抓取中两个对象首 dword 相同的原因。`tostring(Game())` 返回的是 userdata
   块地址（如 `userdata: 80FBD3F8`），不是 `Game*`。
2. **`Game` 单例全局 = RVA `0x871678`**（文件 VA `0x00c71678`；运行时 `base + 0x871678`）。
   `Isaac.GetPlayer` 绑定（RVA `0x46ef50`）就是通过它取 Game，再访问 `Game+0x1baa8/0x1baac`
   的玩家向量。
3. **`Game.GetFrameCount` 绑定 = RVA `0x413ce0`**；反汇编确认它返回
   `[Game + 0x264f8] - [本地基准]`，即 `Game+0x264f8` 是全局帧计数。
4. **`Game.Update` 强候选 = RVA `0x2fadc0`**：
   - 调用点 `0x55522a`：`mov eax, [0xc71678]; mov ecx, eax; call 0x2fadc0`
     （`ecx = Game*`，符合 `__thiscall`）；
   - 函数体在 `0x2fb9f7..0x2fba0b` 递增 `[edi + 0x264f8]`（edi 即 `ecx`/Game*）——
     与 `GetFrameCount` 读取的是同一字段；
   - 函数体调用大量子系统更新（音频、计时器、`Game+0x18300` 子对象等），
     大小约 0x3660 字节，符合“每帧一次”的主更新函数特征；
   - 调用者 `0x554cd0` 是帧级函数，先做输入/资源/子系统准备，再调用该函数。
   - **尚未动态验证**：需要 hook 该地址，确认“每帧一次、ecx == [base+0x871678]、
     与帧计数增量一致、无崩溃”，通过后才允许写入任何接管逻辑。

外部队列采样与帧字段读取在游戏失焦/暂停时不会推进（观察到的帧计数停在 51），
因此动态验证必须在游戏保持前台、处于一局内时进行。

下一步（迭代 3）：新增只读调用探针（MinHook 计数 + ecx 校验 + 帧计数 delta），
对 `0x2fadc0` 做 30–60 秒验证；通过后再设计 P1 的“主机执行、客机跳过”接管骨架。

## 迭代 3 结果：动态验证通过（2026-11-01）

新增 `--call-probe --candidate-rva 0x2fadc0`：MinHook 安装裸汇编 detour，所有调用原样转发，
10 秒后自动撤销并写 `call-probe.json`。局内实测（`authority/runs/call-20261101-3`）：

| 指标 | 结果 |
|---|---|
| 调用次数 | 305 |
| 帧计数增量 | 306（`1 → 307`） |
| calls / frame | **0.9967** |
| `ecx` 稳定性 | 305 次全部为 `0x3c5b5034` |
| `ecx` 与 Game 单例 | 探针结束后外部读取 `[base+0x871678]` = `0x3c5b5034`，**完全一致** |
| 钩子撤销 | `hook_disabled = true`，游戏继续运行无崩溃 |
| 判据 | 每帧约一次、`this = Game*`、帧计数同步推进 |

说明：探针在主菜单安装时读到 `game_global_ptr = 0`（Game 单例此时尚未写入），
因此探针内的实时比较记为 mismatch；事后用记录下来的 `ecx` 与运行中的 Game 单例对照，
完全一致，判据成立。`probe_passed` 字段仍保留探针内的保守结果（false），
但人工复核结论是 **`Game.Update` 已在 J460 本机 exe 上动态确认：RVA `0x2fadc0`，
`__thiscall`，`ecx = Game*`，每帧一次。**

P0 验收结论：**通过（仅限“定位并验证 Game.Update”，仍不可玩联机）。**

下一步 P1：设计并实现“主机执行、客机跳过 Game.Update”的接管骨架；先做 60 秒空钩稳定性、
再接入最小世界状态快照/应用，最后才谈双机。

## 迭代 4 更正：真正的主机接管入口是 `0x554cd0`（2026-11-02）

跳过 `0x2fadc0` 的 dry run 暴露了命名错误：**帧号不动，但玩家仍在移动**。
位置采样证据（`authority/runs/skip-20261102-5/skip-probe.json`）：

- 跳过 2 秒：帧号 `91 → 91`，但玩家位置位移 **150.38 单位**；
- 3 轮均如此 → `0x2fadc0` 不是完整的每帧模拟入口。

继续向上测试直接调用者 `0x554cd0`（`ret 4`，带一个参数；反汇编入口
`push ebp; mov ebp,esp; and esp,-16; sub esp,0x478`，调用大量子系统）：

- 跳过 `0x554cd0` 2 秒（`authority/runs/skip-20261102-7`）：
  - 帧号 `94 → 94`；
  - 玩家位置位移 **0.0**（`player_moved_during_skip=false`）；
  - 恢复后 `recovered=true`、钩子撤销、无崩溃；
- 调用量约 60 次/秒，符合每帧一次。

结论修正：

| 地址 | 结论 |
|---|---|
| `0x2fadc0` | 每帧一次、`ecx=Game*`、递增帧号的**子更新**；跳过它不会停止角色模拟 |
| **`0x554cd0`** | **真正的每帧游戏更新入口（`ret 4`，一个参数）；跳过它会冻结角色/模拟** |

后续“客机跳过”必须以 `0x554cd0` 为目标，并保留 `ret 4` 的调用约定；`0x2fadc0`
仍可用于帧计数/子更新观测。P0 的“Game.Update”命名应理解为“帧级子更新”，
真正接管入口为 `0x554cd0`。



