# -*- coding: utf-8 -*-
"""股权穿透引擎 — 4级BFS + 12类标识符全量提取 + 更名历史追踪"""
import os, sys, json, threading
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.helpers import generate_id
from config.settings import (MAX_EQUITY_CHAIN_DEPTH, MIN_EQUITY_RATIO,
    MAX_RECURSIVE_SEARCH_DEPTH, GOVERNMENT_KEYWORDS, ENTERPRISE_INFO_SOURCES,
    API_KEYS, API_ENDPOINTS)
try:
    import requests; HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
try:
    from bs4 import BeautifulSoup; HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

class EquityChainEngine:
    """4级股权穿透BFS + 12类标识符提取 + 更名历史 + 全维度发散搜索"""

    def __init__(self, org_manager=None, enrichment_engine=None, rate_limiter=None):
        self.org_mgr = org_manager
        self.enrichment = enrichment_engine
        self.rate_limiter = rate_limiter
        self._log_cb = None
        self._need_login_cb = None
        self._session = None
        self._stop_event = threading.Event()

    def set_callbacks(self, log_cb=None, need_login_cb=None):
        self._log_cb = log_cb
        self._need_login_cb = need_login_cb

    def _log(self, msg):
        if self._log_cb: self._log_cb(msg)

    def stop(self):
        self._stop_event.set()

    def _reset_stop(self):
        self._stop_event.clear()

    # ===== 人在环登录兜底 =====
    def _session_http(self):
        if self._session is None and HAS_REQUESTS:
            self._session = requests.Session()
        return self._session

    def _wait_limit(self, api_name):
        if self.rate_limiter:
            self.rate_limiter.wait_and_acquire(api_name, timeout=15)

    def _request_login(self, source, reason):
        """触发人在环登录兜底。need_login_cb(source, reason) -> bool。"""
        if not self._need_login_cb:
            return False
        try:
            return bool(self._need_login_cb(source, reason))
        except Exception:
            return False

    @staticmethod
    def _is_login_redirect(r):
        """爱企查登录态失效信号：重定向登录页或返回 HTML 登录页。"""
        try:
            if "login" in (r.url or "") or "passport" in (r.url or ""):
                return True
            ctype = (r.headers or {}).get("Content-Type", "")
            if "text/html" in ctype:
                body = (r.text or "")[:500]
                if "登录" in body or "passport" in body:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _is_aiqicha_nologin(data):
        """爱企查 AJAX 未登录信号：HTTP 200 但 JSON 里 userType == 'nologin'。"""
        try:
            if not isinstance(data, dict):
                return False
            lf = (data.get("data") or {}).get("limitForward", {}) or {}
            return str(lf.get("userType", "")) == "nologin"
        except Exception:
            return False

    def is_government_entity(self, name):
        return any(kw in (name or "") for kw in GOVERNMENT_KEYWORDS)

    # ===== 主入口: 企业全维度档案提取 =====
    def extract_enterprise_profile(self, company_name):
        """从多数据源提取企业12类标识符"""
        profile = {
            "full_name":company_name,"short_name":"","former_names":[],
            "english_name":"","legal_person":"","shareholders":[],
            "beneficial_owners":[],"actual_controllers":[],"key_executives":[],
            "emails":[],"phones":[],"mobile_numbers":[],
            "registered_address":"","business_scope":"",
            "registered_capital":"","established_date":"","credit_code":"",
            "source":"auto","name_changes":[],
        }
        for source in ENTERPRISE_INFO_SOURCES:
            fetcher = getattr(self, f"_fetch_from_{source}", None)
            if not fetcher: continue
            try:
                data = fetcher(company_name)
                if data: self._merge_profile(profile, data, source)
            except Exception as e:
                self._log(f"  [{source}] 查询异常: {e}")
        if self.is_government_entity(company_name):
            nc = self.track_name_history(company_name)
            if nc: profile["name_changes"] = nc
        return profile

    def _merge_profile(self, profile, new_data, source):
        str_fields = ["short_name","english_name","legal_person","registered_address",
            "business_scope","registered_capital","established_date","credit_code"]
        for f in str_fields:
            if new_data.get(f) and not profile.get(f): profile[f] = new_data[f]
        list_fields = ["former_names","shareholders","beneficial_owners",
            "actual_controllers","key_executives","emails","phones","mobile_numbers"]
        for f in list_fields:
            existing = profile.get(f,[])
            incoming = new_data.get(f,[])
            if isinstance(incoming, str):
                try: incoming = json.loads(incoming)
                except: incoming = [incoming] if incoming else []
            for item in incoming:
                if item not in existing: existing.append(item)
            profile[f] = existing
        profile["source"] = source

    # ===== 数据源采集器 =====
    def _fetch_from_tianyancha(self, company_name):
        # 优先走开放平台 API（已配置 token 时），否则退回静态抓取
        if self._get_tyc_token():
            return self._fetch_tianyancha_api(company_name)
        if not HAS_REQUESTS or not HAS_BS4: return {}
        try:
            url = f"https://www.tianyancha.com/search?key={company_name}"
            resp = requests.get(url, timeout=15, headers={
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if resp.status_code != 200: return {}
            soup = BeautifulSoup(resp.text, "html.parser")
            result = {"source":"tianyancha"}
            leg = soup.find("a",{"tyc-event-ch":"CompanySearch.LegalPerson"})
            if leg: result["legal_person"] = leg.text.strip()
            return result
        except: return {}

    def _fetch_from_qichacha(self, company_name):
        if not HAS_REQUESTS or not HAS_BS4: return {}
        try:
            url = f"https://www.qichacha.com/search?key={company_name}"
            resp = requests.get(url, timeout=15, headers={
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if resp.status_code != 200: return {"source":"qichacha"}
            soup = BeautifulSoup(resp.text, "html.parser")
            result = {"source":"qichacha"}
            oper = soup.find("a", class_=lambda c: c and "bname" in str(c))
            if oper: result["legal_person"] = oper.text.strip()
            return result
        except: return {}

    def _fetch_from_qixinbao(self, company_name):
        return {"source":"qixinbao"}

    # ===== 天眼查开放平台 API（token 认证）=====
    def _get_tyc_token(self):
        if self.org_mgr:
            tok = self.org_mgr.get_setting("api_key:tianyancha_token", "")
            if tok: return tok
        return API_KEYS.get("tianyancha_token", "")

    def _tyc_api_get(self, endpoint_key, query):
        """调用天眼查开放平台接口，返回 result dict 或 {}。

        鉴权失效（token 过期/欠费/风控）与"无数据"分开：前者记日志提示用户去开放平台
        后台更新 token。注意：开放平台 API 的 token 无法通过浏览器登录网页获得，
        因此这里不触发浏览器登录兜底，只做明确告警。
        """
        token = self._get_tyc_token()
        if not token or not HAS_REQUESTS: return {}
        url = API_ENDPOINTS.get(endpoint_key, "")
        if not url: return {}
        self._wait_limit("tianyancha")
        try:
            r = requests.get(url.format(query=query), timeout=15,
                             headers={"Authorization": token})
            if r.status_code != 200: return {}
            data = r.json()
            ec = data.get("error_code", 0)
            if ec != 0:
                self._log(f"[天眼查] token 失效/欠费/风控 error_code={ec}，"
                          f"请在「系统设置」更新天眼查开放平台 Token（浏览器登录无法获取 API token）")
                return {}
            return data.get("result") or {}
        except Exception:
            return {}

    @staticmethod
    def _first(item, *keys):
        for k in keys:
            v = item.get(k)
            if v: return v
        return ""

    @classmethod
    def _tyc_ratio(cls, item):
        for k in ("fundedRatio", "percent", "ratio"):
            v = item.get(k)
            if isinstance(v, (int, float)): return float(v)
            if isinstance(v, str):
                s = v.replace("%", "").strip()
                try: return float(s) / 100.0 if "%" in v else float(s)
                except: pass
        cap = item.get("capitalActl") or item.get("capital")
        if isinstance(cap, list) and cap:
            return cls._tyc_ratio(cap[0])
        return None

    def _fetch_tianyancha_api(self, company_name):
        """天眼查开放平台：股东信息（需 token）。"""
        result = {"source": "tianyancha_api", "shareholders": []}
        holder = self._tyc_api_get("tianyancha_holder", company_name)
        for it in (holder.get("items") or holder.get("holderList") or []):
            name = self._first(it, "name", "holderName", "stockName", "shareholderName")
            if name:
                result["shareholders"].append({"name": name, "ratio": self._tyc_ratio(it)})
        return result

    # ===== 爱企查（百度）登录态 cookie 复用 =====
    def _get_aiqicha_cookie(self):
        if self.org_mgr:
            # 优先用浏览器登录落库的加密 Cookie（人在环兜底产物）
            ck = self.org_mgr.get_browser_cookie("aiqicha")
            if ck: return ck
            ck = self.org_mgr.get_setting("api_key:aiqicha_cookie", "")
            if ck: return ck
        return API_KEYS.get("aiqicha_cookie", "")

    def _aiqicha_get(self, url, _retry=True):
        if not HAS_REQUESTS: return {}
        self._wait_limit("aiqicha")
        try:
            r = self._session_http().get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Cookie": self._get_aiqicha_cookie(),
                "Referer": "https://aiqicha.baidu.com/",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/plain, */*",
            })
            if r.status_code != 200:
                if r.status_code in (401, 403) or self._is_login_redirect(r):
                    self._log(f"[爱企查] 登录态失效 (HTTP {r.status_code})")
                    if _retry and self._request_login("aiqicha", f"HTTP {r.status_code}"):
                        return self._aiqicha_get(url, _retry=False)
                return {}
            data = r.json() or {}
            if self._is_aiqicha_nologin(data):
                self._log("[爱企查] 登录态失效 (userType=nologin)")
                if _retry and self._request_login("aiqicha", "nologin"):
                    return self._aiqicha_get(url, _retry=False)
                return {}
            return data
        except Exception:
            return {}

    def _aiqicha_search_pid(self, company_name):
        url = API_ENDPOINTS.get("aiqicha_search", "").format(query=company_name)
        data = self._aiqicha_get(url)
        for it in (data.get("data") or {}).get("list") or []:
            pid = it.get("pid") or it.get("entId") or ""
            if pid: return str(pid)
        return ""

    def _fetch_from_aiqicha_api(self, company_name):
        result = {"source": "aiqicha_api", "shareholders": []}
        pid = self._aiqicha_search_pid(company_name)
        if not pid: return result
        data = self._aiqicha_get(API_ENDPOINTS.get("aiqicha_baseinfo", "").format(pid=pid))
        d = data.get("data") or {}
        lp = d.get("legalPerson") or d.get("operName") or ""
        if lp: result["legal_person"] = lp
        holders = d.get("shareholderList") or d.get("stockList") or d.get("holderList") or []
        for h in holders:
            name = self._first(h, "name", "stockName", "holderName", "shareholderName")
            if name:
                result["shareholders"].append({"name": name, "ratio": self._tyc_ratio(h)})
        return result

    def _aiqicha_investments(self, company_name):
        pid = self._aiqicha_search_pid(company_name)
        if not pid: return []
        data = self._aiqicha_get(API_ENDPOINTS.get("aiqicha_invest", "").format(pid=pid))
        d = data.get("data") or {}
        items = d.get("list") or d.get("investList") or []
        subs = []
        for it in items:
            name = self._first(it, "entName", "name", "investName", "companyName")
            if name:
                subs.append({"name": name, "equity_ratio": self._tyc_ratio(it)})
        return subs

    def _fetch_from_aiqicha(self, company_name):
        # 优先用登录态 cookie 复用内部接口，否则占位
        if self._get_aiqicha_cookie():
            return self._fetch_from_aiqicha_api(company_name)
        return {"source":"aiqicha"}

    def _fetch_from_gsxt(self, company_name):
        return {"source":"gsxt"}

    def _fetch_from_beian(self, company_name):
        if not self.enrichment: return {"source":"beian"}
        records = self.enrichment.query_icp_by_company(company_name)
        if records:
            domains = list(set(r.get("domain_name","") for r in records if r.get("domain_name")))
            return {"source":"beian","domains":domains}
        return {"source":"beian"}

    # ===== 更名历史追踪 =====
    def track_name_history(self, company_name):
        changes = []
        if not HAS_REQUESTS or not HAS_BS4: return changes
        for source in ["tianyancha","qichacha"]:
            try:
                fetcher = getattr(self, f"_fetch_from_{source}")
                data = fetcher(company_name) or {}
                for c in (data.get("name_changes") or []):
                    if c not in changes: changes.append(c)
            except: pass
        return changes

    def build_org_timeline(self, company_name):
        timeline = []
        changes = self.track_name_history(company_name)
        for c in sorted(changes, key=lambda x: x.get("change_date","")):
            timeline.append({"name":c.get("old_name",""),
                "period_end":c.get("change_date",""),
                "change_type":c.get("change_type","rename")})
        timeline.append({"name":company_name,"period_start":"",
            "period_end":"至今"})
        return timeline

    def search_by_all_names(self, company_name):
        """全名称搜索: 当前名+简称+所有曾用名+更名历史"""
        profile = self.extract_enterprise_profile(company_name)
        all_names = {company_name}
        if profile.get("short_name"): all_names.add(profile["short_name"])
        for fn in (profile.get("former_names") or []): all_names.add(str(fn))
        for nc in (profile.get("name_changes") or []):
            all_names.add(nc.get("old_name",""))
            all_names.add(nc.get("new_name",""))
        return list(all_names)

    # ===== 4级股权穿透BFS =====
    def discover_subsidiaries(self, company_name, max_level=None, min_equity=None):
        max_level = max_level or MAX_EQUITY_CHAIN_DEPTH
        min_equity = min_equity or MIN_EQUITY_RATIO
        visited = set()
        queue = deque([(company_name, 0, "", 1.0)])
        all_subs, all_rels = [], []
        self._log(f"[BFS] '{company_name}' depth≤{max_level} ratio≥{min_equity*100}%")
        while queue:
            if self._stop_event.is_set():
                self._log("[BFS] 已停止")
                break
            name, depth, parent_path, equity = queue.popleft()
            if name in visited or depth > max_level: continue
            visited.add(name)
            if depth > 0:
                all_subs.append({"sub_name":name,"equity_ratio":equity,
                    "chain_level":depth,"chain_path":f"{parent_path} -> {name}"})
            for sub in self._query_investments(name):
                sn, sr = sub.get("name",""), sub.get("equity_ratio")
                if sn and sn not in visited and (sr is None or sr >= min_equity):
                    np = f"{parent_path} -> {name}" if depth > 0 else name
                    queue.append((sn, depth+1, np, sr))
                    all_rels.append({"from_name":name,"to_name":sn,
                        "relation_type":"holding","equity_ratio":sr,
                        "chain_level":depth+1})
        self._log(f"[BFS] {len(all_subs)} subsidiaries, {len(all_rels)} relations")
        return all_subs, all_rels

    def _query_investments(self, company_name):
        # 优先走天眼查开放平台 API（已配置 token 时）
        if self._get_tyc_token():
            invest = self._tyc_api_get("tianyancha_invest", company_name)
            subs = []
            for it in (invest.get("items") or invest.get("investList") or []):
                name = self._first(it, "name", "investName", "companyName")
                if name:
                    subs.append({"name": name, "equity_ratio": self._tyc_ratio(it)})
            if subs: return subs
        # 爱企查登录态 cookie 复用
        if self._get_aiqicha_cookie():
            subs = self._aiqicha_investments(company_name)
            if subs: return subs
        subs = []
        if HAS_REQUESTS and HAS_BS4:
            try:
                url = f"https://www.tianyancha.com/search?key={company_name}"
                resp = requests.get(url, timeout=10, headers={
                    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", class_=lambda c: c and "link-click" in str(c)):
                        n = a.get_text(strip=True)
                        if n and n != company_name and len(n)>2:
                            subs.append({"name":n,"equity_ratio":None})
            except: pass
        return subs

    # ===== 12类标识符专项查询 =====
    def search_by_legal_person(self, name):
        return self._person_related_search(name, "legal_person")

    def search_by_shareholder(self, name):
        return self._person_related_search(name, "shareholder")

    def search_by_shareholder_downstream(self, name):
        return self._person_related_search(name, "shareholder")

    def search_by_controller(self, name):
        return self._person_related_search(name, "controller")

    def search_by_beneficial_owner(self, name):
        return self._person_related_search(name, "beneficial_owner")

    def _person_related_search(self, person_name, role_type):
        results = []
        if HAS_REQUESTS and HAS_BS4:
            try:
                url = f"https://www.tianyancha.com/search?key={person_name}"
                resp = requests.get(url, timeout=15, headers={
                    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for item in soup.find_all("div", class_=lambda c: c and "search-item" in str(c)):
                        a = item.find("a")
                        if a:
                            results.append({"company_name":a.get_text(strip=True),
                                "relation":role_type,"person":person_name,"source":"tianyancha"})
            except: pass
        return results

    # ===== 全维度发散搜索 =====
    def full_divergent_search(self, company_name):
        all_results = {"profiles":[],"subsidiaries":[],"relations":[],
            "assets":[],"name_variants":[],"name_history":[]}
        self._log(f"[发散] Step0: 提取 '{company_name}' 档案")
        profile = self.extract_enterprise_profile(company_name)
        all_results["profiles"].append(profile)
        all_results["name_variants"] = self.search_by_all_names(company_name)
        all_results["name_history"] = profile.get("name_changes",[])
        self._log("[发散] Step1: 股权穿透BFS")
        subs, rels = self.discover_subsidiaries(company_name)
        all_results["subsidiaries"] = subs
        all_results["relations"] = rels
        lp = profile.get("legal_person","")
        if lp:
            self._log(f"[发散] Step2: 法人 '{lp}'")
            all_results["relations"].extend(self.search_by_legal_person(lp))
        shareholders = profile.get("shareholders",[])
        if isinstance(shareholders, str):
            try: shareholders = json.loads(shareholders)
            except: shareholders = []
        for sh in (shareholders or [])[:5]:
            sn = sh.get("name","") if isinstance(sh,dict) else str(sh)
            if sn:
                all_results["relations"].extend(self.search_by_shareholder(sn))
                all_results["relations"].extend(self.search_by_shareholder_downstream(sn))
        for key, role in [("actual_controllers","控制人"),("beneficial_owners","受益人")]:
            persons = profile.get(key,[])
            if isinstance(persons, str):
                try: persons = json.loads(persons)
                except: persons = [persons] if persons else []
            for p in (persons or [])[:3]:
                all_results["relations"].extend(self._person_related_search(str(p), key))
        if self.enrichment:
            self._log("[发散] Step5: 邮箱/电话交叉搜索")
            all_results["assets"] = self.enrichment.search_all_identifiers(profile)
        discovered = set()
        for r in all_results["relations"]:
            for k in ["company_name","to_name"]:
                v = r.get(k,"")
                if v: discovered.add(v)
        new_names = discovered - {company_name}
        if new_names and MAX_RECURSIVE_SEARCH_DEPTH > 0:
            self._log(f"[发散] 递归 {len(new_names)}个新企业")
            for nn in list(new_names)[:10]:
                if self._stop_event.is_set():
                    self._log("[发散] 已停止")
                    break
                try:
                    sp = self.extract_enterprise_profile(nn)
                    all_results["profiles"].append(sp)
                    ss, sr = self.discover_subsidiaries(nn, max_level=2)
                    all_results["subsidiaries"].extend(ss)
                    all_results["relations"].extend(sr)
                except Exception as e:
                    self._log(f"  [warn] {nn}: {e}")
        self._log(f"[发散] 完成: {len(all_results['profiles'])}档案 "
            f"{len(all_results['subsidiaries'])}子公司 {len(all_results['relations'])}关系 "
            f"{len(all_results['assets'])}交叉资产 {len(all_results['name_variants'])}名称变体")
        return all_results

    def resolve_identifier(self, identifier_value):
        """任意标识符→关联企业"""
        results = []
        if self.org_mgr:
            for r in self.org_mgr.resolve_identifier(identifier_value):
                results.append(dict(r))
        for pr in self._person_related_search(identifier_value, "lookup"):
            if pr not in results: results.append(pr)
        return results