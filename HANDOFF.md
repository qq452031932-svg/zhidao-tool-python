# hong-1 开发交接

更新：2026-09-20（Asia/Shanghai）

## 1. 工作边界与目录

D:\hong-1 是后续开发目录。不得修改 C:\Users\45203\Documents\dakazhandian 下的现有代码；D:\hong 保留为上一阶段来源，后续改动应落在 D:\hong-1。

| 路径 | 用途 |
|---|---|
| D:\hong-1\PRD-拉新流水线重建-v1.md | 原需求和模块验收标准 |
| D:\hong-1\lxds、tests、demo | Python 拉新流水线 M01–M18、测试和离线演示 |
| D:\hong-1\dist\lxds_rebuilt-0.1.0-py3-none-any.whl | 已构建的 Python 安装包 |
| D:\hong-1\csharp_isolated | 以提交 608c524619ac91b9bbc17b52a7e0fe510783268a 为基线、实现 C02–C04 的 C# 独立副本 |
| D:\hong-1\dakazhandian | 从原目录复制的完整 C# 项目和 Git 历史；C02–C04 尚未合入 |
| D:\hong-1\README.md | Python 安装、CLI 和配置说明 |
| D:\hong-1\csharp_isolated\CHANGES.md | C# 修改点、测试及限制 |

完整 C# 目录复制了 397,618 个文件，Robocopy 失败数为 0。复制后的只读扫描显示源与副本的文件数、总字节数一致，增量扫描没有待补文件。仅在新副本内修正了 31 个 Git worktree 路径文件，并重建 3 个只指向 D:\hong-1 内部的目录连接。Git 列出的主仓库及 15 个 worktree 均已指向 D:\hong-1。原目录未改动。

完整 C# 主仓库当前提交为 92334976cf21de5a70b5771268f2646bc7599e60，分支 codex/superpan；transfer-share-link-replacement worktree 当前提交为 608c524619ac91b9bbc17b52a7e0fe510783268a。该 worktree 原本已有文档修改和未跟踪文件，已原样复制；不要清理或覆盖。其 src、tests 在复制时没有未提交差异。

## 2. 已实现的 Python 功能

M01–M18 的代码均在 D:\hong-1\lxds，分别有离线测试和 demo。“已实现”表示代码具备该能力，不代表线上账号验收已经完成。

| 模块 | 已实现的功能 |
|---|---|
| M01 config | 配置读写；Windows DPAPI 加密 DeepSeek Key、百度知道和百度网盘 Cookie；保存后回读校验 |
| M02 excelio | 读写 CSV/XLSX 资源表、识别名称/链接/提取码列、构造百度知道批量上传模板 |
| M03 deepseek | DeepSeek 聊天请求、JSON 模式及错误映射 |
| M04 qa | 按第一人称、第三人称、帮手三种提示词生成单题回答 |
| M05 zhidao_bulk | 获取知道账号信息，直连上传批量问答表并读取 taskId |
| M06 template_engine | 资源名和新网盘链接生成问答；标题格式与长度校正；AI 异常时整批兜底且不丢行 |
| M07 websearch | 百度网页搜索摘要；为模板补资料和采集补量 |
| M08 pan_auth | 网盘 Cookie 状态检查、bdstoken、列目录和目标目录核对 |
| M09 pan_transfer | 验证分享、读取文件、转存；区分重复、文件数超限及瞬时故障 |
| M10 pan_share | 创建新分享链接和提取码；组合单条转存与分享，并保留部分成功状态 |
| M11 zhidao_parse | 纯 HTML 解析搜索页/详情页、网盘链接、提取码、资源名 |
| M12 behavior | 请求节奏、休息和浏览器请求特征 |
| M13 pool | 多账号与出口分配，风控检测、健康探针、静默冷却及可中断等待 |
| M14 collect | 精准/模糊采集、去重、分页、补量、停止及进度回调 |
| M15 checkpoint | 进度文件读写、清理和过期裁剪；采集流程已接入断点 |
| M16 miner_parsers | 小说、影视、短剧、游戏、软件等公开榜单的抓取与名称解析 |
| M17 miner | 分配站点配额、历史去重、搜索补量，按领域输出关键词 TXT |
| M18 pipeline | mine、collect、transfer、template、publish、answer、run 七个 CLI 命令；中间文件落盘；本地或外部 C# 转存 |

完整主链路：挖词 → 百度知道采集 → 网盘转存/生成新分享 → 问答模板 → 知道批量上传。外部转存模式把采集表放入指定 inbox，等待本次任务之后产生的 C# 结果表，再由 M02 读取。

