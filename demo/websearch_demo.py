"""M07 离线演示：百度结果块与知道详情页补量。"""

from pathlib import Path
from threading import Event
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.websearch import BaiduSiteSearchCollector, BaiduWebCollector, site_queries


class FixtureFetcher:
    def get(self, url: str, referer: str | None = None, purpose: str = "search"):
        if "zhidao.baidu.com/question/" in url:
            return "<title>斗破苍穹资源</title>链接：https://pan.baidu.com/s/1AbCd 提取码：ab12", None
        return '<h3><a href="https://zhidao.baidu.com/question/123.html">斗破苍穹</a></h3>' \
               '<div>链接：https://pan.baidu.com/s/1AbCd 提取码：ab12</div>', None


def main() -> None:
    fetcher = FixtureFetcher()
    web = BaiduWebCollector(fetcher, Event()).search("斗破苍穹", print)
    site = BaiduSiteSearchCollector(fetcher, Event(), max_variants=1).search("斗破苍穹", print)
    assert web[0]["links"][0]["pwd"] == site[0]["links"][0]["pwd"] == "ab12"
    print(f"站内查询示例：{site_queries('斗破苍穹')[0]}")
    print(f"网页结果 {len(web)} 条，站内详情结果 {len(site)} 条")


if __name__ == "__main__":
    main()
