# -*- coding: utf-8 -*-
"""可复用GUI组件 — 深色/浅色双主题 + StatCard/RiskBadge/ConfidenceBar/LogPanel/PhaseProgress"""
import tkinter as tk
import queue
from tkinter import ttk
from datetime import datetime
from config.settings import COLORS, DARK_THEME, THEME_MODE

# ===== 主题引擎 =====
def apply_theme(root, mode=None):
    m = mode or THEME_MODE
    c = DARK_THEME if m == "dark" else DARK_THEME
    style = ttk.Style(); style.theme_use("clam")
    bg = c.get("bg_primary", c.get("main_bg","#00143C"))
    fg = c.get("text_primary","#E8ECF1")
    card = c.get("bg_card", c.get("card_bg","#0A1E40"))
    accent = c.get("accent_primary", c.get("primary","#226ED8"))
    header_bg = c.get("bg_header","#000A1E")
    style.configure(".", background=bg, foreground=fg, font=("Microsoft YaHei",9))
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TButton", background=accent, foreground="#FFF", borderwidth=0, padding=(12,4))
    style.map("TButton", background=[("active",c.get("accent_secondary","#4A90D9")),("disabled","#555")])
    style.configure("TEntry", fieldbackground=card, foreground=fg, insertcolor=fg)
    style.configure("TCombobox", fieldbackground=card, foreground=fg)
    style.configure("Treeview", background=card, foreground=fg, fieldbackground=card, rowheight=28)
    style.configure("Treeview.Heading", background=header_bg, foreground=fg, font=("Microsoft YaHei",9,"bold"))
    style.map("Treeview", background=[("selected",accent)], foreground=[("selected","#FFF")])
    style.configure("TProgressbar", background=accent, troughcolor=c.get("bg_secondary","#001428"))
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=c.get("bg_sidebar","#001028"), foreground=fg, padding=[15,6])
    style.map("TNotebook.Tab", background=[("selected",card)], foreground=[("selected",accent)])
    style.configure("TScale", background=bg, troughcolor=card)
    style.configure("Primary.TButton", background=accent, foreground="#FFF", font=("Microsoft YaHei",9,"bold"), padding=(16,5))
    style.map("Primary.TButton", background=[("active",c.get("accent_secondary","#4A90D9"))])
    style.configure("Danger.TButton", background=c.get("accent_danger", c.get("danger","#F54A45")), foreground="#FFF")
    root.configure(bg=bg)

# ===== 滚动表格 =====
class ScrolledTreeview(ttk.Frame):
    def __init__(self, parent, columns, headings=None, height=10, **kw):
        super().__init__(parent)
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=height, **kw)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0,column=0,sticky="nsew"); vsb.grid(row=0,column=1,sticky="ns"); hsb.grid(row=1,column=0,sticky="ew")
        self.grid_rowconfigure(0,weight=1); self.grid_columnconfigure(0,weight=1)
        if headings:
            for col,hd in zip(columns, headings): self.tree.heading(col,text=hd); self.tree.column(col,width=100)
    def clear(self):
        for i in self.tree.get_children(): self.tree.delete(i)
    def insert(self, values, tags=None):
        return self.tree.insert("", tk.END, values=values, tags=tags if tags else ())

# ===== 统计卡片(增强版) =====
class StatCard(tk.Frame):
    def __init__(self, parent, title, value, color=None, trend=None, **kw):
        c = DARK_THEME if THEME_MODE=="dark" else DARK_THEME
        cb = c.get("bg_card",c.get("card_bg","#0A1E40"))
        super().__init__(parent, bg=cb, padx=16, pady=12,
            highlightbackground=c.get("bg_secondary","#001428"), highlightthickness=1, **kw)
        tk.Label(self, text=title, font=("Microsoft YaHei",10), bg=cb,
            fg=c.get("text_secondary","#8899AA")).pack(anchor="w")
        color = color or c.get("accent_primary", c.get("primary","#226ED8"))
        self.vl = tk.Label(self, text=str(value), font=("Microsoft YaHei",26,"bold"), bg=cb, fg=color)
        self.vl.pack(anchor="w", pady=(4,0))
        self.tl = None
        if trend:
            tc = "#44CC44" if trend[0] in "+↑" else ("#FF4444" if trend[0] in "-↓" else c.get("text_secondary","#8899AA"))
            self.tl = tk.Label(self, text=trend, font=("Microsoft YaHei",9), bg=cb, fg=tc)
            self.tl.pack(anchor="w")
    def set_value(self, value, trend=None):
        self.vl.configure(text=str(value))
        if trend and self.tl: self.tl.configure(text=trend)

# ===== 风险等级标签 =====
class RiskBadge(tk.Canvas):
    CLR = {"CRITICAL":"#FF4444","HIGH":"#FF8800","MEDIUM":"#FFCC00","LOW":"#44CC44","INFO":"#4488FF"}
    def __init__(self, parent, level="INFO", **kw):
        super().__init__(parent, width=72, height=22, highlightthickness=0, **kw)
        self.set_level(level)
    def set_level(self, level):
        self.delete("all"); self.level=level
        c=self.CLR.get(level,"#888"); self.create_rectangle(2,2,70,20,fill=c,outline="")
        self.create_text(36,11,text=level,fill="#FFF",font=("Microsoft YaHei",8,"bold"))

