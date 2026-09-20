# M07 百度网页搜索实现记录

依据：`PRD-拉新流水线重建-v1.md` 的 M07。只编辑本工作区内的 M07 文件。

1. 离线样本先覆盖安全验证页、站内检索变体、标题与摘要、两个 Collector 的提取与中途停机。
2. `BaiduWebCollector` 只处理搜索结果块里已有的网盘链接；`BaiduSiteSearchCollector` 搜索知道问题，再请求详情提取链接。两者接收调用方注入的 `fetcher`，由 M14 传入固定直连出口。
3. 风控页按“短页面 + 安全验证关键词”识别。站内补量遇风控时设置 `stop_supplement` 并返回先前结果。
4. `robust_search_snippets` 自建不读系统代理的会话，依次尝试百度、360、搜狗的原名与“网盘”查询；没有可用结果时返回空串。
5. 验证命令：`py -3.12 -m pytest tests/test_websearch.py -q` 与 `py -3.12 demo/websearch_demo.py`。在线页面结构、搜索引擎风控规则和直连出口未在离线测试中验证。
