"""M11 搜索页、详情页、链接和名称解析的离线样本。"""

from datetime import date, timedelta

import pytest

from lxds.zhidao_parse import (
    classify_search_html,
    clean_title_for_name,
    extract_pan_entries,
    extract_resource_name,
    has_concrete_name,
    link_key,
    normalize_pan_url,
    parse_detail_page,
    parse_search_page,
    strip_spam_letters,
    within_range,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("凡I人I修I仙", "凡人修仙"),
        ("斗l破l苍l穹ltlxlt", "斗破苍穹"),
        ("战Q神", "战Q神"),
        ("大l陆", "大l陆"),
        ("IPX-580", "IPX-580"),
    ],
)
def test_strip_spam_letters_requires_same_letter_twice(raw, expected):
    assert strip_spam_letters(raw) == expected


def test_resource_name_removes_prefix_extension_and_generic_phrasing():
    assert clean_title_for_name("9_斗破苍穹.txt") == "斗破苍穹"
    assert extract_resource_name("求《斗破苍穹》百度网盘链接") == "斗破苍穹"
    assert extract_resource_name("求XXX百度网盘链接") == "XXX"
    assert has_concrete_name("这个游戏谁有") is False


def test_search_page_parses_item_and_next_page():
    html = '<a href="https://zhidao.baidu.com/question/123.html?fr=search">求《斗破苍穹》链接</a><span>2026-09-18</span><a class="pager-next" href="/search?word=x&pn=10">下一页</a>'
    items, next_pn = parse_search_page(html)
    assert len(items) == 1
    assert items[0]["qid"] == "123"
    assert items[0]["title"] == "求《斗破苍穹》链接"
    assert next_pn == 10
    assert classify_search_html(html, items) == "normal"


def test_search_page_three_states():
    assert classify_search_html("找到相关结果", [{"qid": "1"}]) == "normal"
    assert classify_search_html("抱歉，没有找到相关结果", []) == "empty"
    assert classify_search_html("请完成安全验证", []) == "unknown"


@pytest.mark.parametrize(
    ("html", "status"),
    [
        ('<div class="best-text">这里有资源</div>', "ok"),
        ("该问题已被删除", "dead"),
        ("<html><body>备用正文</body></html>", "fallback"),
        ("", "empty"),
    ],
)
def test_detail_page_four_states(html, status):
    text, actual = parse_detail_page(html)
    assert actual == status
    if status == "ok":
        assert "这里有资源" in text


def test_pan_entries_preserve_code_and_normalize_wrappers():
    text = "分享链接：【https://pan.baidu.com/s/1AbCd】 提取码：ab12"
    entries = extract_pan_entries(text)
    assert entries == [{"link": "https://pan.baidu.com/s/1AbCd?pwd=ab12", "pwd": "ab12"}]
    assert normalize_pan_url("https://pan.baidu.com/s/1AbCd?pwd=ab12。") == entries[0]["link"]
    assert link_key("https://pan.baidu.com/s/1AbCd?pwd=ab12") == link_key("https://pan.baidu.com/s/1AbCd?pwd=xy34")


def test_within_range_uses_iso_dates():
    today = date.today()
    recent = (today - timedelta(days=3)).isoformat()
    old = (today - timedelta(days=365)).isoformat()
    assert within_range(recent, 7) is True
    assert within_range(old, 7) is False
    assert within_range("unknown", 7) is False
