# -*- coding: utf-8 -*-
"""资产清单面板 — 来源/类型/风险/置信度筛选 + 批量标注"""
import tkinter as tk; from tkinter import ttk, messagebox
from config.settings import DARK_THEME as DT
from gui.widgets import ScrolledTreeview

class AssetPanel:
    def __init__(self, parent, app):
        self.app=app
        self._org_map={}
        self._row_org={}
        self.frame=tk.Frame(parent,bg=DT["bg_primary"],padx=12,pady=12)
        self._create_ui()

    def _create_ui(self):
        c=DT
        tk.Label(self.frame,text="资产清单",font=("Microsoft YaHei",16,"bold"),
            bg=c["bg_primary"],fg=c["text_primary"]).pack(anchor="w",pady=(0,10))

        fc=tk.Frame(self.frame,bg=c["bg_card"],padx=10,pady=8); fc.pack(fill=tk.X,pady=(0,8))
        tk.Label(fc,text="组织:",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT)
        self.org_var=tk.StringVar()
        self.org_cb=ttk.Combobox(fc,textvariable=self.org_var,width=22,state="readonly")
        self.org_cb.pack(side=tk.LEFT,padx=4)
        self.org_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        tk.Label(fc,text="风险:",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT,padx=(10,0))
        self.sev_var=tk.StringVar(value="全部")
        ttk.Combobox(fc,textvariable=self.sev_var,values=["全部","CRITICAL","HIGH","MEDIUM","LOW","INFO"],
            width=10,state="readonly").pack(side=tk.LEFT,padx=4)
        tk.Label(fc,text="类型:",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT,padx=(10,0))
        self.type_var=tk.StringVar(value="全部")
        types=["全部"]+[d[1] for d in self.app.ai_engine.ASSET_DIMENSIONS]
        ttk.Combobox(fc,textvariable=self.type_var,values=types,width=10,state="readonly"
            ).pack(side=tk.LEFT,padx=4)
        tk.Label(fc,text="置信度≥:",bg=c["bg_card"],fg=c["text_primary"]).pack(side=tk.LEFT,padx=(10,0))
        self.conf_var=tk.IntVar(value=0)
        ttk.Scale(fc,from_=0,to=100,orient=tk.HORIZONTAL,length=80,variable=self.conf_var
            ).pack(side=tk.LEFT,padx=4)
        self.conf_lbl=tk.Label(fc,text="0%",bg=c["bg_card"],fg=c["text_secondary"],width=4)
        self.conf_lbl.pack(side=tk.LEFT)
        self.conf_var.trace_add("write",lambda*a: self.conf_lbl.configure(text=f"{self.conf_var.get()}%"))
        ttk.Button(fc,text="查询",command=self.refresh).pack(side=tk.LEFT,padx=10)
        ttk.Button(fc,text="导出CSV",command=self._export).pack(side=tk.RIGHT,padx=3)
        ttk.Button(fc,text="刷新",command=self.refresh).pack(side=tk.RIGHT,padx=3)

        self.stats_var=tk.StringVar(value="总计:0")
        tk.Label(self.frame,textvariable=self.stats_var,bg=c["bg_primary"],fg="#D32F2F",
            font=("Microsoft YaHei",11)).pack(fill=tk.X,anchor="w",pady=3)

        tf=tk.Frame(self.frame,bg=c["bg_card"]); tf.pack(fill=tk.BOTH,expand=True)
        self.tree=ScrolledTreeview(tf,columns=("type","name","value","source","risk","conf","time"),
            headings=["资产类型","资产名称","资产值","来源","风险","可信度","发现时间"],height=15)
        self.tree.pack(fill=tk.BOTH,expand=True,padx=5,pady=5)
        self.tree.tree.tag_configure("reviewed", background="#FFF9C4")
        self.tree.tree.tag_configure("false_positive", background="#FFCDD2")
        self.tree.tree.bind("<Button-3>", self._on_tree_right_click)

        ba=tk.Frame(self.frame,bg=c["bg_card"],padx=8,pady=4); ba.pack(fill=tk.X,pady=(5,0))
        ttk.Button(ba,text="标记已复核",command=lambda:self._batch_tag("reviewed")).pack(side=tk.LEFT,padx=3)
        ttk.Button(ba,text="标记误报",command=lambda:self._batch_tag("false_positive")).pack(side=tk.LEFT,padx=3)
        self._refresh_orgs()

    def _refresh_orgs(self):
        orgs=self.app.org_mgr.get_org_names()
        self._org_map={n:o for o,n in orgs}
        self.org_cb["values"]=["全部"]+[n for o,n in orgs]; self.org_var.set("全部")

    def refresh(self):
        ov=self.org_var.get(); oid=None if ov in("全部","") else self._org_map.get(ov)
        sv=self.sev_var.get(); sev=None if sv=="全部" else sv
        tv=self.type_var.get()
        at=None
        if tv!="全部":
            for d in self.app.ai_engine.ASSET_DIMENSIONS:
                if d[1]==tv: at=d[0]; break
        cf=self.conf_var.get()/100.0
        tags={}
        try:
            with self.app.org_mgr._connect() as conn:
                for r in conn.execute("SELECT key, value FROM system_settings WHERE key LIKE 'tag:%'").fetchall():
                    tags[r["key"]] = r["value"]
        except Exception:
            pass
        self.tree.clear()
        self._row_org = {}
        exps=[dict(e) for e in self.app.org_mgr.list_exposures(org_id=oid,risk_level=sev)]
        filtered=[e for e in exps if (not at or e["asset_type"]==at) and e.get("confidence",0)>=cf]
        for e in filtered:
            av = e["asset_value"] or ""
            oid_row = e.get("org_id","") or ""
            if tags.get(f"tag:{oid_row}:{av}:false_positive", ""):
                conf_text, tag = "0%（误报）", "false_positive"
            elif tags.get(f"tag:{oid_row}:{av}:reviewed", ""):
                conf_text, tag = "100%（已复核）", "reviewed"
            else:
                conf_text, tag = f"{e.get('confidence',0.5):.0%}", ""
            iid = self.tree.insert((e["asset_type"],e["asset_name"],e["asset_value"],
                e["source"],e["risk_level"]or"INFO",conf_text,
                (e["discovered_at"]or"")[:16]), tags=tag)
            self._row_org[iid] = oid_row
        stats={"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0}
        for e in filtered:
            rl=e["risk_level"]or"INFO"
            if rl in stats: stats[rl]+=1
        self.stats_var.set(f"总计:{len(filtered)} | 严重:{stats.get('CRITICAL',0)} | "
            f"高危:{stats.get('HIGH',0)} | 中危:{stats.get('MEDIUM',0)} | 低危:{stats.get('LOW',0)}")

    def _set_tag(self, oid, value, tag):
        """写入单条标记：置 tag=1 并清除对立标记。"""
        other = "false_positive" if tag == "reviewed" else "reviewed"
        self.app.org_mgr.set_setting(f"tag:{oid}:{value}:{tag}", "1")
        self.app.org_mgr.set_setting(f"tag:{oid}:{value}:{other}", "")

    def _batch_tag(self, tag):
        sel=self.tree.tree.selection()
        if not sel: return messagebox.showinfo("提示","请先选择资产")
        for item in sel:
            vs=self.tree.tree.item(item,"values")
            if vs and len(vs)>=3:
                self._set_tag(self._row_org.get(item, ""), vs[2], tag)
        self.refresh()
        messagebox.showinfo("完成",f"已标记{len(sel)}条资产")

    def _on_tree_right_click(self, event):
        tree = self.tree.tree
        iid = tree.identify_row(event.y)
        if not iid:
            return
        tree.selection_set(iid)
        vs = tree.item(iid, "values")
        if not vs or len(vs) < 3:
            return
        value = str(vs[2])
        is_url = value.startswith(("http://", "https://"))
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="复制资产值", command=lambda: self._copy_value(value))
        if is_url:
            menu.add_command(label="打开链接", command=lambda: self._open_url(value))
            menu.add_command(label="打开链接并进行人工核验",
                             command=lambda: self._open_and_review(iid, value))
        menu.add_separator()
        menu.add_command(label="标记已复核", command=lambda: self._tag_item(iid, "reviewed"))
        menu.add_command(label="标记误报", command=lambda: self._tag_item(iid, "false_positive"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_value(self, value):
        self.frame.clipboard_clear()
        self.frame.clipboard_append(value)
        messagebox.showinfo("提示", "已复制资产值")

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def _open_and_review(self, iid, value):
        self._open_url(value)
        dlg = tk.Toplevel(self.frame)
        dlg.title("人工核验")
        dlg.geometry("400x170")
        dlg.configure(bg=DT["bg_primary"])
        dlg.resizable(False, False)
        dlg.transient(self.frame.winfo_toplevel())
        dlg.grab_set()
        tk.Label(dlg, text="已打开链接，请核验该资产是否真实：", bg=DT["bg_primary"],
                 fg=DT["text_primary"], font=("Microsoft YaHei", 10)).pack(anchor="w", padx=16, pady=(16, 6))
        tk.Label(dlg, text=value, bg=DT["bg_primary"], fg=DT["text_secondary"],
                 font=("Microsoft YaHei", 8), wraplength=368, justify="left").pack(anchor="w", padx=16)
        bf = tk.Frame(dlg, bg=DT["bg_primary"]); bf.pack(pady=(14, 4))
        result = {}
        def choose(tag):
            result["tag"] = tag
            dlg.destroy()
        ttk.Button(bf, text=" 真实资产 ", command=lambda: choose("reviewed")).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text=" 误报 ", command=lambda: choose("false_positive")).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text=" 取消 ", command=lambda: choose(None)).pack(side=tk.LEFT, padx=6)
        dlg.wait_window()
        if result.get("tag"):
            self._tag_item(iid, result["tag"], silent=True)

    def _tag_item(self, iid, tag, silent=False):
        vs = self.tree.tree.item(iid, "values")
        if not vs or len(vs) < 3:
            return
        self._set_tag(self._row_org.get(iid, ""), vs[2], tag)
        self.refresh()
        if not silent:
            messagebox.showinfo("完成", f"已标记为「{'已复核' if tag=='reviewed' else '误报'}」")

    def _export(self):
        p=self.app.report_mgr.export_excel()
        messagebox.showinfo("导出","已导出" if p else "失败")
