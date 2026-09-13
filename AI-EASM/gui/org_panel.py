# -*- coding: utf-8 -*-
import os, tkinter as tk
from tkinter import ttk, messagebox
from config.settings import COLORS
from gui.widgets import ScrolledTreeview
from gui.dialogs import OrgDialog

class OrgPanel:
    def __init__(self, parent, app):
        self.app = app; self._selected_org_id = None
        self.frame = tk.Frame(parent, bg=COLORS["main_bg"], padx=12, pady=12)
        self._create_ui(); self.refresh()
    def _create_ui(self):
        c = COLORS
        bar = tk.Frame(self.frame, bg=c["main_bg"])
        bar.pack(fill=tk.X, pady=(0,8))
        ttk.Button(bar, text="+ 新增组织", command=self.add_org, style="Primary.TButton").pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="编辑", command=self.edit_org).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="删除", command=self.delete_org, style="Danger.TButton").pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="刷新", command=self.refresh).pack(side=tk.RIGHT, padx=3)
        # Main area
        main = tk.Frame(self.frame, bg=c["main_bg"])
        main.pack(fill=tk.BOTH, expand=True)
        # Left list
        left = tk.Frame(main, bg=c["card_bg"], highlightbackground=c["card_border"], highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree = ScrolledTreeview(left, columns=("name","type","domain","network","level","status"),
            headings=["组织名称","类型","域名","IP网段","安全等级","状态"], height=18)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.tree.bind("<<TreeviewSelect>>", self._on_select)
        # Right detail
        right = tk.Frame(main, bg=c["card_bg"], highlightbackground=c["card_border"], highlightthickness=1, width=280)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8,0)); right.pack_propagate(False)
        tk.Label(right, text="组织详情", font=("Microsoft YaHei",12,"bold"),
            bg=c["card_bg"], fg=c["text_primary"]).pack(anchor="w", padx=12, pady=(12,8))
        self.detail_text = tk.Text(right, width=28, bg=c["main_bg"], fg=c["text_primary"],
            font=("Microsoft YaHei",10), state=tk.DISABLED, wrap=tk.WORD, bd=0, padx=10, pady=8)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))
    def refresh(self):
        self.tree.clear()
        for org in self.app.org_mgr.list_orgs():
            self.tree.insert((org["org_name"],org["org_type"],dict(org).get("domain_name",""),
                dict(org).get("network_ranges",""),dict(org).get("security_level",""),org["status"]))
    def _on_select(self, event):
        sel = self.tree.tree.selection()
        if not sel: return
        vs = self.tree.tree.item(sel[0],"values")
        if vs:
            for org in self.app.org_mgr.list_orgs():
                if org["org_name"]==vs[0]:
                    self._selected_org_id = org["org_id"]
                    self.detail_text.configure(state=tk.NORMAL)
                    self.detail_text.delete("1.0",tk.END)
                    lines = [
                        "名称: "+str(org["org_name"]),
                        "类型: "+str(org["org_type"]),
                        "域名: "+str(dict(org).get("domain_name","")),
                        "IP网段: "+str(dict(org).get("network_ranges","")),
                        "联系人: "+str(dict(org).get("contact_person","")),
                        "电话: "+str(dict(org).get("contact_phone","")),
                        "安全等级: "+str(dict(org).get("security_level","")),
                        "备注: "+str(dict(org).get("notes","")),
                    ]
                    clues = self.app.org_mgr.list_clues(org["org_id"])
                    if clues:
                        lines.append("")
                        lines.append("— 线索 —")
                        for c in clues:
                            lines.append(f"{c['clue_type']}: {c['clue_value']}")
                    txt = os.linesep.join(lines)
                    self.detail_text.insert("1.0",txt)
                    self.detail_text.configure(state=tk.DISABLED)
                    break
    def add_org(self):
        dlg = OrgDialog(self.frame,"新增组织")
        if dlg.result:
            clues = dlg.result.pop("clues", [])
            org_id = self.app.org_mgr.add_org(**dlg.result)
            self.app.org_mgr.save_clues(org_id, clues)
            self.refresh()
    def edit_org(self):
        if not self._selected_org_id: return
        org = self.app.org_mgr.get_org(self._selected_org_id)
        if org:
            clues = [{"type": c["clue_type"], "value": c["clue_value"]}
                     for c in self.app.org_mgr.list_clues(self._selected_org_id)]
            dlg = OrgDialog(self.frame,"编辑组织",data=dict(org),clues=clues)
            if dlg.result:
                clues = dlg.result.pop("clues", [])
                self.app.org_mgr.update_org(self._selected_org_id,**dlg.result)
                self.app.org_mgr.save_clues(self._selected_org_id, clues)
                self.refresh()
    def delete_org(self):
        if not self._selected_org_id: return
        if messagebox.askyesno("确认","确定删除该组织及其所有数据?"):
            self.app.org_mgr.delete_org(self._selected_org_id); self._selected_org_id=None; self.refresh()
    def get_selected_org_id(self): return self._selected_org_id