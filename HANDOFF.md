# hong-1/hong-2 双目录开发交接

更新：2026-09-28（Asia/Shanghai）

## 最新执行结果（2026-09-28 12:27，优先于下方历史记录）

用户指定的六项任务已按顺序完成。下文原有“必须重建”“224 passed, 1 failed”“miner.py 未提交”等描述属于执行前记录，不应再次据此删除当前开发目录。

- **C# 开发环境**：`D:\hong-2\dakazhandian` 已独立克隆，分支 `codex/collect-on-release`，当前提交 `8d3d9fd7`。`origin` 指向 `D:\hong-1\dakazhandian`，worktree 列表只包含 hong-2 本仓库。
- **重建发现的编译缺口**：原提交 `875ef777` 缺少 `CollectHelperClient.HasExited`，干净克隆无法编译。本次补齐属性并增加进程生命周期回归测试，已提交。全 solution 构建通过，0 警告、0 错误；采集客户端与 ViewModel 的 33 项测试通过。
- **助手运行时**：已从原开发目录复制 `.artifacts/helper-bundle-cdp` 到新 C# 仓库；真实助手握手测试通过。系统默认 Python 3.14 缺少 requests，外层 Python 测试使用依赖齐全的 `py -3.12`。
- **Python 测试修复**：`tests/test_zhidao_parse.py` 改用相对日期，提交 `eca65b0`；解析模块 14 项测试通过。
- **年份参数化**：`lxds/miner.py` 原有改动已提交为 `5aa67dc`，提交消息为 `refactor(miner): 参数化年份常量`。
- **完整 Python 测试**：hong-2 与同步后的 hong-1 均为 **225 passed**。
- **README**：工作目录示例已改为 `D:/hong-2/output`，提交 `ab8c8cf`。
- **稳定标签**：外层 Python 仓库已在 hong-1 创建注解标签 `v1.1-release`，指向 `ab8c8cf416c06b46e6af815e45a9cef08aa654d0`，并同步到 hong-2。此标签不包含被外层 Git 忽略的独立 C# 仓库。
- **保留现场**：旧 hong-2 C# 副本移至 `D:\hong-2\.recovery\20260928-environment-rebuild\dakazhandian-original`；其中旧 worktree 指针仍可能指向 hong-1，仅作为恢复备份，不作为开发入口。hong-1 的 dev-playwright 原有 15 个未提交文件保持原样，另有补丁备份；其未提交改动未整批迁入新仓库。
- **稳定目录原有文档修改**：已保存为恢复目录中的 `hong-1-HANDOFF-before-release.md`、补丁和 hong-1 的 Git stash（标识记录在 `hong-1-handoff-stash.txt`），未重新应用。原稳定提交另由 `codex/pre-v1.1-release-20260928` 分支保留。
- **验证边界**：C# 稳定分支 `codex/superpan` 与开发分支已分叉，本轮未整条合并；C# 全量测试、界面实机及真实账号端到端验收仍未完成。本次标签是 Python 源码稳定点，未重新生成安装包。

---

## 0. 双目录隔离策略（2026-09-28 重要更新）

**本项目采用物理隔离的双目录策略，明确区分稳定版本与开发环境。**

### 目录角色定义

| 目录 | 角色 | 用途 | 修改策略 |
|------|------|------|----------|
| **D:\hong-1** | 稳定发版环境 | 已验证的可运行版本，用于紧急回退 | 🔒 **仅发布新版本时更新**，不在此开发新功能 |
| **D:\hong-2** | 日常开发环境 | 当前活跃工作目录，所有新功能在此开发 | ✅ 随意修改、测试、提交 |

### 稳定版本标记（D:\hong-1）

- **Python 稳定版**
  - Git 仓库：`D:\hong-1`（独立仓库）
  - 稳定标签：`v1.0-release` 
  - 提交 ID：`f6887a0`（2026-09-20 14:56:30）
  - 状态：M01-M18 模块完整，测试通过

- **C# 稳定版**
  - Git 仓库：`D:\hong-1\dakazhandian`
  - 主分支：`main` / `codex/superpan`
  - 基线提交：`92334976`
  - ⚠️ **注意**：最新界面开发在 worktree `dev-playwright`（分支 `codex/collect-on-release`，提交 `875ef777`），这部分还在迭代，不属于"稳定版"

