# 暂停快照与动画推进

继续推进可用联机扩展，本步接通完整 MCM/EID 渲染回调的前两个缺口。保留字体候选及冻结旧模组源码。

1. `Game.IsPaused` 读取权威场景中显式提供的布尔值，按字段版本追踪。缺失字段拒绝，不默认返回 false；帧号变化不能使暂停读取失效，暂停 A→B→A 必须失效。
2. 依据实际 ANM2 的 FrameNum 与 Loop，以及公开 Play/Update 契约推进私有精灵。仅在显式 Play 建立了已知播放状态后支持推进。每个精灵固定保存一份时钟，Update 不逐次追加永久操作。SetFrame 后的播放标志、非循环动画终止边界等没有原生证明的行为继续拒绝。
3. 验证循环跨界、重复 Play、强制重播、字段失效、资源重载、GC、连续数千次更新和事务恢复。保持 1000 万工作单位、5 秒、1 GiB，先命令行短测，不启动游戏。
4. 运行原始完整 MC_POST_RENDER，记录下一处真实缺口。模型动画推进不等于原生动画或画面验收，不将后续失败改成兼容通过。

公开调用说明：[Sprite](https://wofsauge.github.io/IsaacDocs/rep/Sprite.html)、[Game](https://wofsauge.github.io/IsaacDocs/rep/Game.html)。原生终止边界和像素重放仍需后续 J460 集中核对。
