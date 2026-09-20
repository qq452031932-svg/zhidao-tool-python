"""M14 采集调度的离线协议测试。"""

from datetime import date, timedelta
from threading import Event, Timer
import time
from urllib.parse import parse_qs, urlsplit

import pytest

from lxds.collect import CollectWorker
from lxds.checkpoint import load
from lxds.pool import SlotPool


def page(items=(), next_pn=None):
    chunks = []
    for qid, title, when in items:
        chunks.append(
            f'<a href="https://zhidao.baidu.com/question/{qid}.html?fr=search">{title}</a>'
            f'<span>{when}</span>'
        )
    if next_pn is not None:
        chunks.append(f'<a class="pager-next" href="/search?word=x&pn={next_pn}">下一页</a>')
    return "".join(chunks) if chunks else "没有找到相关结果"


def detail(link, pwd="abcd"):
    return f'<div class="best-text">分享 https://pan.baidu.com/s/{link} 提取码：{pwd}</div>'


class FakePool:
    def __init__(self):
        self.probes = []
        self.slots = [type("Slot", (), {"exit_kind": "direct"})()]

    def start(self):
        pass

    def on_silent_risk(self, keywords, page):
        self.probes.append((keywords, page))
        return True


class FakeFetcher:
    def __init__(self, pages, details=None):
        self.pages = pages
        self.details = details or {}
        self.searches = []
        self.details_requested = []

    def get(self, url, **kwargs):
        if "/question/" in url:
            self.details_requested.append(url)
            qid = url.split("/question/", 1)[1].split(".", 1)[0]
            return self.details.get(qid, ""), None
        query = parse_qs(urlsplit(url).query)
        word = query["word"][0]
        pn = int(query["pn"][0])
        self.searches.append((word, pn))
        return self.pages.get((word, pn), page()), None


def test_precise_ten_keywords_emit_at_most_one_each(tmp_path):
    today = date.today().isoformat()
    words = [f"书{i}" for i in range(10)]
    fetcher = FakeFetcher(
        {(word, 0): page([(f"{i}1", f"求《{word}》链接", today),
                          (f"{i}2", f"求《{word}》链接", today)]) for i, word in enumerate(words)},
        {f"{i}{j}": detail(f"link{i}{j}") for i in range(10) for j in (1, 2)},
    )
    worker = CollectWorker(keyword=words, mode="precise", fetcher=fetcher,
                           pool=FakePool(), checkpoint_path=str(tmp_path / "cp.json"))
    result = worker.run()
    assert len(result["items"]) == 10
    assert [row["资源名称"] for row in result["items"]] == words
    assert len(fetcher.details_requested) == 10


def test_fuzzy_widens_one_month_one_year_all_until_target(tmp_path):
    now = date.today()
    old = [("1", "求《一月书》链接", (now - timedelta(days=12)).isoformat()),
           ("2", "求《一年书》链接", (now - timedelta(days=120)).isoformat()),
           ("3", "求《古书》链接", (now - timedelta(days=900)).isoformat())]
    fetcher = FakeFetcher({("求小说百度网盘链接", 0): page(old)},
                          {"1": detail("one"), "2": detail("two"), "3": detail("three")})
    status = []
    worker = CollectWorker(keyword="小说", count=3, mode="fuzzy", fetcher=fetcher,
                           pool=FakePool(), checkpoint_path=str(tmp_path / "cp.json"),
                           on_status=status.append)
    result = worker.run()
    assert len(result["items"]) == 3
    assert fetcher.searches.count(("求小说百度网盘链接", 0)) == 3
    assert any("一年" in message for message in status)
    assert any("全部" in message for message in status)


def test_five_empty_keywords_call_health_probe(tmp_path):
    pool = FakePool()
    worker = CollectWorker(keyword=[f"空{i}" for i in range(5)], fetcher=FakeFetcher({}),
                           pool=pool, checkpoint_path=str(tmp_path / "cp.json"))
    assert worker.run()["items"] == []
    assert len(pool.probes) == 1


def test_five_empty_pages_of_one_query_call_health_probe(tmp_path):
    pool = FakePool()
    pages = {}
    for pn in (0, 10, 20, 30, 40):
        next_page = (f'<a class="pager-next" href="/search?word=x&pn={pn + 10}">下一页</a>'
                     if pn < 40 else "")
        pages[("空词", pn)] = "没有找到相关结果" + next_page
    worker = CollectWorker(keyword="空词", fetcher=FakeFetcher(pages), pool=pool,
                           checkpoint_path=str(tmp_path / "cp.json"))
    assert worker.run()["found"] == 0
    assert len(pool.probes) == 1


