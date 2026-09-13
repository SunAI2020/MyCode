# -*- coding: utf-8 -*-
"""主窗口 — 星海EASM 深色主题 5级中控台"""
import tkinter as tk, os, sys
from tkinter import ttk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import APP_NAME, APP_VERSION, COLORS, FULLSCREEN, THEME_MODE, DARK_THEME, COPYRIGHT, LOGO_PATH
from gui.widgets import apply_theme
from core.org_manager import OrgManager
from core.scan_manager import ScanManager
from core.risk_manager import RiskManager
from core.ai_search_engine import AISearchEngine
from core.report_manager import ReportManager
from core.enrichment_engine import EnrichmentEngine
from core.equity_chain_engine import EquityChainEngine
from core.leak_detector import LeakDetector
from core.shadow_asset_detector import ShadowAssetDetector
from core.rapid_assessor import RapidAssessor
from core.cache_manager import CacheManager
from core.rate_limiter import RateLimiter
from core.cve_manager import CVEManager
from core.browser_login import BrowserLoginManager

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        if FULLSCREEN:
            self.root.state("zoomed")
        else:
            self.root.geometry("1400x900")
        apply_theme(self.root)
        self.root.bind("<Escape>", self._toggle_fullscreen)

        # 服务层初始化
        self.org_mgr = OrgManager()
        self.cache_mgr = CacheManager()
        self.rate_limiter = RateLimiter()
        self.enrichment = EnrichmentEngine(self.org_mgr, self.cache_mgr)
        self.equity_engine = EquityChainEngine(self.org_mgr, self.enrichment, rate_limiter=self.rate_limiter)
        self.browser_login = BrowserLoginManager(self.org_mgr.credential_store)
        self.leak_detector = LeakDetector(self.org_mgr, self.enrichment)
        self.shadow_detector = ShadowAssetDetector(self.org_mgr)
        self.scan_mgr = ScanManager(self.org_mgr)
        self.risk_mgr = RiskManager()
        self.cve_mgr = CVEManager()
        self.report_mgr = ReportManager(self.org_mgr)
        self.ai_engine = AISearchEngine(self.org_mgr, self.enrichment,
            self.leak_detector, self.shadow_detector, self.cache_mgr)
        self.rapid_assessor = RapidAssessor(self.org_mgr, self.enrichment,
            self.equity_engine, self.ai_engine, self.leak_detector,
            self.shadow_detector, self.report_mgr)

        self._create_layout()
        self._refresh_dashboard()

    def _toggle_fullscreen(self, event=None):
        if self.root.state() == "zoomed":
            self.root.state("normal")
        else:
            self.root.state("zoomed")

    def _create_layout(self):
        c = DARK_THEME if THEME_MODE == "dark" else DARK_THEME
        # Header
        hdr = tk.Frame(self.root, bg=c.get("bg_header","#000A1E"), height=52)
        hdr.pack(fill=tk.X, side=tk.TOP); hdr.pack_propagate(False)
        # Logo
        if os.path.exists(LOGO_PATH):
            try:
                from PIL import Image, ImageTk
                img = Image.open(LOGO_PATH)
                ratio = 40 / img.size[1]
                img = img.resize((int(img.size[0]*ratio), 40), Image.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(hdr, image=self.logo_img, bg=c["bg_header"]).pack(side=tk.LEFT, padx=(12,6), pady=6)
            except: pass
        tk.Label(hdr, text=f"  {APP_NAME}", font=("Microsoft YaHei",15,"bold"),
            bg=c["bg_header"], fg=c.get("text_primary","#E8ECF1")).pack(side=tk.LEFT, pady=10)
        tk.Label(hdr, text=f"  v{APP_VERSION} | {COPYRIGHT}", font=("Microsoft YaHei",8),
            bg=c["bg_header"], fg=c.get("text_secondary","#8899AA")).pack(side=tk.LEFT, padx=10, pady=18)
        self.status_var = tk.StringVar(value="就绪 | 按Esc切换最大化/还原")
        tk.Label(hdr, textvariable=self.status_var, font=("Microsoft YaHei",9),
            bg=c["bg_header"], fg=c.get("text_secondary","#8899AA")).pack(side=tk.RIGHT, padx=18, pady=15)
        # Body
        body = tk.Frame(self.root, bg=c.get("bg_primary","#00143C"))
        body.pack(fill=tk.BOTH, expand=True)
        # Sidebar
        sb = tk.Frame(body, bg=c.get("bg_sidebar","#001028"), width=200)
        sb.pack(side=tk.LEFT, fill=tk.Y); sb.pack_propagate(False)
        # Content
        content = tk.Frame(body, bg=c.get("bg_primary","#00143C"))
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.notebook = ttk.Notebook(content); self.notebook.pack(fill=tk.BOTH, expand=True)
        # 8个侧边栏菜单
        self.menu_btns = {}
        menu_items = [
            (chr(0x2302)+"  系统仪表盘",0),(chr(0x2630)+"  组织管理",1),
            (chr(0x2606)+"  AI资产发现",2),(chr(0x2261)+"  资产清单",3),
            (chr(0x26A0)+"  风险评估",4),(chr(0x270E)+"  报告中心",5),
            (chr(0x1F310)+"  企业图谱",6),(chr(0x2699)+"  系统设置",7),
            (chr(0x1F5C4)+"  CVE库管理",8),
        ]
        for text, idx in menu_items:
            btn = tk.Button(sb, text=text, font=("Microsoft YaHei",11),
                bg=c["bg_sidebar"], fg=c.get("text_secondary","#8899AA"), bd=0,
                anchor="w", padx=20, pady=10,
                activebackground=c.get("accent_primary","#226ED8"),
                activeforeground="#FFFFFF", cursor="hand2",
                command=lambda i=idx: self._switch_tab(i))
            btn.pack(fill=tk.X); self.menu_btns[idx] = btn
        # 面板导入
        from gui.dashboard_panel import DashboardPanel
        from gui.org_panel import OrgPanel
        from gui.scan_panel import ScanPanel
        from gui.asset_panel import AssetPanel
        from gui.risk_panel import RiskPanel
        from gui.report_panel import ReportPanel
        from gui.network_map_panel import NetworkMapPanel
        from gui.settings_panel import SettingsPanel
        from gui.cve_panel import CVEPanel
        self.panels = [
            DashboardPanel(self.notebook, self), OrgPanel(self.notebook, self),
            ScanPanel(self.notebook, self), AssetPanel(self.notebook, self),
            RiskPanel(self.notebook, self), ReportPanel(self.notebook, self),
            NetworkMapPanel(self.notebook, self), SettingsPanel(self.notebook, self),
            CVEPanel(self.notebook, self),
        ]
        for p in self.panels: self.notebook.add(p.frame, text="")
        # 仅隐藏主 Notebook 的标签栏（侧边栏导航），改用自定义 style，避免影响子面板内 Notebook 的标签
        _style = ttk.Style()
        _style.layout("Main.TNotebook.Tab", [])
        self.notebook.configure(style="Main.TNotebook")
        self._switch_tab(0)

    def _switch_tab(self, idx):
        self.notebook.select(idx)
        c = DARK_THEME
        for i, btn in self.menu_btns.items():
            btn.configure(bg=c.get("bg_card","#0A1E40") if i==idx else c.get("bg_sidebar","#001028"),
                fg=c.get("accent_primary","#226ED8") if i==idx else "#8899AA")
        # 切换到面板时刷新其组织下拉，保证组织改名/新增/删除后同步
        panel = self.panels[idx]
        if hasattr(panel, "_refresh_orgs"):
            try: panel._refresh_orgs()
            except Exception: pass

    def refresh_reports(self):
        """报告中心列表刷新（AI搜索/保存报告后调用）"""
        try: self.panels[5]._refresh_list()
        except Exception: pass

    def set_status(self, text): self.status_var.set(text)
    def get_selected_org_id(self): return self.panels[1].get_selected_org_id()
    def _refresh_dashboard(self):
        try: self.panels[0].refresh()
        except: pass
        self.root.after(30000, self._refresh_dashboard)
    def run(self): self.root.mainloop()