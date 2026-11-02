# 权威字段与个人意图：API 层通过，用户规则门槛失败

本候选是独立 Windows x86 命令行研究入口 `ia-lua533-world-view-1`。没有启动游戏、写入个人存档或修改冻结的 MCM/EID 源码。尚不能实际联机，未通过完整菜单、HUD 或通用模组隔离验收。

## 已实现

主机在 authority 阶段可更新金币模型中的玩家位置、速度、控制开关和已登记的 `SEED_NO_HUD` 状态。每次操作记录前值、请求值、状态序号、会话/角色/事件/帧身份及动态调用上下文。调用证据包括冻结源码 SHA256、函数字节码 SHA256 和实际 Lua 指令位置；没有跨进程传送地址。位置、参数或调用顺序相似不构成语义匹配证明。

个人 presentation 阶段的这些写入生成意图，不提交权威世界；主机自己的 presentation 同样不能提交。查询读取权威模型。已核对为 void 的方法返回零个 Lua 结果；没有伪造带返回值的修改结果。未登记的种子效果、世界属性和非授权阶段明确失败。意图尚无权威用途对应，绘制帧仍不可发布。

字段更新只访问已观察的目标字段、相关子路径及祖先路径，不重新遍历全部字段索引。值没有改变时保留纯查询的值版本，逻辑写入仍推进操作状态序号。A→B→A 会失效。原生 ItemConfig 受控对象的内部注册表访问与真正查询依赖分开，避免冷缓存创建污染读集合；真正的可用性仍记录精确字段版本。

失败由接受历史重建上下文，恢复模型世界、RNG、个人配置、私有变量及绘制/音效草稿。重复帧复用父候选的回执，不重复提交世界。每帧最多 512 条/128 KiB 世界记录，调用栈最多 6 层，单函数字节码审计最多 1 MiB。失败现场最多保留 64 KiB 记录；更大时明确记录省略字节数和 SHA256，不把省略当作完整证据。

## 道具数据的来源与限制

读取本机 `repentance.a` 中的 `items.xml`、`items_metadata.xml`、`wisps.xml`，只冻结道具 1、73、78 的必要元数据及范围哈希，实际校验范围共 156921 字节，没有复制游戏图片、字体或整个资源包。

ID、名称键、品质、类型、成就编号等来自 XML 和冻结枚举。部分默认值及 active WISP 标签依据 XML 契约和对应 wisp 条目推导；这些是推导，未重新抽样 J460 原生 getter，不能声称完整 ItemConfig 等价。模组 XML 覆盖也尚未接通。

