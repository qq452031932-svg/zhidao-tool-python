# 2026-09-30 未调用代码清理与验证

用户已实测确认采集规则符合要求，要求清理未使用代码，保留 UI、正常功能和 OTA 源码，清理后再次实测，通过后再发新版。本轮完成本地清理及测试版本准备，没有修改版本号、提交代码、签名、发布 OTA 或分发安装包。

## 清理范围

清理前检查源代码、DI 注册、XAML、后台入口、反射、序列化、测试、脚本及构建引用。独立审查复核了清理前后差异。12 个生产源文件只删除 151 行，不新增或替换运行逻辑：

| 文件（相对于 `dakazhandian`） | 删除内容 |
|---|---|
| `src/BaiduBatchTransfer.App/AppStartupController.cs` | 未注册的 `UnavailableAppRecoveryRunner`；保留整个真实启动恢复与授权流程 |
| `src/BaiduBatchTransfer.App/Features/Imports/LocalImportWorkflow.cs` | 无调用的 `ReadExcelAsync`；现有导入/恢复读取流程仍保留 |
| `src/BaiduBatchTransfer.App/Features/BrowserAutomation/WebViewBaiduNetdiskAdapter.cs` | 无引用的 `OfficialFilesUri` 字段 |
| `src/BaiduBatchTransfer.App/Features/Shares/ShareWorkspaceViewModel.cs` | 两个已被真实实现替代的资源选择/分享存储占位类 |
| `src/BaiduBatchTransfer.App/Features/Transfers/TransferWorkspaceOptions.cs` | 无注册、无调用的旧内存结果目录桥接类及过期注释 |
| `src/BaiduBatchTransfer.App/Services/DialogService.cs` | 两个未使用的登录/适配器不可用占位类；保留真实实现及接口 |
| `src/BaiduBatchTransfer.Application/Scheduling/ExistingShareDecisionService.cs` | 未用 `policy` 字段、`Request` 私有方法 |
| `src/BaiduBatchTransfer.Application/Scheduling/StandaloneShareOperationExecutor.cs` | 无调用的 `MarkResultPendingAsync` 包装方法；实际提交回调保留 |
| `src/BaiduBatchTransfer.BaiduAdapter/WebAutomation/TransferAutomationContracts.cs` | 无参数、字段、序列化或协议引用的 `TransferListingCompleteness` 旧 record |
| `tools/collect_helper/lxds/pool.py`、外层 `lxds/pool.py` | 同步移除无调用的 `_ask_when_all_blocked`；现用风险处理路径不变 |
| `tools/collect_helper/main.py` | 未使用的 `io` import |

根目录 `diagnose_collect_helper.py`、`test_collect_manually.py` 无调用且硬编码指向旧 `D:\hong-1`；已完整归档后从工作根移除，没有执行它们。

## 备份及保护证据

- 备份：`D:\hong-2\.recovery\20260930-unused-code-cleanup`，14 份源文件/旧脚本，SHA256 全部复核一致。备份反映清理前的工作区，包含此前尚未提交的功能修复；不能用 HEAD 代替该基线恢复。
- `source-hashes.json` 记录待清理文件；`ui-hashes.json` 记录 **24 个源 XAML，全部未变**。
- `ota-protected.json` 记录 **352 个 OTA/授权保护文件 + 47 个共享装配/打包输入，合计 399 项全部未变**。OTA 后端、部署、数据库迁移、恢复/回滚、签名信任配置、更新器、旧启动器、授权源码及相关测试均保留。
- 保留 `LicenseAcceptanceSmokeRunner.cs` 中实际使用的授权注册；保留验收入口、嵌入 ZIP/CER 夹具、条件编译文件。文件名并不是删除依据。
- 保留外层 CLI 的七类命令和支持模块；保留 `csharp_isolated`，该历史副本含 C02–C04 修复，不能因为主 UI 不引用就推定没有保留价值。
- 保留原安装包、既有恢复备份及两个有实际构建依赖的 helper bundle：`.artifacts/helper-bundle-cdp`、`.artifacts/managed-session-pipeline-20260901/helper-bundle-r2`。
- 独立审查未发现清理引入的阻断项；同名但仍被调用的方法/字段、扩展方法和 DI 注册均保留。

