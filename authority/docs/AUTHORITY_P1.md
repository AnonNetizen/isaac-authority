# P1 主机权威接管：第一阶段记录（2026-11-01）

P0 已确认 `Game.Update` = RVA `0x2fadc0`（`__thiscall`，`ecx = Game*`，每帧一次）。
P1 第一小步的目标：**长时间空钩稳定性 + Update 边界状态可采集性**。
这一小步不改变游戏行为，只安装钩子并原样转发，用最小字段采集验证后续接管的可行性。

## 实测（`authority/runs/update-stability-20261101-2`）

| 指标 | 结果 |
|---|---|
| 钩子持续时间 | 30.25 秒 |
| 调用次数 | 862 |
| 帧计数增量 | 845（`1 → 846`） |
| calls / frame | **1.0201** |
| `ecx` 稳定 | 862/862 等于 Game 单例（`0x3c95901c`） |
| 玩家向量长度（`Game+0x1baa8/0x1baac`） | 首/末均为 1 |
| 重复帧调用 | 18 / 862（约 2%） |
| 钩子撤销 | `hook_disabled = true`，游戏继续响应、无崩溃 |
| 探针内部 `probe_passed` | false（判据要求 duplicate_frames == 0） |

## 判读

- **空钩稳定性通过**：30 秒持续钩子、每帧调用、`this` 稳定、无崩溃，撤销成功。
- **帧粒度契约基本成立**：862 次调用对应 845 帧，比例 1.02；18 次“同帧重复”约 2%，
  与测量起点/终点边界以及可能的追赶帧一致，不足以否定“每帧一次”，但**不能宣称严格一一对应**。
- **状态可采集**：`Game` 指针与玩家向量（`+0x1baa8/+0x1baac`）在 Update 入口可稳定读取，
  这是后续世界状态契约的起点。
- Update 调用约定：调用点没有压入参数，返回值在返回后未被使用，
  **为客机跳过（guest skip）留出了机械上的空间**，但语义后果尚未测试。

## 结论

P1a 验收：**通过（带保留：2% 同帧重复、未做 60 秒长测）**。

## 下一步 P1b（尚未开始）

1. **发现更多状态偏移**：玩家位置/速度、实体列表、房间与游戏模式字段。
   方法：Lua API 真值（`Isaac.GetPlayer(0).Position`、`Isaac.GetRoomEntities()`）与
   Update 入口内存快照对照，扫描候选偏移，只记录可复核的字段。
2. **定义最小权威状态包**：帧号、玩家列表（指针/位置/速度）、房间索引、实体 ID 集合；
   先做“入口/出口快照 + 单机重复性”测试，不接管模拟。
3. **客机跳过 dry run**：在一次性存档/种子局中让 detour 直接返回，观察画面/崩溃；
   自动在 N 秒后或异常时恢复转发。此步会改变游戏行为，必须单独标注并可回滚。

所有步骤继续保持：只读优先、失败即撤销、不写存档、双机验收前不宣称可玩。

## P1b 第一阶段：已确认的原生字段偏移（2026-11-01）

新增 `--state-probe`：在一次局内 Lua 回调中同时取 Lua 真值（位置/速度/大小/种子/类型/变体）
与 `Game*`、`EntityPlayer*` 的内存快照，再用离线脚本
`authority/tools/analyze_state_offsets.py` 搜索精确 float32/u32 编码。随后在游戏仍运行时
从外部进程读取同一批字段做独立复核。

已确认（两次一致，另一路外部读取完全相等）：

| 字段 | 位置 |
|---|---|
| `Game*` 单例全局 | `base + 0x871678`（RVA） |
| 帧计数 | `Game + 0x264F8`（u32） |
| 玩家向量（指针数组） | `Game + 0x1BAA8`（start）、`Game + 0x1BAAC`（end） |
| Level 指针 | `Game + 0x18300` |
| 玩家位置 | `EntityPlayer + 0x33C`（float x/y）；`+0x38C` 有同值副本 |
| 玩家速度 | `EntityPlayer + 0x360`（float x/y） |
| 玩家 Size | `EntityPlayer + 0x370`（float） |
| 实体 Type / Variant | `EntityPlayer + 0x28` / `+0x2C`（u32） |
| 实体 InitSeed | `EntityPlayer + 0x3EC`（u32；`+0x3DC` 是另一个 seed 字段） |
| Stage | **未定位**（`Level + 0x8` 已确认不是 Stage） |

