# 菜单环境候选：基础契约通过，真实 UI 门槛未通过

独立 Windows x86 命令行候选：`ia-lua533-menu-environment-1`。它没有接管游戏模拟，没有网络连接，不能用于实际联机或修复 desync。

## 已实现并验证的部分

- 受控的玩家、实体、房间、楼层、种子查询身份。两名玩家的身份、关系、控制器、物品数量、位置等来自明确快照；查询返回的 Vector 暂为只读视图，未知别名写入拒绝。
- 按字段读取和版本失效，包括 A→B→A。物品数量的普通视图与忽略修改器视图分别登记，不忽略布尔参数。超出 Lua 整数范围的值拒绝。
- 个人数字按键、控制器动作和鼠标快照。`-1` 只在输入快照明确包含该键时可查询，不能凭“未列出的按键释放”推断负数输入。
- 音效 `Play` 捕获原始实参数量和值，保留会话、角色、事件、帧和序号组成的事件身份。每帧 128 条/64 KiB；没有调用真实音频后端，未验证本机播放等价性。
- 每个事件流的帧去重，重复帧返回原回执，不重复计算、保存或生成音效。同号异载荷拒绝；128 条/4 MiB 回执缓存淘汰后，高水位仍阻止旧帧重新执行。
- 失败后新建上下文、重放接受历史，恢复配置、私有变量、实体私有数据及绘制/音效帧。过期实体和房间对象拒绝使用，并移除不再需要的运行时强引用。
- 冻结目录允许通用的逐文件物理来源登记。加载仍核对工作区边界、重解析点、源码大小和 SHA256；模组收到原虚拟路径，不修改源码来适配运行时。

## 验收证据

正式上限保持每个子进程 1000 万工作单位、5 秒、1 GiB。普通返回值、字符串字节、世界及配置状态均对照未修改 Lua，并以两个独立研究进程检查状态和证据重复性。

| 清单 | 结果 | 含义 |
|---|---|---|
| `menu_environment_v3.json` | 37 项，完整运行两次 | 23 项功能、14 项预期拒绝；拒绝不算兼容通过 |
| `menu_environment_edges_v2.json` | 5 项 | 回执淘汰、过期房间、悬空关系、私有数据隔离和整数越界 |
| 原 `ui_flow_v2.json` | 36 项回归 | 不启用新环境时保留原契约；不代表所有历史运行时重新通过 |
| `menu_environment_real_v3.json` | 5 项，只有关闭菜单的 MCM 回调完成 | EID、组合 HUD、MCM 打开及组合打开均为功能失败 |

最终二进制的结果位于 `reports/menu-environment-v4`、`menu-environment-repeat-v4`、`menu-environment-edges-v2`、`menu-environment-flow-regressions-v2` 和 `menu-environment-real-v4`。最终封存记录给出每文件哈希、压缩报告与原始内容哈希、实际资源用量。

## 修正历史冻结基线

历史冻结 MCM 的 `scripts/modconfig.lua` 含有早期实验的在线菜单拦截块。双人场景按 L 后会播放拒绝音效并返回；首轮驱动只检查回调完成，曾把这个案例标记为通过，实际 `IsVisible=false` 且没有绘制。

原报告和驱动压缩副本保留，明确更正见 `reports/menu-environment-baseline-review.json`。首次模型测试还有一项诊断测试在错误阶段调用音效，未到达预期的无效声音 ID 检查；新清单从真实呈现回调测试它，原失败记录未改。

安装目录的 `modconfig.lua.iodg.bak` 与旧冻结文件逐字节比较，仅差一段插入的拦截补丁。新基线原样复制备份字节到 `research/menu_environment/pristine_modconfig.lua`，SHA256 为 `19a0366d7db6faae98a94dd46c5111f5ec4e5d4dc1bc456cb7fd3cacac3ffaf2`。其余 Lua 文件和资源沿用旧冻结哈希，无整份模组或资源复制。该证据证明恢复到本机实验前备份；不声称已证明与上游发行包完全一致。游戏安装目录与个人存档均未写入。

## 真实回调的失败位置

| 场景 | 首个未支持入口 |
|---|---|
| MCM 关闭状态的 PostRender | 无；回调完成，不证明菜单显示 |
| EID / 组合 PostRender | `Uncaptured ItemConfig lookup: 0:78`：真实解锁检查需要道具查询，当前受控目录没有该记录 |
| MCM / 组合使用个人按键打开菜单 | `Unregistered seeds API: AddSeedEffect`：原源码进入修改世界的分支 |

MCM 打开流程还会写入玩家速度、位置及 `ControlsEnabled`。不能仅补一个种子空操作就称为完整菜单隔离。下一批应登记有明确语义的世界读写和个人意图，将其接入权威记录及用途投影；继续验证个人界面、世界结果和失败恢复，保持源码不变。EID 应补齐有证据的 ItemConfig 查询及解锁状态；不得把所有道具设为可用、关闭警告或换空场景跳过检查。之后才继续精灵程序捕获、真实导航和配置修改。

## 当前限制

快照是明确构造的研究场景，并非从 J460 实机提取的完整世界状态。字体和动画的历史限定契约保留；当前不支持完整精灵绘制重放，不证明原生环境或画面等价性。

旧的 Slice3 用途约定继续保留；新的 API 边界架构还没有接通通用菜单用途或混合回调权威引用。因此个人绘制帧仍不可发布，不能宣称真实 MCM/EID 的完整配置独立和奖励投影已通过。

强引用、输入读集合、观察字段、音效队列和回执均有容量限制，但研究 Session 仍在内存中保留已接受历史用于重建。长会话的检查点、历史压缩和长期回收尚未完成；5 秒诊断保护不能当作实时帧性能或长期内存证明。

没有新建 ZIP、复制游戏图片字体或保留解压树；该阶段交付哈希封存及压缩测试记录，尚未完成独立分发包的解压复现。原生世界接管、通信、重连、个人进度和双机 30 分钟验收都未完成。

## 命令

在工作区根目录使用命令行：

```powershell
python -B authority/tools/verify_menu_environment.py
python -B authority/tools/run_menu_environment.py run --output authority/reports/menu-environment-local-check
```

输出目录必须不存在。真实 UI 诊断通过以下命令复现，当前应得到上述功能失败，退出码为 1：

```powershell
python -B authority/tools/run_menu_environment.py real --output authority/reports/menu-environment-local-real
```

重建先运行 `python -B authority/menu_runtime/prepare.py`，再用 Visual Studio CMake 对 `authority/menu_runtime` 配置 Win32 并构建 Release。`prepare.py` 校验封存的父候选，不重建 Lua，不启动游戏。
