"""独立演示 M10：模拟分享接口并生成带提取码的链接。"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.pan_share import PanClient


class DemoResponse:
    def json(self) -> dict:
        return {"errno": 0, "shorturl": "1DemoShare"}


class DemoSession:
    def __init__(self) -> None:
        self.headers = {}

    def post(self, url, **kwargs) -> DemoResponse:
        return DemoResponse()


def main() -> None:
    with patch("lxds.pan_auth.requests.Session", return_value=DemoSession()):
        client = PanClient("demo-cookie")
        result = client.share_files([77], "token", "abcd")
        assert result["share_url"] == "https://pan.baidu.com/s/1DemoShare?pwd=abcd"
        print("分享链接格式通过模拟验证")


if __name__ == "__main__":
    main()
