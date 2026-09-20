"""M08 百度网盘 Cookie 状态与目录校验。"""

import pytest

from lxds.pan_auth import PanClient, PanError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.text = ""

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(self.responses.pop(0))

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        raise AssertionError("目录体检不应创建文件夹")


@pytest.mark.parametrize(
    ("responses", "status", "snippet"),
    [
        ([{"errno": 0}, {"errno": 0}], "ok", ""),
        ([{"errno": -6}], "expired", "登录态已失效"),
        ([{"errno": 0}, {"errno": -6}], "incomplete", "缺少 STOKEN"),
        ([{"errno": 132}], "risk", "安全验证"),
        ([{"errno": 2}], "risk", "安全验证"),
        ([{"errno": -9}], "risk", "安全验证"),
    ],
)
def test_cookie_statuses(monkeypatch, responses, status, snippet):
    session = FakeSession(responses)
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("cookie")
    actual_status, message = client.check_cookie()
    assert actual_status == status
    assert snippet in message
    assert session.headers["Cookie"] == "cookie"


def test_bdstoken_uses_official_json_response(monkeypatch):
    session = FakeSession([{"errno": 0, "result": {"bdstoken": "abc123"}}])
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("cookie")
    assert client.bdstoken() == "abc123"
    assert "gettemplatevariable" in session.calls[0][1]


def test_ensure_target_dir_never_creates_missing_folder_and_caches_result(monkeypatch):
    session = FakeSession([{"errno": 0, "list": [{"path": "/已有", "isdir": 1}]}])
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("cookie")
    client.ensure_target_dir("/已有")
    client.ensure_target_dir("/已有")
    assert len(session.calls) == 1
    assert all(method == "GET" for method, _, _ in session.calls)

    missing = FakeSession([{"errno": 0, "list": []}])
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: missing)
    client = PanClient("cookie")
    with pytest.raises(PanError, match="目标文件夹不存在或读不到"):
        client.ensure_target_dir("/不存在")
    assert all(method == "GET" for method, _, _ in missing.calls)
