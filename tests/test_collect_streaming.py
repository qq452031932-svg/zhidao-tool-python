"""Results must be emitted and saved before later network work completes."""

import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.collect import CollectWorker
from lxds.pool import PoolError
from lxds.websearch import BaiduSiteSearchCollector, BaiduWebCollector


def detail(name):
    return (f'<div class="best-text">https://pan.baidu.com/s/1fixture-{name} 提取码：ab12</div>'
            + '<script>' + 'x' * 2100 + '</script>')


def question(qid, name):
    return f'<dl><dt><a href="https://zhidao.baidu.com/question/{qid}.html?fr=search">求《{name}》链接</a></dt></dl>'


def web_result(name):
    share_id = "first" if name == "第一本" else "second"
    return f'<h3><a href="https://example.com/{share_id}">《{name}》资源</a></h3><div>{detail(share_id)}</div>'


class OfflinePool:
    slots = [type("Slot", (), {"exit_kind": "direct"})()]

    def start(self):
        pass

    def on_silent_risk(self, *args):
        return True


class EmptyFetcher:
    def get(self, url, **kwargs):
        return "没有找到相关结果", None


class BlockingSecondFetcher:
    def __init__(self, mode="main", on_block=None):
        self.mode = mode
        self.entered = threading.Event()
        self.release = threading.Event()
        self.on_block = on_block

    def get(self, url, **kwargs):
        if self.mode == "web":
            second = parse_qs(urlsplit(url).query).get("pn") == ["10"]
            response = web_result("第二本" if second else "第一本")
        elif "/question/" in url:
            # Legacy site search requests extensionless question URLs.
            second = urlsplit(url).path.rsplit("/", 1)[-1].split(".", 1)[0] == "102"
            response = detail("second" if second else "first")
            if self.mode == "site":
                response = f'<title>《{"第二本" if second else "第一本"}》资源</title>' + response
        else:
            return question(101, "第一本") + question(102, "第二本"), None
        if second:
            self.entered.set()
            if self.on_block:
                self.on_block()
            if not self.release.wait(10):
                raise AssertionError("Test did not release the second offline response")
        return response, None


class CollectStreamingTests(unittest.TestCase):
    def test_site_search_keeps_its_existing_named_term_argument_and_list_result(self):
        collector = BaiduSiteSearchCollector(EmptyFetcher(), threading.Event(), max_variants=1)
        self.assertEqual([], collector.search(term="资源", on_log=None))

    def assert_first_result_is_live(self, worker, fetcher, checkpoint, items, progress):
        completed = threading.Event()
        outcome = {}

        def run():
            try:
                outcome["result"] = worker.run()
            except BaseException as error:
                outcome["error"] = error
            finally:
                completed.set()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            self.assertTrue(fetcher.entered.wait(3), "Second request did not begin")
            self.assertFalse(completed.is_set(), "Task must still be awaiting its second result")
            self.assertEqual(1, len(items), "First item must be emitted before target/done")
            self.assertEqual({"found": 1, "target": 2}, progress[-1])
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(1, saved["found"])
            self.assertEqual(items, saved["items"])
        finally:
            fetcher.release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        if "error" in outcome:
            raise outcome["error"]
        self.assertEqual(2, outcome["result"]["found"])
        self.assertEqual(2, len(items))

    def test_main_path_emits_progress_and_saves_first_row_while_second_detail_waits(self):
        with tempfile.TemporaryDirectory(prefix="collect-stream-") as temporary:
            checkpoint = Path(temporary) / "checkpoint.json"
            items, progress = [], []
            fetcher = BlockingSecondFetcher()
            worker = CollectWorker(
                keyword="资源", count=2, mode="fuzzy", time_range="全部",
                fetcher=fetcher, pool=OfflinePool(), checkpoint_path=str(checkpoint),
                on_item=items.append, on_progress=progress.append,
            )
            self.assert_first_result_is_live(worker, fetcher, checkpoint, items, progress)

    def test_supplements_emit_and_save_before_next_page_or_detail_returns(self):
        for mode, collector_type in (("web", BaiduWebCollector), ("site", BaiduSiteSearchCollector)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="supplement-stream-") as temporary:
                checkpoint = Path(temporary) / "checkpoint.json"
                items, progress = [], []
                fetcher = BlockingSecondFetcher(mode)
                worker = CollectWorker(
                    keyword="资源", count=2, mode="fuzzy", time_range="全部",
                    fetcher=EmptyFetcher(), pool=OfflinePool(), checkpoint_path=str(checkpoint),
                    on_item=items.append, on_progress=progress.append,
                    supplement_factory=lambda _, stop: collector_type(fetcher, stop),
                )
                self.assert_first_result_is_live(worker, fetcher, checkpoint, items, progress)

    def test_target_and_stop_close_stream_without_requesting_another_record(self):
        for stop_after_first in (False, True):
            with self.subTest(stop=stop_after_first), tempfile.TemporaryDirectory(prefix="stream-close-") as temporary:
                closed = threading.Event()
                advanced = threading.Event()

                class Collector:
                    def search(self, *args):
                        raise AssertionError("Worker should use the streaming API")

                    def iter_search(self, *args):
                        try:
                            yield {"title": "第一本", "links": [{"link": "https://pan.baidu.com/s/1fixture-first", "pwd": "ab12"}]}
                            advanced.set()
                            yield {"title": "第二本", "links": [{"link": "https://pan.baidu.com/s/1fixture-second", "pwd": "ab12"}]}
                        finally:
                            closed.set()

                worker = CollectWorker(
                    keyword="资源", count=2 if stop_after_first else 1, mode="fuzzy", time_range="全部",
                    fetcher=EmptyFetcher(), pool=OfflinePool(), checkpoint_path=str(Path(temporary) / "checkpoint.json"),
                    supplement_factory=lambda *_: Collector(),
                )
                if stop_after_first:
                    worker.on_item = lambda _: worker.stop()
                result = worker.run()
                self.assertEqual(1, result["found"])
                self.assertEqual(stop_after_first, result["stopped"])
                self.assertTrue(closed.is_set(), "Suspended generator must be closed")
                self.assertFalse(advanced.is_set(), "Target/stop must not fetch another result")

    def test_stream_network_error_preserves_the_row_already_emitted(self):
        class Collector:
            def search(self, *args):
                raise AssertionError("Worker should use the streaming API")

            def iter_search(self, *args):
                yield {"title": "第一本", "links": [{"link": "https://pan.baidu.com/s/1fixture-first", "pwd": "ab12"}]}
                raise PoolError("offline interruption")

        with tempfile.TemporaryDirectory(prefix="stream-error-") as temporary:
            logs, items = [], []
            checkpoint = Path(temporary) / "checkpoint.json"
            worker = CollectWorker(
                keyword="资源", count=2, mode="fuzzy", time_range="全部",
                fetcher=EmptyFetcher(), pool=OfflinePool(), checkpoint_path=str(checkpoint),
                on_log=logs.append, on_item=items.append, supplement_factory=lambda *_: Collector(),
            )
            # Fatal pool errors propagate to the host while the emitted rows stay resumable.
            with self.assertRaisesRegex(PoolError, "offline interruption"):
                worker.run()
            self.assertEqual(1, len(items))
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(1, saved["found"])
            self.assertEqual(items, saved["items"])
            self.assertTrue(any("补量提前结束" in message for message in logs))


if __name__ == "__main__":
    unittest.main()
