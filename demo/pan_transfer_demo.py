"""独立演示 M09：模拟分享验证与转存，不接触真实账号。"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.pan_transfer import PanClient, extract_pwd, extract_surl


class DemoResponse:
    def __init__(self, payload=None, text=""):
        self.payload = payload or {}
        self.text = text

    def json(self):
        return self.payload


class DemoSession:
    def __init__(self):
        self.headers = {}

    def get(self, url, **kwargs):
        return DemoResponse(text='shareid: 123, uk=0, share_uk: 456')

    def post(self, url, **kwargs):
        if "verify" in url:
            return DemoResponse({"errno": 0, "randsk": "ticket"})
        return DemoResponse({"errno": 0, "extra": {"list": [{"to_fs_id": 77}]}})


def main() -> None:
    url = "https://pan.baidu.com/s/1AbCd?pwd=abcd"
    with patch("lxds.pan_auth.requests.Session", return_value=DemoSession()):
        client = PanClient("demo-cookie")
        client.ensure_target_dir = lambda path: None
        shareid, uk, _ = client.verify_share(url, extract_surl(url), extract_pwd(url))
        result = client.transfer_files(shareid, uk, [1], "/演示", url, "token")
        assert client.transferred_fsids(result, 1) == [77]
        print("分享验证与转存结果解析通过模拟验证")


if __name__ == "__main__":
    main()
