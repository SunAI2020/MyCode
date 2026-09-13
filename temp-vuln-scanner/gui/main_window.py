#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漏洞扫描系统 - 图形化用户界面
版权所有：山西有信网安科技有限公司
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine import create_engine
from config.settings import VERSION

# 尝试导入 PIL 用于图片处理
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class LoadingScreen(tk.Toplevel):
    """启动加载屏幕"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("正在加载...")
        self.geometry("400x300")
        self.resizable(False, False)
        self.overrideredirect(True)  # 无边框窗口
        
        # 居中显示
        self.center_window()
        
        # 背景色
        self.configure(bg='#1a1a2e')
        
        # 创建内容框架
        content_frame = tk.Frame(self, bg='#1a1a2e')
        content_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # 商标区域
        self.logo_label = tk.Label(
            content_frame,
            text="[LOGO]",
            font=("Arial", 80),
            bg='#1a1a2e',
            fg='#00d9ff'
        )
        self.logo_label.pack(pady=(30, 20))
        
        # 产品名称
        title_label = tk.Label(
            content_frame,
            text="漏洞扫描系统",
            font=("Microsoft YaHei", 18, "bold"),
            bg='#1a1a2e',
            fg='#ffffff'
        )
        title_label.pack(pady=(0, 5))
        
        # 英文副标题
        subtitle_label = tk.Label(
            content_frame,
            text="Vulnerability Scanner System",
            font=("Arial", 10),
            bg='#1a1a2e',
            fg='#888888'
        )
        subtitle_label.pack(pady=(0, 30))
        
        # 进度条
        self.progress = ttk.Progressbar(
            content_frame,
            mode='indeterminate',
            length=300
        )
        self.progress.pack(pady=(0, 20))
        self.progress.start(10)
        
        # 加载提示
        loading_label = tk.Label(
            content_frame,
            text="正在初始化系统...",
            font=("Microsoft YaHei", 9),
            bg='#1a1a2e',
            fg='#00d9ff'
        )
        loading_label.pack()
        
        # 版权信息
        copyright_label = tk.Label(
            content_frame,
            text="© 2026 山西有信网安科技有限公司",
            font=("Microsoft YaHei", 8),
            bg='#1a1a2e',
            fg='#666666'
        )
        copyright_label.pack(side='bottom', pady=(0, 10))
        
        # 版本号
        version_label = tk.Label(
            content_frame,
            text=f"Version {VERSION}",
            font=("Arial", 8),
            bg='#1a1a2e',
            fg='#666666'
        )
        version_label.pack(side='bottom')
    
    def center_window(self):
        """居中窗口"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def close(self):
        """关闭加载屏幕"""
        self.destroy()


