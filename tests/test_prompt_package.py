from pathlib import Path
from hashlib import sha256


def test_packaged_prompts_are_byte_identical():
    root = Path(__file__).resolve().parents[1]
    source = root / "assets" / "prompts"
    packaged = root / "lxds" / "prompts"
    assert {p.name for p in source.glob("*.txt")} == {p.name for p in packaged.glob("*.txt")}
    for original in source.glob("*.txt"):
        assert sha256(original.read_bytes()).digest() == sha256((packaged / original.name).read_bytes()).digest()
