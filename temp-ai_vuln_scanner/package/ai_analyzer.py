# -*- coding: utf-8 -*-
"""
AI Vuln Scanner Pro - AI分析模块
集成Claude API进行智能代码安全审计和漏洞分析
"""
import os
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 安全漏洞模式库
SECURITY_PATTERNS = {
    'python': [
        {
            'name': 'SQL注入',
            'pattern': r'(execute|exec|raw_sql|cursor\.execute)\s*\([^)]*\{[^}]*\}|\'.*\%s|\".*\"\s*\%\s*\w+|\$\{.*\}|\'.*\+.*\+',
            'severity': 'CRITICAL',
            'description': '使用字符串拼接构建SQL查询，存在SQL注入风险'
        },
        {
            'name': 'XSS跨站脚本',
            'pattern': r'(flask|django|render|return).*\{[^}]*\}|\.html\(.*\)|\.render_template\(.*\)',
            'severity': 'HIGH',
            'description': '直接输出用户输入，可能存在XSS跨站脚本漏洞'
        },
        {
            'name': '硬编码密码',
            'pattern': r'(password|pass|pwd|secret|key|token)\s*=\s*[\'"].*[\'"]',
            'severity': 'HIGH',
            'description': '代码中包含硬编码的密码或密钥'
        },
        {
            'name': '不安全的哈希',
            'pattern': r'(md5|sha1)\s*\(|\.md5\(|\.sha1\(',
            'severity': 'MEDIUM',
            'description': '使用不安全的哈希算法(MD5/SHA1)'
        },
        {
            'name': '代码注入',
            'pattern': r'eval\s*\(|exec\s*\(|compile\s*\(',
            'severity': 'CRITICAL',
            'description': '使用eval/exec动态执行代码，可能导致代码注入'
        },
        {
            'name': '不安全的反序列化',
            'pattern': r'pickle\.loads?|yaml\.load\(|marshal\.load\(',
            'severity': 'CRITICAL',
            'description': '使用不安全的反序列化，可能导致远程代码执行'
        },
        {
            'name': '路径遍历',
            'pattern': r'open\s*\([^)]*\+[^)]*\)|os\.path\.join\([^)]*request\.',
            'severity': 'HIGH',
            'description': '可能存在路径遍历漏洞'
        },
        {
            'name': '命令注入',
            'pattern': r'os\.system\(|os\.popen\(|subprocess\..*shell\s*=\s*True|subprocess\..*shell\s*=\s*1',
            'severity': 'CRITICAL',
            'description': '使用shell执行命令，可能存在命令注入'
        },
        {
            'name': '不安全的随机数',
            'pattern': r'random\.random\(\)|random\.randrange\(',
            'severity': 'MEDIUM',
            'description': '使用random模块生成安全相关随机数'
        },
        {
            'name': 'SSL验证禁用',
            'pattern': r'verify\s*=\s*False|SSL._create_unverified_context',
            'severity': 'HIGH',
            'description': '禁用SSL证书验证，存在中间人攻击风险'
        }
    ],
    'javascript': [
        {
            'name': 'SQL注入',
            'pattern': r'(mysql|sqlite|pg).*\.query\(|connection\.query\(|execute\s*\(',
            'severity': 'CRITICAL',
            'description': '使用字符串拼接构建SQL查询'
        },
        {
            'name': 'XSS跨站脚本',
            'pattern': r'innerHTML\s*=|outerHTML\s*=|document\.write\(|eval\s*\(',
            'severity': 'HIGH',
            'description': '直接操作DOM或使用eval，可能导致XSS'
        },
        {
            'name': '硬编码凭证',
            'pattern': r'(password|pass|pwd|secret|key|token)\s*[:=]\s*["\'][^"\']+["\']',
            'severity': 'HIGH',
            'description': '代码中包含硬编码的凭证'
        },
        {
            'name': '敏感信息泄露',
            'pattern': r'console\.log\([^)]*(password|token|secret|key)',
            'severity': 'MEDIUM',
            'description': '敏感信息可能被输出到控制台'
        },
        {
            'name': '不安全的随机数',
            'pattern': r'Math\.random\(\)',
            'severity': 'MEDIUM',
            'description': 'Math.random()不适合安全用途'
        }
    ],
    'java': [
        {
            'name': 'SQL注入',
            'pattern': r'(Statement|PreparedStatement).*\.execute.*\(|executeQuery\(|executeUpdate\(',
            'severity': 'CRITICAL',
            'description': '使用字符串拼接构建SQL查询'
        },
        {
            'name': 'XSS跨站脚本',
            'pattern': r'(out\.print|response\.getWriter\(\)\.print|JspWriter\.print)',
            'severity': 'HIGH',
            'description': '直接输出到响应，可能存在XSS'
        },
        {
            'name': '硬编码密码',
            'pattern': r'(password|pass|pwd|secret|key)\s*=\s*"[^"]*"',
            'severity': 'HIGH',
            'description': '代码中包含硬编码的密码'
        },
        {
            'name': '不安全的哈希',
            'pattern': r'MessageDigest\.getInstance\(["\'](MD5|SHA1)["\']\)',
            'severity': 'MEDIUM',
            'description': '使用不安全的哈希算法'
        },
        {
            'name': 'XML外部实体',
            'pattern': r'DocumentBuilderFactory\.newInstance\(\)|SAXParserFactory\.newInstance\(\)',
            'severity': 'HIGH',
            'description': '可能存在XXE(XML外部实体)漏洞'
        }
    ],
    'c': [
        {
            'name': '缓冲区溢出',
            'pattern': r'(gets|scanf|strcpy|strcat|sprintf)\s*\(',
            'severity': 'CRITICAL',
            'description': '使用不安全的字符串函数，可能导致缓冲区溢出'
        },
        {
            'name': '格式化字符串',
            'pattern': r'printf\s*\([^)]*\+[^)]*\)|printf\s*\([^)]*\%s[^)]*\)',
            'severity': 'HIGH',
            'description': '格式化字符串漏洞'
        },
        {
            'name': '整数溢出',
            'pattern': r'(malloc|calloc|realloc)\s*\([^)]*\*[^)]*\)',
            'severity': 'HIGH',
            'description': '可能存在整数溢出'
        }
    ]
}


