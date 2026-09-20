"""把资源名称与网盘链接生成百度知道问题标题和三段式回答。"""

from __future__ import annotations

import html
import json
from pathlib import Path
import re
import time

from lxds.deepseek import chat
from lxds.websearch import robust_search_snippets
from lxds.zhidao_parse import strip_spam_letters


_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "template_system_prompt.txt"
_PAIRS = (
    ("求", "完整网盘链接下载"),
    ("求", "完整网盘链接获取"),
    ("哪里有", "完整网盘资源链接"),
    ("跪求", "百度网盘链接获取"),
    ("求", "百度网盘链接下载"),
    ("谁有", "百度网盘资源链接"),
)
_TYPE_WORDS = re.compile(
    r"(?:游戏|单机|破解|手游|网游|小说|全本|精校|txt|电影|电视剧|综艺|纪录|动漫|动画|番剧|"
    r"课件|教案|讲义|习题|练习册|试卷|试题|题库|真题|模拟题|拼音|识字|数学|语文|英语|古诗|"
    r"成语|绘本|故事|儿歌|童谣|描红|字帖|手工|折纸|绘画|涂色|教程|课程|讲座|公开课|软件|"
    r"工具|模板|素材|合集|汇总|大全|全集|全套|字典|词典|百科|手册|指南|攻略|电子书|视频|"
    r"音频|音乐|幼小衔接|启蒙|早教|作业本|打卡|计算|思维|阅读|作文|写字|算术|复习|预习|教学|计划)",
    re.I,
)
_EXTENSION = re.compile(r"\.(xlsx|xls|doc|docx|pdf|txt|epub|mobi|mp4|mp3|zip|rar|7z|apk|exe|iso|ppt|pptx)$", re.I)
_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffd]")
_BRACKETS = re.compile(r"[【】\[\]{}()（）]")
_ANCHOR = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>[\s\S]*?</a>", re.I)
_TAGS = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://[^\s<>\"'，。；、）】｝」》]+", re.I)
_FALLBACK_INTRO = (
    "《{name}》是一份网络分享的资源，本资源由百度网盘分享，点击上方链接即可转存获取。\n"
    "下载后即可使用，如有疑问欢迎在评论区留言交流。"
)
_RETRY_WAITS = (3, 6, 12)


def should_search(name: str) -> bool:
    """名称已有类型词时，不再额外联网搜资料。"""
    return _TYPE_WORDS.search(name) is None


def _clean_name(name: str) -> str:
    name = strip_spam_letters(name)
    name = re.sub(r"^\d+[_.\-\s]+", "", name)
    name = _EXTENSION.sub("", name)
    name = _CONTROL.sub("", name)
    name = _BRACKETS.sub("", name)
    return name.strip()


def build_title(resource_name: str, index: int) -> str:
    """按 index%6 固定轮询前后缀，超过 49 字仅截资源名末尾。"""
    prefix, suffix = _PAIRS[index % len(_PAIRS)]
    name = _clean_name(resource_name)
    allowed = 49 - len(prefix) - len(suffix)
    return prefix + name[:allowed] + suffix


def enforce_title_format(title: str, index: int) -> str:
    """剥离 AI 可能给出的错配前后缀，再重新套固定组合。"""
    name = title.strip().rstrip("？?！!。")
    for prefix, _ in sorted(_PAIRS, key=lambda pair: len(pair[0]), reverse=True):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    for _, suffix in sorted(_PAIRS, key=lambda pair: len(pair[1]), reverse=True):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return build_title(name, index)


def strip_link_wrappers(value: str) -> str:
    """剥掉链接外常见的中文和英文包裹符。"""
    return value.strip().strip('【】[]()（）"“”「」\' ')


def unwrap_anchor_tags(value: str) -> str:
    """把 AI 输出的 HTML 锚点还原为裸链接。"""
    return _ANCHOR.sub(lambda match: html.unescape(match.group(1)), value)


def normalize_answer(raw: str, link: str, resource_name: str) -> str:
    """强制回答为三段 HTML，第二段仅有裸链接、第三段无链接。"""
    unwrapped = unwrap_anchor_tags(raw)
    text = html.unescape(_TAGS.sub(" ", unwrapped))
    text = _URL.sub(" ", text)
    text = re.sub(r"点击链接获取完整素材[：:]?", " ", text)
    text = strip_link_wrappers(text)
    intro = re.sub(r"\s+", " ", text).strip(" ：:，,;；-—")
    if not intro:
        intro = _FALLBACK_INTRO.format(name=resource_name)
    intro = intro[:200]
    return _format_answer(intro, link)


def _format_answer(intro: str, link: str) -> str:
    bare_link = strip_link_wrappers(link)
    return f"<p><strong>点击链接获取完整素材：</strong><br/></p><p>{bare_link}<br/></p><p>{intro}</p>"


def fallback_qa(name: str, link: str, index: int) -> dict:
    """任何整批 AI 异常都回退到本地模板，绝不丢行。"""
    return {
        "name": name, "link": link, "index": index,
        "title": build_title(name, index),
        "answer": _format_answer(_FALLBACK_INTRO.format(name=name), link),
    }


def post_process_row(ai_row: dict, name: str, link: str, index: int) -> dict:
    """对 AI 输出再次做本地强校正。"""
    title = enforce_title_format(str(ai_row.get("title") or name), index)
    answer = normalize_answer(str(ai_row.get("answer") or ""), link, name)
    return {"name": name, "link": link, "index": index, "title": title, "answer": answer}


def _parse_ai_rows(content: str) -> list[dict]:
    cleaned = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.I)
    if fenced:
        cleaned = fenced.group(1)
    payload = json.loads(cleaned)
    rows = payload["rows"]
    if not isinstance(rows, list):
        raise ValueError("AI rows 不是列表")
    return rows


def ai_generate_batch(
    api_key: str, rows: list[dict], backoff: float = 0,
    search_map: dict | None = None,
) -> list[dict]:
    """整批请求 DeepSeek；网络、JSON、数量或顺序异常均整批兜底。"""
    if not rows:
        return []
    source = [(row["name"], row["link"], int(row.get("index", offset))) for offset, row in enumerate(rows)]
    fallback = [fallback_qa(name, link, index) for name, link, index in source]
    try:
        prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        payload = []
        for name, link, index in source:
            skip = not should_search(name)
            search = "" if skip else (
                search_map.get(name, "") if search_map is not None else robust_search_snippets(name)
            )
            payload.append({"index": index, "name": name, "link": link, "search": search, "skip_search": skip})
        if backoff > 0:
            time.sleep(backoff)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps({"rows": payload}, ensure_ascii=False)},
        ]
        for attempt in range(len(_RETRY_WAITS) + 1):
            try:
                content = chat(api_key, messages, max_tokens=6000, json_mode=True, timeout=180)
                ai_rows = _parse_ai_rows(content)
                if len(ai_rows) != len(source):
                    raise ValueError("AI rows 数量不匹配")
                if any(not isinstance(item, dict) or item.get("index") != index for item, (_, _, index) in zip(ai_rows, source)):
                    raise ValueError("AI rows 顺序不匹配")
                return [post_process_row(item, name, link, index) for item, (name, link, index) in zip(ai_rows, source)]
            except Exception:
                if attempt == len(_RETRY_WAITS):
                    break
                time.sleep(_RETRY_WAITS[attempt])
    except Exception:
        pass
    return fallback
