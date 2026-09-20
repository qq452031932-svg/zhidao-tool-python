"""M06 标题、回答结构和 AI 整批兜底。"""

import json
from pathlib import Path

import pytest

from lxds.template_engine import (
    ai_generate_batch,
    build_title,
    enforce_title_format,
    fallback_qa,
    normalize_answer,
    post_process_row,
    should_search,
)


LINK = "https://pan.baidu.com/s/1AbCd?pwd=abcd"
PAIRS = [
    ("求", "完整网盘链接下载"),
    ("求", "完整网盘链接获取"),
    ("哪里有", "完整网盘资源链接"),
    ("跪求", "百度网盘链接获取"),
    ("求", "百度网盘链接下载"),
    ("谁有", "百度网盘资源链接"),
]


@pytest.mark.parametrize("index", range(12))
def test_titles_cycle_through_exact_prefix_suffix_pairs(index):
    title = build_title("古诗合集", index)
    prefix, suffix = PAIRS[index % 6]
    assert title == f"{prefix}古诗合集{suffix}"


def test_long_title_keeps_prefix_suffix_and_first_part_of_name():
    title = build_title("甲" * 60, 0)
    assert len(title) <= 49
    assert title.startswith("求甲甲")
    assert title.endswith("完整网盘链接下载")
    assert enforce_title_format("古诗合集", 1) == "求古诗合集完整网盘链接获取"


@pytest.mark.parametrize(
    "wrapped",
    [
        '<a href="https://pan.baidu.com/s/1AbCd?pwd=abcd">网盘链接</a>',
        '【https://pan.baidu.com/s/1AbCd?pwd=abcd】',
    ],
)
def test_answer_unwraps_link_and_keeps_three_paragraphs(wrapped):
    answer = normalize_answer(f"{wrapped} 这是一份可供学习使用的资料。", LINK, "古诗合集")
    assert answer.startswith("<p><strong>点击链接获取完整素材：</strong><br/></p><p>" + LINK + "<br/></p><p>")
    assert answer.count(LINK) == 1
    assert "<a " not in answer
    assert "【" not in answer
    assert answer.endswith("</p>")


def test_post_process_corrects_ai_title_and_link():
    row = post_process_row(
        {"index": 0, "title": "古诗合集", "answer": f"【{LINK}】 这份资料包含常见古诗。"},
        "古诗合集", LINK, 0,
    )
    assert row["title"] == "求古诗合集完整网盘链接下载"
    assert row["answer"].count(LINK) == 1


def test_fallback_keeps_original_short_template():
    row = fallback_qa("古诗合集", LINK, 0)
    assert "《古诗合集》是一份网络分享的资源" in row["answer"]
    assert "即可转存获取。\n下载后即可使用" in row["answer"]
    assert row["answer"].count(LINK) == 1


@pytest.mark.parametrize("failure", ["timeout", "invalid_json", "wrong_length", "wrong_order"])
def test_ai_failure_falls_back_for_every_input_row(monkeypatch, failure):
    source = [
        {"name": "古诗合集", "link": LINK, "index": 0},
        {"name": "数学试卷", "link": LINK, "index": 1},
    ]

    def fake_chat(*args, **kwargs):
        if failure == "timeout":
            raise RuntimeError("timeout")
        if failure == "invalid_json":
            return "not json"
        if failure == "wrong_length":
            return json.dumps({"rows": [{"index": 0, "title": "甲", "answer": "介绍"}]})
        return json.dumps({"rows": [{"index": 1, "title": "乙", "answer": "介绍"}, {"index": 0, "title": "甲", "answer": "介绍"}]})

    monkeypatch.setattr("lxds.template_engine.chat", fake_chat)
    monkeypatch.setattr("lxds.template_engine.time.sleep", lambda seconds: None)
    output = ai_generate_batch("key", source, search_map={})
    assert len(output) == len(source)
    assert [row["name"] for row in output] == [row["name"] for row in source]
    assert all("网络分享的资源" in row["answer"] for row in output)


def test_ai_request_uses_exact_prompt_and_json_mode(monkeypatch):
    seen = []

    def fake_chat(key, messages, **kwargs):
        seen.append((messages, kwargs))
        return json.dumps({"rows": [{"index": 0, "title": "古诗合集", "answer": "资料介绍"}]})

    monkeypatch.setattr("lxds.template_engine.chat", fake_chat)
    rows = ai_generate_batch("key", [{"name": "古诗合集", "link": LINK, "index": 0}], search_map={})
    expected_prompt = (Path(__file__).resolve().parents[1] / "assets/prompts/template_system_prompt.txt").read_text(encoding="utf-8")
    assert seen[0][0][0] == {"role": "system", "content": expected_prompt}
    assert seen[0][1]["json_mode"] is True
    assert seen[0][1]["max_tokens"] == 6000
    assert seen[0][1]["timeout"] == 180
    assert len(rows) == 1


def test_ai_retries_three_times_with_original_waits_then_falls_back(monkeypatch):
    waits = []
    attempts = []
    monkeypatch.setattr("lxds.template_engine.time.sleep", lambda seconds: waits.append(seconds))

    def fail(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError("network")

    monkeypatch.setattr("lxds.template_engine.chat", fail)
    output = ai_generate_batch("key", [{"name": "古诗合集", "link": LINK, "index": 0}], search_map={})
    assert len(attempts) == 4
    assert waits == [3, 6, 12]
    assert "网络分享的资源" in output[0]["answer"]


def test_type_words_skip_web_search():
    assert should_search("古诗课件") is False
    assert should_search("斗破苍穹") is True
