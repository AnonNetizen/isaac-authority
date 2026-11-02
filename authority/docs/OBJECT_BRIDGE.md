# J460 原生对象桥接（0.3.0，2026-10-10）

**独立 Lua 环境访问真实原生对象的单机测试通过。世界权威与通用旧模组兼容尚未通过。** 本次不是模拟对象：在真实 J460 进程中使用游戏已经加载的 Lua 5.3 DLL、类构造器和对象方法。游戏没有进入一局，测试后探针自行撤销，游戏正常关闭。

源码为 `native/lua_bridge.hpp`、`native/lua_bridge.cpp`。`--object-probe` 是单独的诊断选项，不安装绘制钩子、不连接 Steam 对端、不注册模组、不调用实体、战斗或存档 API。普通观察器路径仍会正常执行游戏模拟。

## 真实结果

记录见 `reports/j460-object-bridge.json` 与 `reports/j460-object-bridge-stopped.json`。

| 检查 | 结果 |
|---|---|
| 两个独立 Lua 状态加载原始 J460 `enums.lua` | 通过；源码只读，SHA256 `9737fc06…549dadb0` |
| BitSet128 原生构造、字段、位运算 | 通过 |
| Vector 构造、字段修改、加法、Length 与缓存方法 | 通过 |
| Color / KColor 原生字段 | 通过 |
| Font / Sprite 原生构造 | 通过；未验证精灵加载、动画或绘制 |
| 两套私有变量、类表配置和独立向量实例 | 通过；没有改动主游戏全局变量或类表 |
| Font.Load 与缓存 GetStringWidth | 通过；读取已安装 EID 字体，`native bridge` 宽度为 65 |
| 宿主 Lua 栈恢复、IAT 撤销 | 通过；DLL 驻留至游戏退出 |

第一环境发生 146 次桥接调用，保留 134 个引用；第二环境发生 112 次调用，保留 118 个引用。数字包含构造器、方法和类表引用，不是网络实体数或性能指标。没有测量战斗帧耗时、操作延迟或网络带宽。

第一次运行在枚举脚本向 `ItemConfig` 添加常量时失败，记录保留为 `j460-object-bridge-first-failed.json`。随后实现独立的类表副本，并加入 `ItemConfig` / `RoomDescriptor` 命名空间，原始枚举无需修改即可加载。这只解决了枚举初始化，不表示 EID 或配置菜单完整运行；0.2.0 的四份真实模组加载失败记录仍有效，因为那些探测使用独立的 Python 模型，尚未连接这层桥接。

## 数据与所有权

原生 userdata 保留在游戏 Lua 状态的 registry 中。另一个状态只持有新建的代理 userdata，其内容是作用域编号与对象编号；不复制原生内存、原生指针或资源缓存。标量、原始字符串字节和带作用域的编号通过结构化数据往返。方法调用回到宿主状态，使用原始对象、原始方法和受保护调用，随后恢复栈。

构造器生成的新对象属于当前桥接作用域。借用的类常量对象只允许读字段，拒绝写属性或以其为接收者调用方法。类命名空间是本地 Lua 表：普通赋值和 `rawset` 留在各自表中，不写宿主类表。缓存函数仍走同一个桥接入口，不改动真实方法字段；这避免了早期替换原生 C 方法字段时的分派问题。

作用域关闭时先销毁独立状态，再释放宿主 registry 引用。编号只在当前桥接作用域有效，不是房间实体的永久网络 ID。当前实现同步运行在游戏 Lua 线程，拒绝 coroutine 的桥接调用和嵌套执行。未支持的边界会保留错误，即使脚本用 `pcall` 捕获也不会将该次诊断标为通过。

[Lua 5.3 C API 手册](https://www.lua.org/manual/5.3/manual.html#4) 是 registry、userdata、受保护调用和多返回值处理的依据。这里只用公开导出和运行时对象引用，没有安装猜测地址上的引擎更新钩子。

## 验证与限制

24 项新增 x86 检查使用本机同一 Lua DLL 与原生 C 测试 userdata，覆盖对象身份、字段、缓存方法、多返回值、64 位整数、double、NUL / 非 UTF8 字节、原生错误、借用对象拒写、独立类表、两个状态的私有变量和栈恢复。它们不是游戏战斗测试。Lua DLL 的已验证哈希为 `fb84afbc…05a13e`；不同哈希拒绝这项原生诊断。该 DLL 不随研究包分发。

仍未完成的接口包括原生 metatable 的完整虚拟化、类表字段枚举、任意 Lua 表/闭包传入原生函数、跨环境回调、未知对象的所有权、资源完整绘制状态，以及 mod:GetData / SaveData 等游戏语义。普通表参数、未知值和 coroutine 会被拒绝；并没有通过关闭模组功能获得兼容结论。

这层桥接本身**没有事务回滚**：新建对象的字段修改立即发生在对应对象上。它没有连到 0.2.0 的世界候选帧模型，也没有访问或隔离实体世界。不能把新对象的独立性推断为任意实体、碰撞、随机数或渲染中的世界写入已被隔离。诊断运行的是固定测试和原始枚举，尚未运行完整旧模组；环境限制也不是安全沙箱。

研究前新增的 32 份备份全部校验通过。启动并退出游戏后，仅既有 `stats-plus/save1.dat` 与备份不同，见 `object-bridge-baseline-audit.json`；按哈希无法确定具体内容或写入归因。当前文件保留，没有自动恢复用户数据。诊断代码没有调用存档 API，正常游戏与已有模组仍可能写配置。

下一步应把这层桥接与完整模组运行环境、输入/配置命名空间、世界 API 调用记录连接起来，再验证实体访问和世界写入能否统一隔离。还需要核对原生 Game.Update 与状态应用，才能开始可玩主机权威实现。

## 复现

在解压包根目录使用自己的已安装游戏，先备份存档。对象诊断不要求进入一局，完成后检查 `object-bridge.json` 和 `stopped.json`。

```powershell
.\run.ps1 -Game '完整游戏目录' -Mode steam-launch -ObjectProbe -OutputDirectory '.\runs\objects-001'
# 游戏已打开时可使用 -Mode attach -ProcessId 实际编号；每次用新的输出目录。

.\bin\authority-bridge-tests.exe '完整游戏目录\Lua5.3.3r.dll'
py -3 .\source\tools\validate.py --binary-dir .\bin --lua-runtime '完整游戏目录\Lua5.3.3r.dll' --output .\runs\validation.json
```

源码工作区的本次二进制在 `build-bridge/Release`；`tools/run.ps1` 可以用 `-BinaryDirectory` 显式选择。原型仍为 `playable=false`，不能用于替代官方在线合作。