class MainWindow(tk.Tk):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        self.title("漏洞扫描系统 v" + VERSION)
        self.geometry("1200x800")
        self.minsize(1024, 768)
        
        # 设置窗口图标（如果有的话）
        try:
            self.iconphoto(True, tk.PhotoImage(file='assets/icon.png'))
        except:
            pass
        
        # 居中显示
        self.center_window()
        
        # 设置样式
        self.setup_styles()
        
        # 创建界面
        self.create_ui()
        
        # 初始化扫描引擎
        self.engine = None
        self.scan_thread = None
        self.is_scanning = False
        
        # 显示加载屏幕
        self.show_loading_screen()
    
    def center_window(self):
        """居中窗口"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_styles(self):
        """设置样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 自定义颜色
        self.colors = {
            'primary': '#00d9ff',
            'secondary': '#16213e',
            'accent': '#0f3460',
            'success': '#00ff88',
            'warning': '#ffaa00',
            'danger': '#ff4444',
            'bg_dark': '#1a1a2e',
            'bg_light': '#16213e',
            'text_light': '#ffffff',
            'text_dim': '#888888'
        }
        
        # 配置按钮样式
        style.configure('Primary.TButton',
            foreground='#ffffff',
            background=self.colors['primary'],
            font=('Microsoft YaHei', 10, 'bold'))
        
        style.map('Primary.TButton',
            background=[('active', '#00b8d9')])
    
    def show_loading_screen(self):
        """显示加载屏幕"""
        self.loading = LoadingScreen(self)
        self.after(2000, self.close_loading_screen)
    
    def close_loading_screen(self):
        """关闭加载屏幕"""
        if hasattr(self, 'loading'):
            self.loading.close()
            # 初始化引擎
            self.init_engine()
    
    def init_engine(self):
        """初始化扫描引擎"""
        try:
            self.engine = create_engine()
            self.status_var.set("[OK] 系统就绪")
            self.status_label.configure(foreground=self.colors['success'])
        except Exception as e:
            messagebox.showerror("错误", f"初始化失败：{e}")
            self.status_var.set("[ERROR] 初始化失败")
            self.status_label.configure(foreground=self.colors['danger'])
    
    def create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True)
        
        # 创建菜单栏
        self.create_menu()
        
        # 创建标题栏（带 Logo）
        self.create_header(main_frame)
        
        # 创建内容区域
        self.create_content(main_frame)
        
        # 创建状态栏
        self.create_statusbar(main_frame)
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="导入目标列表", command=self.import_targets)
        file_menu.add_command(label="导出报告", command=self.export_report)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit)
        
        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="漏洞库管理", command=self.show_vuln_manager)
        tools_menu.add_command(label="CVE 搜索", command=self.show_cve_search)
        tools_menu.add_separator()
        tools_menu.add_command(label="系统设置", command=self.show_settings)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用文档", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
    
    def create_header(self, parent):
        """创建标题栏（带 Logo 和版权信息）"""
        header_frame = tk.Frame(parent, bg=self.colors['bg_dark'], height=120)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Logo 区域
        logo_frame = tk.Frame(header_frame, bg=self.colors['bg_dark'], width=120)
        logo_frame.pack(side='left', padx=(20, 10), pady=10)
        logo_frame.pack_propagate(False)
        
        # 尝试加载 Logo 图片
        self.logo_image = None
        logo_path = Path(__file__).parent.parent / 'assets' / 'logo.png'
        
        if PIL_AVAILABLE and logo_path.exists():
            try:
                img = Image.open(logo_path)
                img = img.resize((80, 80), Image.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(img)
                logo_label = tk.Label(
                    logo_frame,
                    image=self.logo_image,
                    bg=self.colors['bg_dark']
                )
                logo_label.pack(expand=True)
            except Exception as e:
                # 如果加载失败，显示文字 Logo
                self.show_text_logo(logo_frame)
        else:
            # 显示文字 Logo
            self.show_text_logo(logo_frame)
        
        # 标题区域
        title_frame = tk.Frame(header_frame, bg=self.colors['bg_dark'])
        title_frame.pack(side='left', fill='both', expand=True, pady=10)
        
        # 产品名称
        title_label = tk.Label(
            title_frame,
            text="[盾] 漏洞扫描系统",
            font=("Microsoft YaHei", 20, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['primary'],
            anchor='w'
        )
        title_label.pack(anchor='w')
        
        # 英文副标题
        subtitle_label = tk.Label(
            title_frame,
            text="Professional Vulnerability Scanner System",
            font=("Arial", 11),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_dim'],
            anchor='w'
        )
        subtitle_label.pack(anchor='w', pady=(5, 0))
        
        # 版权信息
        copyright_label = tk.Label(
            title_frame,
            text="© 2026 版权所有：山西有信网安科技有限公司",
            font=("Microsoft YaHei", 9),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_dim'],
            anchor='w'
        )
        copyright_label.pack(anchor='w', side='bottom', pady=(10, 0))
        
        # 版本号
        version_label = tk.Label(
            title_frame,
            text=f"Version {VERSION} | Build 2026.03",
            font=("Arial", 8),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_dim'],
            anchor='w'
        )
        version_label.pack(anchor='w', side='bottom')
    
    def show_text_logo(self, parent):
        """显示文字 Logo（当图片不可用时）"""
        logo_canvas = tk.Canvas(
            parent,
            width=80,
            height=80,
            bg=self.colors['bg_dark'],
            highlightthickness=0
        )
        logo_canvas.pack(expand=True)
        
        # 绘制盾牌形状
        logo_canvas.create_polygon(
            40, 10, 70, 20, 70, 50, 40, 75, 10, 50, 10, 20,
            fill=self.colors['primary'],
            outline=self.colors['success'],
            width=2
        )
        
        # 绘制对勾
        logo_canvas.create_line(
            25, 40, 35, 50, 55, 30,
            fill=self.colors['bg_dark'],
            width=3
        )
    
    def create_content(self, parent):
        """创建内容区域"""
        content_frame = ttk.Frame(parent)
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 左侧面板（扫描配置）
        left_panel = ttk.LabelFrame(content_frame, text="扫描配置", padding=10)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        
        # 目标输入
        ttk.Label(left_panel, text="扫描目标:").pack(anchor='w', pady=(0, 5))
        self.target_var = tk.StringVar(value="127.0.0.1")
        target_entry = ttk.Entry(left_panel, textvariable=self.target_var, width=30)
        target_entry.pack(fill='x', pady=(0, 10))
        
        # 端口配置
        ttk.Label(left_panel, text="端口范围:").pack(anchor='w', pady=(0, 5))
        self.ports_var = tk.StringVar(value="1-1000")
        ports_entry = ttk.Entry(left_panel, textvariable=self.ports_var, width=30)
        ports_entry.pack(fill='x', pady=(0, 10))
        
        # 扫描选项
        options_frame = ttk.LabelFrame(left_panel, text="扫描选项", padding=5)
        options_frame.pack(fill='x', pady=(0, 10))
        
        self.version_detect_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="版本检测",
            variable=self.version_detect_var
        ).pack(anchor='w')
        
        self.os_detect_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="操作系统检测",
            variable=self.os_detect_var
        ).pack(anchor='w')
        
        # 扫描按钮
        self.scan_button = ttk.Button(
            left_panel,
            text=">> 开始扫描",
            command=self.start_scan,
            style='Primary.TButton'
        )
        self.scan_button.pack(fill='x', pady=(10, 5))
        
        self.stop_button = ttk.Button(
            left_panel,
            text="[] 停止扫描",
            command=self.stop_scan,
            state='disabled'
        )
        self.stop_button.pack(fill='x')
        
        # 右侧面板（结果显示）
        right_panel = ttk.LabelFrame(content_frame, text="扫描结果", padding=10)
        right_panel.pack(side='right', fill='both', expand=True)
        
        # 结果文本区域
        self.result_text = scrolledtext.ScrolledText(
            right_panel,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg='#1a1a2e',
            fg='#00ff88',
            insertbackground='#00ff88'
        )
        self.result_text.pack(fill='both', expand=True)
        
        # 结果统计
        stats_frame = ttk.Frame(right_panel)
        stats_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(stats_frame, text="主机:", width=8).pack(side='left')
        self.hosts_count_var = tk.StringVar(value="0")
        ttk.Label(stats_frame, textvariable=self.hosts_count_var, 
                 foreground=self.colors['primary']).pack(side='left', padx=(0, 15))
        
        ttk.Label(stats_frame, text="服务:", width=8).pack(side='left')
        self.services_count_var = tk.StringVar(value="0")
        ttk.Label(stats_frame, textvariable=self.services_count_var,
                 foreground=self.colors['primary']).pack(side='left', padx=(0, 15))
        
        ttk.Label(stats_frame, text="漏洞:", width=8).pack(side='left')
        self.vulns_count_var = tk.StringVar(value="0")
        ttk.Label(stats_frame, textvariable=self.vulns_count_var,
                 foreground=self.colors['danger']).pack(side='left')
    
    def create_statusbar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill='x', side='bottom')
        
        self.status_var = tk.StringVar(value="正在初始化...")
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief='sunken',
            anchor='w'
        )
        self.status_label.pack(fill='x', side='left', expand=True)
        
        # 进度指示器
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            maximum=100,
            length=200
        )
        self.progress_bar.pack(side='right', padx=(10, 10))
    
    def start_scan(self):
        """开始扫描"""
        if self.is_scanning:
            messagebox.showwarning("警告", "扫描正在进行中!")
            return
        
        target = self.target_var.get().strip()
        if not target:
            messagebox.showerror("错误", "请输入扫描目标!")
            return
        
        # 法律免责声明确认
        if not messagebox.askyesno(
            "法律免责声明",
            "[警告] 重要提示\n\n"
            "本工具仅用于授权的安全测试和漏洞评估。\n"
            "使用前请确保：\n"
            "1. 您拥有目标系统的所有权或已获得书面授权\n"
            "2. 您的使用符合当地法律法规\n"
            "3. 您了解并承担使用本工具的全部责任\n\n"
            "未经授权扫描他人系统是违法行为!\n\n"
            "是否同意上述条款并继续？",
            icon='warning'
        ):
            return
        
        self.is_scanning = True
        self.scan_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.status_var.set("[扫描中]...")
        self.progress_bar.start()
        
        # 清空结果区域
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, f"{'='*60}\n")
        self.result_text.insert(tk.END, f"扫描目标：{target}\n")
        self.result_text.insert(tk.END, f"端口范围：{self.ports_var.get()}\n")
        self.result_text.insert(tk.END, f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.result_text.insert(tk.END, f"{'='*60}\n\n")
        
        # 在后台线程执行扫描
        self.scan_thread = threading.Thread(target=self.run_scan, args=(target,))
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def run_scan(self, target):
        """执行扫描（后台线程）"""
        try:
            if self.engine:
                result = self.engine.scan_sync(
                    target=target,
                    ports=self.ports_var.get(),
                    version_detect=self.version_detect_var.get(),
                    os_detect=self.os_detect_var.get(),
                    generate_report=False
                )
                
                # 更新 UI（在主线程）
                self.after(0, self.update_scan_result, result)
            else:
                self.after(0, lambda: messagebox.showerror("错误", "引擎未初始化"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("扫描错误", str(e)))
        finally:
            self.after(0, self.scan_finished)
    
    def update_scan_result(self, result):
        """更新扫描结果"""
        self.result_text.insert(tk.END, f"\n[OK] 扫描完成!\n\n")
        self.result_text.insert(tk.END, f"发现主机：{len(result.hosts)}\n")
        self.result_text.insert(tk.END, f"发现服务：{len(result.services)}\n")
        self.result_text.insert(tk.END, f"发现漏洞：{len(result.vulnerabilities)}\n\n")
        
        # 更新统计
        self.hosts_count_var.set(str(len(result.hosts)))
        self.services_count_var.set(str(len(result.services)))
        self.vulns_count_var.set(str(len(result.vulnerabilities)))
        
        # 显示漏洞详情
        if result.vulnerabilities:
            self.result_text.insert(tk.END, f"\n{'='*60}\n")
            self.result_text.insert(tk.END, f"漏洞详情:\n")
            self.result_text.insert(tk.END, f"{'='*60}\n\n")
            
            for vuln in result.vulnerabilities:
                severity_color = {
                    'CRITICAL': '#ff0000',
                    'HIGH': '#ff6600',
                    'MEDIUM': '#ffaa00',
                    'LOW': '#00ff00'
                }.get(vuln.severity, '#ffffff')
                
                self.result_text.insert(tk.END, f"[{vuln.severity}] {vuln.cve_id}\n",
                                       ('color', severity_color))
                self.result_text.insert(tk.END, f"  服务：{vuln.service}:{vuln.port}\n")
                self.result_text.insert(tk.END, f"  描述：{vuln.description[:100]}...\n\n")
        
        self.result_text.see(tk.END)
    
    def scan_finished(self):
        """扫描完成"""
        self.is_scanning = False
        self.scan_button.configure(state='normal')
        self.stop_button.configure(state='disabled')
        self.status_var.set("[OK] 扫描完成")
        self.progress_bar.stop()
    
    def stop_scan(self):
        """停止扫描"""
        if self.is_scanning and self.engine:
            self.engine.cancel_scan()
            self.is_scanning = False
            self.scan_button.configure(state='normal')
            self.stop_button.configure(state='disabled')
            self.status_var.set("[停止] 扫描已停止")
            self.progress_bar.stop()
    
    def import_targets(self):
        """导入目标列表"""
        file_path = filedialog.askopenfilename(
            title="选择目标列表文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    targets = [line.strip() for line in f if line.strip()]
                self.target_var.set('\n'.join(targets[:10]))  # 只显示前 10 个
                messagebox.showinfo("成功", f"已导入 {len(targets)} 个目标")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败：{e}")
    
    def export_report(self):
        """导出报告"""
        file_path = filedialog.asksaveasfilename(
            title="保存报告",
            defaultextension=".html",
            filetypes=[("HTML 文件", "*.html"), ("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            messagebox.showinfo("提示", "报告导出功能开发中...")
    
    def show_vuln_manager(self):
        """显示漏洞库管理"""
        messagebox.showinfo("提示", "漏洞库管理功能开发中...")
    
    def show_cve_search(self):
        """显示 CVE 搜索"""
        messagebox.showinfo("提示", "CVE 搜索功能开发中...")
    
    def show_settings(self):
        """显示系统设置"""
        messagebox.showinfo("提示", "系统设置功能开发中...")
    
    def show_help(self):
        """显示帮助"""
        help_text = """
漏洞扫描系统 - 使用帮助

1. 在"扫描目标"输入框中输入 IP 地址、IP 范围或 CIDR
2. 配置端口范围（默认：1-1000）
3. 选择扫描选项（版本检测、操作系统检测）
4. 点击"开始扫描"按钮

支持的目标格式:
- 单个 IP: 192.168.1.1
- IP 范围：192.168.1.1-100
- CIDR: 192.168.1.0/24

© 2026 山西有信网安科技有限公司
        """
        messagebox.showinfo("使用帮助", help_text)
    
    def show_about(self):
        """显示关于对话框"""
        about_text = f"""
🛡️ 漏洞扫描系统
Vulnerability Scanner System

版本：{VERSION}
构建：2026.03

━━━━━━━━━━━━━━━━━━━━━━━━
© 2026 版权所有：山西有信网安科技有限公司
━━━━━━━━━━━━━━━━━━━━━━━━

本软件仅供授权的安全测试使用。
未经授权扫描他人系统是违法行为。

技术支持：support@youxinwang'an.com
官方网站：www.youxinwangan.com
        """
        
        # 创建自定义关于对话框
        about_win = tk.Toplevel(self)
        about_win.title("关于")
        about_win.geometry("450x350")
        about_win.resizable(False, False)
        about_win.transient(self)
        
        # 背景色
        about_win.configure(bg=self.colors['bg_dark'])
        
        # Logo 区域
        logo_label = tk.Label(
            about_win,
            text="[盾]",
            font=("Arial", 60),
            bg=self.colors['bg_dark'],
            fg=self.colors['primary']
        )
        logo_label.pack(pady=(30, 10))
        
        # 产品名称
        title_label = tk.Label(
            about_win,
            text="漏洞扫描系统",
            font=("Microsoft YaHei", 18, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_light']
        )
        title_label.pack()
        
        # 版本信息
        version_label = tk.Label(
            about_win,
            text=f"Version {VERSION} | Build 2026.03",
            font=("Arial", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_dim']
        )
        version_label.pack(pady=(5, 20))
        
        # 版权信息（突出显示）
        copyright_box = tk.Frame(about_win, bg=self.colors['accent'], relief='ridge', bd=2)
        copyright_box.pack(padx=20, pady=10, fill='x')
        
        copyright_label = tk.Label(
            copyright_box,
            text="© 2026 版权所有：山西有信网安科技有限公司",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['accent'],
            fg=self.colors['primary']
        )
        copyright_label.pack(pady=15)
        
        # 免责声明
        disclaimer_label = tk.Label(
            about_win,
            text="本软件仅供授权的安全测试使用",
            font=("Microsoft YaHei", 8),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_dim']
        )
        disclaimer_label.pack(pady=(10, 5))
        
        # 关闭按钮
        close_btn = ttk.Button(
            about_win,
            text="关闭",
            command=about_win.destroy
        )
        close_btn.pack(pady=(10, 20))
        
        # 居中
        about_win.update_idletasks()
        x = (about_win.winfo_screenwidth() // 2) - (about_win.winfo_width() // 2)
        y = (about_win.winfo_screenheight() // 2) - (about_win.winfo_height() // 2)
        about_win.geometry(f"+{x}+{y}")


def main():
    """主函数"""
    app = MainWindow()
    app.mainloop()


if __name__ == '__main__':
    main()
