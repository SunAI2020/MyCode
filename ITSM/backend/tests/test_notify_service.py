"""多渠道推送单测：未配置/未知渠道降级。"""
from app.services.notify_service import send_channel


def test_send_channel_unconfigured():
    assert send_channel("企微", "测试") is False  # 未配置 webhook → 降级


def test_send_channel_unknown():
    assert send_channel("短信", "测试") is False  # 未支持渠道 → 降级
