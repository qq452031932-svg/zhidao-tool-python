"""DeepSeek 官方聊天接口，保留原系统的错误文案。"""

from __future__ import annotations

import requests


_ENDPOINT = "https://api.deepseek.com/chat/completions"
_MODEL = "deepseek-chat"


class DeepSeekError(Exception):
    """DeepSeek 调用失败，消息可直接展示给用户。"""


def chat(
    api_key: str,
    messages: list[dict],
    max_tokens: int | None = None,
    json_mode: bool = False,
    timeout: int = 120,
) -> str:
    """调用固定模型并返回第一条消息的正文。"""
    key = api_key.strip()
    if not key:
        raise DeepSeekError("请先在个人中心配置 DeepSeek API Key")

    payload: dict = {"model": _MODEL, "messages": messages}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    try:
        response = requests.post(_ENDPOINT, headers=headers, json=payload, timeout=timeout)
    except requests.Timeout as exc:
        raise DeepSeekError("DeepSeek 请求超时，请稍后重试") from exc
    except requests.RequestException as exc:
        raise DeepSeekError(f"DeepSeek 网络错误：{exc}") from exc

    if response.status_code == 401:
        raise DeepSeekError("DeepSeek API Key 无效，请检查个人中心配置")
    if response.status_code in (402, 429):
        raise DeepSeekError("DeepSeek 余额不足或请求限流，请稍后重试")
    if response.status_code >= 400:
        raise DeepSeekError(f"DeepSeek 接口异常（HTTP {response.status_code}）")

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError("DeepSeek 返回格式异常") from exc
    if not isinstance(content, str):
        raise DeepSeekError("DeepSeek 返回格式异常")
    if not content:
        raise DeepSeekError("DeepSeek 返回内容为空")
    return content


def test_key(api_key: str) -> tuple[bool, str]:
    """用最小 ping 请求验证 API Key。"""
    try:
        chat(api_key, [{"role": "user", "content": "ping"}])
    except DeepSeekError as exc:
        return False, str(exc)
    return True, "DeepSeek API Key 可用"
