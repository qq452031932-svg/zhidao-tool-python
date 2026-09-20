"""独立演示 M08：用模拟响应完成 Cookie 体检和目录检查。"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.pan_auth import PanClient


class DemoResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class DemoSession:
    def __init__(self) -> None:
        self.headers = {}

    def get(self, url: str, **kwargs) -> DemoResponse:
        if "xpan/nas" in url or "api/quota" in url:
            return DemoResponse({"errno": 0})
        if "api/list" in url:
            return DemoResponse({"errno": 0, "list": [{"path": "/演示", "isdir": 1}]})
        raise AssertionError(url)


def main() -> None:
    with patch("lxds.pan_auth.requests.Session", return_value=DemoSession()):
        client = PanClient("demo-cookie")
        assert client.check_cookie()[0] == "ok"
        client.ensure_target_dir("/演示")
        print("Cookie 体检与目标目录检查通过模拟验证")


if __name__ == "__main__":
    main()
