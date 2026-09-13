# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - AI分析模块"""
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI安全分析器"""

    # 危险代码模式
    DANGEROUS_PATTERNS = {
        'SQL注入': [r'execute\s*\(.*\+', r'execute\s*\(.*%', r'\.format\(.*\)\s*.*SELECT',
                    r'f".*SELECT', r"f'.*SELECT", r'cursor\.execute\(.*\%s'],
        '命令注入': [r'os\.system\(', r'os\.popen\(', r'subprocess\.call\(.*shell\s*=\s*True',
                     r'eval\(', r'exec\(', r'__import__\(.*input'],
        'XSS漏洞': [r'innerHTML\s*=', r'document\.write\(', r'\.html\(.*\+',
                    r'\.html\(.*%', r'response\.write\(.*\+', r'<%=.*request\.'],
        '路径遍历': [r'open\(.*\.\.\/', r'open\(.*\\\.\\', r'\.\./\.\./',
                     r'file_get_contents\(.*\.\.', r'readFile\(.*\.\.'],
        '硬编码密钥': [r'(?:password|passwd|secret|key|token|apikey)\s*=\s*[\'"][^\'"]{8,}[\'"]',
                       r'(?:private_key|secret_key|access_key)\s*=\s*[\'"][^\'"]{8,}[\'"]'],
        '不安全的反序列化': [r'pickle\.loads\(', r'pickle\.load\(', r'cPickle\.loads\(',
                            r'yaml\.load\(', r'yaml\.full_load\(', r'marshal\.loads\('],
        '弱加密算法': [r'MD5\b', r'SHA1\b', r'DES\b', r'RC2\b', r'RC4\b',
                       r'hashlib\.md5\(', r'hashlib\.sha1\('],
        '不安全的随机数': [r'random\.randint\(', r'random\.random\(', r'Math\.random\('],
        '信息泄露': [r'print\(.*password', r'console\.log\(.*password',
                     r'log\.debug\(.*secret', r'log\.info\(.*token'],
        'SSRF漏洞': [r'requests\.get\(.*input', r'urllib\.request\.urlopen\(.*input',
                     r'curl_setopt\(.*CURLOPT_URL.*\$_(?:GET|POST)'],
    }

    SEVERITY_MAP = {
        'SQL注入': 'CRITICAL', '命令注入': 'CRITICAL', '不安全的反序列化': 'CRITICAL',
        'XSS漏洞': 'HIGH', '路径遍历': 'HIGH', 'SSRF漏洞': 'HIGH',
        '硬编码密钥': 'HIGH', '信息泄露': 'MEDIUM',
        '弱加密算法': 'MEDIUM', '不安全的随机数': 'LOW'
    }

    RECOMMENDATIONS = {
        'SQL注入': '使用参数化查询或ORM框架，避免字符串拼接SQL语句',
        '命令注入': '使用subprocess.run([cmd, arg1, arg2])而非shell=True，并验证输入',
        'XSS漏洞': '对输出进行HTML实体编码，使用CSP头，避免直接拼接用户输入到HTML',
        '路径遍历': '使用白名单验证文件路径，使用os.path.basename过滤，禁止..\\',
        '硬编码密钥': '将密钥移至环境变量或密钥管理服务(KMS)，使用加密的配置文件',
        '不安全的反序列化': '避免反序列化不可信数据，使用JSON代替pickle，或使用安全沙箱',
        '弱加密算法': '使用SHA-256/512、AES-256-GCM等强加密算法替换MD5/SHA1/DES',
        '不安全的随机数': '使用secrets模块或os.urandom()生成安全随机数',
        '信息泄露': '避免在日志和输出中打印敏感信息，使用脱敏处理',
        'SSRF漏洞': '使用URL白名单，禁用内网地址访问，验证和过滤用户输入的URL',
    }

    def __init__(self):
        logger.info("AI分析器初始化完成")

    def scan_directory(self, path: str, extensions: List[str] = None) -> Dict:
        """扫描代码目录"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.java', '.go', '.php', '.rb', '.c', '.cpp', '.html']

        results = {'scan_time': datetime.now().isoformat(), 'target': path, 'files': [], 'issues': []}
        total_files = 0

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ['node_modules', '__pycache__', 'venv', '.git', 'dist', 'build']]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    filepath = os.path.join(root, file)
                    total_files += 1
                    issues = self._analyze_file(filepath)
                    if issues:
                        results['files'].append({
                            'path': filepath,
                            'issues_count': len(issues)
                        })
                        results['issues'].extend(issues)

        results['total_files_scanned'] = total_files
        results['total_vulnerabilities'] = len(results['issues'])

        severity_counts = {}
        for issue in results['issues']:
            sev = issue.get('severity', 'UNKNOWN')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        results['severity_summary'] = severity_counts

        return results

    def _analyze_file(self, filepath: str) -> List[Dict]:
        """分析单个文件"""
        issues = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except:
            return issues

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for category, patterns in self.DANGEROUS_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        severity = self.SEVERITY_MAP.get(category, 'MEDIUM')
                        issues.append({
                            'file': filepath, 'line': line_num,
                            'code': line[:120], 'category': category,
                            'severity': severity,
                            'recommendation': self.RECOMMENDATIONS.get(category, ''),
                            'pattern_matched': pattern
                        })
                        break

        return issues

    def generate_report(self, scan_result: Dict) -> Dict:
        """生成分析报告"""
        total_files = scan_result.get('total_files_scanned', 0)
        total_vulns = scan_result.get('total_vulnerabilities', 0)
        severity_summary = scan_result.get('severity_summary', {})

        critical_count = severity_summary.get('CRITICAL', 0)
        high_count = severity_summary.get('HIGH', 0)

        if total_vulns == 0:
            risk_level = '安全'
            recommendation = '未发现漏洞，建议保持定期代码审计'
        elif critical_count > 0:
            risk_level = '严重风险'
            recommendation = f'发现{critical_count}个严重漏洞，建议立即修复并停止部署'
        elif high_count > 3:
            risk_level = '高风险'
            recommendation = f'发现{high_count}个高危漏洞，建议优先修复后再部署'
        elif high_count > 0:
            risk_level = '中等风险'
            recommendation = '存在高危漏洞，建议计划修复'
        else:
            risk_level = '低风险'
            recommendation = '发现低风险问题，建议逐步修复'

        return {
            **scan_result,
            'risk_level': risk_level,
            'recommendation': recommendation,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def analyze_vulnerability(self, vuln_data: Dict) -> str:
        """分析单个漏洞"""
        desc = vuln_data.get('description', '')
        service = vuln_data.get('service', '')
        cvss = vuln_data.get('cvss_score', 0)

        analysis_parts = []

        if 'sql' in desc.lower() or 'injection' in desc.lower():
            analysis_parts.append('[高危] 检测到注入类漏洞')
        if 'rce' in desc.lower() or 'remote code' in desc.lower():
            analysis_parts.append('[严重] 检测到远程代码执行漏洞')
        if 'xss' in desc.lower():
            analysis_parts.append('[中危] 检测到跨站脚本漏洞')
        if 'dos' in desc.lower() or 'denial of service' in desc.lower():
            analysis_parts.append('[中危] 检测到拒绝服务漏洞')

        if cvss >= 9.0:
            analysis_parts.append('[紧急] CVSS评分>=9.0，建议立即修复')
        elif cvss >= 7.0:
            analysis_parts.append('[高优先级] CVSS评分>=7.0，建议尽快修复')

        if not analysis_parts:
            analysis_parts.append(f'服务{service}存在安全风险，建议升级到最新版本')

        return '\n'.join(analysis_parts)
