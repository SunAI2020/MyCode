"""
CTEM 修复验证：记录基线扫描 → 整改后重扫 → 对比，输出「路径已闭合 / 仍可利用 / 新增」。

自包含：不 import 其它 core 模块，可被 GUI / report_builder 单向引用。
基线快照存 SQLite（data/ctem.db），字段 target / scan_time / vulns_json。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ctem.db"


def vuln_fingerprint(vuln: Dict) -> Tuple[str, str, str]:
    """漏洞唯一指纹 (host, port, cve_id)，用于跨扫描对比。

    FINDING: 类型（无 CVE 编号）用 finding_type 补足 cve_id 位，保证可辨识。
    """
    host = str(vuln.get("host") or "")
    port = str(vuln.get("port") or "")
    cid = str(vuln.get("cve_id") or "")
    if not cid and vuln.get("finding_type"):
        cid = f"FINDING:{vuln.get('finding_type')}"
    return (host, port, cid)


def diff_scans(previous: List[Dict], current: List[Dict]) -> Dict[str, List[Dict]]:
    """对比两次扫描的漏洞集。

    Returns:
        {"closed": 基线有、复测无（已闭合/路径已闭合）,
         "still_open": 基线有、复测仍有（仍可利用）,
         "new": 复测新增}
    """
    prev_by_key = {vuln_fingerprint(v): v for v in (previous or []) if isinstance(v, dict)}
    curr_by_key = {vuln_fingerprint(v): v for v in (current or []) if isinstance(v, dict)}
    prev_set = set(prev_by_key)
    curr_set = set(curr_by_key)
    return {
        "closed": [prev_by_key[k] for k in (prev_set - curr_set)],
        "still_open": [curr_by_key[k] for k in (prev_set & curr_set)],
        "new": [curr_by_key[k] for k in (curr_set - prev_set)],
    }


class CtemStore:
    """CTEM 基线快照存储。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or _DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS ctem_baselines ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "target TEXT NOT NULL,"
                "scan_time TEXT NOT NULL,"
                "vulns_json TEXT NOT NULL)"
            )

    def save_baseline(self, target: str, vulns: List[Dict]) -> int:
        """保存一次扫描为基线，返回基线 id。"""
        payload = json.dumps(vulns or [], ensure_ascii=False, default=str)
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO ctem_baselines (target, scan_time, vulns_json) VALUES (?, ?, ?)",
                (target, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), payload))
            return cur.lastrowid

    def latest_baseline(self, target: str) -> Optional[Dict]:
        """取某目标最近一次基线，返回 {id, target, scan_time, vulns}；无则 None。"""
        with self._connect() as con:
            row = con.execute(
                "SELECT id, target, scan_time, vulns_json FROM ctem_baselines "
                "WHERE target=? ORDER BY id DESC LIMIT 1", (target,)).fetchone()
        if not row:
            return None
        try:
            vulns = json.loads(row["vulns_json"])
        except Exception:  # noqa: BLE001
            vulns = []
        return {"id": row["id"], "target": row["target"],
                "scan_time": row["scan_time"], "vulns": vulns}

    def targets(self) -> List[str]:
        """返回所有存过基线的不重复目标。"""
        with self._connect() as con:
            rows = con.execute(
                "SELECT DISTINCT target FROM ctem_baselines ORDER BY target").fetchall()
        return [r["target"] for r in rows]


def run_ctem_compare(store: CtemStore, target: str,
                     current_vulns: List[Dict], save_as_new: bool = False) -> Dict:
    """复测对比主流程：取最近基线 diff 当前漏洞，可选把当前结果存为新基线。

    Returns:
        {"has_baseline": bool, "baseline_time": str, "diff": {closed, still_open, new}}
    """
    base = store.latest_baseline(target)
    if base is None:
        # 无基线：仅当显式 save_as_new 时才建基线（如用户主动点「复测对比」），
        # 否则（如导出报告）不落库，避免产生未预期的基线副作用。
        if save_as_new:
            store.save_baseline(target, current_vulns)
        return {"has_baseline": False, "baseline_time": "", "diff": None}
    diff = diff_scans(base["vulns"], current_vulns)
    if save_as_new:
        store.save_baseline(target, current_vulns)
    return {"has_baseline": True, "baseline_time": base["scan_time"], "diff": diff}
