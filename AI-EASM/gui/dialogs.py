# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
from config.settings import COLORS, ORG_TYPES, SECURITY_LEVELS, ORG_CLUE_TYPES

class OrgDialog(tk.Toplevel):
    def __init__(self, parent, title, data=None, clues=None):
        super().__init__(parent); self.title(title); self.result = None
        self.geometry("620x680"); self.configure(bg=COLORS["main_bg"])
        self.resizable(False, True); self.transient(parent); self.grab_set()
        self._clue_rows = []
        outer = tk.Frame(self, bg=COLORS["main_bg"])
        outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # 固定字段
        fields = [("org_name","组织名称 *",""),("org_type","组织类型","企业"),("domain_name","域名",""),
                  ("network_ranges","IP网段",""),("contact_person","联系人",""),("contact_phone","联系电话",""),
                  ("security_level","安全等级","S2A2G2"),("notes","备注","")]
        self.vars = {}
        frm = tk.Frame(outer, bg=COLORS["main_bg"]); frm.pack(fill=tk.X)
        for i,(key,label,default) in enumerate(fields):
            tk.Label(frm, text=label, width=12, anchor="w",
                     bg=COLORS["main_bg"], fg=COLORS["text_primary"]).grid(row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=data.get(key,default) if data else default)
            if key=="org_type": ttk.Combobox(frm, textvariable=var, values=ORG_TYPES, width=38).grid(row=i, column=1, sticky="ew", padx=5, pady=3)
            elif key=="security_level": ttk.Combobox(frm, textvariable=var, values=SECURITY_LEVELS, width=38).grid(row=i, column=1, sticky="ew", padx=5, pady=3)
            else: ttk.Entry(frm, textvariable=var, width=42).grid(row=i, column=1, sticky="ew", padx=5, pady=3)
            self.vars[key] = var
        frm.grid_columnconfigure(1, weight=1)

        # 线索标题
        tk.Label(outer, text="线索（可选，用于更精准的暴露面搜索）",
                 bg=COLORS["main_bg"], fg=COLORS["text_secondary"], anchor="w").pack(fill=tk.X, pady=(10,4))

        # 可滚动线索区域
        cv = tk.Canvas(outer, bg=COLORS["main_bg"], highlightthickness=0, height=160)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self._clue_container = tk.Frame(cv, bg=COLORS["main_bg"])
        self._clue_window = cv.create_window((0,0), window=self._clue_container, anchor="nw")
        self._clue_container.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(self._clue_window, width=e.width))

        # 添加线索按钮
        ttk.Button(outer, text="+ 添加线索", command=lambda: self._add_clue_row()).pack(anchor="w", pady=4)

        # 保存/取消
        bf = tk.Frame(outer, bg=COLORS["main_bg"]); bf.pack(fill=tk.X, pady=(10,0))
        ttk.Button(bf, text=" 保存 ", command=self._ok, style="Primary.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text=" 取消 ", command=self.destroy).pack(side=tk.LEFT, padx=5)

        # 回填已有线索
        for c in (clues or []):
            self._add_clue_row(c.get("type",""), c.get("value",""))
        if not self._clue_rows:
            self._add_clue_row()
        self.wait_window()

    def _add_clue_row(self, type_val="", value_val=""):
        row = tk.Frame(self._clue_container, bg=COLORS["main_bg"])
        row.pack(fill=tk.X, pady=2)
        tvar = tk.StringVar(value=type_val)
        vvar = tk.StringVar(value=value_val)
        ttk.Combobox(row, textvariable=tvar, values=ORG_CLUE_TYPES, width=20).pack(side=tk.LEFT, padx=(0,5))
        ttk.Entry(row, textvariable=vvar, width=36).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="✕", width=3, command=lambda r=row: self._del_clue_row(r)).pack(side=tk.LEFT, padx=(5,0))
        self._clue_rows.append({"type_var": tvar, "value_var": vvar, "frame": row})

    def _del_clue_row(self, row):
        for r in self._clue_rows:
            if r["frame"] is row:
                row.destroy(); self._clue_rows.remove(r); break
        if not self._clue_rows:
            self._add_clue_row()

    def _ok(self):
        if not self.vars["org_name"].get().strip():
            messagebox.showerror("错误","组织名称不能为空"); return
        clues = []
        for r in self._clue_rows:
            t = r["type_var"].get().strip(); v = r["value_var"].get().strip()
            if t or v: clues.append({"type": t, "value": v})
        self.result = {k: var.get() for k,var in self.vars.items()}
        self.result["clues"] = clues
        self.destroy()