# ===== 置信度进度条 =====
class ConfidenceBar(tk.Frame):
    def __init__(self, parent, value=0.5, **kw):
        c = DARK_THEME if THEME_MODE=="dark" else DARK_THEME
        super().__init__(parent, bg=c.get("bg_card","#0A1E40"), height=22, **kw)
        self.canvas = tk.Canvas(self, height=22, bg=c.get("bg_card","#0A1E40"), highlightthickness=0)
        self.canvas.pack(fill=tk.X, expand=True)
        self.set_value(value)
    def set_value(self, value):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 140; v = max(0,min(1,value))
        color = "#44CC44" if v>=0.85 else ("#FFCC00" if v>=0.65 else ("#FF8800" if v>=0.4 else "#FF4444"))
        self.canvas.create_rectangle(0,5,w*v,17, fill=color, outline="")
        self.canvas.create_rectangle(0,5,w,17, outline="#8899AA")
        self.canvas.create_text(w/2,11, text=f"{v:.0%}", fill="#FFF", font=("Microsoft YaHei",8,"bold"))

# ===== 日志面板(深色终端) =====
class LogPanel(tk.Frame):
    def __init__(self, parent, height=8, **kw):
        c = DARK_THEME if THEME_MODE=="dark" else DARK_THEME
        super().__init__(parent, **kw)
        self.text = tk.Text(self, height=height, bg=c.get("bg_secondary","#001428"), fg="#34C759",
            insertbackground=c.get("accent_primary","#226ED8"), font=("Consolas",9), wrap=tk.WORD, state=tk.DISABLED)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        for t,c in [("warn","#FF8800"),("error","#FF4444"),("found","#44CC44"),("info","#4488FF"),("phase","#FFCC00")]:
            self.text.tag_configure(t, foreground=c)
        # 线程安全日志：子线程入队，主线程轮询消费
        self._q = queue.Queue()
        self.after(50, self._drain)

    def log(self, msg, level="info"):
        self._q.put((msg, level))

    def _drain(self):
        try:
            while True:
                msg, level = self._q.get_nowait()
                self._log_impl(msg, level)
        except queue.Empty:
            pass
        self.after(50, self._drain)

    def _log_impl(self, msg, level="info"):
        self.text.configure(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        lv = level
        if "[Phase" in msg: lv="phase"
        elif "错误" in msg or "FAIL" in msg: lv="error"
        elif "发现" in msg or "条" in msg: lv="found"
        self.text.insert(tk.END, f"[{ts}] ", "info")
        self.text.insert(tk.END, f"{msg}\n", lv)
        self.text.see(tk.END); self.text.configure(state=tk.DISABLED)
    def clear(self):
        self.text.configure(state=tk.NORMAL); self.text.delete("1.0",tk.END); self.text.configure(state=tk.DISABLED)

# ===== 多阶段进度条 =====
class PhaseProgressBar(tk.Frame):
    def __init__(self, parent, phases=None, **kw):
        c = DARK_THEME if THEME_MODE=="dark" else DARK_THEME
        super().__init__(parent, bg=c.get("bg_primary","#00143C"), **kw)
        self._bars = {}
        for name in (phases or ["Phase0","Phase1","Phase2","Phase3"]):
            f=tk.Frame(self, bg=c.get("bg_primary","#00143C")); f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=name, font=("Microsoft YaHei",8), bg=c.get("bg_primary","#00143C"),
                fg=c.get("text_secondary","#8899AA"), width=14, anchor="w").pack(side=tk.LEFT)
            bar = ttk.Progressbar(f, length=300, mode="determinate"); bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            self._bars[name]=bar
    def update(self, phase_name, pct):
        if phase_name in self._bars: self._bars[phase_name].configure(value=pct)

# ===== 筛选标签 =====
class FilterChip(tk.Frame):
    def __init__(self, parent, text, on_remove=None, **kw):
        c = DARK_THEME if THEME_MODE=="dark" else DARK_THEME
        super().__init__(parent, bg=c.get("accent_primary","#226ED8"), padx=8, pady=2, **kw)
        tk.Label(self, text=text, bg=c.get("accent_primary","#226ED8"), fg="#FFF",
            font=("Microsoft YaHei",8)).pack(side=tk.LEFT)
        x=tk.Label(self, text=" x", bg=c.get("accent_primary","#226ED8"), fg="#FFF",
            font=("Microsoft YaHei",8,"bold"), cursor="hand2"); x.pack(side=tk.LEFT, padx=(4,0))
        if on_remove: x.bind("<Button-1>", lambda e: on_remove())

# ===== 辅助函数 =====
def create_card(parent, **kw):
    c = DARK_THEME if THEME_MODE=="dark" else DARK_THEME
    return tk.Frame(parent, bg=c.get("bg_card","#0A1E40"),
        highlightbackground=c.get("bg_secondary","#001428"), highlightthickness=1, **kw)

def create_section_frame(parent, text, **kw):
    return ttk.LabelFrame(parent, text=text, padding="10", **kw)

def make_toolbar(parent):
    c = DARK_THEME if THEME_MODE=="dark" else DARK_THEME
    return tk.Frame(parent, bg=c.get("bg_primary","#00143C"))
