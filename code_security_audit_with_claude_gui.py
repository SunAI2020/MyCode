#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
软件代码安全审计程序 - GUI版本（集成Claude Code Security）
功能：分析代码文件，检测常见的安全漏洞和风险，并使用Claude进行安全分析
支持语言：Python、Java、C/C++、JavaScript
"""

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from datetime import datetime
from code_security_audit_with_claude import CodeSecurityAuditor

class CodeSecurityAuditGUI:
    def __init__(self, root):
        """初始化GUI"""
        self.root = root
        self.root.title("代码安全审计工具 - 集成Claude Code Security")
        self.root.geometry("1200x800")
        
        # 变量
        self.target_path = tk.StringVar()
        self.rules_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.claude_api_key = tk.StringVar()
        self.auditor = None
        
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
        
        # Claude API密钥
        ttk.Label(config_frame, text="Claude API密钥:", width=15).grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.claude_api_key, width=50, show="*").grid(row=3, column=1, columnspan=3, padx=5, pady=5)
        ttk.Label(config_frame, text="(可选，用于安全分析)", foreground="gray").grid(row=4, column=1, columnspan=3, padx=5, pady=2, sticky=tk.W)
        
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
        
        # 结果标签页
        notebook = ttk.Notebook(result_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 问题列表标签页
        issues_frame = ttk.Frame(notebook)
        notebook.add(issues_frame, text="问题列表")
        
        # 统计图表标签页
        charts_frame = ttk.Frame(notebook)
        notebook.add(charts_frame, text="统计图表")
        
        # Claude安全分析标签页
        claude_frame = ttk.Frame(notebook)
        notebook.add(claude_frame, text="Claude安全分析")
        
        # 问题列表表格
        columns = ("file", "line", "language", "message", "code")
        self.tree = ttk.Treeview(issues_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.tree.heading("file", text="文件路径")
        self.tree.heading("line", text="行号")
        self.tree.heading("language", text="语言")
        self.tree.heading("message", text="问题")
        self.tree.heading("code", text="代码")
        
        # 设置列宽
        self.tree.column("file", width=300)
        self.tree.column("line", width=50)
        self.tree.column("language", width=100)
        self.tree.column("message", width=200)
        self.tree.column("code", width=400)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(issues_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # 统计图表
        self.charts_frame = charts_frame
        
        # Claude安全分析文本框
        self.claude_text = tk.Text(claude_frame, wrap=tk.WORD)
        claude_scrollbar = ttk.Scrollbar(claude_frame, orient=tk.VERTICAL, command=self.claude_text.yview)
        self.claude_text.configure(yscroll=claude_scrollbar.set)
        claude_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.claude_text.pack(fill=tk.BOTH, expand=True)
    
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
        api_key = self.claude_api_key.get().strip() if self.claude_api_key.get().strip() else None
        self.auditor = CodeSecurityAuditor(rules_file, api_key)
        
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
            
            # 使用Claude进行安全分析
            self.auditor.analyze_with_claude()
            
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
                issue['language'],
                issue['message'],
                issue['code']
            ))
        
        # 显示统计图表
        self.show_charts()
        
        # 显示Claude安全分析
        self.show_claude_analysis()
    
    def show_charts(self):
        """显示统计信息"""
        # 清空图表框架
        for widget in self.charts_frame.winfo_children():
            widget.destroy()
        
        # 生成报告数据
        report = self.auditor.generate_report()
        issues_by_language = report.get('issues_by_language', {})
        issues_by_type = report.get('issues_by_type', {})
        
        # 创建统计信息文本
        stats_text = "# 统计信息\n\n"
        
        # 语言分布
        stats_text += "## 漏洞语言分布\n"
        if issues_by_language:
            for lang, count in issues_by_language.items():
                stats_text += f"- {lang}: {count}个\n"
        else:
            stats_text += "- 无数据\n"
        
        stats_text += "\n"
        
        # 漏洞类型分布
        stats_text += "## 漏洞类型分布\n"
        if issues_by_type:
            for vuln_type, count in issues_by_type.items():
                stats_text += f"- {vuln_type}: {count}个\n"
        else:
            stats_text += "- 无数据\n"
        
        # 创建文本框显示统计信息
        stats_textbox = tk.Text(self.charts_frame, wrap=tk.WORD)
        stats_textbox.insert(tk.END, stats_text)
        stats_textbox.config(state=tk.DISABLED)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.charts_frame, orient=tk.VERTICAL, command=stats_textbox.yview)
        stats_textbox.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        stats_textbox.pack(fill=tk.BOTH, expand=True)
    
    def show_claude_analysis(self):
        """显示Claude安全分析"""
        # 清空文本框
        self.claude_text.delete(1.0, tk.END)
        
        # 添加Claude安全分析
        if self.auditor.security_analysis:
            self.claude_text.insert(tk.END, self.auditor.security_analysis)
        else:
            self.claude_text.insert(tk.END, "未进行Claude安全分析")
    
    def clear_results(self):
        """清空结果"""
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 清空图表
        for widget in self.charts_frame.winfo_children():
            widget.destroy()
        
        # 清空Claude分析
        self.claude_text.delete(1.0, tk.END)
        
        # 清空审计器
        self.auditor = None
        
        self.status_var.set("就绪")

if __name__ == '__main__':
    root = tk.Tk()
    app = CodeSecurityAuditGUI(root)
    root.mainloop()
