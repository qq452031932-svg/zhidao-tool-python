# 拉新流水线 Python 重建

本目录按 [PRD](PRD-拉新流水线重建-v1.md) 实现 M01–M18。需要 Python 3.12 及以上。源码、离线测试和独立演示都在本目录；未改动 `C:\Users\45203\Documents\dakazhandian`。

C# C02–C04 的改动位于 [独立副本](csharp_isolated/CHANGES.md)，原目录保持只读。

## 安装与运行

```powershell
py -3.12 -m pip install -e .
lxds --help
py -3.12 -m pytest tests -q
py -3.12 -m demo.pipeline_demo
```

未安装命令入口时可用 `py -3.12 -m lxds --help`。M01 的 `ConfigStore` 保存在当前用户 `%LOCALAPPDATA%\lxds\config.json`，DeepSeek Key、知道 Cookie 和网盘 Cookie 由 Windows DPAPI 加密。正式执行前需由调用程序或脚本通过 `ConfigStore` 写入凭据。

七个命令分别为 `mine`、`collect`、`transfer`、`template`、`publish`、`answer` 和 `run`。示例：

```powershell
lxds mine --category 小说 --count 200 --out keywords.txt
lxds collect --mode precise --keywords keywords.txt --out collected.xlsx
lxds transfer --in collected.xlsx --target /我的资源 --share --out transferred.xlsx
lxds template --in transferred.xlsx --out qa.xlsx
lxds publish --in qa.xlsx --account 知道甲
lxds run --config pipeline.yaml
```

`pipeline.yaml` 的最小配置：

```yaml
category: 小说
count: 200
workdir: D:/hong/output
transfer:
  mode: local
  target: /我的资源
publish:
  account: 知道甲
```

转存交给 C# 时把 `transfer.mode` 设为 `external`，再填写 `external_inbox`、`external_outbox`。可选 `result_name` 指定固定结果名，或用 `result_glob` 匹配带时间戳的文件；默认匹配 `*转存分享结果*.xlsx`。只读取本次提交后新生成的结果。每一步写入工作目录，失败时可以从已有的 `keywords.txt`、`collected.xlsx`、`transferred.xlsx` 或 `qa.xlsx` 通过相应子命令继续。

离线测试以样本和假请求验证逻辑。百度知道、百度网盘、DeepSeek 的当前线上行为及 C# 实际收发目录尚需在具备账号的环境联调；M09 的真实响应结构由用户此前在另一台电脑验证，未把那次验证冒充为本机测试。