### 开发版本状态（D:\hong-2）

- **Python 开发版**
  - Git 仓库：`D:\hong-2`（独立仓库，从 hong-1 fork）
  - 当前分支：`main`
  - 最新提交：`f6887a0`
  - 未提交改动：`lxds/miner.py`（年份参数化，待提交）
  - 测试状态：224 passed, 1 failed（`test_zhidao_parse.py:82` 时间敏感测试）

- **C# 开发版**
  - ⚠️ **状态：需要重建**
  - `D:\hong-2\dakazhandian` 当前是损坏副本（Git 配置仍指向 hong-1）
  - **必须执行重建步骤**（见下方"重建 C# 开发环境"）

### 回退策略

当 hong-2 开发出现严重问题时：

**方案 A：回退到最后的好提交**
```bash
cd D:\hong-2
git log --oneline  # 找到最后一个稳定提交
git reset --hard <commit-id>
```

**方案 B：完全重置到稳定版**
```bash
# 1. 备份当前工作（如果有未提交的重要改动）
cd D:\hong-2
git stash  # 或 git branch backup-$(date +%Y%m%d)

# 2. 删除开发目录
cd D:\
rm -rf hong-2

# 3. 从稳定版重新 clone
mkdir hong-2
cd hong-2

# Python
git clone D:\hong-1 .

# C#
git clone D:\hong-1\dakazhandian dakazhandian
cd dakazhandian
git checkout -b my-new-dev-branch
```

### 重建 C# 开发环境（立即执行）

**当前 `D:\hong-2\dakazhandian` 的 Git 配置已损坏，必须重建：**

```powershell
# 1. 删除损坏的副本
cd D:\hong-2
Remove-Item -Recurse -Force dakazhandian

# 2. 从 hong-1 重新 clone
git clone D:\hong-1\dakazhandian dakazhandian

# 3. 切换到开发分支（或新建分支）
cd dakazhandian
git checkout -b dev-my-feature  # 或 git checkout codex/collect-on-release

# 4. 验证 Git 配置
git remote -v
git worktree list  # 确认引用正确
```

### 同步策略

**hong-1 → hong-2（稳定版发布新版本后）**

```bash
# Python
cd D:\hong-2
git fetch D:\hong-1
git merge <stable-tag>  # 如 v1.1-release

# C#
cd D:\hong-2\dakazhandian
git fetch origin
git merge main  # 或合并稳定分支
```

**hong-2 → hong-1（开发版验证通过，准备发版）**

```bash
# 1. 在 hong-2 确认测试通过
cd D:\hong-2
pytest tests/ -v  # Python
cd dakazhandian && dotnet build  # C#

# 2. 推送到 hong-1
git push D:\hong-1 HEAD:main

# 3. 在 hong-1 打标签
cd D:\hong-1
git tag -a v1.1-release -m "第二次发版"
```

### 文档路径约定

- 本交接文档（`HANDOFF.md`）同时存在于两个目录
- 修改时**先在 hong-2 更新**，验证通过后复制到 hong-1
- 代码路径引用：
  - 涉及稳定版时写 `D:\hong-1`
  - 涉及开发版时写 `D:\hong-2`
  - 如果是通用说明（两边都适用），写相对路径或标注 `<根目录>`

---

## 1. 最新接手入口（2026-09-28 审阅）

本节记录 2026-09-28 代码审阅结果。后文保留 2026-09-20 的重建、复制和测试记录；历史记录不等于最新分支已完成同样的验收。

### 当前开发位置与最新提交

**⚠️ 重要：C# 最新开发仍在 hong-1 的 worktree，尚未迁移到 hong-2**

- **C# 最新开发目录**：`D:\hong-1\dakazhandian\.worktrees\dev-playwright`
- **分支**：`codex/collect-on-release`
- **最新提交**：`875ef777`（2026-09-28，Claude 修复 UI 上下文捕获与连接清理逻辑）
- **上一个人工提交**：`6b321a35`（2026-09-23 23:53:26 +08:00，修复监控反馈表头）

