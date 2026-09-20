"""本地配置与凭据存储。"""

from __future__ import annotations

import base64
import copy
import ctypes
import ctypes.wintypes
import json
import os
from pathlib import Path
import sys
import tempfile
import warnings
from typing import Any


_CIPHER_PREFIX = "dpapi:"
_DEFAULT_APP = "lxds"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _input_blob(data: bytes) -> tuple[_DataBlob, Any]:
    # 缓冲区要和调用同时存活，否则 DLL 会读到已释放的内存。
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    return blob, buffer


def _dpapi_transform(data: bytes, *, decrypt: bool) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [
        ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, ctypes.wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    function.restype = ctypes.wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    source, buffer = _input_blob(data)
    result = _DataBlob()
    # UI_FORBIDDEN 防止后台任务意外弹出系统凭据窗口。
    if not function(ctypes.byref(source), None, None, None, None, 0x01, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def _encrypt(value: str) -> str:
    if not value:
        return ""
    if sys.platform != "win32":
        return value
    encrypted = _dpapi_transform(value.encode("utf-8"), decrypt=False)
    return _CIPHER_PREFIX + base64.b64encode(encrypted).decode("ascii")


def _decrypt(value: str) -> str:
    if not value or sys.platform != "win32":
        return value
    if not value.startswith(_CIPHER_PREFIX):
        raise ValueError("配置中的凭据未使用 DPAPI 加密")
    encrypted = base64.b64decode(value[len(_CIPHER_PREFIX):], validate=True)
    return _dpapi_transform(encrypted, decrypt=True).decode("utf-8")


def _accounts_for_disk(accounts: list[dict]) -> list[dict]:
    result = copy.deepcopy(accounts)
    for account in result:
        account["cookie"] = _encrypt(str(account.get("cookie", "")))
    return result


def _accounts_from_disk(accounts: list[dict]) -> list[dict]:
    result = copy.deepcopy(accounts)
    for account in result:
        account["cookie"] = _decrypt(str(account.get("cookie", "")))
    return result


class ConfigStore:
    """保存配置，并对 API Key 和 Cookie 逐项使用 DPAPI 加密。"""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        if path is None:
            local_appdata = os.environ.get("LOCALAPPDATA")
            if local_appdata:
                path = Path(local_appdata) / _DEFAULT_APP / "config.json"
            else:
                path = Path.home() / ".config" / _DEFAULT_APP / "config.json"
        self.path = Path(path)
        self._deepseek_key = ""
        self._zhidao_accounts: list[dict] = []
        self._pan_accounts: list[dict] = []
        self._settings: dict[str, Any] = {}
        if sys.platform != "win32":
            warnings.warn("当前平台不支持 Windows DPAPI，凭据将以明文保存", RuntimeWarning, stacklevel=2)

    def load(self) -> None:
        """从磁盘加载配置；首次运行时保持空配置。"""
        if not self.path.exists():
            return
        payload = self._read_persisted()
        self._deepseek_key = _decrypt(str(payload.get("deepseek_key", "")))
        self._zhidao_accounts = _accounts_from_disk(payload.get("zhidao_accounts", []))
        self._pan_accounts = _accounts_from_disk(payload.get("pan_accounts", []))
        self._settings = copy.deepcopy(payload.get("settings", {}))

    def save(self) -> None:
        """原子写入并重新读取校验，避免写入失败被误报为成功。"""
        payload = {
            "deepseek_key": _encrypt(self._deepseek_key),
            "zhidao_accounts": _accounts_for_disk(self._zhidao_accounts),
            "pan_accounts": _accounts_for_disk(self._pan_accounts),
            "settings": copy.deepcopy(self._settings),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".config-", suffix=".tmp", delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.path)
            self.verify_persisted(payload)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def verify_persisted(self, expected: dict[str, Any]) -> None:
        """原系统要求保存后重读，以发现磁盘或权限问题。"""
        try:
            actual = self._read_persisted()
        except (OSError, ValueError) as exc:
            raise OSError("配置写入校验失败：无法重新读取") from exc
        if actual != expected:
            raise OSError("配置写入校验失败：落盘内容不一致")

    def _read_persisted(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise ValueError("配置文件格式异常：根节点不是对象")
        return payload

    def get_deepseek_key(self) -> str:
        return self._deepseek_key

    def set_deepseek_key(self, key: str) -> None:
        self._deepseek_key = key

    def get_zhidao_accounts(self) -> list[dict]:
        return copy.deepcopy(self._zhidao_accounts)

    def set_zhidao_accounts(self, accounts: list[dict]) -> None:
        self._zhidao_accounts = copy.deepcopy(accounts)

    def get_pan_accounts(self) -> list[dict]:
        return copy.deepcopy(self._pan_accounts)

    def set_pan_accounts(self, accounts: list[dict]) -> None:
        self._pan_accounts = copy.deepcopy(accounts)

    def get_setting(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self._settings.get(key, default))

    def set_setting(self, key: str, value: Any) -> None:
        self._settings[key] = copy.deepcopy(value)
