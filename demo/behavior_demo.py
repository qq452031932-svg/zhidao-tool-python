"""独立演示 M12：指纹、块内洗牌和单账号请求间隔。"""

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.behavior import HumanPacer, pick_profile, shuffle_blocks


def main() -> None:
    profile = pick_profile()
    assert "ua" in profile and "platform" in profile
    shuffled = shuffle_blocks(list(range(10)), 5)
    assert set(shuffled[:5]) == set(range(5))
    pacer = HumanPacer()
    pacer.note_request(0)
    wait = pacer.wait_time(time.monotonic())
    assert 0 < wait <= 10
    print("浏览器指纹、块内洗牌和账号请求间隔已生成")


if __name__ == "__main__":
    main()
