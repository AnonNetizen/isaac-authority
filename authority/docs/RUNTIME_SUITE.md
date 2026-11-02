# 0.8.0 分阶段研究与批量验收

第一阶段提供冻结清单、命令行批量入口和可撤销诊断。第二阶段的金币模型候选已测试，**没有通过通用混合回调隔离门槛**。第三阶段按计划不执行：不把未通过的处理用于真实游戏世界，不修改 MCM/EID 源码，也不通过隐藏 HUD、删除回调或逐模组适配来通过。

## 清单和复现

`research/runtime_suite.template.json` 记录 13 个案例、两人的初始配置、逐帧输入和输出预期。`research/runtime_suite.json` 冻结 bootstrap、J460 枚举及所有选中模组的 Lua 文件哈希。默认是两人、相同程序和资源、个人设置不同。不存在联网或解锁提交。

```powershell
# 本机源码目录；只运行金币模型，不操作游戏。连续两次必须得到相同结果。
python authority/tools/run_suite.py --binary-dir authority/build-suite-final/Release --lua-runtime '完整游戏目录/Lua5.3.3r.dll' --source authority --manifest authority/research/runtime_suite.json --output runs/local-suite.json

# 按本地源码重新冻结；输出必须使用新文件名。
python authority/tools/freeze_suite.py --template authority/research/runtime_suite.template.json --game '完整游戏目录' --research authority --output runs/my-suite.json

# 一次附加，一次共享资源前置检查；每案例重新建立两份私有上下文。
authority/build-suite-final/Release/isaac-authority.exe --game '完整游戏目录' --attach 12345 --runtime-source authority --runtime-suite runs/my-suite.json --out runs/j460-suite
```

解压包用 `bin` 替换二进制目录，`source` 替换 authority 源码目录。J460 枚举和游戏资源来自本地安装，包内不分发。未知程序拒绝注入；源码或清单改变后必须重新冻结并使用新的输出目录。

清单 schema 为 `isaac-runtime-suite-1`：cases 含唯一 id、strict/presentation 模式、mods(base/root/sha256)、stores[2]、可选 options[2]、frames。每帧含 frame、time_ms、inputs[2]、expect。expect 用 RFC6901 values 指针、精确 texts 或引用权威结果的 text_templates 核对实际界面。明确拒绝指定 error_contains。没有功能预期的案例被拒绝。原生初始化案例另含只读 inspect 和精确返回值。

最大 64 个案例、每例 128 帧、总计 256 帧；所有唯一源码总计不超过 32 MiB、案例源码副本总计不超过 64 MiB。路径越界、哈希改变和不支持入口均报错，不以空操作代替。首次拒绝、逐帧候选结果、源码是否变化、主 Lua 栈恢复和失败帧恢复均记录在结果中。

`passed` 表示案例的预期结果被复现，包含预期失败；`compatibility_passed` 和 `presentation_gate_passed` 单独记录能力结论。`generic_mod_compatibility_passed` 与 playable 始终为 false。离线运行必须将真实 MCM/EID 原生初始化标记为 `unverified_requires_game`，不能把跳过算作通过。

## 第二阶段候选

strict 保留原有逐次调用核对。presentation 只有权威环境执行世界写入；个人环境读取权威帧最终金币、帧号和时间，独立运行私有变量、Options、输入和 SaveData。AddCoins 与 randomseed 在模型副本上验证后丢弃，只记录抑制的操作。返回值会改变结果的 math.random 必须找到未消费、操作与参数相同的权威记录，否则明确拒绝。缓存函数仍走相同服务入口。

返回值修改在这里具体指会推进模型 RNG 状态并返回结果的 math.random；没有接入原生 Spawn 等返回实体的修改接口。这些结果不能推广到原生实体事务。

输出 oracle 在提交候选金币帧前执行。拒绝后从初始配置和已接受历史重建上下文，重放并比较完整输出；这会恢复闭包私有计数、配置、Options、绘制队列和 RNG。重复消息只返回已接受输出，不能重复运行回调或保存。oracle 是测试清单提供的已知语义，**不能替任意旧模组自动推导正确界面**，所以不作为可发布的通用修复。

| 功能案例 | 金币模型结果 |
|---|---|
| 原有 legacy_chaos 混合回调，strict 与 presentation | 个人文字和位置、权威随机/时间、单次世界修改符合预期 |
| 原有 config_drives_world | strict 拒绝个人参数分歧并恢复；presentation 接受个人配置变化，只提交权威数量 |
| 不同数量、额外无返回值写入、修改后查询、缓存函数 | 个人文字显示实际权威金币，配置和按键独立 |
| 新上下文使用保存配置 | 两份配置独立，权威世界从新局模型开始 |
| 失败恢复、重复和改写的重复消息 | 世界、RNG、配置、私有计数、Options、绘制队列恢复；没有再次保存 |
| 相同随机调用、时间和缓存函数 | 只返回对应权威记录，UI 数字与权威记录一致 |
| 个人分支新增随机调用 | 没有对应返回记录，明确拒绝并恢复；通用兼容要求失败 |
| 同参数随机调用对应不同用途 | 操作/参数匹配仍可返回错误含义的数值；UI oracle 拒绝；通用要求失败 |
| 先读取、写入、立即再次读取 | strict 显示 0→1；presentation 显示 1→1，语义失败且恢复 |
| 原始 MCM/EID 中文/英文初始化 | 离线明确跳过；J460 整批实测通过初始化与语言查询，不能视为菜单/HUD 通过 |

