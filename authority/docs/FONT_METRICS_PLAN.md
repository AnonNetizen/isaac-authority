# 字体加载与实际文件度量

本轮先补 Font 的加载和查询，不进入绘制发布。新增独立 `--font-suite` / `ia-lua533-font-metrics-1`，保留上一候选。沿用 1000 万工作单位、5 秒子进程、1 GiB 配额；旧模组不改，配置私有，世界提交仍受主机/阶段守卫。

1. 冻结 14 份实际 BMFont v3 字体及其 PNG 依赖的路径、大小和 SHA，不复制游戏文件。以独立 Python 解析核对度量签名，保留 14 份历史 J460 宽度控制。运行时按需解析，缓存有上限的共享紧凑字形索引，避免生成重复的大字形 JSON。
2. 登记 Font userdata 的生命周期、资源版本和缺字设置版本；实现 Load、IsLoaded、GetStringWidth、GetLineHeight、GetBaselineHeight、SetMissingCharacter、Unload，并原样执行 J460 GetStringWidthUTF8 包装。资源校验成功后才提交对象状态；缓存方法继续通过受控入口。
3. 从冻结源码根到本机资源根建立通用路径映射，覆盖绝对、相对和旧式源文件/../ 路径；只接受唯一对应的冻结资源，不根据模组名添加特殊规则。
4. CLI 比较原版 Lua与研究 Lua，验证真实文件度量、原始文本字节、独立对象、精确读取失效、GC、失败恢复和预算。未验证的缺字默认、控制字符、无效 UTF-8、UTF-16 代理对行为和绘制明确拒绝。再尝试真实 MCM/EID，记录首个失败入口。

参考 [Font API](https://wofsauge.github.io/IsaacDocs/rep/Font.html) 与 [BMFont 文件格式](https://www.angelcode.com/products/bmfont/doc/file_format.html)。14 条控制只证明固定测试串的历史原生宽度，不覆盖全部文本、当前引擎或画面。命令行门槛通过不等于真实字体绘制、可信菜单或通用旧模组隔离通过。
