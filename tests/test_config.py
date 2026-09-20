"""M01 配置持久化的验收测试。"""

import json
import os
import subprocess
import sys

import pytest

from lxds.config import ConfigStore


def test_credentials_survive_new_process_and_are_encrypted(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.set_deepseek_key("secret-deepseek-key")
    store.set_zhidao_accounts([{"name": "知道甲", "remark": "主号", "cookie": "secret-zhidao-cookie"}])
    store.set_pan_accounts([{"name": "网盘甲", "cookie": "secret-pan-cookie"}])
    store.set_setting("gap", 8)
    store.save()

    raw = path.read_text(encoding="utf-8")
    assert "secret-deepseek-key" not in raw
    assert "secret-zhidao-cookie" not in raw
    assert "secret-pan-cookie" not in raw
    data = json.loads(raw)
    if sys.platform == "win32":
        assert data["deepseek_key"].startswith("dpapi:")
        assert data["zhidao_accounts"][0]["cookie"].startswith("dpapi:")
        assert data["pan_accounts"][0]["cookie"].startswith("dpapi:")

    code = (
        "import json, sys; from lxds.config import ConfigStore; "
        "s=ConfigStore(sys.argv[1]); s.load(); "
        "print(json.dumps([s.get_deepseek_key(), s.get_zhidao_accounts(), "
        "s.get_pan_accounts(), s.get_setting('gap')], ensure_ascii=False))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        cwd=os.getcwd(), capture_output=True, text=True, check=True,
    )
    values = json.loads(result.stdout)
    assert values == [
        "secret-deepseek-key",
        [{"name": "知道甲", "remark": "主号", "cookie": "secret-zhidao-cookie"}],
        [{"name": "网盘甲", "cookie": "secret-pan-cookie"}],
        8,
    ]


def test_save_reports_write_failure(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / "config.json")
    store.set_deepseek_key("key")

    def deny_replace(*args, **kwargs):
        raise PermissionError("目标目录不可写")

    monkeypatch.setattr("lxds.config.os.replace", deny_replace)
    with pytest.raises(PermissionError, match="目标目录不可写"):
        store.save()


def test_save_verifies_persisted_content(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / "config.json")
    store.set_setting("count", 3)

    def wrong_data(self):
        return {"settings": {"count": 4}}

    monkeypatch.setattr(ConfigStore, "_read_persisted", wrong_data)
    with pytest.raises(OSError, match="配置写入校验失败"):
        store.save()


def test_getters_do_not_expose_mutable_internal_state(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.set_zhidao_accounts([{"name": "甲", "cookie": "cookie"}])
    store.set_setting("options", {"retry": 2})
    store.get_zhidao_accounts()[0]["cookie"] = "changed"
    store.get_setting("options")["retry"] = 9
    assert store.get_zhidao_accounts()[0]["cookie"] == "cookie"
    assert store.get_setting("options")["retry"] == 2
