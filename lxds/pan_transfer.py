"""外部分享链接验证、文件列取及百度网盘转存。"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

from lxds.pan_auth import PanClient as AuthPanClient, PanError, PanQuotaError, PanTransientError


_PAN = "https://pan.baidu.com"
_SURL_PARAM = re.compile(r"[?&]surl=([0-9A-Za-z_-]+)")
_SURL_PATH = re.compile(r"/s/1?([0-9A-Za-z_-]+)")
_PWD = re.compile(r"[?&]pwd=([0-9A-Za-z]{4})(?:&|$)", re.I)
_SHARE_ID = re.compile(r"shareid[\"']?\s*[:=]\s*[\"']?(\d+)")
_SHARE_UK = re.compile(r"share_uk[\"']?\s*[:=]\s*[\"']?(\d+)")
_UK = re.compile(r"\buk[\"']?\s*[:=]\s*[\"']?(\d+)")


def extract_surl(url: str) -> str:
    """支持 `/s/1...` 和 `/share/init?surl=...` 两种分享形式。"""
    match = _SURL_PARAM.search(url) or _SURL_PATH.search(url)
    if not match:
        raise PanError("链接格式错误：无法提取 surl")
    return match.group(1)


def extract_pwd(url: str) -> str:
    match = _PWD.search(url)
    return match.group(1) if match else ""


def cookie_fields(cookie: str) -> set[str]:
    return {part.split("=", 1)[0].strip() for part in cookie.split(";") if "=" in part}


class PanClient(AuthPanClient):
    """在 M08 登录态客户端上增加分享验证与转存能力。"""

    def _post_json(self, url: str, **kwargs: Any) -> dict:
        try:
            response = self.session.post(url, timeout=self.timeout, **kwargs)
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PanTransientError("百度网盘网络异常") from exc
        if not isinstance(payload, dict):
            raise PanTransientError("百度网盘返回格式异常")
        return payload

    def verify_share(self, url: str, surl: str, pwd: str) -> tuple[str, str, str]:
        """先读分享页，再验证提取码；优先识别分享者 `share_uk`。"""
        try:
            page = self.session.get(f"{_PAN}/s/1{surl}", timeout=self.timeout)
        except requests.RequestException as exc:
            raise PanTransientError("分享页网络异常") from exc
        share_id = _SHARE_ID.search(page.text)
        share_uk = _SHARE_UK.search(page.text) or _UK.search(page.text)
        if not share_id or not share_uk:
            raise PanError("分享链接信息缺失")
        result = self._post_json(
            f"{_PAN}/share/verify",
            params={"surl": surl, "t": int(time.time() * 1000)},
            data={"pwd": pwd, "vcode": "", "vcode_str": ""},
            headers={"Referer": url},
        )
        if result.get("errno") != 0:
            raise PanError(f"提取码错误或分享不可用（errno={result.get('errno')}）")
        inner = result.get("data") if isinstance(result.get("data"), dict) else result
        randsk = inner.get("randsk")
        if not randsk:
            raise PanError("分享验证返回缺少 randsk")
        cookie = self.session.headers.get("Cookie", self.cookie)
        self.session.headers["Cookie"] = f"{cookie}; BDCLND={randsk}"
        return share_id.group(1), share_uk.group(1), str(randsk)

    def file_list(self, shareid: str, uk: str, url: str) -> list[dict]:
        """读取分享根目录第一百个文件以内的列表。"""
        payload = self._get_json(
            f"{_PAN}/share/list",
            params={"shareid": shareid, "uk": uk, "root": 1, "page": 1, "num": 100, "order": "name", "desc": 0, "web": 1, "folder_path": "/"},
            headers={"Referer": url},
        )
        if payload.get("errno") != 0:
            raise PanError(f"分享文件列表读取失败（errno={payload.get('errno')}）")
        items = payload.get("list")
        if not isinstance(items, list):
            raise PanError("分享文件列表返回格式异常")
        return items

    def transfer_files(
        self, shareid: str, uk: str, fsids: list[int], target_path: str,
        share_url: str, bdstoken: str,
    ) -> dict:
        """调用转存接口；errno 12 必须按返回字段细分。"""
        self.ensure_target_dir(target_path)
        payload = self._post_json(
            f"{_PAN}/share/transfer",
            params={
                "shareid": shareid, "from": uk, "bdstoken": bdstoken,
                "channel": "chunlei", "web": 1, "app_id": 250528, "clienttype": 0,
            },
            data={"fsidlist": json.dumps(fsids, separators=(",", ":")), "path": target_path},
            headers={"Referer": share_url},
        )
        errno = payload.get("errno")
        message = str(payload.get("message", payload.get("errmsg", "")))
        if "空间不足" in message:
            raise PanQuotaError("网盘空间不足，请停止整批转存")
        if errno == 0:
            return {**payload, "status": "转存成功", "retryable": False}
        if errno == 12:
            duplicated = payload.get("duplicated")
            if isinstance(duplicated, dict) and isinstance(duplicated.get("list"), list):
                paths = [str(item["path"]) for item in duplicated["list"] if isinstance(item, dict) and item.get("path")]
                return {**payload, "status": "重复跳过", "retryable": False, "dup_paths": paths}
            if any(key in payload for key in ("target_file_nums_limit", "non_vip_limit", "target_file_nums")):
                limit = payload.get("target_file_nums_limit", payload.get("non_vip_limit", payload.get("target_file_nums", "未知")))
                detail = (
                    f"百度网盘限制：转存文件数超限，（本次分享约 {len(fsids)} 个文件，上限 {limit} 个）；"
                    "请开通会员或改用文件更少的分享链接"
                )
                return {**payload, "status": "文件数超限", "retryable": False, "message": detail}
            return {**payload, "status": "瞬时故障", "retryable": True}
        raise PanError(f"转存失败（errno={errno}）")

    def transferred_fsids(self, result: dict, expect: int) -> list[int]:
        """从本次转存响应取新 fs_id，避免并发时抓到别人的文件。"""
        extra = result.get("extra", {})
        items = extra.get("list", []) if isinstance(extra, dict) else []
        fsids = [int(item["to_fs_id"]) for item in items if isinstance(item, dict) and item.get("to_fs_id")]
        return fsids[:expect]

    def fsids_by_names(self, target_path: str, names: list[str]) -> list[int]:
        """仅在响应缺少 to_fs_id 时按文件名兜底，不取最新 N 个。"""
        by_name = {str(item.get("server_filename")): item.get("fs_id") for item in self.list_dir(target_path)}
        return [int(by_name[name]) for name in names if by_name.get(name) is not None]
