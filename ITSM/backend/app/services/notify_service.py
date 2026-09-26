"""多渠道消息推送：企微/飞书/钉钉 webhook，未配置/失败静默降级站内。"""
import json
import urllib.request

from app.core.config import settings


def _post_json(url: str, payload: dict) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5):
        pass


def send_channel(channel: str, content: str) -> bool:
    """按渠道发送消息；未配置 webhook 或发送失败返回 False（调用方降级站内）。"""
    if channel == "企微":
        url = settings.WECOM_WEBHOOK
        payload = {"msgtype": "text", "text": {"content": content}}
    elif channel == "钉钉":
        url = settings.DINGTALK_WEBHOOK
        payload = {"msgtype": "text", "text": {"content": content}}
    elif channel == "飞书":
        url = settings.FEISHU_WEBHOOK
        payload = {"msg_type": "text", "content": {"text": content}}
    else:
        return False
    if not url:
        return False
    try:
        _post_json(url, payload)
        return True
    except Exception:
        return False
