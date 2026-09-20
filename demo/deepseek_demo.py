"""独立演示 M03：用模拟 HTTP 响应验证请求和返回，不消耗 API 额度。"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.deepseek import chat, test_key


class DemoResponse:
    status_code = 200

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "演示回答"}}]}


def main() -> None:
    with patch("lxds.deepseek.requests.post", return_value=DemoResponse()) as request:
        answer = chat("demo-key", [{"role": "user", "content": "问题"}])
        valid, _ = test_key("demo-key")
        assert answer == "演示回答" and valid
        assert request.call_args_list[0].kwargs["json"]["model"] == "deepseek-chat"
        print("DeepSeek 请求与返回结构：通过模拟验证")


if __name__ == "__main__":
    main()
