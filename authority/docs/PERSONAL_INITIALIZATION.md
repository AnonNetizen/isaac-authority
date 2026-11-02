# 0.7.0 私有初始化验收

2026-10-10，使用同一 J460 种子局，DLL SHA256 为 `42bb4bb087ac04796e4938ef53951649055f7083ec715a52e8f6f0a451852eef`。最终证据为 `reports/j460-personal-options.json` 与对应 stopped 文件。

| 验收内容 | 结果 |
|---|---|
| 包内及松散资源，字体、精灵及只读道具查询 | 35 项前置检查通过；22 份资源，81 份动画元数据 |
| 原生私有 Lua 金币模型 | 7 项运行检查通过；未提交原生世界修改 |
| 两份个人 Options | Language/HUDOffset 独立，原生 Options 前后相同 |
| 未修改 MCM/EID 完整初始化 | 单独、联合及中文/英文两份联合上下文通过；源码哈希一致 |
| EID 自动语言查询 | 完整初始化后分别返回 zh_cn/en_us |
| 真实菜单、HUD、配置导航与绘制重放 | 未验证；没有执行这些真实回调 |
| 自动诊断撤销 | IAT 恢复、原生绑定钩子禁用，DLL 驻留但不再执行诊断 |
| 游戏正常退出与退出后存档审计 | 未验证，独立于源码和研究包交付 |

`personal_option_probe.actual_eid_language_selection_tested=false` 只描述不加载模组的 Options 子测试。真实 EID getter 验证记录在 `personal_mcm_eid_initializations`，不能混为一谈。日期默认使用金币模型时钟，不是当前日历；原生进度和网络玩法未实现。

历史报告 `j460-mod-runtime-packed-resources.json`、`j460-personal-options-before-callbacks.json`、`j460-personal-options-before-fonts.json`、`j460-personal-options-before-cn-font.json` 保留逐次失败及二进制哈希。失败分别涉及 Options、RunCallback、Font.Load 兼容参数与中文字体资源，不能用最终结果覆盖历史证据。

本地复现：运行 tools/validate.py，指定 build-personal-release/Release 与已安装的 Lua5.3.3r.dll；262 项检查不启动游戏。运行 tools/package.py 后，压缩包 CRC 和 bundle-manifest.json 全文件 SHA256 必须匹配。包不分发游戏资源、存档或原始日志。
