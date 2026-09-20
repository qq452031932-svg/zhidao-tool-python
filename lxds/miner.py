"""M17: coordinate public ranking sources into a deduplicated keyword TXT."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random
import re
from threading import Event

import requests

from lxds import miner_parsers as p
from lxds import websearch


CATEGORIES = ("小说", "电影", "电视剧", "动漫", "短剧", "游戏", "软件")
SEARCH_YEAR = 2026  # PRD 固定年份；跨年时同时检查下面的搜索模板。
PREVIOUS_SEARCH_YEAR = 2025
SOURCES = {
    "小说": (("七猫大热榜", p.fetch_qimao, False), ("七猫最新上架", p.fetch_qimao_new, True),
           ("纵横人气榜", p.fetch_zongheng, False), ("飞卢总榜", p.fetch_faloo, False), ("17K榜单", p.fetch_17k, False)),
    "电影": (("豆瓣热门", p.fetch_douban_movie_hot, False), ("豆瓣最新", p.fetch_douban_movie_new, True),
           ("豆瓣华语最新", p.fetch_douban_movie_cn_new, True), ("豆瓣动漫电影", p.fetch_douban_movie_anime, False),
           ("猫眼票房", p.fetch_maoyan, False)),
    "电视剧": (("豆瓣热门", p.fetch_douban_tv_hot, False), ("豆瓣国产", p.fetch_douban_tv_guochan, False),
             ("豆瓣日剧", p.fetch_douban_tv_jp, False), ("豆瓣韩剧", p.fetch_douban_tv_kr, False),
             ("豆瓣美剧", p.fetch_douban_tv_us, False), ("豆瓣英剧", p.fetch_douban_tv_uk, False),
             ("豆瓣最新", p.fetch_douban_tv_new, True)),
    "动漫": (("豆瓣日本动画", p.fetch_douban_tv_anime, False), ("豆瓣动漫电影", p.fetch_douban_movie_anime, False),
           ("红果漫剧", p.fetch_hongguo_comic, True), ("豆瓣动画新番", p.fetch_douban_anime_new, True)),
    "短剧": (("红果热播", p.fetch_hongguo_hot, False), ("红果真人", p.fetch_hongguo_real, False),
           ("红果AI", p.fetch_hongguo_ai, True), ("豆瓣短剧", p.fetch_douban_short_drama, False),
           ("豆瓣短剧最新", p.fetch_douban_short_new, True)),
    "游戏": (("TapTap热门", p.fetch_taptap, False), ("TapTap新品", p.fetch_taptap_new, True),
           ("TapTap预约", p.fetch_taptap_reserve, True), ("Steam热销", p.fetch_steam, False),
           ("Steam在线", p.fetch_steam_mostplayed, False), ("应用宝", p.fetch_appbao, False),
           ("3DM", p.fetch_3dm, False), ("游民热门", p.fetch_gamersky_hot, False),
           ("游民排行", p.fetch_gamersky_top, False), ("游侠排行", p.fetch_ali_rank, False)),
    "软件": (("华军热门", p.fetch_onlinedown, False), ("华军最新", p.fetch_onlinedown_new, True),
           ("360宝库", p.fetch_baoku, False), ("非凡热门", p.fetch_crsky, False),
           ("非凡最新", p.fetch_crsky_new, True), ("423Down", p.fetch_423down, True)),
}

_SEARCH_TEMPLATES = {
    "小说": ("2026年热门小说排行榜", "2026年{month}月小说人气榜", "2025年热门小说排行榜"),
    "电影": ("2026年热门电影排行榜", "2026年{month}月电影票房榜", "2025年热门电影排行榜"),
    "电视剧": ("2026年热门电视剧排行榜", "2026年{month}月电视剧热播榜", "2026年国产剧排行榜"),
    "动漫": ("2026年热门动漫排行榜", "2026年{month}月新番推荐", "2026年日本动画热门榜"),
    "短剧": ("2026年热门短剧排行榜", "2026年{month}月短剧热播榜", "2026年{month}月红果短剧热播榜",
           "2026年红果短剧热播榜", "2026最火短剧TOP10", "2026年爆款短剧名单", "2026年短剧百强榜",
           "2026年真人短剧热播榜", "2026年短剧播放量排行榜", "2025年热门短剧排行榜"),
    "游戏": ("2026年热门手游排行榜", "2026年{month}月手游下载榜", "2026年热门单机游戏", "2025年热门单机游戏",
           "2026年PC游戏热门榜", "2026年Steam热销游戏", "2026年TapTap热门游戏"),
    "软件": ("2026年热门电脑软件", "2026年常用电脑工具软件"),
}
_STOP_WORDS = ("排行榜", "榜单", "盘点", "推荐", "名单", "排名", "前十", "TOP", "No.", "2026", "2025",
               "年", "月", "日", "短剧", "手游", "游戏", "单机", "电影", "电视剧", "动漫", "小说", "软件",
               "动画", "新番", "热播", "红果", "Steam", "TapTap", "PC", "第", "第一", "第二", "第三")


def _fresh_names(category: str) -> set[str]:
    return {name for name, _, fresh in SOURCES[category] if fresh}


def _plan_quotas(category: str, target: int) -> dict[str, int]:
    if category not in CATEGORIES:
        raise ValueError(f"未知分类：{category}")
    if target < 0:
        raise ValueError("数量不能为负")
    sources = SOURCES[category]
    fresh = [name for name, _, is_fresh in sources if is_fresh]
    regular = [name for name, _, is_fresh in sources if not is_fresh]
    if not fresh or not regular:
        fresh_target = target if fresh else 0
    else:
        fresh_target = math.floor(target * p.FRESH_SOURCE_SHARE + 0.5)
    quotas = {name: 0 for name, _, _ in sources}
    for names, amount in ((fresh, fresh_target), (regular, target - fresh_target)):
        if not names:
            continue
        base, extra = divmod(amount, len(names))
        for index, name in enumerate(names):
            quotas[name] = base + (index < extra)
    return quotas


def _read_history(path: Path, keep_days: int) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    payload = payload.get("entries", payload)
    if not isinstance(payload, dict):
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    out = {}
    for key, stamp in payload.items():
        try:
            when = datetime.fromisoformat(stamp)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= cutoff:
                out[str(key)] = when.isoformat()
        except (TypeError, ValueError):
            continue
    return dict(sorted(out.items(), key=lambda entry: entry[1], reverse=True)[:p.HISTORY_MAX_ENTRIES])


def _write_history(path: Path, history: dict[str, str], keep_days: int = p.HISTORY_KEEP_DAYS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    payload = {"version": 1, "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "keep_days": keep_days, "entries": history}
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def prune_history(history_path: str, keep_days: int = 7) -> None:
    path = Path(history_path)
    if path.exists():
        _write_history(path, _read_history(path, keep_days), keep_days)


def _search_supplement(category: str, need: int, stop_event, on_log) -> list[str]:
    results = []
    month = datetime.now().month
    for template in _SEARCH_TEMPLATES[category]:
        if len(results) >= need or (stop_event is not None and stop_event.is_set()):
            break
        query = template.format(month=month)
        summary = websearch.robust_search_snippets(query, max_chars=2500)
        # 优先提取《作品名》，再接纳搜索摘要中的短编号条目。
        names = re.findall(r"《([^》]{2,30})》", summary)
        names += re.findall(r"(?:^|[；：])\s*(?:\d{1,2}[.、]\s*)?([^；：]{2,30})(?=；|$)", summary)
        results.extend(names)
        if on_log:
            on_log(f"榜单搜索 {query}：{len(names)} 个候选")
    return results


def _clean_candidate(raw: str, category: str) -> str:
    name = p.clean_name(raw)
    if category in ("游戏", "软件"):
        name = p.strip_trailing_version(name)
    if not name or p.looks_like_body_text(name):
        return ""
    if category == "游戏" and p.is_mass_game(name):
        return ""
    if category == "软件" and p.is_mass_software(name):
        return ""
    return name


def _prefix(name: str, category: str) -> str:
    return f"{category}{name}"


def collect_hot_names(category: str, target: int, save_path: str, stop_event,
                      on_log, add_prefix: bool = True, history_path: str = None,
                      history_days: int = 7, shuffle: bool = True) -> dict:
    if category not in CATEGORIES or target < 1:
        raise ValueError("分类或数量无效")
    output_path = Path(save_path)
    history_file = Path(history_path) if history_path else output_path.with_name(p.HISTORY_FILE_NAME)
    history = _read_history(history_file, history_days)
    previous = set(history)
    selected: list[str] = []
    selected_keys: set[str] = set()
    quotas = _plan_quotas(category, target)
    event = stop_event if stop_event is not None else Event()
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": random.choice(p.UA_LIST), "Accept-Language": "zh-CN,zh;q=0.9"})

    def absorb(values, *, from_search=False, limit=None):
        added = 0
        for raw in values:
            if len(selected) >= target or (limit is not None and added >= limit):
                break
            candidate = _clean_candidate(raw, category)
            if not candidate or (from_search and any(word.lower() in candidate.lower() for word in _STOP_WORDS)):
                continue
            key = f"{category}|{p.canonical_key(candidate)}"
            if not key or key in previous or key in selected_keys:
                continue
            selected.append(candidate)
            selected_keys.add(key)
            added += 1

    try:
        leftovers = []
        for name, fetch, _fresh in SOURCES[category]:
            if event.is_set() or len(selected) >= target:
                break
            need = quotas[name]
            if need <= 0:
                continue
            try:
                names = fetch(session, need, event, on_log)
                absorb(names, limit=need)
                leftovers.extend(names)
                if on_log:
                    on_log(f"{name}：新增 {len(names)} 个候选，累计 {len(selected)} 个")
            except Exception as exc:
                if on_log:
                    on_log(f"{name} 失败，跳过：{exc}")
        if not event.is_set() and len(selected) < target:
            absorb(leftovers)
        if not event.is_set() and len(selected) < target:
            for name, fetch, _fresh in SOURCES[category]:
                if event.is_set() or len(selected) >= target:
                    break
                try:
                    absorb(fetch(session, target - len(selected), event, on_log))
                except Exception as exc:
                    if on_log:
                        on_log(f"{name} 补采失败，跳过：{exc}")
        if not event.is_set() and len(selected) < target:
            try:
                absorb(_search_supplement(category, target - len(selected), event, on_log), from_search=True)
            except Exception as exc:
                if on_log:
                    on_log(f"榜单搜索补量失败：{exc}")
    finally:
        session.close()
        if shuffle:
            random.shuffle(selected)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [(_prefix(name, category) if add_prefix else name) for name in selected]
        output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        stamp = datetime.now(timezone.utc).isoformat()
        history.update({key: stamp for key in selected_keys})
        _write_history(history_file, _read_history_from_dict(history, history_days), history_days)
    stopped = event.is_set()
    return {"count": len(selected), "saved_path": str(output_path), "stopped": stopped,
            "reason": "用户停止" if stopped else ("已达到目标" if len(selected) >= target else "来源不足")}


def _read_history_from_dict(history: dict[str, str], keep_days: int) -> dict[str, str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    valid = {}
    for key, stamp in history.items():
        try:
            when = datetime.fromisoformat(stamp)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= cutoff:
                valid[key] = when.isoformat()
        except (TypeError, ValueError):
            continue
    return dict(sorted(valid.items(), key=lambda entry: entry[1], reverse=True)[:p.HISTORY_MAX_ENTRIES])
