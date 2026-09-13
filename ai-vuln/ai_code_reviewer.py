# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 代码质量与设计审计模块

在正则安全扫描之外，对代码做全面的质量与设计审查，覆盖软件架构、逻辑、
函数规范、功能完整性、循环复杂度、调用关系、接口规范、参数传递、命名标识、
输入输出、交互界面、API 设计、数据库设计等维度。

分层检测：
- 第一层（确定性规则，零外部依赖）：循环嵌套、TODO占位、命名、函数过长、
  裸 except、可变默认参数 —— 免费、零延迟，无 AI 也可运行。
- 第二层（Claude AI 深度分析）：架构、逻辑、接口、API、数据库等复杂问题。

产出与安全审计统一字段的 issue 列表（含 dimension / problem / recommendation）。
"""
import os
import re
import json
import logging
from typing import List, Dict, Optional, Callable

from ai_client import AIClient, is_ai_available, strip_markdown_fences

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 跳过的目录（与 ai_analyzer.py 保持一致）
SKIP_DIRS = ['node_modules', '__pycache__', 'venv', '.git', 'dist', 'build']

# 文件准入阈值
MAX_FILE_BYTES = 200 * 1024        # 超过 200KB 跳过 AI 深度分析
AI_CHUNK_LINES = 400               # AI 分析分块行数
AI_CHUNK_OVERLAP = 10              # 分块重叠行数
FUNCTION_LENGTH_THRESHOLD = 60     # 函数超过 60 行视为过长
LOOP_NESTING_THRESHOLD = 3         # 循环嵌套超过 3 层告警


# 质量维度分类：key -> 中文名 -> 描述（覆盖用户需求全部维度）
QUALITY_DIMENSIONS = {
    'architecture': {'name': '架构设计', 'desc': '模块/类划分、分层、依赖方向、耦合、单一职责、可扩展性'},
    'logic': {'name': '逻辑问题', 'desc': '逻辑混乱、边界条件、错误分支、死代码、重复逻辑、状态不一致'},
    'function': {'name': '函数规范', 'desc': '函数过长、职责不清、副作用、命名与语义不符、参数过多'},
    'completeness': {'name': '功能完整性', 'desc': '未实现、TODO占位、缺失错误处理、缺失边界处理、半成品逻辑'},
    'loop': {'name': '循环与复杂度', 'desc': '循环嵌套过深、循环变量误用、可能无限循环、时间/空间复杂度'},
    'invocation': {'name': '调用关系', 'desc': '调用混乱、循环依赖、错误调用链、时序问题、重复调用'},
    'interface': {'name': '接口规范', 'desc': '接口设计不合理、返回类型不明确、契约不清晰、职责重叠'},
    'parameter': {'name': '参数传递', 'desc': '参数不完整、参数顺序混乱、可变默认参数、魔法值、类型不明确'},
    'naming': {'name': '命名标识', 'desc': '命名不清晰、缩写、命名不一致、误导性命名、命名过长'},
    'io': {'name': '输入输出', 'desc': '文件/网络/数据库资源未释放、编码问题、IO 异常处理缺失、路径拼接'},
    'ui': {'name': '交互界面', 'desc': 'UI 逻辑与业务耦合、交互流程、用户体验、状态管理、可访问性'},
    'api': {'name': 'API 设计', 'desc': 'REST 规范、状态码、鉴权、版本控制、错误响应、幂等性、限流'},
    'database': {'name': '数据库', 'desc': '查询优化、连接管理、事务、索引、范式、N+1 问题、并发一致性'},
    'security': {'name': '安全', 'desc': '安全漏洞（由安全扫描模块负责，此处兜底补充）'},
}

# AI 深度分析系统提示词
CODE_REVIEW_SYSTEM_PROMPT = """你是一位资深的软件架构师与代码质量审查专家，精通软件设计、代码规范与工程最佳实践。

你会收到一个代码文件（可能被分块，每行前缀标注了行号）。请对该代码进行**质量与设计维度**的全面审查（安全问题由另一模块负责，无需重复报告 SQL 注入等纯安全漏洞）。