**Python 开发目录**：`D:\hong-2`（独立 Git 仓库）
- **分支**：`main`
- **最新提交**：`f6887a0`（2026-09-20 14:56:30 +08:00，首次纳入版本控制）
- **未提交改动**：`lxds/miner.py`（年份参数化）

**重要提示**：
1. 不要只看外层仓库（`D:\hong-1` 或 `D:\hong-2`）判断整个开发进度
2. C# `dakazhandian` 根工作目录在 `codex/superpan` / `92334976`，不代表最新界面代码
3. 修改前应在目标目录重新确认分支和工作区状态
4. `D:\hong-2\dakazhandian` 当前是损坏副本，**必须先重建**（见第 0 节）

### 最近功能进展与代码入口

**2026-09-28 最新修复**（Claude 提交）：

| 提交 | 内容 |
|---|---|
| `875ef777` | 修复 CollectViewModel UI 上下文捕获时机、进程存活检查、连接清理逻辑，补上 ValidateCookieCommand 初始化 |
| `18600f99` | 修复 FakeCollectHelperProcess 缺少 StandardError 属性实现（测试桩编译错误） |

**2026-09-23 近期提交**：

| 提交 | 内容 |
|---|---|
| `6b321a35` | 修复监控反馈表头空白及点击不排序 |
| `c2a79c2c`、`82810cfc` | 统一输入框文本内缩为 7px，修正占位提示与光标对齐 |
| `37a4f1d8`、`943a7321` | 调整采集页布局，修复文字重叠和重复标题，增加关键词说明及文件导入 |
| `f0248df2`、`79a7b1f5`、`773585f6` | 接入知道采集页面、C# 采集助手客户端和 Python 采集助手 |
| `fc2ea807`、`eb4ebc35` | 用自带 CDP 客户端替换第三方浏览器驱动，并重新生成 helper 包 |

**C# 代码入口**（以 `D:\hong-1\dakazhandian\.worktrees\dev-playwright` 为根）：

| 路径 | 用途 |
|---|---|
| `src/BaiduBatchTransfer.App/Features/Collect/` | `CollectView.xaml`、`CollectViewModel.cs`：知道采集界面、关键词导入、开始/停止、进度和风险提示交互 |
| `src/BaiduBatchTransfer.App/Features/Collect/` | `CollectHelperClient.cs`、`CollectHelperSession.cs`：Python 子进程定位、启动、生命周期与按行 JSON 通信 |
| `tools/collect_helper/` | `main.py`、`protocol.py`、`lxds/`：Python 采集助手及其携带的采集模块 |
| `src/BaiduBatchTransfer.App/Features/ShareAnalytics/ShareAnalyticsView.xaml` | 监控反馈表格；绑定代理在 `src/BaiduBatchTransfer.App/Features/Common/BindingProxy.cs` |
| `tests/BaiduBatchTransfer.App.Tests/Features/` | `Collect*Tests.cs`、`ShareAnalyticsView*Tests.cs`：采集与监控反馈的 C# 测试入口 |
| `tools/collect_helper/tests/test_collect_helper.py` | 采集助手协议、关键词文件、事件流、停止与风险答复测试 |

**Python 代码入口**（`D:\hong-2\lxds`）：

| 路径 | 用途 |
|---|---|
| `lxds/miner.py` | 挖词模块（⚠️ 有未提交的年份参数化改动） |
| `lxds/collect.py` | 采集核心逻辑 |
| `lxds/zhidao_parse.py` | 知道页面解析（⚠️ 测试失败：`test_within_range_uses_iso_dates`） |
| `tests/` | Python 测试套件（224 passed, 1 failed） |

**架构说明**：
- C# WPF 界面通过本机 Python 子进程调用采集能力
- 资源、进度、日志等事件通过 stdin/stdout JSON 协议回传给界面
- `tools/collect_helper/lxds/` 与外层 `D:\hong-2\lxds` 是不同目录，修改其中一处不会自动同步

### 本轮验证范围与后续约定

**2026-09-28 审阅内容**：
- ✅ 读取 C# 代码，发现并修复 2 个编译错误：
  - `CollectViewModel.cs` UI 上下文捕获时机错误
  - `FakeCollectHelperProcess.cs` 缺少 `StandardError` 属性