def test_twenty_real_searches_interleave_common_questions_without_import(tmp_path, monkeypatch):
    monkeypatch.setattr("lxds.collect.pick_every", lambda bounds: 3)
    words = [f"词{i}" for i in range(20)]
    fetcher = FakeFetcher({})
    worker = CollectWorker(keyword=words, fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"))
    result = worker.run()
    common = [word for word, _ in fetcher.searches if word not in words]
    assert len(common) == 6
    assert not result["items"]


def test_duplicate_link_and_name_logged_separately(tmp_path):
    today = date.today().isoformat()
    fetcher = FakeFetcher({("求词百度网盘链接", 0): page([
        ("1", "求《甲书》链接", today), ("2", "求《乙书》链接", today),
        ("3", "求《甲书》链接", today), ("4", "求《丁书》链接", today),
    ])}, {"1": detail("same", "abcd"), "2": detail("same", "wxyz"),
         "3": detail("other"), "4": detail("four")})
    logs = []
    worker = CollectWorker(keyword="词", mode="fuzzy", count=4, fetcher=fetcher,
                           pool=FakePool(), checkpoint_path=str(tmp_path / "cp.json"), on_log=logs.append)
    result = worker.run()
    assert len(result["items"]) == 2
    assert any("跳过重复链接" in line for line in logs)
    assert any("跳过重复名称" in line for line in logs)


def test_nonadvancing_pn_ends_query(tmp_path):
    fetcher = FakeFetcher({("词", 0): page([("1", "求《甲书》链接", date.today().isoformat())], next_pn=0)},
                          {"1": '<div class="best-text">没有链接</div>'})
    logs = []
    worker = CollectWorker(keyword="词", fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"), on_log=logs.append)
    worker.run()
    assert fetcher.searches == [("词", 0)]
    assert any("分页 pn=0 未继续前进" in line for line in logs)
    assert worker.stats["idle_pages"] == 1


def test_stop_from_item_callback_returns_quickly_and_resume_keeps_rows(tmp_path):
    today = date.today().isoformat()
    path = str(tmp_path / "cp.json")
    pages = {(word, 0): page([(str(i), f"求《{word}》链接", today)])
             for i, word in enumerate(("甲书", "乙书"), 1)}
    details = {"1": detail("one"), "2": detail("two")}
    first_fetcher = FakeFetcher(pages, details)
    first = CollectWorker(keyword=["甲书", "乙书"], fetcher=first_fetcher,
                          pool=FakePool(), checkpoint_path=path)
    first.on_item = lambda row: first.stop()
    started = time.monotonic()
    result = first.run()
    assert time.monotonic() - started < 1
    assert result["stopped"] and result["found"] == 1
    assert load(path)["found"] == 1
    resumed = CollectWorker(keyword=["甲书", "乙书"], fetcher=FakeFetcher(pages, details),
                            pool=FakePool(), checkpoint_path=path, resume=True).run()
    assert resumed["found"] == 2
    assert {row["资源名称"] for row in resumed["items"]} == {"甲书", "乙书"}
    assert load(path)["found"] == 2


def test_supplement_uses_direct_slot_even_with_proxy_account(tmp_path, monkeypatch):
    visited = []
    pool = SlotPool([{"name": "直连", "cookie": "a"}, {"name": "代理", "cookie": "b"}],
                    pause_ask=lambda payload: False, on_log=lambda message: None,
                    stop_event=Event(), on_status=lambda message: None)
    pool.start()
    monkeypatch.setattr(pool, "fetch", lambda slot, url, **kwargs: visited.append(slot.exit_kind) or "没有找到相关结果")

    class Supplement:
        def __init__(self, fetcher, stop_event):
            self.fetcher = fetcher

        def search(self, term, on_log):
            self.fetcher.get("https://www.baidu.com/s?wd=x")
            return [{"title": term, "source_url": "https://example.com",
                     "links": [{"link": "https://pan.baidu.com/s/new", "pwd": "abcd"}]}]

    worker = CollectWorker(keyword="甲书", fetcher=FakeFetcher({}), pool=pool,
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement)
    result = worker.run()
    assert visited == ["direct"]
    assert result["found"] == 1


def test_supplement_risk_stops_without_losing_site_results(tmp_path):
    today = date.today().isoformat()
    fetcher = FakeFetcher({("求甲百度网盘链接", 0): page([("1", "求《甲书》链接", today)])},
                          {"1": detail("one")})
    called = []

    class Supplement:
        def __init__(self, fetcher, stop_event):
            pass

        def search(self, term, on_log):
            called.append(term)
            on_log("百度网页搜索失败：安全验证")
            return []

    result = CollectWorker(keyword=["甲", "乙"], mode="fuzzy", count=2,
                           fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement).run()
    assert result["found"] == 1
    assert called == ["甲"]


def test_precise_supplement_does_not_add_second_item_for_found_keyword(tmp_path):
    today = date.today().isoformat()
    fetcher = FakeFetcher({("资源词", 0): page([("1", "求《实际书名》链接", today)])},
                          {"1": detail("one")})
    called = []

    class Supplement:
        def __init__(self, fetcher, stop_event):
            pass

        def search(self, term, on_log):
            called.append(term)
            return [{"title": "其它书", "source_url": "https://example.com",
                     "links": [{"link": "https://pan.baidu.com/s/two", "pwd": "abcd"},
                               {"link": "https://pan.baidu.com/s/three", "pwd": "abcd"}]}]

    result = CollectWorker(keyword="资源词", fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement).run()
    assert result["found"] == 1
    assert called == []


def test_supplement_waits_for_direct_without_falling_back_to_proxy(tmp_path, monkeypatch):
    visited = []
    pool = SlotPool([{"name": "直连", "cookie": "a"}, {"name": "代理", "cookie": "b"}],
                    pause_ask=lambda payload: False, on_log=lambda message: None,
                    stop_event=Event(), on_status=lambda message: None)
    pool.start()
    pool.slots[0].unavailable_until = time.monotonic() + 0.25
    monkeypatch.setattr(pool, "fetch", lambda slot, url, **kwargs: visited.append(slot.exit_kind) or "没有找到相关结果")

    class Supplement:
        def __init__(self, fetcher, stop_event):
            self.fetcher = fetcher

        def search(self, term, on_log):
            self.fetcher.get("https://www.baidu.com/s?wd=x")
            return []

    worker = CollectWorker(keyword="甲书", fetcher=FakeFetcher({}), pool=pool,
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement)
    timer = Timer(0.05, worker.stop)
    timer.start()
    started = time.monotonic()
    result = worker.run()
    timer.join()
    assert time.monotonic() - started < 0.2
    assert result["stopped"]
    assert visited == []


def test_precise_resume_after_mid_keyword_stop_keeps_one_item(tmp_path):
    today = date.today().isoformat()
    pages = {("资源词", 0): page([
        ("1", "求《甲书》链接", today), ("2", "求《乙书》链接", today),
    ])}
    details = {"1": detail("one"), "2": detail("two")}
    checkpoint = str(tmp_path / "cp.json")
    first = CollectWorker(keyword="资源词", fetcher=FakeFetcher(pages, details),
                          pool=FakePool(), checkpoint_path=checkpoint)
    first.on_item = lambda row: first.stop()
    assert first.run()["found"] == 1
    resumed_fetcher = FakeFetcher(pages, details)
    resumed = CollectWorker(keyword="资源词", fetcher=resumed_fetcher,
                            pool=FakePool(), checkpoint_path=checkpoint, resume=True).run()
    assert resumed["found"] == 1
    assert resumed_fetcher.details_requested == []


def test_precise_supplement_stops_after_first_link_per_keyword(tmp_path):
    class Supplement:
        def __init__(self, fetcher, stop_event):
            pass

        def search(self, term, on_log):
            return [{"title": "甲书", "source_url": "https://example.com",
                     "links": [{"link": "https://pan.baidu.com/s/one", "pwd": "abcd"},
                               {"link": "https://pan.baidu.com/s/two", "pwd": "abcd"}]},
                    {"title": "乙书", "source_url": "https://example.com/2",
                     "links": [{"link": "https://pan.baidu.com/s/three", "pwd": "abcd"}]}]

    result = CollectWorker(keyword="资源词", fetcher=FakeFetcher({}), pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement).run()
    assert result["found"] == 1
