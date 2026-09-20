"""
知识库真实数据加载：CVE 库 + 历史报告。

自包含：从 vendor/cve_database.db 按 cve_id 查询描述灌入 kb.store（kind="cve"），
从 reports/*.html 抽取标题/正文片段灌入（kind="attack_case"）。按 entry_id 去重，
避免重复灌入；仅在需要时加载（按需，非全量 33 万条）。
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import List, Optional

_VENDOR_DB = Path(__file__).resolve().parent.parent.parent / "vendor" / "cve_database.db"
_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"


def load_cves(kb, cve_ids: List[str]) -> int:
    """从 vendor/cve_database.db 按 cve_id 批量查询描述，灌入 kb.store（kind="cve"）。

    过滤掉非 CVE 的 FINDING:* 前缀；按 entry_id="cve-<id>" 去重。返回新增条数。
    """
    ids = [c for c in (cve_ids or []) if c and not str(c).startswith("FINDING:")]
    if not ids:
        return 0
    try:
        con = sqlite3.connect(str(_VENDOR_DB))
        try:
            rows = []
            # 分块查询：SQLite 变量上限约 999，超过则静默失败；每 500 条一批。
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                placeholders = ",".join("?" for _ in chunk)
                rows.extend(con.execute(
                    f"SELECT cve_id, description, severity, cwe FROM cve_database "
                    f"WHERE cve_id IN ({placeholders})", chunk).fetchall())
        finally:
            con.close()
    except Exception:
        return 0
    loaded = 0
    for cve_id, desc, severity, cwe in rows:
        eid = f"cve-{cve_id}"
        if kb.store.get(eid) is not None:
            continue
        kb.store.add("cve", cve_id, desc or "",
                     {"severity": severity or "", "cwe": cwe or ""}, entry_id=eid)
        loaded += 1
    return loaded


def load_reports(kb, reports_dir: Optional[str] = None) -> int:
    """从 reports/*.html 抽取标题与正文片段，灌入 kb.store（kind="attack_case"）。"""
    reports_dir = Path(reports_dir or _REPORTS_DIR)
    if not reports_dir.exists():
        return 0
    loaded = 0
    for p in sorted(reports_dir.glob("*.html")):
        eid = f"report-{p.name}"
        if kb.store.get(eid) is not None:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        title = _extract_title(text) or p.name
        snippet = _strip_html(text)[:500]
        if snippet:
            kb.store.add("attack_case", f"历史报告：{title}", snippet,
                         {"report": p.name}, entry_id=eid)
            loaded += 1
    return loaded


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"&[a-zA-Z#0-9]+;", " ", html)
    return re.sub(r"\s+", " ", html).strip()
