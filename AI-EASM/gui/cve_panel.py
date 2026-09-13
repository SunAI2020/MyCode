# -*- coding: utf-8 -*-
"""CVE数据库管理 — 抓取最近 X 天 CVE 并去重导入"""
import tkinter as tk, threading
from tkinter import ttk, messagebox
from config.settings import DARK_THEME as DT
from gui.widgets import LogPanel


class CVEPanel:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=DT["bg_primary"], padx=12, pady=12)
        self._create_ui()
        self._refresh_stats()

    def _create_ui(self):
        c = DT
        tk.Label(self.frame, text="CVE数据库管理", font=("Microsoft YaHei", 16, "bold"),
            bg=c["bg_primary"], fg=c["text_primary"]).pack(anchor="w", pady=(0, 10))

        cards = tk.Frame(self.frame, bg=c["bg_primary"]); cards.pack(fill=tk.X)
        self._sv = {}
        for k, lbl, clr in [("total", "CVE总数", c["accent_primary"]), ("critical", "严重", c["accent_danger"]),
                            ("high", "高危", c["risk_high"]), ("medium", "中危", c["risk_medium"]),
                            ("low", "低危", c["risk_low"])]:
            sv = tk.StringVar(value="0")
            f = tk.Frame(cards, bg=c["bg_card"], padx=12, pady=8)
            f.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)
            tk.Label(f, textvariable=sv, font=("Microsoft YaHei", 20, "bold"), bg=c["bg_card"], fg=clr).pack()
            tk.Label(f, text=lbl, font=("Microsoft YaHei", 8), bg=c["bg_card"], fg=c["text_secondary"]).pack()
            self._sv[k] = sv

        cfg = tk.Frame(self.frame, bg=c["bg_card"], padx=12, pady=10); cfg.pack(fill=tk.X, pady=(10, 8))
        tk.Label(cfg, text="抓取最近", bg=c["bg_card"], fg=c["text_primary"]).pack(side=tk.LEFT)
        self.days_var = tk.StringVar(value="7")
        ttk.Entry(cfg, textvariable=self.days_var, width=6).pack(side=tk.LEFT, padx=4)
        tk.Label(cfg, text="天的 CVE", bg=c["bg_card"], fg=c["text_primary"]).pack(side=tk.LEFT)
        tk.Label(cfg, text="  NVD API Key(可选):", bg=c["bg_card"], fg=c["text_primary"]).pack(side=tk.LEFT, padx=(15, 0))
        self.api_key_var = tk.StringVar(value=self.app.org_mgr.get_setting("nvd_api_key", ""))
        ttk.Entry(cfg, textvariable=self.api_key_var, width=32, show="*").pack(side=tk.LEFT, padx=4)
        self.fetch_btn = ttk.Button(cfg, text=" 搜索并导入 ", command=self._fetch_import)
        self.fetch_btn.pack(side=tk.LEFT, padx=(12, 3))
        ttk.Button(cfg, text=" 刷新统计 ", command=self._refresh_stats).pack(side=tk.LEFT, padx=3)

        lf = tk.Frame(self.frame, bg=c["bg_card"]); lf.pack(fill=tk.BOTH, expand=True)
        self.log_panel = LogPanel(lf, height=15)
        self.log_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _refresh_stats(self):
        try:
            stats = self.app.cve_mgr.get_stats()
            self._sv["total"].set(str(stats["total"]))
            self._sv["critical"].set(str(stats["critical"]))
            self._sv["high"].set(str(stats["high"]))
            self._sv["medium"].set(str(stats["medium"]))
            self._sv["low"].set(str(stats["low"]))
        except Exception as e:
            try: self.log_panel.log(f"[统计] 读取失败: {e}")
            except Exception: pass

    def _fetch_import(self):
        try:
            days = int(self.days_var.get().strip())
        except Exception:
            return messagebox.showerror("错误", "请输入有效的天数")
        api_key = self.api_key_var.get().strip()
        self.app.org_mgr.set_setting("nvd_api_key", api_key)
        self.fetch_btn.configure(state=tk.DISABLED)
        self.log_panel.clear()
        self.log_panel.log(f"=== 抓取最近 {days} 天 CVE ===")

        def run():
            try:
                records = self.app.cve_mgr.fetch_recent_cves(days, api_key, log_cb=self.log_panel.log)
                self.log_panel.log(f"抓取完成: {len(records)} 条")
                added, dup = self.app.cve_mgr.import_cves(records)
                self.log_panel.log(f"导入完成: 新增 {added} 条, 重复跳过 {dup} 条")
            except Exception as e:
                self.log_panel.log(f"[失败] {e}")
            self.frame.after(0, lambda: self.fetch_btn.configure(state=tk.NORMAL))
            self.frame.after(0, self._refresh_stats)
        threading.Thread(target=run, daemon=True).start()
