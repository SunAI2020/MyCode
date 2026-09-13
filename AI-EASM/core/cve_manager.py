# -*- coding: utf-8 -*-
"""CVE 数据库管理 — 从 NVD 全网抓取最近 X 天 CVE，按 cve_id 去重后导入"""
import os, sys, sqlite3, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import CVE_DB_PATH
try:
    import requests; HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"


class CVEManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or CVE_DB_PATH

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = self._connect()
        try:
            conn.execute('''CREATE TABLE IF NOT EXISTS cve_database (
                id INTEGER PRIMARY KEY AUTOINCREMENT, cve_id TEXT,
                name TEXT, description TEXT, cvss_score REAL, severity TEXT,
                published_date TEXT, modified_date TEXT, affected_products TEXT,
                references_url TEXT, ai_analysis TEXT, exploit_available INTEGER,
                created_at TEXT, cwe TEXT, patch_link TEXT
            )''')
            conn.commit()
        finally:
            conn.close()

    # ===== NVD 抓取 =====
    def fetch_recent_cves(self, days, api_key="", log_cb=None):
        """抓取最近 days 天发布的 CVE 记录列表。"""
        if not HAS_REQUESTS:
            return []
        self._ensure_schema()
        end = datetime.utcnow()
        start = end - timedelta(days=int(days))
        headers = {"User-Agent": "AI-EASM/1.0"}
        if api_key:
            headers["apiKey"] = api_key
        params = {
            "pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "pubEndDate": end.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "resultsPerPage": 2000,
        }
        records = []
        start_index = 0
        page = 0
        while True:
            params["startIndex"] = start_index
            try:
                resp = requests.get(NVD_API, params=params, headers=headers, timeout=60)
                if resp.status_code != 200:
                    if log_cb: log_cb(f"[NVD] HTTP {resp.status_code}，停止抓取")
                    break
                data = resp.json()
            except Exception as e:
                if log_cb: log_cb(f"[NVD] 请求失败: {e}")
                break
            vulns = data.get("vulnerabilities") or []
            for v in vulns:
                records.append(self._parse_cve(v.get("cve", {})))
            total = data.get("totalResults", 0)
            start_index += len(vulns)
            page += 1
            if log_cb: log_cb(f"[NVD] 第{page}页 {len(vulns)}条 (累计{len(records)}/{total})")
            if start_index >= total or not vulns:
                break
            time.sleep(6)  # 无 key 时限速 5 次/30s，翻页间隔
        return records

    @staticmethod
    def _parse_cve(cve):
        desc = ""
        for d in (cve.get("descriptions") or []):
            if d.get("lang") == "en":
                desc = d.get("value", ""); break
        score, severity = None, ""
        metrics = cve.get("metrics") or {}
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV40", "cvssMetricV2"):
            for m in (metrics.get(key) or []):
                cd = m.get("cvssData") or {}
                if cd.get("baseScore") is not None:
                    score = cd["baseScore"]
                    severity = (cd.get("baseSeverity") or "").upper()
                    break
            if score is not None: break
        cwe = ""
        for w in (cve.get("weaknesses") or []):
            for d in (w.get("description") or []):
                if d.get("value", "").startswith("CWE-"):
                    cwe = d["value"]; break
            if cwe: break
        products = []
        for conf in (cve.get("configurations") or []):
            for node in (conf.get("nodes") or []):
                for cm in (node.get("cpeMatch") or []):
                    crit = cm.get("criteria", "")
                    parts = crit.split(":")
                    if crit.startswith("cpe:2.3:") and len(parts) >= 5:
                        products.append(f"{parts[3]}:{parts[4]}")
        affected = ",".join(sorted(set(products))[:20])
        refs = [r.get("url", "") for r in (cve.get("references") or []) if r.get("url")]
        return {
            "cve_id": cve.get("id", ""),
            "name": "",
            "description": desc,
            "cvss_score": score,
            "severity": severity or "UNKNOWN",
            "published_date": (cve.get("published") or "")[:19].replace("T", " "),
            "modified_date": (cve.get("lastModified") or "")[:19].replace("T", " "),
            "affected_products": affected,
            "references_url": ",".join(refs[:10]),
            "cwe": cwe,
            "exploit_available": 0,
            "ai_analysis": "",
            "patch_link": "",
        }

    # ===== 去重导入 =====
    def import_cves(self, records):
        """按 cve_id 去重后批量导入，返回 (新增数, 重复跳过数)。"""
        if not records:
            return 0, 0
        self._ensure_schema()
        conn = self._connect()
        try:
            existing = set(r["cve_id"] for r in conn.execute("SELECT cve_id FROM cve_database").fetchall())
            added, dup = 0, 0
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for r in records:
                cid = r.get("cve_id", "")
                if not cid or cid in existing:
                    dup += 1; continue
                conn.execute('''INSERT INTO cve_database
                    (cve_id,name,description,cvss_score,severity,published_date,modified_date,
                     affected_products,references_url,ai_analysis,exploit_available,created_at,cwe,patch_link)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (cid, r.get("name", ""), r.get("description", ""), r.get("cvss_score"),
                     r.get("severity", ""), r.get("published_date", ""), r.get("modified_date", ""),
                     r.get("affected_products", ""), r.get("references_url", ""), r.get("ai_analysis", ""),
                     r.get("exploit_available", 0), now, r.get("cwe", ""), r.get("patch_link", "")))
                existing.add(cid); added += 1
            conn.commit()
            return added, dup
        finally:
            conn.close()

    # ===== 统计 =====
    def get_stats(self):
        self._ensure_schema()
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM cve_database").fetchone()[0]
            rows = conn.execute("SELECT severity, COUNT(*) c FROM cve_database WHERE severity IN ('CRITICAL','HIGH','MEDIUM','LOW') GROUP BY severity").fetchall()
        finally:
            conn.close()
        stats = {"total": total, "critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in rows:
            stats[r["severity"].lower()] = r["c"]
        return stats

    def latest_published_date(self):
        self._ensure_schema()
        conn = self._connect()
        try:
            row = conn.execute("SELECT MAX(published_date) m FROM cve_database").fetchone()
        finally:
            conn.close()
        return row["m"] or ""