复核样本：`authority/runs/state-20261101-1/state-probe.json`、
`authority/reports/state-offsets-20261101-1.json`；外部复核给出的
`Position = (373.81121826171875, 209.40194702148438)`、`Velocity`、`Size = 10`、
`Seed = 2716708871`、`Type = 1` 与 Lua 真值逐位相等。

## P1b 尚未完成

- **实体列表/房间**：目前只抓到了 `EntityPlayer`（它同时是 `GetRoomEntities()[1]`）。
  还需要抓多个实体指针并定位房间实体向量（预计在 `Level`/`Room` 对象内），
  以及 RoomDescriptor/当前房间索引。
- **偏移稳定性**：`+0x33C` 与 `+0x38C` 两个同值副本需要在移动中区分（哪个是权威 Position）。
- **多帧重复性**：需要在两次不同位置/房间的抓取中复现同一偏移。
- 未做任何写操作，客机跳过尚未测试。

下一步 P1b-2：一次抓取前 N 个实体的指针与真值，扫描 Level/Room 内存定位实体向量；
再用“移动中”的第二帧确认 Position 与移动速度字段；然后才能起草最小权威状态契约。

## P1b-2 结果：实体列表与房间字段已定位（2026-11-01）

`--state-probe` 升级后一次抓取 8 个实体（含玩家、火、effect），并在离线分析中
对全部私有可读写内存做实体指针序列扫描，再对运行中的游戏做外部读取复核。

| 字段 | 位置 |
|---|---|
| 实体数组指针 | `Level + 0x125C` |
| 实体数组容量（字节） | `Level + 0x1260`（本样本 2048） |
| 实体数量 | `Level + 0x1264`（本样本 14） |
| 实体 Type | `Entity + 0x28` |
| 实体 Variant | `Entity + 0x2C` |
| 实体 Position | `Entity + 0x33C`（float x/y） |
| 实体 Velocity | `Entity + 0x360` |
| 实体 Size | `Entity + 0x370` |
| 实体 InitSeed | `Entity + 0x3EC`（`+0x3DC` 是另一个 seed 字段，二者不完全相等） |
| 当前房间索引 | `Game + 0x18304`（P1d 确认；`Level + 0x7B2C` **不是**房间索引） |
| 上一房间索引 | `Game + 0x18308`（候选） |
| Stage | **未定位**（`Level + 0x8` 已确认不是 Stage） |

复核证据：从 `Level+0x125C` 读出 14 个实体指针，逐个读取 Type/Variant/Position/Seed，
与同帧 Lua 真值（`GetRoomEntities` 前 8 项）逐项一致；实体指针序列在堆内存中
`0x3ce6a014` 处连续出现 8 个，和 Level 字段指向的数组完全一致。

## P1b-2 尚未完成

- 只抓了一个房间；`RoomIndex`/`Stage` 偏移需要第二个房间（换房）再确认。
- `+0x33C` 与 `+0x38C` 两个同值 Position 副本仍未区分；需要移动中的多帧快照。
- 尚未实现“在 Update 入口用纯原生读取生成状态快照”的探测（目前靠 Lua 真值 + 一次性内存 dump）。
- 未开始客机跳过/主机接管；所有操作仍只读。

下一步 P1c：在 Update 入口以纯原生方式每帧采集最小状态包（帧号/Stage/RoomIndex/
玩家列表/实体列表及其字段），连续采样并验证可重复性与开销；同时做换房与移动中的
第二次抓取，确认房间与 Position 偏移的稳定性。

## P1c 结果：Update 入口原生逐帧采集已验证（2026-11-01）

`--call-probe --capture-state` 在 `Game.Update` 入口逐帧读取原生字段（不写文件、不调 Lua），
30 秒后汇总写盘。结果（`authority/runs/state-motion-20261101-1`）：

| 指标 | 结果 |
|---|---|
| 调用 / 帧 | 862 / 836（1.03） |
| `ecx` 稳定 | 862/862 等于 Game 单例 |
| 玩家向量指针变化 | 0 |
| 实体数组指针变化 | 0 |
| 实体数量范围 | 2 – 37（房间内容变化时更新） |
| Stage | 恒为 1 |
| Position 两副本差异帧 | **836 / 836** |
| 首次差异样本 | `+0x33C = (321.521, 380.0)`，`+0x38C = (320.0, 380.0)` |
| 钩子撤销 / 稳定性 | 成功，无崩溃 |

判读：

- **纯原生逐帧采集可行**：每帧读取 Game/Level/玩家/实体计数与位置副本，30 秒无异常，
  开销未造成掉帧（calls/frame 仍约 1）。