_SITE_CN = {"aiqicha": "爱企查", "tianyancha": "天眼查", "gsxt": "国家企业信用信息公示系统"}


class BrowserLoginDialog(tk.Toplevel):
    """人在环登录兜底弹窗 — 非阻塞，引导用户在应用内嵌浏览器完成登录/验证。"""

    def __init__(self, parent, source, url, login_manager, on_done=None):
        super().__init__(parent)
        self.title("人工登录/验证")
        self.geometry("560x220")
        self.configure(bg=COLORS["main_bg"])
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self._parent = parent
        self.source = source
        self.url = url
        self.login_manager = login_manager
        self.on_done = on_done
        self.result = None
        self._finished = False

        site_cn = _SITE_CN.get(source, source)
        box = tk.Frame(self, bg=COLORS["main_bg"])
        box.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)
        tk.Label(box, text=f"系统将打开【{site_cn}】，需要您登录账号（或输入验证码、拖动图片滑块验证）。",
                 bg=COLORS["main_bg"], fg=COLORS["text_primary"],
                 font=("Microsoft YaHei", 10), justify="left", wraplength=520).pack(anchor="w", pady=(0, 4))
        tk.Label(box, text="请在浏览器中完成操作后，点击下方【我已登录，继续】按钮。",
                 bg=COLORS["main_bg"], fg=COLORS["text_secondary"],
                 font=("Microsoft YaHei", 9), justify="left", wraplength=520).pack(anchor="w")
        self.status_lbl = tk.Label(box, text="正在打开浏览器…", bg=COLORS["main_bg"],
                                   fg=COLORS["primary"], font=("Microsoft YaHei", 9))
        self.status_lbl.pack(anchor="w", pady=(10, 4))

        bf = tk.Frame(box, bg=COLORS["main_bg"]); bf.pack(fill=tk.X, pady=(10, 0))
        self.ok_btn = ttk.Button(bf, text=" 我已登录，继续 ", command=self._ok)
        self.ok_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text=" 取消 ", command=self._cancel).pack(side=tk.LEFT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(50, self._start_browser)

    def _start_browser(self):
        if self._finished:
            return
        if not self.login_manager.available:
            self.status_lbl.configure(
                text="未安装 Playwright / cryptography，无法自动登录。请手动复制 Cookie 粘贴到「系统设置」。")
            self.ok_btn.configure(state=tk.DISABLED)
            return
        self.login_manager.start_login(self.source, self.url)
        self._poll_open()

    def _poll_open(self):
        if self._finished:
            return
        if self.login_manager.open_event.is_set():
            self.status_lbl.configure(text="浏览器已打开，请完成登录/验证后点击下方按钮。")
        elif self.login_manager.error:
            self.status_lbl.configure(text=f"浏览器启动失败：{self.login_manager.error}")
        else:
            self.after(300, self._poll_open)

    def _ok(self):
        if self._finished:
            return
        self._finished = True
        self.status_lbl.configure(text="正在捕获登录态…")
        self.login_manager.signal_capture()
        self._poll_done()

    def _poll_done(self):
        if self.login_manager.done_event.is_set():
            self.result = {"ok": self.login_manager.capture_ok, "error": self.login_manager.error}
            if self.on_done:
                self.on_done(self.result)
            self.destroy()
        else:
            self.after(300, self._poll_done)

    def _cancel(self):
        if self._finished:
            return
        self._finished = True
        self.login_manager.cancel()
        self.result = {"ok": False}
        if self.on_done:
            self.on_done(self.result)
        self.destroy()