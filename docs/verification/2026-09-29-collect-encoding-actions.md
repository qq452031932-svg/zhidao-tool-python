# 采集中文解码与结果操作

## 问题与根因

用户实机确认模糊采集得到 3 条，但资源名称乱码且没有结果操作入口。检查结果断点发现中文在 Python 端保存前已经损坏。两份 `SlotPool.fetch` 直接使用 `response.text`；Requests 将未声明 charset 的 `text/html` 默认按 ISO-8859-1 解码，原始 UTF-8 中文因此乱码。使用真实 `requests.Response` 原始字节离线复现。

## 修复

- 外层和发布助手新增相同的 `lxds/http_decode.py`，在 HTTP 响应边界处理 BOM、明确声明的 HTTP/HTML 编码，随后严格尝试 UTF-8、GB18030；保留 GBK/GB18030 和显式 Latin1，不对任意标题做猜测式替换。
- 采集结果新增复制链接（含已有提取码）、导出 Excel、送入批量转存。支持 Ctrl/Shift 多选，未选中时处理全部；显示实际操作范围和结果反馈，操作失败不清空采集结果。
- Excel 使用文本单元格，保存资源名称、资源链接、提取码、来源。实际经现有工作簿检查、列建议和导入读取器验证中文名称、链接、码及来源完整保留。
- 送入转存复用原有 Excel 列映射、本地导入和导航流程，不启动远端转存。有旧导入需确认替换；忙碌或已有批次时拒绝替换，并在异步间隙重新检查状态。生成的来源工作簿保留，支持导入中断后恢复。
- 独立复核发现取消列映射会提前清除旧会话：仅此送入入口启用 `preserveCurrentOnFailure`，在新会话持久化前取消/失败会恢复旧会话和恢复来源；新会话持久化后才释放旧来源。普通手动导入入口保持原行为。
- 结果工具栏与表格检查了 640/714/1000px 宽度。保留独立日志区，设置名称、链接、来源列的最小宽度；离线 WPF 渲染已目视检查，图位于内层 `.artifacts/collect-result-layout.png`。

## 验证

- Python 外层完整测试：236 passed，15 subtests passed。
- 发布助手完整测试：46 tests OK；既有模拟异常栈与测试管道 ResourceWarning 不影响退出码 0。
- C# 隔离构建目录中的采集/Cookie/导入相关测试：138 passed，0 failed，0 skipped。筛选 Collect、ZhidaoCookieValidatorTests、ImportViewModelTests、LocalExcelImportIntegrationTests。
- 中间运行曾暴露结果表格高度不足，已调整留白和日志高度。另一次扩大范围运行出现已有 HelperExitIsSurfacedAsABrokenChannel 单项失败，单独重跑通过，最终相同扩展范围 138 项通过；未将该次失败隐去。
- 全部变更尚未提交。未重跑 C# 全量验收；旧交接中的其他 26 项失败不因本轮定向回归而关闭。未使用用户真实 Cookie 执行账号网络采集或远端转存。

## 当前数据与发布

当前 3 条结果已单独保存到 `.recovery/20260929-collect-results/results-before-encoding-fix.json`，链接和提取码另存为 `links-before-encoding-fix.txt`；不包含 Cookie。旧乱码名称原样保留，更新后需重新采集才能得到按正确编码读取的名称。

用户确认关闭旧窗口后，已执行标准 Debug 构建（0 警告、0 错误），并从原入口重新启动主程序，进程 ID 35444。输出目录的 http_decode.py 和 pool.py 与源码 SHA256 一致。真实账号的新一轮采集及操作由用户继续手动验证。