当前交付是命令行程序，没有新图形界面。凭据需由调用程序或脚本通过 ConfigStore 写入；尚无配置凭据的 CLI 子命令。M15 的采集断点已接入；转存和模板阶段主要依靠落盘的中间表从阶段入口重跑，不应宣称已具备逐行自动断点恢复。README 示例 workdir 仍写 D:/hong/output，新开发时应改为 D:/hong-1/output 或其他新目录。

## 3. 已实现的 C# 修改及隔离状态

C01：用户表示已在另一台电脑跑通真实转存与分享。此机器没有 PRD 要求的 6 份真实响应 JSON，也没有在本机重跑；不要将用户确认写成此机自动测试通过。

C02：D:\hong-1\csharp_isolated 细分 /share/transfer 的 errno 12。duplicated.list 识别为重复；能查到确切目标文件 ID 时写入 Succeeded/AlreadySatisfied 并保留分享证据。target_file_nums_limit、non_vip_limit、target_file_nums 识别为不可重试的 FileCountLimitExceeded；其他 errno 12 保持瞬时故障。结果列表显示“重复跳过”和“文件数超限”。若启用分享但重复文件的确切 ID 无法确认，因数据库证据约束，记为不可重试的 DuplicateEvidenceUnavailable，不能虚构分享成功。

C03：C# 结果表输出“资源名称 / 分享链接 / 提取码 / 状态 / 账号 / 目标目录 / 备注 / 错误”。链接取已生成的新分享；失败行不把旧链接伪装成新链接。已生成互通示例表，Python M02 直接读出正确名称与新链接。

C04：C# 导入识别“资源链接”和“网盘链接”。测试读取 Python M02 生成的资源表，无需人工映射。

上述修改只在 csharp_isolated；尚未合入 D:\hong-1\dakazhandian 的完整源码。不要把两处都称为已集成。

## 4. 已有验证与缺口

2026-09-20 在 D:\hong-1 重新运行：
- py -3.12 -m pytest tests -q -p no:cacheprovider：225 passed。
- py -3.12 -m demo.pipeline_demo：退出码 0，生成离线中间文件。
- py -3.12 -m lxds --help：七个命令可列出。

C# 在复制前于独立副本验证：App 项目构建 0 警告、0 错误；Core、网盘适配器、Excel 映射、调度、SQLite 对账、App 结果页的相关定向测试通过；C# 导出样表经 Python M02 实际读取通过。完整 solution 测试未全部通过，遇到 OTA/本地服务、Git 结构、样本及界面时序相关失败；尚未证明这些失败均是环境问题，不能宣称 C# 全量测试通过。

C02 测试目前使用按 PRD 字段构造的响应，而非 C01 的六份真实 JSON。百度知道、百度网盘、DeepSeek 当前线上行为及全流程真实账号运行，在本机尚未验收。PRD 的 I1–I7 线上集成验收和风控验收仍待执行；其中 I6（同一批 20 条链接在 Python 与 C# 逐条比较结果）是优先项。

## 5. 接手顺序

1. 先读本文件、根目录 PRD、README 与 csharp_isolated\CHANGES.md；确认只在 D:\hong-1 开发。
2. 在 D:\hong-1\dakazhandian 为新功能选独立分支或 worktree，保留已复制的文档改动和未跟踪文件。核对 csharp_isolated 与完整项目的差异，再将 C02–C04 安全整合到新开发分支；不要直接覆盖整个 src/tests。
3. 取得用户在另一台电脑 C01 存档的 6 份真实响应 JSON 和结果表，脱敏后加入测试 fixture，复验 errno 12 三分支。
4. 用一次性测试账号完成 I6：同一批 20 条链接由 Python 与 C# 各处理一次，逐条比较成功、失败和重复跳过。随后完成 I1–I7 及采集风控真机验收。
5. 定位 C# 全方案测试中的实际失败并修复，再考虑交付或合并。不要以定向测试通过代替全量验收。

## 6. 常用命令

在 D:\hong-1：
    py -3.12 -m pytest tests -q -p no:cacheprovider
    py -3.12 -m demo.pipeline_demo
    py -3.12 -m lxds --help

在 D:\hong-1\csharp_isolated：
    dotnet build src\BaiduBatchTransfer.App\BaiduBatchTransfer.App.csproj --verbosity quiet

在 D:\hong-1\dakazhandian：
    git status --short --branch
    git worktree list

不要在交接文档、日志或测试样本中写入真实 Cookie、DeepSeek Key 或 token。
