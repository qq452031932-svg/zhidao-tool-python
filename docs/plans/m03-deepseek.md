# M03 DeepSeek 客户端实施计划

依据：`PRD-拉新流水线重建-v1.md` 的 M03。不得修改 `C:\Users\45203\Documents\dakazhandian` 下的现有代码。

## 文件

- `lxds/deepseek.py`：固定端点和模型、错误映射、`chat` 与 `test_key`。
- `tests/test_deepseek.py`：模拟 HTTP，覆盖每个错误分支和 JSON 模式。
- `demo/deepseek_demo.py`：不使用真实密钥的本地模拟调用，展示接口返回。

## 步骤

1. 写请求体、返回读取、全部错误映射与 `test_key` 的测试。
2. 运行测试，确认因模块缺失而失败。
3. 用 `requests` 实现固定端点与错误映射，不额外引入依赖。
4. 用 Python 3.12 运行模块测试及全部现有测试，再运行 demo。
