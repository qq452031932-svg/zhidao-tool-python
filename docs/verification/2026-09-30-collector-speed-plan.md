# 采集保守提速实施计划

> Use test-driven-development and independent requesting-code-review. Preserve prior uncommitted work; no UI changes, no live collection or credential access.

**Goal:** 用户已选择保守提速：在单任务内复用正常页面，到目标立即结束辅助浏览；维持模糊模式全局目标、关键词/句式/日期阶段顺序、解析筛选、无密码计数、请求节奏及重试。

**Architecture:** 新增有界内存页面缓存及 fetcher 适配器，供 worker 主采集和固定出口补量共享；以知道问题 ID 统一详情页 URL，仅缓存验证过的正常页面。健康探针继续直接走 pool，异常响应不缓存；每个 run 开始/结束清空缓存，断点和日志不包含缓存正文、Cookie。已有部署下复制 Python 模块即可，无需改变 WPF。

**Tech Stack:** Python 3.14 / unittest / existing JSON helper, WPF unchanged.

## 已批准的行为与边界

- 5 词/目标10表示全局最多10条，不按词均分，也没有全局相关度排名；时间阶段内按词、句式、页码处理。此次不改变该策略。
- 缓存限当前 worker 的一次 run，LRU 最多128页、总计4百万字符；超大页面不缓存。不落盘、不跨任务或账号会话共享。下一次任务仍获取新页面。
- 知道搜索页有正常候选才缓存；合法无结果、验证、异常页不缓存。知道详情仅正文容器解析成功(ok)或有原版可提取分享链接的正常 fallback 才缓存，dead/empty不缓存。百度站点搜索页有知道问题 URL且无风险标记才缓存。
- 精确 URL保留搜索词和页码区分；详情按知道问题ID统一 .html/来源参数等链接形式。未识别 URL不缓存。缓存只复用响应，不跳过解析、日期和去重判断。
- 健康探针不经缓存；pool 的显式 on_risk / on_silent_risk 入口均提升缓存代际。适配器每次命中前、底层请求返回后检查并失效旧缓存，覆盖fetcher内部风险恢复路径。
- 缓存分类依据严格 URL而不是purpose；站点补量的详情也用purpose=search，首次网络参数原样转发。对照同时覆盖结果顺序、no_pwd/filtered_date/no_link、done_queries、风险调用和同worker再次运行清理。
- 请求依然串行、间隔和冷却保持原样；达到目标后不再发起常规问题/随机打开回答的网络请求。
- 验证的是固定响应下结果和顺序一致及减少请求数；活网页单任务期间的变化可能到下一任务才看到，不承诺线上固定倍率。

## Tasks

- [x] 备份本轮助手、外层核心与8个UI文件哈希：`.recovery/20260930-collector-speed-baseline`。
- [x] 新增 `tools/collect_helper/tests/test_collect_page_cache.py`：正常页复用、URL边界、正常空/异常/风险不缓存、停止/失败不缓存、容量淘汰、跨worker隔离和风险失效，先红后绿。
- [x] 新增 `tools/collect_helper/lxds/page_cache.py`，接入 `collect.py` / `collect_engine.py` 主流程与补量；最小 pool 风险代际适配如有必要先加测试。
- [x] 增加端到端离线场景：跨三日期阶段复用搜索页、跨句式/补量复用详情，5词目标10验证前词可占全部、达标不再辅助浏览；比较缓存开关的输出与请求数。
- [x] 定向及全套助手测试；仅迁移与“有意减少重复请求”冲突的旧断言，保留原筛选/统计/停止覆盖。外层核心同步后跑外层pytest。
- [x] 独立规格/代码审阅；修复重要问题。C#采集78项回归；部署实际解释器握手与源码/mirror/output哈希校验。
- [x] 保留用户现有窗口和采集结果，更新运行目录；确认采集空闲后仅退出旧助手让下一次开始加载新代码（无法确认时保持任务，不强行终止）。
- [x] 更新 HANDOFF 和验证记录，注明减少请求数的离线场景及线上提速需要实测。
