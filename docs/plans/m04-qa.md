# M04 AI 问答生成实施计划

依据：`PRD-拉新流水线重建-v1.md` 的 M04。继续遵守不修改 `C:\Users\45203\Documents\dakazhandian` 下现有代码的限制。

1. 写三种风格的 prompt 组合、非法风格和原样返回测试。
2. 运行测试确认模块缺失。
3. 实现 `lxds/qa.py`，从 `assets/prompts` 读取原文并调用 M03。
4. 运行 Python 3.12 测试，执行 `demo/qa_demo.py` 的模拟演示。
