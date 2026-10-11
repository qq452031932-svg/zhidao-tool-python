"""M13 双账号和单账号风控状态机。"""

import threading
import time

import pytest

from lxds.pool import CollectCancelled, PinnedExitFetcher, SlotPool, is_risk_html


@pytest.fixture(autouse=True)
def offline_pool(monkeypatch):
    """启动探测全部离线；固定时钟并禁止意外真实 HTTP 请求。"""
    monkeypatch.setattr("lxds.pool.probe_clash_detail", lambda **kwargs: (7890, True, "offline"))
    monkeypatch.setattr("lxds.pool.time.time", lambda: 100.0)
    monkeypatch.setattr("lxds.pool.random.shuffle", lambda slots: None)
    monkeypatch.setattr("lxds.pool.requests.Session.get",
                        lambda *args, **kwargs: pytest.fail("单元测试不允许真实 HTTP 请求"))


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
    # 这些状态机测试从所有槽都就绪开始；启动错峰由 parity 测试单独覆盖。
    for slot in pool.slots:
        slot.pacer.reset()
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
    monkeypatch.setattr(pool, "_interruptible_wait", lambda seconds: pytest.fail("风控回调仅安排冷却，不在内部等待"))
    monkeypatch.setattr(pool.slots[0].pacer, "cool_down", durations.append)
    for number in range(1, 4):
        assert pool.on_silent_risk(["资源"], page=True)
        assert pool.silent_rounds == number
        assert len(durations) == number
        assert paused == []
    assert len(durations) == 3
    assert 60 <= durations[0] <= 90
    assert 90 <= durations[1] <= 150
    assert 120 <= durations[2] <= 180
    assert pool.on_silent_risk(["资源"], page=True)
    assert len(paused) == 1
    assert paused[0]["kind"] == "enable_proxy"
    assert pool.slots[0].exit_kind == "proxy"


def test_single_account_three_explicit_hits_schedule_only_one_silent_round(monkeypatch):
    pool, paused = _pool(count=1)
    monkeypatch.setattr(pool, "probe_slot", lambda slot: False)
    monkeypatch.setattr(pool, "_interruptible_wait", lambda seconds: pytest.fail("不应内联等待"))
    for _ in range(3):
        assert pool.on_risk(pool.slots[0], "安全验证")
    assert pool.silent_rounds == 1
    assert 60 <= pool.slots[0].pacer.wait_time() <= 90
    assert paused == []


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


def test_pinned_fetcher_uses_matching_exit_even_while_cooling(monkeypatch):
    pool, _ = _pool(count=1)
    direct = pool.slots[0]
    direct.pacer.cool_down(180)
    monkeypatch.setattr(pool, "acquire", lambda: pytest.fail("固定出口不能退回普通节奏调度"))
    monkeypatch.setattr(pool, "fetch", lambda slot, url, **kwargs: "正常页面")
    html, selected = PinnedExitFetcher(pool, exit_kind="direct").get("https://example.com/")
    assert (html, selected) == ("正常页面", direct)


def test_pinned_fetcher_checks_stop_before_matching_exit_request(monkeypatch):
    pool, _ = _pool(count=1)
    pool.stop_event.set()
    monkeypatch.setattr(pool, "fetch", lambda *args, **kwargs: pytest.fail("停止后不应请求"))
    with pytest.raises(CollectCancelled):
        PinnedExitFetcher(pool, exit_kind="direct").get("https://example.com/")