class AIAnalyzer:
    """AI安全分析器"""

    def __init__(self, claude_api_key: str = None):
        """初始化AI分析器"""
        self.claude_api_key = claude_api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.results = []

        # 尝试导入anthropic
        self.anthropic_client = None
        if self.claude_api_key:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=self.claude_api_key)
                logger.info("Claude API集成成功")
            except ImportError:
                logger.warning("未安装anthropic库，将使用本地模式")

    def detect_language(self, file_path: str) -> str:
        """检测代码语言"""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'c',
            '.h': 'c',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.cs': 'c#',
            '.sh': 'bash'
        }

        ext = os.path.splitext(file_path)[1].lower()
        return ext_map.get(ext, 'unknown')

    def scan_file(self, file_path: str) -> Dict[str, Any]:
        """扫描单个代码文件"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, {e}")
            return {'file': file_path, 'error': str(e), 'vulnerabilities': []}

        language = self.detect_language(file_path)
        vulnerabilities = []

        # 模式匹配检测
        if language in SECURITY_PATTERNS:
            for pattern_info in SECURITY_PATTERNS[language]:
                matches = re.finditer(pattern_info['pattern'], content, re.IGNORECASE)
                for match in matches:
                    # 获取匹配行号
                    line_num = content[:match.start()].count('\n') + 1
                    context_start = max(0, match.start() - 30)
                    context_end = min(len(content), match.end() + 30)
                    context = content[context_start:context_end]

                    vulnerabilities.append({
                        'type': pattern_info['name'],
                        'severity': pattern_info['severity'],
                        'description': pattern_info['description'],
                        'line': line_num,
                        'code': match.group(),
                        'context': context.replace('\n', ' ')
                    })

        result = {
            'file': file_path,
            'language': language,
            'lines': len(content.split('\n')),
            'vulnerabilities': vulnerabilities,
            'vulnerability_count': len(vulnerabilities)
        }

        # 如果有漏洞且配置了API，进行AI深度分析
        if vulnerabilities and self.anthropic_client:
            try:
                ai_analysis = self._claude_analyze(vulnerabilities, content[:5000])
                result['ai_analysis'] = ai_analysis
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                result['ai_analysis'] = None

        return result

    def scan_directory(self, dir_path: str, extensions: List[str] = None) -> List[Dict]:
        """扫描目录中的所有代码文件"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.go', '.rb', '.php']

        results = []
        for root, dirs, files in os.walk(dir_path):
            # 跳过隐藏目录和常见忽略目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__', 'build', 'dist']]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    file_path = os.path.join(root, file)
                    result = self.scan_file(file_path)
                    results.append(result)

        return results

    def analyze_vulnerability(self, cve_data: Dict) -> str:
        """AI分析CVE漏洞"""
        if not self.anthropic_client:
            return "AI分析需要配置API密钥"

        prompt = f"""你是一个网络安全专家。请分析以下CVE漏洞并提供专业的安全建议：

CVE编号: {cve_data.get('cve_id')}
漏洞名称: {cve_data.get('name')}
描述: {cve_data.get('description')}
CVSS评分: {cve_data.get('cvss_score')}
严重程度: {cve_data.get('severity')}
受影响产品: {', '.join(cve_data.get('affected_products', []))}

请提供:
1. 漏洞利用可能性��析
2. 潜在影响评估
3. 修复建议
4. 风险等级评估(低/中/高/严重)

请用中文回复。"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"CVE分析失败: {e}")
            return f"分析失败: {str(e)}"

    def analyze_network_service(self, service_info: Dict) -> str:
        """AI分析网络服务安全性"""
        if not self.anthropic_client:
            return "AI分析需要配置API密钥"

        prompt = f"""你是一个网络安全专家。请分析以下网络服务的安全性：