`IsAvailable()` 来自显式的权威查询场景，独立于静态 XML。它不能仅凭成就编号计算，也不能当成当前个人存档的解锁结果；实际游戏接入时须读取对应运行状态。场景分别包含可用和不可用值，缺失或非布尔值拒绝，不默认全部可用。API 契约参考 [ItemConfigItem](https://wofsauge.github.io/IsaacDocs/rep/ItemConfig_Item.html)、[Seeds](https://wofsauge.github.io/IsaacDocs/rep/Seeds.html)。

## 分开统计的验收

正式子进程上限仍为 1000 万工作单位、5 秒、1 GiB。

| 清单 | 结果 | 解释 |
|---|---|---|
| `world_view_v6.json` | 35 项运行两次，通过 | 24 项 API/普通 Lua 模型行为，11 项预期拒绝；不是用户规则兼容通过 |
| 原 `menu_environment_v3.json` | 37 项回归通过 | 新模式关闭时保持父候选行为 |
| `world_view_required_projection_v3.json` | 1 项功能失败 | 个人设置仍为 2，关联奖励 HUD 应取主机 1，目前仍显示 2 |
| `world_view_required_mixed_v1.json` | 1 项功能失败 | 同一个混合回调在个人环境执行仍触发 AddCoins 权限拒绝；不能算兼容通过 |
| `world_view_real_v6.json` | 6 项，5 项失败 | 只有关闭状态的 MCM 回调完成；菜单和描述绘制未通过 |

最终结果目录为 `world-view-v7`、`world-view-repeat-v7`、`world-view-menu-regressions-v2`、`world-view-required-projection-v5`、`world-view-required-mixed-v2` 和 `world-view-real-v7`。封存文件记录已完成子进程的最大工作量、耗时和提交内存；这些短模型数字不是完整模组或实时帧性能。

第一个必过反例保留原始源码：主机 amount=1，个人 amount=2。API 普通执行测试以原始 Lua 输出 2 作对照；**用户规则测试明确要求 HUD 输出 1、个人存档仍保留 2，目前失败**。不能通过修改预期把原始输出算成用途投影成功。

第二个必过反例要求主机和个人执行同一份混合回调：修改前应看到旧状态，修改后应看到对应权威新状态，且金币只结算一次。当前 AddCoins 拒绝阻止了第二次提交，却也阻止了回调完成。因此跨上下文的查询时点和通用混合回调都未通过；本候选只证明主机模型自身的顺序更新。

## 真实源码执行到的位置

场景保留两名玩家和一个可被 EID 描述的道具。EID 默认每两次 render 才刷新描述；现在正常道具案例执行两帧并要求非空 HUD，未拿第一帧的零绘制当通过。另测不可用道具触发的真实解锁警告分支，不删除正常道具案例。

| 场景 | 当前失败入口 |
|---|---|
| MCM 关闭状态 PostRender | 完成，但没有菜单画面证明 |
| MCM / 组合按个人按键打开 | `Sprite.Render contract not implemented` |
| EID / 组合正常道具描述第二帧 | `Frozen module path outside registered roots`，实参是 `ReplaceSpritesheet(0, "")` |
| EID 权威解锁警告 | `Sprite property write not implemented: Scale` |

空图片名在 EID 中用于背景清除，当前严格资源入口拒绝了它；这不是测试试图越出目录，也不能把它当缺失图片直接吞掉。后续须验证空图片清除的原生语义，并接入完整精灵状态程序；不能凭最终 GetFrame 重建。

MCM 的失败现场完整保留了 7 条个人世界意图：一个种子效果操作、两名玩家各自的速度、位置和控制开关。它们均未提交权威模型。只记录意图尚未满足菜单行为和权威用途对应，因此该证据不能把完整 UI 门槛改为通过。

## 历史与下一步

初轮模型失败保留：一次测试读错上下文，以及两项内部注册表依赖导致的失效。修改了测试上下文和受控对象实现，没有修改原模组反例。历史报告、二进制哈希和驱动压缩副本保留。首轮 EID 单帧回调完成但无 HUD 的记录也保留，并由双帧非空验收取代其兼容性解释。

最终来源校验还发现：未修改 Lua 的原始 dofile 会为另行登记的备份文件报告绝对物理路径。现在用冻结文件的精确物理路径索引补足模块归属，保留命名空间路径查询；歧义直接拒绝，不按查找顺序选择。没有回读历史日志或每次重建目录索引。独立的双根模块案例在不启用 SDK 根覆盖的情况下确认：备用文件 require 的同名模块来自自身所属根，而非主根。`world-view-source-identity-v1` 保留该项三进程对照。

下一步优先连接**最小生产者和消费关系**：字段、寄存器和 upvalue 的版本应把配置来源、世界贡献及 HUD 使用位置关联起来。重用现有来源绑定设施，先审计其覆盖范围，不重新开启初始化的全量追踪。只在能证明唯一权威贡献时选择游戏视图；设置菜单和无关个人设置继续保留个人视图。调用上下文和指令位置只作证据，不能直接匹配语义。

必须先让上述两个功能门槛通过，覆盖数值交换、别名、闭包、缓存函数、保存重载和失败恢复，再继续精灵程序与菜单导航。未知或歧义仍明确失败；功能需求被拒绝仍算失败。

接受历史仍随会话增长，长期检查点和回收未完成。没有通用值版本图或已证明的双视图、真实客户端停模拟、实体同步、通信、重连或个人解锁。没有新建 ZIP 或解压副本，独立包解压复现仍未完成。

## 复现

```powershell
python -B authority/tools/verify_world_view.py
python -B authority/tools/run_world_view.py run --output authority/reports/world-view-local-check
python -B authority/tools/run_world_view.py projection --output authority/reports/world-view-local-required
python -B authority/tools/check_world_view_mixed_gate.py --output authority/reports/world-view-local-mixed
```

输出目录须不存在。后两条当前应失败并返回 1；那是未满足的功能要求，不是“预期拒绝通过”。重建使用 `world_view_runtime/prepare.py` 后对该目录配置 Win32 CMake、构建 Release；不重建 Lua，不操作游戏。
