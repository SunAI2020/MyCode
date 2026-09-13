#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
软件代码安全审计程序 - 集成Claude Code Security
功能：分析代码文件，检测常见的安全漏洞和风险，并使用Claude进行安全分析
支持语言：Python、Java、C/C++、JavaScript
"""

import os
import re
import json
import requests
from datetime import datetime

class CodeSecurityAuditor:
    def __init__(self, rules_file=None, claude_api_key=None):
        """初始化安全审计器"""
        self.rules = self.load_rules(rules_file)
        self.claude_api_key = claude_api_key
        self.results = []
        self.security_analysis = None
    
    def load_rules(self, rules_file):
        """加载安全规则"""
        default_rules = {
            'python': {
                'sql_injection': {
                    'pattern': r'(execute|exec|raw_sql|cursor\.execute)\s*\([^)]*\{[^}]*\}|\'.*\%s|\".*\"\s*\%\s*\w+'
                              r'|\$\{.*\}|\'.*\+.*\+'
                              r'|\'.*\+.*\+'
                              r'|\".*\+.*\"',
                    'message': '可能存在SQL注入漏洞'
                },
                'xss': {
                    'pattern': r'(flask|django|render|return).*\{[^}]*\}|\.html\(.*\)|\.render_template\(.*\)',
                    'message': '可能存在XSS漏洞'
                },
                'hardcoded_password': {
                    'pattern': r'(password|pass|pwd|secret|key)\s*=\s*[\'"].*[\'"]',
                    'message': '硬编码密码或密钥'
                },
                'insecure_hash': {
                    'pattern': r'(md5|sha1)\s*\(',
                    'message': '使用不安全的哈希算法'
                },
                'eval_usage': {
                    'pattern': r'eval\s*\(',
                    'message': '使用eval函数，可能导致代码注入'
                }
            },
            'java': {
                'sql_injection': {
                    'pattern': r'(Statement|PreparedStatement).*\.execute.*\(|executeQuery\(|executeUpdate\(',
                    'message': '可能存在SQL注入漏洞'
                },
                'xss': {
                    'pattern': r'(out\.print|response\.getWriter\(\)\.print|JspWriter\.print)',
                    'message': '可能存在XSS漏洞'
                },
                'hardcoded_password': {
                    'pattern': r'(password|pass|pwd|secret|key)\s*=\s*"[^"]*"',
                    'message': '硬编码密码或密钥'
                },
                'insecure_hash': {
                    'pattern': r'MessageDigest\.getInstance\("(MD5|SHA1)"\)',
                    'message': '使用不安全的哈希算法'
                }
            },
            'javascript': {
                'sql_injection': {
                    'pattern': r'(mysql|sqlite|pg).*\.query\(|connection\.query\(',
                    'message': '可能存在SQL注入漏洞'
                },
                'xss': {
                    'pattern': r'(innerHTML|outerHTML|document\.write|eval)\s*=|\$\(.*\)\.html\(',
                    'message': '可能存在XSS漏洞'
                },
                'hardcoded_password': {
                    'pattern': r'(password|pass|pwd|secret|key)\s*[:=]\s*["\'].*["\']',
                    'message': '硬编码密码或密钥'
                },
                'insecure_hash': {
                    'pattern': r'(md5|sha1)\s*\(',
                    'message': '使用不安全的哈希算法'
                }
            },
            'c': {
                'buffer_overflow': {
                    'pattern': r'(gets|scanf|strcpy|strcat)\s*\(',
                    'message': '可能存在缓冲区溢出漏洞'
                },
                'sql_injection': {
                    'pattern': r'sqlite3_exec\(|mysql_query\(|pg_query\(',
                    'message': '可能存在SQL注入漏洞'
                },
                'hardcoded_password': {
                    'pattern': r'(password|pass|pwd|secret|key)\s*=\s*["\'].*["\']',
                    'message': '硬编码密码或密钥'
                }
            }
        }
        
        if rules_file and os.path.exists(rules_file):
            try:
                with open(rules_file, 'r', encoding='utf-8') as f:
                    custom_rules = json.load(f)
                    default_rules.update(custom_rules)
            except Exception as e:
                print(f"加载规则文件失败: {e}")
        
        return default_rules
    
    def detect_language(self, file_path):
        """检测文件语言"""
        ext = os.path.splitext(file_path)[1].lower()
        language_map = {
            '.py': 'python',
            '.java': 'java',
            '.js': 'javascript',
            '.c': 'c',
            '.cpp': 'c',
            '.h': 'c'
        }
        return language_map.get(ext, None)
    
    def audit_file(self, file_path):
        """审计单个文件"""
        language = self.detect_language(file_path)
        if not language:
            return f"不支持的文件类型: {file_path}"
        
        if language not in self.rules:
            return f"暂不支持该语言的审计: {language}"
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            return f"读取文件失败: {e}"
        
        # 应用规则
        for rule_name, rule in self.rules[language].items():
            pattern = rule['pattern']
            message = rule['message']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    self.results.append({
                        'file': file_path,
                        'line': line_num,
                        'language': language,
                        'rule': rule_name,
                        'message': message,
                        'code': line.strip()
                    })
        
        return f"审计完成: {file_path}"
    
    def audit_directory(self, directory):
        """审计目录"""
        results = []
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                result = self.audit_file(file_path)
                results.append(result)
        return results
    
    def analyze_with_claude(self):
        """使用Claude进行安全分析"""
        if not self.claude_api_key:
            self.security_analysis = "未提供Claude API密钥，无法进行安全分析"
            return
        
        try:
            # 构建审计结果摘要
            audit_summary = {
                "total_issues": len(self.results),
                "issues_by_language": {},
                "issues_by_type": {},
                "top_issues": self.results[:10]  # 只取前10个问题进行分析
            }
            
            # 按语言和类型统计问题
            for issue in self.results:
                language = issue['language']
                issue_type = issue['rule']
                
                if language not in audit_summary['issues_by_language']:
                    audit_summary['issues_by_language'][language] = 0
                audit_summary['issues_by_language'][language] += 1
                
                if issue_type not in audit_summary['issues_by_type']:
                    audit_summary['issues_by_type'][issue_type] = 0
                audit_summary['issues_by_type'][issue_type] += 1
            
            # 构建Claude API请求
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.claude_api_key,
                "anthropic-version": "2023-06-01"
            }

            prompt = f"""作为一名代码安全专家，请分析以下代码安全审计结果，并提供详细的安全分析报告和改进建议：

