"""M07 的离线检索页、风控页及采集补量样本。"""

from threading import Event
from urllib.parse import parse_qs, urlsplit

import pytest

from lxds.websearch import (
    BaiduSiteSearchCollector,
    BaiduWebCollector,
    BaiduWebError,
    robust_search_snippets,
    site_queries,
)


RESULT = '''<html><h3><a href="https://zhidao.baidu.com/question/123.html">《斗破苍穹》资源</a></h3>
<div class="c-abstract">分享链接：https://pan.baidu.com/s/1AbCd 提取码：ab12</div></html>'''
RISK = "<html><body>请完成百度安全验证</body></html>"


class FakeFetcher:
    def __init__(self, search_html=RESULT, detail_html=""):
        self.search_html = search_html
        self.detail_html = detail_html
        self.calls = []

    def get(self, url, referer=None, purpose="search"):
        self.calls.append((url, referer, purpose))
        if "zhidao.baidu.com/question/" in url:
            return self.detail_html, None
        return self.search_html, None


def test_site_queries_are_distinct_and_cover_zhidao_and_pan():
    queries = site_queries(" 斗破苍穹 ")
    assert len(queries) == len(set(queries))
    assert all("斗破苍穹" in query for query in queries)
    assert any(query.startswith("site:zhidao.baidu.com ") for query in queries)
    assert any(query.startswith("site:pan.baidu.com ") for query in queries)
    assert site_queries("  ") == []


def test_short_safety_page_raises_baidu_web_error():
    collector = BaiduWebCollector(FakeFetcher(RISK), Event())
    with pytest.raises(BaiduWebError, match="安全验证"):
        collector._search_page("https://www.baidu.com/s?wd=x")


def test_web_collector_extracts_title_link_and_password():
    fetcher = FakeFetcher()
    records = BaiduWebCollector(fetcher, Event()).search("斗破苍穹", None)
    assert records == [{
        "title": "《斗破苍穹》资源",
        "source_url": "https://zhidao.baidu.com/question/123.html",
        "links": [{"link": "https://pan.baidu.com/s/1AbCd?pwd=ab12", "pwd": "ab12"}],
    }]
    assert all(purpose == "search" for _, _, purpose in fetcher.calls)


def test_web_collector_returns_empty_on_risk_and_logs():
    logs = []
    records = BaiduWebCollector(FakeFetcher(RISK), Event()).search("资源", logs.append)
    assert records == []
    assert any("安全验证" in log for log in logs)


def test_site_collector_follows_detail_and_deduplicates():
    search_html = '''<h3><a href="https://zhidao.baidu.com/question/123.html">问题 A</a></h3>
    <h3><a href="https://zhidao.baidu.com/question/123.html">问题 A 重复</a></h3>'''
    detail = "<title>斗破苍穹网盘分享</title>链接：https://pan.baidu.com/s/1AbCd 提取码：xy34"
    fetcher = FakeFetcher(search_html, detail)
    collector = BaiduSiteSearchCollector(fetcher, Event(), max_variants=1)
    records = collector.search("斗破苍穹", None)
    assert records == [{
        "title": "斗破苍穹网盘分享",
        "source_url": "https://zhidao.baidu.com/question/123.html",
        "links": [{"link": "https://pan.baidu.com/s/1AbCd?pwd=xy34", "pwd": "xy34"}],
    }]
    assert sum("zhidao.baidu.com/question/" in url for url, _, _ in fetcher.calls) == 1
    assert parse_qs(urlsplit(fetcher.calls[0][0]).query)["wd"][0].startswith("site:zhidao.baidu.com")


def test_site_collector_stops_on_risk_and_preserves_previous_records():
    class RiskAfterFirst(FakeFetcher):
        def get(self, url, referer=None, purpose="search"):
            if "www.baidu.com" in url and len([x for x in self.calls if "www.baidu.com" in x[0]]) >= 1:
                self.calls.append((url, referer, purpose))
                return RISK, None
            return super().get(url, referer=referer, purpose=purpose)

    fetcher = RiskAfterFirst(
        '<h3><a href="https://zhidao.baidu.com/question/123.html">问题</a></h3>',
        "<title>已采结果</title>https://pan.baidu.com/s/1AbCd",
    )
    collector = BaiduSiteSearchCollector(fetcher, Event(), max_variants=2)
    records = collector.search("测试", None)
    assert len(records) == 1
    assert collector.stop_supplement is True


def test_stop_event_prevents_requests():
    stop = Event()
    stop.set()
    fetcher = FakeFetcher()
    assert BaiduWebCollector(fetcher, stop).search("x", None) == []
    assert BaiduSiteSearchCollector(fetcher, stop).search("x", None) == []
    assert fetcher.calls == []


def test_robust_snippets_extracts_title_and_summary_with_limit(monkeypatch):
    class Response:
        status_code = 200
        text = '<h3><a href="https://example.com">资源标题</a></h3><div class="c-abstract">这是详细的资源简介</div>'

    class Session:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def get(self, url, timeout):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("lxds.websearch.requests.Session", Session)
    summary = robust_search_snippets("资源", max_chars=25)
    assert "资源标题" in summary
    assert "资源简介" in summary
    assert len(summary) <= 25


def test_robust_snippets_returns_empty_on_risk(monkeypatch):
    class Response:
        status_code = 200
        text = RISK

    class Session:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def get(self, url, timeout):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("lxds.websearch.requests.Session", Session)
    assert robust_search_snippets("资源", max_chars=100) == ""
