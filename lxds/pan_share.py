"""为已转存的网盘文件创建分享，并组合转存与分享流程。"""

from __future__ import annotations

import json
import secrets

from lxds.pan_auth import PanError, PanQuotaError, PanTransientError
from lxds.pan_transfer import PanClient as TransferPanClient, extract_pwd, extract_surl


_PWD_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
)


def generate_pwd(length: int = 4) -> str:
    """从原系统字符集生成分享提取码。"""
    if length <= 0:
        raise ValueError("提取码长度必须大于零")
    return "".join(secrets.choice(_PWD_ALPHABET) for _ in range(length))


def random_ua() -> str:
    return secrets.choice(_USER_AGENTS)


class PanClient(TransferPanClient):
    """在 M09 转存客户端上增加分享与组合入口。"""

    def share_files(self, fsids: list[int], bdstoken: str, pwd: str) -> dict:
        """调用分享接口，返回带 `?pwd=` 的完整链接。"""
        payload = self._post_json(
            "https://pan.baidu.com/share/set",
            params={"channel": "chunlei", "web": 1, "app_id": 250528, "bdstoken": bdstoken, "clienttype": 0},
            data={
                "schannel": 0, "channel_list": "[]", "period": 0,
                "pwd": pwd, "fid_list": json.dumps(fsids, separators=(",", ":")),
            },
        )
        errno = payload.get("errno")
        if errno != 0:
            detail = str(payload.get("message", payload.get("errmsg", "")))
            if "权限" in detail:
                raise PanError("分享失败：无权限")
            if "提取码" in detail or "密码" in detail:
                raise PanError("分享失败：提取码格式错误")
            if "频繁" in detail or "风控" in detail:
                raise PanTransientError(f"分享被风控/请求过于频繁（errno={errno}），请稍后重试")
            raise PanError(f"分享失败（errno={errno}）")
        raw_link = payload.get("link") or payload.get("shorturl")
        if not raw_link:
            raise PanError("分享失败：返回缺少链接")
        link = str(raw_link)
        if not link.startswith("http"):
            link = "https://pan.baidu.com/s/" + link.lstrip("/")
        if "pwd=" not in link:
            link += ("&" if "?" in link else "?") + f"pwd={pwd}"
        return {**payload, "share_url": link, "share_pwd": pwd}

    def transfer_link(
        self, url: str, target_path: str, do_share: bool,
        pwd: str | None = None,
    ) -> dict:
        """完成一条外部链接的转存和可选分享，保留部分成功状态。"""
        outcome = {
            "status": "失败", "share_url": "", "share_pwd": "",
            "dup_paths": [], "retryable": False, "message": "",
        }
        transferred = False
        try:
            surl = extract_surl(url)
            source_pwd = extract_pwd(url)
            shareid, uk, _ = self.verify_share(url, surl, source_pwd)
            files = self.file_list(shareid, uk, url)
            if not files:
                raise PanError("分享为空")
            fsids = [int(item["fs_id"]) for item in files if item.get("fs_id") is not None]
            names = [str(item.get("server_filename", "")) for item in files]
            token = self.bdstoken()
            transfer = self.transfer_files(shareid, uk, fsids, target_path, url, token)
            status = transfer["status"]
            outcome["dup_paths"] = transfer.get("dup_paths", [])
            if status == "文件数超限":
                outcome["message"] = transfer.get("message", "文件数超限")
                return outcome
            if status == "瞬时故障":
                outcome["retryable"] = True
                outcome["message"] = "转存遇到瞬时故障"
                return outcome
            transferred = True
            outcome["status"] = status
            if not do_share:
                return outcome
            own_fsids = self.transferred_fsids(transfer, len(fsids))
            if len(own_fsids) < len(fsids):
                own_fsids = self.fsids_by_names(target_path, names)
            if not own_fsids:
                raise PanError("分享失败：无法定位已转存文件")
            share = self.share_files(own_fsids, token, pwd or generate_pwd())
            outcome["share_url"] = share["share_url"]
            outcome["share_pwd"] = share["share_pwd"]
            return outcome
        except PanQuotaError:
            raise
        except PanError as exc:
            if transferred:
                outcome["status"] = "转存成功，分享失败" if outcome["status"] == "转存成功" else outcome["status"]
                outcome["retryable"] = False
            else:
                outcome["retryable"] = isinstance(exc, PanTransientError)
            outcome["message"] = str(exc)
            return outcome