{json.dumps(audit_summary, indent=2, ensure_ascii=False)}

请包括以下内容：
1. 安全风险评估
2. 漏洞详细分析
3. 具体的安全建议
4. 最佳修复措施
5. 代码安全最佳实践
"""

            data = {
                "model": "claude-sonnet-4-6",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            }

            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                self.security_analysis = result.get("content", [{}])[0].get("text", "")
            else:
                self.security_analysis = f"Claude分析失败: {response.status_code} - {response.text[:200]}"
        except Exception as e:
            self.security_analysis = f"Claude分析异常: {str(e)}"
    
    def generate_report(self, output_file=None):
        """生成审计报告"""
        # 按语言和类型统计问题
        issues_by_language = {}
        issues_by_type = {}
        for issue in self.results:
            language = issue['language']
            issue_type = issue['rule']
            
            if language not in issues_by_language:
                issues_by_language[language] = 0
            issues_by_language[language] += 1
            
            if issue_type not in issues_by_type:
                issues_by_type[issue_type] = 0
            issues_by_type[issue_type] += 1
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_issues': len(self.results),
            'issues_by_language': issues_by_language,
            'issues_by_type': issues_by_type,
            'issues': self.results,
            'security_analysis': self.security_analysis
        }
        
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                return f"审计报告已生成: {output_file}"
            except Exception as e:
                return f"生成报告失败: {e}"
        
        return report
