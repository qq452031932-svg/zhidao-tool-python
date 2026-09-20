"""独立演示 M05：用本地模拟响应创建批量任务。"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.zhidao_bulk import upload_file


class DemoResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class DemoSession:
    trust_env = True

    def get(self, url: str, **kwargs) -> DemoResponse:
        return DemoResponse({"code": 200, "data": {"hasPermission": True}})

    def post(self, url: str, **kwargs) -> DemoResponse:
        assert self.trust_env is False
        assert kwargs["files"]["file"][0] == "qa.xlsx"
        return DemoResponse({"code": 200, "data": {"taskId": "demo-task"}})

    def close(self) -> None:
        pass


def main() -> None:
    with patch("lxds.zhidao_bulk.requests.Session", return_value=DemoSession()):
        result = upload_file("demo-cookie", "qa.xlsx", b"demo", "演示任务")
    assert result["taskId"] == "demo-task"
    print("模拟批量任务已创建，taskId=demo-task")


if __name__ == "__main__":
    main()
