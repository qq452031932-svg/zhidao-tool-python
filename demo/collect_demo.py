"""M14 纯离线演示：精准与模糊采集，无账号、无网络请求。"""

from datetime import date, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.collect import CollectWorker


class DemoPool:
    def __init__(self):
        self.probes = 0

    def on_silent_risk(self, keywords, page):
        self.probes += 1
        return True


class DemoFetcher:
    def __init__(self, pages, details):
        self.pages = pages
        self.details = details

    def get(self, url, **kwargs):
        if "/question/" in url:
            qid = url.split("/question/", 1)[1].split(".", 1)[0]
            return self.details[qid], None
        query = parse_qs(urlsplit(url).query)
        word = query["word"][0]
        return self.pages.get(word, "没有找到相关结果"), None


def result_page(rows):
    return "".join(
        f'<a href="https://zhidao.baidu.com/question/{qid}.html?fr=search">'
        f'求《{name}》链接</a><span>{when}</span>'
        for qid, name, when in rows
    )


def main():
    today = date.today()
    pages = {
        "甲书": result_page([("1", "甲书", today.isoformat())]),
        "求小说百度网盘链接": result_page([
            ("1", "甲书", today.isoformat()),
            ("2", "乙书", (today - timedelta(days=100)).isoformat()),
        ]),
    }
    details = {
        "1": '<div class="best-text">https://pan.baidu.com/s/demo1 提取码：abcd</div>',
        "2": '<div class="best-text">https://pan.baidu.com/s/demo2 提取码：efgh</div>',
    }
    with TemporaryDirectory() as directory:
        precise = CollectWorker(keyword=["甲书"], mode="precise",
                                fetcher=DemoFetcher(pages, details), pool=DemoPool(),
                                checkpoint_path=str(Path(directory) / "precise.json")).run()
        fuzzy = CollectWorker(keyword="小说", count=2, mode="fuzzy",
                              fetcher=DemoFetcher(pages, details), pool=DemoPool(),
                              checkpoint_path=str(Path(directory) / "fuzzy.json")).run()
    assert precise["found"] == 1
    assert fuzzy["found"] == 2
    print(f"精准采集：{precise['found']} 条；模糊采集：{fuzzy['found']} 条（自动放宽到一年）")


if __name__ == "__main__":
    main()
