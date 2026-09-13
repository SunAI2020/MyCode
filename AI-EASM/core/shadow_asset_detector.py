# -*- coding: utf-8 -*-
"""影子资产检测 — 证书SAN聚类/IP段聚合/MX-NS关联/Favicon匹配"""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ShadowAssetDetector:
    """多维度聚类发现影子资产"""

    def __init__(self, org_manager=None):
        self.org_mgr = org_manager
        self._log_cb = None
    def set_callbacks(self, log_cb=None):
        self._log_cb = log_cb
    def _log(self, msg):
        if self._log_cb: self._log_cb(msg)

    def detect_shadow_assets(self, known_domains, discovered_assets):
        """对比已知清单，识别影子资产"""
        known = set((d or "").lower().strip() for d in known_domains)
        shadows = []
        for a in discovered_assets:
            av = (a.get("asset_value") or a.get("asset_name","")).lower().strip()
            if av and av not in known:
                if self._is_related(av, known):
                    a["asset_category"] = "shadow"
                    a["shadow_risk"] = self._shadow_risk(a)
                    shadows.append(a)
        self._log(f"[Shadow] {len(shadows)}疑似影子资产 (已知{len(known)}个)")
        return shadows

    def _is_related(self, val, known):
        for k in known:
            if k and len(k)>3 and (k in val or val in k): return True
            if self._sim(val[:15], k[:15]) > 0.6: return True
        return False

    def _sim(self, a, b):
        if not a or not b: return 0
        m, n = len(a), len(b)
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(m+1): dp[i][0] = i
        for j in range(n+1): dp[0][j] = j
        for i in range(1,m+1):
            for j in range(1,n+1):
                dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1,
                    dp[i-1][j-1]+(0 if a[i-1]==b[j-1] else 1))
        return 1 - dp[m][n] / max(m,n)

    def _shadow_risk(self, a):
        r = 0
        if a.get("asset_type") in ("domain","subdomain"): r += 2
        if a.get("risk_level") in ("HIGH","CRITICAL"): r += 3
        if a.get("confidence",0) > 0.6: r += 2
        return min(r, 10)

    def cert_san_clustering(self, certificates):
        """SSL证书SAN条目聚类"""
        clusters = defaultdict(set)
        for cert in certificates:
            domains = list(cert.get("sans",[]))
            cn = cert.get("cn","")
            if cn: domains.append(cn)
            for d1 in domains:
                for d2 in domains:
                    if d1 != d2: clusters[d1].add(d2); clusters[d2].add(d1)
        return {k: list(v) for k,v in clusters.items() if len(v)>1}

    def ip_range_clustering(self, ips):
        """同/24网段IP聚合"""
        groups = defaultdict(list)
        for ip in ips:
            p = str(ip).split(".")
            if len(p)==4: groups[".".join(p[:3])+".0/24"].append(ip)
        return {k:v for k,v in groups.items() if len(v)>1}

    def mx_ns_correlation(self, dns_list):
        """共享MX/NS域名关联"""
        mx_g, ns_g = defaultdict(set), defaultdict(set)
        for r in dns_list:
            domain = r.get("domain","")
            for mx in r.get("MX",[]): mx_g[str(mx)].add(domain)
            for ns in r.get("NS",[]): ns_g[str(ns)].add(domain)
        results = {}
        for label, g in [("MX",mx_g),("NS",ns_g)]:
            for srv, domains in g.items():
                if len(domains)>1: results[f"{label}:{srv}"] = list(domains)
        return results

    def favicon_hash_correlation(self, fingerprints):
        """相同favicon hash关联"""
        groups = defaultdict(list)
        for fp in fingerprints:
            fh = fp.get("favicon_hash",""); d = fp.get("domain","")
            if fh and d: groups[fh].append(d)
        return {k:v for k,v in groups.items() if len(v)>1}

    def comprehensive_detection(self, known_domains, assets, certs, fingerprints):
        """5维度综合影子资产检测"""
        signals = {}
        # D1: 已知清单对比
        for s in self.detect_shadow_assets(known_domains, assets):
            signals[s.get("asset_value","")] = signals.get(s.get("asset_value",""),0) + 1
        # D2: 证书SAN聚类
        for cluster in self.cert_san_clustering(certs).values():
            for d in [x for x in cluster if x not in known_domains]:
                signals[d] = signals.get(d,0) + 1
        # D3: IP段聚合
        ips = [a.get("asset_value","") for a in assets if a.get("asset_type")=="ip"]
        self.ip_range_clustering(ips)
        # D4: Favicon关联
        for cluster in self.favicon_hash_correlation(fingerprints).values():
            for d in [x for x in cluster if x not in known_domains]:
                signals[d] = signals.get(d,0) + 1
        # 汇总: 3+信号=高置信
        results = []
        for key, cnt in signals.items():
            conf = "HIGH" if cnt>=3 else ("MEDIUM" if cnt>=2 else "LOW")
            results.append({"asset":key,"signal_count":cnt,"confidence":conf})
        results.sort(key=lambda x: -x["signal_count"])
        self._log(f"[Shadow] 综合: {len(results)}个 ({sum(1 for r in results if r['confidence']=='HIGH')}高置信)")
        return results