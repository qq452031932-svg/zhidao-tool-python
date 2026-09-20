"""M04 三套问答 prompt 的原样组合。"""

from pathlib import Path

import pytest

from lxds.qa import STYLES, generate_answer


PROMPTS = Path(__file__).resolve().parents[1] / "assets" / "prompts"


@pytest.mark.parametrize(
    ("style", "filename"),
    [
        ("first_person", "qa_style1_first_person.txt"),
        ("third_person", "qa_style2_third_person.txt"),
        ("helper", "qa_style3_helper.txt"),
    ],
)
def test_each_style_uses_unchanged_prompt_plus_human_suffix(monkeypatch, style, filename):
    calls = []

    def fake_chat(api_key, messages, **kwargs):
        calls.append((api_key, messages, kwargs))
        return "正文原样返回"

    monkeypatch.setattr("lxds.qa.chat", fake_chat)
    assert generate_answer("key", "问题原文", style) == "正文原样返回"
    key, messages, kwargs = calls[0]
    assert key == "key"
    assert messages == [
        {"role": "system", "content": (PROMPTS / filename).read_text(encoding="utf-8") + (PROMPTS / "qa_human_suffix.txt").read_text(encoding="utf-8")},
        {"role": "user", "content": "问题原文"},
    ]
    assert kwargs["json_mode"] is False


def test_invalid_style_raises_before_request(monkeypatch):
    monkeypatch.setattr("lxds.qa.chat", lambda *args, **kwargs: pytest.fail("不应调用 DeepSeek"))
    assert STYLES == ("first_person", "third_person", "helper")
    with pytest.raises(ValueError, match="不支持的问答风格"):
        generate_answer("key", "问题", "unknown")
