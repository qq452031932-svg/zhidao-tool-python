"""独立演示 M15：保存采集断点、读回并清理。"""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds import checkpoint


def main() -> None:
    with TemporaryDirectory() as directory:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = directory
        try:
            path = checkpoint.checkpoint_path("demo.xlsx", "collect")
            checkpoint.save(path, {"items": [{"name": "演示"}], "found": 1})
            assert checkpoint.load(path)["found"] == 1
            checkpoint.clear(path)
            assert checkpoint.load(path) == {}
            print("断点保存、读取和清理均完成")
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous


if __name__ == "__main__":
    main()
