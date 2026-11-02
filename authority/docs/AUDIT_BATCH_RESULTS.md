# 固定容量审计批量写入结果

批量写入和恢复门槛通过。真实 MCM/EID 初始化仍失败：三项在约 3.4–3.8 秒返回审计配额拒绝，没有完成初始化，没有触发 1000 万工作上限。没有推进真实绘制、菜单导航、游戏接管或联机。

## 已实现

私有 ABI `ia-lua533-audit-batch-1`，仅独立 Windows x86 命令行。`audit_batch_runtime/prepare.py` 从已验收的 init-profile 派生，不修改旧运行时、冻结模组或已有清单。

- 每个审计上下文固定增加 256 KiB 缓冲，无异步写入队列。小记录完整复制入队，满时同步提交；超过容量的记录先排空再直接分块写，仍受原 8 MiB 单条限制。测试文件上限保持 16 MiB。
- `bytes/records` 是逻辑接受位置；`submitted_*` 只有整批 WriteFile 成功才前移；`durable_*` 只有 FlushFileBuffers 成功才前移。结构完整的文件前缀不等于已接受一帧。所有旧 CRC、顺序、编号、偏移和最终审计字节保持一致。
- 执行期历史读取继续禁止，拒绝发生在任何排空操作之前。显式诊断读取先排空缓冲，再读取；不会把审计当作执行缓存。
- CLI 在阶段观测发布前刷新，包括回收和检查产生的记录；真实源码入口在枚举、模组加载边界刷新。成功结束必须 `close_checked()`，确认缓冲清空并刷新后关闭。析构是异常放弃，不隐式刷新后假称成功。
- 复制、CRC、真实 IO 和提交检查计费；写入、配额、短写、刷新及预算失败锁存。故障上下文不能继续读、写、刷新或提交。金币事务夹具实现并验证丢弃暂存状态、在新上下文重放已接受历史的恢复策略；真实源码 CLI 对故障返回拒绝并销毁上下文，不自动恢复游戏或向失败文件续写。

源实现：`audit_batch_runtime/batch_journal.hpp`。即时写入诊断开关 `IA_AUDIT_IMMEDIATE=1` 可在同一 DLL 内对照。两个模式使用相同的来源判定、证据索引、世界规则和输出格式。

## 完整性和失败恢复

20 个独立 Journal 案例全部通过，总耗时 1.45 秒，每子进程最多 5 秒、批次最多 60 秒：精确容量、跨界、大记录、空记录、先读后写、非法执行读取、文件配额、计费拒绝、短写、部分写后失败、刷新失败、关闭失败、校验损坏、线程限制、重复帧、未封存放弃和强制结束。部分写入不会推进声明的提交前缀，刷新失败不会推进 durable 前缀，故障后不能再做 IO。

三个恢复案例分别在暂存配置保存、私有变量和绘制后触发写入失败。金币、个人配置、私有变量、RNG、保存计数和绘制队列均恢复到已接受帧；新上下文重放历史后的结果、RNG 及审计字节与无故障对照相同。重复帧不再次保存、计算 RNG 或写审计，同编号不同负载拒绝。这证明金币事务模型，不能代替真实游戏存档或网络重连验收。

原有冻结 37 项模型清单原样通过：27 项功能、10 项拒绝诊断，耗时 23.95 秒。核对未修改 Lua 的普通结果、原来源 oracle、个人配置和权威 HUD 值、上下文/字段/upvalue、独立审计重建与重复执行。30 项可比较案例与上一版 DLL 的完整审计 SHA256 相同；32 项返回完整报告的案例都验证成功关闭、pending=0、durable=logical。执行期历史审计读取仍为 0。拒绝诊断单独统计，不当成功能兼容。

## 短基准

同一个二进制，每模式每案例运行两次，第二轮反转顺序；计时包括阶段刷新、诊断导出和进程结束。样本很少，不给出统计速度保证。

| 冻结案例 | 即时写入平均墙钟 | 批量平均墙钟 | 即时/批量 WriteFile 次数 | 即时/批量计费 |
|---|---:|---:|---:|---:|
| root-128 | 0.230 s | 0.186 s | 4306 / 8 | 120062 / 122631 |
| graph-churn-16 | 1.412 s | 1.148 s | 29856 / 51 | 979990 / 1006491 |
| dual-config-2 | 0.067 s | 0.058 s | 484 / 5 | 约 15960 / 16179 |

