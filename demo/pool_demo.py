"""独立演示 M13：双账号固定出口与请求池轮换，无真实请求。"""

from pathlib import Path
import sys
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.pool import PinnedExitFetcher, SlotPool


def main() -> None:
    pool = SlotPool(
        [{"name": "直连账号", "cookie": "demo-1"}, {"name": "代理账号", "cookie": "demo-2"}],
        pause_ask=lambda payload: True,
        on_log=lambda message: None,
        stop_event=Event(),
        on_status=lambda message: None,
    )
    pool.start()
    pool.fetch = lambda slot, url, **kwargs: "<html>正常搜索页</html>"
    body, slot = PinnedExitFetcher(pool, "direct").get("https://example.com")
    assert slot.exit_kind == "direct"
    assert "正常" in body
    print("固定直连出口通过模拟验证")


if __name__ == "__main__":
    main()
