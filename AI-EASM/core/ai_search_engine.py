# -*- coding: utf-8 -*-
"""AI全网资产搜索引擎 — 15维度真实数据发现 + 7因子置信度评分"""
import os, sys, threading, socket, ssl, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import CONFIDENCE_WEIGHTS, NAME_LIKE_CLUE_TYPES
from config.dork_library import (SEARCH_DORK_TEMPLATES, build_query,
                                 build_platform_url, KEY_LEAK_KEYWORDS)
try: import requests; HAS_REQUESTS = True
except ImportError: HAS_REQUESTS = False

class AISearchEngine:
    ASSET_DIMENSIONS = [
        ("domain","域名资产"),("subdomain","子域名"),("ip","IP资产"),
        ("cloud","云资产"),("certificate","SSL证书"),("code_repo","代码仓库"),
        ("document","文库文档"),("app","APP应用"),("wechat","公众号/小程序"),
        ("email","邮箱资产"),("supply_chain","供应链"),("social","社工信息"),
        ("port_service","端口服务"),("data_leak","数据泄露"),("network_device","网络设备"),
        ("surface_dork","暴露面检索"),("sensitive_dir","敏感目录/文件"),("mgmt_entry","管理入口"),
    ]

    def __init__(self, org_manager, enrichment_engine=None, leak_detector=None,
                 shadow_detector=None, cache_manager=None):
        self.org_mgr = org_manager; self.enrichment = enrichment_engine
        self.leak_detector = leak_detector; self.shadow_detector = shadow_detector
        self.cache = cache_manager
        self._stop_event = threading.Event()
        self._log_cb = self._progress_cb = self._found_cb = None

    def set_callbacks(self, log_cb=None, progress_cb=None, found_cb=None):
        self._log_cb = log_cb; self._progress_cb = progress_cb; self._found_cb = found_cb
    def _log(self, m):
        if self._log_cb: self._log_cb(m)
    def _progress(self, p, s=""):
        if self._progress_cb: self._progress_cb(p, s)
    def _found(self, t, n, v, s, r="INFO", d=""):
        if self._found_cb: self._found_cb(t, n, v, s, r, d)
    def stop(self): self._stop_event.set()

    # ===== 主入口 =====
    def search(self, org_id, org_name, domain=None, dimensions=None, multi_name=False):
        self._stop_event.clear()
        org = self.org_mgr.get_org(org_id)
        if org:
            try: org = dict(org)
            except: pass
        org_name = org.get("org_name", org_name) if org else org_name
        domain = domain or (org.get("domain_name","") if org else "")
        if not dimensions: dimensions = [d[0] for d in self.ASSET_DIMENSIONS]
        total = len(dimensions)
        self._log(f"[AI搜索] '{org_name}' {total}维度")

        search_names = [org_name]
        self._clue_identifiers = []
        if self.org_mgr:
            # 组织线索：名称型并入多名称搜索，标识符型用于精准检索
            try:
                for c in self.org_mgr.list_clues(org_id):
                    t = (c["clue_type"] or "").strip()
                    v = (c["clue_value"] or "").strip()
                    if not v: continue
                    if t in NAME_LIKE_CLUE_TYPES:
                        if multi_name and v not in search_names:
                            search_names.append(v)
                    else:
                        self._clue_identifiers.append((t, v))
            except Exception:
                pass
        if multi_name and self.org_mgr:
            p = self.org_mgr.get_enterprise_profile(org_id=org_id)
            if p:
                if p["short_name"]: search_names.append(p["short_name"])
                try: search_names.extend(json.loads(p["former_names"] or "[]")[:3])
                except: pass
        if self._clue_identifiers:
            self._log(f"[线索] {len(self._clue_identifiers)}条标识符线索, {len(search_names)}个搜索名称")

        all_results = []
        for ni, sn in enumerate(search_names):
            if self._stop_event.is_set(): break
            if ni > 0: self._log(f"[多名称#{ni}] '{sn}'")
            for i, dim in enumerate(dimensions):
                if self._stop_event.is_set(): break
                pct = int((i+1)/total*100)
                dim_name = dict(self.ASSET_DIMENSIONS).get(dim, dim)
                self._progress(pct, dim_name)
                m = getattr(self, f"_search_{dim}", None)
                if m:
                    try:
                        rl = m(sn, domain)
                        all_results.extend(rl)
                        for r in rl:
                            self._found(r["asset_type"],r["asset_name"],r["asset_value"],
                                r["source"],r.get("risk_level","INFO"),r.get("detail",""))
                    except Exception as e: self._log(f"  [{dim_name}] {e}")

        self._progress(95, "AI置信度评分")
        scored = self._ai_confidence_scoring(org_name, all_results)

        if self.shadow_detector:
            known = [domain] if domain else []
            for s in self.shadow_detector.detect_shadow_assets(known, scored):
                s["risk_level"] = "HIGH" if s.get("shadow_risk",0)>=6 else "MEDIUM"
                s["detail"] = (s.get("detail","")+" [疑似影子资产]").strip()

        # AI 风险研判（LLM，可选）
        judge = self._ai_risk_judge(org_name, scored)
        if judge:
            scored.append({"asset_type":"ai_risk","asset_name":"AI风险研判",
                "asset_value":"LLM","source":"LLM风险研判","detail":judge[:500],
                "risk_level":"INFO","confidence":0.8})
            self._log(f"[AI风险研判] {judge[:80]}...")

        exposures = [{"org_id":org_id,"asset_type":r["asset_type"],
            "asset_name":r["asset_name"],"asset_value":r["asset_value"],
            "source":r["source"],"detail":r.get("detail",""),
            "risk_level":r.get("risk_level","INFO"),
            "confidence":r.get("confidence",0.5),
            "confidence_factors":r.get("confidence_factors","")} for r in scored]
        if exposures: self.org_mgr.add_exposure_batch(exposures)
        self._progress(100, f"完成 {len(scored)}条")
        self._log(f"[完成] {len(scored)}条暴露面")
        return scored

    # ===== 15搜索维度 =====
    def _search_domain(self, org_name, domain):
        r = []
        if domain: r.append({"asset_type":"domain","asset_name":f"主域名-{domain}","asset_value":domain,"source":"用户输入","risk_level":"INFO"})
        if self.enrichment:
            for ic in self.enrichment.query_icp_by_company(org_name):
                d = ic.get("domain_name","")
                if d and d != domain:
                    r.append({"asset_type":"domain","asset_name":f"ICP-{d}","asset_value":d,"source":"ICP备案","risk_level":"INFO","detail":f"ICP:{ic.get('icp_number','')}"})
        return r

    def _search_subdomain(self, org_name, domain):
        if not domain: return []
        r = []
        if self.enrichment:
            for s in self.enrichment.enumerate_subdomains(domain):
                r.append({"asset_type":"subdomain","asset_name":s,"asset_value":s,"source":"crt.sh+DNS","risk_level":"INFO"})
            for e in self.enrichment.query_otx_passive_dns(domain):
                hn = e.get("hostname","")
                if hn: r.append({"asset_type":"subdomain","asset_name":hn,"asset_value":hn,"source":"OTX","risk_level":"INFO","detail":f"IP:{e.get('address','')}"})
        return r

    def _search_ip(self, org_name, domain):
        r = []
        if domain:
            try:
                ip = socket.gethostbyname(domain)
                r.append({"asset_type":"ip","asset_name":f"{domain} IP","asset_value":ip,"source":"DNS","risk_level":"INFO"})
                if self.enrichment:
                    for nip in self.enrichment.reverse_ip_neighbors(ip, 5):
                        r.append({"asset_type":"ip","asset_name":f"邻居-{nip}","asset_value":nip,"source":"邻居发现","risk_level":"LOW"})
            except: pass
        return r

    def _search_cloud(self, org_name, domain):
        return self.enrichment.check_cloud_bucket(org_name, domain) if self.enrichment else []

    def _search_certificate(self, org_name, domain):
        r = []
        if domain and self.enrichment:
            cert = self.enrichment.query_ssl_certificate(domain)
            if cert:
                r.append({"asset_type":"certificate","asset_name":f"SSL-{cert.get('cn','')}","asset_value":cert.get("cn",""),"source":"SSL直连","risk_level":"LOW","detail":f"SAN:{','.join(cert.get('sans',[])[:8])}"})
            for c in self.enrichment.query_crtsh(domain)[:10]:
                r.append({"asset_type":"certificate","asset_name":c["asset_name"],"asset_value":c["asset_value"],"source":"crt.sh","risk_level":"LOW"})
        return r

    def _search_code_repo(self, org_name, domain):
        r = []
        if self.enrichment:
            queries = [f'"{org_name}"']
            if domain: queries.append(f'"{domain}"')
            for kw in KEY_LEAK_KEYWORDS[:6]:
                queries.append(f'"{org_name}" {kw}')
            # 标识符型线索（信用代码/电话/邮箱/地址等）作为精确检索词
            for _t, v in getattr(self, "_clue_identifiers", []):
                q = f'"{v}"'
                if q not in queries: queries.append(q)
            for q in queries:
                for gh in self.enrichment.query_github_search(q)[:10]:
                    r.append({"asset_type":"code_repo","asset_name":f"{gh['repo']}/{gh['name']}","asset_value":gh["url"],"source":"GitHub","risk_level":"HIGH","detail":"代码泄露风险"})
                for ge in self.enrichment.query_gitee_search(q)[:5]:
                    r.append({"asset_type":"code_repo","asset_name":ge.get("repo",""),"asset_value":ge.get("url",""),"source":"Gitee","risk_level":"HIGH","detail":"代码泄露风险"})
                for gl in self.enrichment.query_gitlab_search(q)[:5]:
                    r.append({"asset_type":"code_repo","asset_name":gl.get("repo",""),"asset_value":gl.get("url",""),"source":"GitLab","risk_level":"HIGH","detail":"代码泄露风险"})
        return r

    def _with_search_result(self, exposures, org_name):
        """为「搜索 URL 模板」型暴露面补充真实搜索结果（best-effort，反爬时标注无法确认）。"""
        if not self.enrichment:
            return exposures
        for r in exposures:
            av = r.get("asset_value", "")
            if av.startswith(("http://", "https://")) and "搜索结果" not in (r.get("detail") or ""):
                res = self.enrichment.probe_search_result(av, org_name)
                if res:
                    d = (r.get("detail") or "").strip()
                    r["detail"] = (d + "；" if d else "") + res
        return exposures

    def _search_document(self, org_name, domain):
        return self._with_search_result([
            {"asset_type":"document","asset_name":f"百度文库-{org_name}","asset_value":f"https://wenku.baidu.com/search?word={org_name}","source":"百度文库","risk_level":"MEDIUM"},
            {"asset_type":"document","asset_name":f"道客巴巴-{org_name}","asset_value":f"https://www.doc88.com/?keyword={org_name}","source":"道客巴巴","risk_level":"MEDIUM"}], org_name)

    def _search_app(self, org_name, domain):
        return [{"asset_type":"app","asset_name":f"应用商店-{org_name}","asset_value":org_name,"source":"应用商店","risk_level":"LOW"}]

    def _search_wechat(self, org_name, domain):
        return self._with_search_result([
            {"asset_type":"wechat","asset_name":f"微信公众号-{org_name}","asset_value":f"https://weixin.sogou.com/weixin?type=2&query={org_name}","source":"搜狗微信","risk_level":"LOW"}], org_name)

    def _search_email(self, org_name, domain):
        r = []
        if domain:
            r.append({"asset_type":"email","asset_name":f"邮箱-@{domain}","asset_value":f"@{domain}","source":"域名推断","risk_level":"LOW"})
            if self.enrichment:
                for e in self.enrichment.query_hunter_emails(domain)[:10]:
                    r.append({"asset_type":"email","asset_name":f"邮箱-{e.get('value','')}","asset_value":e.get("value",""),"source":"Hunter.io","risk_level":"LOW"})
        return r

    def _search_supply_chain(self, org_name, domain):
        items = [
            {"asset_type":"supply_chain","asset_name":f"国家企业信用信息公示系统-{org_name}","asset_value":f"https://www.gsxt.gov.cn/index.html","source":"国家企业信用信息公示系统","risk_level":"MEDIUM","detail":"企业登记/信用信息"},
            {"asset_type":"supply_chain","asset_name":f"爱企查-{org_name}","asset_value":f"https://aiqicha.baidu.com/s?q={org_name}","source":"爱企查","risk_level":"MEDIUM","detail":"企业档案/关联方"},
            {"asset_type":"supply_chain","asset_name":f"天眼查-{org_name}","asset_value":f"https://www.tianyancha.com/search?key={org_name}","source":"天眼查","risk_level":"MEDIUM","detail":"股权穿透/关联方"},
            {"asset_type":"supply_chain","asset_name":f"企查查-{org_name}","asset_value":f"https://www.qichacha.com/search?key={org_name}","source":"企查查","risk_level":"MEDIUM","detail":"供应商/客户"},
            {"asset_type":"supply_chain","asset_name":f"启信宝-{org_name}","asset_value":f"https://www.qixin.com/search?key={org_name}","source":"启信宝","risk_level":"MEDIUM","detail":"企业信息/司法"},
        ]
        # 标识符型线索 → 天眼查/爱企查/企查查精确检索
        for t, v in getattr(self, "_clue_identifiers", []):
            items.append({"asset_type":"supply_chain","asset_name":f"天眼查[{t}]-{v}",
                          "asset_value":f"https://www.tianyancha.com/search?key={v}",
                          "source":"天眼查","risk_level":"MEDIUM","detail":f"线索({t})检索"})
            items.append({"asset_type":"supply_chain","asset_name":f"企查查[{t}]-{v}",
                          "asset_value":f"https://www.qichacha.com/search?key={v}",
                          "source":"企查查","risk_level":"MEDIUM","detail":f"线索({t})检索"})
        return self._with_search_result(items, org_name)

    def _search_social(self, org_name, domain):
        return self._with_search_result([
            {"asset_type":"social","asset_name":f"领英-{org_name}","asset_value":f"https://www.linkedin.com/search/results/companies/?keywords={org_name}","source":"LinkedIn","risk_level":"MEDIUM"},
            {"asset_type":"social","asset_name":f"脉脉-{org_name}","asset_value":f"https://maimai.cn/search?q={org_name}","source":"脉脉","risk_level":"LOW"}], org_name)

    def _search_port_service(self, org_name, domain):
        r = []
        if domain:
            try:
                ip = socket.gethostbyname(domain)
                if self.enrichment:
                    sd = self.enrichment.query_shodan_ip(ip)
                    for p in sd.get("ports",[])[:20]:
                        r.append({"asset_type":"port_service","asset_name":f"{ip}:{p}","asset_value":f"{ip}:{p}","source":"Shodan","risk_level":"HIGH","detail":f"开放端口: {p}"})
                if not r:
                    r.append({"asset_type":"port_service","asset_name":f"Shodan-{ip}","asset_value":f"https://www.shodan.io/host/{ip}","source":"Shodan","risk_level":"HIGH"})
            except: pass
        return r

    def _search_data_leak(self, org_name, domain):
        r = [{"asset_type":"data_leak","asset_name":f"数据泄露-{org_name}","asset_value":org_name,"source":"AI监测","risk_level":"HIGH"}]
        if self.leak_detector:
            for lk in self.leak_detector.scan_github_code(org_name, domain):
                r.append({"asset_type":"data_leak","asset_name":lk.get("matched_content_snippet","")[:80],"asset_value":lk.get("source_url",""),"source":"GitHub LeakDetector","risk_level":lk.get("severity","HIGH"),"detail":f"[{lk.get('leak_pattern','')}]"})
        return r

    def _search_network_device(self, org_name, domain):
        r = []
        if domain:
            try:
                ip = socket.gethostbyname(domain)
                r.append({"asset_type":"network_device","asset_name":f"入口-{domain}","asset_value":ip,"source":"DNS","risk_level":"MEDIUM"})
                if self.enrichment:
                    bgp = self.enrichment.query_asn_bgp(ip)
                    if bgp:
                        r.append({"asset_type":"network_device","asset_name":f"ASN-{bgp.get('asn_number','')}","asset_value":bgp.get("ip_range",""),"source":"BGPView","risk_level":"MEDIUM","detail":f"ISP:{bgp.get('isp','')} ASN:{bgp.get('asn_name','')}"})
            except: pass
        return r

    # ===== 暴露面检索（6维度补充） =====
    def _run_dork_sweep(self, org_name, domain, dims):
        api_methods = {
            "fofa": "query_fofa", "quake": "query_quake", "hunter": "query_hunter_qianxin",
            "censys": "query_censys_search", "zoomeye": "query_zoomeye_search",
            "github": "query_github_search", "gitee": "query_gitee_search", "gitlab": "query_gitlab_search",
            "certspotter": "query_certspotter",
        }
        dim_risk = {"space_mapping": "MEDIUM", "code_repo": "HIGH", "search_engine": "MEDIUM",
                    "mgmt_entry": "MEDIUM", "cert_transparency": "LOW", "doc_leak": "MEDIUM"}
        r = []
        for dim in dims:
            platforms = SEARCH_DORK_TEMPLATES.get(dim, {})
            risk = dim_risk.get(dim, "MEDIUM")
            for platform, items in platforms.items():
                mname = api_methods.get(platform)
                for label, tmpl in items:
                    if "{domain}" in tmpl and not domain: continue
                    q = build_query(tmpl, domain=domain, org=org_name)
                    if not q: continue
                    found = False
                    if mname and self.enrichment:
                        m = getattr(self.enrichment, mname, None)
                        if m:
                            try:
                                for item in m(q)[:10]:
                                    val = item.get("url") or item.get("host") or item.get("ip") or item.get("repo") or item.get("asset_value") or item.get("domain") or ""
                                    if val:
                                        r.append({"asset_type": dim, "asset_name": f"{platform}-{label}",
                                                  "asset_value": val, "source": platform,
                                                  "risk_level": risk, "detail": f"查询: {q}"})
                                        found = True
                            except: pass
                    if not found:
                        url = build_platform_url(platform, q)
                        detail = f"查询: {q}"
                        if url and url.startswith(("http://","https://")) and self.enrichment:
                            res = self.enrichment.probe_search_result(url, org_name)
                            if res: detail += f"；{res}"
                        r.append({"asset_type": dim, "asset_name": f"{platform}-{label}",
                                  "asset_value": url or q, "source": platform,
                                  "risk_level": risk if url else "INFO", "detail": detail})
        return r

    def _search_surface_dork(self, org_name, domain):
        return self._run_dork_sweep(org_name, domain,
            ["search_engine", "space_mapping", "code_repo", "cert_transparency", "doc_leak"])

    def _search_mgmt_entry(self, org_name, domain):
        return self._run_dork_sweep(org_name, domain, ["mgmt_entry"])

    def _search_sensitive_dir(self, org_name, domain):
        if not domain or not self.enrichment: return []
        r = []
        for hit in self.enrichment.probe_sensitive_paths(domain):
            st = hit["status"]
            if 200 <= st < 400:
                level, result = "HIGH", f"搜索结果：1（HTTP {st}，可访问）"
            elif st in (401, 403):
                level, result = "MEDIUM", f"搜索结果：存在但拒绝访问（HTTP {st}）"
            elif st == 404:
                level, result = "INFO", f"搜索结果：0（HTTP 404，未发现）"
            else:
                level, result = "INFO", f"搜索结果：—（HTTP {st}）"
            r.append({"asset_type": "sensitive_dir", "asset_name": f"敏感路径-{hit['path']}",
                      "asset_value": hit["url"], "source": "敏感目录探测",
                      "risk_level": level, "detail": result})
        return r

    # ===== 7因子AI置信度评分 =====
    def _ai_confidence_scoring(self, org_name, results):
        for r in results:
            factors = {}; score = 0.0
            f1 = self._is_dns_resolved(r)
            factors["dns_verified"] = 1.0 if f1 else 0.0
            score += (1.0 if f1 else 0.0) * CONFIDENCE_WEIGHTS["dns_verified"]
            f2 = self._cert_matches_org(r, org_name)
            factors["cert_match"] = f2
            score += f2 * CONFIDENCE_WEIGHTS["cert_match"]
            f3 = self._name_similarity(r, org_name)
            factors["name_similarity"] = f3
            score += f3 * CONFIDENCE_WEIGHTS["name_similarity"]
            sources = set([r.get("source","")])
            f4 = min(len(sources)/3.0, 1.0)
            factors["multi_source"] = f4
            score += f4 * CONFIDENCE_WEIGHTS["multi_source"]
            f5 = self._icp_confirms(r, org_name)
            factors["icp_confirm"] = 1.0 if f5 else 0.0
            score += (1.0 if f5 else 0.0) * CONFIDENCE_WEIGHTS["icp_confirm"]
            f6 = self._fingerprint_matches(r)
            factors["fingerprint_match"] = 1.0 if f6 else 0.0
            score += (1.0 if f6 else 0.0) * CONFIDENCE_WEIGHTS["fingerprint_match"]
            f7 = self._whois_matches_org(r, org_name)
            factors["whois_match"] = 1.0 if f7 else 0.0
            score += (1.0 if f7 else 0.0) * CONFIDENCE_WEIGHTS["whois_match"]
            r["confidence"] = min(score, 0.98)
            r["confidence_factors"] = json.dumps(factors, ensure_ascii=False)
            if r["confidence"] >= 0.85: tag = "高可信度-确认资产"
            elif r["confidence"] >= 0.65: tag = "中可信度-待确认"
            elif r["confidence"] >= 0.40: tag = "低可信度-疑似影子资产"
            else: tag = "需人工研判"
            r["detail"] = (r.get("detail","") + f" [AI:{tag}]").strip()
        return sorted(results, key=lambda x: x.get("confidence",0), reverse=True)

    def _ai_risk_judge(self, org_name, scored):
        """LLM 风险研判：对高危/高分资产做自然语言研判（未配置 LLM 时返回 None）。"""
        try:
            from core.llm_client import LLMClient
            llm = LLMClient(org_manager=self.org_mgr)
            if not llm.available():
                return None
            top = [r for r in scored if r.get("risk_level") in ("CRITICAL","HIGH")][:15]
            if not top:
                top = sorted(scored, key=lambda x: x.get("confidence",0), reverse=True)[:15]
            return llm.assess_risks(org_name, top) or None
        except Exception:
            return None

    def _is_dns_resolved(self, r):
        av = r.get("asset_value","")
        if not av or "." not in av: return False
        try: socket.gethostbyname(av.replace("https://","").replace("http://","").split("/")[0]); return True
        except: return False

    def _cert_matches_org(self, r, org_name):
        d = r.get("detail",""); n = r.get("asset_name","")
        if org_name and org_name[:4] in (d+n): return 0.8
        if "SAN:" in d: return 0.3
        return 0.0

    def _name_similarity(self, r, org_name):
        a = (r.get("asset_name","") or "")[:30]; b = (org_name or "")[:20]
        if not a or not b: return 0.0
        if b[:4] in a or a[:4] in b: return 0.8
        m, n = len(a), len(b)
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(m+1): dp[i][0] = i
        for j in range(n+1): dp[0][j] = j
        for i in range(1,m+1):
            for j in range(1,n+1):
                dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+(0 if a[i-1]==b[j-1] else 1))
        return max(0, 1-dp[m][n]/max(m,n))

    def _icp_confirms(self, r, org_name):
        av = r.get("asset_value","")
        if not av or not self.org_mgr: return False
        try:
            for rec in self.org_mgr.list_icp_records(domain_name=av):
                if org_name[:4] in (rec["company_name"] or ""): return True
        except: pass
        return False

    def _fingerprint_matches(self, r):
        av = r.get("asset_value","")
        if not av or not self.org_mgr: return False
        try:
            with self.org_mgr._connect() as conn:
                return conn.execute("SELECT COUNT(*) as cnt FROM site_fingerprints WHERE domain=?",(av,)).fetchone()["cnt"] > 0
        except: return False

    def _whois_matches_org(self, r, org_name):
        av = r.get("asset_value","")
        if not av or not self.org_mgr: return False
        try:
            w = self.org_mgr.get_whois(av)
            return bool(w and org_name[:4] in (w.get("registrant_org") or ""))
        except: return False

    # ===== 置信度分布统计 =====
    def get_confidence_distribution(self, org_id=None):
        """返回置信度分布: high/medium/low/shadow"""
        exps = self.org_mgr.list_exposures(org_id=org_id)
        dist = {"high":0,"medium":0,"low":0,"shadow":0,"total":len(exps)}
        for e in exps:
            try: e = dict(e)
            except: pass
            cf = e.get("confidence", 0.5) if isinstance(e, dict) else (e["confidence"] if isinstance(e, (tuple, list)) and len(e)>7 else 0.5)
            if isinstance(cf, (int, float)):
                if cf >= 0.85: dist["high"] += 1
                elif cf >= 0.65: dist["medium"] += 1
                elif cf >= 0.40: dist["low"] += 1
                else: dist["shadow"] += 1
        return dist

    def _pinyin_similarity(self, name1, name2):
        """中文汉字共现相似度"""
        if not name1 or not name2: return 0.0
        cn1 = set(c for c in name1 if '一' <= c <= '鿿')
        cn2 = set(c for c in name2 if '一' <= c <= '鿿')
        if not cn1 or not cn2: return 0.0
        common = len(cn1 & cn2); total = len(cn1 | cn2)
        return common / max(total, 1) if total > 0 else 0.0

    def _name_similarity(self, r, org_name):
        """增强版名称相似度 — 编辑距离 + 汉字共现"""
        a = (r.get("asset_name","") or "")[:30]
        b = (org_name or "")[:20]
        if not a or not b: return 0.0
        if b[:4] in a or a[:4] in b: return 0.85
        if b in a or a in b: return 0.95
        pinyin_sim = self._pinyin_similarity(a, b)
        if pinyin_sim > 0.5: return 0.6 + pinyin_sim * 0.3
        m, n = len(a), len(b)
        if m == 0 or n == 0: return pinyin_sim * 0.5
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(m+1): dp[i][0] = i
        for j in range(n+1): dp[0][j] = j
        for i in range(1,m+1):
            for j in range(1,n+1):
                dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1,
                    dp[i-1][j-1]+(0 if a[i-1]==b[j-1] else 1))
        edit_sim = max(0, 1-dp[m][n]/max(m,n))
        return max(edit_sim, pinyin_sim * 0.4)