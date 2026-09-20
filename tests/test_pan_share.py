"""M10 分享链接格式与组合入口状态。"""

from unittest.mock import patch

import pytest

from lxds.pan_auth import PanError
from lxds.pan_share import PanClient, generate_pwd


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload=None):
        self.headers = {}
        self.payload = payload or {"errno": 0, "shorturl": "1ShareAbC"}
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def test_generate_pwd_is_four_lowercase_or_digit_characters():
    samples = [generate_pwd() for _ in range(1000)]
    assert all(len(value) == 4 and set(value) <= set("abcdefghijklmnopqrstuvwxyz0123456789") for value in samples)
    assert len(set(samples)) > 900


def test_share_files_builds_final_link_and_form(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("cookie")
    result = client.share_files([71], "token", "abcd")
    assert result["share_url"] == "https://pan.baidu.com/s/1ShareAbC?pwd=abcd"
    assert result["share_pwd"] == "abcd"
    url, kwargs = session.calls[0]
    assert "share/set" in url
    assert kwargs["data"] == {"schannel": 0, "channel_list": "[]", "period": 0, "pwd": "abcd", "fid_list": "[71]"}


def test_transfer_success_but_share_failure_is_partial_success(monkeypatch):
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: FakeSession())
    client = PanClient("cookie")
    monkeypatch.setattr(client, "verify_share", lambda url, surl, pwd: ("123", "456", "ticket"))
    monkeypatch.setattr(client, "file_list", lambda shareid, uk, url: [{"fs_id": 1, "server_filename": "文件"}])
    monkeypatch.setattr(client, "bdstoken", lambda: "token")
    monkeypatch.setattr(client, "transfer_files", lambda *args: {"status": "转存成功", "retryable": False, "extra": {"list": [{"to_fs_id": 71}]}})
    monkeypatch.setattr(client, "share_files", lambda *args: (_ for _ in ()).throw(PanError("分享失败：无权限")))
    result = client.transfer_link("https://pan.baidu.com/s/1AbCd?pwd=abcd", "/目标", True)
    assert result["status"] == "转存成功，分享失败"
    assert result["retryable"] is False
    assert "分享失败：无权限" in result["message"]


def test_transfer_and_share_returns_new_link(monkeypatch):
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: FakeSession())
    client = PanClient("cookie")
    monkeypatch.setattr(client, "verify_share", lambda url, surl, pwd: ("123", "456", "ticket"))
    monkeypatch.setattr(client, "file_list", lambda shareid, uk, url: [{"fs_id": 1, "server_filename": "文件"}])
    monkeypatch.setattr(client, "bdstoken", lambda: "token")
    monkeypatch.setattr(client, "transfer_files", lambda *args: {"status": "转存成功", "retryable": False, "extra": {"list": [{"to_fs_id": 71}]}})
    result = client.transfer_link("https://pan.baidu.com/s/1AbCd?pwd=abcd", "/目标", True, pwd="xy12")
    assert result["status"] == "转存成功"
    assert result["share_url"] == "https://pan.baidu.com/s/1ShareAbC?pwd=xy12"
