# 审计配额定位与体积候选结果

已确认上一轮三项失败都是文件配额耗尽，单条记录均未超过 8 MiB。完成精确拒绝快照、逐通道账本和有固定工作区的逐记录无损编码。完整性与恢复门槛通过，体积收益有限且有额外计算成本；MCM/EID/组合在最终 5 秒窗口内仍未完成初始化。

保持独立 Windows x86，10000000 工作上限、每子进程 5 秒，文件仍最多 16777216 字节，原始单条最多 8388608 字节。模组源码、个人配置与主机奖励规则不变，没有启动游戏或写个人存档。不宣称任意旧模组、真实菜单、HUD 渲染或联机已经可用。

## 精确拒绝原因

新的 `quota_check` 分别记录记录长度、文件剩余、通道/编号、两项超限标志，以及 pending/submitted/durable 位置。首个失败锁存，后续失败不能覆盖快照。诊断只用固定 33 槽计数器，不读取历史文件；每条记录增加一个计费单位。

先通过原 20 项恢复/完整性案例，加上单条超限、文件耗尽及同时超限三个反例，再通过原样的 37 项模型清单和短基准，才做三项真实诊断：

| 案例 | 被拒通道/编号 | 被拒载荷 | 文件剩余 | 单条超限 | 文件超限 |
|---|---|---:|---:|---|---|
| MCM 中文 | 静态区域 4 / 933 | 238010 B | 164871 B | 否 | 是 |
| EID 中文 | 证据描述 8 / 9132 | 436 B | 314 B | 否 | 是 |
| 组合中文 | 静态区域 4 / 934 | 237915 B | 32116 B | 否 | 是 |

每条还需要 32 字节头部。三项均明确返回 `Audit file quota exceeded`，而不是单条超限或工作预算超限。不能再从“最后一条较大”推断根因。

MCM 的主要原始载荷为值图节点 6779618 B、证据描述 2513673 B、证据位置 1324330 B、图位置 938647 B；节点另有约 1.44 MB 头部。EID/组合分布相似。大量小记录和少数大元数据共同占用空间，不能通过删除失败记录或省略依赖取得通过。

## 无损编码与边界

新增私有 ABI `ia-lua533-audit-volume-1`，源码在 `audit_volume_runtime`，从上一版派生。旧批量运行时、模组和清单保持原样。`volume_stats.inc` 记录原始与存储字节；`wire_codec.hpp` 只处理字节，不判断模组用途或游戏逻辑。

- 记录内容、通道、编号和顺序不变。原格式 ICA1 与逐记录压缩 ICA2 可以混用；无收益或不在编码范围的记录沿用 ICA1。
- 最终只尝试 512 B–256 KiB 的载荷，至少节省 16 字节才使用压缩。大于 256 KiB 的记录照旧直接写入，最大原始记录仍为 8 MiB。
- 编码工作区固定 294912 字节，另保留原 256 KiB 写缓冲。4096 槽字典按代数失效，不保存跨记录历史，不随运行增长。所有哈希命中必须核对实际字节，哈希不用于匹配世界贡献。
- 存储载荷有 CRC，压缩载荷还保存原始长度和原文 CRC。解码长度、距离、字面量、匹配边界、截断和多余输出都检查；先验证长度再分配。当前压缩格式最多展开 256 KiB，未压缩格式保持 8 MiB 上限。
- 文件配额按实际存储字节计算，仍为 16 MiB；没有把解码上限或工作预算扩大。离线流式检查额外限制总展开量最多 64 MiB，且不写出展开副本。
- 扫描、字典工作区、匹配、字面量复制、CRC、解码和原 IO 都计费。只有诊断读取可以解码；执行期历史审计读取继续禁止。
- 原有缓冲提交、刷新、关闭和错误锁存边界不变。故障上下文废弃；金币事务夹具在新上下文重放已接受历史恢复世界、RNG、个人配置、私有变量、保存与绘制，不向失败文件续写。

可用 `IA_AUDIT_WIRE_RAW=1` 对照原存储格式。模式选择不暴露给 Lua，不修改模组 JSON 或个人设置。

## 完整性与恢复验收

最终二进制通过 23 项原格式边界/恢复案例、9 项原生编码/压缩恢复案例，以及 5 项独立畸形载荷检查。包括随机数据回退、所有字节值、窗口边界、重叠匹配、固定工作区、物理文件配额、损坏、非法距离、截断、原文 CRC 和保存/私有变量/绘制暂存后的失败恢复。压缩恢复后的完整审计与无故障对照相同，重复帧仍不重复计算或保存。

