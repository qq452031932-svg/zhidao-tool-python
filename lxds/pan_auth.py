"""百度网盘 Cookie 体检、bdstoken 和目标目录检查。"""

from __future__ import annotations

from pathlib import PurePosixPath
import re

import requests


_PAN = "https://pan.baidu.com"
_RISK_ERRNOS = {2, -9, 132}


class PanError(Exception):
    """网盘请求或输入错误。"""


class PanTransientError(PanError):
    """可重试的网盘错误。"""


class PanQuotaError(PanError):
    """空间不足；批量任务应立即停止。"""


class PanClient:
    """持有一个百度网盘 Cookie 的请求会话。"""

    def __init__(self, cookie: str, timeout: int = 30) -> None:
        self.cookie = cookie
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Cookie": cookie, "Referer": f"{_PAN}/disk/home"})
        self._checked_dirs: set[str] = set()

    def _get_json(self, url: str, **kwargs) -> dict:
        try:
            response = self.session.get(url, timeout=self.timeout, **kwargs)
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PanTransientError("百度网盘网络异常") from exc
        if not isinstance(payload, dict):
            raise PanTransientError("百度网盘返回格式异常")
        return payload

    def check_cookie(self) -> tuple[str, str]:
        """区分真失效、风控与仅缺 STOKEN，避免误导用户重新登录。"""
        try:
            user = self._get_json(f"{_PAN}/rest/2.0/xpan/nas?method=uinfo&clienttype=0&web=1")
        except PanTransientError:
            return "network", "百度网盘网络异常，请稍后重试"
        errno = user.get("errno")
        if errno == -6:
            return "expired", f"登录态已失效（errno={errno}）。请重新登录 pan.baidu.com，复制完整 Cookie 后再粘贴"
        if errno in _RISK_ERRNOS:
            return "risk", f"触发百度安全验证（errno={errno}）。请先在浏览器打开一次 pan.baidu.com 通过验证，再回来重试"
        if errno != 0:
            return "network", f"百度网盘账号信息异常（errno={errno}）"

        try:
            quota = self._get_json(f"{_PAN}/api/quota")
        except PanTransientError:
            return "network", "百度网盘配额接口网络异常"
        quota_errno = quota.get("errno")
        if quota_errno == -6:
            return "incomplete", "登录态有效，但 Cookie 缺少 STOKEN：部分接口可能失败，建议重新复制完整 Cookie"
        if quota_errno in _RISK_ERRNOS:
            return "risk", f"触发百度安全验证（errno={quota_errno}）。请先在浏览器打开一次 pan.baidu.com 通过验证，再回来重试"
        if quota_errno != 0:
            return "network", f"百度网盘配额接口异常（errno={quota_errno}）"
        return "ok", "登录态正常"

    def bdstoken(self) -> str:
        """优先从 JSON 端点获取 token，失败时回退到首页 HTML。"""
        payload = self._get_json(
            f"{_PAN}/api/gettemplatevariable?fields=%5B%22bdstoken%22%5D&clienttype=0&web=1"
        )
        result = payload.get("result", {})
        token = result.get("bdstoken") if isinstance(result, dict) else None
        if token:
            return str(token)
        try:
            response = self.session.get(f"{_PAN}/disk/home", timeout=self.timeout)
        except requests.RequestException as exc:
            raise PanTransientError("获取 bdstoken 时网络异常") from exc
        match = re.search(r"bdstoken[\"\s:]+[\"']?([0-9A-Za-z]+)", response.text)
        if match:
            return match.group(1)
        raise PanError("无法获取 bdstoken，请检查登录态")

    def list_dir(self, path: str) -> list[dict]:
        """列取一个已有目录中的条目，不进行创建操作。"""
        payload = self._get_json(
            f"{_PAN}/api/list",
            params={"dir": path, "num": 1000, "order": "name", "desc": 0, "showempty": 0, "web": 1},
        )
        if payload.get("errno") != 0:
            raise PanError(f"目标目录读取失败（errno={payload.get('errno')}）")
        items = payload.get("list")
        if not isinstance(items, list):
            raise PanError("目标目录返回格式异常")
        return items

    def ensure_target_dir(self, path: str) -> None:
        """只确认目录仍存在；不创建，以免产生用户不认识的空目录。"""
        normalized = "/" + path.strip("/") if path.strip("/") else "/"
        if normalized == "/" or normalized in self._checked_dirs:
            return
        parent = str(PurePosixPath(normalized).parent)
        try:
            items = self.list_dir(parent)
        except PanError as exc:
            raise PanError(f"目标文件夹不存在或读不到：{normalized}。请重新选择目标文件夹") from exc
        if not any(item.get("path") == normalized and item.get("isdir") == 1 for item in items):
            raise PanError(f"目标文件夹不存在或读不到：{normalized}。请重新选择目标文件夹")
        self._checked_dirs.add(normalized)
