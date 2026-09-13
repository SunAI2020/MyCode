# -*- coding: utf-8 -*-
"""系统仪表盘 — 8图表卡片（参考 AI-VULN：白卡 + 彩色顶边 + KPI头 + 小图表）"""
import tkinter as tk
from tkinter import ttk
from datetime import date
from collections import Counter, defaultdict
from config.settings import DARK_THEME as DT, APP_NAME, APP_VERSION, COPYRIGHT
from gui.widgets import StatCard

import matplotlib
matplotlib.use("TkAgg")
from matplotlib import rcParams
rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
rcParams["axes.unicode_minus"] = False
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

RISK_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
RISK_CN = {"CRITICAL": "严重", "HIGH": "高危", "MEDIUM": "中危", "LOW": "低危", "INFO": "信息"}
# 风险等级色（与 AI-VULN SEV_COLORS 一致）
RISK_COLORS = ["#d32f2f", "#f57c00", "#fbc02d", "#388e3c", "#1976d2"]
SCAN_TYPES = ["AI搜索", "暴露面发现", "端口扫描"]
CVE_LEVELS = [("critical", "严重", "#d32f2f"), ("high", "高危", "#f57c00"),
              ("medium", "中危", "#fbc02d"), ("low", "低危", "#388e3c")]
DONUT = {"width": 0.42, "edgecolor": "white", "linewidth": 1.5}
# 卡片：(标题, 主题色) —— 参考 AI-VULN card_config
CHART_CONFIG = [
    ("CVE分布", "#ff8c00"),
    ("企业图谱(近十次)", "#881798"),
    ("组织数量", "#0078d4"),
    ("暴露面数量(近十次)", "#0078d4"),
    ("高危风险(近十次)", "#d13438"),
    ("今日扫描", "#0078d4"),
    ("风险评估", "#d13438"),
    ("任务汇总", "#107c10"),
]


def _luma(hexcolor):
    h = hexcolor.lstrip("#")
    return 0.299 * int(h[0:2], 16) + 0.587 * int(h[2:4], 16) + 0.114 * int(h[4:6], 16)


def _classify(asset_type, source):
    if asset_type in ("surface_dork", "sensitive_dir", "mgmt_entry"):
        return "暴露面发现"
    if asset_type in ("port_service", "network_device") or (source or "") in ("扫描", "Shodan", "端口扫描", "端口"):
        return "端口扫描"
    return "AI搜索"


