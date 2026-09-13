# -*- coding: utf-8 -*-
"""报告中心 — 综合/股权/泄露/网络/CSV 5种报告"""
import os, webbrowser, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from config.settings import DARK_THEME as DT, REPORT_DIR
from gui.widgets import ScrolledTreeview

class ReportPanel:
    def __init__(self,parent,app):
        self.app=app
        self._org_map={}
        self.frame=tk.Frame(parent,bg=DT["bg_primary"],padx=12,pady=12)
        self._create_ui()

    def _create_ui(self):
        c=DT
        tk.Label(self.frame,text="报告中心",font=("Microsoft YaHei",16,"bold"),
            bg=c["bg_primary"],fg=c["text_primary"]).pack(anchor="w",pady=(0,10))

        fc=tk.Frame(self.frame,bg=c["bg_card"],padx=10,pady=8); fc.pack(fill=tk.X,pady=(0,8))
        tk.Label(fc,text="组织:",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT)
        self.org_var=tk.StringVar()
        self.org_cb=ttk.Combobox(fc,textvariable=self.org_var,width=25,state="readonly")
        self.org_cb.pack(side=tk.LEFT,padx=4); ttk.Button(fc,text="刷新",command=self._refresh_orgs).pack(side=tk.LEFT,padx=3)

        r1=tk.Frame(self.frame,bg=c["bg_card"],padx=10,pady=6); r1.pack(fill=tk.X,pady=(0,4))
        tk.Label(r1,text="标准:",bg=c["bg_card"],fg=c["text_secondary"]).pack(side=tk.LEFT,padx=(0,10))
        ttk.Button(r1,text=" 综合暴露面报告 ",command=self._gen_html).pack(side=tk.LEFT,padx=3)
        ttk.Button(r1,text=" 导出CSV ",command=self._gen_csv).pack(side=tk.LEFT,padx=3)
        ttk.Button(r1,text=" 打开目录 ",command=self._open_dir).pack(side=tk.RIGHT,padx=3)

        r2=tk.Frame(self.frame,bg=c["bg_card"],padx=10,pady=6); r2.pack(fill=tk.X,pady=(0,8))
        tk.Label(r2,text="专题:",bg=c["bg_card"],fg=c["text_secondary"]).pack(side=tk.LEFT,padx=(0,10))
        ttk.Button(r2,text=" 股权穿透报告 ",command=self._gen_equity).pack(side=tk.LEFT,padx=3)
        ttk.Button(r2,text=" 数据泄露报告 ",command=self._gen_leak).pack(side=tk.LEFT,padx=3)
        ttk.Button(r2,text=" 网络资产图谱 ",command=self._gen_network).pack(side=tk.LEFT,padx=3)

        tf=tk.Frame(self.frame,bg=c["bg_card"]); tf.pack(fill=tk.BOTH,expand=True)
        self.tree=ScrolledTreeview(tf,columns=("title","type","size","time"),
            headings=["文件名","类型","大小","时间"],height=14)
        self.tree.pack(fill=tk.BOTH,expand=True,padx=5,pady=5)
        self.tree.tree.bind("<Double-1>",lambda e: self._open_selected())
        self._refresh_orgs(); self._refresh_list()

    def _refresh_orgs(self):
        orgs=self.app.org_mgr.get_org_names()
        self._org_map={n:o for o,n in orgs}
        self.org_cb["values"]=[n for o,n in orgs]
        if orgs: self.org_var.set(orgs[0][1])

    def _oid(self):
        name=self.org_var.get(); return self._org_map.get(name) if name else None

    def _gen_html(self):
        oid=self._oid()
        if not oid: return messagebox.showerror("错误","请选择组织")
        p=self.app.report_mgr.generate_html_report(oid)
        if p: self._refresh_list(); messagebox.showinfo("完成",f"已生成:\n{p}")

    def _gen_csv(self):
        oid=self._oid()
        p=self.app.report_mgr.export_excel(org_id=oid)
        if p: self._refresh_list(); messagebox.showinfo("完成",f"已导出:\n{p}")

    def _gen_equity(self):
        oid=self._oid()
        if not oid: return messagebox.showerror("错误","请选择组织")
        p=self.app.report_mgr.generate_equity_chain_report(oid)
        if p: self._refresh_list(); messagebox.showinfo("完成",f"已生成:\n{p}")

    def _gen_leak(self):
        oid=self._oid()
        p=self.app.report_mgr.generate_leak_report(org_id=oid)
        if p: self._refresh_list(); messagebox.showinfo("完成",f"已生成:\n{p}")

    def _gen_network(self):
        oid=self._oid()
        p=self.app.report_mgr.generate_network_map_report(org_id=oid)
        if p: self._refresh_list(); messagebox.showinfo("完成",f"已生成:\n{p}")

    def _open_dir(self):
        os.makedirs(REPORT_DIR,exist_ok=True); webbrowser.open(REPORT_DIR)

    def _open_selected(self):
        sel=self.tree.tree.selection()
        if not sel: return
        name=self.tree.tree.item(sel[0],"values")[0]
        fp=os.path.join(REPORT_DIR,name)
        if os.path.exists(fp): webbrowser.open(fp)

    @staticmethod
    def _categorize(f):
        if "暴露面综合报告" in f: return "综合"
        if "股权穿透报告" in f: return "股权"
        if "数据泄露报告" in f: return "泄露"
        if "网络资产报告" in f: return "网络"
        if "快速评估报告" in f or f.startswith("rapid_"): return "评估"
        if f.startswith("report_") or f.startswith("exposures_"): return "综合"
        if f.startswith("equity_"): return "股权"
        if f.startswith("leaks_"): return "泄露"
        if f.startswith("network_"): return "网络"
        return "-"

    def _refresh_list(self):
        self.tree.clear()
        if os.path.exists(REPORT_DIR):
            files = [f for f in os.listdir(REPORT_DIR)
                     if os.path.isfile(os.path.join(REPORT_DIR, f))]
            files.sort(key=lambda f: os.path.getmtime(os.path.join(REPORT_DIR, f)), reverse=True)
            for f in files[:30]:
                fp=os.path.join(REPORT_DIR,f)
                mt=os.path.getmtime(fp); sz=os.path.getsize(fp)
                tp="HTML" if f.endswith(".html") else ("CSV" if f.endswith(".csv") else
                    ("MD" if f.endswith(".md") else ("DOCX" if f.endswith(".docx") else
                    ("PDF" if f.endswith(".pdf") else "-"))))
                cat=self._categorize(f)
                self.tree.insert((f,f"{cat}/{tp}",f"{sz/1024:.1f}KB",
                    datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")))
