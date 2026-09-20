"""M05 百度知道批量接口与直连约束。"""

import pytest
import requests

from lxds.zhidao_bulk import BulkError, upload_file, userinfo


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *, user_payload=None, upload_payload=None):
        self.trust_env = True
        self.user_payload = user_payload or {"code": 200, "data": {"hasPermission": True}}
        self.upload_payload = upload_payload or {"code": 200, "data": {"taskId": "task-123"}}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(self.user_payload)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse(self.upload_payload)

    def close(self):
        pass


def test_upload_is_direct_and_uses_official_multipart_fields(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr("lxds.zhidao_bulk.requests.Session", lambda: session)
    result = upload_file("private-cookie", "qa.xlsx", b"xlsx", "任务甲")
    assert session.trust_env is False
    assert result["taskId"] == "task-123"
    method, url, kwargs = session.calls[-1]
    assert method == "POST"
    assert url == "https://zhidao.baidu.com/qa/api/bulkqa/upload"
    assert kwargs["headers"]["Cookie"] == "private-cookie"
    assert kwargs["files"]["file"] == (
        "qa.xlsx", b"xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert kwargs["data"]["taskName"] == "任务甲"


def test_userinfo_uses_direct_session_and_fixed_headers(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr("lxds.zhidao_bulk.requests.Session", lambda: session)
    info = userinfo("private-cookie")
    assert info["hasPermission"] is True
    assert session.trust_env is False
    _, url, kwargs = session.calls[0]
    assert url == "https://zhidao.baidu.com/qa/api/bulkqa/userinfo"
    assert kwargs["headers"]["Referer"] == "https://zhidao.baidu.com/b/batch/batch-upload"


def test_permission_and_login_failures_have_codes(monkeypatch):
    for payload, expected in [
        ({"code": 200, "data": {"hasPermission": False}}, "PERM"),
        ({"code": 401, "message": "未登录"}, "LOGIN"),
    ]:
        session = FakeSession(user_payload=payload)
        monkeypatch.setattr("lxds.zhidao_bulk.requests.Session", lambda: session)
        with pytest.raises(BulkError) as error:
            upload_file("private-cookie", "qa.xlsx", b"xlsx", "任务")
        assert error.value.code == expected
        assert not any(call[0] == "POST" for call in session.calls)


def test_cookie_never_appears_in_error_or_output(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("连接失败")

    session = FakeSession()
    session.get = fail
    monkeypatch.setattr("lxds.zhidao_bulk.requests.Session", lambda: session)
    with pytest.raises(BulkError) as error:
        userinfo("private-cookie")
    assert "private-cookie" not in str(error.value)
    assert "private-cookie" not in capsys.readouterr().out
