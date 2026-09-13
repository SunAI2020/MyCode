# -*- coding: utf-8 -*-
"""数据泄露检测 — 凭证/架构文档/源码暴露 正则模式匹配"""
import os, sys, re
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import LEAK_PATTERNS

class LeakDetector:
    """基于正则模式 + GitHub API的数据泄露检测"""

    def __init__(self, org_manager=None, enrichment_engine=None):
        self.org_mgr = org_manager
        self.enrichment = enrichment_engine
        self._log_cb = None

    def set_callbacks(self, log_cb=None):
        self._log_cb = log_cb
    def _log(self, msg):
        if self._log_cb: self._log_cb(msg)

    def scan_text(self, text, org_name=""):
        """对文本进行全模式匹配"""
        findings = []
        for category, patterns in LEAK_PATTERNS.items():
            for pname, pre in patterns.items():
                try:
                    for m in re.finditer(pre, text, re.IGNORECASE):
                        snippet = m.group(0)
                        if len(snippet) > 120: snippet = snippet[:120] + "..."
                        findings.append({
                            "leak_category": category, "leak_pattern": pname,
                            "matched_content_snippet": snippet,
                            "confidence": self._confidence(pname),
                            "severity": self._severity(pname),
                        })
                except: pass
        seen = set(); unique = []
        for f in findings:
            k = (f["leak_pattern"], f["matched_content_snippet"][:60])
            if k not in seen: seen.add(k); unique.append(f)
        return unique

    def _confidence(self, pname):
        h = {"private_key","aws_key","jwt_token","db_connection","connection_string"}
        m = {"api_key","password_assignment","config_file","backup_file"}
        if pname in h: return 0.90
        if pname in m: return 0.75
        return 0.60

    def _severity(self, pname):
        c = {"private_key","aws_key","db_connection","connection_string","db_account","password_assignment"}
        h = {"api_key","jwt_token","config_file","backup_file"}
        if pname in c: return "CRITICAL"
        if pname in h: return "HIGH"
        return "MEDIUM"

    def scan_github_code(self, org_name, domain=""):
        """GitHub API搜索代码泄露"""
        findings = []
        queries = [
            f'"{org_name}" password OR secret OR api_key OR token',
            f'"{org_name}" connectionString OR jdbc OR mongodb',
            f'"{org_name}" config.php OR .env OR settings.py OR web.config',
        ]
        if domain:
            queries.append(f'"{domain}" password OR secret')
        if self.enrichment:
            for q in queries[:3]:
                results = self.enrichment.query_github_search(q)
                for r in results:
                    findings.append({
                        "leak_category":"credential","leak_pattern":"github_code_search",
                        "matched_content_snippet":f"{r['repo']}/{r['path']}",
                        "source_url":r.get("url",""),"confidence":0.6,"severity":"HIGH",
                    })
                if results: self._log(f"  [GitHub] '{q[:40]}...' -> {len(results)}条")
        return findings

    def scan_for_leaked_urls(self, org_name, domain=""):
        """搜索泄露的内部URL"""
        findings = []
        if not domain or not self.enrichment: return findings
        for kw in ["admin","internal","test","dev","staging","backup","db","api"]:
            results = self.enrichment.query_github_search(f'"{kw}.{domain}"')
            for r in results:
                findings.append({
                    "leak_category":"architecture","leak_pattern":"internal_url_exposure",
                    "matched_content_snippet":f"{r['repo']}/{r['path']}: {kw}.{domain}",
                    "source_url":r.get("url",""),"confidence":0.7,"severity":"MEDIUM",
                })
        return findings

    def scan_document_content(self, doc_text, source_url=""):
        """扫描文档文本"""
        findings = self.scan_text(doc_text)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for f in findings:
            f["source_url"] = source_url; f["discovered_at"] = now
        return findings

    def full_leak_scan(self, org_name, domain="", org_id=None):
        """全面泄露扫描 + 入库"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_findings = []
        for f in self.scan_github_code(org_name, domain):
            f.update({"org_id":org_id,"discovered_at":now}); all_findings.append(f)
        for f in self.scan_for_leaked_urls(org_name, domain):
            f.update({"org_id":org_id,"discovered_at":now}); all_findings.append(f)
        if self.org_mgr and org_id:
            for f in all_findings:
                self.org_mgr.add_leak_evidence(
                    org_id=org_id, leak_category=f.get("leak_category",""),
                    leak_pattern=f.get("leak_pattern",""),
                    matched_content_snippet=f.get("matched_content_snippet",""),
                    source_url=f.get("source_url",""),
                    confidence=f.get("confidence",0.5), severity=f.get("severity","HIGH"))
            self._log(f"[LeakDetector] {len(all_findings)}条泄露证据已入库")
        return all_findings