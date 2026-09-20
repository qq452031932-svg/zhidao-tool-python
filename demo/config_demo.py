"""独立演示 M01：保存后由新实例读回，且不打印凭据。"""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxds.config import ConfigStore


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "config.json"
        first = ConfigStore(path)
        first.set_deepseek_key("demo-private-key")
        first.set_zhidao_accounts([{"name": "演示账号", "remark": "测试", "cookie": "demo-cookie"}])
        first.set_setting("request_gap", 8)
        first.save()

        second = ConfigStore(path)
        second.load()
        assert second.get_deepseek_key() == "demo-private-key"
        assert second.get_zhidao_accounts()[0]["cookie"] == "demo-cookie"
        assert second.get_setting("request_gap") == 8
        disk_text = path.read_text(encoding="utf-8")
        print("重新加载：成功")
        print(f"凭据未以明文出现：{'是' if 'demo-private-key' not in disk_text and 'demo-cookie' not in disk_text else '否'}")


if __name__ == "__main__":
    main()
