"""M03 DeepSeek 客户端的请求契约和错误映射。"""

import pytest
import requests

from lxds.deepseek import DeepSeekError, chat, test_key as check_key


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"choices": [{"message": {"content": "回答"}}]}

    def json(self):
        return self._payload


def test_chat_sends_fixed_model_headers_and_json_mode(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr("lxds.deepseek.requests.post", fake_post)
    assert chat("test-key", [{"role": "user", "content": "问题"}], max_tokens=300, json_mode=True, timeout=9) == "回答"
    url, kwargs = calls[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"] == {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "问题"}],
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    assert kwargs["timeout"] == 9


def test_chat_without_key_fails_before_network(monkeypatch):
    monkeypatch.setattr("lxds.deepseek.requests.post", lambda *args, **kwargs: pytest.fail("不应请求网络"))
    with pytest.raises(DeepSeekError, match="请先在个人中心配置 DeepSeek API Key"):
        chat("", [])


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "DeepSeek API Key 无效，请检查个人中心配置"),
        (402, "DeepSeek 余额不足或请求限流，请稍后重试"),
        (429, "DeepSeek 余额不足或请求限流，请稍后重试"),
        (503, "DeepSeek 接口异常（HTTP 503）"),
    ],
)
def test_http_errors_map_to_prd_messages(monkeypatch, status, message):
    monkeypatch.setattr("lxds.deepseek.requests.post", lambda *args, **kwargs: FakeResponse(status_code=status))
    with pytest.raises(DeepSeekError) as error:
        chat("key", [])
    assert str(error.value) == message


@pytest.mark.parametrize(
    ("raised", "message"),
    [
        (requests.Timeout("timeout"), "DeepSeek 请求超时，请稍后重试"),
        (requests.ConnectionError("offline"), "DeepSeek 网络错误：offline"),
    ],
)
def test_network_errors_map_to_prd_messages(monkeypatch, raised, message):
    def fail(*args, **kwargs):
        raise raised

    monkeypatch.setattr("lxds.deepseek.requests.post", fail)
    with pytest.raises(DeepSeekError) as error:
        chat("key", [])
    assert str(error.value) == message


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "DeepSeek 返回格式异常"),
        ({"choices": []}, "DeepSeek 返回格式异常"),
        ({"choices": [{"message": {"content": ""}}]}, "DeepSeek 返回内容为空"),
    ],
)
def test_invalid_response_maps_to_prd_messages(monkeypatch, payload, message):
    monkeypatch.setattr("lxds.deepseek.requests.post", lambda *args, **kwargs: FakeResponse(payload=payload))
    with pytest.raises(DeepSeekError) as error:
        chat("key", [])
    assert str(error.value) == message


def test_key_uses_minimal_ping_request(monkeypatch):
    requests_seen = []

    def fake_post(url, **kwargs):
        requests_seen.append(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr("lxds.deepseek.requests.post", fake_post)
    result = check_key("key")
    assert result[0] is True
    assert requests_seen[0]["messages"] == [{"role": "user", "content": "ping"}]
