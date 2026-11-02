# Audit volume：取消人工资源配额的单次诊断

本轮只运行 Windows x86 命令行初始化，不启动游戏、不修改模组或个人存档。

独立 ABI：`ia-lua533-audit-volume-sizing-1`。诊断 DLL 取消 1000 万工作量、5 秒时限、16 MiB 审计配额、512 MiB DLL 堆和 1 GiB 进程配额；扩大遍历与计数保护到其表示范围。
仍保留来源/资源/操作校验、32 位地址空间、定宽 ID、格式限制及可驱逐缓存。系统剩余内存低于 512 MiB 或磁盘低于 1 GiB 时停止，以免耗尽整机资源。

正式运行时及正式 1000 万/5 秒验收保持原样。本结果不是正式门槛通过，也没有验证菜单导航、绘制捕获、世界奖励投影或真实联机。

| 案例 | 初始化 | 冻结契约 | 运行秒数 | 完整初始化工作量 | 总工作量 | 私有内存峰值 MiB | 审计 MiB |
|---|---|---|---:|---:|---:|---:|---:|
| mcm-zh | 通过 | 通过 | 20.363 | 35054616 | 36609711 | 110.57 | 46.01 |
| eid-zh | 失败 | 失败 | 578.909 | 未完成 | 1136146648 | 3187.71 | 2495.30 |
| combined-zh | 失败 | 失败 | 754.729 | 未完成 | 1207308891 | 3239.52 | 2521.03 |

运行秒数包含加载、契约检查、收尾与原生进程退出；不包含离线逐记录审计核对。初始化工作量在所有模组加载并检查成功后、契约检查前读取。失败项的总工作量只是达到失败点的工作量，不是完整加载需求。

## mcm-zh

- 首个失败：`None`
- 机器保护：`None`；超时：`False`。
- 执行期间历史审计回读：`0`。
- 审计 CRC/解码尾部错误：`None`；与原生持久化前沿一致：`True`。
- 审计 SHA256：`8d768c83015aaa6c9d33ccd277293823a3183270ca7945cd97c831ad6123c0ea`。大日志已校验并移除：`True`。
- DLL 堆：`{"all_private_dll_cpp_allocations_capped":true,"host_heap_included":false,"limit":4294967295,"live_bytes":76605093,"lua_c_heap_included":false,"peak_bytes":85007623}`。

## eid-zh

- 首个失败：`authority-native-mod-context:165: Compact managed heap remains faulted`
- 机器保护：`None`；超时：`False`。
- 执行期间历史审计回读：`0`。
- 审计 CRC/解码尾部错误：`None`；与原生持久化前沿一致：`True`。
- 审计 SHA256：`358398469e85ba5518547a5402e1851e1a2d668aef722f384896f0bc4479d471`。大日志已校验并移除：`True`。
- DLL 堆：`{"all_private_dll_cpp_allocations_capped":true,"host_heap_included":false,"limit":4294967295,"live_bytes":3199081268,"lua_c_heap_included":false,"peak_bytes":3199824984}`。

## combined-zh

- 首个失败：`authority-native-mod-context:165: Compact managed heap remains faulted`
- 机器保护：`None`；超时：`False`。
- 执行期间历史审计回读：`0`。
- 审计 CRC/解码尾部错误：`None`；与原生持久化前沿一致：`True`。
- 审计 SHA256：`a970b01412dc78dcb7016096a3501a5c3d0d9b35db9bef20958c328ae8e9b416`。大日志已校验并移除：`True`。
- DLL 堆：`{"all_private_dll_cpp_allocations_capped":true,"host_heap_included":false,"limit":4294967295,"live_bytes":3246032666,"lua_c_heap_included":false,"peak_bytes":3247067336}`。

## 常驻记录扩容线索

失败两项的 channel 11 均提交 26,906,977 条使用记录，工作量记账均已尝试第 26,906,978 条。`ResidentUses::push_back` 先扩容再写审计，因此失败发生在未提交该条记录之前。
本机 MSVC `<vector>` 的 `_Calculate_growth` 取旧容量加旧容量的一半。24 字节元素从容量 26,906,977 扩到 40,360,465，需要新申请 968,651,160 字节（923.78 MiB）；旧的 645,767,448 字节缓冲在搬移完成前仍占用地址空间。
两次相同记录边界、两单位一次的使用记账、故障位置和当前分配器代码共同强烈支持向量扩容失败。没有新增分配级探针，不能把推算的申请大小写成直接观测值，也不能进一步断言具体地址碎片分布。
分块存储可以减少连续扩容峰值，但仅更换容器仍会保留数千万条历史使用记录，不能解决常驻证据随执行增长的问题。

## 保护与复现

- 正式代码、二进制与冻结输入不变：`True`。
- 存档审计不变：`True`。没有自动恢复或覆盖存档。
- 私有运行时保留 `personal-settings-authority-hud-v1`；本轮初始化不产生世界修改，也不能证明奖励投影功能已通过。
- 入口：`python -B authority/tools/measure_audit_volume_completion.py run --output <新的空结果目录>`。
- 当前派生源码与 CMake 在 `authority/build-audit-volume-measurement/source`；构建 `build` 中的 Release 目标。`derivation.json` 记录来源与派生文件哈希，`invocation.json` 记录实际二进制哈希。
- 不打包或复制模组。日志核对逐记录执行，恒定缓冲；其耗时单独于上述原生运行秒数。

编译缓存清理：Remove-Item 操作被自动审批拒绝，未返回具体原因；没有重试绕过拦截。11 个测量用 .obj 共 30,901,469 字节暂留。三个大审计文件均已校验并删除，正式 ABI 对象未删除。
