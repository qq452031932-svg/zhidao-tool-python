"""M09 分享验证、转存结果和 errno 12 三分支。"""

import pytest

from lxds.pan_auth import PanQuotaError, PanTransientError
from lxds.pan_transfer import PanClient, cookie_fields, extract_pwd, extract_surl


def test_surl_pwd_and_cookie_fields():
    assert extract_surl("https://pan.baidu.com/s/1AbCdEf?pwd=a1b2") == "AbCdEf"
    assert extract_surl("https://pan.baidu.com/share/init?surl=AbC&pwd=xy12") == "AbC"
    assert extract_pwd("https://pan.baidu.com/s/1AbCdEf?pwd=a1b2") == "a1b2"
    assert cookie_fields("BDUSS=one; STOKEN=two; foo=bar") == {"BDUSS", "STOKEN", "foo"}


class FakeResponse:
    def __init__(self, payload=None, text=""):
        self.payload = payload or {}
        self.text = text

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, get_responses=None, post_responses=None):
        self.headers = {}
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.post_responses.pop(0)


def test_verify_share_prefers_share_uk_and_adds_bdclnd(monkeypatch):
    session = FakeSession(
        get_responses=[FakeResponse(text='shareid: 123, uk=0, share_uk: 456')],
        post_responses=[FakeResponse({"errno": 0, "randsk": "ticket"})],
    )
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("BDUSS=abc")
    assert client.verify_share("https://pan.baidu.com/s/1AbCd?pwd=abcd", "AbCd", "abcd") == ("123", "456", "ticket")
    assert "BDCLND=ticket" in session.headers["Cookie"]
    assert session.calls[1][2]["data"]["pwd"] == "abcd"


def test_transfer_uses_returned_fsids_without_listing_directory(monkeypatch):
    session = FakeSession(post_responses=[FakeResponse({"errno": 0, "extra": {"list": [{"to_fs_id": 71}, {"to_fs_id": 72}]}})])
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("cookie")
    monkeypatch.setattr(client, "ensure_target_dir", lambda path: None)
    monkeypatch.setattr(client, "list_dir", lambda path: pytest.fail("已有 to_fs_id，不应列目录"))
    result = client.transfer_files("123", "456", [1, 2], "/目标", "https://pan.baidu.com/s/1AbCd", "token")
    assert client.transferred_fsids(result, 2) == [71, 72]
    assert session.calls[0][2]["data"]["fsidlist"] == "[1,2]"


@pytest.mark.parametrize(
    ("payload", "status", "retryable"),
    [
        ({"errno": 12, "duplicated": {"list": [{"path": "/目标/文件"}]}}, "重复跳过", False),
        ({"errno": 12, "target_file_nums_limit": 500}, "文件数超限", False),
        ({"errno": 12}, "瞬时故障", True),
    ],
)
def test_errno_12_is_split_by_response_fields(monkeypatch, payload, status, retryable):
    session = FakeSession(post_responses=[FakeResponse(payload)])
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("cookie")
    monkeypatch.setattr(client, "ensure_target_dir", lambda path: None)
    result = client.transfer_files("123", "456", [1], "/目标", "url", "token")
    assert result["status"] == status
    assert result["retryable"] is retryable
    if status == "重复跳过":
        assert result["dup_paths"] == ["/目标/文件"]


def test_no_space_stops_batch_immediately(monkeypatch):
    session = FakeSession(post_responses=[FakeResponse({"errno": 12, "message": "网盘空间不足"})])
    monkeypatch.setattr("lxds.pan_auth.requests.Session", lambda: session)
    client = PanClient("cookie")
    monkeypatch.setattr(client, "ensure_target_dir", lambda path: None)
    with pytest.raises(PanQuotaError):
        client.transfer_files("123", "456", [1], "/目标", "url", "token")
