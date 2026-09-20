"""M15 断点存储与清理验收。"""

import os
from pathlib import Path
import time

from lxds import checkpoint


def test_save_and_load_preserves_collect_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = checkpoint.checkpoint_path("source.xlsx", "collect")
    payload = {
        "items": [{"name": "甲"}],
        "seen_keys": ["x"],
        "seen_names": ["甲"],
        "done_keywords": ["词"],
        "keywords": ["词"],
        "found": 1,
    }
    checkpoint.save(path, payload)
    assert checkpoint.load(path) == payload
    assert checkpoint.checkpoint_path("source.xlsx", "collect") == path
    assert checkpoint.checkpoint_path("other.xlsx", "collect") != path


def test_invalid_json_returns_empty_dict(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert checkpoint.load(str(path)) == {}
    assert checkpoint.load(str(tmp_path / "missing.json")) == {}


def test_prune_removes_old_files_and_keeps_newest_fifty(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    directory = Path(checkpoint.checkpoint_path("source", "collect")).parent
    directory.mkdir(parents=True)
    old = directory / "old.json"
    old.write_text("{}", encoding="utf-8")
    past = time.time() - 8 * 86400
    os.utime(old, (past, past))
    for index in range(55):
        target = directory / f"collect-{index:02}.json"
        target.write_text("{}", encoding="utf-8")
        current = time.time() - (55 - index) * 60
        os.utime(target, (current, current))
    checkpoint.prune(max_age_days=7, keep=50)
    assert not old.exists()
    assert len(list(directory.glob("*.json"))) == 50
    assert (directory / "collect-54.json").exists()
    assert not (directory / "collect-00.json").exists()


def test_operation_listing_and_clear_are_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    transfer = checkpoint.operation_path("a.xlsx", "transfer")
    template = checkpoint.operation_path("a.xlsx", "template")
    checkpoint.save(transfer, {"found": 2})
    checkpoint.save(template, {"found": 3})
    assert [item["found"] for item in checkpoint.find_operations("transfer")] == [2]
    checkpoint.clear_operations("transfer")
    assert checkpoint.load(transfer) == {}
    assert checkpoint.load(template) == {"found": 3}
    checkpoint.clear_all()
    assert checkpoint.load(template) == {}
