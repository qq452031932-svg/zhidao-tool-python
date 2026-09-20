"""M18: command line entry points and persisted pipeline steps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from threading import Event

from lxds.collect import CollectWorker
from lxds.config import ConfigStore
from lxds.excelio import build_publish_workbook_bytes, read_resource_table, write_resource_table
from lxds.miner import CATEGORIES, collect_hot_names
from lxds.pan_share import PanClient
from lxds.qa import generate_answer
from lxds.template_engine import ai_generate_batch
from lxds.zhidao_bulk import upload_file


def _scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.lower() in ("null", "none"):
        return None
    try:
        return int(value)
    except ValueError:
        return value


def _without_comment(value: str) -> str:
    quote = None
    for index, char in enumerate(value):
        if char in "\"'":
            quote = None if quote == char else (char if quote is None else quote)
        elif char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value


def load_pipeline_config(path: str) -> dict:
    """Read the simple nested mapping needed by pipeline.yaml or a JSON object."""
    body = Path(path).read_text(encoding="utf-8-sig")
    if body.lstrip().startswith("{"):
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("流水线配置根节点必须是对象")
        return payload
    root: dict = {}
    parents = [(0, root)]
    for number, raw in enumerate(body.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[:len(raw) - len(raw.lstrip())]:
            raise ValueError(f"第 {number} 行不能使用制表符缩进")
        indent = len(raw) - len(raw.lstrip())
        if ":" not in raw:
            raise ValueError(f"第 {number} 行缺少冒号")
        key, value = raw.strip().split(":", 1)
        value = _without_comment(value)
        key = key.strip()
        if not key or key.startswith("-"):
            raise ValueError(f"第 {number} 行键名无效")
        while parents and indent < parents[-1][0]:
            parents.pop()
        if not parents or indent != parents[-1][0]:
            raise ValueError(f"第 {number} 行缩进无效")
        parent = parents[-1][1]
        if key in parent:
            raise ValueError(f"第 {number} 行键名重复：{key}")
        if value.strip() == "":
            child = {}
            parent[key] = child
            parents.append((indent + 2, child))
        else:
            parent[key] = _scalar(value)
    return root


def _credentials() -> dict:
    store = ConfigStore()
    store.load()
    pan_accounts = store.get_pan_accounts()
    return {
        "deepseek_key": store.get_deepseek_key(),
        "pan_accounts": pan_accounts,
        "pan_cookie": pan_accounts[0].get("cookie", "") if pan_accounts else "",
        "zhidao_accounts": store.get_zhidao_accounts(),
    }


def _account_cookie(accounts: list[dict], name: str) -> str:
    for account in accounts:
        if account.get("name") == name:
            return str(account.get("cookie") or "")
    raise ValueError(f"未找到账号：{name}")


def mine_file(category: str, count: int, out: str, *, history_path=None,
              add_prefix=True) -> dict:
    return collect_hot_names(category, count, out, Event(), None,
                             add_prefix=add_prefix, history_path=history_path)


def collect_file(mode: str, keywords: str | None, category: str | None,
                 count: int, out: str, *, accounts=None, resume=False) -> dict:
    if mode == "precise" and not keywords:
        raise ValueError("精准采集需要 --keywords")
    if mode == "fuzzy" and not category:
        raise ValueError("模糊采集需要 --category")
    worker = CollectWorker(mode=mode, txt_paths=keywords if mode == "precise" else None,
                           keyword=category if mode == "fuzzy" else None,
                           count=count, accounts=accounts or [], resume=resume)
    result = worker.run()
    write_resource_table(out, result["items"])
    return {"count": result["found"], "saved_path": out,
            "stopped": result["stopped"], "stats": result["stats"]}


def transfer_file(source: str, out: str, target: str, share: bool,
                  cookie: str) -> dict:
    if not cookie:
        raise ValueError("请先在配置中保存百度网盘 Cookie")
    rows, skipped = read_resource_table(source)
    client = PanClient(cookie)
    output = []
    outcomes = []
    for row in rows:
        result = client.transfer_link(row["link"], target, share)
        outcomes.append({"name": row["name"], **result})
        if share and result.get("share_url"):
            output.append({"name": row["name"], "link": result["share_url"],
                           "pwd": result.get("share_pwd", "")})
        elif not share and result.get("status") in ("转存成功", "重复跳过"):
            output.append({"name": row["name"], "link": row["link"]})
    write_resource_table(out, output)
    return {"count": len(output), "saved_path": out, "skipped": skipped, "outcomes": outcomes}


def template_file(source: str, out: str, api_key: str) -> dict:
    if not api_key:
        raise ValueError("请先在配置中保存 DeepSeek API Key")
    rows, skipped = read_resource_table(source)
    generated = ai_generate_batch(api_key, rows)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(build_publish_workbook_bytes(generated))
    return {"count": len(generated), "saved_path": out, "skipped": skipped}


def publish_file(source: str, account: str) -> dict:
    credentials = _credentials()
    cookie = _account_cookie(credentials["zhidao_accounts"], account)
    if not cookie:
        raise ValueError("所选知道账号 Cookie 为空")
    path = Path(source)
    return upload_file(cookie, path.name, path.read_bytes(), path.stem)


def answer_question(question: str, style: str = "first_person") -> str:
    key = _credentials()["deepseek_key"]
    if not key:
        raise ValueError("请先在配置中保存 DeepSeek API Key")
    return generate_answer(key, question, style)


def _wait_external(path: Path, timeout: float, poll: float, *,
                   after_ns: int = 0, result_glob: str | None = None) -> Path:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        candidates = [path]
        if result_glob:
            candidates.extend(path.parent.glob(result_glob))
        ready = [item for item in candidates if item.is_file() and
                 item.stat().st_size > 0 and item.stat().st_mtime_ns > after_ns]
        if ready:
            return max(ready, key=lambda item: item.stat().st_mtime_ns)
        time.sleep(poll)
    raise TimeoutError(f"等待 C# 转存结果超时：{path}")


def external_transfer(source: str, out: str, inbox: str, outbox: str,
                      timeout: float = 1800, result_name: str | None = None,
                      result_glob: str = "*转存分享结果*.xlsx") -> dict:
    in_dir, out_dir = Path(inbox), Path(outbox)
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_path = Path(source)
    sent = in_dir / source_path.name
    # outbox 文件须由本次任务新生成；不能误读旧结果。
    before = (out_dir / (result_name or source_path.name))
    started_ns = time.time_ns()
    shutil.copy2(source_path, sent)
    produced = _wait_external(before, timeout, 1.0, after_ns=started_ns,
                              result_glob=result_glob)
    rows, skipped = read_resource_table(str(produced))
    write_resource_table(out, rows)
    return {"count": len(rows), "saved_path": out, "sent_path": str(sent),
            "received_path": str(produced), "skipped": skipped}


def run_pipeline(config: dict) -> dict:
    category = str(config.get("category") or "")
    if category not in CATEGORIES:
        raise ValueError("流水线配置需要有效的 category")
    count = int(config.get("count") or 0)
    if count <= 0:
        raise ValueError("流水线配置需要正整数 count")
    workdir = Path(config.get("workdir") or ".").resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    keywords = workdir / "keywords.txt"
    collected = workdir / "collected.xlsx"
    transferred = workdir / "transferred.xlsx"
    qa = workdir / "qa.xlsx"
    credentials = _credentials()
    summary = {}
    summary["mined"] = mine_file(category, count, str(keywords),
                                 history_path=config.get("history_path"))
    summary["collected"] = collect_file("precise", str(keywords), None, count,
                                        str(collected), accounts=credentials["zhidao_accounts"])
    transfer = config.get("transfer") or {}
    mode = transfer.get("mode", "local")
    if mode == "local":
        summary["transferred"] = transfer_file(str(collected), str(transferred),
                                                  transfer.get("target", "/我的资源"), True,
                                                  credentials["pan_cookie"])
    elif mode == "external":
        summary["transferred"] = external_transfer(
            str(collected), str(transferred),
            transfer["external_inbox"], transfer["external_outbox"],
            float(transfer.get("timeout_seconds", 1800)), transfer.get("result_name"),
            transfer.get("result_glob", "*转存分享结果*.xlsx"))
    else:
        raise ValueError(f"未知转存模式：{mode}")
    summary["templated"] = template_file(str(transferred), str(qa), credentials["deepseek_key"])
    publication = config.get("publish") or {}
    account = publication.get("account")
    if not account:
        raise ValueError("流水线配置需要 publish.account")
    summary["published"] = publish_file(str(qa), account)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lxds")
    commands = parser.add_subparsers(dest="command", required=True)
    mine = commands.add_parser("mine")
    mine.add_argument("--category", choices=CATEGORIES, required=True)
    mine.add_argument("--count", type=int, required=True)
    mine.add_argument("--out", required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--mode", choices=("precise", "fuzzy"), required=True)
    collect.add_argument("--keywords")
    collect.add_argument("--category")
    collect.add_argument("--count", type=int, default=0)
    collect.add_argument("--out", required=True)
    transfer = commands.add_parser("transfer")
    transfer.add_argument("--in", dest="source", required=True)
    transfer.add_argument("--target", required=True)
    transfer.add_argument("--share", action="store_true")
    transfer.add_argument("--out", required=True)
    template = commands.add_parser("template")
    template.add_argument("--in", dest="source", required=True)
    template.add_argument("--out", required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("--in", dest="source", required=True)
    publish.add_argument("--account", required=True)
    answer = commands.add_parser("answer")
    answer.add_argument("--question", required=True)
    answer.add_argument("--style", default="first_person")
    run = commands.add_parser("run")
    run.add_argument("--config", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "mine":
            result = mine_file(args.category, args.count, args.out)
        elif args.command == "collect":
            result = collect_file(args.mode, args.keywords, args.category, args.count,
                                  args.out, accounts=_credentials()["zhidao_accounts"])
        elif args.command == "transfer":
            result = transfer_file(args.source, args.out, args.target, args.share,
                                   _credentials()["pan_cookie"])
        elif args.command == "template":
            result = template_file(args.source, args.out, _credentials()["deepseek_key"])
        elif args.command == "publish":
            result = publish_file(args.source, args.account)
        elif args.command == "answer":
            result = {"answer": answer_question(args.question, args.style)}
        else:
            result = run_pipeline(load_pipeline_config(args.config))
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    except (OSError, ValueError, TimeoutError, KeyError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
