#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
软件代码安全审计程序 - GUI版本
功能：分析代码文件，检测常见的安全漏洞和风险
支持语言：Python、Java、C/C++、JavaScript
"""

import os
import re
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import threading

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
    
    def generate_report(self, output_file=None):
        """生成审计报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_issues': len(self.results),
            'issues': self.results
        }
        
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                return f"审计报告已生成: {output_file}"
            except Exception as e:
                return f"生成报告失败: {e}"
        
        return report

class CodeSecurityAuditGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("代码安全审计工具")
        self.root.geometry("1000x700")
        
        # 变量
        self.target_path = tk.StringVar()
        self.rules_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.auditor = None
        self.results = []
        
        # 创建界面
        self.create_widgets()
    
    def create_widgets(self):
        """创建GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部配置区域
        config_frame = ttk.LabelFrame(main_frame, text="配置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)
        
        # 目标路径
        ttk.Label(config_frame, text="目标路径:", width=10).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.target_path, width=60).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(config_frame, text="浏览文件", command=self.browse_file).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(config_frame, text="浏览目录", command=self.browse_directory).grid(row=0, column=3, padx=5, pady=5)
        
        # 规则文件
        ttk.Label(config_frame, text="规则文件:", width=10).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.rules_path, width=60).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(config_frame, text="浏览", command=self.browse_rules).grid(row=1, column=2, padx=5, pady=5)
        
        # 输出路径
        ttk.Label(config_frame, text="输出报告:", width=10).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.output_path, width=60).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(config_frame, text="浏览", command=self.browse_output).grid(row=2, column=2, padx=5, pady=5)
        
        # 审计按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        self.audit_button = ttk.Button(button_frame, text="开始审计", command=self.start_audit)
        self.audit_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空结果", command=self.clear_results).pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, pady=5)
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(main_frame, text="审计结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 结果表格
        columns = ("file", "line", "message", "code")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.tree.heading("file", text="文件路径")
        self.tree.heading("line", text="行号")
        self.tree.heading("message", text="问题")
        self.tree.heading("code", text="代码")
        
        # 设置列宽
        self.tree.column("file", width=300)
        self.tree.column("line", width=50)
        self.tree.column("message", width=200)
        self.tree.column("code", width=400)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
    
    def browse_file(self):
        """浏览文件"""
        file_path = filedialog.askopenfilename(
            title="选择文件",
            filetypes=[("所有文件", "*.*"), ("Python文件", "*.py"), ("Java文件", "*.java"), ("JavaScript文件", "*.js"), ("C/C++文件", "*.c;*.cpp;*.h")]
        )
        if file_path:
            self.target_path.set(file_path)
    
    def browse_directory(self):
        """浏览目录"""
        directory = filedialog.askdirectory(title="选择目录")
        if directory:
            self.target_path.set(directory)
    
    def browse_rules(self):
        """浏览规则文件"""
        file_path = filedialog.askopenfilename(
            title="选择规则文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            self.rules_path.set(file_path)
    
    def browse_output(self):
        """浏览输出文件"""
        file_path = filedialog.asksaveasfilename(
            title="保存审计报告",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            self.output_path.set(file_path)
    
    def start_audit(self):
        """开始审计"""
        target = self.target_path.get()
        if not target:
            messagebox.showerror("错误", "请选择目标文件或目录")
            return
        
        if not os.path.exists(target):
            messagebox.showerror("错误", "目标路径不存在")
            return
        
        # 禁用按钮
        self.audit_button.config(state=tk.DISABLED)
        self.status_var.set("正在审计...")
        
        # 清空之前的结果
        self.clear_results()
        
        # 创建审计器
        rules_file = self.rules_path.get() if self.rules_path.get() else None
        self.auditor = CodeSecurityAuditor(rules_file)
        
        # 在后台线程中执行审计
        thread = threading.Thread(target=self.perform_audit, args=(target,))
        thread.daemon = True
        thread.start()
    
    def perform_audit(self, target):
        """执行审计"""
        try:
            if os.path.isfile(target):
                result = self.auditor.audit_file(target)
                self.status_var.set(result)
            elif os.path.isdir(target):
                results = self.auditor.audit_directory(target)
                self.status_var.set(f"审计完成，共处理 {len(results)} 个文件")
            
            # 显示结果
            self.show_results()
            
            # 生成报告
            output_file = self.output_path.get()
            if output_file:
                result = self.auditor.generate_report(output_file)
                self.status_var.set(result)
            else:
                self.status_var.set(f"审计完成，发现 {len(self.auditor.results)} 个问题")
        except Exception as e:
            self.status_var.set(f"审计失败: {e}")
        finally:
            # 启用按钮
            self.audit_button.config(state=tk.NORMAL)
    
    def show_results(self):
        """显示审计结果"""
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 添加结果
        for issue in self.auditor.results:
            self.tree.insert("", tk.END, values=(
                issue['file'],
                issue['line'],
                issue['message'],
                issue['code']
            ))
    
    def clear_results(self):
        """清空结果"""
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 清空审计器结果
        if self.auditor:
            self.auditor.results = []
        
        self.status_var.set("就绪")

if __name__ == '__main__':
    root = tk.Tk()
    app = CodeSecurityAuditGUI(root)
    root.mainloop()
