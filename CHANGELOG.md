# Changelog

## v2.0.0（ISAAC Coop Stability v2）

- guard v2：检测 API 全部做能力探测与 pcall；区分 `remote_player` / `local_coop` /
  `single_owner` / `single_player` / `coop_fallback` / `detection_unavailable`，异常时保留
  预警并写日志，不崩溃；每局最多记录一次判定，运行中由“保留”翻转为“拦截”时再记一次。
- 安装器 v2（Python 与 PowerShell 行为一致）：
  - 默认只接受已验证的 `main.lua` SHA-256；未知版本默认拒绝。
  - `--allow-unreviewed` / `-AllowUnreviewed` 时执行 8 条结构不变量校验（回调注册、函数布局、
    spawn 函数可追溯、dispatcher 调用位置等），并在 manifest/status 中标记“未审核版本”。
  - 新增 `verify`：输出双方可比较的 12 位 `PATCH FINGERPRINT`。
  - 新增 `diagnose`：读取 `savedatapath.txt`、`log.txt`、`online_logs/desyncs/sessions` 与
    `*diff*.txt`，报告补丁状态、guard 日志与 desync 会话统计。
  - v1 → v2 迁移：识别历史 V1 标记，先用文本手术还原原版、校验备份，再安装 v2。
  - 过期备份自动轮换（改名保留，不删除）；备份缺失/被改时进入 `patched_needs_attention`，
    拒绝覆盖。
  - 还原时删除 v2 manifest（备份保留）。
- 打包：`artifacts/ISAAC-Coop-Stability-v2.zip` + `.sha256`；不包含模组本体。
- 文档：新增 README、CHANGELOG；重写使用说明；补充验证协议、状态表与限制声明。
- 测试：49 项离线测试，覆盖 Lua 5.3 编译、guard 行为矩阵、安装/还原/迁移、未知版本策略、
  诊断解析、Python/PowerShell 一致性、打包校验。
- 兼容：保留旧版 `main.lua.isaac-stability-v1.backup` 与 `isaac-stability-v1.json` 的识别；
  authority 研究工具的基线脚本仍可使用（允许状态新增 `patched_v1_verified`）。

## v1（2026-09）

- 首次发布：按整文件 SHA-256 校验后，在 `postRender` 前注入 guard，合作模式阻止
  Watch out, laser! 生成 `1000.198.0` 预警实体；提供 install/status/restore 与离线测试。
