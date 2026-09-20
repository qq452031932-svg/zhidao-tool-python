# C# C02–C04 独立副本实施计划

来源是原工作树提交 `608c524619ac91b9bbc17b52a7e0fe510783268a` 的只读 `git archive`，提取到 `D:\hong\csharp_isolated`。原工作树只有文档改动，代码与该提交一致。后续仅编辑副本。用户已经在另一台电脑验证 C01；六份真实响应未在本机提供，因此测试可用合成响应，但不能声称完成基于 C01 存档的交叉验证。

1. C04：导入列名补 `资源链接` 与 `网盘链接`，补实际 Python 三列表导入测试。
2. C03：从 `OperationResultRecord.ResolvedTitle`、`GeneratedShareUrl`、`GeneratedExtractionCode` 传到导出行；表头改为三列互通字段加原五列排障字段。确认失败行不会把原链接伪装成新分享。以 C# 导出文件经 Python M02 读取验收。
3. C02：针对 `/share/transfer` errno 12 细分重复与文件数上限；定义不可重试状态并贯穿调度与状态持久化。测试三分支及全量回归。由于真实 JSON 不在本机，先在测试中构造与 PRD 字段一致的响应，保留后续替换为真实 fixture 的入口。

每步先添加失败测试，再改实现。先跑受影响项目测试，再按可用环境跑全量；构建与测试都只在 `D:\hong\csharp_isolated` 写入。

实施结果见 `D:\hong\csharp_isolated\CHANGES.md`。三项已在副本中实现；真实六份响应仍未在此机器取得，全方案测试在副本环境有非本项失败。数据库约束要求启用分享时具备确切文件证据，因此重复响应确认但 ID 无法确认的任务记录为不可重试的 `DuplicateEvidenceUnavailable`，不伪造已生成分享。
