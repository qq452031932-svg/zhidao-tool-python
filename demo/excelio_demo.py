"""独立演示 M02：资源表写入、读回和发布模板生成。"""

from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import load_workbook

from lxds.excelio import build_publish_workbook_bytes, read_resource_table, write_resource_table


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "resources.xlsx"
        write_resource_table(
            str(path),
            [{"name": "古诗合集", "link": "https://pan.baidu.com/s/1AbCd", "pwd": "abcd"}],
        )
        rows, skipped = read_resource_table(str(path))
        assert not skipped
        assert rows[0]["link"] == "https://pan.baidu.com/s/1AbCd?pwd=abcd"

        publish = build_publish_workbook_bytes([{"title": "求古诗合集完整网盘链接下载", "answer": "<p>演示回答</p>"}])
        sheet = load_workbook(BytesIO(publish)).active
        assert [cell.value for cell in sheet[1]] == ["qid", "问题标题", "回答内容"]
        print(f"读取资源：{len(rows)} 条")
        print("发布模板表头：" + ", ".join(str(cell.value) for cell in sheet[1]))


if __name__ == "__main__":
    main()
