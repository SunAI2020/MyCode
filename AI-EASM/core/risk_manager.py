# -*- coding: utf-8 -*-
"""风险评估管理 - CVE漏洞匹配"""
import os, sqlite3
from config.settings import CVE_DB_PATH

class RiskManager:
    def __init__(self):
        self.cve_db_path = CVE_DB_PATH
    def _connect_cve(self):
        if not os.path.exists(self.cve_db_path): return None
        conn = sqlite3.connect(self.cve_db_path)
        conn.row_factory = sqlite3.Row
        return conn
    def search_cve(self, service=None, product=None, version=None, limit=20):
        conn = self._connect_cve()
        if not conn: return []
        sql = "SELECT * FROM cve_database WHERE 1=1"
        params = []
        if product:
            sql += " AND (affected_products LIKE ? OR name LIKE ?)"
            params.extend([f"%{product}%", f"%{product}%"])
        if service:
            sql += " AND (affected_products LIKE ? OR description LIKE ?)"
            params.extend([f"%{service}%", f"%{service}%"])
        sql += " ORDER BY cvss_score DESC LIMIT ?"
        params.append(limit)
        try:
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return rows
        except:
            conn.close()
            return []
    def match_vulnerabilities(self, services):
        results = []
        for svc in services:
            cves = self.search_cve(service=svc.get("service",""), product=svc.get("product",""), limit=5)
            for cve in cves:
                results.append({
                    "host": svc.get("host",""), "port": svc.get("port",0),
                    "service": svc.get("service",""),
                    "cve_id": cve["cve_id"], "name": cve["name"] or "",
                    "cvss_score": cve["cvss_score"] or 0,
                    "severity": cve["severity"] or "INFO",
                    "description": (cve["description"] or "")[:200]
                })
        return sorted(results, key=lambda x: x["cvss_score"], reverse=True)
    def get_cve_detail(self, cve_id):
        conn = self._connect_cve()
        if not conn: return None
        row = conn.execute("SELECT * FROM cve_database WHERE cve_id=?", (cve_id,)).fetchone()
        conn.close()
        return row
    def get_cve_stats(self):
        conn = self._connect_cve()
        if not conn: return {"total":0,"critical":0,"high":0,"medium":0,"low":0}
        rows = conn.execute("""SELECT severity, COUNT(*) as cnt FROM cve_database
            WHERE severity IN ("CRITICAL","HIGH","MEDIUM","LOW") GROUP BY severity""").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM cve_database").fetchone()[0]
        conn.close()
        stats = {"total":total,"critical":0,"high":0,"medium":0,"low":0}
        for r in rows: stats[r["severity"].lower()] = r["cnt"]
        return stats
