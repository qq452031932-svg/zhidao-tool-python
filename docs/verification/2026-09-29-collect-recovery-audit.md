# 2026-09-29 采集功能迁移核对与日志修复

## 结论与范围

用户实机先发现“验证 Cookie”按钮缺失，随后发现运行日志空白、无法判断采集进度。此前仅通过编译和局部测试就让用户测试，未充分核对旧目录的未提交改动及真实 WPF 消息更新链路。

本次对照 `D:\hong-1\dakazhandian\.worktrees\dev-playwright` 和 `.recovery/20260928-environment-rebuild/hong-1-dev-playwright-final.patch`，逐项审查补丁涉及的 15 个文件。确认的功能迁移遗漏是验证按钮和助手 stderr 诊断接收；另发现现有代码中会导致界面更新中断、重复订阅和失败后无法恢复的缺陷。不能把“15 个未迁入文件”解释成“15 个丢失的功能”，也不能据此声称整套产品已经完整验收。

旧目录、恢复补丁及 C02–C04 已有功能均未被覆盖。

## 旧补丁逐文件处理

以下路径均相对于 C# 仓库 `dakazhandian`。

| 文件 | 核对与处理 |
| --- | --- |
| `src/BaiduBatchTransfer.App/Features/Collect/CollectHelperClient.cs` | `HasExited` 已在当前提交中；stderr 接收确实漏迁，本次恢复并补 Cookie 脱敏。旧补丁设置的环境变量会被 `-E` 忽略，改用明确的 `-X utf8`。 |
| `src/BaiduBatchTransfer.App/Features/Collect/CollectView.xaml` | 恢复 Cookie 验证按钮及对应布局；本次补日志换行、可读高度与自动滚动。 |
| `src/BaiduBatchTransfer.App/Styles/SuperPanTheme.xaml` | 旧补丁修改全局 Padding，会撤销已有内边距修正；保留当前样式。 |
| `src/BaiduBatchTransfer.App/packages.lock.json` | 运行时目标、依赖版本等还原生成差异；未覆盖。 |
| `src/BaiduBatchTransfer.Application/Scheduling/OperationExecutor.cs` | 旧改动会回退已提交的 C02–C04 相关行为；保留当前代码。 |
| `src/BaiduBatchTransfer.Application/packages.lock.json` | 构建还原差异；未覆盖。 |
| `src/BaiduBatchTransfer.BaiduAdapter/Http/BaiduWebApiClient.cs` | 旧改动会回退已提交的 C02–C04 相关行为；保留当前代码。 |
| `src/BaiduBatchTransfer.BaiduAdapter/packages.lock.json` | 构建还原差异；未覆盖。 |
| `src/BaiduBatchTransfer.Core/Domain/BaiduErrorKind.cs` | 旧改动会删除现有错误分类；保留当前代码。 |
| `src/BaiduBatchTransfer.Core/packages.lock.json` | 构建还原差异；未覆盖。 |
| `src/BaiduBatchTransfer.Infrastructure/Excel/ExcelColumnSuggestionEngine.cs` | 旧改动会回退现有 Excel 列识别行为；保留当前代码。 |
| `src/BaiduBatchTransfer.Infrastructure/Excel/OpenXmlResultWriter.cs` | 旧改动会回退现有导出行为；保留当前代码。本次未修复全量测试记录中的 Excel 问题。 |
| `src/BaiduBatchTransfer.Infrastructure/packages.lock.json` | 构建还原差异；未覆盖。 |
| `src/SuperPan.Licensing.Client/packages.lock.json` | 构建还原差异；未覆盖。 |
| `tools/collect_helper/main.py` | 当前已有 stdout/stderr UTF-8 reconfigure；未恢复多余的旧 Python 兼容分支。本次另补启动拒绝时的命令和运行状态字段。 |

## 本次修复行为

