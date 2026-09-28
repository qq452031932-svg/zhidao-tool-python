# C# 开发环境全量验收记录（2026-09-28）

## 结论

**未通过。目录重建和定向测试通过，不代表环境可用于新功能开发。**

- 验证目录：`D:\hong-2\dakazhandian`
- 分支：`codex/collect-on-release`
- 源码提交：`8d3d9fd72158da54addb059a4d8ab16b6db87e71`
- 首轮执行用户指定的 `dotnet test --no-build`，已发现失败；因受限环境中存在权限提示及大量超时，未等其自然结束，终止后改用宿主权限完整复核。首轮不作为最终数量统计。
- 第二轮执行 `dotnet test --no-build --logger trx --results-directory .artifacts/full-test-20260928`，没有筛选、排除或修改测试。
- 第二轮已自然结束，仍有失败；原始 TRX 保存在 `D:\hong-2\dakazhandian\.artifacts\full-test-20260928`。
- 界面冒烟检查未执行：用户要求先通过 C# 全量测试。

## 已核实的问题

1. **错误类型缺少映射。** `BaiduErrorKind` 已新增 `DuplicateSkipped`、`FileCountLimitExceeded`，但 `BaiduAdapterResult.GetScope/GetSafeMessage` 没有对应分支。全量测试实际在 `DuplicateSkipped` 上抛出 `ArgumentOutOfRangeException`。
2. **Excel 导出存在真实列错位。** `OpenXmlResultWriter` 声明了“资源名称/分享链接/提取码/状态/账号/目标目录/备注/错误”八列表头，写入循环仍按旧结构输出七列，第一列仍是数值行号。不能仅通过修改测试期望消除失败。
3. **合成样本审计失败。** `Fixtures/ShareAnalytics/share-page.synthetic.json` 命中审计规则的 `https://` 模式。命中规则不等于已确认真实凭据泄露；需结合该样本用途修正样本或审计边界。
4. **本地授权服务工具链缺失，错误被清理逻辑掩盖。** `scripts/run_local_license_stack.ps1` 硬编码引用 `.tools\go-1.27.1\go\bin\go.exe`，该路径在新仓库和原仓库均不存在；脚本第 171 行会报工具链缺失，随后 finally 中的第 103 行又抛出运行目录所有权错误。即使宿主权限运行，相关测试仍失败。
5. **取消与超时测试未通过。** 包括大 Excel 节点读取的取消测试、两分钟超时的产品标识构建测试，以及 `ManagedTransferPickerSessionTests.CancelledPendingReconciliationSendRetainsUntilSettlementAndLaterConclusiveRetry` 超时。不能直接全部归因于代码或环境，需要单独核实。
6. **数据库调度状态断言失败。** `ShareSchedulingStoreTests.NewerActiveLoginIsNotInvalidatedByOlderObservedSessionFailure` 期望 `Accepted`，实际为 `ResultPending`；根因尚未确认。
7. **WPF 启动路径测试失败。** `AppBootstrapTests.RejectedLicensePreparesFreshAndOlderDatabasesAndCreatesLocalShellWithoutAuthorizedRecovery` 在加载界面资源时抛出“应用程序对象正在关闭”。需要核实应用生命周期和测试间共享状态，不能直接等同于已完成实机验证。
8. **大数据量性能验收失败。** Application 的 20 万行结果查询/导出用例实测约 32.37 秒，超过该用例的时间门槛。Infrastructure 的 20 万条资源、60 万条操作批量写入实测约 3 分 52 秒；60 万条分享操作分块写入实测约 4 分 29 秒，均未达到各自用例门槛。这些性能失败与资源占用和运行环境的关系尚需单独排查。

## 最终汇总

第二轮已自然结束，耗时约 48 分 37 秒，六个项目均生成 TRX；退出码 1。所有项目均参与，没有排除失败测试。

| 测试项目 | 通过 | 失败 | 跳过 | 总数 |
|---|---:|---:|---:|---:|
| BaiduBatchTransfer.App.Tests | 3338 | 15 | 9 | 3362 |
| BaiduBatchTransfer.Application.Tests | 1210 | 2 | 0 | 1212 |
| BaiduBatchTransfer.BaiduAdapter.Tests | 285 | 2 | 0 | 287 |
| BaiduBatchTransfer.Core.Tests | 356 | 0 | 0 | 356 |
| BaiduBatchTransfer.Infrastructure.Tests | 835 | 7 | 2 | 844 |
| SuperPan.Licensing.Client.Tests | 116 | 0 | 0 | 116 |
| **合计** | **6140** | **26** | **11** | **6177** |

采样时剩余进程在执行 SQLite 迁移、建库及大数据量用例；不能仅凭控制台长时间没有新输出认定死锁。采样文件和测试发现清单也保留在 TRX 目录。

## 失败用例清单

### BaiduBatchTransfer.App.Tests