- ✅ 验证 C# 编译通过（在 `D:\hong-1\dakazhandian\.worktrees\dev-playwright`）
- ✅ 检查 Python 测试状态：224 passed, 1 failed
- ✅ 发现 `lxds/miner.py` 有未提交的年份参数化改动
- ✅ 核查双目录 Git 配置，发现 `D:\hong-2\dakazhandian` 损坏
- ✅ 更新交接文档，增加双目录隔离策略说明

**本轮未做的事**：
- ❌ 未运行 C# 实机测试（只验证编译）
- ❌ 未修复 Python 测试失败（`test_zhidao_parse.py:82` 时间敏感测试）
- ❌ 未提交 `lxds/miner.py` 改动
- ❌ 未重建 `D:\hong-2\dakazhandian`
- ❌ 未执行完整端到端流程测试

**立即待办事项**（按优先级）：

1. **重建 C# 开发环境**（高优先级）
   ```powershell
   cd D:\hong-2
   Remove-Item -Recurse -Force dakazhandian
   git clone D:\hong-1\dakazhandian dakazhandian
   cd dakazhandian
   git checkout codex/collect-on-release
   ```

2. **提交 Python 改动**
   ```bash
   cd D:\hong-2
   git add lxds/miner.py
   git commit -m "refactor(miner): 参数化搜索模板年份以便跨年维护"
   ```

3. **修复时间敏感测试**
   - 编辑 `tests/test_zhidao_parse.py:82`
   - 用相对日期替换硬编码的 `"2026-09-18"`
   - 运行 `pytest tests/test_zhidao_parse.py -v` 验证

4. **更新稳定版标签**（等开发版验证通过后）
   ```bash
   cd D:\hong-1
   git tag -a v1.1-release -m "第二次发版：修复 UI 上下文、年份参数化"
   ```

**后续开发约定**：
- 所有新功能在 `D:\hong-2` 开发
- `D:\hong-1` 保持锁定，仅发版时更新
- 修改 Python 代码：在 `D:\hong-2\lxds` 修改
- 修改 C# 代码：重建 `D:\hong-2\dakazhandian` 后在那里修改
- 提交前运行测试：Python `pytest tests/`，C# `dotnet build`
- C02–C04 独立副本的迁移状态本轮未复核；如需这些功能，先比较实际代码

### 已知问题清单（2026-09-28）

**高优先级（阻塞开发）**：

1. **`D:\hong-2\dakazhandian` Git 配置损坏**
   - 症状：Git 配置仍指向 `D:\hong-1` 的 worktree 路径
   - 影响：无法在 hong-2 独立开发 C# 代码
   - 修复方案：删除后重新 clone（见第 0 节"重建 C# 开发环境"）

**中优先级（影响测试）**：

2. **`tests/test_zhidao_parse.py:82` 时间敏感测试失败**
   - 症状：`assert within_range("2026-09-18", 7) is True` 已过期（今天是 9 月 28 日）
   - 影响：测试套件显示 `224 passed, 1 failed`
   - 修复方案：
     ```python
     from datetime import date, timedelta
     recent = (date.today() - timedelta(days=3)).isoformat()
     old = (date.today() - timedelta(days=365)).isoformat()
     assert within_range(recent, 7) is True
     assert within_range(old, 7) is False
     ```

3. **`lxds/miner.py` 有未提交改动**
   - 内容：年份参数化（`SEARCH_YEAR = "2026"`）
   - 影响：改动未进版本控制，克隆仓库会丢失
   - 修复方案：`git add lxds/miner.py && git commit`

**低优先级（文档）**：

4. **`README.md` 示例路径过时**
   - 内容：示例写 `D:/hong/output`，应为 `D:/hong-2/output`
   - 影响：用户按示例操作会失败
   - 修复方案：全局替换路径

5. **两处 `lxds` 目录不同步**
   - `D:\hong-2\lxds`（Python 开发版）
   - `D:\hong-1\dakazhandian\.worktrees\dev-playwright\tools\collect_helper\lxds`（C# 携带的副本）
   - 影响：修改一处不会自动同步到另一处
   - 建议：建立明确的同步流程或符号链接

