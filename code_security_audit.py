#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
软件代码安全审计程序
功能：分析代码文件，检测常见的安全漏洞和风险
支持语言：Python、Java、C/C++、JavaScript
"""

import os
import re
import argparse
import json
from datetime import datetime

class CodeSecurityAuditor:
    def __init__(self, rules_file=None):
        """初始化安全审计器"""
        self.rules = self.load_rules(rules_file)
        self.results = []
    
    def load_rules(self, rules_file):
        """加载安全规则"""
        default_rules = {
            'python': {
                'sql_injection': {
                    'pattern': r'(execute|exec|raw_sql|cursor\.execute)\s*\([^)]*\{[^}]*\}|\'.*\%s|\".*\"\s*\%\s*\w+'
                    '|\$\{.*\}|\'.*\+.*\+'
                    '|\'.*\+.*\+'
                    '|\".*\+.*\"',
                    'message': '可能存在SQL注入漏洞'
                },
                'xss': {
                    'pattern': r'(flask|django|render|return).*\{[^}]*\}|\.html\(.*\)|\.render_template\(.*\)',
                    'message': '可能存在XSS漏洞'
                },
                'hardcoded_password': {
                    'pattern': r'(password|pass|pwd|secret|key)\s*=\s*[\'\"].*[\'\"]',
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
            with open(rules_file, 'r', encoding='utf-8') as f:
                custom_rules = json.load(f)
                default_rules.update(custom_rules)
        
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
            print(f"[INFO] 不支持的文件类型: {file_path}")
            return
        
        if language not in self.rules:
            print(f"[INFO] 暂不支持该语言的审计: {language}")
            return
        
        print(f"[INFO] 审计文件: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"[ERROR] 读取文件失败: {e}")
            return
        
        # 应用规则
        for rule_name, rule in self.rules[language].items():
            pattern = rule['pattern']
            message = rule['message']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    self.results.append({
                        'file': file_path,
                        'line': line_num,
                        'rule': rule_name,
                        'message': message,
                        'code': line.strip()
                    })
    
    def audit_directory(self, directory):
        """审计目录"""
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                self.audit_file(file_path)
    
    def generate_report(self, output_file=None):
        """生成审计报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_issues': len(self.results),
            'issues': self.results
        }
        
        # 控制台输出
        print("\n=== 代码安全审计报告 ===")
        print(f"审计时间: {report['timestamp']}")
        print(f"发现问题: {report['total_issues']}")
        print("\n详细问题:")
        for issue in report['issues']:
            print(f"\n文件: {issue['file']}")
            print(f"行号: {issue['line']}")
            print(f"问题: {issue['message']}")
            print(f"代码: {issue['code']}")
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n[INFO] 审计报告已生成: {output_file}")
        
        return report

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='软件代码安全审计程序')
    parser.add_argument('path', help='要审计的文件或目录')
    parser.add_argument('--rules', help='自定义规则文件路径')
    parser.add_argument('--output', help='审计报告输出文件路径')
    
    args = parser.parse_args()
    
    auditor = CodeSecurityAuditor(args.rules)
    
    if os.path.isfile(args.path):
        auditor.audit_file(args.path)
    elif os.path.isdir(args.path):
        auditor.audit_directory(args.path)
    else:
        print(f"[ERROR] 路径不存在: {args.path}")
        return
    
    auditor.generate_report(args.output)

if __name__ == '__main__':
    main()
