"""M18 全流程离线演示，外部请求用假实现替代。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lxds import miner, pipeline
from lxds.excelio import write_resource_table


class DemoPan:
    def __init__(self, cookie):
        assert cookie == "demo-cookie"

    def transfer_link(self, url, target, share):
        return {"status": "转存成功", "share_url": "https://pan.baidu.com/s/1demo?pwd=1234",
                "share_pwd": "1234"}


def collect(mode, keywords, category, count, out, **kwargs):
    assert Path(keywords).read_text(encoding="utf-8").strip() == "小说流光之城"
    write_resource_table(out, [{"name": "流光之城", "link": "https://pan.baidu.com/s/1source?pwd=abcd"}])
    return {"count": 1}


def main():
    with TemporaryDirectory() as directory:
        with patch.dict(miner.SOURCES, {"小说": (("演示榜单", lambda *a: ["流光之城"], False),)}), \
             patch.object(miner, "_search_supplement", return_value=[]), \
             patch.object(pipeline, "collect_file", side_effect=collect), \
             patch.object(pipeline, "PanClient", DemoPan), \
             patch.object(pipeline, "ai_generate_batch", side_effect=lambda key, rows: [
                 {"title": "求流光之城完整网盘链接下载", "answer": "<p>演示回答</p>"}]), \
             patch.object(pipeline, "publish_file", return_value={"task_id": "demo"}), \
             patch.object(pipeline, "_credentials", return_value={
                 "pan_cookie": "demo-cookie", "deepseek_key": "demo-key", "zhidao_accounts": []}):
            result = pipeline.run_pipeline({"category": "小说", "count": 1, "workdir": directory,
                                            "transfer": {"mode": "local", "target": "/演示"},
                                            "publish": {"account": "演示账号"}})
            assert result["published"]["task_id"] == "demo"
            print("离线全流程：", [p.name for p in Path(directory).glob("*")])


if __name__ == "__main__":
    main()
