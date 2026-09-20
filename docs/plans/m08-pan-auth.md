# M08 网盘登录态实施计划

依据：`PRD-拉新流水线重建-v1.md` 的 M08。只在 `D:\hong` 实施，不修改现有 C# 代码。

1. 写四种 `check_cookie` 状态、token 读取和目录不存在时不得 create 的测试。
2. 运行测试确认因 M08 缺失而失败。
3. 实现 `lxds/pan_auth.py`，使用 Cookie Session 请求固定接口，保留目录检查缓存。
4. 运行 Python 3.12 模块与全量测试，再运行 `demo/pan_auth_demo.py`。