审计与机器可读验证材料位于 `dakazhandian/.artifacts/cleanup-audit-20260930/`，包括 `app-audit.json`、`ota-protected.json`、`cleanup-integrity.json`、`deployment_report.json`、TRX 及摘要。`verify_cleanup.py` 检查备份完整性、仅删除差异及 399/24 项保护哈希。

## 验证结果与边界

| 检查 | 结果 |
|---|---|
| 全解决方案隔离 Debug 构建 | 0 警告、0 错误；使用本机 NuGet 缓存还原 |
| 原标准 Debug 入口与 App 测试项目构建 | 0 警告、0 错误 |
| 主程序受影响功能：采集、导入、浏览器转存适配、分享、转存工作区、启动、对话框 | **431 通过** |
| OTA/品牌/授权相关离线组 | **594 通过**；排除真实证书库及已知缺工具链的本地授权服务集成组 |
| Application 分享执行、协调与核对 | **62 通过** |
| 授权客户端完整测试 | **116 通过** |
| 采集助手完整 Python 测试 | **222 通过** |
| 外层 Python 完整测试 | **257 通过，另 50 子测试通过** |
| managed helper 打包输入检查 | **27 通过** |
| BaiduAdapter 扩大检查 | **285 通过、2 个已有失败**：错误枚举映射、合成样本审计，均与 9 月 28 日清单一致 |
| 两仓库 `git diff --check` | 通过，仍有既有换行提示 |
| 运行目录采集助手 | **15 个生产 Python 文件与源码一致**，两份核心镜像一致，实际内置解释器返回 ready/pong |

扩大检查过程中保留了失败记录，没有删测试或改断言求绿：

1. 首轮隔离 App 测试 1042 通过、91 失败、1 跳过。其中 75 项找不到 PATH 中的 PowerShell 7；另外暴露固定相对目录、WPF 测试生命周期和临时启动器检查问题。12 项本地授权服务失败与 9 月 28 日失败列表双向一致：固定 Go 工具链不存在，清理异常掩盖原错误。
2. 补齐测试进程 PATH 并回到标准目录后，混合组完成 662 项且均通过，但 WPF 测试宿主崩溃导致整轮中止，不能记作整轮通过。
3. 随后拆分进程复查，功能组 431 项、OTA 离线组 594 项全部通过。未修改生产代码或测试断言解决测试环境问题。

本轮不是全量 C# 验收，也没有关闭 [9 月 28 日全量记录](2026-09-28-csharp-full-tests.md) 的其余历史问题。未读取真实 Cookie、执行联网采集、账号远端转存或真实证书库验收。

## 本地复测入口及发版前事项

清理后的程序已更新到原入口：

`D:\hong-2\dakazhandian\src\BaiduBatchTransfer.App\bin\Debug\net8.0-windows\知道综合工具.exe`

已打开 PID **50968**，独立窗口 **2819540**；通过 Windows UI 状态确认“当前模块：首页”“就绪”。用户可以重新测试采集、表格导入、复制/导出、送入转存及其他功能。

正式发布仍须在用户复测通过后处理现有发布输入问题：

- `scripts/build_ota_release.ps1` 的生产源码快照允许 `src` 和 `tools/managed_browser_helper`，未纳入 `tools/collect_helper`，而 App 打包配置依赖它；必须验证最终生产包内采集助手齐全。
- 生产构建取 HEAD 加受审核 SHA256 覆盖白名单，当前未提交修复不会自动全部入包。发版时必须整理并核对真实发布来源，不能绕过现有发布安全边界。

本次仅记录这些既有风险，没有改动 OTA 发布脚本，也没有发布新版本。
