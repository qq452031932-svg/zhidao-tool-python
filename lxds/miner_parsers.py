"""M16: offline parsers and public ranking fetchers for keyword mining.

The parsers accept decoded HTML/JSON strings and perform no I/O. Fetchers use
the caller's Session, stop event and logger, so the M17 scheduler can isolate
failures by source. Site patterns and URLs were read from the packaged
``business.hot_names_collector``; samples are synthetic, not live captures.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import html
import json
import random
import re
import socket
import time
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener, getproxies


PACE_RANGE = (2.5, 4.5)
HONG_GUO_MAX_PAGE = 5
HISTORY_KEEP_DAYS = 7
HISTORY_MAX_ENTRIES = 20000
HISTORY_FILE_NAME = "挖词历史.json"
FRESH_SOURCE_SHARE = 0.3
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_ANCHOR_RE = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
_HEADING_RE = re.compile(r"<h([1-4])\b[^>]*>([\s\S]*?)</h\1>", re.I)
_CANON_SUFFIX = re.compile(
    r"(?:[第]?[一二三四五六七八九十百千万\d]+[季部册集]|S\d{1,3}|Season\s*\d+|\s+[vV]\d[\d.]*\w*|"
    r"\s+\d+(?:\.\d+)+\w*|\s*\d+位|x64|x86|win\d[\d\- ]*64位|win\d+|正式版|绿色版|"
    r"便携版|中文版|汉化版|破解版|免安装版|官方版|纯净版|远程控制软件|远程控制|"
    r"下载工具|下载器|播放器)$",
    re.I,
)
_SOFT_META = re.compile(
    r"[（(]\s*v?[\d.]+[^）)]*[）)]|\s+[vV]\d[\d.]*.*$|"
    r"(中文版|直装版|绿色版|便携版|正式版|破解版|汉化版|官方版|纯净版|解锁.*|"
    r"豪华版|企业版|专业版|旗舰版|增强版|标准版).*$",
    re.I,
)
_SOFT_MASS = (
    "微信", "企业微信", "QQ", "TIM", "钉钉", "飞书", "微博", "小红书", "抖音", "抖音极速版",
    "快手", "快手极速版", "虎牙", "斗鱼", "哔哩哔哩", "B站", "爱奇艺", "优酷", "腾讯视频",
    "芒果TV", "搜狐视频", "西瓜视频", "乐视", "网易云音乐", "酷狗音乐", "QQ音乐", "酷我音乐",
    "汽水音乐", "百度网盘", "阿里云盘", "夸克网盘", "115网盘", "迅雷网盘", "百度云管家",
    "迅雷", "豆包", "人人视频", "飞球直播", "360安全卫士", "360安全浏览器", "360极速浏览器",
    "360压缩", "360驱动大师", "360软件管家", "360安全桌面", "360游戏保险箱", "鲁大师",
    "金山毒霸", "2345安全卫士", "谷歌浏览器", "Google Chrome", "Microsoft Edge", "搜狗输入法",
    "百度输入法", "QQ输入法", "2345浏览器", "WPS Office", "Office365", "腾讯电脑管家",
    "人人网", "多邻国", "高途", "剪映",
)
_MASS_GAMES = (
    "王者荣耀", "王者万象棋", "和平精英", "原神", "崩坏：星穹铁道", "崩坏星穹铁道", "崩坏3",
    "蛋仔派对", "金铲铲之战", "第五人格", "阴阳师", "梦幻西游", "大话西游", "问道", "倩女幽魂",
    "明日方舟", "部落冲突", "开心消消乐", "欢乐斗地主", "欢乐麻将", "天天爱消除", "元梦之星",
    "光·遇", "光遇", "我的世界", "火影忍者", "三国志·战略版", "率土之滨", "皇室战争",
    "荒野乱斗", "使命召唤手游", "穿越火线", "地下城与勇士", "DNF", "英雄联盟手游",
    "超自然行动组", "红果免费短剧", "番茄免费小说", "元宝",
)
_GAME_HINT = (
    "红色警戒", "魔兽争霸", "反恐精英", "帝国时代", "植物大战僵尸", "欢乐斗地主", "Steam",
    "永劫无间", "地铁跑酷", "我的世界", "蛋仔派对", "英雄联盟", "王者荣耀", "和平精英",
    "原神", "崩坏", "星穹铁道", "模拟人生", "NBA 2K", "FIFA", "GTA", "鬼泣", "生化危机",
    "真三", "三国志", "赛博朋克", "巫师", "只狼", "黑神话", "艾尔登", "荒野大镖客",
    "刺客信条", "战神", "最终幻想", "文明", "怪物猎人", "明末", "上古卷轴", "宝可梦",
    "羊蹄", "死亡搁浅", "光与影", "丝之歌", "无主之地", "最后生还者", "地铁离去",
    "仁王", "剑星", "热血传奇", "梦幻西游", "大话西游", "问道", "穿越火线", "CS1.6",
    "鬼武者", "黎明行者", "星战零号连队", "元气骑士", "光·遇", "Phigros", "金铲铲",
)
_VERSION_MARKER = re.compile(
    r"(?:第[一二三四五六七八九十百千万零〇\d]+[季部卷集版]|Part\s*\.?\s*\d+|OVA|"
    r"重制版|重置版|导演剪辑版|加长版|剧场版|完整版)", re.I
)
_VERSION_BRACKET = re.compile(
    r"[（(]\s*(?:第[一二三四五六七八九十百千万\d]+[季部卷集版]|S\d{1,3})\s*[）)]\s*$", re.I
)
_TRAIL_NUM = re.compile(r"(?:[\s·\-—]*\d+\s*)$")
_MAX_NAME_LEN = 30


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", _SCRIPT_RE.sub("", fragment))).replace("\xa0", " ")).strip()


def clean_name(raw: str) -> str:
    t = (raw or "").strip().replace("\u3000", " ").replace("\xa0", " ")
    t = re.sub(r"[\u200b-\u200f\ufeff]", "", t)
    for left, right in (("《", "》"), ("「", "」"), ("『", "』"), ("【", "】"), ("[", "]"), ("(", ")")):
        if t.startswith(left) and t.endswith(right) and len(t) > 2:
            t = t[len(left):-len(right)]
            break
    t = re.sub(r"\s+", " ", t).strip()
    t = _SOFT_META.sub(" ", t)
    t = re.sub(r"[\s\-—]*第[0-9一二三四五六七八九十百千万]+集\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip(" |·")


def canonical_key(name: str) -> str:
    n = (name or "").strip().lower()
    while True:
        shorter = _CANON_SUFFIX.sub("", n).rstrip(" -—·._")
        if shorter == n:
            return re.sub(r"\s+", "", n)
        n = shorter


def is_mass_software(name: str) -> bool:
    n = (name or "").lower()
    return any(w.lower() in n for w in _SOFT_MASS + _GAME_HINT) or "游戏" in n or bool(
        re.search(r"(聊天|社交|即时通讯|短视频|直播|浏览器|输入法|杀毒软件|安全卫士)$", n)
    )


def is_mass_game(name: str) -> bool:
    n = (name or "").lower()
    return any(w.lower() in n for w in _MASS_GAMES)


def strip_trailing_version(name: str) -> str:
    t = _VERSION_BRACKET.sub("", (name or "").strip())
    marker = _VERSION_MARKER.search(t)
    if marker:
        t = t[:marker.start()]
    t = re.sub(r"\s+[vV]\d[\d.]*\w*.*$", "", t)
    t = re.sub(r"(?:正式版|绿色版|便携版|中文版|汉化版|破解版|免安装版|官方版|纯净版).*$", "", t)
    t = re.sub(r"\s+\d{4}(?=\s*$)", "", t)
    t = _TRAIL_NUM.sub("", t)
    return re.sub(r"\s+", " ", t).strip(" -—：:；，。！？·、")


def looks_like_body_text(name: str) -> bool:
    t = (name or "").strip()
    return not t or len(t) > _MAX_NAME_LEN or "。" in t


def _unique(values):
    return list(dict.fromkeys(x for x in values if x))


def _anchors(body: str, href_pattern: str, *, limit: int | None = None, exclusions=()) -> list[str]:
    out = []
    for match in _ANCHOR_RE.finditer(body):
        href, name = match.group(1), _plain(match.group(2))
        if not re.search(href_pattern, href, re.I) or not name:
            continue
        if limit is not None and len(name) > limit:
            continue
        if any(word in name for word in exclusions):
            continue
        out.append(name)
    return _unique(out)


def parse_qimao(body: str) -> list[str]:
    return _unique(_plain(m.group(1)) for m in re.finditer(r'class="s-book-title"[^>]*>(.*?)</a>', body, re.I | re.S))


def parse_zongheng(body: str) -> list[str]:
    return _anchors(body, r"/detail/")


def parse_faloo(body: str) -> list[str]:
    return _anchors(body, r"/\d{5,}\.html$")


def parse_17k(body: str) -> list[str]:
    return _anchors(body, r"17k\.com/book/\d+\.html$")


def parse_douban(body: str) -> list[str]:
    try:
        return _unique(str(item.get("title") or "").strip() for item in json.loads(body).get("subjects", []))
    except (ValueError, TypeError, AttributeError):
        return []


def parse_maoyan(body: str) -> list[str]:
    start = body.find('id="ranks-list"')
    if start < 0:
        return []
    return _unique(_plain(m.group(1)) for m in re.finditer(r'<p\s+class="first-line"[^>]*>(.*?)</p>', body[start:], re.I | re.S))


def parse_hongguo(body: str) -> list[str]:
    out = []
    for match in re.finditer(r'(?:title|alt)="([^"]{1,80})"', body):
        name = html.unescape(match.group(1)).strip()
        if name.endswith("封面"):
            name = name[:-2].strip()
        if not name or any(x in name.lower() for x in ("logo", "二维码", "红果短剧app")):
            continue
        if re.search(r"[\u4e00-\u9fff]", name):
            out.append(name)
    return _unique(out)


def parse_taptap(body: str) -> list[str]:
    out = []
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    for match in re.finditer(pattern, body, re.I | re.S):
        try:
            data = json.loads(html.unescape(match.group(1)))
            if not isinstance(data, dict) or data.get("@type") != "ItemList":
                continue
            items = data.get("itemListElement") or []
            try:
                items = sorted(items, key=lambda x: int(x.get("position", 0)))
            except (ValueError, TypeError, AttributeError):
                pass
            out.extend(str(item.get("name") or "").strip() for item in items if isinstance(item, dict))
        except (ValueError, TypeError):
            continue
    return _unique(out)


def parse_steam_rows(body: str) -> list[str]:
    row_re = re.compile(r'<td[^>]*><a[^>]*href="https://store\.steampowered\.com/app/\d+/[^"]*"[^>]*>(.*?)</a></td>', re.I | re.S)
    out = []
    for row in row_re.finditer(body):
        title = re.search(r'<div[^>]*>\s*([^<]{2,80}?)\s*</div>', row.group(1), re.S)
        if title:
            out.append(_plain(title.group(1)))
    return _unique(out)


def parse_steam(body: str) -> list[str]:
    return parse_steam_rows(body)


def parse_appbao(body: str) -> list[str]:
    out = []
    for pattern in (
        r'<div[^>]*title="([^"]{1,40})"[^>]*class="[^"]*GameCard_name[^"]*"[^>]*>',
        r'<div[^>]*class="[^"]*GameCard_name[^"]*"[^>]*>([^<]{1,40})</div>',
    ):
        out.extend(_plain(m.group(1)) for m in re.finditer(pattern, body, re.I))
        if out:
            break
    return _unique(out)


def parse_3dm(body: str) -> list[str]:
    return _anchors(body, r"3dmgame\.com/games/[a-z0-9]+/?$", limit=36, exclusions=("首页", "专区", "游戏", "单机", "更多"))


def parse_ali_rank(body: str) -> list[str]:
    return _anchors(body, r"ali213\.(net|com)/(?:zt|pcgame)/", limit=36, exclusions=("首页", "专区", "游戏", "单机", "下载", "更多", "排行榜"))


_GAMERSKY_EXCLUDE = ("更多", "下载", "首页", "排行", "专题", "专区", "游戏", "软件", "新作", "推荐", "更新", "资讯", "评测", "攻略", "汉化", "补丁", "存档", "工具", "音乐", "地图", "发售")


def _gamersky_names(body: str, marker: str) -> list[str]:
    at = body.find(marker)
    if at < 0:
        return []
    segment = body[at:at + 22000]
    return [name for name in _anchors(segment, r".", limit=40, exclusions=_GAMERSKY_EXCLUDE) if len(name) >= 2 and re.search(r"[\u4e00-\u9fff]", name)]


def parse_gamersky_hot(body: str) -> list[str]:
    return _gamersky_names(body, "热门单机")


def parse_gamersky_top(body: str) -> list[str]:
    return _anchors(body, r"gamersky.com/z/", limit=40, exclusions=("更多", "首页", "排行", "专题", "专区", "游戏", "软件", "新作", "推荐", "资讯", "评测", "攻略", "汉化", "补丁", "下载"))


def parse_onlinedown(body: str) -> list[str]:
    return _anchors(body, r"/soft/\d+\.htm$", exclusions=("查看", "更多", "详情"))


def parse_baoku(body: str) -> list[str]:
    out = []
    for match in _ANCHOR_RE.finditer(body):
        if re.search(r"/[a-z]{3,6}/\d+\.html$", match.group(1), re.I):
            title = _plain(match.group(2))
            out.append(re.split(r"\s+\d+(?:\.\d+)?分", title, maxsplit=1)[0].strip())
    return _unique(out)


def parse_crsky(body: str) -> list[str]:
    return _anchors(body, r"/soft/\d+\.html$")


def parse_423down(body: str) -> list[str]:
    out = []
    for match in _HEADING_RE.finditer(body):
        title = _plain(match.group(2))
        if len(title) < 4 or any(x in title for x in ("首页", "下载排行", "软件分类", "热门", "关于", "联系")):
            continue
        title = re.sub(r"[\s\-—]+$", "", title.split("|", 1)[0].strip())
        out.append(title)
    return _unique(out)


def _force_utf8(response) -> None:
    response.encoding = "utf-8"


def _wait(sess, stop_event) -> None:
    if stop_event is not None and stop_event.is_set():
        return
    last = getattr(sess, "_rt_last", 0.0)
    gap = getattr(sess, "_rt_gap", 0.0)
    left = max(0.0, gap - (time.monotonic() - last)) if last else 0.0
    if left and stop_event is not None and hasattr(stop_event, "wait"):
        stop_event.wait(left)
    else:
        while left > 0 and not (stop_event is not None and stop_event.is_set()):
            step = min(left, 0.25)
            time.sleep(step)
            left -= step
    sess._rt_last = time.monotonic()
    sess._rt_gap = random.uniform(*PACE_RANGE)


def _get(sess, url: str, stop_event=None, headers=None, params=None, timeout=25):
    _wait(sess, stop_event)
    if stop_event is not None and stop_event.is_set():
        raise RuntimeError("已停止")
    merged = dict(getattr(sess, "headers", {}))
    if headers:
        merged.update(headers)
    response = sess.get(url, params=params, headers=merged, timeout=timeout, allow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}")
    _force_utf8(response)
    return response


def _fetch_pages(sess, need, stop_event, on_log, urls, parse, *, label="来源", headers=None):
    out, errors = [], []
    for index, url in enumerate(urls, 1):
        if len(out) >= need or (stop_event is not None and stop_event.is_set()):
            break
        for attempt in (1, 2):
            try:
                names = parse(_get(sess, url, stop_event=stop_event, headers=headers).text)
                if on_log:
                    on_log(f"{label} 页 {index} 解析到 {len(names)} 个候选")
                out.extend(name for name in names if name not in out)
                sink = getattr(sess, "_absorb_page", None)
                if sink and sink(names):
                    return out
                break
            except Exception as exc:
                if attempt == 1 and on_log:
                    on_log(f"{label} 页 {index} 第 1 次失败（将重试）：{exc}")
                if attempt == 1 and not (stop_event is not None and stop_event.is_set()):
                    if stop_event is not None and hasattr(stop_event, "wait"):
                        stop_event.wait(3)
                    else:
                        time.sleep(3)
                else:
                    errors.append(f"{label} 页 {index}: {exc}")
                    if on_log:
                        on_log(f"{label} 页 {index} 失败：{exc}")
    if not out and errors:
        raise RuntimeError("；".join(errors))
    return out


def fetch_qimao(sess, need, stop_event, on_log):
    urls = tuple(f"https://www.qimao.com/paihang/{gender}/{kind}/{period}/" for kind in ("hot", "collect") for period in ("date", "month") for gender in ("boy", "girl"))
    return _fetch_pages(sess, need, stop_event, on_log, urls, parse_qimao, label="七猫大热榜")


def fetch_qimao_new(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, (f"https://www.qimao.com/paihang/{gender}/new/date/" for gender in ("boy", "girl")), parse_qimao, label="七猫最新上架")


def fetch_zongheng(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.zongheng.com/rank",), parse_zongheng, label="纵横人气榜")


def fetch_faloo(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, (f"https://b.faloo.com/Rank_{n}.html" for n in range(1, 7)), parse_faloo, label="飞卢总榜")


def fetch_17k(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.17k.com/top/",), parse_17k, label="17K榜单")


def fetch_douban(sess, need, stop_event, on_log, typ, tag, *, sort="recommend", max_pages=20):
    out = []
    for page in range(max_pages):
        if len(out) >= need or (stop_event is not None and stop_event.is_set()):
            break
        params = {"type": typ, "tag": tag, "sort": sort, "page_limit": min(50, max(1, need)), "page_start": page * 50}
        try:
            resp = _get(sess, "https://movie.douban.com/j/search_subjects", stop_event, headers={"Referer": "https://movie.douban.com/"}, params=params)
            names = parse_douban(resp.text)
        except Exception:
            if out:
                break
            raise
        if on_log:
            on_log(f"豆瓣 {tag} 第 {page + 1} 页解析到 {len(names)} 个候选")
        if not names:
            if out:
                break
            raise RuntimeError(f"豆瓣 {tag} 返回空列表（疑似限流或标签无数据）")
        out.extend(name for name in names if name not in out)
        sink = getattr(sess, "_absorb_page", None)
        if sink and sink(names):
            break
    return out


def fetch_douban_movie_hot(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "movie", "热门")


def fetch_douban_movie_new(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "movie", "热门", sort="time")


def fetch_douban_movie_cn_new(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "movie", "华语", sort="time")


def fetch_douban_movie_anime(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "movie", "动漫")


def fetch_douban_movie_animation(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "movie", "动画")


def fetch_douban_tv_hot(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "热门")


def fetch_douban_tv_guochan(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "国产剧")


def fetch_douban_tv_jp(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "日剧")


def fetch_douban_tv_kr(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "韩剧")


def fetch_douban_tv_us(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "美剧")


def fetch_douban_tv_uk(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "英剧")


def fetch_douban_tv_new(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "热门", sort="time")


def fetch_douban_tv_anime(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "日本动画")


def fetch_douban_anime_new(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "tv", "日本动画", sort="time")


def fetch_douban_short_drama(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "movie", "短剧")


def fetch_douban_short_new(sess, need, stop_event, on_log):
    return fetch_douban(sess, need, stop_event, on_log, "movie", "短剧", sort="time")


def fetch_maoyan(sess, need, stop_event, on_log):
    url = f"https://piaofang.maoyan.com/rankings/year?year={date.today().year}"
    return _fetch_pages(sess, need, stop_event, on_log, (url,), parse_maoyan, label="猫眼票房")


def fetch_hongguo(sess, need, stop_event, on_log, rank="hot-drama"):
    urls = (f"https://hongguoduanju.com/rank/{rank}?page={page}" for page in range(1, HONG_GUO_MAX_PAGE + 1))
    return _fetch_pages(sess, need, stop_event, on_log, urls, parse_hongguo, label="红果")


def fetch_hongguo_hot(sess, need, stop_event, on_log):
    return fetch_hongguo(sess, need, stop_event, on_log, "hot-drama")


def fetch_hongguo_real(sess, need, stop_event, on_log):
    return fetch_hongguo(sess, need, stop_event, on_log, "hot-real-drama")


def fetch_hongguo_ai(sess, need, stop_event, on_log):
    return fetch_hongguo(sess, need, stop_event, on_log, "hot-ai-drama")


def fetch_hongguo_comic(sess, need, stop_event, on_log):
    return fetch_hongguo(sess, need, stop_event, on_log, "hot-comic-drama")


def fetch_taptap(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.taptap.cn/top/download",), parse_taptap, label="TapTap热门榜")


def fetch_taptap_new(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.taptap.cn/top/new",), parse_taptap, label="TapTap新品榜")


def fetch_taptap_reserve(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.taptap.cn/top/reserve",), parse_taptap, label="TapTap预约榜")


def _steam_proxy() -> str:
    """Return a verified local HTTP proxy URL or empty string."""
    ports = [7890, 7891, 7897]
    for configured in getproxies().values():
        try:
            parsed = urlparse(configured if "://" in configured else "http://" + configured)
            port = parsed.port
        except ValueError:
            continue
        if parsed.hostname in ("127.0.0.1", "localhost") and port and port not in ports:
            ports.append(port)
    for port in ports:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                pass
            proxy = f"http://127.0.0.1:{port}"
            opener = build_opener(ProxyHandler({"http": proxy, "https": proxy}))
            with opener.open(Request("https://zhidao.baidu.com/robots.txt"), timeout=3) as response:
                if response.status in (200, 204):
                    return proxy
        except (OSError, ValueError):
            continue
    return ""


@contextmanager
def _use_proxy(sess, proxy):
    previous = getattr(sess, "proxies", None)
    sess.proxies = {"http": proxy, "https": proxy}
    try:
        yield
    finally:
        sess.proxies = previous


def fetch_steam(sess, need, stop_event, on_log):
    proxy = _steam_proxy()
    if not proxy:
        raise RuntimeError("未检测到本地代理（Clash 未开启），跳过")
    with _use_proxy(sess, proxy):
        return _fetch_pages(sess, need, stop_event, on_log, ("https://store.steampowered.com/charts/topselling/?l=schinese",), parse_steam, label="Steam最畅销")


def fetch_steam_mostplayed(sess, need, stop_event, on_log):
    proxy = _steam_proxy()
    if not proxy:
        raise RuntimeError("未检测到本地代理（Clash 未开启），跳过")
    with _use_proxy(sess, proxy):
        return _fetch_pages(sess, need, stop_event, on_log, ("https://store.steampowered.com/charts/mostplayed/?l=schinese",), parse_steam_rows, label="Steam在线榜")


def fetch_appbao(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://sj.qq.com/myapp/android/hot.htm",), parse_appbao, label="应用宝热门榜")


def fetch_3dm(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.3dmgame.com/games/",), parse_3dm, label="3DM单机库")


def fetch_ali_rank(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.ali213.net/paihb.html",), parse_ali_rank, label="游侠热门单机榜")


def fetch_gamersky_hot(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://down.gamersky.com/index.shtml",), parse_gamersky_hot, label="游民下载中心热门单机")


def fetch_gamersky_top(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.gamersky.com/top/",), parse_gamersky_top, label="游民单机排行榜")


def fetch_onlinedown(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.onlinedown.net/hits/",), parse_onlinedown, label="华军下载排行")


def fetch_onlinedown_new(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.onlinedown.net/new/",), parse_onlinedown, label="华军最新更新")


def fetch_baoku(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://baoku.360.cn/rmph/",), parse_baoku, label="360热门排行")


def fetch_crsky(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.crsky.com/top/",), parse_crsky, label="非凡软件TOP")


def fetch_crsky_new(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.crsky.com/new/",), parse_crsky, label="非凡最新更新")


def fetch_423down(sess, need, stop_event, on_log):
    return _fetch_pages(sess, need, stop_event, on_log, ("https://www.423down.com/",), parse_423down, label="423Down近期软件")