需要审查的维度（dimension 取值必须严格使用下列 key 之一）：
- architecture: 架构设计（模块/类划分、分层、依赖方向、耦合、单一职责、可扩展性）
- logic: 逻辑问题（逻辑混乱、边界条件、错误分支、死代码、重复逻辑、状态不一致）
- function: 函数规范（函数过长、职责不清、副作用、命名与语义不符）
- completeness: 功能完整性（未实现、TODO占位、缺失错误处理、缺失边界处理）
- loop: 循环与复杂度（嵌套过深、循环变量误用、可能无限循环、时间复杂度）
- invocation: 调用关系（调用混乱、循环依赖、错误调用链、时序问题）
- interface: 接口规范（接口设计不合理、返回类型不明确、契约不清晰）
- parameter: 参数传递（参数不完整、参数顺序混乱、可变默认参数、魔法值）
- naming: 命名标识（命名不清晰、缩写、不一致、误导性命名）
- io: 输入输出（资源未释放、编码问题、IO 异常处理缺失、路径拼接）
- ui: 交互界面（UI 逻辑与业务耦合、交互流程、用户体验、状态管理）
- api: API 设计（REST 规范、状态码、鉴权、版本、错误响应、幂等性）
- database: 数据库（查询优化、连接管理、事务、索引、范式、N+1 问题）

审查规则：
1. 仅报告**真实、具体、可行动**的问题，避免主观风格偏好（如空格数量、引号风格）。
2. 优先报告正确性、架构、数据库、API、资源管理等高价值问题。
3. 每个问题给出**详尽的中文解决方案（solution 字段）**，包含具体修复代码示例。
4. line 字段请填问题代码行前标注的行号（整数）。
5. 若该文件没有值得报告的问题，返回空数组 []，不要编造问题。

