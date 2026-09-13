# -*- coding: utf-8 -*-
"""企业图谱面板 — Canvas交互式关系图谱"""
import tkinter as tk
from tkinter import ttk
from config.settings import DARK_THEME as C

class NetworkMapPanel:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=C["bg_primary"], padx=12, pady=12)
        self._org_map = {}
        self._nodes = {}; self._scale = 1.0
        self._drag_data = {"x":0,"y":0}
        self._create_ui()

    def _create_ui(self):
        tk.Label(self.frame, text="企业图谱", font=("Microsoft YaHei",16,"bold"),
            bg=C["bg_primary"], fg=C["text_primary"]).pack(anchor="w", pady=(0,8))
        fbar = tk.Frame(self.frame, bg=C["bg_card"], padx=10, pady=6)
        fbar.pack(fill=tk.X, pady=(0,6))
        tk.Label(fbar, text="组织:", bg=C["bg_card"], fg=C["text_primary"]).pack(side=tk.LEFT)
        self.org_var = tk.StringVar()
        self.org_cb = ttk.Combobox(fbar, textvariable=self.org_var, width=20, state="readonly")
        self.org_cb.pack(side=tk.LEFT, padx=5)
        tk.Label(fbar, text="深度:", bg=C["bg_card"], fg=C["text_primary"]).pack(side=tk.LEFT, padx=(15,0))
        self.depth_var = tk.StringVar(value="4")
        ttk.Combobox(fbar, textvariable=self.depth_var, values=["1","2","3","4"], width=3, state="readonly").pack(side=tk.LEFT, padx=5)
        ttk.Button(fbar, text="刷新图谱", command=self._refresh).pack(side=tk.LEFT, padx=10)
        ttk.Button(fbar, text="适应窗口", command=self._fit).pack(side=tk.LEFT, padx=3)

        paned = tk.PanedWindow(self.frame, bg=C["bg_primary"], orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(paned, bg=C["bg_secondary"], highlightthickness=0, cursor="hand2")
        paned.add(self.canvas, minsize=600)
        self.canvas.bind("<Button-1>", lambda e: setattr(self,"_drag_data",{"x":e.x,"y":e.y}))
        self.canvas.bind("<B1-Motion>", lambda e: (self.canvas.scan_dragto(e.x-self._drag_data["x"],e.y-self._drag_data["y"],gain=1),setattr(self,"_drag_data",{"x":e.x,"y":e.y})))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.scale("all",e.x,e.y,1.1 if e.delta>0 else 0.9,1.1 if e.delta>0 else 0.9))
        self.canvas.bind("<Double-Button-1>", lambda e: self._fit())

        detail = tk.Frame(paned, bg=C["bg_card"], width=250)
        paned.add(detail, minsize=200)
        tk.Label(detail, text="节点详情", font=("Microsoft YaHei",12,"bold"),
            bg=C["bg_card"], fg=C["text_primary"]).pack(pady=8)
        self.detail_text = tk.Text(detail, bg=C["bg_secondary"], fg=C["text_primary"],
            font=("Microsoft YaHei",9), wrap=tk.WORD, state=tk.DISABLED, bd=0, padx=8, pady=8)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        leg = tk.Frame(self.frame, bg=C["bg_card"], padx=10, pady=4)
        leg.pack(fill=tk.X, pady=(6,0))
        for color, label in [("#226ED8","企业"),("#8B5CF6","子公司"),("#44CC44","域名"),
            ("#FF8844","IP"),("#FF4444","泄露")]:
            dot = tk.Canvas(leg, width=14, height=14, bg=C["bg_card"], highlightthickness=0)
            dot.create_oval(1,1,13,13, fill=color, outline=""); dot.pack(side=tk.LEFT, padx=(8,3))
            tk.Label(leg, text=label, bg=C["bg_card"], fg=C["text_secondary"],
                font=("Microsoft YaHei",8)).pack(side=tk.LEFT, padx=(2,0))
        tk.Label(leg, text="  ── 控股  ··· 疑似  ═══ 影子", bg=C["bg_card"],
            fg=C["text_muted"], font=("Microsoft YaHei",8)).pack(side=tk.RIGHT, padx=10)
        self._refresh_orgs()

    def _refresh_orgs(self):
        orgs = self.app.org_mgr.get_org_names()
        self._org_map = {name: oid for oid, name in orgs}
        self.org_cb["values"] = [name for oid, name in orgs]
        if orgs: self.org_var.set(orgs[0][1])

    def _get_org_id(self):
        v = self.org_var.get()
        return self._org_map.get(v) if v else None

    def _refresh(self):
        oid = self._get_org_id()
        if not oid: return
        self.canvas.delete("all"); self._nodes.clear()
        org = self.app.org_mgr.get_org(oid)
        if not org: return
        root_name = org["org_name"]
        subs = self.app.org_mgr.list_subsidiaries(parent_org_id=oid)
        cw = self.canvas.winfo_width() or 900
        cx = cw // 2

        # Root
        rid = self._draw_node(cx, 60, root_name, "company")
        if subs:
            n = len(subs)
            for i, sub in enumerate(subs):
                x = cx + (i-(n-1)/2)*180; y = 200
                sid = self._draw_node(x, y, sub["sub_name"], "subsidiary")
                x1,y1,x2,y2 = self.canvas.coords(rid)
                x3,y3,x4,y4 = self.canvas.coords(sid)
                self.canvas.create_line((x1+x2)/2,(y1+y2)/2,(x3+x4)/2,(y3+y4)/2,
                    fill="#8899AA", width=2, tags="edge")
        else:
            self.canvas.create_text(cx, 280, text="暂无股权链数据\n请先在AI资产发现中搜索",
                fill=C["text_muted"], font=("Microsoft YaHei",12))
        self._fit()

    def _draw_node(self, x, y, label, ntype):
        colors = {"company":"#226ED8","subsidiary":"#8B5CF6"}
        r = 35 if ntype=="company" else 28
        nid = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=colors.get(ntype,"#4488FF"),
            outline="", tags=("node",ntype,label))
        self.canvas.create_text(x, y, text=label[:8], fill="#FFFFFF",
            font=("Microsoft YaHei",9,"bold"))
        self._nodes[label] = (x, y, ntype)
        # Click handler
        self.canvas.tag_bind(nid, "<Button-1>", lambda e, n=label: self._show_detail(n))
        return nid

    def _fit(self):
        bbox = self.canvas.bbox("all")
        if bbox:
            bw = bbox[2]-bbox[0]; bh = bbox[3]-bbox[1]
            cw = self.canvas.winfo_width() or 900; ch = self.canvas.winfo_height() or 500
            if bw > 0 and bh > 0:
                s = min(cw/bw, ch/bh) * 0.85
                self.canvas.scale("all", 0, 0, s, s)

    def _show_detail(self, name):
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, f"名称: {name}\n")
        if name in self._nodes:
            self.detail_text.insert(tk.END, f"类型: {self._nodes[name][2]}\n")
        self.detail_text.configure(state=tk.DISABLED)