读写交错失败说明：只同步最终状态不能重建混合回调中不同时点的观察。随机调用歧义说明：相同操作和参数不能证明不同个人分支中的两次调用具有相同用途。强制按原次序匹配会恢复 strict 的个人分支限制。这些是该候选的失败结论，不是所有虚拟机、引擎隔离或依赖追踪方案的不可能性证明。

## 证据、撤销和历史

`reports/runtime-suite-offline.json` 记录两次一致的本地结果。`tests/test_runtime_suite.py` 除业务结果外，还验证不匹配返回值、闭包/配置恢复、下一案例不受上一失败影响，以及清单越界和修改拒绝。

2026-10-10 的最终 J460 批次记录于 `reports/j460-runtime-suite.json`，冻结清单 SHA256 为 `7713261c2c0b0369b5811facaba5f07244afa75cb0d85ef51208c693e2db9eea`，DLL SHA256 为 `45ed34613e73710804f2d8af1158c9e5273dc99fdd1663de297145ee3591efe4`。同一次附加完成 13 个案例：13 个预期结果复现、0 个意外失败、0 个跳过，主 Lua 栈恢复，模组源码未变。35 项资源前置检查、7 项已有原生金币模型检查及两套个人 Options/MCM/EID 初始化通过。

其中 4 例的 `compatibility_passed=false`：读写交错的文字语义错误、个人分支增加无匹配随机调用、额外同参数随机调用不能重复消费记录、同参数但不同用途的随机调用产生错误奖励文字。这些预期失败被成功复现，**并非兼容通过**；`presentation_gate_passed=false`。金币模型的写入、恢复与去重结果不能代替原生世界事务验证。

本批只执行一次共享资源前置检查。22 份档案共读取 1,541,034,809 字节，哈希时间合计 3,578 毫秒，后续命中缓存 154 次；字体和精灵对象状态仍按上下文隔离。这是一次诊断的资源校验数据，不是联机带宽、帧耗时或输入延迟。诊断完成后游戏重新响应；`reports/j460-runtime-suite-stopped.json` 确认 stopped、lua_iat_restored 和 native_binding_hooks_disabled 全为 true。游戏保持打开，没有为本轮要求再次进入菜单。

| 分阶段验收 | 当前结论 |
|---|---|
| 第一阶段：冻结清单、独立上下文、可重复本地执行、整批诊断与自动撤销 | 功能通过；研究包另做全文件哈希校验及解压复测 |
| 游戏正常退出及退出后的存档审计 | 未验证，单独记录；不阻塞第一阶段研究包 |
| 第二阶段：候选实现、对照与反例 | 已交付并复现；通用混合回调隔离门槛失败 |
| 第三阶段：真实个人菜单和 HUD 重放 | 按门槛不执行；初始化通过不代表此阶段通过 |
| 原生世界接管、个人解锁、双机通信和 30 分钟游戏 | 未实现或未验证；当前只有一台电脑 |

第一次 J460 批次因资源包在多个上下文反复哈希造成长时间主线程阻塞，Windows 报告 AppHang 后进程关闭；记录于 `reports/j460-runtime-suite-interrupted.json`，保留对应 DLL 哈希，不计作成功，也不将进程退出当成自动钩子恢复通过。修正版的 ResourceVerificationScope 在整个诊断中共享档案哈希与只读句柄，字体/精灵操作状态仍逐上下文独立；库存、松散覆盖和依赖检查继续执行，句柄只在诊断结束后释放。

随后一次启动画面中的诊断未等到进局后的 Lua 初始化，120 秒后撤销，记录于 `reports/j460-runtime-suite-readiness-timeout.json`；不计为功能通过。最终批次复用同一游戏进程，在用户进入种子局后完成。

首次本地 oracle 将 Lua 的 1.0 写成了 1，造成三例失败。旧清单、测试报告与二进制哈希保留；修正 oracle 后再冻结，不掩盖这个测试错误。0.7.0 中文字体等历史失败也保留。

批次结束必须核对 stopped.json 的 stopped、lua_iat_restored 和 native_binding_hooks_disabled。DLL 留到游戏退出，但没有有效钩子。游戏正常退出及退出后的存档审计独立记录，未验证时保持未验证。备份不自动恢复。

用户另行要求关闭中文补丁的每次版本提示。已备份该补丁 res/config.ini，并依据其自带说明将 `[isaac] check` 改为 -1；其他字节和主程序未改。记录于 `reports/cn-prompt-disabled.json`，该设置不属于联机隔离能力。
