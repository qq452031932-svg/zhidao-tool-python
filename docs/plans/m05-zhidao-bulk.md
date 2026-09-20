# M05 百度知道批量发布实施计划

依据：`PRD-拉新流水线重建-v1.md` 的 M05。不得修改 `C:\Users\45203\Documents\dakazhandian` 下的现有代码。

1. 先写直连 Session、固定请求头、multipart 字段、权限/登录异常和 Cookie 保密测试。
2. 运行测试确认因 M05 缺失而失败。
3. 实现 `lxds/zhidao_bulk.py`，让 `userinfo` 与 `upload_file` 共用无代理会话。
4. 用 Python 3.12 运行测试，再运行 `demo/zhidao_bulk_demo.py` 的模拟演示。
