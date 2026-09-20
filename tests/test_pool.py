"""M13 双账号和单账号风控状态机。"""

import threading
import time

import pytest

from lxds.pool import CollectCancelled, PinnedExitFetcher, SlotPool, is_risk_html


def _pool(count=2, pause_result=True):
    paused = []
    pool = SlotPool(
        [{"name": f"账号{i+1}", "cookie": f"cookie{i+1}"} for i in range(count)],
        pause_ask=lambda payload: paused.append(payload) or pause_result,
        on_log=lambda message: None,
        stop_event=threading.Event(),
        on_status=lambda message: None,
    )
    pool.start()
    return pool, paused


def test_short_security_page_is_risk_but_normal_result_is_not():
    assert is_risk_html("<html>请完成安全验证</html>")
    assert is_risk_html("<html>" + "x" * 5000 + "wappass</html>")
    assert not is_risk_html("<html>正常结果</html>")


def test_two_accounts_silent_risk_before_probe(monkeypatch):
    pool, paused = _pool()
    first, second = pool.slots
    monkeypatch.setattr(pool, "probe_slot", lambda slot: pytest.fail("未到三次，不应探针"))
    assert pool.on_risk(first, "安全验证")
    assert pool.on_risk(first, "安全验证")
    assert first.risk_hits == 2
    assert pool.acquire() in (first, second)
    assert paused == []


def test_three_hits_disable_one_account_but_other_continues(monkeypatch):
    pool, paused = _pool()
    first, second = pool.slots
    monkeypatch.setattr(pool, "probe_slot", lambda slot: False)
    for _ in range(3):
        assert pool.on_risk(first, "安全验证")
    assert first.risk_confirmed
    assert pool.acquire() is second
    assert paused == []


def test_all_accounts_probe_abnormal_prompts_once(monkeypatch):
    pool, paused = _pool()
    monkeypatch.setattr(pool, "probe_slot", lambda slot: False)
    for slot in pool.slots:
        for _ in range(3):
            pool.on_risk(slot, "安全验证")
    assert len(paused) == 1


def test_single_account_three_silent_cooldowns_before_prompt(monkeypatch):
    pool, paused = _pool(count=1)
    durations = []
    monkeypatch.setattr(pool, "probe_slot", lambda slot: False)
    monkeypatch.setattr(pool, "_interruptible_wait", lambda seconds: durations.append(seconds))
    for _ in range(3):
        pool.on_risk(pool.slots[0], "安全验证")
    assert len(durations) == 3
    assert 60 <= durations[0] <= 90
    assert 90 <= durations[1] <= 150
    assert 120 <= durations[2] <= 180
    assert len(paused) == 1


def test_cooling_wait_exits_quickly_when_stopped():
    pool, _ = _pool(count=1)
    pool.stop_event.set()
    start = time.monotonic()
    with pytest.raises(CollectCancelled):
        pool._interruptible_wait(180)
    assert time.monotonic() - start < 1


def test_pinned_fetcher_falls_back_when_direct_slot_missing(monkeypatch):
    pool, _ = _pool(count=1)
    pool.slots[0].exit_kind = "proxy"
    monkeypatch.setattr(pool, "fetch", lambda slot, url, **kwargs: "正常页面")
    fetcher = PinnedExitFetcher(pool, exit_kind="direct")
    html, slot = fetcher.get("https://example.com/")
    assert html == "正常页面"
    assert slot is pool.slots[0]
