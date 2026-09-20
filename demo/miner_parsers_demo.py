"""M16 standalone offline demo; no live requests are made."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lxds import miner_parsers as m


def main() -> None:
    path = ROOT / "tests" / "fixtures" / "miner_parsers" / "cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    for site, case in cases.items():
        actual = getattr(m, "parse_" + site)(case["body"])
        if actual != case["expected"]:
            raise AssertionError(f"{site}: {actual!r} != {case['expected']!r}")
    assert m.strip_trailing_version("Photoshop 2024 v25.0 绿色版") == "Photoshop"
    assert m.canonical_key("鬼灭之刃 第三季") == m.canonical_key("鬼灭之刃")
    print(f"M16 离线演示通过：{len(cases)} 个解析入口；未执行真实站点请求。")


if __name__ == "__main__":
    main()
