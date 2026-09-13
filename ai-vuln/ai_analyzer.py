# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - AI分析模块"""
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Callable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI安全分析器"""

    # 危险代码模式（优化版 - 减少误报）
    DANGEROUS_PATTERNS = {
        'SQL注入': [
            # +拼接SQL字符串: execute("SELECT..." + var + "...")（允许字符串内出现引号）
            r"""\.execute\s*\(\s*['"].*['"]\s*\+\s*""",
            # %s/%d/%r格式化拼接到SQL字符串中(排除LIKE通配符)
            r'\.execute\s*\(.*\%[srd]',
            # .format()拼接SQL
            r'\.execute\s*\(\s*.*\.format\s*\(',
            # f-string直接构建SQL查询(作为execute的第一参数)
            r'\.execute\s*\(\s*f"',
            r"\.execute\s*\(\s*f'",
        ],
        '命令注入': [r'os\.system\(', r'os\.popen\(', r'subprocess\.call\(.*shell\s*=\s*True',
                     r'eval\(', r'exec\(', r'__import__\(.*input'],
        'XSS漏洞': [r'innerHTML\s*=', r'document\.write\(', r'\.html\(.*\+',
                    r'\.html\(.*%', r'response\.write\(.*\+', r'<%=.*request\.'],
        '路径遍历': [r'open\(.*\.\.\/', r'open\(.*\\\.\\', r'\.\./\.\./',
                     r'file_get_contents\(.*\.\.', r'readFile\(.*\.\.'],
        '硬编码密钥': [
            # 排除注释和文档字符串中的硬编码密钥
            r'(?:password|passwd|secret|key|token|apikey)\s*=\s*[\'"][^\'"]{8,}[\'"]',
            r'(?:private_key|secret_key|access_key)\s*=\s*[\'"][^\'"]{8,}[\'"]',
        ],
        '不安全的反序列化': [r'pickle\.loads\(', r'pickle\.load\(', r'cPickle\.loads\(',
                            r'yaml\.load\(', r'yaml\.full_load\(', r'marshal\.loads\('],
        '弱加密算法': [
            # 只检测实际函数调用，不检测字典定义中的算法名称
            r'hashlib\.md5\s*\(', r'hashlib\.sha1\s*\(',
            r'\.MD5\s*\(', r'\.SHA1\s*\(',
            r'Crypto\.Cipher\.DES\b', r'Crypto\.Cipher\.ARC4\b',
            r'cryptography\.hazmat\.primitives\.hashes\.MD5\b',
            r'cryptography\.hazmat\.primitives\.hashes\.SHA1\b',
        ],
        '不安全的随机数': [
            r'(?<!\.)random\.randint\(', r'(?<!\.)random\.random\(', r'Math\.random\(',
        ],
        '信息泄露': [r'print\(.*password', r'console\.log\(.*password',
                     r'log\.debug\(.*secret', r'log\.info\(.*token'],
        'SSRF漏洞': [r'requests\.get\(.*input', r'urllib\.request\.urlopen\(.*input',
                     r'curl_setopt\(.*CURLOPT_URL.*\$_(?:GET|POST)'],
    }

    SEVERITY_MAP = {
        'SQL注入': 'CRITICAL', '命令注入': 'CRITICAL', '不安全的反序列化': 'CRITICAL',
        'XSS漏洞': 'HIGH', '路径遍历': 'HIGH', 'SSRF漏洞': 'HIGH',
        '硬编码密钥': 'HIGH', '信息泄露': 'LOW',
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

    def __init__(self, ai_verifier=None, audit_type: str = 'code'):
        """
        初始化AI分析器

        Args:
            ai_verifier: AIVerifier实例（AI增强验证），None则不启用AI验证
            audit_type: 审计类型 'code'（纯正则）或 'claude_security'（AI增强）
        """
        self.ai_verifier = ai_verifier
        self.audit_type = audit_type
        self.ai_excluded_issues = []  # 被AI排除的误报列表
        logger.info(f"AI分析器初始化完成 (模式: {audit_type})")

    def scan_directory(self, path: str, extensions: List[str] = None,
                       progress_callback: Callable[[str], None] = None,
                       enable_quality_review: bool = False,
                       enable_sca: bool = True,
                       stop_security: Callable[[], bool] = None,
                       stop_quality: Callable[[], bool] = None) -> Dict:
        """扫描代码目录或单个文件（自动判断）

        Args:
            enable_quality_review: 是否启用代码质量/设计审计（架构/逻辑/接口/API/数据库等）
            enable_sca: 是否启用供应链安全检测（依赖清单解析 + CVE 匹配，确定性）
            stop_security: 中断回调，返回 True 时中止 AI 安全核验
            stop_quality: 中断回调，返回 True 时中止代码质量/设计审计
        """
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.java', '.go', '.php', '.rb', '.c', '.cpp', '.html']

        results = {'scan_time': datetime.now().isoformat(), 'target': path,
                   'files': [], 'issues': [], 'audit_type': self.audit_type}
        total_files = 0
        file_contents = {}  # 缓存文件内容供AI验证使用

        # 判断是否为单个文件
        if os.path.isfile(path):
            total_files = 1
            filename = os.path.basename(path)
            if progress_callback:
                progress_callback(f"正在扫描: {filename}")
            issues = self._analyze_file(path)
            if issues:
                results['files'].append({
                    'path': path,
                    'issues_count': len(issues)
                })
                results['issues'].extend(issues)
        else:
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                           ['node_modules', '__pycache__', 'venv', '.git', 'dist', 'build']]
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in extensions:
                        filepath = os.path.join(root, file)
                        total_files += 1
                        if progress_callback:
                            progress_callback(f"正在扫描: {file}")
                        issues = self._analyze_file(filepath)
                        if issues:
                            results['files'].append({
                                'path': filepath,
                                'issues_count': len(issues)
                            })
                            results['issues'].extend(issues)

        results['total_files_scanned'] = total_files
        results['regex_candidates'] = len(results['issues'])  # AI验证前的候选数

        # === AI增强验证阶段 ===
        if self.ai_verifier and self.audit_type == 'claude_security' and results['issues']:
            if progress_callback:
                progress_callback(f"AI验证阶段: 正在分析 {len(results['issues'])} 个候选漏洞...")
            results['issues'] = self._ai_verify_issues(
                results['issues'], path, extensions, progress_callback, stop_security
            )
        results['security_issues_count'] = len(results['issues'])

        # === 代码质量/设计审计阶段（新增）===
        if enable_quality_review:
            if progress_callback:
                progress_callback("代码质量/设计审计阶段: 启动深度分析...")
            from ai_code_reviewer import AICodeReviewer
            reviewer = AICodeReviewer()
            quality_issues = reviewer.review_project(path, extensions, progress_callback, stop_quality)
            results['issues'].extend(quality_issues)
            results['quality_issues_count'] = len(quality_issues)
            if progress_callback:
                progress_callback(f"代码质量/设计审计完成: 发现 {len(quality_issues)} 个设计问题")
        else:
            results['quality_issues_count'] = 0

        # === 供应链安全检测阶段（SCA：依赖清单解析 + CVE 版本区间匹配，确定性）===
        if enable_sca:
            if progress_callback:
                progress_callback("供应链安全检测: 解析依赖清单并匹配已知 CVE...")
            from supply_chain import scan_dependencies
            sca_issues = scan_dependencies(path)
            results['issues'].extend(sca_issues)
            results['sca_issues_count'] = len(sca_issues)
            if progress_callback:
                progress_callback(f"供应链安全检测完成: 发现 {len(sca_issues)} 个依赖风险")
        else:
            results['sca_issues_count'] = 0

        # === 相似度去重 + evidence/remediation 结构化富化（新增）===
        from audit_dedup import AuditDeduplicator
        from audit_enrich import enrich_audit_findings
        dedup_result = AuditDeduplicator().deduplicate(results['issues'])
        results['issues'] = enrich_audit_findings(dedup_result['unique'])
        results['duplicate_count'] = len(dedup_result['duplicates'])
        if results['duplicate_count'] and progress_callback:
            progress_callback(f"相似度去重: 排除 {results['duplicate_count']} 条重复发现")

        results['total_vulnerabilities'] = len(results['issues'])

        severity_counts = {}
        for issue in results['issues']:
            sev = issue.get('severity', 'UNKNOWN')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        results['severity_summary'] = severity_counts

        # 按维度统计（安全 + 质量）
        dimension_counts = {}
        for issue in results['issues']:
            dim = issue.get('dimension', 'security')
            dimension_counts[dim] = dimension_counts.get(dim, 0) + 1
        results['dimension_summary'] = dimension_counts

        return results

    def _ai_verify_issues(self, issues: List[Dict], base_path: str,
                          extensions: List[str] = None,
                          progress_callback: Callable[[str], None] = None,
                          should_stop: Callable[[], bool] = None) -> List[Dict]:
        """使用AI验证候选漏洞，过滤误报"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.java', '.go', '.php', '.rb', '.c', '.cpp', '.html']

        # 收集所有涉及的文件内容
        file_paths = set()
        for issue in issues:
            fp = issue.get('file', '')
            if fp and os.path.exists(fp):
                file_paths.add(fp)

        file_contents = {}
        for fp in file_paths:
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    file_contents[fp] = f.read()
            except Exception:
                pass

        # 逐批次验证
        total = len(issues)
        confirmed_issues = []
        self.ai_excluded_issues = []

        batch_size = 10  # 每批最多10个
        for batch_start in range(0, total, batch_size):
            if should_stop and should_stop():
                if progress_callback:
                    progress_callback("AI安全核验已被用户停止")
                break
            batch = issues[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            if progress_callback:
                progress_callback(
                    f"AI验证中 (第{batch_num}/{total_batches}批, "
                    f"已确认{len(confirmed_issues)}个, 已排除{len(self.ai_excluded_issues)}个)..."
                )

            for i, issue in enumerate(batch):
                idx = batch_start + i + 1
                filepath = issue.get('file', '')
                content = file_contents.get(filepath, '')

                if not content:
                    confirmed_issues.append(issue)
                    continue

                if progress_callback:
                    progress_callback(
                        f"AI验证 [{idx}/{total}]: {issue.get('category')} "
                        f"@ {os.path.basename(filepath)}:{issue.get('line')} "
                        f"(已确认{len(confirmed_issues)}个, 已排除{len(self.ai_excluded_issues)}个)"
                    )

                if should_stop and should_stop():
                    break
                result = self.ai_verifier.verify_issue(issue, content)

                issue['ai_verified'] = True
                issue['ai_confidence'] = result.get('confidence', 0)
                issue['ai_reasoning'] = result.get('reasoning', '')

                if result.get('is_vulnerability') and result.get('confidence', 0) >= 0.6:
                    issue['ai_fix_suggestion'] = result.get('fix_suggestion', '')
                    confirmed_issues.append(issue)
                else:
                    issue['excluded_reason'] = result.get('reasoning', 'AI判定为误报')
                    self.ai_excluded_issues.append(issue)

        if progress_callback and self.ai_excluded_issues:
            progress_callback(
                f"AI验证完成: {total}个候选 → {len(confirmed_issues)}个确认, "
                f"{len(self.ai_excluded_issues)}个误报已排除"
            )

        # 统计
        stats = self.ai_verifier.get_statistics()
        logger.info(
            f"AI验证统计: {stats['total_verified']}已验证, "
            f"{stats['confirmed']}确认, {stats['false_positives']}排除, "
            f"误报率: {stats['fp_rate']:.1%}"
        )

        return confirmed_issues

    def _analyze_file(self, filepath: str) -> List[Dict]:
        """分析单个文件"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return []
        return self._analyze_lines(lines, filepath)

    def analyze_code(self, code: str, filename: str = '<code>') -> List[Dict]:
        """分析一段代码字符串（不落盘），返回问题列表"""
        lines = code.splitlines()
        return self._analyze_lines(lines, filename)

    def _analyze_lines(self, lines: List[str], filepath: str) -> List[Dict]:
        """对逐行内容执行正则模式匹配（_analyze_file 与 analyze_code 共用）"""
        issues = []
        # 检测是否在扫描器自己的模式定义区域内
        in_pattern_block = False

        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # 跳过空行和注释
            if not line_stripped or line_stripped.startswith('#'):
                continue

            # 跟踪模式定义块：进入 DANGEROUS_PATTERNS / WEAK_CIPHERS 等字典定义时跳过
            if re.match(r'(?:DANGEROUS_PATTERNS|WEAK_CIPHERS|WEAK_CIPHER_SUITES|KNOWN_VULN)\s*=', line_stripped):
                in_pattern_block = True
                continue
            if in_pattern_block:
                # 字典定义结束：遇到独立的类方法定义或顶层赋值时退出
                if (re.match(r'(?:def\s+|class\s+|^\S+\s*=\s*\{)', line_stripped) and
                        not re.match(r'\s*[\'"]', line_stripped)):
                    in_pattern_block = False
                else:
                    continue

            for category, patterns in self.DANGEROUS_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        severity = self.SEVERITY_MAP.get(category, 'MEDIUM')
                        issues.append({
                            'file': filepath, 'line': line_num,
                            'dimension': 'security',
                            'code': line_stripped[:120], 'category': category,
                            'severity': severity,
                            'problem': f'{category}风险：代码匹配到危险模式',
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

        # 附加AI验证统计
        report = {
            **scan_result,
            'risk_level': risk_level,
            'recommendation': recommendation,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # 如果启用了AI验证，附带验证信息
        if scan_result.get('audit_type') == 'claude_security':
            report['ai_enhanced'] = True
            report['regex_candidates'] = scan_result.get('regex_candidates', total_vulns)
            report['ai_confirmed'] = total_vulns
            report['ai_excluded_count'] = len(self.ai_excluded_issues)
            report['ai_excluded_issues'] = self.ai_excluded_issues
            if self.ai_verifier:
                report['ai_verification_stats'] = self.ai_verifier.get_statistics()

        return report

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
