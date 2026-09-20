import json
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest

from lxds import miner


@pytest.mark.parametrize("category", miner.CATEGORIES)
def test_each_category_runs_with_mock_sources(monkeypatch, tmp_path, category):
    monkeypatch.setitem(miner.SOURCES, category, (("test", lambda s, n, e, l: ["作品甲", "作品乙"], False),))
    monkeypatch.setattr(miner, "_search_supplement", lambda *args: [])
    result = miner.collect_hot_names(category, 2, str(tmp_path / "words.txt"), Event(), None,
                                     add_prefix=False, history_path=str(tmp_path / "history.json"), shuffle=False)
    assert result["count"] == 2
    assert (tmp_path / "words.txt").read_text(encoding="utf-8").splitlines() == ["作品甲", "作品乙"]


def test_stop_keeps_partial_file(monkeypatch, tmp_path):
    stop = Event()
    def first_source(session, need, event, log):
        stop.set()
        return ["作品甲"]
    monkeypatch.setitem(miner.SOURCES, "小说", (("first", first_source, False), ("second", lambda *a: ["作品乙"], False)))
    monkeypatch.setattr(miner, "_search_supplement", lambda *args: [])
    result = miner.collect_hot_names("小说", 5, str(tmp_path / "words.txt"), stop, None,
                                     add_prefix=False, history_path=str(tmp_path / "history.json"))
    assert result["stopped"] is True
    assert result["count"] == 1
    assert (tmp_path / "words.txt").read_text(encoding="utf-8").strip() == "作品甲"


def test_history_deduplicates_second_run(monkeypatch, tmp_path):
    monkeypatch.setitem(miner.SOURCES, "小说", (("test", lambda *a: ["鬼灭之刃 第三季", "新作品"], False),))
    monkeypatch.setattr(miner, "_search_supplement", lambda *args: [])
    hist = str(tmp_path / "history.json")
    first = miner.collect_hot_names("小说", 2, str(tmp_path / "first.txt"), Event(), None,
                                    add_prefix=False, history_path=hist, shuffle=False)
    second = miner.collect_hot_names("小说", 2, str(tmp_path / "second.txt"), Event(), None,
                                     add_prefix=False, history_path=hist, shuffle=False)
    assert first["count"] == 2
    assert second["count"] == 0


def test_prune_history_removes_old_and_caps_size(tmp_path):
    path = tmp_path / "history.json"
    recent = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    path.write_text(json.dumps({"version": 1, "updated": recent, "keep_days": 7,
                                "entries": {"old": old, "recent": recent}}), encoding="utf-8")
    miner.prune_history(str(path))
    assert json.loads(path.read_text(encoding="utf-8"))["entries"] == {"recent": recent}


def test_fresh_quota_is_thirty_percent():
    quotas = miner._plan_quotas("小说", 100)
    fresh = sum(quota for name, quota in quotas.items() if name in miner._fresh_names("小说"))
    assert 27 <= fresh <= 33
    assert sum(quotas.values()) == 100


def test_bad_source_does_not_abort_and_search_supplements(monkeypatch, tmp_path):
    def broken(*args):
        raise RuntimeError("down")
    monkeypatch.setitem(miner.SOURCES, "小说", (("broken", broken, False),))
    monkeypatch.setattr(miner, "_search_supplement", lambda *args: ["《新书甲》", "2026年热门小说排行榜", "《新书乙》"])
    result = miner.collect_hot_names("小说", 2, str(tmp_path / "words.txt"), Event(), None,
                                     add_prefix=False, history_path=str(tmp_path / "history.json"), shuffle=False)
    assert result["count"] == 2
    assert (tmp_path / "words.txt").read_text(encoding="utf-8").splitlines() == ["新书甲", "新书乙"]


def test_prefix_and_versioned_history_use_category(monkeypatch, tmp_path):
    monkeypatch.setitem(miner.SOURCES, "小说", (("test", lambda *a: ["共同作品"], False),))
    monkeypatch.setitem(miner.SOURCES, "电影", (("test", lambda *a: ["共同作品"], False),))
    monkeypatch.setattr(miner, "_search_supplement", lambda *args: [])
    hist = str(tmp_path / "history.json")
    miner.collect_hot_names("小说", 1, str(tmp_path / "novel.txt"), Event(), None,
                            history_path=hist, shuffle=False)
    movie = miner.collect_hot_names("电影", 1, str(tmp_path / "movie.txt"), Event(), None,
                                    history_path=hist, shuffle=False)
    assert movie["count"] == 1
    assert (tmp_path / "novel.txt").read_text(encoding="utf-8").strip() == "小说共同作品"
    assert (tmp_path / "movie.txt").read_text(encoding="utf-8").strip() == "电影共同作品"
    payload = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert set(payload["entries"]) == {"小说|共同作品", "电影|共同作品"}