---

## 2. 工作边界与目录（已更新）

**主工作目录**：`D:\hong-2`（日常开发）  
**稳定版目录**：`D:\hong-1`（发版快照，仅紧急回退时使用）

**开发环境（hong-2）**：

| 路径 | 用途 | 状态 |
|---|---|---|
| `D:\hong-2\PRD-拉新流水线重建-v1.md` | 原需求和模块验收标准 | ✅ |
| `D:\hong-2\lxds`、`tests`、`demo` | Python 拉新流水线 M01–M18、测试和离线演示 | ✅（1 个测试失败） |
| `D:\hong-2\dist\lxds_rebuilt-0.1.0-py3-none-any.whl` | 已构建的 Python 安装包 | ✅ |
| `D:\hong-2\dakazhandian` | C# 项目（⚠️ 需要重建） | ❌ Git 配置损坏 |
| `D:\hong-2\README.md` | Python 安装、CLI 和配置说明 | ⚠️ 示例路径过时 |
| `D:\hong-2\HANDOFF.md` | 本交接文档 | ✅ 已更新 |

**稳定环境（hong-1）**：

| 路径 | 用途 | 备注 |
|---|---|---|
| `D:\hong-1\` | Python 稳定版（Git 仓库） | 提交 `f6887a0`，标签 `v1.0-release` |
| `D:\hong-1\dakazhandian` | C# 稳定版主仓库 | 分支 `codex/superpan`，提交 `92334976` |
| `D:\hong-1\dakazhandian\.worktrees\dev-playwright` | C# 最新界面开发（⚠️ 仍在迭代） | 分支 `codex/collect-on-release`，提交 `875ef777` |
| `D:\hong-1\csharp_isolated` | C02–C04 独立副本 | 基线提交 `608c524619ac91b9bbc17b52a7e0fe510783268a` |

**历史记录（2026-09-20 复制记录）**：
- 完整 C# 目录复制了 397,618 个文件，Robocopy 失败数为 0
- 复制后修正了 31 个 Git worktree 路径文件，重建 3 个目录连接
- 主仓库及 15 个 worktree 均已指向 `D:\hong-1`
- `transfer-share-link-replacement` worktree（提交 `608c524619ac91b9bbc17b52a7e0fe510783268a`）原本已有文档修改和未跟踪文件，已原样复制

**不再使用的目录**：
- `C:\Users\45203\Documents\dakazhandian`（原始目录，不得修改）
- `D:\hong`（上一阶段来源，保留但不再开发）

## 3. 已实现的 Python 功能（验证状态更新）

M01–M18 的代码均在 `D:\hong-2\lxds`（开发版）和 `D:\hong-1\lxds`（稳定版），分别有离线测试和 demo。

**测试状态**：
- ✅ **224 passed**（2026-09-28 实测）
- ❌ **1 failed**：`tests/test_zhidao_parse.py::test_within_range_uses_iso_dates`（时间敏感测试过期）
- ⚠️ 交接文档历史记录写 “225 passed”，那是 2026-09-20 的结果，不代表当前状态

**”已实现”的含义**：代码具备该能力，离线测试通过，但不代表线上账号验收已经完成。

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

外层 Python 包的交付形式仍是命令行程序；最新 C# 分支已新增知道采集图形界面，详见第 0 节。外层 CLI 的凭据需由调用程序或脚本通过 ConfigStore 写入；尚无配置凭据的 CLI 子命令。M15 的采集断点已接入；转存和模板阶段主要依靠落盘的中间表从阶段入口重跑，不应宣称已具备逐行自动断点恢复。README 示例 workdir 仍写 D:/hong/output，新开发时应改为 D:/hong-1/output 或其他新目录。

## 3. 已实现的 C# 修改及隔离状态

C01：用户表示已在另一台电脑跑通真实转存与分享。此机器没有 PRD 要求的 6 份真实响应 JSON，也没有在本机重跑；不要将用户确认写成此机自动测试通过。

C02：D:\hong-1\csharp_isolated 细分 /share/transfer 的 errno 12。duplicated.list 识别为重复；能查到确切目标文件 ID 时写入 Succeeded/AlreadySatisfied 并保留分享证据。target_file_nums_limit、non_vip_limit、target_file_nums 识别为不可重试的 FileCountLimitExceeded；其他 errno 12 保持瞬时故障。结果列表显示“重复跳过”和“文件数超限”。若启用分享但重复文件的确切 ID 无法确认，因数据库证据约束，记为不可重试的 DuplicateEvidenceUnavailable，不能虚构分享成功。

C03：C# 结果表输出“资源名称 / 分享链接 / 提取码 / 状态 / 账号 / 目标目录 / 备注 / 错误”。链接取已生成的新分享；失败行不把旧链接伪装成新链接。已生成互通示例表，Python M02 直接读出正确名称与新链接。

C04：C# 导入识别“资源链接”和“网盘链接”。测试读取 Python M02 生成的资源表，无需人工映射。

截至 2026-09-20 的交接记录，上述修改只在 csharp_isolated，尚未合入 D:\hong-1\dakazhandian 的完整源码。2026-09-26 未逐项复核其在最新分支中的整合状态，不应直接宣称已经集成，也不要未比较代码就覆盖迁移。

## 4. 已有验证与缺口

以下为 2026-09-20 交接保留的历史验证和待验收事项；2026-09-26 未重跑，最新分支的验证范围见第 0 节。

2026-09-20 在 D:\hong-1 重新运行：
- py -3.12 -m pytest tests -q -p no:cacheprovider：225 passed。
- py -3.12 -m demo.pipeline_demo：退出码 0，生成离线中间文件。
- py -3.12 -m lxds --help：七个命令可列出。

C# 在复制前于独立副本验证：App 项目构建 0 警告、0 错误；Core、网盘适配器、Excel 映射、调度、SQLite 对账、App 结果页的相关定向测试通过；C# 导出样表经 Python M02 实际读取通过。完整 solution 测试未全部通过，遇到 OTA/本地服务、Git 结构、样本及界面时序相关失败；尚未证明这些失败均是环境问题，不能宣称 C# 全量测试通过。

C02 测试目前使用按 PRD 字段构造的响应，而非 C01 的六份真实 JSON。百度知道、百度网盘、DeepSeek 当前线上行为及全流程真实账号运行，在本机尚未验收。PRD 的 I1–I7 线上集成验收和风控验收仍待执行；其中 I6（同一批 20 条链接在 Python 与 C# 逐条比较结果）是优先项。

## 5. 接手顺序

1. 先读第 0 节并承接用户的具体修改要求；用户尚未布置的功能或历史待办不自动开工。
2. 根据修改对象选择目录：最新桌面界面/采集功能从 dev-playwright 工作目录接手，外层 Python CLI 从 D:\hong-1\lxds 接手。改前重新核查分支、最新提交及未提交文件，保留已有改动。需要隔离时从确认的目标基线创建分支或 worktree，不默认从较旧的 codex/superpan 开始。
3. 按任务阅读相关 PRD、README、设计与测试。任务涉及 C02–C04 时，先比较 csharp_isolated 与目标分支，再决定需要迁移的具体改动；不要覆盖整个 src/tests。
4. 修改后运行与改动对应的验证，分别记录自动测试、构建和实机验证结果，不以历史通过记录代替本轮验证。

保留的历史验收待办（按后续任务范围安排）：取得 C01 的 6 份脱敏真实响应及结果表，复验 errno 12 三分支；完成 I6 的 Python/C# 同批 20 条链接对比，再完成其余 I1–I7 与采集真机验收；定位 C# 全方案测试失败。上述工作未在本轮执行，不以定向测试通过代替全量验收。

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

核查最新开发目录（可从任意目录运行）：

```powershell
git -C D:\hong-1\dakazhandian\.worktrees\dev-playwright status --short --branch
git -C D:\hong-1\dakazhandian\.worktrees\dev-playwright log -5 --date=iso-strict --format="%h %cI %s"
git -C D:\hong-1\dakazhandian for-each-ref --sort=-committerdate --count=5 --format="%(committerdate:iso-strict) %(refname:short) %(objectname:short)"
```

不要在交接文档、日志或测试样本中写入真实 Cookie、DeepSeek Key 或 token。
