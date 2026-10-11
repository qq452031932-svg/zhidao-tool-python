"""M14 采集调度的离线协议测试。"""

from datetime import date, timedelta
from threading import Event, Timer
import time
from urllib.parse import parse_qs, urlsplit

import pytest

from lxds.collect import CollectWorker
from lxds.checkpoint import load
from lxds.pool import SlotPool


@pytest.fixture(autouse=True)
def isolate_offline_pool_and_optional_browsing(monkeypatch):
    # v1.0.4 startup probes Clash; these tests never contact a real proxy/network.
    monkeypatch.setattr("lxds.pool.probe_clash_detail", lambda **kwargs: (7890, True, ""), raising=False)
    monkeypatch.setattr("lxds.collect.pick_every", lambda bounds: 10000)


def precise_query(word):
    return f"求{word}百度网盘链接"


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
    # Strict legacy detail rejects responses below 2000 chars and share IDs below 8.
    return (f'<div class="best-text">分享 https://pan.baidu.com/s/1fixture{link} 提取码：{pwd}</div>'
            + '<script>' + 'x' * 2100 + '</script>')


class FakePool:
    def __init__(self):
        self.probes = []
        self.slots = [type("Slot", (), {"exit_kind": "direct"})()]

    def start(self):
        pass

    def on_silent_risk(self, keywords, page):
        self.probes.append((keywords, page))
        return False  # A healthy probe means no retry is needed.


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
    words = [f"书籍{i}" for i in range(10)]
    fetcher = FakeFetcher(
        {(precise_query(word), 0): page([(f"{i}1", f"求《{word}》链接", today),
                          (f"{i}2", f"求《{word}》链接", today)]) for i, word in enumerate(words)},
        {f"{i}{j}": detail(f"link{i}{j}") for i in range(10) for j in (1, 2)},
    )
    worker = CollectWorker(keyword=words, mode="precise", fetcher=fetcher,
                           pool=FakePool(), checkpoint_path=str(tmp_path / "cp.json"))
    result = worker.run()
    assert len(result["items"]) == 10
    # Original precise mode shuffles keywords in blocks of ten.
    assert {row["资源名称"] for row in result["items"]} == set(words)
    assert len(fetcher.details_requested) == 10


def test_fuzzy_widens_after_three_recent_rounds_but_stops_at_three_months(tmp_path):
    now = date.today()
    old = [("1", "求《一月书》链接", (now - timedelta(days=12)).isoformat()),
           ("2", "求《上月书》链接", (now - timedelta(days=60)).isoformat()),
           ("3", "求《古书》链接", (now - timedelta(days=900)).isoformat())]
    fetcher = FakeFetcher({("求小说百度网盘链接", 0): page(old)},
                          {"1": detail("one"), "2": detail("two"), "3": detail("three")})
    status = []
    worker = CollectWorker(keyword="小说", count=3, mode="fuzzy", fetcher=fetcher,
                           pool=FakePool(), checkpoint_path=str(tmp_path / "cp.json"),
                           on_status=status.append)
    result = worker.run()
    assert [row['资源名称'] for row in result['items']] == ['一月书', '上月书']
    # The month stage is capped at three rounds; 90 days reuse its normal page.
    assert fetcher.searches.count(("求小说百度网盘链接", 0)) == 1
    assert any("3 轮" in message and "最近三个月" in message for message in status)
    assert not any("自动放宽到「最近一年」" in message for message in status)
    assert not any("全部" in message for message in status)


@pytest.mark.parametrize(("misses", "probes"), [(14, 0), (15, 1)])
def test_fifteen_empty_keywords_call_health_probe(tmp_path, misses, probes):
    pool = FakePool()
    worker = CollectWorker(keyword=[f"空词{i}" for i in range(misses)], fetcher=FakeFetcher({}),
                           pool=pool, checkpoint_path=str(tmp_path / "cp.json"))
    assert worker.run()["items"] == []
    assert len(pool.probes) == probes
    assert worker.stats["no_link"] == misses
    if probes:
        assert len(pool.probes[0][0]) == 15


def test_precise_stops_after_two_empty_pages_without_keyword_health_probe(tmp_path):
    pool = FakePool()
    pages = {}
    for pn in (0, 10, 20, 30, 40):
        next_page = (f'<a class="pager-next" href="/search?word=x&pn={pn + 10}">下一页</a>'
                     if pn < 40 else "")
        pages[(precise_query("空词"), pn)] = "没有找到相关结果" + next_page
    fetcher = FakeFetcher(pages)
    worker = CollectWorker(keyword="空词", fetcher=fetcher, pool=pool,
                           checkpoint_path=str(tmp_path / "cp.json"))
    assert worker.run()["found"] == 0
    assert fetcher.searches == [(precise_query("空词"), 0), (precise_query("空词"), 10)]
    assert pool.probes == []