- `BaiduBatchTransfer.App.Tests.Updates.ProductIdentityBuildTests.FreshDebugBuildUsesBrandedPhysicalNamesAndMetadata`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.LocalStackSupportsHttpLoginWithTheOneTimePassword`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StopRetriesTransientRuntimeRenameWhilePreservingTheJournal`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StopPreservesUnownedEmptyDirectoryAddedAfterInventoryAndCanRetry`
- `BaiduBatchTransfer.App.Tests.AppBootstrapTests.RejectedLicensePreparesFreshAndOlderDatabasesAndCreatesLocalShellWithoutAuthorizedRecovery`
- `BaiduBatchTransfer.App.Tests.Features.ManagedTransferPickerSessionTests.CancelledPendingReconciliationSendRetainsUntilSettlementAndLaterConclusiveRetry`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StopPreservesEmptyDirectoryReplacedByReparsePointAndCanRetry`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.PartialQuarantineDeletionRetainsJournalForIdempotentRetry`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StopScriptNeverDeletesAnExecutableReplacedAfterServiceExit`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StopScriptCleansArtifactsAfterTheOwnedServiceAlreadyExited`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StopPreservesExecutableReplacedAfterQuarantineVerificationAndCanRetry`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.ConcurrentStopsAreSerializedAndOnlyOneOwnsCleanup`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.ScriptsRejectConcurrentStartAndTamperedIdentityThenStopExactProcess`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StackStartsAndStopsThroughCheckoutPathContainingSpaces`
- `BaiduBatchTransfer.App.Tests.Updates.LicenseLocalStackScriptTests.StopPreservesChangedRuntimeArtifactAfterVerificationAndCanRetry`

### BaiduBatchTransfer.Application.Tests

- `BaiduBatchTransfer.Application.Tests.Jobs.PagingAndStatisticsTests.TwoHundredThousandResultsUseIndexedKeysetsAndBoundedExportMemory`
- `BaiduBatchTransfer.Application.Tests.Jobs.PagingAndStatisticsTests.ResultExportStreamsKeysetPagesAndEscapesFormulaText`

### BaiduBatchTransfer.BaiduAdapter.Tests

- `BaiduBatchTransfer.BaiduAdapter.Tests.WebAutomation.BaiduPageObservationParserTests.SyntheticFixturesContainNoSecretsOrRealIdentifiers`
- `BaiduBatchTransfer.BaiduAdapter.Tests.AdapterContractTests.Failure_UsesCanonicalPublicMessagesForEveryErrorKind`

### BaiduBatchTransfer.Infrastructure.Tests

- `BaiduBatchTransfer.Infrastructure.Tests.Excel.OpenXmlStreamingTests.CancelledResultExportLeavesAReadablePartialWorkbookThatCanBeRestarted`
- `BaiduBatchTransfer.Infrastructure.Tests.Database.RepositoryTests.PreparedStreamingWritesHandleTwoHundredThousandResourcesAndThreeReplicasWithinBoundedMemory`
- `BaiduBatchTransfer.Infrastructure.Tests.Excel.OpenXmlStreamingTests.TemplateAndResultWriterUseExpectedColumnsAndExplicitTextCells`
- `BaiduBatchTransfer.Infrastructure.Tests.Database.RepositoryTests.ShareWritesStreamSixHundredThousandOperationsInBoundedChunksAndMemory`
- `BaiduBatchTransfer.Infrastructure.Tests.Excel.ExcelColumnMappingTests.SharedStringAndCellReadersObserveCancellationBetweenLargeItemNodes`
- `BaiduBatchTransfer.Infrastructure.Tests.Database.ShareSchedulingStoreTests.NewerActiveLoginIsNotInvalidatedByOlderObservedSessionFailure`
- `BaiduBatchTransfer.Infrastructure.Tests.Excel.OpenXmlStreamingTests.ResultWriterRollsOverAtConfiguredExcelRowBoundaryAndRepeatsHeaders`

## 跳过用例清单

### BaiduBatchTransfer.App.Tests

- `BaiduBatchTransfer.App.Tests.Features.ManagedBrowserHelperClientTests.PackagedHelperCanObserveTheSelectedLiveAcceptanceTarget`
- `BaiduBatchTransfer.App.Tests.Features.ManagedBrowserHelperClientTests.PackagedHelperHandshakeHealthShutdownNeedsNoBrowserAndRetainsVerifiedLease`
- `BaiduBatchTransfer.App.Tests.Features.ManagedChromiumProcessManagerTests.OptInRealBrowserRemainsVisibleForFifteenSecondsAndOnlyOwnedJobIsClosed`
- `BaiduBatchTransfer.App.Tests.Features.ManagedBrowserHelperIntegrityVerifierTests.PackagedRuntimeImportCreatesNoFilesAndSnapshotCanBeVerifiedAgain`
- `BaiduBatchTransfer.App.Tests.Features.ManagedChromiumProcessManagerTests.ManualRealBrowserStaysOpenUntilUserClosesIt`
- `BaiduBatchTransfer.App.Tests.Features.ManagedBrowserHelperIntegrityVerifierTests.PackagedReleaseBundleMatchesTheEmbeddedManifestAndEveryPayloadHash`
- `BaiduBatchTransfer.App.Tests.Updates.OtaPublisherTrustTests.ExistingPublisherVerificationCanRunTwiceWithoutCreatingAnotherIdentity`
- `BaiduBatchTransfer.App.Tests.Updates.OtaPublisherTrustTests.EnrolledPrivateIdentityExistsOnlyAsOneNonExportableStoreKey`
- `BaiduBatchTransfer.App.Tests.Features.ManagedBrowserHelperIntegrityVerifierTests.PackagedRuntimeDisablesSiteAndCarriesCompleteLockedLicenseCorpus`

### BaiduBatchTransfer.Infrastructure.Tests

- `BaiduBatchTransfer.Infrastructure.Tests.Security.BrowserExecutableVerifierTests.ExplicitlySelectedChromeCompletesInitialAndLaunchVerification`
- `BaiduBatchTransfer.Infrastructure.Tests.Security.BrowserExecutableVerifierTests.ExplicitlySelectedEdgeCompletesInitialAndLaunchVerification`
