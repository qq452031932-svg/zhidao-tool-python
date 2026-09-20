"""独立演示 M04 的 prompt 选择与回答原样返回。"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.qa import STYLES, generate_answer


def main() -> None:
    with patch("lxds.qa.chat", return_value="演示回答正文") as mocked:
        for style in STYLES:
            assert generate_answer("demo-key", "问题原文", style) == "演示回答正文"
        assert mocked.call_count == 3
        print("三种风格的 prompt 已分别组装并调用模拟模型")


if __name__ == "__main__":
    main()
