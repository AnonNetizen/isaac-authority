# Slice3 UI：真实源码初始化门槛研究

当前候选未通过真实 MCM/EID 初始化门槛。未修改 Lua 5.3.3 使用同一个命令行对象后端，可以初始化冻结的 MCM 中文版、EID 及其组合，并通过当前注册契约检查；研究 Lua 在 J460 枚举加载时拒绝执行。枚举根函数需要 12,440 条字节码，继承的单函数上限为 4,096 条。32 条路径、8 个未解析条件和 200 万探索工作单位的上限保留，没有通过跳过枚举或提高上限取得通过。

最终证据位于 `reports/slice3-ui-final/validation.json`，解压复现位于 `reports/slice3-ui-portable-reproduction/reproduction.json`。它们只有在相应命令完成后才会生成。安全拒绝复现与功能兼容分别记录；六个真实源码功能案例的预算拒绝仍算功能失败。

## 已实现的入口和冻结材料

- 独立 Windows x86 DLL：`ia_lua533_slice3_ui.dll`，ABI `ia-lua533-slice3-ui-1`。
- 独立运行器：`authority-slice3-ui-research.exe --suite`；`--suite-reference` 强制使用未修改 Lua。DLL 哈希必须与命令参数一致。
- 冻结清单：`research/slice3_ui_contract_suite_v7.json`，规则为 `personal-settings-authority-hud-v1`。旧 13、31、24、42、56 项清单及 Slice3 DLL、源码和原研究包均保留。
- `research/slice3_ui_inputs.json` 登记本机 143 个未经修改的模组 Lua 文件，以及 J460 枚举和兼容脚本。运行报告列出实际加载模块及其哈希。
- `research/slice3_ui_resources.json` 登记 22 项资源、64 个本地文件哈希、14 个字体的实际字宽/字偶距/行高数据及已有动画元数据。图片、字体和动画文件不放入研究包。

共享套件加载器明确拒绝 `slice3-ui`，游戏附加入口不能执行新清单。普通研究清单仍使用原模式和各自保留的 DLL；新版共享 C++ 运行器负责回归，因此覆盖此次共享代码改动。

## 当前契约证据的范围

