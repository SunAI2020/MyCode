# -*- coding: utf-8 -*-
"""AI 响应解析鲁棒性测试 — 容错散文前缀/代码块/嵌套对象"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_client import strip_markdown_fences
from ai_verifier import AIVerifier


def test_strip_fence_at_start():
    assert strip_markdown_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_fence_with_preamble():
    # 响应被环境告警前置语污染，代码块不在开头（本次 bug 场景）
    text = '注意：记忆服务不可用\n以下是结论：\n```json\n{"a": 1}\n```'
    assert strip_markdown_fences(text) == '{"a": 1}'


def test_strip_no_fence_unchanged():
    assert strip_markdown_fences('{"a": 1}') == '{"a": 1}'


def _make_verifier():
    # 不触发 __init__（避免 AIClient 依赖），仅测试纯解析逻辑
    return AIVerifier.__new__(AIVerifier)


def test_parse_response_with_preamble_and_fence():
    v = _make_verifier()
    polluted = ('注意：claude-mem 记忆服务当前不可用\n以下是分析结论：\n'
                '```json\n{"is_vulnerability": false, "confidence": 0.98, '
                '"reasoning": "误报", "fix_suggestion": ""}\n```')
    r = v._parse_response(polluted)
    assert r['is_vulnerability'] is False
    assert r['confidence'] == 0.98


def test_parse_response_with_prose_and_nested_json():
    v = _make_verifier()
    # 散文前缀 + 嵌套对象 + 字符串内花括号
    text = '分析结果：这是误报 {"is_vulnerability": false, "data": {"nested": true}, "note": "}"}'
    r = v._parse_response(text)
    assert r['is_vulnerability'] is False
    assert r['data']['nested'] is True


def test_parse_response_unparseable_keeps_finding():
    v = _make_verifier()
    r = v._parse_response('完全无法解析的内容，没有 JSON')
    assert r['is_vulnerability'] is True  # 保守保留
    assert r['confidence'] == 0.5