较大案例墙钟约少 19%，工作量反而增加约 2.7%，来自显式计费的缓冲复制；没有免除这部分开销。所有模式的功能证明和完整审计字节相同。纯 Journal 6000 条记录测试中，WriteFile 12000 → 14，定位 6000 → 4，文件均为 863898 字节且 SHA256 相同。原数量和内存上限保持；缓冲实测峰值不超过 262144 字节。

## 真实源码结果与收集器修复

通过上述门槛后，MCM、EID、组合先各做一次 5 秒窗口。三项日志已在约 3 秒记录审计拒绝，但旧收集器只在进程退出后才读取输出；47–76 KiB 结束报告填满 Windows 管道，进程等待输出被误记为超时。第一批 `audit-batch-real-v1` 原样保留为诊断历史，不拿它的 5 秒解释初始化耗时。

新 `bounded_profile_child.py` 同时读取 stdout/stderr，分别最多保留 1 MiB / 64 KiB；超出即终止。主线程继续采样固定共享页，保留原 5 秒截止和最多 64 个进度点。双管道输出、捕获限额和 0.4 秒截止三个独立检查通过。随后同一 DLL、同一清单仅复测一批：

| 案例 | 完整返回时间 | 总计费 | 加载状态 | 结论 |
|---|---:|---:|---|---|
| MCM 中文 | 3.365 s | 5314887 | 首个模组未完成 | 审计配额拒绝 |
| EID 中文 | 3.685 s | 5067220 | 首个模组未完成 | 审计配额拒绝 |
| 组合中文 | 3.751 s | 5512316 | 首个模组未完成 | 审计配额拒绝 |

原始报错 `Audit record/disk budget exceeded` 共用单条 8 MiB 与文件 16 MiB 的检查；当前逻辑文件位置分别 16605203、16776713、16662769，已接近文件上限。报告没有记录被拒记录的长度，不能仅凭共用报错断言每项具体命中了哪一个检查。下一步应先补精确拒绝原因，再研究减少审计体积；没有扩大任何限额。

三项都返回 returncode=0 的完整研究报告，兼容性结果为 false；拒绝后继续执行检查确认被阻止，关闭未被报告为成功。已提交文件前缀逐条 CRC 校验，长度与 submitted_bytes 一致；未提交缓冲不计入前缀。1000 万上限未触发，不能推断完整初始化总预算。此时审计 IO 的采样占比已明显降低，值图装配、解码和证据处理成为主要活动；没有因此继续无上限运行。

## 复现

从 `D:\Coding\ISAAC` 执行，目录必须新建；基准和真实入口会验证前置门槛及 DLL 哈希：

```powershell
python -B authority/tools/run_audit_journal_tests.py --output authority/reports/batch-journal-next
python -B authority/tools/run_audit_batch_gate.py --output authority/reports/batch-model-next --journal-gate authority/reports/batch-journal-next/result.json
python -B authority/tools/benchmark_audit_batch.py --output authority/reports/batch-bench-next --gate authority/reports/batch-model-next/result.json
python -B authority/tools/test_bounded_profile_child.py --output authority/reports/batch-pipes-next.json
python -B authority/tools/run_audit_batch_initialization.py --output authority/reports/batch-real-next --gate authority/reports/batch-model-next/result.json --benchmark authority/reports/batch-bench-next/result.json
```

主要证据：`reports/audit-batch-journal-v1/result.json`、`audit-batch-model-v1/result.json`、`audit-batch-benchmark-v1/result.json`、`audit-batch-output-gate.json`、`audit-batch-real-v2/result.json`。首轮误记超时保存在 `audit-batch-real-v1/result.json`。生成源码、二进制及脚本哈希汇总在 `reports/audit-batch-final.json`。

最终 DLL SHA256：`ea46c4b5c2a7a472483f8f0d232d80a6dfbae849bb7bdc6a7e0ac1eede111216`。
模型 CLI SHA256：`2620ec4c6b012a93f925b0e59ec39c964c55428b3f6586d478c98b1092b55b2f`。
真实源码 CLI SHA256：`7c9b6fcbd8b5c5b0d531b5c20981397b7296523bafb99424079fe022d2ccc05e`。

冻结的 143 个模组源码、个人存档和受保护的历史成果哈希未变。没有启动游戏、增加 ZIP、复制模组或保留解压副本。原始测试审计校验后即删除，模型完整证明压缩保留，真实报告汇总完成后移除重复案例 JSON。删除本轮 14 个明确命名的 C++ 中间文件释放 42417838 字节，64 个受保护输出/生成源码哈希不变。
