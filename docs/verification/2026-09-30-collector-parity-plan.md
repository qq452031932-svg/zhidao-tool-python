# v1.0.4 精准 / 模糊采集规则对齐实施计划

> **For agentic workers:** Use superpowers:subagent-driven-development and test-driven-development. Preserve existing uncommitted work. Do not change UI, credentials, original installation, or hong-1.

**Goal:** 在现有 WPF 界面、通信协议和结果操作保持不变的前提下，将精准、模糊采集的内部决策对齐用户指定 v1.0.4。

**Architecture:** 将原程序静态提取的采集函数逐项转换为可维护 Python 源码；沿用现有 callback / JSON-lines 适配层。两个 Python 核心副本同步；用离线固定响应验证搜索轨迹、收录结果、停止/重试和逐条交付。新代码不依赖旧 EXE 运行、不新增 Qt 运行时。

**Tech Stack:** Python 3.14 bundled runtime, unittest, requests; existing WPF / .NET 8 adapter.

## 已授权范围与边界

- 用户 2026-09-30 明确授权对照、照搬原版内部规则，UI 不做更改。此前比较已确认关键偏差；不重复请求设计批准。
- 原件：`安装包_百度知道拉新大师_v1.0.4_20260918/百度知道拉新大师/百度知道拉新大师.exe`，SHA256 `B3AF68F956ACF4474FAA262703A28200B9541820CA5C61F1BB25E73EA356981C`。
- 证据：`dakazhandian/.artifacts/legacy-compare-20260930/*.dis.txt`、`catalog.json`。读取完整相关函数，不把模块注释当执行行为。
- 现有开发目录包含用户正在测试的未提交修复，按项目物理隔离策略在 hong-2 工作；先保存本轮基线，禁止 reset / 覆盖其他改动。保持 UI 文件本轮前后哈希一致。
- 原版无严格语义相关性评分，不能擅自新增“标题必须包含关键词”的筛选。既有 UTF-8 解码、URL/提取码边界、搜索结果容器边界、可中断等待和逐条交付修复保留；这些兼容性修复需单列说明。
- 搜索规则的等价性以相同网页响应和确定的随机种子为验证基础。网络波动不作为规则对齐的证据。
- 单个现有 Cookie 输入保持单账号工作；不增加原版多账号管理 UI。原版可选项取其 UI 默认值，需从 collect_page 核对。

## Task 1: 规则基线与备份

Files: diagnostics directory above; `.recovery/20260930-collector-parity-baseline`; this plan.

- [x] 保存两份核心、助手协议和 UI 哈希，以及 git 状态。
- [x] 逐函数核对 precise/fuzzy、web supplement、parser、behavior/pool 及 UI 默认参数。
- [x] 独立审阅本计划和规则清单，修正未覆盖项。
- [x] 运行助手 Python 全套作为本轮基线。

## Task 2: 解析与资源命名

Files: `dakazhandian/tools/collect_helper/lxds/zhidao_parse.py`, mirror `lxds/zhidao_parse.py`; new helper `tests/test_legacy_parser_parity.py`.

- [x] 为原版名称长度、噪声词、领域前缀、书名/文件名、无具体名称、空页面/已删除页/正文容器与真实标题回退写失败用例。
- [x] 运行新用例确认缺失规则导致失败。
- [x] 按原版实现名称与详情解析；保留既有 URL/编码边界正确性修复。
- [x] 跑新用例与原有边界回归，审阅后同步两份核心。

## Task 3: 补量采集

Files: helper/mirror `lxds/websearch.py`; helper `tests/test_legacy_web_parity.py`.

- [x] 为实际默认补量、site 查询变体、精准一个变体/模糊六个、每变体最多六页/每页六详情、连续三空页/三空变体/三无新详情、风险停止、原 HTML 中 href 链接、逐条产出写失败用例。
- [x] 依据原版 BaiduSiteSearchCollector 移植逻辑；补量来自知道问答详情，保留流式接口。
- [x] 确认普通 BaiduWebCollector 兼容用途不受不必要改变。
- [x] 新旧补量相关测试及 streaming 测试通过。

## Task 4: 调度、收录与断点

Files: helper/mirror `lxds/collect.py`; helper `tests/test_legacy_collect_parity.py`; helper `protocol.py` only if adapter default mapping requires it.

