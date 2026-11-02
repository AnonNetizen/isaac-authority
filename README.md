# ISAAC Coop Stability v2

> 本仓库同时包含 `authority/` 主机权威联机研究原型。该原型**尚不可玩**（`playable=false`）；
> 接手或继续开发前请先读 [AGENTS.md](AGENTS.md)、[authority/docs/AUTHORITY_P1.md](authority/docs/AUTHORITY_P1.md)
> 与 [authority/GOAL_STATUS.md](authority/GOAL_STATUS.md)。

面向《以撒的结合：忏悔+》（Repentance+，J460）的**联机兼容补丁工具**，针对创意工坊模组
[Watch out, laser!](https://steamcommunity.com/sharedfiles/filedetails/?id=2887926286)（ID 2887926286）。

它只做一件事：**在合作模式中阻止该模组生成/更新激光预警实体**，从而消掉一条已定位的
desync 触发路径。单人模式、Jacob/Esau 等成对角色不受影响，也不关闭官方 desync 检查。

> 重要：本工具是**针对性缓解**，不是通用“免 desync 补丁”。它只覆盖 Watch out, laser!
> 生成 `1000.198.0`（`EffectVariant.GENERIC_TRACER`）与 Laser 实体这一条路径；
> 其他模组、原版或网络问题造成的 desync 不在范围内。真实联机改善仍需要你和队友按下面的
> 协议实测，本项目不宣称已经修复。

## 原理（为什么关掉它会减少掉线）

该模组的 `postRender`（实际注册在 `POST_UPDATE`）会对即将发射 Brimstone 的敌人调用
`LaserIndicator` / `TargetLaserIndicator`，并用 `Isaac.Spawn(1000, 198, ...)` 生成预警特效，
随后设置位置并调用 `indicator:Update()`。两端各自生成、各自更新的这类实体在 desync 检查中
出现过约 0.001 的坐标差（2026-09-05 的一份记录）。

补丁在 `postRender` 入口插入一个检查：合作模式下一旦命中，整段预警逻辑直接返回，因此不会再
生成这些实体；单人模式照常执行。判定会锁存到本局结束，避免中途反复生成/消失。

## 使用条件

- 游戏版本：Repentance+ J460（`isaac-ng.exe` v1.9.7.17 系列）。
- 模组：双方都订阅 **Watch out, laser!**，且版本一致（本工具已验证版本 1.1，
  `main.lua` SHA-256 为 `8651d515…9a25b`）。
- **双方都要安装**，并且 `verify` 显示的 `PATCH FINGERPRINT` 必须完全一致；
  **只装一边比两边都不装更糟**（两端行为不同会制造新的差异）。
- 安装/还原前退出游戏；安装后**新开一局**才会生效。
- Windows 10/11，使用系统自带 PowerShell 即可，不需要安装 Python。

## 一键使用

解压发布包后：

| 文件 | 作用 |
| --- | --- |
| `install.cmd` | 安装补丁（自动查找 Steam 库与模组目录） |
| `status.cmd` | 查看当前状态 |
| `verify.cmd` | 显示双方需要对比的 `PATCH FINGERPRINT` |
| `restore.cmd` | 精确还原模组原始 `main.lua`（保留备份） |
| `diagnose.cmd` | 读取游戏日志与联机 desync 会话记录，辅助判断是否生效 |

建议流程：

1. 双方都退出游戏。
2. 双方双击 `install.cmd`，看到 `"status": "patched_verified"`。
3. 双方双击 `verify.cmd`，确认 `PATCH FINGERPRINT` 完全一致。
4. 启动游戏，进入联机合作，**新开一局**。
5. 游戏 `log.txt` 中应出现 `[ISAAC-STABILITY] v2 ... indicators=disabled`。
6. 打完后双方运行 `diagnose.cmd`，记录 desync 会话数量，与安装前对比。

如果想还原：退出游戏，双击 `restore.cmd`，`status` 变为 `original_supported`。

## 状态含义

| 状态 | 含义 |
| --- | --- |
| `original_supported` | 模组是已知原始版本，补丁未安装（可以安装） |
| `patched_verified` | v2 补丁已安装，且与备份逐字节校验一致 |
| `patched_v1_verified` | 旧的 v1 补丁仍在，运行 `install` 可升级到 v2 |
| `unsupported_version` | 模组版本未验证；默认拒绝修改，可加 `-AllowUnreviewed`（见下） |
| `patched_needs_attention` | 有补丁标记但备份缺失/被改，工具不会覆盖，需要人工处理 |

`verify` 输出中的 `fingerprint` 是已安装 `main.lua` SHA-256 的前 12 位大写，双方必须相同。
`patched_sha256` 是完整哈希，也用于人工核对。

## 诊断

`diagnose.cmd` 会读取：

- 游戏的 `savedatapath.txt` 定位存档目录（也可用 `-SaveDir` 指定）；
- `log.txt` 中最近的 `[ISAAC-STABILITY]` 记录与 `NetDesyncHandler::RemoveUser` 事件数；
- `online_logs/desyncs/sessions/*/log.txt` 的历史会话（时间、清理事件数、用户、存档快照）；
- 存档目录下可能存在的 `*diff*.txt`。

注意：会话计数只反映 `NetDesyncHandler` 的清理/掉线事件，**不能证明**某个实体就是根因；
它用于对比打补丁前后的趋势。

## 常见问题

- **提示 `unsupported_version`**：Steam 更新了模组。默认不改未知版本是安全策略。
  可以确认新版本结构仍兼容后运行 `install.cmd` 时加 `-AllowUnreviewed`（Python 为
  `--allow-unreviewed`），工具会做结构校验并在状态中标记“未审核版本”。更新后建议反馈给维护者。
- **Steam 更新后补丁消失**：更新会覆盖 `main.lua`，补丁失效；重新运行 `install.cmd` 即可。
  旧备份若与当前版本不符，会被自动改名为 `main.lua.isaac-stability-v1.backup.<hash8>` 保留，不会删除。
- **单人/本地双人**：单人、Jacob/Esau 保留预警。若当前游戏版本没有 `IsLocalPlayer` 接口，
  本地双人合作也会被保守地关闭预警（与联网无法区分）。
- **只装了一边**：请先还原或让双方都装；指纹不一致时不要开始联机。
- **日志在哪里**：`%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance+\log.txt`。

## 开发者

```powershell
# 安装/查看/还原（Python 3，仅开发与测试需要）
py -3 patch_watch_out_laser.py status
py -3 patch_watch_out_laser.py install
py -3 patch_watch_out_laser.py verify
py -3 patch_watch_out_laser.py diagnose
py -3 patch_watch_out_laser.py restore

# 全量离线测试（Lua 5.3 语法、guard 行为、安装器、v1 迁移、PowerShell 对等、打包）
$env:ISAAC_LASER_SOURCE = 'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth\mods\watch_out_laser!_2887926286\main.lua'
py -3 test_stability_patch.py

# 构建发布包（artifacts/ISAAC-Coop-Stability-v2.zip + .sha256）
py -3 build_release.py
```

`legacy/coop_guard_v1.lua` 保留历史 v1 注入内容，仅用于迁移识别与测试。
本工具不重新分发模组本体，只包含补丁文件与脚本。

## 安全与回滚

- 只写模组目录内的 `main.lua`、复用既有备份 `main.lua.isaac-stability-v1.backup`，
  并新增说明文件 `isaac-stability.json`（v2 manifest）；旧 `isaac-stability-v1.json` 不删除。
- 写入使用同目录临时文件 + 原子替换，写前再次确认哈希未变化。
- 还原只使用已校验的备份，拒绝覆盖未知内容；备份永不自动删除。
- 不修改游戏 exe、存档或其他模组。

## 已知限制（诚实声明）

1. 真实双机掉线改善**尚未验证**：需要双方实测并按 `diagnose` 对比，不能仅凭离线测试宣称。
2. 补丁会关闭该模组在合作模式中的激光预警视觉；这是本方案的代价。
3. 版本策略默认只信任已验证的 `main.lua` 哈希；未审核版本必须显式开启结构补丁。
4. 只有一台测试电脑时无法自动完成双机联机验收。
