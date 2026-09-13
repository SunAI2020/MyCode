# -*- coding: utf-8 -*-
"""系统设置 — API Key管理 + 缓存 + DB维护 + 关于"""
import tkinter as tk; from tkinter import ttk, messagebox
from config.settings import DARK_THEME as DT, APP_NAME, APP_VERSION, COMPANY_NAME, COPYRIGHT, API_KEYS, LLM_PROVIDERS, LLM_CONFIG

class SettingsPanel:
    def __init__(self,parent,app):
        self.app=app; self.frame=tk.Frame(parent,bg=DT["bg_primary"],padx=12,pady=12)
        self._create_ui()

    def _create_ui(self):
        c=DT
        tk.Label(self.frame,text="系统设置",font=("Microsoft YaHei",16,"bold"),
            bg=c["bg_primary"],fg=c["text_primary"]).pack(anchor="w",pady=(0,10))

        # About
        ab=tk.Frame(self.frame,bg=c["bg_card"],padx=15,pady=15); ab.pack(fill=tk.X,pady=(0,8))
        tk.Label(ab,text=f"{APP_NAME} v{APP_VERSION}",font=("Microsoft YaHei",18,"bold"),
            bg=c["bg_card"],fg=c["accent_primary"]).pack(anchor="w")
        tk.Label(ab,text=f"{COPYRIGHT}",font=("Microsoft YaHei",9),
            bg=c["bg_card"],fg=c["text_secondary"]).pack(anchor="w")
        tk.Label(ab,text="AI全网搜索 | 4级股权穿透 | 12类标识符 | 7因子置信度 | 1小时快速评估",
            bg=c["bg_card"],fg=c["text_primary"]).pack(anchor="w",pady=2)
        tk.Label(ab,text="crt.sh + DNS + WHOIS + ICP + Shodan + GitHub + BGPView + 国家企业信用信息公示系统/爱企查/天眼查/企查查/启信宝",
            bg=c["bg_card"],fg=c["text_secondary"]).pack(anchor="w",pady=1)

        # API Keys
        ap=tk.Frame(self.frame,bg=c["bg_card"],padx=15,pady=12); ap.pack(fill=tk.X,pady=(0,8))
        tk.Label(ap,text="API Key 配置",font=("Microsoft YaHei",12,"bold"),
            bg=c["bg_card"],fg=c["text_primary"]).pack(anchor="w",pady=(0,8))
        self._api_entries={}
        for key,label in [("shodan","Shodan"),("securitytrails","SecurityTrails"),
            ("github","GitHub"),("whoisxmlapi","WhoisXMLAPI"),("hunter","Hunter.io"),
            ("fofa","FOFA"),("quake","QUAKE(360)"),("qianxin_hunter","鹰图Hunter"),
            ("censys_id","Censys ID"),("censys_secret","Censys Secret"),
            ("zoomeye","ZoomEye"),("gitee","Gitee"),("gitlab","GitLab"),
            ("tianyancha_token","天眼查Token"),("aiqicha_cookie","爱企查Cookie")]:
            row=tk.Frame(ap,bg=c["bg_card"]); row.pack(fill=tk.X,pady=2)
            tk.Label(row,text=f"{label}:",bg=c["bg_card"],fg=c["text_primary"],
                width=14,anchor="w").pack(side=tk.LEFT)
            var=tk.StringVar(value=API_KEYS.get(key,""))
            ttk.Entry(row,textvariable=var,width=40,show="*").pack(side=tk.LEFT,padx=4)
            ttk.Button(row,text="测试",command=lambda k=key: self._test(k)).pack(side=tk.LEFT,padx=2)
            if key == "aiqicha_cookie":
                ttk.Button(row,text="引导登录",command=self._browser_login_aiqicha).pack(side=tk.LEFT,padx=2)
            self._api_entries[key]=var
        ttk.Button(ap,text="保存全部API Key",command=self._save).pack(pady=(8,0))

        # LLM 大模型
        lm=tk.Frame(self.frame,bg=c["bg_card"],padx=15,pady=12); lm.pack(fill=tk.X,pady=(0,8))
        tk.Label(lm,text="AI 大模型",font=("Microsoft YaHei",12,"bold"),
            bg=c["bg_card"],fg=c["text_primary"]).pack(anchor="w",pady=(0,8))
        r0=tk.Frame(lm,bg=c["bg_card"]); r0.pack(fill=tk.X,pady=2)
        tk.Label(r0,text="服务商:",bg=c["bg_card"],fg=c["text_primary"],width=14,anchor="w").pack(side=tk.LEFT)
        self._llm_provider_var=tk.StringVar(value=LLM_CONFIG.get("provider","custom"))
        self._llm_provider_cb=ttk.Combobox(r0,textvariable=self._llm_provider_var,width=30,state="readonly",
            values=[f"{k} ({v['name']})" for k,v in LLM_PROVIDERS.items()])
        self._llm_provider_cb.pack(side=tk.LEFT,padx=4)
        self._llm_base_var=tk.StringVar(value=LLM_CONFIG.get("base_url",""))
        self._llm_model_var=tk.StringVar(value=LLM_CONFIG.get("model",""))
        self._llm_key_var=tk.StringVar(value=LLM_CONFIG.get("api_key",""))
        self._llm_temp_var=tk.StringVar(value=str(LLM_CONFIG.get("temperature",0.3)))
        for label,var,show in [("Base URL",self._llm_base_var,False),("模型",self._llm_model_var,False),
            ("API Key",self._llm_key_var,True),("温度",self._llm_temp_var,False)]:
            rr=tk.Frame(lm,bg=c["bg_card"]); rr.pack(fill=tk.X,pady=2)
            tk.Label(rr,text=f"{label}:",bg=c["bg_card"],fg=c["text_primary"],width=14,anchor="w").pack(side=tk.LEFT)
            ttk.Entry(rr,textvariable=var,width=40,show=("*" if show else "")).pack(side=tk.LEFT,padx=4)
        lf=tk.Frame(lm,bg=c["bg_card"]); lf.pack(fill=tk.X,pady=(8,0))
        ttk.Button(lf,text="测试连接",command=self._test_llm).pack(side=tk.LEFT,padx=3)
        ttk.Button(lf,text="保存大模型配置",command=self._save_llm).pack(side=tk.LEFT,padx=6)

        # Cache
        cc=tk.Frame(self.frame,bg=c["bg_card"],padx=15,pady=12); cc.pack(fill=tk.X,pady=(0,8))
        tk.Label(cc,text="缓存管理",font=("Microsoft YaHei",12,"bold"),
            bg=c["bg_card"],fg=c["text_primary"]).pack(anchor="w",pady=(0,8))
        ttk.Button(cc,text="清除过期缓存",command=self._clear_exp).pack(side=tk.LEFT,padx=3)
        ttk.Button(cc,text="清除全部缓存",command=self._clear_all).pack(side=tk.LEFT,padx=3)
        self.cache_lbl=tk.Label(cc,text="",bg=c["bg_card"],fg=c["text_secondary"])
        self.cache_lbl.pack(anchor="w",pady=(6,0)); self._up_cache()

        # DB
        db=tk.Frame(self.frame,bg=c["bg_card"],padx=15,pady=12); db.pack(fill=tk.X)
        tk.Label(db,text="数据库维护",font=("Microsoft YaHei",12,"bold"),
            bg=c["bg_card"],fg=c["text_primary"]).pack(anchor="w",pady=(0,8))
        self.db_lbl=tk.Label(db,text="",bg=c["bg_card"],fg=c["text_secondary"])
        self.db_lbl.pack(anchor="w",pady=(0,6)); self._up_db()
        ttk.Button(db,text="清理30天前数据",command=self._clean).pack(side=tk.LEFT,padx=3)
        ttk.Button(db,text="VACUUM优化",command=self._vacuum).pack(side=tk.LEFT,padx=10)

        tk.Label(self.frame,text=f"{APP_NAME} v{APP_VERSION} | {COPYRIGHT}",
            bg=c["bg_primary"],fg=c["text_muted"],font=("Microsoft YaHei",8)).pack(pady=(15,0))

    def _save(self):
        for k,v in self._api_entries.items():
            val=v.get().strip(); API_KEYS[k]=val
            self.app.org_mgr.set_setting(f"api_key:{k}",val)
        messagebox.showinfo("完成","API Keys已保存")

    def _persist_llm(self):
        provider=self._llm_provider_var.get().split(" ")[0]
        base=self._llm_base_var.get().strip()
        model=self._llm_model_var.get().strip()
        key=self._llm_key_var.get().strip()
        temp=self._llm_temp_var.get().strip()
        for k,v in [("provider",provider),("base_url",base),("model",model),("api_key",key),("temperature",temp)]:
            self.app.org_mgr.set_setting(f"llm:{k}",v)
        LLM_CONFIG.update({"provider":provider,"base_url":base,"model":model,"api_key":key})
        try: LLM_CONFIG["temperature"]=float(temp)
        except: pass

    def _save_llm(self):
        self._persist_llm()
        messagebox.showinfo("完成","大模型配置已保存")

    def _test_llm(self):
        self._persist_llm()
        from core.llm_client import LLMClient
        c=LLMClient(org_manager=self.app.org_mgr)
        if not c.available():
            return messagebox.showwarning("提示","缺少 Base URL 或模型名，无法测试")
        out=c.complete("请用一句话回复：连接成功",max_tokens=50)
        if out:
            messagebox.showinfo("测试成功",f"模型回复: {out[:120]}")
        else:
            messagebox.showerror("测试失败","无响应，请检查 Base URL / API Key / 模型名")

    def _test(self,key):
        val=self._api_entries[key].get().strip()
        if not val: return messagebox.showwarning("提示","请先输入API Key")
        try:
            import requests
            urls={"github":"https://api.github.com","shodan":"https://api.shodan.io/api-info"}
            if key in urls:
                r=requests.get(urls[key]+("" if key=="github" else f"?key={val}"),
                    headers={"Authorization":f"token {val}"} if key=="github" else {},timeout=5)
                messagebox.showinfo("结果",f"{key}: HTTP {r.status_code}")
            else: messagebox.showinfo("结果",f"{key}: Key已保存")
        except Exception as e: messagebox.showerror("失败",str(e))

    def _browser_login_aiqicha(self):
        from gui.dialogs import BrowserLoginDialog
        from config.settings import LOGIN_URLS
        BrowserLoginDialog(self.frame, "aiqicha", LOGIN_URLS["aiqicha"], self.app.browser_login,
            on_done=self._on_login_done)

    def _on_login_done(self, result):
        if result.get("ok"):
            cookie = self.app.org_mgr.get_browser_cookie("aiqicha")
            self._api_entries["aiqicha_cookie"].set(cookie)
            messagebox.showinfo("完成", "登录态已捕获并加密保存（已回填到爱企查 Cookie 输入框）")
        else:
            messagebox.showinfo("提示", "已取消登录")

    def _clear_exp(self): self.app.cache_mgr.clear_expired(); self._up_cache(); messagebox.showinfo("完成","过期缓存已清除")
    def _clear_all(self):
        if messagebox.askyesno("确认","清除全部API缓存?"):
            self.app.cache_mgr.clear_all(); self._up_cache(); messagebox.showinfo("完成","已清除")

    def _up_cache(self):
        try:
            with self.app.cache_mgr._connect() as conn:
                t=conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                e=conn.execute("SELECT COUNT(*) FROM cache WHERE expires_at<=datetime('now','localtime')").fetchone()[0]
            self.cache_lbl.configure(text=f"缓存:{t}条 (过期:{e}条)")
        except: self.cache_lbl.configure(text="缓存: --")

    def _up_db(self):
        try:
            with self.app.org_mgr._connect() as conn:
                o=conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0]
                e=conn.execute("SELECT COUNT(*) FROM exposures").fetchone()[0]
                t=conn.execute("SELECT COUNT(*) FROM scan_tasks").fetchone()[0]
            self.db_lbl.configure(text=f"组织:{o} 资产:{e} 任务:{t}")
        except: self.db_lbl.configure(text="DB: --")

    def _clean(self):
        if messagebox.askyesno("确认","删除30天前的扫描任务?"):
            with self.app.org_mgr._connect() as conn:
                conn.execute("DELETE FROM scan_tasks WHERE created_at<datetime('now','-30 days')")
                conn.commit()
            self._up_db(); messagebox.showinfo("完成","已清理")

    def _vacuum(self):
        with self.app.org_mgr._connect() as conn: conn.execute("VACUUM")
        self._up_db(); messagebox.showinfo("完成","数据库已优化(VACUUM)")