- [x] 精准：求{kw}百度网盘链接、最多两页/三详情、先摘要、每词至多一条、全部时间、块内洗牌；无提取码不收录，名称提取失败回退关键词，链接/小写名称全局去重。
- [x] 精准恢复：分别统计连续 2 个异常空内容和 15 个无命中；常规探针确认限制后重搜原窗口一次；只补未命中词。
- [x] 模糊：领域扩展、六句式、月/年/全部、具体名称过滤；连续五页无命中换查询、30 页复核、60 页结束站内；保持原版 no_pwd 命中计数语义。
- [x] 补量：直连出口、精准每词一条、无新增连续十词停止；风险时保留结果。
- [x] 从原版核对详情模式、常规问题/开回答节奏、默认设置；对齐状态和断点字段含义，兼容现有恢复数据。
- [x] 先跑失败用例，再实现，再跑完整助手回归。原有与新规范冲突的断言仅在说明具体规则变化后调整，不删除行为覆盖。

## Task 5: 请求池与节奏

Files: helper/mirror `lxds/behavior.py`, `lxds/pool.py`; respective legacy parity tests.

- [x] 核对原版采集实际使用的请求节奏、risk retry、silent probe 返回值、固定出口、stop / resume 决策；按执行行为列差异。
- [x] 对有差异且影响规则的路径先失败测试再修复。
- [x] 不增加新 UI、不读取/输出 Cookie、不向第三方发送消息、不进行转存。

## Task 6: 验证与交付

- [x] 用固定 HTML 样例验证三词精准轨迹、多句式模糊轨迹、未命中/无密码/重复/删帖/异常恢复/停止/断点/补量，每个预期注明原版函数来源。
- [x] 运行助手全套：`.artifacts/helper-bundle-cdp/python.exe -X utf8 -m unittest discover -s tools/collect_helper/tests`（cwd dakazhandian）。
- [x] 运行外层 Python 全套，核对 mirror 哈希。
- [x] 运行 C# 采集相关回归（独立 artifacts path）和构建，保持既有全量 26 项失败范围不混淆。
- [x] 独立代码审阅，解决重要问题，再复跑受影响检查。
- [x] 更新标准 Debug 输出的 Python 核心并验证 UI 文件哈希；若旧助手仍在运行，仅在空闲/用户关闭后更新生效，避免丢输入和采集结果。
- [x] 记录结果、明确未做的真实联网验证及任何保留兼容性差异到 verification 和 HANDOFF。

## 当前状态

2026-09-30 已完成。基线助手 82 项通过；最终助手 177 项、外层 Python 257 项（另 50 子测试）、C# 采集相关 78 项通过。独立审阅通过，原版离线对照 9,556 项无差异。两份核心和运行目录已同步，采集 UI 8 文件哈希未变，标准主 UI 已重开。详见 [交付验证记录](2026-09-30-collector-rule-parity.md)。真实联网结果仍由用户实测，不代表历史 C# 全量失败已解决。

## 独立审阅补充的精确合同

- 协议明确兼容 `true -> auto`、`false -> off`，内部另支持 `auto/off/always`；UI 保持 bool 参数不变。
- 补量两模式均 `extract_resource_name(title) or term`，不套站内模糊的名称过滤。
- 补量 `dup_run >= 3` 仅退出当页详情循环，随后仍应用翻页/三空页判断；原始分享 URL 去重，详情 URL 不去重，知道问题 URL 从全文提取。
- 原版请求最多 30 次；超时 12 秒；请求异常/非200冷却2–6秒重试，验证页处理后继续同URL；成功才记录节奏。搜索阅读3–6秒、详情2.5–6秒。
- 模糊连续两异常页另行复核，每个候选问题最多收录一个链接。所有链接均无密码时 no_pwd 按问题加一；只用于命中/计数复位/进度，不用于目标完成。
- 合格名称/提取码后，先消费分享key，再检查名称小写去重；名称重复被拒的分享仍已消费。
- 固定出口按原版：找到匹配槽则使用（原版不等待pacer）；没有匹配槽回退池。停止仍由请求入口检查。原单号确认为受限后的显式继续可切换代理；不增加UI。
- 常规问题和开回答间隔均8–12，精准每关键词递减、模糊每页递减；不会收录这些辅助请求结果。
- 断点：新保存原版字段别名seen_links；精准恢复已处理done即resolved，跳过旧已处理词；模糊使用带页码key。读取旧字段seen_keys兼容并从已有记录归一化；旧的整查询key视为对应查询已完成。自然完成清除断点；停止/失败保留逐条保存数据。现UI仍默认resume=false。
- 原版分享ID最少8字符、分享ID去重忽略协议、最近提取码匹配等原规则通过独立采集解析API承载，避免影响与本任务无关的转存解析；已修复非法长码/中文说明URL边界仍保留。
