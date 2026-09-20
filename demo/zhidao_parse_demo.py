"""独立演示 M11：离线解析一条百度知道搜索结果和网盘链接。"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.zhidao_parse import extract_pan_entries, extract_resource_name, parse_search_page


def main() -> None:
    html = '<a href="https://zhidao.baidu.com/question/123.html?fr=search">求《斗破苍穹》链接</a>'
    items, _ = parse_search_page(html)
    entries = extract_pan_entries("链接：https://pan.baidu.com/s/1AbCd 提取码：ab12")
    assert extract_resource_name(items[0]["title"]) == "斗破苍穹"
    assert entries[0]["pwd"] == "ab12"
    print("搜索页、资源名称与网盘链接离线解析成功")


if __name__ == "__main__":
    main()
