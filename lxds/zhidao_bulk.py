"""百度知道官方批量上传接口。始终直连，不记录 Cookie。"""

from __future__ import annotations

import requests


_ORIGIN = "https://zhidao.baidu.com"
_USERINFO = f"{_ORIGIN}/qa/api/bulkqa/userinfo"
_UPLOAD = f"{_ORIGIN}/qa/api/bulkqa/upload"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class BulkError(Exception):
    """批量任务错误；code 可供调用方识别 LOGIN/PERM。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": _ORIGIN,
        "Referer": f"{_ORIGIN}/b/batch/batch-upload",
        "Cookie": cookie,
    }


def _session() -> requests.Session:
    session = requests.Session()
    # 原系统要求这条链路直连；忽略环境和系统代理。
    session.trust_env = False
    return session


def _json_response(response: requests.Response) -> tuple[dict, dict]:
    try:
        root = response.json()
    except ValueError as exc:
        raise BulkError("FORMAT", "百度知道返回格式异常") from exc
    if not isinstance(root, dict):
        raise BulkError("FORMAT", "百度知道返回格式异常")
    data = root.get("data", root)
    if not isinstance(data, dict):
        raise BulkError("FORMAT", "百度知道返回格式异常")
    code = root.get("code", data.get("code"))
    if code != 200:
        message = str(root.get("message", root.get("msg", "")))
        if code in (401, 403, -1) or "未登录" in message or "登录" in message:
            raise BulkError("LOGIN", "百度知道登录态已失效，请重新登录")
        raise BulkError("API", f"百度知道批量接口失败（code={code}）")
    return root, data


def _userinfo(session: requests.Session, cookie: str) -> dict:
    try:
        response = session.get(_USERINFO, headers=_headers(cookie), timeout=30)
    except requests.RequestException as exc:
        raise BulkError("NETWORK", "百度知道账号信息请求失败") from exc
    _, data = _json_response(response)
    if data.get("hasPermission") is False:
        raise BulkError("PERM", "该账号无批量发布权限")
    return data


def userinfo(cookie: str) -> dict:
    """查询账号信息和批量发布权限。"""
    if not cookie.strip():
        raise BulkError("LOGIN", "请先配置百度知道 Cookie")
    session = _session()
    try:
        return _userinfo(session, cookie)
    finally:
        session.close()


def upload_file(cookie: str, filename: str, file_bytes: bytes, task_name: str) -> dict:
    """预检权限后，上传 xlsx 并返回任务信息。"""
    if not cookie.strip():
        raise BulkError("LOGIN", "请先配置百度知道 Cookie")
    session = _session()
    try:
        _userinfo(session, cookie)
        try:
            response = session.post(
                _UPLOAD,
                headers=_headers(cookie),
                files={"file": (filename, file_bytes, _XLSX_MIME)},
                data={"taskName": task_name},
                timeout=120,
            )
        except requests.RequestException as exc:
            raise BulkError("NETWORK", "百度知道批量任务上传失败") from exc
        _, data = _json_response(response)
        if data.get("hasPermission") is False:
            raise BulkError("PERM", "该账号无批量发布权限")
        task_id = data.get("taskId")
        if not task_id:
            raise BulkError("FORMAT", "百度知道返回格式异常：缺少 taskId")
        return data
    finally:
        session.close()
