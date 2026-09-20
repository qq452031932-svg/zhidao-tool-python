# M13 账号池与风控编排实施计划

依据：`PRD-拉新流水线重建-v1.md` 的 M13。只在 `D:\hong` 实施，不修改现有 C# 代码。

1. 写双账号偶发与三连击、单账号三轮静默冷却、探针判定、停止可中断和固定出口回退测试。
2. 运行测试确认因模块缺失而失败。
3. 实现 `lxds/pool.py` 的 AccountSlot、SlotPool、PooledFetcher 与 PinnedExitFetcher。
4. 用 Python 3.12 运行测试及独立 demo。

PRD 未列出的原始常量已从打包产物只读核对：风控页长度阈值 60000，风险词为“百度安全验证/安全验证/wappass/请输入验证码”，Clash 候选端口为 7890/7891/7897。
