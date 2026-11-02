# 资源与只读道具接入（0.5.0，2026-10-10）

本文保留 0.5.0 的历史证据。0.6.0 的 Sprite.SetFrame/GetFrame、完整 MCM 字体目录与私有初始化结果见 [动画与松散资源记录](RESOURCE_ANIMATION.md)。

**资源接入的有限诊断通过，完整旧模组兼容与可玩联机仍失败。** 新增 `--api-probe`，并将相同资源检查作为 `--runtime-probe` 的前置检查。诊断在游戏线程上、原始 Lua 调用返回后执行；必须先看到正常 MCM 的后段加载标记和 EID 的后段加载标记。没有第二台电脑，没有客机世界应用或战斗接管。

0.4.0 的首次 `Sprite_Load` 崩溃发生在仅加载完游戏脚本时。新找到的进程转储确认访问异常 `0xc0000005`，出错位置是主程序 RVA `0x4f5b6b`，读取地址为 `0x3713c`。无符号调用链包含游戏、Lua 和观察器；它不能给出完整根因。分析工具仅输出异常、寄存器和模块相对地址，不打包转储或内存内容。改变初始化时机后，已测加载路径通过；这支持时机假设，不能据此保证任意资源、版本或模组都会安全。

独立诊断的 8 项检查如下。

| 检查 | 已测范围 |
|---|---|
| 正常游戏状态中的绝对精灵路径 | MCM 菜单 anm2，关闭图片加载，播放 Idle |
| 正常游戏状态中的相对路径 | 同一菜单资源，加载图片 |
| 私有状态中的绝对路径 | 编号代理调用真实 Sprite.Load，加载图片 |
| 两个私有状态及相对路径 | 两份精灵 Scale 分别为 1.25/1.5 与 2/3，互不改变 |
| MCM 字体 | 绝对路径读取已安装字体，缓存 GetStringWidth 测得 67 |
| 两份只读道具配置 | GetCollectible、GetTrinket、GetCard、GetPillEffect；缓存 getter 与字段读取 |
| 写入与未开放进度查询 | 借用的 ItemConfig 对象不能写 Quality；IsAvailable 明确拒绝 |
| 对象生命周期 | 销毁两个上下文并释放注册表引用后，新上下文再次加载菜单精灵 |

最新组合实测见 `reports/j460-mod-runtime-api.json` 中的 `engine_api_preflight` 与 `checks`。它携带已测 DLL 哈希；`j460-mod-runtime-api-stopped.json` 记录 IAT 撤销。较早的独立实测 `j460-engine-api.json` 使用它自己记录的历史 DLL，不能将其哈希当成最终 DLL。两次初版诊断因启动提示/菜单阶段等待逻辑超时，未调用诊断原生 API；没有把超时算作资源检查通过。

新增 `expose_readonly_getter` 只选择一个函数，不把整个 Isaac 命名空间映射到私有状态。返回的原生对象仍在游戏 Lua 注册表中，代理只持有作用域与编号。借用对象的写入始终拒绝，方法要逐项声明。方法能力绑定到接收者来源和字段名，缓存函数不能给另一种接收者增加权限，也不会因两个字段引用相同 C 函数而一起获得权限。只读 getter 和方法要求是主程序可执行页中的 C 绑定；若正常游戏的 getter 被换成 Lua 函数，会在执行前拒绝。这里仍不是安全沙箱，也没有完成任意原生绑定被模组替换的兼容验证。

私有运行环境新增真实 Isaac.GetItemConfig 和上述四项元数据查询。当前 Sprite.Load 只开放相对路径 `gfx/ui/modconfig/menu.anm2`、显式加载图片，以及已测 anm2 哈希。Sprite.Play、GetAnimation、GetFilename 已在该资源上验证；其他精灵方法没有因为构造或加载成功而自动开放。运行环境的 Font.Load 仍只开放此前验证的 EID 字体绝对路径；MCM 字体的独立测量不能替代完整字体资源解析。

| 未修改模组 | 0.5.0 组合实测结果 |
|---|---|
| MCM 中文独立版 | 7 个入口/模块，Sprite.Load 成功，下一缺口是 `Sprite.SetFrame`；完整加载失败 |
| EID | 已取得真实 ItemConfig，下一缺口是未验证的 `gfx/eid_transform_icons.anm2` 资源；完整加载失败 |

两份 Lua 源码树在测试前后哈希相同，没有给它们增加网络接口或修改逻辑。7 项原生私有环境/金币模型检查继续通过：个人输入、配置、闭包重建、原生字体缓存与失败回滚仍工作。世界写入仍是金币模型，没有在真实游戏增加金币；没有分派真实 MCM/EID 的局内回调，不能声称菜单、HUD、不同语言、配置保存、内容模组或解锁已通过。

阶段备份均有 32 份校验文件。正常游戏启动/退出后的审计发现 stats-plus/save1.dat、Steam 侧 rep+persistentgamedata1.dat 与 remotecache.vdf 变化；没有判断具体内容或归因，也没有自动恢复。最后一轮用户用 Escape 停止了窗口控制，之后没有再操作游戏；整理报告时检测到游戏已退出，日志确认正常关闭。该轮 IAT 撤销和退出均已确认。退出后的只读审计见 `reports/engine-api-release-baseline-audit.json`。主程序哈希与测试前一致，版本文字相同仍不足以加载。

```powershell
# 游戏先正常关闭；研究包根目录。正常 MCM 和 EID 必须启用。
.\run.ps1 -Game '完整游戏目录' -Mode steam-launch -ApiProbe -OutputDirectory '.\runs\api-001'
# 前置资源诊断成功后，再测试私有回调、模型和未修改模组。
.\run.ps1 -Game '完整游戏目录' -Mode steam-launch -RuntimeProbe -OutputDirectory '.\runs\runtime-001'
```

每个目录只使用一次。调用前进度写入 `engine-api-trace.jsonl`，Lua 的加载标记最多等待 120 秒；超时撤销观察器并明确失败，不在工作线程调用游戏 Lua。正常关闭游戏移除驻留 DLL，下一次普通启动不会加载它。如果出现现有中文补丁的版本提示，选择“否”可跳过覆盖文件的安装；测试不依赖强制安装。

下一步是验证更完整的精灵动画和资源解析能力，再研究绘制命令拦截、菜单输入与本地设置。即使补齐这些 API，还必须解决个人配置影响世界逻辑的反例、原生世界事务、客机应用和双机验收，才能满足最初的通用方案要求。
