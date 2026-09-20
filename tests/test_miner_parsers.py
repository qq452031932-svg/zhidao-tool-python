"""M16 离线契约；样本是按安装包规则构造的合成页面。"""

import json
from pathlib import Path

import pytest

from lxds import miner_parsers as m


CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "miner_parsers" / "cases.json").read_text(
        encoding="utf-8"
    )
)
SOURCES = json.loads(
    (Path(__file__).parent / "fixtures" / "miner_parsers" / "sources.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("site", CASES)
def test_each_site_has_offline_sample(site):
    case = CASES[site]
    assert getattr(m, "parse_" + site)(case["body"]) == case["expected"]


def test_clean_and_canonical_names():
    assert m.clean_name(" 《 鬼灭之刃 第三季 》 ") == "鬼灭之刃 第三季"
    assert m.canonical_key("鬼灭之刃 第三季") == m.canonical_key("鬼灭之刃")
    assert m.canonical_key("游戏 Season 2") == m.canonical_key("游戏")
    assert m.canonical_key("云端绘图 v2.3") == m.canonical_key("云端绘图")


def test_blacklists_and_body_filter():
    assert m.is_mass_software("微信")
    assert m.is_mass_software("WPS Office 2024")
    assert not m.is_mass_software("小众剪辑器")
    assert m.is_mass_game("王者荣耀")
    assert not m.is_mass_game("雾境奇旅")
    assert [x for x in ("微信", "云端绘图") if not m.is_mass_software(x)] == ["云端绘图"]
    assert [x for x in ("王者荣耀", "雾境奇旅") if not m.is_mass_game(x)] == ["雾境奇旅"]
    assert m.looks_like_body_text("这是一段很长的网页介绍文字，描述了作者创作背景以及不同人物的故事发展和整部作品的结局")
    assert m.looks_like_body_text("一个名字。还有一句")
    assert not m.looks_like_body_text("雾境奇旅")


def test_version_strip_prd_examples():
    assert m.strip_trailing_version("Photoshop 2024 v25.0 绿色版") == "Photoshop"
    assert m.strip_trailing_version("鬼灭之刃 第三季") == "鬼灭之刃"
    assert m.strip_trailing_version("雾境奇旅（第二部）") == "雾境奇旅"


def test_global_parameters_match_prd():
    assert m.PACE_RANGE == (2.5, 4.5)
    assert m.HONG_GUO_MAX_PAGE == 5
    assert m.HISTORY_KEEP_DAYS == 7
    assert m.HISTORY_MAX_ENTRIES == 20000
    assert m.HISTORY_FILE_NAME == "挖词历史.json"
    assert m.FRESH_SOURCE_SHARE == 0.3
    assert len(m.UA_LIST) == 4


class FakeResponse:
    status_code = 200
    encoding = "latin-1"

    def __init__(self, body):
        self.content = body.encode("utf-8")
        self.text = body


class FakeSession:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        self.response = FakeResponse(self.body)
        return self.response


class FakeStop:
    def is_set(self):
        return False

    def wait(self, seconds):
        return False


def test_fetch_qimao_reuses_offline_parser_and_stops_at_need(monkeypatch):
    monkeypatch.setattr(m, "_wait", lambda sess, stop: None)
    sess = FakeSession(CASES["qimao"]["body"])
    logs = []
    assert m.fetch_qimao(sess, 1, FakeStop(), logs.append) == ["星河旅人"]
    assert len(sess.calls) == 1
    assert sess.calls[0][0].startswith("https://www.qimao.com/paihang/")
    assert sess.response.encoding == "utf-8"


def test_fetch_douban_uses_json_endpoint_and_query(monkeypatch):
    monkeypatch.setattr(m, "_wait", lambda sess, stop: None)
    sess = FakeSession(CASES["douban"]["body"])
    assert m.fetch_douban_movie_hot(sess, 1, FakeStop(), lambda _: None) == ["海边来信"]
    url, kw = sess.calls[0]
    assert url == "https://movie.douban.com/j/search_subjects"
    assert kw["params"]["type"] == "movie"
    assert kw["params"]["tag"] == "热门"
    assert kw["params"]["page_start"] == 0


def test_fetch_steam_requires_proxy(monkeypatch):
    monkeypatch.setattr(m, "_steam_proxy", lambda: "")
    sess = FakeSession(CASES["steam"]["body"])
    with pytest.raises(RuntimeError, match="代理"):
        m.fetch_steam(sess, 1, FakeStop(), lambda _: None)
    assert not sess.calls


@pytest.mark.parametrize("source,site", SOURCES.items())
def test_each_prd_source_fetches_its_offline_sample(monkeypatch, source, site):
    monkeypatch.setattr(m, "_wait", lambda sess, stop: None)
    monkeypatch.setattr(m, "_steam_proxy", lambda: "http://127.0.0.1:7890")
    sess = FakeSession(CASES[site]["body"])
    actual = getattr(m, "fetch_" + source)(sess, 1, FakeStop(), lambda _: None)
    assert actual == CASES[site]["expected"]
    assert sess.calls


def test_steam_proxy_checks_windows_system_proxy_port(monkeypatch):
    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    seen = []

    def connect(address, timeout):
        seen.append(address[1])
        if address[1] != 9999:
            raise OSError("closed")
        return Socket()

    monkeypatch.setattr(m, "getproxies", lambda: {"https": "http://127.0.0.1:9999"})
    monkeypatch.setattr(m.socket, "create_connection", connect)
    monkeypatch.setattr(m, "build_opener", lambda *_: type("Opener", (), {"open": lambda *_a, **_k: Response()})())
    assert m._steam_proxy() == "http://127.0.0.1:9999"
    assert 9999 in seen


def test_steam_proxy_ignores_malformed_system_proxy(monkeypatch):
    monkeypatch.setattr(m, "getproxies", lambda: {"https": "http://127.0.0.1:invalid"})
    monkeypatch.setattr(m.socket, "create_connection", lambda *_a, **_k: (_ for _ in ()).throw(OSError("closed")))
    assert m._steam_proxy() == ""


def test_stopped_fetch_makes_no_request(monkeypatch):
    class Stopped(FakeStop):
        def is_set(self):
            return True

    sess = FakeSession(CASES["qimao"]["body"])
    assert m.fetch_qimao(sess, 3, Stopped(), lambda _: None) == []
    assert not sess.calls


def test_fetch_entrypoints_exist_for_all_prd_sources():
    expected = (
        "qimao qimao_new zongheng faloo 17k douban_movie_hot douban_movie_new "
        "douban_movie_cn_new douban_movie_anime douban_movie_animation "
        "douban_tv_hot douban_tv_guochan douban_tv_jp douban_tv_kr douban_tv_us "
        "douban_tv_uk douban_tv_new douban_tv_anime douban_anime_new "
        "douban_short_drama douban_short_new maoyan hongguo_hot hongguo_real "
        "hongguo_ai hongguo_comic taptap taptap_new taptap_reserve steam "
        "steam_mostplayed appbao 3dm ali_rank gamersky_hot gamersky_top "
        "onlinedown onlinedown_new baoku crsky crsky_new 423down"
    ).split()
    assert all(callable(getattr(m, "fetch_" + name, None)) for name in expected)
