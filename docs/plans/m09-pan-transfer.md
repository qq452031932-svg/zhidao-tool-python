# M09 百度网盘转存实施计划

依据：`PRD-拉新流水线重建-v1.md` 的 M09。只在 `D:\hong` 实施，不修改现有 C# 代码。

1. 写 surl/pwd 提取、`share_uk` 优先、`to_fs_id` 优先、errno 12 三分支与空间不足测试。
2. 运行测试确认因 M09 缺失而失败。
3. 实现 `lxds/pan_transfer.py`，继承 M08 的 `PanClient` 并添加转存接口。
4. 用 Python 3.12 运行测试，执行 `demo/pan_transfer_demo.py` 的离线演示。

真实接口结构的最终校验仍以 C01 的六份响应为准；该电脑目前没有这些响应文件。