原有 37 项模型清单按原预期回归：27 项功能和 10 项拒绝诊断，最终耗时 27.15 秒。普通 Lua 结果、来源 oracle、个人值、主机 HUD 值、消费证明、字段/upvalue 和独立解码重建均通过；所有完成的上下文都确认成功封存、pending=0、durable=文件长度。执行期历史审计读取为 0。拒绝诊断不计作新增兼容功能。

独立 Python 解码器 `audit_wire.py` 和 `read_volume_audit.py` 不调用 DLL，流式恢复每条原始记录。短基准将压缩和原格式都归一成原始 ICA1 字节流，SHA256 必须一致；同时比较完整语义证明及两次输出。没有仅比较记录数量，也没有写巨型解压文件。

## 收窄策略及成本

最初从 128 B 开始压缩。较大循环案例体积减少约 9%，计费却增加约 53%，耗时也略增；这一策略未进入真实初始化测试。保留其报告，最终将起点提高到 512 B，避免在大量小记录上尝试。

最终同一二进制、相同输入、每模式两次并反向排序的短基准：

| 案例 | 原格式/压缩文件 | 体积减少 | 原格式/压缩计费 | 原格式/压缩平均墙钟 |
|---|---:|---:|---:|---:|
| root-128 | 359765 / 328213 B | 8.8% | 124784 / 151051 | 0.202 / 0.211 s |
| graph-churn-16 | 3151262 / 3134431 B | 0.5% | 1021419 / 1032967 | 1.254 / 1.286 s |
| dual-config-2 | 35049 / 35049 B | 0% | 约 16423 / 16423 | 0.074 / 0.070 s |

计时包括子进程的刷新、诊断导出及解码；样本很少，不能据此宣称整体加速。较大循环案例把计费增幅降至约 1.1%，但体积收益也下降；此候选不是通用性能解决方案。没有隐去额外费用或通过扩大上限获得通过。

## 最终真实初始化

短测通过后，各进行一次原 5 秒窗口，继续使用有界并发管道收集器：

| 案例 | 结果 | 最后完整工作量快照 | 完整已写文件前缀 | 其中压缩节省 |
|---|---|---:|---:|---:|
| MCM 中文 | 5 秒未完成 | 6731800 | 15509787 B | 1440838 B |
| EID 中文 | 5 秒未完成 | 6595587 | 16520845 B | 1370238 B |
| 组合中文 | 5 秒未完成 | 7150266 | 15509990 B | 1012214 B |

三项仍在首个模组加载阶段；没有完整返回初始化结果。最后账本没有预算拒绝，stderr 只有 bootstrap/enums 完成，没有返回配额拒绝，不能进一步断言初始化完整总工作量。MCM/EID 的已写前缀若还原成原格式已超过原 16 MiB 文件大小，说明压缩确实减轻了文件压力；实际文件始终小于 16 MiB。全部完整前缀通过 CRC 和原文 CRC，强制终止时尚在缓冲中的记录不计成功提交。

本轮出口：拒绝定位通过，编码完整性/恢复通过；收益有限，初始化门槛仍失败。下一步宜按现有逐通道数据研究值图/证据中重复字段的有界共享表示，先证明逐条内容和恢复完全一致，再做短基准；不继续扩大压缩范围、提高预算或延长运行，更不推进真实菜单和联机验收。

## 入口与记录

从 `D:\Coding\ISAAC` 执行，输出目录必须不存在：

```powershell
python -B authority/tools/run_audit_volume_journal.py --output authority/reports/volume-journal-next
python -B authority/tools/run_audit_wire_tests.py --output authority/reports/volume-wire-next
python -B authority/tools/run_audit_volume_gate.py --output authority/reports/volume-model-next --journal-gate authority/reports/volume-journal-next/result.json --wire-gate authority/reports/volume-wire-next/result.json
python -B authority/tools/benchmark_audit_volume.py --output authority/reports/volume-bench-next --gate authority/reports/volume-model-next/result.json
python -B authority/tools/run_audit_volume_initialization.py --output authority/reports/volume-real-next --gate authority/reports/volume-model-next/result.json --benchmark authority/reports/volume-bench-next/result.json
```

原始定位：`reports/audit-volume-diagnosis-v1/result.json`；初版压缩成本：`audit-volume-benchmark-v2/result.json`。最终验收：`audit-volume-journal-v3/result.json`、`audit-volume-wire-v2/result.json`、`audit-volume-model-v3/result.json`、`audit-volume-benchmark-v3/result.json`、`audit-volume-real-v1/result.json`。汇总哈希及清理记录见 `reports/audit-volume-final.json` 和 `audit-volume-build-cleanup.json`。

只增加一个构建目录，不新增 ZIP、模组副本或重复解压。原始审计校验后删除，真实报告合并后移除重复案例 JSON，保留必要的历史判定和紧凑证明。冻结模组、个人存档和受保护的历史源码/二进制哈希未变。