执行依据是冻结的本机源码。公开 API 对照入口为 [MCM API 文档](https://github.com/Zamiell/isaac-mod-config-menu/blob/main/docs/api.md)；本机中文分支具有额外翻译接口，文档不能替代实际实现。定位和范围见 `research/slice3_ui_contracts.json`。

当前命令行案例核对 AddSetting 两参数和三参数调用、nil 子分类、原设置表身份、已有数字分类索引、无效分类错误，以及直接调用 CurrentSetting、OnChange、Display 时的 false、参数和原始字符串字节。普通 Lua 对照还实际加载 EID 的 `features/eid_mcm.lua`。这些检查没有驱动 MCM PostRender，不能证明真实菜单调度时机、翻译优先级在绘制中的行为或 EID 预览已经通过。

Display 在本机菜单绘制中收到光标命中、是否位于选项页和前一选项位置；Info 函数由 ConvertDisplayToTextTable 无参数调用。CurrentSetting 和 OnChange 出现在输入处理分支中。静态定位已经记录，实际输入驱动、调用身份和设置用途传播仍未验证。

## 对象后端及其限制

同一 C API 后端运行于参考和研究 Lua。受控 userdata 包括 Vector、Color、KColor、Font、FontRenderSettings、Sprite、BitSet128，跨上下文使用独立编号和字段表。已比较 Vector 别名、缓存方法、字段经闭包读取、KColor 独立通道、含 NUL/FF 的字符串以及冻结字体 AB 字宽；未知读取和未登记资源明确失败。

目前对象在上下文生命周期内固定保留，弱引用/GC 生命周期与游戏并未对照。字体查询使用冻结文件的度量模型，不证明原生字体测量完全一致。精灵查询采用声明的动画时间线模型，不证明 J460 原生 GetFrame 或播放状态完全一致。字体和精灵绘制函数明确报告 `capture_not_installed`，没有空绘制返回或真实绘制调用。

对象桥的完整有序处理链、对象副作用事务、可信真实 MCM 设置消费、场景查询、脚本化菜单导航、配置保存重载、菜单内 EID 预览和普通 HUD 捕获尚未实现。本轮因第一阶段预算失败未进入这些验收，不使用空实体场景替代 HUD。也未进入游戏画面、世界接管、通信、解锁或双机验收。

## 可重复命令

从工作区执行：

```powershell
pwsh -NoProfile -File authority/tools/build.ps1 -BuildDirectory build-slice3-ui -RuntimeOutputDirectory build-slice3-ui-release/Release -TraceResearch -Slice3UiResearch -SkipTests
python authority/tools/run_slice3_ui_research.py --binary authority/build-slice3-ui-release/Release --previous authority/build-slice3-release/Release --game "E:/SteamLibrary/steamapps/common/The Binding of Isaac Rebirth" --output authority/reports/slice3-ui-new-run
```

输出目录必须不存在。运行器输出 JSON 时的退出码 0 只表示报告完成；功能结果必须读取 `initialization_contract_gate_passed` 和逐例 `compatibility_passed`。外部脚本不能把安全拒绝或进程正常退出当成功兼容。

研究入口重复参考和候选清单各两次，要求完整报告相同；五份旧清单各重复两次，并与原始逐例证据比较。随后运行共享代码检查，只加载已安装的 Lua DLL，不启动或附加游戏。存档审计仅比较本轮验证前后的哈希，不自动恢复，也不把与历史备份不同的文件覆盖回去。

打包并解压到一个全新目录后执行：

```powershell
python authority/tools/package_slice3_ui.py --binary authority/build-slice3-ui-release/Release --previous authority/build-slice3-release/Release --evidence authority/reports/slice3-ui-final --game "E:/SteamLibrary/steamapps/common/The Binding of Isaac Rebirth" --output authority/artifacts/isaac-authority-slice3-ui-0.1.0.zip
python authority/tools/reproduce_slice3_ui.py --bundle "解压目录/isaac-authority-slice3-ui-0.1.0" --archive authority/artifacts/isaac-authority-slice3-ui-0.1.0.zip --output authority/reports/slice3-ui-portable-reproduction --game "E:/SteamLibrary/steamapps/common/The Binding of Isaac Rebirth"
```

复现入口逐文件校验，执行参考和候选新清单，以及旧五份清单，比较完整逐例证据；只归一化目录搬迁及冻结 Lua 文件的短文件名。`--game` 用于只读校验本地资源；省略时只能证明冻结元数据环境中的复现。研究包不嵌套原 Slice3 包，原包在原目录保留并按哈希审计；包内包含原 DLL、冻结清单及本轮完整回归报告。

## 历史失败与后续门槛

开发报告原样保留。v1 缺少 RoomDescriptor；v2 涉及错误数字分类测试和 KColor 字段别名；v3 暴露跟踪注册错误未受保护而 PANIC；v4 的 Length 预期错误地使用整数类型；v5 把应当拒绝的操作混入功能上下文；v6 拒绝案例缺少必要 HUDOffset。最终 v7 分开记录七个功能案例与两个安全拒绝案例。早期 v3 PANIC 输出没有保存当时 DLL 哈希，无法补证；不把它绑定到最终二进制。最终报告记录实际测试的 DLL 哈希。

私有候选修复了 lua_load 注册阶段的错误保护路径，预算超限现在返回结构化错误并恢复宿主栈。该修复只在新候选中应用，没有改写旧 Lua 运行时。

下一项工程工作应是设计并验证有界的大函数依赖分析，确认编译/CFG 构建成本纳入工作账本，并明确与现有单函数限制的关系，再建立新的候选和清单。不能直接放宽上限、免追踪枚举或改写旧模组来宣布本候选通过。初始化门槛通过以后，再继续用户计划中的对象处理链、绘制捕获和真实菜单输入验收。
