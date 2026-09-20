"""M17 离线演示：两个假榜单，不发网络请求。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from lxds import miner


def main():
    original_sources = miner.SOURCES["小说"]
    original_search = miner._search_supplement
    try:
        miner.SOURCES["小说"] = (("示例榜单", lambda *args: ["流光之城", "远山来信"], False),)
        miner._search_supplement = lambda *args: []
        with TemporaryDirectory() as directory:
            target = Path(directory) / "keywords.txt"
            result = miner.collect_hot_names("小说", 2, str(target), Event(), print,
                                             shuffle=False)
            assert target.read_text(encoding="utf-8").splitlines() == ["小说流光之城", "小说远山来信"]
            print(result)
    finally:
        miner.SOURCES["小说"] = original_sources
        miner._search_supplement = original_search


if __name__ == "__main__":
    main()