主机: {service_info.get('host')}
端口: {service_info.get('port')}
服务: {service_info.get('service')}
版本: {service_info.get('version')}
状态: {service_info.get('state')}

已知CVE: {service_info.get('vulnerabilities', [])}

请提供:
1. 服务安全性评估
2. 存在的风险点
3. 加固建议
4. 优先级建议

请用中文回复，简洁明了。"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"服务分析失败: {e}")
            return f"分析失败: {str(e)}"

    def _claude_analyze(self, vulnerabilities: List[Dict], code_context: str) -> str:
        """使用Claude进行深度分析"""
        vuln_summary = "\n".join([
            f"- {v['type']} ({v['severity']}): 第{v['line']}行"
            for v in vulnerabilities[:5]
        ])

        prompt = f"""你是一个代码安全审计专家。请分析以下代码中发现的漏洞并提供修复建议：

发现的漏洞:
{vuln_summary}

代码片段:
```{code_context[:2000]}
```

请提供:
1. 漏洞风险评估
2. 修复建议
3. 安全编码最佳实践

请用中文简洁回复。"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude分析失败: {e}")
            return "AI分析暂时不可用"

    def generate_report(self, scan_results: List[Dict]) -> Dict[str, Any]:
        """生成扫描报告"""
        total_vulns = sum(r.get('vulnerability_count', 0) for r in scan_results)

        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for result in scan_results:
            for vuln in result.get('vulnerabilities', []):
                sev = vuln.get('severity', 'MEDIUM')
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        high_risk_files = [
            r['file'] for r in scan_results
            if r.get('vulnerability_count', 0) >= 3
        ]

        return {
            'total_files_scanned': len(scan_results),
            'total_vulnerabilities': total_vulns,
            'severity_breakdown': severity_counts,
            'high_risk_files': high_risk_files,
            'scan_time': datetime.now().isoformat()
        }


class AIThreatAnalyzer:
    """AI威胁分析器 - 用于分析扫描结果中的威胁"""

    def __init__(self, api_key: str = None):
        """初始化"""
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.anthropic_client = None

        if self.api_key:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                pass

    def assess_risk_level(self, scan_results: List[Dict]) -> Dict[str, Any]:
        """评估整体风险等级"""
        if not scan_results:
            return {'level': 'LOW', 'score': 0, 'factors': []}

        severity_weights = {'CRITICAL': 10, 'HIGH': 7, 'MEDIUM': 4, 'LOW': 1}
        total_score = 0
        factors = []

        for result in scan_results:
            for vuln in result.get('vulnerabilities', []):
                severity = vuln.get('severity', 'MEDIUM')
                weight = severity_weights.get(severity, 4)
                total_score += weight
                factors.append(f"{vuln['type']} ({severity})")

        if total_score >= 30:
            level = 'CRITICAL'
        elif total_score >= 20:
            level = 'HIGH'
        elif total_score >= 10:
            level = 'MEDIUM'
        else:
            level = 'LOW'

        return {
            'level': level,
            'score': total_score,
            'factors': list(set(factors))[:10],
            'summary': self._get_level_summary(level)
        }

    def _get_level_summary(self, level: str) -> str:
        """获取风险等级描述"""
        summaries = {
            'CRITICAL': '发现多个严重漏洞，存在极高的安全风险，需要立即修复',
            'HIGH': '发现高危漏洞，存在较高安全风险，建议尽快修复',
            'MEDIUM': '发现中危漏洞，存在一定安全风险，建议关注',
            'LOW': '安全状况良好，未发现严重漏洞'
        }
        return summaries.get(level, '未知')


# 测试
if __name__ == '__main__':
    analyzer = AIAnalyzer()
    result = analyzer.scan_file('ai_vuln_scanner/database.py')
    print(f"扫描文件: {result['file']}")
    print(f"发现漏洞数: {result['vulnerability_count']}")

    if result['vulnerabilities']:
        print("\n漏洞列表:")
        for v in result['vulnerabilities'][:3]:
            print(f"  - {v['type']} ({v['severity']}) 第{v['line']}行")