class DashboardPanel:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=DT["bg_primary"], padx=15, pady=15)
        self._create_ui()

    def _create_ui(self):
        c = DT
        tk.Label(self.frame, text=APP_NAME, font=("Microsoft YaHei", 20, "bold"),
            bg=c["bg_primary"], fg=c["text_primary"]).pack(anchor="w", pady=(0, 5))
        tk.Label(self.frame, text=f"v{APP_VERSION} | {COPYRIGHT}", font=("Microsoft YaHei", 10),
            bg=c["bg_primary"], fg=c["text_secondary"]).pack(anchor="w", pady=(0, 10))

        cards = tk.Frame(self.frame, bg=c["bg_primary"]); cards.pack(fill=tk.X)
        self.card_org = StatCard(cards, "活跃组织", "0", c["accent_primary"])
        self.card_org.pack(side=tk.LEFT, padx=(0, 8), expand=True, fill=tk.X)
        self.card_exp = StatCard(cards, "暴露面总数", "0", c["risk_medium"])
        self.card_exp.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)
        self.card_high = StatCard(cards, "高危风险", "0", c["accent_danger"])
        self.card_high.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)
        self.card_task = StatCard(cards, "扫描任务", "0", c["risk_low"])
        self.card_task.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)
        self.card_cve = StatCard(cards, "CVE总数", "0", "#ff8c00")
        self.card_cve.pack(side=tk.LEFT, padx=(8, 0), expand=True, fill=tk.X)

        grid = tk.Frame(self.frame, bg=c["bg_primary"]); grid.pack(fill=tk.BOTH, expand=True)
        self._charts = {}
        for i, (title, accent) in enumerate(CHART_CONFIG):
            card = tk.Frame(grid, bg="#FFFFFF", highlightbackground="#e0e0e0", highlightthickness=1)
            card.grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="nsew")
            tk.Frame(card, bg=accent, height=4).pack(fill=tk.X, side=tk.TOP)
            hdr = tk.Frame(card, bg="#FFFFFF")
            hdr.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(6, 0))
            tk.Label(hdr, text=title, font=("Microsoft YaHei", 11, "bold"),
                     fg=accent, bg="#FFFFFF").pack(side=tk.LEFT)
            num_lbl = tk.Label(hdr, text="0", font=("Microsoft YaHei", 15, "bold"),
                               fg=accent, bg="#FFFFFF")
            num_lbl.pack(side=tk.RIGHT)
            fig = Figure(figsize=(3.2, 2.3), dpi=100, facecolor="#FFFFFF")
            ax = fig.add_subplot(111)
            ax.set_facecolor("#FFFFFF")
            canvas = FigureCanvasTkAgg(fig, master=card)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
            self._charts[i] = {"fig": fig, "ax": ax, "canvas": canvas, "num_lbl": num_lbl}
        for r in range(2): grid.grid_rowconfigure(r, weight=1)
        for col in range(4): grid.grid_columnconfigure(col, weight=1)

    # ===== 数据 =====
    def _org_types(self):
        try:
            with self.app.org_mgr._connect() as conn:
                rows = conn.execute("SELECT org_type, COUNT(*) c FROM organizations WHERE status='ACTIVE' GROUP BY org_type").fetchall()
            return [(r["org_type"] or "其他", r["c"]) for r in rows]
        except Exception:
            return []

    def _exposures(self):
        try:
            with self.app.org_mgr._connect() as conn:
                rows = conn.execute("SELECT asset_type, source, risk_level, discovered_at FROM exposures").fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _cve_stats(self):
        try:
            return self.app.cve_mgr.get_stats()
        except Exception:
            return {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}

    def _query_trend(self):
        try:
            return self.app.org_mgr.get_query_trend(limit=10)
        except Exception:
            return []

    # ===== 渲染 =====
    def _set_number(self, idx, number):
        num = f"{number:,}" if isinstance(number, int) else str(number)
        self._charts[idx]["num_lbl"].configure(text=num)

    def _draw_pie(self, idx, number, sizes, labels, colors):
        ax = self._charts[idx]["ax"]
        canvas = self._charts[idx]["canvas"]
        ax.clear()
        if sizes:
            _, _, autotexts = ax.pie(
                sizes, labels=labels, autopct="%1.0f%%", startangle=90,
                colors=colors, textprops={"fontsize": 9}, wedgeprops=DONUT,
                pctdistance=0.75, labeldistance=1.12)
            for t, clr in zip(autotexts, colors):
                t.set_color("white" if _luma(clr) < 128 else "#1A1A1A")
                t.set_fontsize(9); t.set_fontweight("bold")
        else:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=12, color="#999999")
        self._set_number(idx, number)
        canvas.draw()

    def _draw_trend(self, idx, days, vals):
        ax = self._charts[idx]["ax"]
        canvas = self._charts[idx]["canvas"]
        ax.clear()
        total = sum(vals)
        if days:
            x = range(len(days))
            ax.bar(x, vals, color="#0078d4", alpha=0.75, label="数量")
            cum, tot = [], 0
            for v in vals:
                tot += v; cum.append(tot)
            ax.plot(x, cum, color="#d32f2f", marker="o", markersize=3, linewidth=1.3, label="累计")
            ax.set_xticks(list(x)); ax.set_xticklabels([d[5:] for d in days], fontsize=7, rotation=30)
            ax.legend(fontsize=7)
        else:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=12, color="#999999")
        self._set_number(idx, total)
        canvas.draw()

    # ===== 各图表 =====
    def _draw_cve_pie(self, s=None):
        s = s if s is not None else self._cve_stats()
        labels = [cn for k, cn, _ in CVE_LEVELS if s.get(k)]
        sizes = [s[k] for k, _, _ in CVE_LEVELS if s.get(k)]
        colors = [clr for k, _, clr in CVE_LEVELS if s.get(k)]
        self._draw_pie(0, s.get("total", 0), sizes, labels, colors)

    def _draw_query_trend(self):
        data = self._query_trend()
        self._draw_trend(1, [d for d, _ in data], [c for _, c in data])

    def _draw_org_pie(self):
        data = self._org_types()
        self._draw_pie(2, sum(d[1] for d in data),
                       [d[1] for d in data], [d[0] for d in data], DT["chart_colors"])

    def _draw_exposure_trend(self, exps):
        by_day = defaultdict(int)
        for e in exps:
            d = (e.get("discovered_at") or "")[:10]
            if d: by_day[d] += 1
        days = sorted(by_day.keys())[-10:]
        self._draw_trend(3, days, [by_day[d] for d in days])

    def _draw_high_trend(self, exps):
        by_day = defaultdict(int)
        for e in exps:
            d = (e.get("discovered_at") or "")[:10]
            if d and e.get("risk_level") in ("CRITICAL", "HIGH"): by_day[d] += 1
        days = sorted(by_day.keys())[-10:]
        self._draw_trend(4, days, [by_day[d] for d in days])

    def _draw_scan_pie(self, exps, today_only):
        today = date.today().strftime("%Y-%m-%d")
        cnt = Counter()
        for e in exps:
            d = (e.get("discovered_at") or "")[:10]
            if today_only and d != today: continue
            cnt[_classify(e.get("asset_type"), e.get("source"))] += 1
        labels = [t for t in SCAN_TYPES if cnt.get(t)]
        sizes = [cnt[t] for t in SCAN_TYPES if cnt.get(t)]
        idx = 5 if today_only else 7
        self._draw_pie(idx, sum(sizes), sizes, labels, DT["chart_colors"][:len(sizes)])

    def _draw_risk_pie(self, exps):
        cnt = Counter(e.get("risk_level") for e in exps)
        labels = [RISK_CN[o] for o in RISK_ORDER if cnt.get(o)]
        sizes = [cnt[o] for o in RISK_ORDER if cnt.get(o)]
        colors = [RISK_COLORS[RISK_ORDER.index(o)] for o in RISK_ORDER if cnt.get(o)]
        self._draw_pie(6, sum(sizes), sizes, labels, colors)

    # ===== 刷新 =====
    def refresh(self):
        try:
            s = self.app.org_mgr.get_dashboard_stats()
            self.card_org.set_value(s["org_count"]); self.card_exp.set_value(s["exp_count"])
            self.card_high.set_value(s["high_risk"]); self.card_task.set_value(s["task_count"])
        except Exception:
            pass
        cve = self._cve_stats()
        self.card_cve.set_value(cve.get("total", 0))
        exps = self._exposures()
        self._draw_cve_pie(cve)
        self._draw_query_trend()
        self._draw_org_pie()
        self._draw_exposure_trend(exps)
        self._draw_high_trend(exps)
        self._draw_scan_pie(exps, today_only=True)
        self._draw_risk_pie(exps)
        self._draw_scan_pie(exps, today_only=False)
