# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - AI增强验证模块

使用本机 Claude Code（默认）或 Anthropic API（回退）对正则匹配的候选漏洞进行上下文分析，
自动识别并排除误报，保留真实漏洞。
"""
import json
import logging
from typing import List, Dict, Optional

from ai_client import AIClient, strip_markdown_fences

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AI 验证的提示词模板
VERIFY_SYSTEM_PROMPT = """你是一位资深代码安全审计专家。你的任务是对静态分析工具发现的候选漏洞进行二次确认。

对于每个候选漏洞，你会收到：
1. 漏洞类别（如SQL注入、命令注入等）
2. 匹配到的正则模式
3. 目标代码行及其周围上下文（前后各5行）

请仔细分析代码上下文，判断该匹配是否为真实的安全漏洞。

常见的误报类型（应标记为误报）：
- 参数化查询：使用了 ? 或 %s 占位符的SQL查询
- 检测规则定义：代码本身就是漏洞检测规则/字典/配置
- LIKE通配符：% 是SQL LIKE的通配符而非Python字符串格式化
- 白名单验证：变量来自硬编码的白名单列表
- UI/日志文本：f-string仅用于显示消息，不涉及SQL
- 注释中的代码：匹配到的代码在注释中

真实的漏洞类型（应标记为漏洞）：
- 用户输入直接拼接到SQL语句中
- 动态构造的命令执行字符串
- 使用+或f-string将变量拼入SQL且无参数化

请以JSON格式返回你的判断，格式如下：
{"is_vulnerability": true/false, "confidence": 0.0-1.0, "reasoning": "分析理由", "fix_suggestion": "修复建议（如果是真实漏洞）"}"""


class AIVerifier:
    """AI增强验证器 — 使用本机Claude Code（默认）或API Key（回退）验证候选漏洞"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 stop_event=None):
        """
        初始化AI验证器

        Args:
            api_key: Anthropic API密钥（可选，默认使用本机Claude Code CLI）
            model: 使用的模型（可选，CLI模式下由CC SWITCH决定）
            stop_event: 可选 threading.Event，置位后终止 Claude CLI 子进程
        """
        self.client = AIClient(api_key=api_key, model=model)
        self.model = model
        self.stop_event = stop_event
        self.verified_count = 0
        self.false_positive_count = 0
        self.confirmed_count = 0
        logger.info(f"AI验证器初始化完成 (模型: {model or 'CLI默认'})")

    def verify_issue(self, issue: Dict, file_content: str) -> Dict:
        """
        验证单个候选漏洞

        Args:
            issue: 候选漏洞字典 {file, line, category, code, severity, pattern_matched, ...}
            file_content: 完整文件内容（用于提取上下文）

        Returns:
            验证结果，包含 is_vulnerability, confidence, reasoning, fix_suggestion
        """
        context = self._extract_context(file_content, issue.get('line', 1))
        prompt = self._build_prompt(issue, context)

        try:
            response_text = self.client.query(
                prompt,
                system_prompt=VERIFY_SYSTEM_PROMPT,
                stop_event=self.stop_event
            )

            result = self._parse_response(response_text)
            self.verified_count += 1

            if result.get('is_vulnerability'):
                self.confirmed_count += 1
            else:
                self.false_positive_count += 1

            return result

        except Exception as e:
            logger.error(f"AI验证失败 ({issue.get('file')}:{issue.get('line')}): {e}")
            # API调用失败时，保守处理：保留原始判断（不排除）
            return {
                'is_vulnerability': True,
                'confidence': 0.3,
                'reasoning': f'AI验证调用失败: {str(e)}，保留原始判断',
                'fix_suggestion': issue.get('recommendation', ''),
            }

    def verify_batch(self, issues: List[Dict], file_contents: Dict[str, str]) -> List[Dict]:
        """
        批量验证候选漏洞列表

        Args:
            issues: 候选漏洞列表
            file_contents: {文件路径: 文件内容} 字典（用于提取上下文）

        Returns:
            确认的漏洞列表（误报已被过滤）
        """
        if not issues:
            return []

        confirmed = []
        false_positives = []

        total = len(issues)
        for i, issue in enumerate(issues, 1):
            filepath = issue.get('file', '')
            content = file_contents.get(filepath, '')

            if not content:
                # 无法读取文件内容，保守保留
                confirmed.append(issue)
                continue

            logger.info(f"AI验证中 [{i}/{total}]: {issue.get('category')} @ {filepath}:{issue.get('line')}")

            result = self.verify_issue(issue, content)

            # 将验证结果附加到原始issue
            issue['ai_verified'] = True
            issue['ai_confidence'] = result.get('confidence', 0)
            issue['ai_reasoning'] = result.get('reasoning', '')

            if result.get('is_vulnerability') and result.get('confidence', 0) >= 0.6:
                issue['ai_fix_suggestion'] = result.get('fix_suggestion', '')
                confirmed.append(issue)
            else:
                issue['excluded_reason'] = result.get('reasoning', 'AI判定为误报')
                false_positives.append(issue)

        logger.info(
            f"AI验证完成: {total}个候选 → "
            f"{len(confirmed)}个确认, {len(false_positives)}个误报排除"
        )

        return confirmed

    def get_excluded_issues(self) -> List[Dict]:
        """返回被排除的误报列表（需要在verify_batch后单独获取）"""
        return []

    def _extract_context(self, file_content: str, line_number: int, context_lines: int = 5) -> str:
        """提取指定行周围的代码上下文"""
        lines = file_content.split('\n')
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        context_parts = []
        for i in range(start, end):
            line_num = i + 1
            prefix = '>>>' if line_num == line_number else '   '
            context_parts.append(f"{prefix} {line_num:4d} | {lines[i]}")

        return '\n'.join(context_parts)

    def _build_prompt(self, issue: Dict, context: str) -> str:
        """构建发送给Claude的分析提示词"""
        return f"""请分析以下候选漏洞：

漏洞类别: {issue.get('category', 'Unknown')}
匹配模式: {issue.get('pattern_matched', 'N/A')}
文件: {issue.get('file', 'N/A')}
行号: {issue.get('line', 'N/A')}
当前行代码: {issue.get('code', 'N/A')[:200]}

代码上下文:
```
{context}
```

请判断该匹配是否构成真实的安全漏洞。以JSON格式返回。"""

    def _parse_response(self, text: str) -> Dict:
        """解析Claude的JSON响应（容错散文前缀/代码块/嵌套对象）。"""
        text = strip_markdown_fences(text)

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取第一个平衡的 {...} 对象（括号计数，容错嵌套与字符串内花括号）
        start = text.find('{')
        if start != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break

        # 解析失败，默认保守处理
        logger.warning(f"无法解析AI响应为JSON，保留为漏洞: {text[:200]}")
        return {
            'is_vulnerability': True,
            'confidence': 0.5,
            'reasoning': 'AI响应解析失败，保留原始判断',
            'fix_suggestion': '',
        }

    def get_statistics(self) -> Dict:
        """获取验证统计"""
        return {
            'total_verified': self.verified_count,
            'confirmed': self.confirmed_count,
            'false_positives': self.false_positive_count,
            'fp_rate': (
                self.false_positive_count / self.verified_count
                if self.verified_count > 0 else 0
            ),
        }
