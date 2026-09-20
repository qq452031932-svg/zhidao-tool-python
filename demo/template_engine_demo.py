"""独立演示 M06：本地生成标题和三段式回答，不调用真实 API。"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.template_engine import fallback_qa, post_process_row


def main() -> None:
    link = "https://pan.baidu.com/s/1AbCd?pwd=abcd"
    row = post_process_row(
        {"title": "古诗合集", "answer": f"【{link}】适合日常学习的资料。"},
        "古诗合集", link, 0,
    )
    assert row["title"] == "求古诗合集完整网盘链接下载"
    assert row["answer"].count(link) == 1
    fallback = fallback_qa("数学试卷", link, 1)
    assert "网络分享的资源" in fallback["answer"]
    print("标题校正、回答结构与本地兜底通过演示")


if __name__ == "__main__":
    main()
