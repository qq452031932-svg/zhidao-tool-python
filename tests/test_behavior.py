"""M12 指纹、关键词打乱与账号请求节奏。"""

from lxds.behavior import HumanPacer, pick_common_question, pick_every, pick_profile, shuffle_blocks


def test_eight_profiles_have_matching_browser_headers(monkeypatch):
    seen = []
    for index in range(8):
        monkeypatch.setattr("lxds.behavior.random.choice", lambda values, index=index: values[index])
        profile = pick_profile()
        seen.append(profile)
        if "Firefox" in profile["ua"]:
            assert profile["sec_ch_ua"] == ""
            assert profile["mobile"] == ""
            assert profile["platform"] == ""
        elif "Edg/" in profile["ua"]:
            assert "Microsoft Edge" in profile["sec_ch_ua"]
        else:
            assert "Google Chrome" in profile["sec_ch_ua"]
        if "Macintosh" in profile["ua"]:
            assert profile["platform"] == '"macOS"'
        elif "Firefox" not in profile["ua"]:
            assert profile["platform"] == '"Windows"'
    assert len({item["ua"] for item in seen}) == 8


def test_human_pacer_keeps_six_to_ten_second_gap_and_cooldown(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("lxds.behavior.time.time", lambda: now[0])
    pacer = HumanPacer(gap_range=(6, 10))
    pacer.note_request(0.5)
    assert 6 <= pacer.wait_time(now[0]) <= 10
    pacer.cool_down(20)
    assert pacer.wait_time(now[0]) >= 20
    now[0] += 21
    assert pacer.wait_time(now[0]) == 0


def test_break_ranges_use_original_defaults_and_allow_override(monkeypatch):
    monkeypatch.setattr("lxds.behavior.time.time", lambda: 100.0)
    original = HumanPacer()
    assert original.break_after_range == (8, 12)
    assert original.break_range == (12.0, 25.0)
    pacer = HumanPacer(gap_range=(6, 10), break_after_range=(1, 1), break_range=(30, 30))
    should_break, duration = pacer.note_request(0)
    assert should_break and duration == 30
    assert pacer.wait_time(100.0) >= 30


def test_shuffle_blocks_changes_only_within_each_block(monkeypatch):
    monkeypatch.setattr("lxds.behavior.random.shuffle", lambda items: items.reverse())
    result = shuffle_blocks(list(range(20)), 5)
    assert result == [4, 3, 2, 1, 0, 9, 8, 7, 6, 5, 14, 13, 12, 11, 10, 19, 18, 17, 16, 15]


def test_common_questions_rotate_and_pick_every_stays_in_range():
    used = set()
    first = pick_common_question(used)
    assert used == set()
    # 原版由调用方记录已使用问题，选择函数不添加或清空 used。
    used.add(first)
    second = pick_common_question(used)
    assert first != second
    assert used == {first}
    used.add(second)
    for _ in range(20):
        assert 3 <= pick_every((3, 6)) <= 6
