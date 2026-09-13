# -*- coding: utf-8 -*-
"""AI资产发现面板 — 3Tab: AI搜索/快速评估/股权穿透"""
import os
import tkinter as tk, threading
from tkinter import ttk, messagebox
from config.settings import DARK_THEME as DT, LOGIN_URLS, BROWSER_LOGIN_TIMEOUT
from gui.widgets import ScrolledTreeview, LogPanel

RISK_CN = {"CRITICAL":"危险","HIGH":"高","MEDIUM":"中","LOW":"低","INFO":"信息"}

class ScanPanel:
    def __init__(self, parent, app):
        self.app = app
        self._org_map = {}
        self._last_report_path = None
        self.frame = tk.Frame(parent, bg=DT["bg_primary"], padx=12, pady=12)
        self._create_ui()

    def _create_ui(self):
        c = DT
        tk.Label(self.frame, text="AI资产发现", font=("Microsoft YaHei",16,"bold"),
            bg=c["bg_primary"], fg=c["text_primary"]).pack(anchor="w", pady=(0,10))

        # Stat cards
        sc = tk.Frame(self.frame, bg=c["bg_primary"]); sc.pack(fill=tk.X, pady=(0,8))
        self._stat_vars = {}
        for k, lbl in [("subsidiaries","子公司"),("assets","发现资产"),("exposures","暴露面"),("leaks","泄露")]:
            f = tk.Frame(sc, bg=c["bg_card"], padx=12, pady=8)
            f.pack(side=tk.LEFT, padx=(0,6), expand=True, fill=tk.X)
            sv = tk.StringVar(value="0")
            tk.Label(f, textvariable=sv, font=("Microsoft YaHei",24,"bold"),
                bg=c["bg_card"], fg=c["accent_primary"]).pack()
            tk.Label(f, text=lbl, font=("Microsoft YaHei",8),
                bg=c["bg_card"], fg=c["text_secondary"]).pack()
            self._stat_vars[k] = sv

        # 3-Tab notebook
        self.tab = ttk.Notebook(self.frame)
        self.tab.pack(fill=tk.BOTH, expand=True)
        self._create_ai_tab(c)
        self._create_rapid_tab(c)
        self._create_equity_tab(c)
        self._refresh_orgs()

    def _create_ai_tab(self, c):
        tab = tk.Frame(self.tab, bg=c["bg_primary"]); self.tab.add(tab, text="AI资产发现")
        cfg = tk.Frame(tab, bg=c["bg_card"], padx=12, pady=10); cfg.pack(fill=tk.X, pady=(5,6))
        r1 = tk.Frame(cfg, bg=c["bg_card"]); r1.pack(fill=tk.X)
        tk.Label(r1, text="目标组织:", bg=c["bg_card"], fg=c["text_primary"]).pack(side=tk.LEFT)
        self.org_var = tk.StringVar()
        self.org_cb = ttk.Combobox(r1, textvariable=self.org_var, width=25, state="readonly")
        self.org_cb.pack(side=tk.LEFT, padx=5)
        self.org_cb.bind("<<ComboboxSelected>>", self._on_org_selected)
        ttk.Button(r1, text="刷新", command=self._refresh_orgs).pack(side=tk.LEFT, padx=3)
        tk.Label(r1, text="  域名:", bg=c["bg_card"], fg=c["text_primary"]).pack(side=tk.LEFT, padx=(10,0))
        self.domain_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.domain_var, width=20).pack(side=tk.LEFT, padx=5)
        r2 = tk.Frame(cfg, bg=c["bg_card"]); r2.pack(fill=tk.X, pady=(8,5))
        self.ai_btn = ttk.Button(r2, text=" AI全网搜索 ", command=self._start_ai_search)
        self.ai_btn.pack(side=tk.LEFT, padx=3)
        self.dork_btn = ttk.Button(r2, text=" 暴露面检索 ", command=self._start_dork_sweep)
        self.dork_btn.pack(side=tk.LEFT, padx=3)
        self.port_btn = ttk.Button(r2, text=" 端口扫描 ", command=self._start_port_scan)
        self.port_btn.pack(side=tk.LEFT, padx=3)
        self.stop_btn = ttk.Button(r2, text=" 停止 ", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        self.multi_name_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r2, text="多名称搜索(含简称/曾用名)", variable=self.multi_name_var).pack(side=tk.LEFT, padx=15)
        self.progress = ttk.Progressbar(cfg, length=400, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(5,2))
        self.prog_label = tk.StringVar(value="就绪")
        tk.Label(cfg, textvariable=self.prog_label, bg=c["bg_card"], fg=c["text_secondary"],
            font=("Microsoft YaHei",8)).pack(anchor="w")
        r3 = tk.Frame(cfg, bg=c["bg_card"]); r3.pack(fill=tk.X, pady=(8,0))
        tk.Label(r3, text="报告格式:", bg=c["bg_card"], fg=c["text_secondary"]).pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value="HTML")
        self.fmt_cb = ttk.Combobox(r3, textvariable=self.fmt_var, width=8, state="readonly",
            values=["HTML","MD","PDF","DOCX"])
        self.fmt_cb.pack(side=tk.LEFT, padx=4)
        self.save_report_btn = ttk.Button(r3, text=" 保存报告 ", command=self._save_report)
        self.save_report_btn.pack(side=tk.LEFT, padx=3)
        self.view_report_btn = ttk.Button(r3, text=" 查看报告 ", command=self._view_report)
        self.view_report_btn.pack(side=tk.LEFT, padx=3)
        rf = tk.Frame(tab, bg=c["bg_card"]); rf.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        self.result_tree = ScrolledTreeview(rf, columns=("type","name","value","source","risk","conf"),
            headings=["资产类型","资产名称","资产值","来源","风险等级","可信度"], height=10)
        self.result_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.result_tree.tree.bind("<Button-3>", self._on_tree_right_click)
        lf = tk.Frame(tab, bg=c["bg_card"]); lf.pack(fill=tk.X)
        self.log_panel = LogPanel(lf, height=6)
        self.log_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_rapid_tab(self, c):
        tab = tk.Frame(self.tab, bg=c["bg_primary"]); self.tab.add(tab, text="快速评估")
        cfg = tk.Frame(tab, bg=c["bg_card"], padx=12, pady=10); cfg.pack(fill=tk.X, pady=(5,6))
        r1 = tk.Frame(cfg, bg=c["bg_card"]); r1.pack(fill=tk.X)
        tk.Label(r1, text="企业名称:", bg=c["bg_card"], fg=c["text_primary"]).pack(side=tk.LEFT)
        self.rapid_name_var = tk.StringVar()
        self.rapid_cb = ttk.Combobox(r1, textvariable=self.rapid_name_var, width=28)
        self.rapid_cb.pack(side=tk.LEFT, padx=5)
        self.rapid_btn = ttk.Button(r1, text=" 1小时快速评估 ", command=self._start_rapid)
        self.rapid_btn.pack(side=tk.LEFT, padx=5)
        self.rapid_stop_btn = ttk.Button(r1, text="停止", command=self._stop_rapid, state=tk.DISABLED)
        self.rapid_stop_btn.pack(side=tk.LEFT)
        self.phase_progress = ttk.Progressbar(cfg, length=400, mode="determinate")
        self.phase_progress.pack(fill=tk.X, pady=(8,2))
        self.phase_label = tk.StringVar(value="等待开始")
        tk.Label(cfg, textvariable=self.phase_label, bg=c["bg_card"], fg=c["text_secondary"],
            font=("Microsoft YaHei",8)).pack(anchor="w")
        sf = tk.Frame(tab, bg=c["bg_card"], padx=10, pady=8); sf.pack(fill=tk.X, pady=(0,5))
        self._rapid_sv = {}
        for k, lbl in [("s","子公司:0"),("a","资产:0"),("l","泄露:0")]:
            sv = tk.StringVar(value=lbl)
            tk.Label(sf, textvariable=sv, bg=c["bg_card"], fg=c["text_secondary"],
                font=("Microsoft YaHei",9)).pack(side=tk.LEFT, padx=(0,20))
            self._rapid_sv[k] = sv
        lf = tk.Frame(tab, bg=c["bg_card"]); lf.pack(fill=tk.BOTH, expand=True)
        self.rapid_log = LogPanel(lf, height=15)
        self.rapid_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_equity_tab(self, c):
        tab = tk.Frame(self.tab, bg=c["bg_primary"]); self.tab.add(tab, text="股权穿透")
        cfg = tk.Frame(tab, bg=c["bg_card"], padx=12, pady=10); cfg.pack(fill=tk.X, pady=(5,6))
        r1 = tk.Frame(cfg, bg=c["bg_card"]); r1.pack(fill=tk.X)
        tk.Label(r1, text="企业名称:", bg=c["bg_card"], fg=c["text_primary"]).pack(side=tk.LEFT)
        self.equity_name_var = tk.StringVar()
        self.equity_cb = ttk.Combobox(r1, textvariable=self.equity_name_var, width=28)
        self.equity_cb.pack(side=tk.LEFT, padx=5)
        self.equity_btn = ttk.Button(r1, text=" 股权穿透 ", command=self._start_equity)
        self.equity_btn.pack(side=tk.LEFT, padx=5)
        self.divergent_btn = ttk.Button(r1, text=" 12类标识符发散搜索 ", command=self._start_divergent)
        self.divergent_btn.pack(side=tk.LEFT, padx=3)
        self.equity_stop_btn = ttk.Button(r1, text=" 停止 ", command=self._stop_equity, state=tk.DISABLED)
        self.equity_stop_btn.pack(side=tk.LEFT, padx=3)
        tf = tk.Frame(tab, bg=c["bg_card"]); tf.pack(fill=tk.BOTH, expand=True, pady=(5,0))
        self.equity_tree = ScrolledTreeview(tf, columns=("name","level","ratio","type","source"),
            headings=["企业名称","层级","股权比例","关系类型","来源"], height=15)
        self.equity_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        lf = tk.Frame(tab, bg=c["bg_card"]); lf.pack(fill=tk.X, pady=(5,0))
        self.equity_log = LogPanel(lf, height=6)
        self.equity_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ===== Actions =====
    def _refresh_orgs(self):
        orgs = self.app.org_mgr.get_org_names()
        self._org_map = {name: oid for oid, name in orgs}
        names = [name for oid, name in orgs]
        self.org_cb["values"] = names
        self.rapid_cb["values"] = names
        self.equity_cb["values"] = names
        if orgs: self.org_var.set(orgs[0][1])

    def _get_org(self):
        name = self.org_var.get()
        if not name: return None, None
        oid = self._org_map.get(name)
        if not oid: return None, None
        return oid, self.app.org_mgr.get_org(oid)

    def _on_org_selected(self, event=None):
        oid, _ = self._get_org()
        if oid:
            self._refresh_stats_ui(oid)

    def _set_running(self, r):
        s = tk.DISABLED if r else tk.NORMAL
        self.ai_btn.configure(state=s); self.dork_btn.configure(state=s); self.port_btn.configure(state=s)
        self.stop_btn.configure(state=tk.NORMAL if r else tk.DISABLED)

    def _start_ai_search(self):
        oid, org = self._get_org()
        if not oid: return messagebox.showerror("错误","请选择组织")
        self._set_running(True); self.result_tree.clear(); self.log_panel.clear()
        self.log_panel.log(f"=== AI全网搜索: {org['org_name']} ===")
        domain = self.domain_var.get() or dict(org).get("domain_name","")
        self.app.ai_engine.set_callbacks(
            log_cb=self.log_panel.log,
            progress_cb=lambda p,s: (self.progress.configure(value=p), self.prog_label.set(s)),
            found_cb=lambda t,n,v,s,r,d: self.result_tree.insert((t,n,v,s,RISK_CN.get(r,r),"—")))
        def run():
            scored = self.app.ai_engine.search(oid, org["org_name"], domain, multi_name=self.multi_name_var.get())
            self._after_search(oid, org["org_name"], scored)
            self.frame.after(0, lambda: self._set_running(False))
        threading.Thread(target=run, daemon=True).start()

    def _start_dork_sweep(self):
        oid, org = self._get_org()
        if not oid: return messagebox.showerror("错误","请选择组织")
        self._set_running(True); self.result_tree.clear(); self.log_panel.clear()
        self.log_panel.log(f"=== 暴露面检索(6维度): {org['org_name']} ===")
        domain = self.domain_var.get() or dict(org).get("domain_name","")
        self.app.ai_engine.set_callbacks(
            log_cb=self.log_panel.log,
            progress_cb=lambda p,s: (self.progress.configure(value=p), self.prog_label.set(s)),
            found_cb=lambda t,n,v,s,r,d: self.result_tree.insert((t,n,v,s,RISK_CN.get(r,r),"—")))
        def run():
            scored = self.app.ai_engine.search(oid, org["org_name"], domain,
                dimensions=["surface_dork","sensitive_dir","mgmt_entry"],
                multi_name=self.multi_name_var.get())
            self._after_search(oid, org["org_name"], scored)
            self.frame.after(0, lambda: self._set_running(False))
        threading.Thread(target=run, daemon=True).start()

    def _fmt_key(self):
        return {"HTML":"html","MD":"md","PDF":"pdf","DOCX":"docx"}.get(self.fmt_var.get(), "html")

    def _after_search(self, oid, org_name, scored):
        try:
            path = self.app.report_mgr.generate_report(oid, fmt="html")
            if path:
                self._last_report_path = path
                self.log_panel.log(f"[报告] 已自动保存(HTML): {path}")
                self.frame.after(0, self.app.refresh_reports)
        except Exception as e:
            self.log_panel.log(f"[报告] 自动保存失败: {e}")
        self.frame.after(0, lambda: self._refresh_results_ui(scored))
        self.frame.after(0, lambda: self._refresh_stats_ui(oid))

    def _refresh_results_ui(self, scored):
        self.result_tree.clear()
        for r in (scored or []):
            conf = r.get("confidence", 0.5)
            rk = r.get("risk_level","INFO")
            self.result_tree.insert((r.get("asset_type",""), r.get("asset_name",""),
                r.get("asset_value",""), r.get("source",""), RISK_CN.get(rk, rk),
                f"{conf:.0%}"))

    def _refresh_stats_ui(self, oid):
        try:
            stats = self.app.org_mgr.get_exposure_stats(org_id=oid)
            leaks = len(self.app.org_mgr.list_leak_evidence(org_id=oid))
            subs = len(self.app.org_mgr.list_subsidiaries(parent_org_id=oid))
            with self.app.org_mgr._connect() as conn:
                assets = conn.execute("SELECT COUNT(DISTINCT asset_value) FROM exposures WHERE org_id=?", (oid,)).fetchone()[0]
            self._stat_vars["subsidiaries"].set(str(subs))
            self._stat_vars["assets"].set(str(assets))
            self._stat_vars["exposures"].set(str(stats.get("total", 0)))
            self._stat_vars["leaks"].set(str(leaks))
        except Exception:
            pass

    def _save_report(self):
        oid, org = self._get_org()
        if not oid: return messagebox.showerror("错误","请选择组织")
        fmt = self._fmt_key()
        try:
            path = self.app.report_mgr.generate_report(oid, fmt=fmt)
            if path:
                self._last_report_path = path
                self.log_panel.log(f"[报告] 已保存({fmt.upper()}): {path}")
                self.app.refresh_reports()
                messagebox.showinfo("完成", f"报告已保存:\n{path}")
            else:
                messagebox.showerror("失败", f"生成 {fmt.upper()} 报告失败（可能缺少依赖，如 PDF 需 reportlab）")
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _view_report(self):
        import webbrowser
        from config.settings import REPORT_DIR
        path = self._last_report_path
        if not path or not os.path.exists(path):
            exts = (".html", ".md", ".pdf", ".docx")
            files = [f for f in os.listdir(REPORT_DIR) if f.lower().endswith(exts)]
            if files:
                files.sort(key=lambda f: os.path.getmtime(os.path.join(REPORT_DIR, f)), reverse=True)
                path = os.path.join(REPORT_DIR, files[0])
            else:
                return messagebox.showwarning("提示", "还没有生成过报告")
        webbrowser.open(path)

    def _on_tree_right_click(self, event):
        tree = self.result_tree.tree
        iid = tree.identify_row(event.y)
        if not iid: return
        tree.selection_set(iid)
        values = tree.item(iid, "values")
        if not values or len(values) < 3: return
        value = values[2]  # 资产值列
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="复制资产值", command=lambda: self._copy_to_clipboard(value))
        if str(value).startswith(("http://", "https://")):
            menu.add_command(label="打开链接", command=lambda: self._open_link(value))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_to_clipboard(self, text):
        self.frame.clipboard_clear()
        self.frame.clipboard_append(str(text))
        self.log_panel.log(f"[复制] {text}")

    def _open_link(self, url):
        import webbrowser
        webbrowser.open(url)

    def _start_port_scan(self):
        oid, org = self._get_org()
        if not oid: return messagebox.showerror("错误","请选择组织")
        target = dict(org).get("network_ranges","") or self.domain_var.get() or dict(org).get("domain_name","")
        if not target: return messagebox.showerror("错误","没有扫描目标")
        self._set_running(True); self.result_tree.clear(); self.log_panel.clear()
        self.log_panel.log(f"=== 端口扫描: {target} ===")
        self.app.scan_mgr.set_callbacks(
            log_cb=self.log_panel.log,
            progress_cb=lambda p,s: (self.progress.configure(value=p), self.prog_label.set(s)),
            result_cb=lambda h,pt,sv,ver,vul: self.result_tree.insert(("端口",f"{h}:{pt}",(f"{sv} {ver}".strip() if ver else sv),"扫描","信息","")))
        self.app.scan_mgr.scan_target(oid, target)
        def check():
            import time
            while self.app.scan_mgr.scan_thread and self.app.scan_mgr.scan_thread.is_alive(): time.sleep(0.5)
            self.frame.after(0, lambda: self._set_running(False))
        threading.Thread(target=check, daemon=True).start()

    def _start_rapid(self):
        name = self.rapid_name_var.get().strip()
        if not name: return messagebox.showerror("错误","请输入企业名称")
        self.rapid_btn.configure(state=tk.DISABLED); self.rapid_stop_btn.configure(state=tk.NORMAL)
        self.rapid_log.clear()
        self.rapid_log.log(f"=== 1小时快速评估: {name} ===")
        self.app.rapid_assessor.set_callbacks(
            log_cb=self.rapid_log.log,
            phase_cb=lambda phase,pct,stats,elapsed: (
                self.phase_progress.configure(value=pct),
                self.phase_label.set(f"{phase} ({elapsed:.0f}s)"),
                self._rapid_sv["s"].set(f"子公司:{stats.get('subsidiaries',0)}"),
                self._rapid_sv["a"].set(f"资产:{stats.get('assets',0)}"),
                self._rapid_sv["l"].set(f"泄露:{stats.get('leaks',0)}")))
        # 复用同名组织，避免每次快速评估都新建重复组织
        oid = None
        for _oid, _name in self.app.org_mgr.get_org_names():
            if _name == name:
                oid = _oid; break
        if not oid:
            oid = self.app.org_mgr.add_org(org_name=name)
        def run():
            self.app.rapid_assessor.run(oid, name)
            self.frame.after(0, lambda: (self.rapid_btn.configure(state=tk.NORMAL),
                self.rapid_stop_btn.configure(state=tk.DISABLED), self._refresh_orgs(),
                self.app.refresh_reports()))
        threading.Thread(target=run, daemon=True).start()

    def _make_login_cb(self):
        """构造 need_login_cb：在 equity_engine 后台线程内被调用，阻塞等待用户完成登录。

        弹窗调度回主线程（frame.after），用 threading.Event 协调"引擎线程等待"与"主线程弹窗"。
        """
        login_evt = threading.Event()
        login_result = {}

        def need_login(source, reason):
            url = LOGIN_URLS.get(source, "")
            def show():
                from gui.dialogs import BrowserLoginDialog
                BrowserLoginDialog(self.frame, source, url, self.app.browser_login,
                    on_done=lambda res: (login_result.update(res or {}), login_evt.set()))
            self.frame.after(0, show)
            login_evt.wait(timeout=BROWSER_LOGIN_TIMEOUT)
            return login_result.get("ok", False)

        return need_login

    def _start_equity(self):
        name = self.equity_name_var.get().strip()
        if not name: return messagebox.showerror("错误","请输入企业名称")
        self.app.org_mgr.log_query("equity", name)
        self.equity_tree.clear(); self.equity_log.clear()
        self.equity_log.log(f"=== 股权穿透: {name} ===")
        self.app.equity_engine.set_callbacks(log_cb=self.equity_log.log,
                                             need_login_cb=self._make_login_cb())
        self.app.equity_engine._reset_stop()
        self._set_equity_running(True)
        def run():
            try:
                subs, rels = self.app.equity_engine.discover_subsidiaries(name)
                self.frame.after(0, lambda: self._finish_equity(subs, rels))
            except Exception as e:
                self.equity_log.log(f"[股权穿透] 失败: {e}", "error")
                self.frame.after(0, lambda: self._set_equity_running(False))
        threading.Thread(target=run, daemon=True).start()

    def _finish_equity(self, subs, rels):
        for s in subs:
            ratio = s.get("equity_ratio")
            ratio_text = "未知" if ratio is None else f"{ratio*100:.0f}%"
            self.equity_tree.insert((s["sub_name"], s["chain_level"],
                ratio_text, "holding", "天眼查/企查查"))
        self.equity_log.log(f"发现 {len(subs)} 个子公司, {len(rels)} 条关系")
        self._set_equity_running(False)

    def _set_equity_running(self, r):
        self.equity_btn.configure(state=tk.DISABLED if r else tk.NORMAL)
        self.divergent_btn.configure(state=tk.DISABLED if r else tk.NORMAL)
        self.equity_stop_btn.configure(state=tk.NORMAL if r else tk.DISABLED)

    def _stop_equity(self):
        self.app.equity_engine.stop()
        self.equity_log.log("[用户] 已请求停止")

    def _start_divergent(self):
        name = self.equity_name_var.get().strip()
        if not name: return messagebox.showerror("错误","请输入企业名称")
        self.app.org_mgr.log_query("divergent", name)
        self.equity_tree.clear(); self.equity_log.clear()
        self.equity_log.log(f"=== 12类标识符发散搜索: {name} ===")
        self.app.equity_engine.set_callbacks(log_cb=self.equity_log.log,
                                             need_login_cb=self._make_login_cb())
        self.app.equity_engine._reset_stop()
        self._set_equity_running(True)
        def run():
            try:
                result = self.app.equity_engine.full_divergent_search(name)
                self.frame.after(0, lambda: self._finish_divergent(result))
            except Exception as e:
                self.equity_log.log(f"[发散搜索] 失败: {e}", "error")
                self.frame.after(0, lambda: self._set_equity_running(False))
        threading.Thread(target=run, daemon=True).start()

    def _finish_divergent(self, result):
        self.equity_log.log(f"完成: {len(result.get('profiles',[]))}档案 "
            f"{len(result.get('subsidiaries',[]))}子公司 "
            f"{len(result.get('relations',[]))}关系")
        for r in result.get("relations",[])[:50]:
            self.equity_tree.insert((r.get("to_entity_name",r.get("company_name","")),
                r.get("chain_level",""),
                "未知" if r.get("equity_ratio") is None else f"{r.get('equity_ratio',0)*100:.0f}%",
                r.get("relation_type",""), r.get("source","")))
        self._set_equity_running(False)

    def _stop(self):
        self.app.ai_engine.stop(); self.app.scan_mgr.stop_scan()
        self._set_running(False); self.log_panel.log("[用户] 已停止")

    def _stop_rapid(self):
        self.app.rapid_assessor.stop()
        self.rapid_btn.configure(state=tk.NORMAL); self.rapid_stop_btn.configure(state=tk.DISABLED)
