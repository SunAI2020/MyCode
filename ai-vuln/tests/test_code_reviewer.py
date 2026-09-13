# -*- coding: utf-8 -*-
"""代码质量与设计审计模块测试"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def reviewer():
    from ai_code_reviewer import AICodeReviewer
    return AICodeReviewer(enable_ai=False)  # 禁用 AI，仅测确定性规则


def _review(reviewer, code, filepath='sample.py'):
    return reviewer.review_file(filepath, code)


class TestQualityDimensions:
    def test_dimensions_cover_all_requested(self):
        from ai_code_reviewer import QUALITY_DIMENSIONS
        required = {
            'architecture', 'logic', 'function', 'completeness', 'loop',
            'invocation', 'interface', 'parameter', 'naming', 'io',
            'ui', 'api', 'database', 'security',
        }
        assert required.issubset(set(QUALITY_DIMENSIONS.keys()))


class TestHeuristicRules:
    def test_loop_nesting_detected(self, reviewer):
        code = (
            'for a in x:\n'
            '    for b in y:\n'
            '        for c in z:\n'
            '            for d in w:\n'
            '                print(d)\n'
        )
        findings = _review(reviewer, code)
        assert any(f['dimension'] == 'loop' for f in findings)

    def test_shallow_loop_not_flagged(self, reviewer):
        code = 'for a in x:\n    print(a)\n'
        findings = _review(reviewer, code)
        assert not any(f['dimension'] == 'loop' for f in findings)

    def test_todo_and_pass_detected(self, reviewer):
        code = '# TODO: 补充实现\ndef foo():\n    pass\n'
        findings = _review(reviewer, code)
        assert any(f['category'] == '待办占位' for f in findings)
        assert any(f['category'] == '空实现占位' for f in findings)

    def test_not_implemented_error_detected(self, reviewer):
        code = 'def foo():\n    raise NotImplementedError\n'
        findings = _review(reviewer, code)
        assert any(f['category'] == '未实现异常' for f in findings)

    def test_bare_except_detected(self, reviewer):
        code = 'try:\n    x = 1\nexcept:\n    x = 0\n'
        findings = _review(reviewer, code)
        assert any(f['category'] == '裸 except 捕获' for f in findings)

    def test_mutable_default_detected(self, reviewer):
        code = 'def foo(items=[]):\n    pass\n'
        findings = _review(reviewer, code)
        assert any(f['category'] == '可变默认参数' for f in findings)

    def test_naming_camelcase_detected_py_only(self, reviewer):
        code = 'def getUserName():\n    return 1\n'
        findings = _review(reviewer, code, filepath='sample.py')
        assert any(f['dimension'] == 'naming' for f in findings)
        # 非 Python 文件不触发命名规则
        findings_js = _review(reviewer, code, filepath='sample.js')
        assert not any(f['dimension'] == 'naming' for f in findings_js)

    def test_long_function_detected(self, reviewer):
        body = '\n'.join(f'    value_{i} = {i}' for i in range(65))
        code = f'def long_func():\n{body}\n'
        findings = _review(reviewer, code)
        assert any(f['category'] == '函数过长' for f in findings)


class TestParseFindings:
    def test_parse_json_array_with_fences(self, reviewer):
        reviewer._current_file = 'foo.py'
        text = (
            '```json\n'
            '[{"dimension":"architecture","category":"循环依赖","severity":"HIGH",'
            '"line":10,"code":"import b","problem":"A与B互相依赖","solution":"抽取公共接口"}]\n'
            '```'
        )
        findings = reviewer._parse_findings(text)
        assert len(findings) == 1
        f = findings[0]
        assert f['dimension'] == 'architecture'
        assert f['severity'] == 'HIGH'
        assert f['line'] == 10
        assert f['file'] == 'foo.py'
        assert f['recommendation'] == '抽取公共接口'

    def test_parse_normalizes_unknown_dimension(self, reviewer):
        reviewer._current_file = 'bar.py'
        text = '[{"dimension":"unknown","severity":"warn","line":"abc","problem":"x","solution":"y"}]'
        findings = reviewer._parse_findings(text)
        assert len(findings) == 1
        assert findings[0]['dimension'] == 'logic'  # 未知维度回退
        assert findings[0]['severity'] == 'MEDIUM'   # 非法严重度回退
        assert findings[0]['line'] == 0              # 非整数行号回退

    def test_parse_single_object(self, reviewer):
        reviewer._current_file = 'baz.py'
        text = '{"dimension":"database","severity":"HIGH","problem":"p","solution":"s"}'
        findings = reviewer._parse_findings(text)
        assert len(findings) == 1
        assert findings[0]['dimension'] == 'database'

    def test_parse_invalid_returns_empty(self, reviewer):
        assert reviewer._parse_findings('this is not json at all') == []


class TestReviewFile:
    def test_review_file_runs_heuristics_without_ai(self, reviewer):
        code = 'def foo(items=[]):\n    pass\n'
        findings = _review(reviewer, code)
        assert any(f['dimension'] == 'parameter' for f in findings)
        assert any(f['category'] == '空实现占位' for f in findings)
        # 每个 finding 都带统一字段
        for f in findings:
            assert 'dimension' in f and 'problem' in f and 'recommendation' in f