- 在 UI 线程创建 ViewModel 时保存 Dispatcher，后台助手消息经该 Dispatcher 更新日志、资源集合及进度。旧代码在后台回调中临时读取 SynchronizationContext，得不到 UI 上下文。
- 恢复 stderr 日志接收；对本助手进程收到过的全部 Cookie 及关键值脱敏，覆盖更换 Cookie 后迟到的上一轮诊断。
- 开始时立即显示启动日志；搜索发出前报告关键词序号、时间范围和页码，详情请求报告问题序号，网络请求显示等待响应，间隔/冷却显示剩余秒数，完成关键词后报告新增与累计数量。
- 日志带时间、自动换行、滚到最新一条，保留最近 500 条；停止和完成也记录到日志。
- 用户后续报告旧窗口点击停止无反应，进一步离线复现：停止恰好发生在进入风控提示前时，`_on_ask` 清空答复事件导致停止信号丢失。助手改为独立保存停止状态，避免清空答复事件后继续等待；已添加确定性回归用例。该竞态已确认存在，未断言它就是用户当次旧进程的唯一原因。
- 正常完成后复用助手及事件订阅，避免第二次采集重复添加资源或日志；助手进程退出或 stdout 关闭后，下次连接重新建立进程。
- 启动参数被拒绝时恢复按钮状态；已有任务仍运行时的重复启动拒绝不会把原任务误标为结束。发送前检查 1 MiB 命令帧上限，超长参数给出可见错误。
- 保留此前 Cookie 验证修复：依据只读账号信息接口响应判断，去除“启动、等 500ms、停止即宣称验证通过”的旧逻辑。

## 验证记录

修改前的回归用例分别重现：stderr 丢失、第二轮资源重复、WPF 集合在后台线程更新、首次网络等待前无状态，以及超长帧和上一轮 Cookie 脱敏边界。测试中的同步阻塞假管道也改为异步 Channel，避免测试线程池饥饿；这属于测试设施修正。

隔离构建目录为 `.artifacts/collect-observability-20260929`，测试期间未替换用户正在运行的标准 Debug 程序。

```powershell
dotnet test tests\BaiduBatchTransfer.App.Tests\BaiduBatchTransfer.App.Tests.csproj --artifacts-path 'D:\hong-2\dakazhandian\.artifacts\collect-observability-20260929' --no-restore --filter 'FullyQualifiedName~Collect|FullyQualifiedName~ZhidaoCookieValidatorTests' --nologo --verbosity minimal
```

结果：**76 通过，0 失败，0 跳过**。覆盖 Cookie 验证、布局宽度 640/714/1000px、真实 STA Dispatcher 更新、助手真实子进程通信、进程退出和输出通道关闭后的重连，以及重复开始、停止、启动拒绝等路径。WPF 用例还验证停止命令确实发送、后台 done 更新“已停止”、按钮恢复、已有资源保留。

```powershell
& '.\.artifacts\helper-bundle-cdp\python.exe' -B -E -s -X utf8 -m unittest discover -s tools\collect_helper\tests -v
```

最新结果：**28 项通过**。包括真实 CollectWorker 配合离线模拟网络响应的事件流、首次请求前状态、冷却提示及可停止性，以及停止发生在风控提示前不丢失。进程测试有既有的未关闭管道 ResourceWarning；故意模拟 worker 异常的用例会输出 traceback，但该用例通过。

`git diff --check` 通过，仅有工作区 LF/CRLF 提示。代码另经独立只读复核，发现的命令帧大小和迟到 stderr 脱敏问题均已补回归并修复。

## 验证边界与待办

- 本次使用虚构 Cookie、模拟网络或本地子进程，未调用用户截图中的 Cookie，未完成真实账号采集端到端验收。
- C# 全量测试未重跑，2026-09-28 的 **26 项失败**仍以原记录为准；本次采集定向测试通过不代表全项目验收通过。
- 当前修复尚未提交。用户已确认关闭旧窗口；标准 Debug 已构建成功，0 警告、0 错误，并重新打开原入口 `D:\hong-2\dakazhandian\src\BaiduBatchTransfer.App\bin\Debug\net8.0-windows\知道综合工具.exe`。
- 当前停止机制仍会等待正在执行的同步网络请求返回或超时；网络请求默认 timeout 为 30 秒，不能把它描述为任意时刻都瞬间中断网络。