请严格以 JSON 数组格式返回，每个元素结构如下：
{"dimension": "上面的key之一", "category": "简短问题类别", "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "line": 行号数字, "code": "问题代码片段", "problem": "详尽问题描述", "solution": "详尽解决方案（含修复代码）"}

只返回 JSON 数组，不要任何其他文字。"""


class AICodeReviewer:
    """AI 代码质量与设计审查器 — 确定性规则 + Claude 深度分析"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 enable_ai: bool = True, stop_event=None):
        """
        初始化审查器

        Args:
            api_key: Anthropic API 密钥（可选，默认本机 Claude Code CLI）
            model: 模型名称（可选）
            enable_ai: 是否启用 AI 深度分析（False 时仅运行确定性规则）
            stop_event: 可选 threading.Event，置位后终止 Claude CLI 子进程
        """
        self.api_key = api_key
        self.model = model
        self.enable_ai = enable_ai and is_ai_available()
        self.stop_event = stop_event
        self.client = AIClient(api_key=api_key, model=model) if self.enable_ai else None
        self._current_file = ''  # 当前正在分析的文件（供解析时回填）
        if self.enable_ai:
            logger.info("代码质量审查器初始化完成 (AI 深度分析已启用)")
        else:
            logger.info("代码质量审查器初始化完成 (仅确定性规则，未检测到 Claude CLI)")

    # ==================== 对外接口 ====================

    def review_file(self, filepath: str, content: Optional[str] = None,
                    should_stop: Callable[[], bool] = None) -> List[Dict]:
        """审查单个文件，返回 issue 列表（确定性规则 + 可选 AI 深度分析）"""
        if content is None:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                return []

        lines = content.split('\n')
        findings = self._run_heuristics(lines, filepath)

        if self.enable_ai and content and len(content) <= MAX_FILE_BYTES:
            ai_findings = self._run_ai_review(filepath, lines, should_stop)
            findings.extend(ai_findings)

        return findings

    def review_project(self, path: str, extensions: List[str] = None,
                       progress_callback: Callable[[str], None] = None,
                       should_stop: Callable[[], bool] = None) -> List[Dict]:
        """审查代码目录或单个文件，返回聚合的 issue 列表"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.java', '.go', '.php', '.rb', '.c', '.cpp', '.html']

        all_findings = []
        if os.path.isfile(path):
            all_findings = self._review_one_file(path, progress_callback, should_stop)
        else:
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
                for file in files:
                    if should_stop and should_stop():
                        logger.info("代码质量审计被用户中断")
                        return all_findings
                    ext = os.path.splitext(file)[1].lower()
                    if ext in extensions:
                        all_findings.extend(
                            self._review_one_file(os.path.join(root, file), progress_callback, should_stop)
                        )

        return all_findings

    def _review_one_file(self, filepath: str, progress_callback=None,
                         should_stop: Callable[[], bool] = None) -> List[Dict]:
        """审查单个文件（带大小准入检查）"""
        try:
            size = os.path.getsize(filepath)
        except OSError:
            return []
        if size > MAX_FILE_BYTES:
            if progress_callback:
                progress_callback(f"质量审计跳过(过大): {os.path.basename(filepath)}")
            return []
        if progress_callback:
            progress_callback(f"质量审计: {os.path.basename(filepath)}")
        return self.review_file(filepath, should_stop=should_stop)

    # ==================== 第一层：确定性规则 ====================

    def _run_heuristics(self, lines: List[str], filepath: str) -> List[Dict]:
        """确定性启发式规则，逐行/跨行扫描，无需 AI"""
        findings = []
        findings.extend(self._detect_loop_nesting(lines, filepath))
        findings.extend(self._detect_todo_stubs(lines, filepath))
        findings.extend(self._detect_bare_except(lines, filepath))
        findings.extend(self._detect_mutable_default(lines, filepath))
        findings.extend(self._detect_long_functions(lines, filepath))
        if filepath.lower().endswith('.py'):
            findings.extend(self._detect_naming(lines, filepath))
        return findings

    def _mk(self, filepath, line, dimension, category, severity, code, problem, solution):
        """构造统一 issue 字典"""
        return {
            'file': filepath, 'line': line,
            'dimension': dimension, 'category': category,
            'severity': severity, 'code': (code or '')[:120],
            'problem': problem, 'recommendation': solution,
            'source': 'rule',
        }

    def _detect_loop_nesting(self, lines, filepath):
        """循环嵌套 > 阈值（按缩进深度跟踪 for/while 栈）"""
        findings = []
        loop_stack = []  # 活跃循环的缩进层级
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            indent = len(raw) - len(raw.lstrip())
            # 弹出已结束的循环
            while loop_stack and indent <= loop_stack[-1]:
                loop_stack.pop()
            if re.match(r'(for|while)\b', stripped):
                if len(loop_stack) >= LOOP_NESTING_THRESHOLD:
                    findings.append(self._mk(
                        filepath, idx, 'loop', '循环嵌套过深', 'MEDIUM', stripped,
                        f'循环嵌套达到 {len(loop_stack) + 1} 层，超过 {LOOP_NESTING_THRESHOLD} 层的推荐上限，'
                        f'可读性差且难以维护，容易出现逻辑错误与性能问题。',
                        '将内层循环体抽取为独立函数（提取方法），或使用 itertools.product/'
                        '列表推导替代深层嵌套；对集合型数据考虑用集合操作（set/dict）减少遍历。'
                    ))
                loop_stack.append(indent)
        return findings

    def _detect_todo_stubs(self, lines, filepath):
        """TODO/FIXME 占位、pass、NotImplementedError（功能不完善）"""
        findings = []
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                # 注释里的 TODO 也值得报告
                if re.search(r'\b(TODO|FIXME|XXX|HACK)\b', stripped, re.IGNORECASE):
                    findings.append(self._mk(
                        filepath, idx, 'completeness', '待办占位', 'LOW', stripped,
                        '代码中残留 TODO/FIXME/XXX 占位标记，功能可能不完善或未完成。',
                        '补充实现并移除占位标记；若为已知限制，记录到 issue/文档并在代码中引用编号，'
                        '避免长期遗留未处理的 TODO。'
                    ))
                continue
            if re.search(r'\b(TODO|FIXME|XXX|HACK)\b', stripped, re.IGNORECASE):
                findings.append(self._mk(
                    filepath, idx, 'completeness', '待办占位', 'LOW', stripped,
                    '代码中残留 TODO/FIXME/XXX 占位标记，功能可能不完善或未完成。',
                    '补充实现并移除占位标记；若为已知限制，记录到 issue/文档并在代码中引用编号。'
                ))
            elif stripped == 'pass':
                findings.append(self._mk(
                    filepath, idx, 'completeness', '空实现占位', 'LOW', stripped,
                    '使用 pass 作为空实现占位，功能未完成。',
                    '补充实际实现；若为抽象基类或接口定义，改用 abc.abstractmethod 明确声明，'
                    '而非留空 pass。'
                ))
            elif 'NotImplementedError' in stripped:
                findings.append(self._mk(
                    filepath, idx, 'completeness', '未实现异常', 'MEDIUM', stripped,
                    '抛出 NotImplementedError，表明该功能尚未实现。',
                    '实现缺失的逻辑，移除占位异常；若为接口契约，确保所有调用方都提供具体实现。'
                ))
        return findings

    def _detect_bare_except(self, lines, filepath):
        """裸 except: 无异常类型（吞掉所有异常）"""
        findings = []
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if re.match(r'except\s*:', stripped):
                findings.append(self._mk(
                    filepath, idx, 'function', '裸 except 捕获', 'MEDIUM', stripped,
                    '裸 except: 会捕获包括 KeyboardInterrupt、SystemExit 在内的所有异常，'
                    '掩盖真实错误，难以定位问题。',
                    '明确捕获具体异常类型（如 except ValueError as e:），并对异常做日志记录或向上抛出；'
                    '确需兜底时至少捕获 Exception 而非裸 except。'
                ))
        return findings

    def _detect_mutable_default(self, lines, filepath):
        """可变默认参数（列表/字典/集合作为默认值）"""
        findings = []
        pattern = re.compile(
            r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|dict\(\)|set\(\)|list\(\))'
        )
        for idx, raw in enumerate(lines, 1):
            if pattern.search(raw):
                findings.append(self._mk(
                    filepath, idx, 'parameter', '可变默认参数', 'MEDIUM', raw.strip(),
                    '使用可变对象（list/dict/set）作为函数默认参数，默认值在函数定义时只创建一次，'
                    '多次调用会共享同一对象，导致状态污染与难以排查的 bug。',
                    '将默认值改为 None，在函数体内创建新对象：def f(items=None): items = items or []。'
                ))
        return findings

    def _detect_long_functions(self, lines, filepath):
        """函数过长（超过阈值行）"""
        findings = []
        n = len(lines)
        idx = 1
        while idx <= n:
            raw = lines[idx - 1]
            stripped = raw.strip()
            if stripped.startswith('def '):
                indent = len(raw) - len(raw.lstrip())
                end = idx + 1
                while end <= n:
                    r = lines[end - 1]
                    s = r.strip()
                    if s and not s.startswith('#') and (len(r) - len(r.lstrip())) <= indent:
                        break
                    end += 1
                length = end - idx
                if length > FUNCTION_LENGTH_THRESHOLD:
                    m = re.match(r'def\s+(\w+)', stripped)
                    name = m.group(1) if m else 'unknown'
                    findings.append(self._mk(
                        filepath, idx, 'function', '函数过长', 'MEDIUM', stripped,
                        f'函数 {name} 长达 {length} 行，超过 {FUNCTION_LENGTH_THRESHOLD} 行的推荐上限，'
                        f'职责过多、可读性与可测试性差。',
                        '按单一职责原则将长函数拆分为多个语义清晰的小函数；提取重复逻辑为私有方法；'
                        '复杂分支考虑使用策略模式或字典分发表。'
                    ))
                idx = end
            else:
                idx += 1
        return findings

    def _detect_naming(self, lines, filepath):
        """命名不规范（Python camelCase 变量/函数名）"""
        findings = []
        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continue
            m = re.search(r'def\s+([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)\s*\(', stripped)
            if m:
                findings.append(self._mk(
                    filepath, idx, 'naming', '命名不规范', 'LOW', stripped,
                    f'函数名 "{m.group(1)}" 使用了 camelCase，不符合 PEP 8 命名规范。',
                    'Python 函数与变量命名统一使用 snake_case（如 get_user_by_id），'
                    '类名使用 PascalCase，常量使用 UPPER_SNAKE_CASE。'
                ))
                continue
            m = re.search(r'\b([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)\s*=', stripped)
            if m and not stripped.startswith(('self.', 'cls.')):
                findings.append(self._mk(
                    filepath, idx, 'naming', '命名不规范', 'LOW', stripped,
                    f'变量名 "{m.group(1)}" 使用了 camelCase，不符合 PEP 8 命名规范。',
                    'Python 变量命名统一使用 snake_case（如 user_name、total_count），'
                    '保持命名风格前后一致。'
                ))
        return findings

    # ==================== 第二层：Claude AI 深度分析 ====================

    def _run_ai_review(self, filepath: str, lines: List[str],
                       should_stop: Callable[[], bool] = None) -> List[Dict]:
        """对单个文件做 AI 深度分析（自动分块）"""
        self._current_file = filepath
        findings = []

        if len(lines) <= AI_CHUNK_LINES:
            chunks = [(1, lines)]
        else:
            chunks = []
            start = 0
            while start < len(lines):
                end = min(start + AI_CHUNK_LINES, len(lines))
                chunks.append((start + 1, lines[start:end]))
                if end >= len(lines):
                    break
                start = end - AI_CHUNK_OVERLAP

        for start_line, chunk_lines in chunks:
            if should_stop and should_stop():
                logger.info("AI 深度分析被用户中断")
                break
            try:
                chunk_findings = self._analyze_chunk(filepath, start_line, chunk_lines)
                findings.extend(chunk_findings)
            except Exception as e:
                logger.error(f"AI 深度分析失败 ({filepath}:{start_line}): {e}")

        return findings

    def _analyze_chunk(self, filepath: str, start_line: int, chunk_lines: List[str]) -> List[Dict]:
        """对单个代码块调用 Claude 并解析结果"""
        numbered = '\n'.join(
            f'{start_line + i:4d} | {line}' for i, line in enumerate(chunk_lines)
        )
        prompt = (
            f'请审查以下代码文件（分块，行号已标注，起始行 {start_line}）：\n\n'
            f'文件路径: {filepath}\n'
            f'```\n{numbered}\n```\n\n'
            f'请从质量与设计维度审查并返回 JSON 数组。'
        )

        response_text = self.client.query(prompt, system_prompt=CODE_REVIEW_SYSTEM_PROMPT,
                                          stop_event=self.stop_event)
        return self._parse_findings(response_text)

    def _parse_findings(self, text: str) -> List[Dict]:
        """解析 Claude 返回的 JSON 数组，并规范化字段"""
        text = strip_markdown_fences(text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\[.*\]', text, re.DOTALL)
            if not m:
                logger.warning(f"AI 深度分析响应无法解析为 JSON: {text[:200]}")
                return []
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                logger.warning(f"AI 深度分析响应无法解析为 JSON: {text[:200]}")
                return []

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []

        normalized = []
        for item in data:
            if not isinstance(item, dict):
                continue
            dim = str(item.get('dimension', 'logic')).strip().lower()
            if dim not in QUALITY_DIMENSIONS:
                dim = 'logic'
            sev = str(item.get('severity', 'MEDIUM')).strip().upper()
            if sev not in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'):
                sev = 'MEDIUM'
            try:
                line = int(item.get('line', 0))
            except (TypeError, ValueError):
                line = 0
            normalized.append({
                'file': self._current_file,
                'line': line,
                'dimension': dim,
                'category': str(item.get('category', '代码质量问题'))[:80],
                'severity': sev,
                'code': str(item.get('code', ''))[:200],
                'problem': str(item.get('problem', '')),
                'recommendation': str(item.get('solution', '')),
                'source': 'ai',
            })
        return normalized
