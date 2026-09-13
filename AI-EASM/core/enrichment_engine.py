# -*- coding: utf-8 -*-
"""信息富化引擎 — DNS/WHOIS/ICP/SSL/Shodan/GitHub/BGP/指纹 统一查询"""
import os, sys, socket, ssl, hashlib, json, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (API_KEYS, API_ENDPOINTS, CACHE_TTL, TOP_SUBDOMAIN_WORDLIST,
                             ENABLE_BROWSER_PROBE, BROWSER_PROBE_TIMEOUT)
from config.dork_library import SENSITIVE_PATHS
try:
    import requests; HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
try:
    import dns.resolver; HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False
try:
    import whois as whois_lib; HAS_WHOIS = True
except ImportError:
    HAS_WHOIS = False

class EnrichmentEngine:
    """外部数据源统一查询入口 —— 全部查询方法均返回dict/list，调用方负责存储"""

    def __init__(self, org_manager=None, cache_manager=None):
        self.org_mgr = org_manager
        self.cache = cache_manager
        self._log_cb = None

    def set_callbacks(self, log_cb=None):
        self._log_cb = log_cb

    def _log(self, msg):
        if self._log_cb: self._log_cb(msg)

    def _cached(self, key, ttl_key, fetcher):
        if self.cache:
            cached = self.cache.get(key)
            if cached: return cached
        result = fetcher()
        if self.cache and result:
            self.cache.set(key, result, CACHE_TTL.get(ttl_key, 3600))
        return result

    # ===== DNS 全量枚举 =====
    def query_dns_records(self, domain):
        """返回 {A:[], AAAA:[], MX:[], NS:[], TXT:[], CNAME:[], SOA:[]}"""
        results = {"A":[],"AAAA":[],"MX":[],"NS":[],"TXT":[],"CNAME":[],"SOA":[]}
        if not HAS_DNSPYTHON:
            try: results["A"]=[socket.gethostbyname(domain)]
            except: pass
            return results
        for rtype in results:
            try:
                answers = dns.resolver.resolve(domain, rtype)
                results[rtype] = [str(a) for a in answers]
            except: pass
        return results

    def reverse_ip_lookup(self, ip):
        try: return [socket.gethostbyaddr(ip)[0]]
        except: return []

    def reverse_ip_neighbors(self, ip, count=10):
        parts = ip.split(".")
        if len(parts) != 4: return []
        base, last = ".".join(parts[:3]), int(parts[3])
        return [f"{base}.{i}" for i in range(max(1,last-count), min(255,last+count)+1) if i!=last]

    # ===== 子域名枚举 =====
    def enumerate_subdomains(self, domain):
        subs = set()
        for r in self.query_crtsh(domain):
            subs.add(r["asset_value"])
        for sub in TOP_SUBDOMAIN_WORDLIST:
            subd = f"{sub}.{domain}"
            try: socket.gethostbyname(subd); subs.add(subd)
            except: pass
        return list(subs)

    # ===== 证书透明度 crt.sh =====
    def query_crtsh(self, domain):
        if not HAS_REQUESTS: return []
        try:
            url = API_ENDPOINTS["crtsh"].format(domain=domain)
            resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            data = resp.json()
            results, seen = [], set()
            for entry in data[:100]:
                name = entry.get("name_value","")
                for n in name.split("\n"):
                    n = n.strip().lstrip("*.")
                    if n and n not in seen and domain in n:
                        seen.add(n)
                        results.append({"asset_type":"subdomain","asset_name":n,"asset_value":n,
                            "source":"crt.sh","risk_level":"INFO"})
            return results
        except: return []

    # ===== WHOIS =====
    def query_whois(self, domain):
        result = None
        if HAS_WHOIS:
            try:
                w = whois_lib.whois(domain)
                result = {
                    "domain_name": w.domain_name or domain,
                    "registrar": w.registrar or "",
                    "creation_date": str(w.creation_date) if w.creation_date else "",
                    "expiration_date": str(w.expiration_date) if w.expiration_date else "",
                    "registrant_org": w.org or w.name or "",
                    "registrant_email": ",".join(w.emails) if w.emails else "",
                    "name_servers": ",".join(w.name_servers) if w.name_servers else "",
                }
            except: result = None
        if not result:
            # fallback: socket whois
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect(("whois.verisign-grs.com", 43))
                s.send(f"{domain}\r\n".encode())
                data = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk: break
                    data += chunk
                s.close()
                result = {"domain_name": domain, "raw_text": data.decode("utf-8","ignore")[:2000]}
            except:
                result = {"domain_name": domain}
        self._store_whois(domain, result)
        return result

    def _store_whois(self, domain, result):
        """将 WHOIS 结果落库 whois_records（供归属置信度评分复用）"""
        if not self.org_mgr or not result: return
        try:
            self.org_mgr.add_whois_record(
                domain_name=result.get("domain_name") or domain,
                registrar=result.get("registrar",""),
                creation_date=result.get("creation_date",""),
                expiration_date=result.get("expiration_date",""),
                registrant_org=result.get("registrant_org",""),
                registrant_email=result.get("registrant_email",""),
                name_servers=result.get("name_servers",""),
                raw_text=result.get("raw_text",""),
            )
        except: pass

    def query_whois_reverse(self, keyword, field="registrant_org"):
        """WHOIS反向搜索: 按注册人/邮箱匹配已知WHOIS记录"""
        if not self.org_mgr: return []
        try:
            with self.org_mgr._connect() as conn:
                rows = conn.execute(
                    f"SELECT * FROM whois_records WHERE {field} LIKE ? ORDER BY created_at DESC",
                    (f"%{keyword}%",)).fetchall()
            return [dict(r) for r in rows]
        except: return []

    # ===== ICP备案 =====
    def query_icp_by_company(self, company_name):
        if not self.org_mgr: return []
        try:
            with self.org_mgr._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM icp_records WHERE company_name LIKE ?",
                    (f"%{company_name}%",)).fetchall()
            return [dict(r) for r in rows]
        except: return []

    def query_icp_reverse(self, identifier):
        """ICP反查: 按法人/电话/邮箱匹配"""
        if not self.org_mgr: return []
        try:
            with self.org_mgr._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM icp_records WHERE company_name LIKE ? OR site_name LIKE ?",
                    (f"%{identifier}%", f"%{identifier}%")).fetchall()
            return [dict(r) for r in rows]
        except: return []

    # ===== SSL证书 =====
    def query_ssl_certificate(self, domain, port=443):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
                s.settimeout(5); s.connect((domain, port))
                cert = s.getpeercert()
                subject = dict(x[0] for x in cert.get("subject",[]))
                cn = subject.get("commonName","")
                sans = [x[1] for x in cert.get("subjectAltName",[])]
                return {"cn":cn,"sans":sans,
                    "issuer":dict(x[0] for x in cert.get("issuer",[])),
                    "not_before":cert.get("notBefore",""),
                    "not_after":cert.get("notAfter","")}
        except: return None

    # ===== BGP/ASN (BGPView.io 免费API) =====
    def query_asn_bgp(self, ip):
        if not HAS_REQUESTS: return {}
        try:
            url = API_ENDPOINTS["bgpview_ip"].format(ip=ip)
            resp = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json().get("data",{})
                prefixes = data.get("prefixes",[])
                if prefixes:
                    asn_data = prefixes[0].get("asn",{})
                    return {"ip_range":prefixes[0].get("prefix",""),
                        "asn_number":str(asn_data.get("asn","")),
                        "asn_name":asn_data.get("name",""),
                        "isp":asn_data.get("description",""),
                        "country":asn_data.get("country_code","")}
        except: pass
        return {}

    # ===== Shodan =====
    def query_shodan_ip(self, ip):
        key = API_KEYS.get("shodan","")
        if not key or not HAS_REQUESTS: return {}
        try:
            url = API_ENDPOINTS["shodan_host"].format(ip=ip, key=key)
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return {"ports":d.get("ports",[]),"org":d.get("org",""),
                    "isp":d.get("isp",""),"hostnames":d.get("hostnames",[]),
                    "os":d.get("os","")}
        except: pass
        return {}

    # ===== AlienVault OTX (免费无key) =====
    def query_otx_passive_dns(self, domain):
        if not HAS_REQUESTS: return []
        try:
            url = API_ENDPOINTS["alienvault_otx"].format(domain=domain)
            resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code == 200:
                entries = resp.json().get("passive_dns",[])
                results, seen = [], set()
                for e in entries[:50]:
                    hn = e.get("hostname","")
                    if hn and hn not in seen and domain in hn:
                        seen.add(hn)
                        results.append({"hostname":hn,"address":e.get("address",""),
                            "record_type":e.get("record_type",""),
                            "first":e.get("first",""),"last":e.get("last","")})
                return results
        except: pass
        return []

    # ===== SecurityTrails =====
    def query_securitytrails(self, domain):
        key = API_KEYS.get("securitytrails","")
        if not key or not HAS_REQUESTS: return {}
        try:
            url = API_ENDPOINTS["securitytrails_domain"].format(domain=domain)
            resp = requests.get(url, timeout=15, headers={"APIKEY":key,"User-Agent":"Mozilla/5.0"})
            if resp.status_code == 200: return resp.json()
        except: pass
        return {}

    # ===== GitHub API =====
    def query_github_search(self, query):
        if not HAS_REQUESTS: return []
        key = API_KEYS.get("github","")
        headers = {"Accept":"application/vnd.github.v3+json","User-Agent":"EASM-Scanner"}
        if key: headers["Authorization"] = f"token {key}"
        try:
            url = API_ENDPOINTS["github_search_code"].format(query=query)
            resp = requests.get(url, timeout=15, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get("items",[])
                return [{"name":i.get("name",""),"path":i.get("path",""),
                    "repo":i.get("repository",{}).get("full_name",""),
                    "url":i.get("html_url",""),"score":i.get("score",0)} for i in items[:20]]
        except: pass
        return []

    def query_github_by_email(self, email):
        return self.query_github_search(f"{email} in:email")

    # ===== Hunter.io 邮箱 =====
    def query_hunter_emails(self, domain):
        key = API_KEYS.get("hunter","")
        if not key or not HAS_REQUESTS: return []
        try:
            url = API_ENDPOINTS["hunter_domain"].format(domain=domain, key=key)
            resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            emails = (resp.json().get("data") or {}).get("emails") or []
            return [{"value": e.get("value",""), "type": e.get("type",""),
                     "confidence": e.get("confidence",0)} for e in emails[:20]]
        except: return []

    # ===== 空间测绘平台（FOFA/鹰图/QUAKE/Censys/ZoomEye） =====
    def query_fofa(self, query):
        key = API_KEYS.get("fofa","")
        if not key or not HAS_REQUESTS: return []
        try:
            qb64 = base64.b64encode(query.encode("utf-8")).decode("ascii")
            url = API_ENDPOINTS["fofa_search"].format(key=key, query_b64=qb64)
            resp = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            data = resp.json()
            results = []
            for row in (data.get("results") or [])[:50]:
                results.append({
                    "host": row[0] if len(row) > 0 else "",
                    "ip": row[1] if len(row) > 1 else "",
                    "port": row[2] if len(row) > 2 else "",
                    "protocol": row[3] if len(row) > 3 else "",
                    "title": row[4] if len(row) > 4 else "",
                    "domain": row[5] if len(row) > 5 else "",
                    "icp": row[6] if len(row) > 6 else "",
                })
            return results
        except: return []

    def query_quake(self, query):
        key = API_KEYS.get("quake","")
        if not key or not HAS_REQUESTS: return []
        try:
            url = API_ENDPOINTS["quake_search"]
            resp = requests.post(url, json={"query": query, "start": 0, "size": 50},
                headers={"X-QuakeToken": key, "Content-Type": "application/json"}, timeout=20)
            if resp.status_code != 200: return []
            data = (resp.json() or {}).get("data") or []
            results = []
            for d in data[:50]:
                svc = d.get("service") or {}
                results.append({
                    "ip": d.get("ip",""), "port": d.get("port",""),
                    "service": svc.get("name","") if isinstance(svc, dict) else "",
                    "hostname": d.get("hostname",""),
                    "title": (svc.get("http") or {}).get("title","") if isinstance(svc, dict) else "",
                })
            return results
        except: return []

    def query_hunter_qianxin(self, query):
        key = API_KEYS.get("qianxin_hunter","")
        if not key or not HAS_REQUESTS: return []
        try:
            qb64 = base64.b64encode(query.encode("utf-8")).decode("ascii")
            url = API_ENDPOINTS["qianxin_hunter_search"].format(key=key, query_b64=qb64)
            resp = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            arr = (resp.json().get("data") or {}).get("arr") or []
            return [{"ip": a.get("ip",""), "port": a.get("port",""),
                     "domain": a.get("domain",""), "title": a.get("web_title",""),
                     "company": a.get("company","")} for a in arr[:50]]
        except: return []

    def query_censys_search(self, query):
        cid = API_KEYS.get("censys_id",""); sec = API_KEYS.get("censys_secret","")
        if not cid or not sec or not HAS_REQUESTS: return []
        try:
            url = API_ENDPOINTS["censys_search"]
            resp = requests.post(url, json={"query": query, "per_page": 50},
                auth=(cid, sec), timeout=20)
            if resp.status_code != 200: return []
            hits = (resp.json().get("result") or {}).get("hits") or []
            return [{"ip": h.get("ip",""),
                     "services": [s.get("service_name","") for s in (h.get("services") or [])]}
                    for h in hits[:50]]
        except: return []

    def query_zoomeye_search(self, query):
        key = API_KEYS.get("zoomeye","")
        if not key or not HAS_REQUESTS: return []
        try:
            url = API_ENDPOINTS["zoomeye_search"].format(query=query)
            resp = requests.get(url, timeout=20, headers={"API-KEY": key, "User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            matches = resp.json().get("matches") or []
            results = []
            for m in matches[:50]:
                pi = m.get("portinfo") or {}
                results.append({"ip": m.get("ip",""),
                    "port": pi.get("port","") if isinstance(pi, dict) else "",
                    "title": pi.get("title","") if isinstance(pi, dict) else "",
                    "site": m.get("site","")})
            return results
        except: return []

    # ===== 代码仓库（Gitee/GitLab） =====
    def query_gitee_search(self, query):
        if not HAS_REQUESTS: return []
        try:
            url = API_ENDPOINTS["gitee_search"].format(query=query)
            resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            items = resp.json()
            if not isinstance(items, list): items = []
            return [{"name": i.get("name",""), "repo": i.get("full_name",""),
                     "url": i.get("html_url",""), "description": i.get("description","")}
                    for i in items[:20]]
        except: return []

    def query_gitlab_search(self, query):
        if not HAS_REQUESTS: return []
        key = API_KEYS.get("gitlab","")
        headers = {"User-Agent":"Mozilla/5.0"}
        if key: headers["PRIVATE-TOKEN"] = key
        try:
            url = API_ENDPOINTS["gitlab_search"].format(query=query)
            resp = requests.get(url, timeout=15, headers=headers)
            if resp.status_code != 200: return []
            items = resp.json()
            if not isinstance(items, list): items = []
            return [{"name": i.get("name",""), "repo": i.get("path_with_namespace",""),
                     "url": i.get("web_url",""), "description": i.get("description","")}
                    for i in items[:20]]
        except: return []

    # ===== Censys 证书（维度4：SSL证书透明度） =====
    def query_censys_cert(self, domain):
        cid = API_KEYS.get("censys_id",""); sec = API_KEYS.get("censys_secret","")
        if not cid or not sec or not HAS_REQUESTS: return []
        try:
            resp = requests.post("https://search.censys.io/api/v2/certificates/search",
                json={"query": f"parsed.names:{domain}", "per_page": 50},
                auth=(cid, sec), timeout=20)
            if resp.status_code != 200: return []
            hits = (resp.json().get("result") or {}).get("hits") or []
            results, seen = [], set()
            for h in hits[:50]:
                names = (h.get("parsed") or {}).get("names") or []
                for n in names:
                    n = (n or "").strip().lstrip("*.")
                    if n and domain in n and n not in seen:
                        seen.add(n)
                        results.append({"asset_type":"subdomain","asset_name":n,
                            "asset_value":n,"source":"Censys证书","risk_level":"INFO"})
            return results
        except: return []

    # ===== CertSpotter 证书透明（免费无 key API，best-effort） =====
    def query_certspotter(self, domain):
        if not domain or not HAS_REQUESTS: return []
        try:
            url = ("https://sslmate.com/certspotter/api/v1/issuances"
                   f"?domain={domain}&include_subdomains=true&expand=dns_names&match_wildcards=true")
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200: return []
            results, seen = [], set()
            for item in (resp.json() or [])[:50]:
                for n in (item.get("dns_names") or []):
                    n = (n or "").strip().lstrip("*.")
                    if n and n not in seen and domain in n:
                        seen.add(n)
                        results.append({"asset_type": "subdomain", "asset_name": n,
                                        "asset_value": n, "source": "CertSpotter", "risk_level": "INFO"})
            return results
        except: return []

    # ===== 敏感目录/文件本地探测（维度5） =====
    def probe_sensitive_paths(self, domain):
        if not domain or not HAS_REQUESTS: return []
        results = []
        base = f"https://{domain}"
        for path in SENSITIVE_PATHS:
            url = base + path
            try:
                resp = requests.get(url, timeout=6, allow_redirects=False,
                    headers={"User-Agent":"Mozilla/5.0"})
                if resp.status_code < 500:
                    results.append({"path": path, "url": url, "status": resp.status_code})
            except: pass
        return results

    # ===== 搜索 URL 结果探测（best-effort，反爬时标注无法确认） =====
    def probe_search_result(self, url, keyword=None):
        if not url or not HAS_REQUESTS: return None
        if not url.startswith(("http://","https://")): return None
        uncertain = None
        try:
            resp = requests.get(url, timeout=6, allow_redirects=True,
                headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"})
            st = resp.status_code
            if st in (401, 403):
                uncertain = f"搜索结果：无法确认（HTTP {st}，站点反爬/需登录）"
            elif st == 404:
                return "搜索结果：0（HTTP 404）"
            elif st != 200:
                return f"搜索结果：无法访问（HTTP {st}）"
            else:
                body = resp.text
                cnt = self._parse_result_count(body)
                if cnt is not None:
                    return f"搜索结果：{cnt}条"
                if keyword and keyword in body:
                    uncertain = "搜索结果：≥1条（含目标名称，数量未解析）"
                else:
                    uncertain = "搜索结果：无法确认（已访问，需人工核验）"
        except Exception:
            uncertain = "搜索结果：无法访问（请求失败）"
        # 静态抓取无法确定数量 → 用无头浏览器渲染精确计数
        bc = self._browser_count(url, keyword)
        if bc is not None:
            cnt, exact = bc
            return f"搜索结果：{cnt}条" if exact else f"搜索结果：约{cnt}条"
        return uncertain or "搜索结果：无法确认"

    # ===== 无头浏览器精确计数（可选，需 playwright + chromium） =====
    def _browser_count(self, url, keyword):
        if not ENABLE_BROWSER_PROBE:
            return None
        try:
            from core.browser_probe import BrowserProbe
            return BrowserProbe(timeout_ms=BROWSER_PROBE_TIMEOUT * 1000).count_results(url, keyword)
        except Exception:
            return None

    @staticmethod
    def _parse_result_count(body):
        if not body: return None
        import re
        for p in (r'找到相关结果约\s*([\d,]+)\s*个',
                  r'为您找到相关结果约\s*([\d,]+)\s*个',
                  r'约\s*([\d,]+)\s*(?:个|条|篇)\s*(?:相关)?结果',
                  r'共\s*([\d,]+)\s*(?:个|条|篇)',
                  r'([\d,]+)\s*(?:个|条|篇)\s*结果',
                  r'相关文档\s*([\d,]+)\s*篇',
                  r'找到\s*([\d,]+)\s*篇'):
            m = re.search(p, body)
            if m:
                return m.group(1).replace(",", "")
        return None

    # ===== ICP 备案在线查询（best-effort 抓取公开查询页；结果不可靠，需人工核验） =====
    def query_icp_online(self, domain):
        if not domain or not HAS_REQUESTS: return {}
        try:
            from bs4 import BeautifulSoup
            import re
            url = API_ENDPOINTS["icp_lookup"].format(domain=domain)
            resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return {}
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(" ", strip=True)
            # 必须同时命中「主办单位」，否则判定无备案信息并返回空，
            # 避免误抓页面“猜你喜欢/推荐”等无关区域的备案号。
            cm = re.search(r'(主办单位|单位名称|主办者名称)[：:]\s*([^\s|]{2,40})', text)
            if not cm:
                return {}
            company = cm.group(2).strip()
            m = re.search(r'([京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼]ICP[备证]?\d{6,10}号?)', text)
            if not m:
                return {}
            return {"domain_name": domain, "icp_number": m.group(1),
                    "company_name": company, "source": "icp.chinaz.com"}
        except: return {}

    # ===== HTTP指纹 =====
    def fetch_site_fingerprint(self, url):
        if not url.startswith(("http://","https://")): url = f"https://{url}"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"},
                allow_redirects=True)
            headers = dict(resp.headers)
            body = resp.text[:5000]
            title = ""
            if "<title>" in body:
                s = body.index("<title>")+7; e = body.index("</title>",s)
                title = body[s:e].strip()
            favicon_hash = ""
            try:
                fr = requests.get(f"{resp.url.rstrip('/')}/favicon.ico", timeout=5)
                if fr.status_code == 200: favicon_hash = hashlib.md5(fr.content).hexdigest()
            except: pass
            return {"url":resp.url,"title":title,"status_code":resp.status_code,
                "headers":json.dumps(headers,ensure_ascii=False),
                "favicon_hash":favicon_hash,
                "tech_stack":json.dumps(self.detect_technologies(headers,body),ensure_ascii=False)}
        except: return None

    def detect_technologies(self, headers, body):
        techs = []
        srv = headers.get("Server","").lower()
        pw = headers.get("X-Powered-By","").lower()
        gen = headers.get("X-Generator","").lower()
        b = (body or "").lower()
        if "apache" in srv: techs.append("Apache")
        if "nginx" in srv: techs.append("Nginx")
        if "iis" in srv: techs.append("IIS")
        if "php" in pw: techs.append("PHP")
        if "asp.net" in pw: techs.append("ASP.NET")
        if "wordpress" in gen: techs.append("WordPress")
        if "wp-content" in b: techs.append("WordPress")
        if "jquery" in b: techs.append("jQuery")
        if "bootstrap" in b: techs.append("Bootstrap")
        if "jira" in b: techs.append("Jira")
        if "confluence" in b: techs.append("Confluence")
        if "grafana" in b: techs.append("Grafana")
        if "jenkins" in b: techs.append("Jenkins")
        return techs

    # ===== 云存储探测 =====
    def check_cloud_bucket(self, org_name, domain=""):
        results = []
        names = set()
        for n in [org_name, domain.split(".")[0] if domain else ""]:
            if n: names.add(n.replace(" ","").lower()[:20])
        patterns = [
            ("{name}.oss-{region}.aliyuncs.com","阿里云OSS"),
            ("{name}.cos.{region}.myqcloud.com","腾讯云COS"),
            ("{name}.blob.core.windows.net","Azure Blob"),
            ("{name}.s3.amazonaws.com","AWS S3"),
        ]
        regions = ["beijing","shanghai","guangzhou","hongkong","singapore","tokyo","ap-southeast-1"]
        for name in names:
            for pat, prov in patterns:
                for region in regions:
                    bucket = pat.replace("{name}",name).replace("{region}",region)
                    try:
                        resp = requests.head(f"https://{bucket}", timeout=5)
                        if resp.status_code < 500:
                            results.append({"asset_type":"cloud","asset_name":prov,
                                "asset_value":bucket,"source":"云探测",
                                "risk_level":"HIGH" if resp.status_code<400 else "MEDIUM",
                                "detail":f"{prov}可能公开 (HTTP {resp.status_code})"})
                    except: pass
        return results

    # ===== 12类标识符发散搜索 =====
    def search_all_identifiers(self, profile_data, domain=""):
        """根据企业档案的12类标识符发散搜索"""
        import json as _json
        all_results = []
        # 名称类 → 搜索词集合
        search_terms = set()
        for k in ["full_name","short_name"]:
            v = profile_data.get(k,"")
            if v: search_terms.add(v)
        former = profile_data.get("former_names","")
        if isinstance(former, str):
            try: former = _json.loads(former)
            except: former = [former] if former else []
        for n in (former or []): search_terms.add(str(n))
        # 邮箱 → WHOIS反查 + GitHub
        emails = profile_data.get("emails","")
        if isinstance(emails, str):
            try: emails = _json.loads(emails)
            except: emails = [emails] if "@" in str(emails) else []
        for email in (emails or [])[:5]:
            all_results.extend(self.query_github_by_email(str(email)))
            for wr in self.query_whois_reverse(str(email),"registrant_email"):
                all_results.append({"asset_type":"domain","asset_name":wr["domain_name"],
                    "asset_value":wr["domain_name"],"source":"WHOIS反查-邮箱","risk_level":"MEDIUM"})
        # 电话 → ICP反查
        phones = profile_data.get("phones","")
        if isinstance(phones, str):
            try: phones = _json.loads(phones)
            except: phones = [phones] if phones else []
        for phone in (phones or [])[:5]:
            for ir in self.query_icp_reverse(str(phone)):
                all_results.append({"asset_type":"domain","asset_name":ir["domain_name"],
                    "asset_value":ir["domain_name"],"source":"ICP反查-电话","risk_level":"MEDIUM"})
        self._log(f"[Enrichment] 标识符发散: {len(search_terms)}词, 交叉发现{len(all_results)}条")
        return all_results