- **Position 偏移确认**：移动中两副本每帧不同，`+0x33C` 是当前值、`+0x38C` 是滞后副本
  （首次差异样本中 `+0x38C` 等于上一位置的整数值 320.0）。权威 Position 采用 `+0x33C`。
- **RoomIndex（当时）未确认**：本次 `room_change_count = 0`，`Level + 0x7B2C` 未发生变化；
  可能这次没有真正换房，或该偏移不是当前房间索引。后由 P1d 确认真正字段是 `Game+0x18304`。
- 重复帧 27/862（约 3%），与边界/追赶帧一致，不影响“约每帧一次”的结论。

下一步：换房验证（在另一个房间抓一次 state-probe，比较 Lua `GetCurrentRoomIndex()` 与
Level 内存候选，确认房间索引偏移）；确认后再定义最小权威状态包并进入客机跳过实验。

## 更正：RoomIndex / Stage 偏移尚未确认（2026-11-01 晚）

后续换房抓取（`authority/runs/state-20261101-3`）直接推翻了此前的巧合匹配：

- Lua 真值：`GetCurrentRoomIndex() = 71`、`GetStage() = 1`；
- 同一快照内内存：`Level + 0x7B2C = 6`、`Level + 0x8 = 4`；
- 在 Level 前 0x8000 内搜索整数 71：**0 个匹配**。

因此之前 `state-20261101-2` 中 `Level+0x7B2C == 71`、`Level+0x8 == 1` 是巧合，
**不能**把这两个偏移当作 RoomIndex/Stage。当前房间索引与 Stage 的实际位置仍未找到。

另外，外部 Level 采样（`authority/runs/room-transition-20261101-1.jsonl`）显示
`Level+0x7B2C` 在整段采样中恒为 6、`Level+0x8` 在 1/4/10 间变化，进一步说明它们是
其他房间/关卡字段（可能是房间类型或关卡状态），不是 Lua 的 RoomIndex/Stage。

## 下一步修正

1. state-probe 增加 **完整 Game 对象 dump**（`Game + 0x0 … 0x28000`）与 Level/子对象 dump；
2. 分别在两个不同房间抓取，用 Lua 真值 71 和另一个房间值在 Game/Level 内存中搜索，
   取**两次都唯一且与真值一致**的偏移；
3. 在找到之前，最小状态包先使用 `Game*`、`Level*`、帧号、玩家列表、实体数组/实体字段，
   房间身份暂由 Level/实体集合表示，不写入 RoomIndex 契约。

## 结论（P1c 阶段）

- `Game.Update` 入口的**纯原生逐帧采集可行**（30 秒、862 调用、无崩、约 1.03 次/帧）；
- **权威 Position = `Entity + 0x33C`**，`+0x38C` 为滞后副本；
- 实体数组/实体字段/玩家字段已在外部读取中复核；
- **RoomIndex/Stage 偏移仍未定位**，需要上述两次房间对照；其余契约可先行。

## P1d 结果：RoomIndex 已定位（2026-11-02）

state-probe 增加完整 `Game` dump（`Game+0x0 … 0x28000`）与 Level/子对象 dump 后，
在两个不同房间各抓一次（样本 A：Lua room 85；样本 B：Lua room 71），
在 Game 内存中搜索“两次偏移相同、且分别等于各自 Lua 真值”的字段：

| 字段 | 位置 |
|---|---|
| **当前房间索引** | `Game + 0x18304` |
| 上一房间索引（候选） | `Game + 0x18308`（样本 A/B 抓取时值分别是 84 等旧房间值） |
| 房间索引副本 | `Game + 0x1B850`（与 0x18304 同步；可能是 HUD/辅助副本） |

证据：

- 两次抓取的共同匹配偏移只有 `0x18304` 与 `0x1B850`；
- 同一时刻外部读取当前运行游戏：`Game+0x18304 = 71 = Lua GetCurrentRoomIndex()`，
  而 `Game+0x18308 = 84`（旧房间值），`Game+0x1B850 = 71`；
- 在 `Game+0x0 … 0x28000` 内搜索 71 共有 9 处，只有上述两处跨房间保持语义一致。

仍未定位：**Stage**（两次样本均为 1，无法区分；`Level+0x8` 已确认不是 Stage）。
`Game+0x1830C` 为 0，暂不采用。

## 最小状态包（草案，待实现验证）

