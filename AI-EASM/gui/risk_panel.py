# -*- coding: utf-8 -*-
"""风险评估面板 — CVE匹配 + 数据泄露证据 双Tab"""
import os, tkinter as tk; from tkinter import ttk
from config.settings import DARK_THEME as DT
from gui.widgets import ScrolledTreeview, StatCard

class RiskPanel:
    def __init__(self,parent,app):
        self.app=app
        self.frame=tk.Frame(parent,bg=DT["bg_primary"],padx=12,pady=12)
        self._create_ui()

    def _create_ui(self):
        c=DT
        tk.Label(self.frame,text="风险评估",font=("Microsoft YaHei",16,"bold"),
            bg=c["bg_primary"],fg=c["text_primary"]).pack(anchor="w",pady=(0,10))
        cards=tk.Frame(self.frame,bg=c["bg_primary"]); cards.pack(fill=tk.X,pady=(0,8))
        self.ct=StatCard(cards,"CVE总量","...",c["accent_primary"]); self.ct.pack(side=tk.LEFT,padx=(0,5),expand=True,fill=tk.X)
        self.cc=StatCard(cards,"严重","-",c["risk_critical"]); self.cc.pack(side=tk.LEFT,padx=3,expand=True,fill=tk.X)
        self.ch=StatCard(cards,"高危","-",c["risk_high"]); self.ch.pack(side=tk.LEFT,padx=3,expand=True,fill=tk.X)
        self.cm=StatCard(cards,"中危","-",c["risk_medium"]); self.cm.pack(side=tk.LEFT,padx=3,expand=True,fill=tk.X)
        self.cl=StatCard(cards,"泄露证据","-",c["risk_critical"]); self.cl.pack(side=tk.LEFT,padx=(5,0),expand=True,fill=tk.X)

        self.tab=ttk.Notebook(self.frame); self.tab.pack(fill=tk.BOTH,expand=True)
        self._create_cve_tab(c); self._create_leak_tab(c); self.refresh()

    def _create_cve_tab(self,c):
        tab=tk.Frame(self.tab,bg=c["bg_primary"]); self.tab.add(tab,text="CVE漏洞匹配")
        fc=tk.Frame(tab,bg=c["bg_card"],padx=10,pady=8); fc.pack(fill=tk.X,pady=(5,8))
        tk.Label(fc,text="搜索(产品/服务):",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT)
        self.sv=tk.StringVar(); ttk.Entry(fc,textvariable=self.sv,width=25).pack(side=tk.LEFT,padx=4)
        ttk.Button(fc,text="搜索CVE",command=self._search).pack(side=tk.LEFT,padx=4)
        tf=tk.Frame(tab,bg=c["bg_card"]); tf.pack(fill=tk.BOTH,expand=True)
        self.cve_tree=ScrolledTreeview(tf,columns=("cve","name","severity","cvss","desc"),
            headings=["CVE编号","名称","严重程度","CVSS","描述"],height=8)
        self.cve_tree.pack(fill=tk.BOTH,expand=True,padx=5,pady=5)
        self.cve_tree.tree.bind("<<TreeviewSelect>>",self._on_cve_sel)
        df=tk.Frame(tab,bg=c["bg_card"]); df.pack(fill=tk.X,pady=(5,0))
        self.dt=tk.Text(df,height=4,bg=c["bg_secondary"],fg=c["text_primary"],state=tk.DISABLED,
            font=("Microsoft YaHei",10),bd=0,padx=10,pady=8)
        self.dt.pack(fill=tk.BOTH,expand=True,padx=5,pady=5)

    def _create_leak_tab(self,c):
        tab=tk.Frame(self.tab,bg=c["bg_primary"]); self.tab.add(tab,text="数据泄露")
        fc=tk.Frame(tab,bg=c["bg_card"],padx=10,pady=8); fc.pack(fill=tk.X,pady=(5,8))
        tk.Label(fc,text="类别:",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT)
        self.leak_cat_var=tk.StringVar(value="全部")
        ttk.Combobox(fc,textvariable=self.leak_cat_var,values=["全部","credential","architecture"],
            width=12,state="readonly").pack(side=tk.LEFT,padx=4)
        tk.Label(fc,text="严重:",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT,padx=(15,0))
        self.leak_sev_var=tk.StringVar(value="全部")
        ttk.Combobox(fc,textvariable=self.leak_sev_var,values=["全部","CRITICAL","HIGH","MEDIUM"],
            width=10,state="readonly").pack(side=tk.LEFT,padx=4)
        ttk.Button(fc,text="查询",command=self._refresh_leaks).pack(side=tk.LEFT,padx=10)
        ttk.Button(fc,text="运行泄露扫描",command=self._run_leak_scan).pack(side=tk.RIGHT,padx=3)
        tf=tk.Frame(tab,bg=c["bg_card"]); tf.pack(fill=tk.BOTH,expand=True)
        self.leak_tree=ScrolledTreeview(tf,columns=("category","pattern","snippet","severity","source","time"),
            headings=["类别","匹配模式","内容片段","严重级别","来源","时间"],height=10)
        self.leak_tree.pack(fill=tk.BOTH,expand=True,padx=5,pady=5)
        self.leak_detail=tk.Text(tf,height=3,bg=c["bg_secondary"],fg=c["text_primary"],
            state=tk.DISABLED,font=("Microsoft YaHei",9),bd=0,padx=8,pady=5)
        self.leak_detail.pack(fill=tk.X,padx=5,pady=(0,5))
        self.leak_tree.tree.bind("<<TreeviewSelect>>",self._on_leak_sel)

    def refresh(self):
        try:
            s=self.app.risk_mgr.get_cve_stats()
            self.ct.set_value(s["total"]); self.cc.set_value(s["critical"])
            self.ch.set_value(s["high"]); self.cm.set_value(s["medium"])
        except: pass
        self._refresh_leaks()

    def _search(self):
        svc=self.sv.get()
        if not svc: return
        self.cve_tree.clear()
        for v in [dict(r) for r in self.app.risk_mgr.search_cve(service=svc,limit=50)]:
            self.cve_tree.insert((v["cve_id"],v.get("name","")or"",
                v.get("severity",""),f"{(v.get('cvss_score',0)or 0):.1f}",
                (v.get("description","")or"")[:60]))

    def _on_cve_sel(self,event):
        sel=self.cve_tree.tree.selection()
        if not sel: return
        vs=self.cve_tree.tree.item(sel[0],"values")
        if vs:
            d=dict(self.app.risk_mgr.get_cve_detail(vs[0]) or {})
            if d:
                self.dt.configure(state=tk.NORMAL); self.dt.delete("1.0",tk.END)
                self.dt.insert("1.0",os.linesep.join([
                    f"CVE: {d['cve_id']}",f"名称: {d.get('name','') or ''}",
                    f"CVSS: {d.get('cvss_score','') or ''}",f"严重: {d.get('severity','') or ''}",
                    f"描述: {(d.get('description','') or '')[:200]}",
                    f"产品: {d.get('affected_products','') or ''}",
                ])); self.dt.configure(state=tk.DISABLED)

    def _refresh_leaks(self):
        self.leak_tree.clear()
        cat=None if self.leak_cat_var.get()=="全部" else self.leak_cat_var.get()
        sev=None if self.leak_sev_var.get()=="全部" else self.leak_sev_var.get()
        for lk in [dict(r) for r in self.app.org_mgr.list_leak_evidence(leak_category=cat,severity=sev)]:
            self.leak_tree.insert((lk.get("leak_category",""),lk.get("leak_pattern",""),
                (lk.get("matched_content_snippet","")or"")[:80],lk.get("severity",""),
                (lk.get("source_url","")or"")[:40],(lk.get("discovered_at","")or"")[:16]))
        self.cl.set_value(len(self.leak_tree.tree.get_children()))

    def _on_leak_sel(self,event):
        sel=self.leak_tree.tree.selection()
        if not sel: return
        vs=self.leak_tree.tree.item(sel[0],"values")
        if vs:
            self.leak_detail.configure(state=tk.NORMAL); self.leak_detail.delete("1.0",tk.END)
            self.leak_detail.insert("1.0",f"类别:{vs[0]} | 模式:{vs[1]}\n内容:{vs[2]}\n来源:{vs[4]}")
            self.leak_detail.configure(state=tk.DISABLED)

    def _run_leak_scan(self):
        from tkinter import messagebox
        oid=self.app.get_selected_org_id()
        if not oid and self.app.org_mgr.get_org_names():
            oid=self.app.org_mgr.get_org_names()[0][0]
        if not oid: return messagebox.showwarning("提示","请先创建组织")
        org=self.app.org_mgr.get_org(oid)
        if not org: return
        import threading
        threading.Thread(target=lambda:(
            self.app.leak_detector.full_leak_scan(org["org_name"],org["domain_name"] or "",oid),
            self.frame.after(0,self._refresh_leaks)
        ),daemon=True).start()
