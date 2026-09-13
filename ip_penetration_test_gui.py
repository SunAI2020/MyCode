#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP地址渗透测试程序 - GUI版本
功能：对指定IP地址进行端口扫描、服务识别和漏洞扫描
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
from datetime import datetime
from ip_penetration_test import IPPenetrationTester

class IPPenetrationTestGUI:
    def __init__(self, root):
        """初始化GUI"""
        self.root = root
        self.root.title("IP渗透测试工具")
        self.root.geometry("1000x700")
        
        # 变量
        self.target_ip = tk.StringVar()
        self.start_port = tk.StringVar(value="1")
        self.end_port = tk.StringVar(value="1000")
        self.timeout = tk.StringVar(value="1")
        self.tester = None
        self.scan_thread = None
        
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
        
        # IP地址
        ttk.Label(config_frame, text="目标IP:", width=10).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.target_ip, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # 端口范围
        ttk.Label(config_frame, text="端口范围:", width=10).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.start_port, width=10).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(config_frame, text="-").grid(row=1, column=2, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.end_port, width=10).grid(row=1, column=3, padx=5, pady=5)
        
        # 超时设置
        ttk.Label(config_frame, text="超时(秒):", width=10).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.timeout, width=10).grid(row=2, column=1, padx=5, pady=5)
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        self.start_button = ttk.Button(button_frame, text="开始扫描", command=self.start_scan)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(button_frame, text="停止扫描", command=self.stop_scan, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="保存报告", command=self.save_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空结果", command=self.clear_results).pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, pady=5)
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(main_frame, text="扫描结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 结果标签页
        notebook = ttk.Notebook(result_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 开放端口标签页
        ports_frame = ttk.Frame(notebook)
        notebook.add(ports_frame, text="开放端口")
        
        # 服务识别标签页
        services_frame = ttk.Frame(notebook)
        notebook.add(services_frame, text="服务识别")
        
        # 漏洞扫描标签页
        vulns_frame = ttk.Frame(notebook)
        notebook.add(vulns_frame, text="漏洞扫描")
        
        # 开放端口表格
        ports_columns = ("port", "status")
        self.ports_tree = ttk.Treeview(ports_frame, columns=ports_columns, show="headings")
        self.ports_tree.heading("port", text="端口")
        self.ports_tree.heading("status", text="状态")
        self.ports_tree.column("port", width=100)
        self.ports_tree.column("status", width=200)
        ports_scrollbar = ttk.Scrollbar(ports_frame, orient=tk.VERTICAL, command=self.ports_tree.yview)
        self.ports_tree.configure(yscroll=ports_scrollbar.set)
        ports_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ports_tree.pack(fill=tk.BOTH, expand=True)
        
        # 服务识别表格
        services_columns = ("port", "service")
        self.services_tree = ttk.Treeview(services_frame, columns=services_columns, show="headings")
        self.services_tree.heading("port", text="端口")
        self.services_tree.heading("service", text="服务")
        self.services_tree.column("port", width=100)
        self.services_tree.column("service", width=200)
        services_scrollbar = ttk.Scrollbar(services_frame, orient=tk.VERTICAL, command=self.services_tree.yview)
        self.services_tree.configure(yscroll=services_scrollbar.set)
        services_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.services_tree.pack(fill=tk.BOTH, expand=True)
        
        # 漏洞扫描表格
        vulns_columns = ("port", "service", "vulnerability")
        self.vulns_tree = ttk.Treeview(vulns_frame, columns=vulns_columns, show="headings")
        self.vulns_tree.heading("port", text="端口")
        self.vulns_tree.heading("service", text="服务")
        self.vulns_tree.heading("vulnerability", text="漏洞")
        self.vulns_tree.column("port", width=100)
        self.vulns_tree.column("service", width=150)
        self.vulns_tree.column("vulnerability", width=400)
        vulns_scrollbar = ttk.Scrollbar(vulns_frame, orient=tk.VERTICAL, command=self.vulns_tree.yview)
        self.vulns_tree.configure(yscroll=vulns_scrollbar.set)
        vulns_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.vulns_tree.pack(fill=tk.BOTH, expand=True)
    
    def validate_input(self):
        """验证输入"""
        # 验证IP地址
        ip = self.target_ip.get().strip()
        if not ip:
            messagebox.showerror("错误", "请输入目标IP地址")
            return False
        
        tester = IPPenetrationTester(ip)
        if not tester.validate_ip(ip):
            messagebox.showerror("错误", "无效的IP地址格式")
            return False
        
        # 验证端口范围
        try:
            start = int(self.start_port.get())
            end = int(self.end_port.get())
            if start < 1 or end > 65535 or start > end:
                messagebox.showerror("错误", "无效的端口范围")
                return False
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return False
        
        # 验证超时
        try:
            timeout = float(self.timeout.get())
            if timeout <= 0:
                messagebox.showerror("错误", "超时必须大于0")
                return False
        except ValueError:
            messagebox.showerror("错误", "超时必须是数字")
            return False
        
        return True
    
    def start_scan(self):
        """开始扫描"""
        if not self.validate_input():
            return
        
        # 禁用按钮
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("正在扫描...")
        
        # 清空之前的结果
        self.clear_results()
        
        # 创建测试器
        ip = self.target_ip.get().strip()
        start = int(self.start_port.get())
        end = int(self.end_port.get())
        timeout = float(self.timeout.get())
        self.tester = IPPenetrationTester(ip, start, end, timeout)
        
        # 在后台线程中执行扫描
        self.scan_thread = threading.Thread(target=self.perform_scan)
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def perform_scan(self):
        """执行扫描"""
        try:
            self.tester.start_scan()
            
            # 更新结果
            self.update_results()
            
            # 更新状态
            report = self.tester.generate_report()
            summary = report["summary"]
            self.status_var.set(f"扫描完成 - 开放端口: {summary['total_open_ports']}, 服务: {summary['total_services']}, 漏洞: {summary['total_vulnerabilities']}")
        except Exception as e:
            self.status_var.set(f"扫描失败: {e}")
        finally:
            # 启用按钮
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
    
    def stop_scan(self):
        """停止扫描"""
        if self.tester:
            self.tester.stop_scan()
        self.status_var.set("扫描已停止")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def update_results(self):
        """更新结果显示"""
        # 清空表格
        for item in self.ports_tree.get_children():
            self.ports_tree.delete(item)
        for item in self.services_tree.get_children():
            self.services_tree.delete(item)
        for item in self.vulns_tree.get_children():
            self.vulns_tree.delete(item)
        
        # 添加开放端口
        for port in sorted(self.tester.open_ports):
            self.ports_tree.insert("", tk.END, values=(port, "开放"))
        
        # 添加服务
        for port, service in sorted(self.tester.services):
            self.services_tree.insert("", tk.END, values=(port, service))
        
        # 添加漏洞
        for port, service, vuln in sorted(self.tester.vulnerabilities):
            self.vulns_tree.insert("", tk.END, values=(port, service, vuln))
    
    def save_report(self):
        """保存扫描报告"""
        if not self.tester:
            messagebox.showerror("错误", "请先执行扫描")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="保存扫描报告",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if file_path:
            try:
                report = self.tester.generate_report()
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("成功", f"报告已保存至: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存报告失败: {e}")
    
    def clear_results(self):
        """清空结果"""
        # 清空表格
        for item in self.ports_tree.get_children():
            self.ports_tree.delete(item)
        for item in self.services_tree.get_children():
            self.services_tree.delete(item)
        for item in self.vulns_tree.get_children():
            self.vulns_tree.delete(item)
        
        # 清空测试器
        self.tester = None
        
        self.status_var.set("就绪")

if __name__ == '__main__':
    root = tk.Tk()
    app = IPPenetrationTestGUI(root)
    root.mainloop()