def test_twenty_real_searches_interleave_common_questions_without_import(tmp_path, monkeypatch):
    monkeypatch.setattr("lxds.collect.pick_every", lambda bounds: 3)
    words = [f"词{i}" for i in range(20)]
    fetcher = FakeFetcher({})
    worker = CollectWorker(keyword=words, fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"))
    result = worker.run()
    queries = {precise_query(word) for word in words}
    common = [word for word, _ in fetcher.searches if word not in queries]
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
    fetcher = FakeFetcher({(precise_query("词"), 0): page([("1", "求《甲书》链接", date.today().isoformat())], next_pn=0)},
                          {"1": '<div class="best-text">没有链接</div>'})
    logs = []
    worker = CollectWorker(keyword="词", fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"), on_log=logs.append)
    worker.run()
    assert fetcher.searches == [(precise_query("词"), 0)]
    assert any("分页 pn=0 未继续前进" in line for line in logs)
    assert worker.stats["no_link"] == 1  # precise records per-keyword misses, not fuzzy idle pages.


def test_stop_from_item_callback_returns_quickly_and_resume_keeps_rows(tmp_path):
    today = date.today().isoformat()
    path = str(tmp_path / "cp.json")
    pages = {(precise_query(word), 0): page([(str(i), f"求《{word}》链接", today)])
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
    assert load(path) == {}  # Natural completion removes the resumable checkpoint.


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
                     "links": [{"link": "https://pan.baidu.com/s/1fixture-new", "pwd": "abcd"}]}]

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
            self.stop_supplement = True  # The collector flag, not log wording, stops later terms.
            on_log("百度网页搜索失败：安全验证")
            return []

    result = CollectWorker(keyword=["甲", "乙"], mode="fuzzy", count=2, time_range="全部",
                           fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement).run()
    assert result["found"] == 1
    assert called == ["甲"]


def test_precise_supplement_does_not_add_second_item_for_found_keyword(tmp_path):
    today = date.today().isoformat()
    fetcher = FakeFetcher({(precise_query("资源词"), 0): page([("1", "求《实际书名》链接", today)])},
                          {"1": detail("one")})
    called = []

    class Supplement:
        def __init__(self, fetcher, stop_event):
            pass

        def search(self, term, on_log):
            called.append(term)
            return [{"title": "其它书", "source_url": "https://example.com",
                     "links": [{"link": "https://pan.baidu.com/s/1fixture-two", "pwd": "abcd"},
                               {"link": "https://pan.baidu.com/s/1fixture-three", "pwd": "abcd"}]}]

    result = CollectWorker(keyword="资源词", fetcher=fetcher, pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement).run()
    assert result["found"] == 1
    assert called == []


def test_supplement_pins_direct_even_during_cooldown_without_falling_back_to_proxy(tmp_path, monkeypatch):
    visited = []
    pool = SlotPool([{"name": "直连", "cookie": "a"}, {"name": "代理", "cookie": "b"}],
                    pause_ask=lambda payload: False, on_log=lambda message: None,
                    stop_event=Event(), on_status=lambda message: None)
    pool.start()
    # v1.0.4 randomizes exit assignment and HumanPacer owns the clock domain.
    for slot in pool.slots:
        slot.pacer.reset()
    next(slot for slot in pool.slots if slot.exit_kind == "direct").pacer.cool_down(0.25)
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
    started = time.monotonic()
    result = worker.run()
    assert time.monotonic() - started < 0.2
    # v1.0.4 pins a matching direct slot immediately; pacing applies to pool selection.
    assert not result["stopped"]
    assert visited == ["direct"]


def test_precise_resume_after_mid_keyword_stop_keeps_one_item(tmp_path):
    today = date.today().isoformat()
    pages = {(precise_query("资源词"), 0): page([
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
                     "links": [{"link": "https://pan.baidu.com/s/1fixture-one", "pwd": "abcd"},
                               {"link": "https://pan.baidu.com/s/1fixture-two", "pwd": "abcd"}]},
                    {"title": "乙书", "source_url": "https://example.com/2",
                     "links": [{"link": "https://pan.baidu.com/s/1fixture-three", "pwd": "abcd"}]}]

    result = CollectWorker(keyword="资源词", fetcher=FakeFetcher({}), pool=FakePool(),
                           checkpoint_path=str(tmp_path / "cp.json"),
                           supplement_factory=Supplement).run()
    assert result["found"] == 1