```
Game*                       base + 0x871678
frame                       Game + 0x264F8
roomIndex                   Game + 0x18304
previousRoomIndex           Game + 0x18308
players                     Game + 0x1BAA8 / +0x1BAAC (EntityPlayer*)
entities                    Level(=Game+0x18300) + 0x125C (array)
                            Level + 0x1260 (capacity bytes), +0x1264 (count)
entity fields               +0x28 Type, +0x2C Variant, +0x33C Position,
                            +0x360 Velocity, +0x370 Size, +0x3EC InitSeed
```

下一步：在 Update 入口用上述字段生成逐帧状态包，验证可重复性/序列化开销；
随后做“客机跳过 Update”的 dry run，再进入双机通信设计。

## P1e 结果：逐帧状态包已可生成（2026-11-02）

`--call-probe --capture-packet` 在 Update 入口生成二进制状态包：
`frame, roomIndex, previousRoom, playerCount, players[], entityCount, entities[]`，
每个玩家/实体一次 0x400 块读取（避免逐字段内存校验）。

| 指标 | 第一次 | 块读取优化后 |
|---|---|---|
| 采样帧 | 120 | 120 |
| 包大小 | 116–224 B（均值 204.8） | 116–260 B（均值 194.9） |
| 实体数 | 2–5 | 2–6 |
| 平均组包耗时 | 515 µs | **230.8 µs** |
| 总耗时 / 15 秒 | 61.8 ms | 27.7 ms |
| 房间变化 | 84 → 97 | 84 → 71 |
| 钩子撤销 | 成功 | 成功 |

判读：

- 包布局正确，首帧可解析出玩家位置 `(320,380)`、Size 10、实体 Type/Variant/Seed；
- 房间索引 `Game+0x18304` 在换房时正确变化，`previous_room` 保留旧值；
- 块读取把组包开销降低约 2.2 倍；当前 230 µs/帧在 60 fps 下约 1.4% 帧预算，
  但本轮只覆盖低实体数（2–6），**高实体数 worst case 尚未测**；
- `probe_passed=false` 仅因严格的重复帧判据（9/447），人工判读为通过。

下一步：客机跳过 Update 的 dry run（先冻结模拟、再恢复），确认可逆性；再决定是否
继续优化高实体数采集/序列化。

## P1f 结果：首次“跳过 Update”dry run 已通过（2026-11-02）

`--skip-probe --candidate-rva 0x2fadc0 --skip-ms 2000`：钩子确认进入局内后，
在 2 秒内不执行 `Game.Update`（直接 `ret`），随后恢复并禁用钩子。
样本：`authority/runs/skip-20261102-3/skip-probe.json`。

| 指标 | 结果 |
|---|---|
| 跳过调用数 | 59 |
| 跳过期间帧号变化 | 0（`2 → 2`） |
| 恢复后帧号 | 3（`recovered=true`） |
| 钩子撤销 | 成功 |
| `probe_passed` | true |
| 游戏进程 | 响应正常，无崩溃 |

注意：本次 skip 发生在**局内很早期（帧 2）**；之后用户切到浏览器，游戏失焦自动暂停，
帧号停在 558，这不是钩子残留。重新聚焦后游戏正常。跳过模式会停用 Lua 观察器，
所以 observer 覆盖层消失/停帧属预期。

尚未验证：正常房间中段、较长时间（>5 秒）的跳过；跳过期间输入/动画/音频表现；
双机场景下的客机跳过语义。

## P1g 更正：跳过目标改为 `0x554cd0`（2026-11-02）

P1f 的“通过”只说明 `0x2fadc0` 可以被跳过并恢复；它**不能冻结角色**。
加玩家位置采样后确认：

- `0x2fadc0` 跳过 2 秒：帧号不动，但玩家位移 **150.38 单位**（`skip-20261102-5`）；
- 直接调用者 `0x554cd0`（`ret 4`，一个参数）跳过 2 秒：
  - 帧号 `94 → 94`；
  - 玩家位移 **0.0**（`player_moved_during_skip=false`）；
  - 恢复 `recovered=true`，钩子撤销，无崩溃。
  样本：`authority/runs/skip-20261102-7/skip-probe.json`。

因此：

- **真正的每帧模拟入口 = `0x554cd0`**，后续客机跳过必须用它，并保留 `ret 4` 调用约定；
- `0x2fadc0` 是帧计数/子更新，不是完整模拟入口；
- 下一轮应把 skip 目标切到 `0x554cd0`，再验证正常房间 5 秒、多轮、输入/动画恢复。

## P1h 离线状态模型与链路（2026-11-02，没有游戏内验证）

