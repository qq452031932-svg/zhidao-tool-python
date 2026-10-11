# 2026-09-29：逐条采集、剪贴板实机错误与转存提示

## 用户反馈与核实

- 用户要求采集命中一条即写入表格，不等待目标数量。
- 复制提示 `COMException (0x800401D0)`，但粘贴得到正确文本。此前增加 OLE 失败读回和重试没有解决这台电脑的实际问题。
- 开始转存后停留在处理结果，完成日志已有 5 条成功，但没有看到完成弹窗。
- 用户已实际操作账号转存；本轮开发验证不发起任何远端转存，不读取或输出 Cookie。

## 改动与证据

1. 主采集路径原本逐条 `on_item → on_progress → checkpoint`，助手每条 JSON 消息立即 flush；同页同秒的 5 条不能证明等待目标才写入。补量搜索确实先积累网页/详情结果再返回，现改为生成器逐条产出。保留原 `search` 列表接口，达到目标或停止时关闭迭代器。
2. WPF 收到每条 item 即添加结果、更新数量并写“已采到第 N 条：名称”。无需等待 progress、下一页或 done。日志记录结果名称，不记录 Cookie。
3. 原剪贴板公有实现已在这台电脑真实复现：`System.Windows.Clipboard.Flush()` 报 `0x800401D0`，3 次重试仍失败。现通过有效的消息窗口句柄直接提交 `CF_UNICODETEXT`，采用 `GMEM_MOVEABLE` 并在提交成功后将内存所有权交给 Windows，不再使用 OLE Set/Flush/Get；仅在尚未修改剪贴板的打开竞争时有限重试。准备/打开/清空/提交/关闭/释放的失败分支均有测试。依据 [Microsoft SetClipboardData 文档](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setclipboarddata)。
4. 转存开始时虽切到运行日志，`RecordCreatedBatch` 和结果 `BatchJobId` 变更又改为处理结果。现保留开始时的日志页；当前任务结果初始化不抢页，用户手动切页不受后续刷新影响，打开其他历史任务仍进入处理结果。开始时自动保存行编辑触发的导入刷新也不再切回待处理页。独立审查发现只按批次 ID 抑制导航会影响手动打开本轮批次，已用 `ResultsRequested` 明确区分用户查看结果与后台初始化，并补先失败后通过的回归。
5. `DialogService.ShowMessageAsync` 原来没有经主 UI dispatcher，也没有指定主窗口 owner；完成提示异常被空 catch 忽略。现经 UI 线程并指定当前主窗口，保留一次性通知语义；显示异常留明确日志，不再静默。关于 owner 行为参见 [Microsoft MessageBox 文档](https://learn.microsoft.com/zh-cn/dotnet/api/system.windows.messagebox.show?view=windowsdesktop-8.0)。不能仅凭旧截图断言唯一原因是被遮挡。

## 验证

- 新增失败用例先确认：成功转存后页签错误、单 item 的数量未更新、弹窗未经过 dispatcher/未传 owner、弹窗失败无警告。最终扩展 C# 回归 **456 项通过，0 失败**，报告在内层 `tests/BaiduBatchTransfer.App.Tests/TestResults/feedback-final.trx`；隔离构建输出 `.artifacts/collect-observability-20260929`。
- 剪贴板本机集成测试：旧实现红灯，新实现公有服务在 Windows session 1 成功写入用户给出的链接，临时 owner 销毁后原生读回 UTF-16 内容及结尾 NUL 完全一致，约 42 ms。测试仅读本次成功写入且序号未改变的数据，不读此前剪贴板。报告为内层 `.artifacts/clipboard-native-20260929/results/clipboard-old-red.trx`、`clipboard-unit-green.trx`、`clipboard-native-green.trx`。19 项剪贴板单元测试通过；真实测试默认不运行，必须显式设置 `BAIDU_CLIPBOARD_NATIVE_TEST=1`。
- Python 外层完整 **253 passed，另 50 subtests passed**；助手完整 **64 tests OK**。
- Event 阻塞第二次获取，验证主路径、网页补量及站内详情补量的第一条 item/progress/checkpoint 均在第二次获取完成前可用。
- 真实有缓冲 stdout 子进程（没有 `-u`，`-E` 忽略环境强制无缓冲设置）验证第一条 IPC 消息在 done 前到达。
- STA WPF Dispatcher 用例目标为 5，仅发送第一条 item，证明表格、数量、逐条日志已更新且仍在采集中。
- 历史全量 C# 验收的 26 项失败未在本轮关闭，本轮不代表完整验收通过。

## 更新状态

- 当前 5 条公开结果字段备份至 `.recovery/20260929-collect-streaming-clipboard/results-before-streaming-fix.json`，不含 Cookie。
- 用户本轮回复“已关闭”后已确认旧进程退出。原 Debug 入口重新构建通过（0 警告、0 错误），输出 `collect.py`、`websearch.py`、`zhidao_parse.py`、`http_decode.py` 与源码 SHA256 一致。
- 已从原入口重新打开主程序：PID **45364**，标题“知道综合工具”，MainWindowHandle **3214258**，Responding **True**。尚未验证更新后用户真实采集/转存时弹窗的显示效果，不发起额外远端转存代验。
