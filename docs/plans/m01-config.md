# M01 配置与凭据存储实施计划

依据：`PRD-拉新流水线重建-v1.md` 的 M01。按模块独立交付源码、测试和 demo。

范围约束：不修改 `C:\Users\45203\Documents\dakazhandian` 下的现有代码。

## 文件

- `lxds/__init__.py`：包标识。
- `lxds/config.py`：`ConfigStore`、Windows DPAPI 封装、持久化校验。
- `tests/test_config.py`：M01 验收标准及相关边界测试。
- `demo/config_demo.py`：在临时配置目录中完成保存和重新加载，打印非敏感结果。

## 步骤

1. 先写读写、密文落盘、不可写目录三项验收测试，以及嵌套设置值和重复保存测试。
2. 运行测试，确认因功能缺失而失败。
3. 实现 DPAPI 封装、原子保存、`verify_persisted()` 和 `ConfigStore` 的公开接口。
4. 运行测试并修复失败；再用 Python 3.12 执行测试。
5. 编写独立 demo，在临时目录下运行，并检查输出无凭据泄漏。

## 约定

- 默认路径为 `%LOCALAPPDATA%/lxds/config.json`；允许传入配置路径，以便测试和 demo 隔离。
- Windows 使用 `ctypes` 调用 `crypt32.dll`；非 Windows 明确警告并按 PRD 降级为明文。
- 配置 JSON 中仅对 DeepSeek Key 和账号 Cookie 字段逐项加密；公开接口返回解密后的值。
- 用临时文件替换目标文件，并在保存后重新读取、比较，失败时抛出异常。