这一步在没有 `isaac-ng`、Steam 和第二台机器的环境里完成。它不把 `playable` 改成 true，也不代替 `skip-20261102-7` 之后仍缺的实机测量。

### 指针无关快照

`NativeCaptureBuilder`（`authority/native/state_model.hpp`）生成和 `probe.cpp` 相同的原生采集字节。采集包**仍然包含主机进程内指针**。`HostPublisher` 才把指针去掉：

- 玩家身份是玩家向量槽位，不是 `EntityPlayer*`。
- 实体身份是主机侧 `(pointer, InitSeed)` 映射出的递增网络 id。指针只要缺席一帧，即使后来地址和种子都相同，也会分配新 id。
- 线上包魔数 `IAW1`、版本 1、CRC-32（IEEE），关键帧或增量二选一。换房，或距离上一关键帧满 30 帧，强制关键帧。帧号变小就是新一局，即使房间号不变，也会重置上一快照和上一关键帧帧号并发出关键帧。同一帧、没有 `force_keyframe()`、也没有换房，仍是 `stale`。
- `GuestIngress` 按序号丢掉重复包，最多缓冲 32 个尚未接上的增量；缺包时不跳帧。关键帧再按序号排序：`highest_seq_ != 0` 且序号更小的关键帧是 `stale`，不会把房间滚回去，正在等待关键帧时也一样。序号更大的关键帧就是更新的一帧，帧号变小也应用，所以同一房间重开不必先 `resync()`。应用该关键帧时丢掉缓冲里序号更小的包；之后序号更小的增量也是 `stale`，旧局增量不会在新局帧号追上时被接上。`resync()` 清空序号窗口和已应用世界，并把 `highest_seq_` 清零，所以另一台从序号 1 开始的主机仍可接受，帧号不限。同一帧换房的更新序号关键帧会应用。
- `GuestView::plan()` 只列出位置（`+0x33C`）、速度（`+0x360`）和大小（`+0x370`）的逻辑写入。它不写进程内存。动画、道具、房间格子、Stage、实体关联都不在包里。

合成夹具 `authority/fixtures/state/native_capture_room_start.bin` 用了文档里的低实体形状（玩家约 `(320, 380)`、Size 10、房间 71）。它是模式样例，不是某次实机抓包的原字节。

### 链路

`AuthorityLink` 坐在 `Transport` 后面。当前唯一实现是 `LoopbackHub`（可丢、可重复、可对调相邻两包）。

- 控制、状态、输入分通道。hello 要求相反角色、`research_only = 1`、相同会话和 32 字节清单。清单或版本不匹配会锁死，不能被后到的正确 hello 解开。
- 超过 3 秒没有对端包就进入 paused。`reconnect` 之后主机发出的下一包必须是关键帧。
- 客机不能发布世界。输入只接受槽位 1。
- 预定的 Steam 通道号是 197461 / 197462 / 197463。`SteamTransport` **没有**改用它们，实机仍只在 `kChannel` 197460 上跑旧的 JSON/CBOR 会话。

### 探针契约（仍未在本环境运行）

- `--packet-rva` 现在才安装第二把钩子，默认关闭。原先跳过探针默认去钩 `0x2fadc0`，但没有给 `g_call_probe_entry` 赋值，游戏线程会调用空函数指针。这个修复没有在游戏里跑过。
- 组包改为读全局 `Game*`（`base + 0x871678`），不读钩子的 `ecx`。
- 跳过探针的采样窗口上限从 120 帧提高到 2048，以便覆盖约 10 秒。调用探针的 120 帧上限不变。
- 高实体数的游戏内字节和时间**没有新数字**。离线测试里 60 个实体的纯编码大约是几百微秒，那不是游戏内逐实体读内存的时间。上次实机仍是低实体数约 231 µs/帧。

### 本环境实际跑过的测试

- `authority-tests`：38 项，和原来的协议测试相同。`live_game_test=false`。
- `authority-state-tests`：245 项，含同房间重开后客机不调用 `resync()` 跟上新一局，以及更小序号关键帧不能把房间滚回去。输出里 `playable=false`、`in_game_timing=false`、`two_machine_test=false`。
- 同一套测试用 `g++ -m32` 编成 i686 后再跑过一遍，仍是 38 项和 245 项。
- `probe.cpp` 里的 MSVC `__declspec(naked)` / `__asm` 不能用 g++ 或 mingw 编译。注入器仍然要在 Windows 上用 MSVC Win32 构建。本环境没有构建 DLL，也没有启动游戏。








