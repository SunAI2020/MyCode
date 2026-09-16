# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 六大数据库模块"""
import sqlite3
import os
import sys
import json
import logging
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    # PyInstaller 打包后：将可写数据（数据库/临时目录）定位到 EXE 同目录，
    # 避免写入 _internal（只读资源目录）导致数据丢失或更新失效。
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 将运行时资源重定向到D盘，避免C盘满导致 "database or disk is full"
# ============================================================
_APP_TEMP_DIR = os.path.join(BASE_DIR, 'temp')
os.makedirs(_APP_TEMP_DIR, exist_ok=True)

# SQLite 临时目录 → 应用temp目录
os.environ['SQLITE_TMPDIR'] = _APP_TEMP_DIR
# Python 临时目录 → 应用temp目录（仅影响tempfile模块，不污染进程环境变量）
tempfile.tempdir = _APP_TEMP_DIR

logger.info(f"运行时临时目录: {_APP_TEMP_DIR}")


def _connect(db_name):
    """创建数据库连接（WAL模式，临时文件定向到D盘）。

    DB_BACKEND 运行期仅支持 'sqlite'；若配置为 postgresql，此处显式报错，
    避免静默回退到 SQLite 导致数据写入与配置不符的存储。PostgreSQL 运行期
    接线（?→%s 占位符、lastrowid→RETURNING、datetime 函数、INSERT OR REPLACE
    →ON CONFLICT）见 db/ 目录与《研发需求差距分析与开发计划》阶段 P1。
    """
    try:
        import config as _cfg
        backend = (_cfg.DB_BACKEND or 'sqlite').lower()
    except Exception:
        backend = 'sqlite'
    if backend in ('postgresql', 'postgres', 'pg'):
        raise RuntimeError(
            "已配置 DB_BACKEND=postgresql，但运行期 PostgreSQL 后端尚未接线完成："
            "database.py 各 DB 类仍使用 SQLite 语义（? 占位符、lastrowid、"
            "datetime('now','localtime')、INSERT OR REPLACE/IGNORE）。"
            "为避免静默回退，请将 DB_BACKEND 设回 'sqlite'，或完成运行期 PG 适配后再启用。"
        )
    path = os.path.join(BASE_DIR, db_name)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    # 临时表使用内存，避免写磁盘临时文件
    conn.execute("PRAGMA temp_store=2")  # 2=MEMORY
    # WAL 自动检查点：当WAL超过1MB时自动合并，防止WAL无限增长
    conn.execute("PRAGMA wal_autocheckpoint=1000")  # 1000页 ≈ 1MB
    return conn


# ============================================================
# 1. 漏洞扫描结果数据库
# ============================================================
class ScanResultsDB:
    def __init__(self):
        self.conn = _connect('scan_results.db')
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS scan_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                target TEXT NOT NULL,
                scan_type TEXT DEFAULT 'quick',
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                vuln_count INTEGER DEFAULT 0,
                start_time TEXT,
                end_time TEXT,
                error_message TEXT,
                config TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                host TEXT,
                port INTEGER,
                protocol TEXT DEFAULT 'tcp',
                state TEXT DEFAULT 'open',
                service TEXT,
                version TEXT,
                cve_id TEXT,
                cve_name TEXT,
                cvss_score REAL,
                severity TEXT DEFAULT 'INFO',
                description TEXT,
                evidence TEXT,
                remediation TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (task_id) REFERENCES scan_tasks(id)
            )
        ''')
        # 新增字段（兼容旧数据库）
        try:
            c.execute('ALTER TABLE scan_results ADD COLUMN evidence TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE scan_results ADD COLUMN remediation TEXT')
        except sqlite3.OperationalError:
            pass
        # Web 应用安全扫描结果（P1 改进1）
        c.execute('''
            CREATE TABLE IF NOT EXISTS web_scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                scan_type TEXT DEFAULT 'web',
                category TEXT,
                title TEXT,
                severity TEXT DEFAULT 'INFO',
                detail TEXT,
                evidence TEXT,
                url TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        # 主动 Web 漏洞检测新增字段（兼容旧库）
        try:
            c.execute('ALTER TABLE web_scan_results ADD COLUMN parameter TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE web_scan_results ADD COLUMN payload TEXT')
        except sqlite3.OperationalError:
            pass
        # AI 误报核验落库字段（P1 增强，兼容旧库）
        try:
            c.execute('ALTER TABLE web_scan_results ADD COLUMN remediation TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE web_scan_results ADD COLUMN ai_verified INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE web_scan_results ADD COLUMN ai_confidence REAL')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE web_scan_results ADD COLUMN ai_reasoning TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE web_scan_results ADD COLUMN excluded_reason TEXT')
        except sqlite3.OperationalError:
            pass
        # 漏洞处置工作流（P1 管理闭环）
        c.execute('''
            CREATE TABLE IF NOT EXISTS vuln_dispositions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vuln_ref TEXT NOT NULL,
                vuln_title TEXT,
                status TEXT DEFAULT 'OPEN',
                severity TEXT DEFAULT 'INFO',
                assignee TEXT,
                note TEXT,
                reopen_reason TEXT,
                source TEXT DEFAULT 'scan',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                closed_at TEXT
            )
        ''')
        self.conn.commit()
        logger.info("扫描结果数据库初始化完成")

    def create_task(self, target, scan_type='quick', config=None):
        import json
        c = self.conn.cursor()
        c.execute('INSERT INTO scan_tasks (target, scan_type, status, start_time, config) VALUES (?,?,"running",datetime("now","localtime"),?)',
                  (target, scan_type, json.dumps(config or {}, ensure_ascii=False)))
        self.conn.commit()
        return c.lastrowid

    def update_task_status(self, task_id, status, vuln_count=0, error=''):
        c = self.conn.cursor()
        if status in ('completed', 'failed', 'stopped'):
            c.execute('UPDATE scan_tasks SET status=?, vuln_count=?, end_time=datetime("now","localtime"), error_message=? WHERE id=?',
                      (status, vuln_count, error, task_id))
        else:
            c.execute('UPDATE scan_tasks SET status=?, error_message=? WHERE id=?', (status, error, task_id))
        self.conn.commit()

    def add_scan_result(self, task_id, result):
        import json

        def _json(v):
            if v is None:
                return None
            if isinstance(v, str):
                return v
            return json.dumps(v, ensure_ascii=False)

        c = self.conn.cursor()
        c.execute('''INSERT INTO scan_results (task_id,host,port,protocol,state,service,version,cve_id,cve_name,cvss_score,severity,description,evidence,remediation)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (task_id, result.get('host'), result.get('port'), result.get('protocol','tcp'),
                   result.get('state','open'), result.get('service'), result.get('version'),
                   result.get('cve_id'), result.get('cve_name'), result.get('cvss_score'),
                   result.get('severity','INFO'), result.get('description'),
                   _json(result.get('evidence')), _json(result.get('remediation'))))
        self.conn.commit()

    def get_all_tasks(self, limit=100, offset=0):
        c = self.conn.cursor()
        c.execute('SELECT * FROM scan_tasks ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))
        return [dict(r) for r in c.fetchall()]

    def get_task(self, task_id):
        r = self.conn.execute('SELECT * FROM scan_tasks WHERE id=?', (task_id,)).fetchone()
        return dict(r) if r else None

    def count_tasks(self):
        return self.conn.execute('SELECT COUNT(*) FROM scan_tasks').fetchone()[0]

    def get_task_results(self, task_id):
        c = self.conn.cursor()
        c.execute('SELECT * FROM scan_results WHERE task_id=?', (task_id,))
        return [dict(r) for r in c.fetchall()]

    def get_today_task_count(self):
        today = datetime.now().strftime('%Y-%m-%d')
        return self.conn.execute("SELECT COUNT(*) FROM scan_tasks WHERE start_time LIKE ?", (today+'%',)).fetchone()[0]

    def get_scan_type_counts(self):
        """按扫描类型统计任务数"""
        rows = self.conn.execute(
            'SELECT scan_type, COUNT(*) as cnt FROM scan_tasks GROUP BY scan_type'
        ).fetchall()
        return {r['scan_type'] or 'other': r['cnt'] for r in rows}

    def get_scan_severity_counts(self):
        """扫描发现的漏洞按严重等级统计（CRITICAL/HIGH/MEDIUM/LOW）"""
        rows = self.conn.execute(
            'SELECT severity, COUNT(*) as cnt FROM scan_results GROUP BY severity'
        ).fetchall()
        return {r['severity']: r['cnt'] for r in rows}

    def get_today_status_counts(self):
        """今日任务按状态统计"""
        today = datetime.now().strftime('%Y-%m-%d')
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM scan_tasks WHERE start_time LIKE ? GROUP BY status",
            (today + '%',)
        ).fetchall()
        return {r['status']: r['cnt'] for r in rows}

    def get_vuln_by_task(self, limit=30):
        """按扫描任务统计各严重等级漏洞数（横轴=任务，非时间）"""
        c = self.conn.cursor()
        tasks = c.execute(
            "SELECT id, target, scan_type, vuln_count, created_at "
            "FROM scan_tasks WHERE status='completed' "
            "ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        if not tasks:
            return []
        # 单次GROUP BY查询获取所有任务的严重度分布
        task_ids = [t['id'] for t in tasks]
        placeholders = ','.join(['?' for _ in task_ids])
        sev_rows = c.execute(
            f"SELECT task_id, severity, COUNT(*) as cnt FROM scan_results "
            f"WHERE task_id IN ({placeholders}) GROUP BY task_id, severity",
            task_ids
        ).fetchall()
        # 构建 task_id → {severity: count} 映射
        sev_map = {}
        for r in sev_rows:
            sev_map.setdefault(r['task_id'], {})[r['severity']] = r['cnt']
        # 组装结果
        results = []
        for t in reversed(tasks):
            tid = t['id']
            counts = sev_map.get(tid, {})
            row = {'label': t['target'][:15], 'task_id': tid,
                   'scan_type': t['scan_type'], 'date': (t['created_at'] or '')[:10]}
            for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                row[sev] = counts.get(sev, 0)
            results.append(row)
        return results

    def get_statistics(self):
        return {
            'total_tasks': self.conn.execute('SELECT COUNT(*) FROM scan_tasks').fetchone()[0],
            'total_vulns': self.conn.execute('SELECT COUNT(*) FROM scan_results').fetchone()[0],
            'critical_count': self.conn.execute("SELECT COUNT(*) FROM scan_results WHERE severity IN ('CRITICAL','HIGH')").fetchone()[0],
            'recent_tasks': self.conn.execute('SELECT * FROM scan_tasks ORDER BY id DESC LIMIT 5').fetchall(),
            'recent_vulns': self.conn.execute('SELECT * FROM scan_results ORDER BY id DESC LIMIT 10').fetchall(),
        }

    # ---- Web 应用安全扫描结果（P1 改进1） ----
    def add_web_scan_result(self, target, result):
        """写入一条 Web 扫描结果"""
        c = self.conn.cursor()
        c.execute('''INSERT INTO web_scan_results
                     (target,scan_type,category,title,severity,detail,evidence,url,parameter,payload,
                      remediation,ai_verified,ai_confidence,ai_reasoning,excluded_reason)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (target, result.get('scan_type', 'web'), result.get('category'),
                   result.get('title'), result.get('severity', 'INFO'),
                   result.get('detail'), result.get('evidence'), result.get('url'),
                   result.get('parameter'), result.get('payload'),
                   result.get('remediation'), 1 if result.get('ai_verified') else 0,
                   result.get('ai_confidence'), result.get('ai_reasoning'),
                   result.get('excluded_reason')))
        self.conn.commit()
        return c.lastrowid

    def get_web_scan_results(self, target=None, limit=500):
        c = self.conn.cursor()
        if target:
            c.execute('SELECT * FROM web_scan_results WHERE target=? ORDER BY id DESC LIMIT ?', (target, limit))
        else:
            c.execute('SELECT * FROM web_scan_results ORDER BY id DESC LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    # ---- 漏洞处置工作流（P1 管理闭环） ----
    def create_disposition(self, vuln_ref, vuln_title=None, severity='INFO',
                           assignee=None, source='scan', status='OPEN'):
        c = self.conn.cursor()
        c.execute('''INSERT INTO vuln_dispositions
                     (vuln_ref,vuln_title,status,severity,assignee,source)
                     VALUES (?,?,?,?,?,?)''',
                  (vuln_ref, vuln_title, status, severity, assignee, source))
        self.conn.commit()
        return c.lastrowid

    def get_disposition(self, disposition_id):
        r = self.conn.execute('SELECT * FROM vuln_dispositions WHERE id=?', (disposition_id,)).fetchone()
        return dict(r) if r else None

    def get_dispositions(self, status=None, assignee=None, limit=500):
        c = self.conn.cursor()
        query = 'SELECT * FROM vuln_dispositions WHERE 1=1'
        params = []
        if status:
            query += ' AND status=?'; params.append(status)
        if assignee:
            query += ' AND assignee=?'; params.append(assignee)
        query += ' ORDER BY updated_at DESC LIMIT ?'; params.append(limit)
        c.execute(query, params)
        return [dict(r) for r in c.fetchall()]

    def update_disposition(self, disposition_id, status=None, assignee=None,
                           note=None, reopen_reason=None):
        """更新处置记录状态，updated_at 自动刷新，CLOSED 时写入 closed_at"""
        fields = []
        values = []
        if status is not None:
            fields.append('status=?'); values.append(status)
        if assignee is not None:
            fields.append('assignee=?'); values.append(assignee)
        if note is not None:
            fields.append('note=?'); values.append(note)
        if reopen_reason is not None:
            fields.append('reopen_reason=?'); values.append(reopen_reason)
        if not fields:
            return
        if status == 'CLOSED':
            fields.append('closed_at=datetime(\'now\',\'localtime\')')
        elif status is not None:
            # 重开/回退时清除 closed_at，避免仍被判定为已关闭
            fields.append('closed_at=NULL')
        fields.append('updated_at=datetime(\'now\',\'localtime\')')
        values.append(disposition_id)
        self.conn.execute(
            'UPDATE vuln_dispositions SET ' + ', '.join(fields) + ' WHERE id=?', values)
        self.conn.commit()

    def clear_all(self):
        self.conn.execute('DELETE FROM scan_results')
        self.conn.execute('DELETE FROM scan_tasks')
        self.conn.execute('DELETE FROM web_scan_results')
        self.conn.execute('DELETE FROM vuln_dispositions')
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# 2. 漏洞库信息数据库
# ============================================================
class CVEDatabase:
    def __init__(self):
        self.conn = _connect('cve_database.db')
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS cve_database (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL UNIQUE,
                name TEXT,
                description TEXT,
                cvss_score REAL,
                severity TEXT DEFAULT 'UNKNOWN',
                published_date TEXT,
                modified_date TEXT,
                affected_products TEXT,
                references_url TEXT,
                ai_analysis TEXT,
                exploit_available INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS vendor_advisories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor TEXT NOT NULL,
                advisory_id TEXT,
                cve_id TEXT,
                package_name TEXT,
                severity TEXT,
                status TEXT,
                published_date TEXT,
                description TEXT,
                link TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS cvss_distribution (
                score_range TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        ''')
        # 新增字段（兼容旧数据库）
        try:
            c.execute('ALTER TABLE cve_database ADD COLUMN cwe TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE cve_database ADD COLUMN patch_link TEXT')
        except sqlite3.OperationalError:
            pass
        self.conn.commit()
        logger.info("CVE漏洞库数据库初始化完成")

    def add_cve_batch(self, cve_list):
        c = self.conn.cursor()
        count = 0
        try:
            c.execute('BEGIN')
            for cve in cve_list:
                try:
                    products = cve.get('affected_products', '')
                    if isinstance(products, list):
                        products = ','.join(products)
                    refs = cve.get('references', '')
                    if isinstance(refs, list):
                        refs = ','.join(refs)
                    c.execute('''INSERT OR REPLACE INTO cve_database
                        (cve_id,name,description,cvss_score,severity,published_date,modified_date,affected_products,references_url,ai_analysis,cwe,patch_link)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (cve.get('cve_id'), cve.get('name'), cve.get('description'),
                         cve.get('cvss_score'), cve.get('severity','UNKNOWN'),
                         cve.get('published_date'), cve.get('modified_date'),
                         products, refs, cve.get('ai_analysis'),
                         cve.get('cwe'), cve.get('patch_link')))
                    count += 1
                except Exception as e:
                    logger.error(f"插入CVE失败 {cve.get('cve_id')}: {e}")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return count

    def search_cve(self, keyword=None, min_cvss=0, limit=9990000, offset=0):
        c = self.conn.cursor()
        query = 'SELECT * FROM cve_database WHERE 1=1'
        params = []
        if keyword:
            query += ' AND (cve_id LIKE ? OR name LIKE ? OR description LIKE ? OR affected_products LIKE ?)'
            kw = f'%{keyword}%'
            params.extend([kw, kw, kw, kw])
        if min_cvss > 0:
            query += ' AND cvss_score >= ?'
            params.append(min_cvss)
        query += ' ORDER BY cvss_score DESC LIMIT ? OFFSET ?'
        params.append(limit)
        params.append(offset)
        c.execute(query, params)
        return [dict(r) for r in c.fetchall()]

    def count_cve(self, keyword=None, min_cvss=0):
        """返回符合筛选条件的CVE总数（用于分页）"""
        c = self.conn.cursor()
        query = 'SELECT COUNT(*) FROM cve_database WHERE 1=1'
        params = []
        if keyword:
            query += ' AND (cve_id LIKE ? OR name LIKE ? OR description LIKE ? OR affected_products LIKE ?)'
            kw = f'%{keyword}%'
            params.extend([kw, kw, kw, kw])
        if min_cvss > 0:
            query += ' AND cvss_score >= ?'
            params.append(min_cvss)
        c.execute(query, params)
        return c.fetchone()[0]

    def search_cve_by_product(self, keyword, limit=100):
        """按受影响产品搜索CVE"""
        c = self.conn.cursor()
        query = '''SELECT * FROM cve_database
                   WHERE affected_products LIKE ?
                   ORDER BY cvss_score DESC LIMIT ?'''
        c.execute(query, (f'%{keyword}%', limit))
        return [dict(r) for r in c.fetchall()]

    def get_cve_by_severity(self):
        c = self.conn.cursor()
        c.execute('SELECT severity, COUNT(*) as cnt FROM cve_database GROUP BY severity')
        return {r['severity']: r['cnt'] for r in c.fetchall()}

    def get_statistics(self):
        return {
            'total_cves': self.conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0],
            'cve_by_severity': self.get_cve_by_severity(),
        }

    def get_top_recent_cves(self, limit=50, days=90):
        """获取最近的高危CVE列表，按CVSS评分降序"""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        c = self.conn.cursor()
        c.execute('''SELECT * FROM cve_database
                     WHERE modified_date >= ? AND cvss_score IS NOT NULL
                     ORDER BY cvss_score DESC LIMIT ?''', (cutoff, limit))
        return [dict(r) for r in c.fetchall()]

    def add_vendor_advisory(self, advisory):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO vendor_advisories
            (vendor,advisory_id,cve_id,package_name,severity,status,published_date,description,link)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (advisory.get('vendor'), advisory.get('advisory_id'), advisory.get('cve_id'),
             advisory.get('package_name'), advisory.get('severity'), advisory.get('status'),
             advisory.get('published_date'), advisory.get('description'), advisory.get('link')))
        self.conn.commit()
        return c.lastrowid

    def get_vendor_advisories(self, vendor=None, limit=500):
        c = self.conn.cursor()
        if vendor:
            c.execute('SELECT * FROM vendor_advisories WHERE vendor=? ORDER BY published_date DESC LIMIT ?', (vendor, limit))
        else:
            c.execute('SELECT * FROM vendor_advisories ORDER BY published_date DESC LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    def update_cvss_distribution(self):
        c = self.conn.cursor()
        ranges = [('0.0-1.0',0,1), ('1.0-2.0',1,2), ('2.0-3.0',2,3), ('3.0-4.0',3,4),
                  ('4.0-5.0',4,5), ('5.0-6.0',5,6), ('6.0-7.0',6,7), ('7.0-8.0',7,8),
                  ('8.0-9.0',8,9), ('9.0-10.0',9,10)]
        for label, lo, hi in ranges:
            count = self.conn.execute(
                'SELECT COUNT(*) FROM cve_database WHERE cvss_score >= ? AND cvss_score < ?',
                (lo, hi)).fetchone()[0]
            c.execute('INSERT OR REPLACE INTO cvss_distribution (score_range,count) VALUES (?,?)', (label, count))
        self.conn.commit()

    def get_today_updated_count(self):
        today = datetime.now().strftime('%Y-%m-%d')
        return self.conn.execute("SELECT COUNT(*) FROM cve_database WHERE modified_date=?", (today,)).fetchone()[0]

    def clear_all(self):
        self.conn.execute('DELETE FROM cve_database')
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# 3. 威胁情报信息数据库
# ============================================================
class ThreatIntelDB:
    def __init__(self):
        self.conn = _connect('threat_intel.db')
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()

        # CISA已知被利用漏洞 (KEV)
        c.execute('''
            CREATE TABLE IF NOT EXISTS cisa_kev (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL UNIQUE,
                vulnerability_name TEXT,
                date_added TEXT,
                due_date TEXT,
                required_action TEXT,
                known_ransomware INTEGER DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')

        # EPSS 漏洞利用预测评分
        c.execute('''
            CREATE TABLE IF NOT EXISTS epss_scores (
                cve_id TEXT PRIMARY KEY,
                epss_score REAL,
                percentile REAL,
                updated_date TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')

        # 威胁行为者
        c.execute('''
            CREATE TABLE IF NOT EXISTS threat_actors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                aliases TEXT,
                motivation TEXT,
                target_sectors TEXT,
                known_tools TEXT,
                associated_cves TEXT,
                description TEXT,
                first_seen TEXT,
                last_seen TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')

        # IoC 威胁指标
        c.execute('''
            CREATE TABLE IF NOT EXISTS iocs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                threat_actor TEXT,
                malware_family TEXT,
                confidence TEXT DEFAULT 'medium',
                first_seen TEXT,
                last_seen TEXT,
                source TEXT,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(ioc_type, ioc_value)
            )
        ''')

        # 攻击模式 (MITRE ATT&CK)
        c.execute('''
            CREATE TABLE IF NOT EXISTS attack_patterns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tactic TEXT,
                platform TEXT,
                description TEXT,
                detection TEXT,
                mitigation TEXT
            )
        ''')

        # 威胁情报源
        c.execute('''
            CREATE TABLE IF NOT EXISTS threat_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT,
                feed_type TEXT,
                update_frequency TEXT,
                enabled INTEGER DEFAULT 1,
                last_updated TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')

        # 弱口令字典
        c.execute('''
            CREATE TABLE IF NOT EXISTS weak_passwords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                password TEXT,
                protocol TEXT DEFAULT 'generic',
                source TEXT DEFAULT 'builtin',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS threat_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')

        # 默认威胁情报源
        c.execute('''INSERT OR IGNORE INTO threat_feeds (name,url,feed_type,update_frequency,enabled) VALUES
            ("CISA KEV Catalog","https://www.cisa.gov/known-exploited-vulnerabilities-catalog","KEV","daily",1),
            ("FIRST EPSS","https://www.first.org/epss/","EPSS","daily",1),
            ("MITRE ATT&CK","https://attack.mitre.org/","Attack Patterns","weekly",1),
            ("AlienVault OTX","https://otx.alienvault.com/","IoC","hourly",1),
            ("Abuse.ch URLhaus","https://urlhaus.abuse.ch/","Malware URLs","hourly",1),
            ("MalwareBazaar","https://bazaar.abuse.ch/","Malware Samples","hourly",1)
        ''')

        # 默认弱口令
        c.execute('SELECT COUNT(*) FROM weak_passwords')
        if c.fetchone()[0] == 0:
            defaults = [
                ('admin','admin','generic'), ('admin','123456','generic'),
                ('admin','password','generic'), ('root','root','generic'),
                ('root','123456','generic'), ('root','password','generic'),
                ('admin','admin123','generic'), ('sa','sa','mssql'),
                ('system','manager','oracle'), ('scott','tiger','oracle'),
                ('postgres','postgres','postgresql'),
            ]
            c.executemany('INSERT INTO weak_passwords (username,password,protocol) VALUES (?,?,?)', defaults)

        self.conn.commit()
        logger.info("威胁情报数据库初始化完成")

    # ---- CISA KEV ----
    def add_kev(self, kev_data):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO cisa_kev (cve_id,vulnerability_name,date_added,due_date,required_action,known_ransomware,notes)
                     VALUES (?,?,?,?,?,?,?)''',
                  (kev_data.get('cve_id'), kev_data.get('vulnerability_name'), kev_data.get('date_added'),
                   kev_data.get('due_date'), kev_data.get('required_action'),
                   kev_data.get('known_ransomware', 0), kev_data.get('notes')))
        self.conn.commit()
        return c.lastrowid

    def get_kev_list(self, limit=1000):
        c = self.conn.cursor()
        c.execute('SELECT * FROM cisa_kev ORDER BY date_added DESC LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    def is_kev(self, cve_id):
        return self.conn.execute('SELECT COUNT(*) FROM cisa_kev WHERE cve_id=?', (cve_id,)).fetchone()[0] > 0

    def get_kev_by_cve(self, cve_id):
        """按 CVE 编号查询单条 KEV 记录（含 known_ransomware / required_action / due_date）。"""
        c = self.conn.cursor()
        c.execute('SELECT * FROM cisa_kev WHERE cve_id=?', (cve_id,))
        r = c.fetchone()
        return dict(r) if r else None

    # ---- EPSS ----
    def add_epss(self, cve_id, epss_score, percentile=None):
        self.conn.execute('''INSERT OR REPLACE INTO epss_scores (cve_id,epss_score,percentile,updated_date)
                             VALUES (?,?,?,date("now"))''', (cve_id, epss_score, percentile))
        self.conn.commit()

    def get_epss(self, cve_id):
        r = self.conn.execute('SELECT * FROM epss_scores WHERE cve_id=?', (cve_id,)).fetchone()
        return dict(r) if r else None

    # ---- 威胁行为者 ----
    def add_threat_actor(self, actor):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO threat_actors (name,aliases,motivation,target_sectors,known_tools,associated_cves,description,first_seen,last_seen)
                     VALUES (?,?,?,?,?,?,?,?,?)''',
                  (actor.get('name'), actor.get('aliases'), actor.get('motivation'),
                   actor.get('target_sectors'), actor.get('known_tools'), actor.get('associated_cves'),
                   actor.get('description'), actor.get('first_seen'), actor.get('last_seen')))
        self.conn.commit()
        return c.lastrowid

    def get_threat_actors(self, limit=100):
        c = self.conn.cursor()
        c.execute('SELECT * FROM threat_actors ORDER BY last_seen DESC LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    # ---- IoC ----
    def add_ioc(self, ioc):
        c = self.conn.cursor()
        try:
            c.execute('''INSERT INTO iocs (ioc_type,ioc_value,threat_actor,malware_family,confidence,first_seen,last_seen,source,description)
                         VALUES (?,?,?,?,?,?,?,?,?)''',
                      (ioc.get('ioc_type'), ioc.get('ioc_value'), ioc.get('threat_actor'),
                       ioc.get('malware_family'), ioc.get('confidence','medium'),
                       ioc.get('first_seen'), ioc.get('last_seen'), ioc.get('source'),
                       ioc.get('description')))
            self.conn.commit()
            return c.lastrowid
        except sqlite3.IntegrityError:
            return -1

    def search_iocs(self, keyword=None, ioc_type=None, limit=1000):
        c = self.conn.cursor()
        query = 'SELECT * FROM iocs WHERE 1=1'
        params = []
        if keyword:
            query += ' AND ioc_value LIKE ?'
            params.append(f'%{keyword}%')
        if ioc_type:
            query += ' AND ioc_type=?'
            params.append(ioc_type)
        query += ' ORDER BY last_seen DESC LIMIT ?'
        params.append(limit)
        c.execute(query, params)
        return [dict(r) for r in c.fetchall()]

    # ---- 攻击模式 ----
    def add_attack_pattern(self, pattern):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO attack_patterns (id,name,tactic,platform,description,detection,mitigation)
                     VALUES (?,?,?,?,?,?,?)''',
                  (pattern.get('id'), pattern.get('name'), pattern.get('tactic'),
                   pattern.get('platform'), pattern.get('description'),
                   pattern.get('detection'), pattern.get('mitigation')))
        self.conn.commit()

    def get_attack_patterns(self, tactic=None, limit=500):
        c = self.conn.cursor()
        if tactic:
            c.execute('SELECT * FROM attack_patterns WHERE tactic=? LIMIT ?', (tactic, limit))
        else:
            c.execute('SELECT * FROM attack_patterns LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    # ---- 威胁情报源 ----
    def get_enabled_feeds(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM threat_feeds WHERE enabled=1')
        return [dict(r) for r in c.fetchall()]

    # ---- 弱口令 ----
    def check_weak_password(self, username, password, protocol=None):
        c = self.conn.cursor()
        if protocol:
            c.execute('SELECT COUNT(*) FROM weak_passwords WHERE username=? AND password=? AND (protocol=? OR protocol="generic")',
                      (username, password, protocol))
        else:
            c.execute('SELECT COUNT(*) FROM weak_passwords WHERE username=? AND password=?', (username, password))
        return c.fetchone()[0] > 0

    def get_weak_passwords(self, protocol=None, limit=500):
        """获取弱口令字典（供 WeakPasswordScanner 使用）"""
        c = self.conn.cursor()
        if protocol:
            c.execute('SELECT username,password FROM weak_passwords WHERE protocol=? OR protocol="generic" ORDER BY id LIMIT ?',
                      (protocol, limit))
        else:
            c.execute('SELECT username,password FROM weak_passwords ORDER BY id LIMIT ?', (limit,))
        rows = c.fetchall()
        return [{'username': r['username'], 'password': r['password']} for r in rows]

    def add_weak_password(self, username, password, protocol='generic'):
        try:
            c = self.conn.cursor()
            c.execute('INSERT INTO weak_passwords (username,password,protocol) VALUES (?,?,?)',
                      (username, password, protocol))
            self.conn.commit()
            return c.lastrowid
        except sqlite3.IntegrityError:
            return -1

    # ---- 设置 ----
    def get_setting(self, key, default=None):
        r = self.conn.execute('SELECT value FROM threat_settings WHERE key=?', (key,)).fetchone()
        return r['value'] if r else default

    def set_setting(self, key, value):
        self.conn.execute('INSERT OR REPLACE INTO threat_settings (key,value,updated_at) VALUES (?,?,datetime("now","localtime"))', (key, value))
        self.conn.commit()

    # ---- 统计 ----
    def get_statistics(self):
        return {
            'kev_count': self.conn.execute('SELECT COUNT(*) FROM cisa_kev').fetchone()[0],
            'epss_count': self.conn.execute('SELECT COUNT(*) FROM epss_scores').fetchone()[0],
            'actor_count': self.conn.execute('SELECT COUNT(*) FROM threat_actors').fetchone()[0],
            'ioc_count': self.conn.execute('SELECT COUNT(*) FROM iocs').fetchone()[0],
            'attack_pattern_count': self.conn.execute('SELECT COUNT(*) FROM attack_patterns').fetchone()[0],
        }

    def clear_all(self):
        self.conn.execute('DELETE FROM cisa_kev')
        self.conn.execute('DELETE FROM epss_scores')
        self.conn.execute('DELETE FROM threat_actors')
        self.conn.execute('DELETE FROM iocs')
        self.conn.execute('DELETE FROM attack_patterns')
        self.conn.execute('DELETE FROM weak_passwords')
        self.conn.execute('DELETE FROM threat_settings')
        self.conn.execute('DELETE FROM threat_feeds')
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# 4. AI代码审计结果数据库
# ============================================================
class AuditResultsDB:
    def __init__(self):
        self.conn = _connect('audit_results.db')
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS audit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                total_files_scanned INTEGER DEFAULT 0,
                total_vulnerabilities INTEGER DEFAULT 0,
                risk_level TEXT,
                recommendation TEXT,
                severity_json TEXT,
                generated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS audit_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id INTEGER NOT NULL,
                file TEXT,
                line INTEGER,
                category TEXT,
                severity TEXT,
                code TEXT,
                recommendation TEXT,
                FOREIGN KEY (audit_id) REFERENCES audit_history(id)
            )
        ''')
        # 兼容旧库：增补代码质量/设计审计新增列
        self._ensure_column(c, 'audit_issues', 'dimension', 'TEXT')
        self._ensure_column(c, 'audit_issues', 'problem', 'TEXT')
        self._ensure_column(c, 'audit_issues', 'evidence', 'TEXT')
        self._ensure_column(c, 'audit_issues', 'remediation', 'TEXT')
        self.conn.commit()
        logger.info("AI审计结果数据库初始化完成")

    def _ensure_column(self, cursor, table, column, col_type):
        """兼容旧库迁移：若列不存在则 ALTER TABLE 增补"""
        cols = [r['name'] for r in cursor.execute(f'PRAGMA table_info({table})').fetchall()]
        if column not in cols:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')

    def save_audit(self, result):
        import json
        c = self.conn.cursor()
        c.execute('''INSERT INTO audit_history (target,total_files_scanned,total_vulnerabilities,risk_level,recommendation,severity_json,generated_at)
                     VALUES (?,?,?,?,?,?,?)''',
                  (result.get('target',''), result.get('total_files_scanned',0),
                   result.get('total_vulnerabilities',0), result.get('risk_level',''),
                   result.get('recommendation',''),
                   json.dumps(result.get('severity_summary',{}), ensure_ascii=False),
                   result.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
        audit_id = c.lastrowid

        # 保存详细问题列表
        for issue in result.get('issues', []):
            evidence = issue.get('evidence') or {}
            remediation = issue.get('remediation') or {}
            c.execute('''INSERT INTO audit_issues
                         (audit_id,file,line,category,severity,code,recommendation,dimension,problem,evidence,remediation)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                      (audit_id,
                       issue.get('file', '') or '',
                       issue.get('line', 0) or 0,
                       issue.get('category', '') or '',
                       issue.get('severity', 'INFO') or 'INFO',
                       (issue.get('code', '') or '')[:200],
                       (issue.get('recommendation', '') or '')[:1000],
                       issue.get('dimension', 'security') or 'security',
                       (issue.get('problem', '') or '')[:1000],
                       json.dumps(evidence, ensure_ascii=False) if isinstance(evidence, dict) else str(evidence or ''),
                       json.dumps(remediation, ensure_ascii=False) if isinstance(remediation, dict) else str(remediation or '')))
        self.conn.commit()
        return audit_id

    def get_history(self, limit=100):
        import json
        c = self.conn.cursor()
        c.execute('SELECT * FROM audit_history ORDER BY id DESC LIMIT ?', (limit,))
        records = []
        for r in c.fetchall():
            d = dict(r)
            # 转换为in-memory格式
            d['total_files_scanned'] = d.get('total_files_scanned', d.get('total_files', 0))
            try:
                d['severity_summary'] = json.loads(d.get('severity_json', '{}'))
            except:
                d['severity_summary'] = {}
            d['scan_time'] = d.get('generated_at', '')
            # 加载详细问题列表
            c2 = self.conn.cursor()
            c2.execute('SELECT * FROM audit_issues WHERE audit_id=?', (d['id'],))
            d['issues'] = [dict(issue) for issue in c2.fetchall()]
            records.append(d)
        return records

    def get_statistics(self):
        return {
            'total_audits': self.conn.execute('SELECT COUNT(*) FROM audit_history').fetchone()[0],
            'total_issues_found': self.conn.execute('SELECT COALESCE(SUM(total_vulnerabilities),0) FROM audit_history').fetchone()[0],
        }

    def get_today_count(self):
        """今日代码审计任务数"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.conn.execute(
            "SELECT COUNT(*) FROM audit_history WHERE generated_at LIKE ?",
            (today + '%',)
        ).fetchone()[0]

    def get_audit_by_task(self, limit=30):
        """按审计任务统计各风险等级问题数（横轴=任务，非时间）"""
        c = self.conn.cursor()
        audits = c.execute(
            "SELECT id, target, total_vulnerabilities, generated_at "
            "FROM audit_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        if not audits:
            return []
        # 单次GROUP BY查询获取所有审计任务的严重度分布
        audit_ids = [a['id'] for a in audits]
        placeholders = ','.join(['?' for _ in audit_ids])
        sev_rows = c.execute(
            f"SELECT audit_id, severity, COUNT(*) as cnt FROM audit_issues "
            f"WHERE audit_id IN ({placeholders}) GROUP BY audit_id, severity",
            audit_ids
        ).fetchall()
        # 构建 audit_id → {severity: count} 映射
        sev_map = {}
        for r in sev_rows:
            sev_map.setdefault(r['audit_id'], {})[r['severity']] = r['cnt']
        # 组装结果
        results = []
        for a in reversed(audits):
            aid = a['id']
            path = a['target'] or 'unknown'
            label = path.replace('\\', '/').split('/')[-1] or path
            counts = sev_map.get(aid, {})
            row = {'label': label[:15], 'audit_id': aid,
                   'date': (a['generated_at'] or '')[:10]}
            for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                row[sev] = counts.get(sev, 0)
            results.append(row)
        return results

    def clear_all(self):
        self.conn.execute('DELETE FROM audit_history')
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# 5. 资产列表及系统操作信息数据库
# ============================================================
class AssetsSystemDB:
    def __init__(self):
        self.conn = _connect('assets_system.db')
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                url TEXT,
                mac TEXT,
                type TEXT DEFAULT 'SERVER',
                os TEXT,
                status TEXT DEFAULT 'ACTIVE',
                tags TEXT,
                owner TEXT,
                department TEXT,
                location TEXT,
                importance TEXT DEFAULT 'MEDIUM',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(ip, mac)
            )
        ''')
        # 新增字段（兼容旧数据库）：资产网址，对应 Web 漏洞扫描
        try:
            c.execute('ALTER TABLE assets ADD COLUMN url TEXT')
        except sqlite3.OperationalError:
            pass
        # 新增字段（兼容旧数据库）：合规检查所需的定级与分类信息
        # dengbao_level 决定等保条款集（L2/L3）；business_system 是问卷答案的作用域键；
        # data_classification 供数据安全合规模块判定分类分级条款
        for _col in ('dengbao_level', 'business_system', 'data_classification'):
            try:
                c.execute(f"ALTER TABLE assets ADD COLUMN {_col} TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        c.execute('''
            CREATE TABLE IF NOT EXISTS scan_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                ports TEXT,
                scan_type TEXT DEFAULT 'quick',
                intensity TEXT DEFAULT 'medium',
                timeout INTEGER DEFAULT 5,
                concurrent INTEGER DEFAULT 10,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT DEFAULT 'scan',
                format TEXT DEFAULT 'html',
                content TEXT,
                file_path TEXT,
                task_id INTEGER,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS work_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_type TEXT NOT NULL,
                status TEXT DEFAULT '已完成',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        # 迁移：为旧版 work_log 补充 status 列
        try:
            c.execute("ALTER TABLE work_log ADD COLUMN status TEXT DEFAULT '已完成'")
        except sqlite3.OperationalError:
            pass
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                user TEXT DEFAULT 'admin',
                target_type TEXT,
                target_id INTEGER,
                detail TEXT,
                ip_address TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        # 用户表（P1 用户+RBAC 系统）
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'viewer',
                email TEXT,
                full_name TEXT,
                active INTEGER DEFAULT 1,
                must_change_password INTEGER DEFAULT 0,
                last_login TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        # 角色表（P1 RBAC）
        c.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                permissions TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        # 默认设置
        c.execute('''INSERT OR IGNORE INTO system_settings (key,value) VALUES
                     ("company_name","山西有信网安科技有限公司"),
                     ("app_version","2.0.0"),("scan_timeout","5"),
                     ("scan_concurrent","10"),("auto_update_cve","true"),
                     ("report_retention_days","90")''')
        # 播种默认角色（RBAC）
        c.execute('SELECT COUNT(*) FROM roles')
        if c.fetchone()[0] == 0:
            import json
            from auth_rbac import ROLES, ROLE_LABELS
            for name, perms in ROLES.items():
                c.execute('INSERT OR IGNORE INTO roles (name,description,permissions) VALUES (?,?,?)',
                          (name, ROLE_LABELS.get(name, name), json.dumps(perms)))
        # 播种默认管理员（首次登录强制改密）
        c.execute('SELECT COUNT(*) FROM users')
        if c.fetchone()[0] == 0:
            from auth_rbac import hash_password
            c.execute('''INSERT INTO users (username,password_hash,role,full_name,must_change_password)
                         VALUES (?,?,?,?,1)''',
                      ('admin', hash_password('admin123'), 'admin', '系统管理员'))
        self.conn.commit()
        logger.info("资产及系统数据库初始化完成")

    # ---- 资产 ----
    def add_asset(self, asset):
        c = self.conn.cursor()
        try:
            c.execute('''INSERT INTO assets (name,ip,url,mac,type,os,status,tags,owner,department,location,importance,
                                             dengbao_level,business_system,data_classification)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (asset.get('name'), asset.get('ip'), asset.get('url'), asset.get('mac'),
                       asset.get('type','SERVER'), asset.get('os'), asset.get('status','ACTIVE'),
                       asset.get('tags'), asset.get('owner'), asset.get('department'),
                       asset.get('location'), asset.get('importance','MEDIUM'),
                       asset.get('dengbao_level',''), asset.get('business_system',''),
                       asset.get('data_classification','')))
            self.conn.commit()
            return c.lastrowid
        except sqlite3.IntegrityError:
            return -1

    def get_assets(self, filters=None, limit=9990000):
        c = self.conn.cursor()
        query = 'SELECT * FROM assets WHERE 1=1'
        params = []
        if filters:
            if 'type' in filters:
                query += ' AND type=?'; params.append(filters['type'])
            if 'status' in filters:
                query += ' AND status=?'; params.append(filters['status'])
            if 'keyword' in filters:
                query += ' AND (name LIKE ? OR ip LIKE ?)'
                kw = f"%{filters['keyword']}%"
                params.extend([kw, kw])
            if 'importance' in filters:
                query += ' AND importance=?'; params.append(filters['importance'])
            if 'tags' in filters:
                t = filters['tags']
                query += ' AND (tags=? OR tags LIKE ? OR tags LIKE ? OR tags LIKE ?)'
                params.extend([t, f'{t},%', f'%,{t}', f'%,{t},%'])
        query += ' ORDER BY updated_at DESC LIMIT ?'
        params.append(limit)
        c.execute(query, params)
        return [dict(r) for r in c.fetchall()]

    def get_asset(self, asset_id):
        r = self.conn.execute('SELECT * FROM assets WHERE id=?', (asset_id,)).fetchone()
        return dict(r) if r else None

    def update_asset(self, asset_id, data):
        # 白名单验证：只允许更新 assets 表中的合法列名
        ALLOWED_COLUMNS = {'name', 'ip', 'url', 'mac', 'type', 'os', 'status', 'tags',
                           'owner', 'department', 'location', 'importance',
                           'dengbao_level', 'business_system', 'data_classification'}
        sanitized = {}
        for k, v in data.items():
            if k in ALLOWED_COLUMNS:
                sanitized[k] = v
            else:
                logger.warning(f"拒绝非法列名: {k}")
        if not sanitized:
            return
        set_clause = ', '.join(f'{k}=?' for k in sanitized)
        query = 'UPDATE assets SET ' + set_clause + ', updated_at=datetime(\'now\',\'localtime\') WHERE id=?'
        values = list(sanitized.values()) + [asset_id]
        self.conn.execute(query, values)
        self.conn.commit()

    def delete_asset(self, asset_id):
        self.conn.execute('DELETE FROM assets WHERE id=?', (asset_id,))
        self.conn.commit()

    def get_asset_count(self):
        return self.conn.execute('SELECT COUNT(*) FROM assets').fetchone()[0]

    def get_asset_type_counts(self):
        """按类型统计资产分布"""
        rows = self.conn.execute(
            'SELECT type, COUNT(*) as cnt FROM assets GROUP BY type ORDER BY cnt DESC'
        ).fetchall()
        return {r['type'] or 'OTHER': r['cnt'] for r in rows}

    def get_asset_tags(self):
        """聚合全部资产标签（去重排序）"""
        rows = self.conn.execute("SELECT tags FROM assets WHERE tags IS NOT NULL AND tags != ''").fetchall()
        tags = set()
        for r in rows:
            for t in (r['tags'] or '').split(','):
                t = t.strip()
                if t:
                    tags.add(t)
        return sorted(tags)

    # ---- 报告 ----
    def save_report(self, title, rtype, fmt, content, file_path, task_id=None):
        c = self.conn.cursor()
        c.execute('INSERT INTO reports (title,type,format,content,file_path,task_id) VALUES (?,?,?,?,?,?)',
                  (title, rtype, fmt, content, file_path, task_id))
        self.conn.commit()
        return c.lastrowid

    def get_reports(self, limit=50):
        c = self.conn.cursor()
        c.execute('SELECT * FROM reports ORDER BY id DESC LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_today_quality_count(self):
        """今日代码质量检测任务数（按 reports.type='quality_audit'）"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.conn.execute(
            "SELECT COUNT(*) FROM reports WHERE type='quality_audit' AND created_at LIKE ?",
            (today + '%',)
        ).fetchone()[0]

    def get_quality_count_total(self):
        """代码质量检测任务历史累计数（按 reports.type='quality_audit'）"""
        return self.conn.execute(
            "SELECT COUNT(*) FROM reports WHERE type='quality_audit'"
        ).fetchone()[0]

    def get_work_type_total(self, work_type):
        """指定工作类型的历史累计次数（work_log 按类型计数）"""
        return self.conn.execute(
            'SELECT COUNT(*) FROM work_log WHERE work_type=?', (work_type,)
        ).fetchone()[0]

    def log_work(self, work_type, status='已完成'):
        """记录一次已结束的工作操作（瞬时操作，直接以终态计数），返回工作ID"""
        c = self.conn.cursor()
        c.execute('INSERT INTO work_log (work_type, status) VALUES (?,?)', (work_type, status))
        self.conn.commit()
        return c.lastrowid

    def start_work(self, work_type):
        """开始一项工作，返回工作会话ID（初始状态=进行中）"""
        c = self.conn.cursor()
        c.execute('INSERT INTO work_log (work_type, status) VALUES (?, "进行中")', (work_type,))
        self.conn.commit()
        return c.lastrowid

    def finish_work(self, work_id, status='已完成'):
        """结束一项工作，更新其状态"""
        self.conn.execute('UPDATE work_log SET status=? WHERE id=?', (status, work_id))
        self.conn.commit()

    def delete_work(self, work_id):
        """删除一项工作记录（如计划中任务已转交实际执行）"""
        self.conn.execute('DELETE FROM work_log WHERE id=?', (work_id,))
        self.conn.commit()

    def get_today_work_type_counts(self):
        """今日各工作类型的操作次数（work_log 按类型计数）"""
        today = datetime.now().strftime('%Y-%m-%d')
        rows = self.conn.execute(
            "SELECT work_type, COUNT(*) as cnt FROM work_log WHERE created_at LIKE ? GROUP BY work_type",
            (today + '%',)
        ).fetchall()
        return {r['work_type']: r['cnt'] for r in rows}

    def get_today_work_status_rows(self):
        """今日 work_log 按 (工作类型, 状态) 计数"""
        today = datetime.now().strftime('%Y-%m-%d')
        rows = self.conn.execute(
            "SELECT work_type, status, COUNT(*) as cnt FROM work_log WHERE created_at LIKE ? GROUP BY work_type, status",
            (today + '%',)
        ).fetchall()
        return [{'work_type': r['work_type'], 'status': r['status'], 'cnt': r['cnt']} for r in rows]

    def delete_report(self, report_id):
        c = self.conn.cursor()
        c.execute('DELETE FROM reports WHERE id=?', (report_id,))
        self.conn.commit()
        return c.rowcount

    # ---- 设置 ----
    def get_setting(self, key, default=None):
        r = self.conn.execute('SELECT value FROM system_settings WHERE key=?', (key,)).fetchone()
        return r['value'] if r else default

    def set_setting(self, key, value):
        self.conn.execute('INSERT OR REPLACE INTO system_settings (key,value,updated_at) VALUES (?,?,datetime("now","localtime"))', (key, value))
        self.conn.commit()

    # ---- 审计日志 ----
    def add_audit_log(self, action, target_type=None, target_id=None, detail=None):
        self.conn.execute('INSERT INTO audit_logs (action,target_type,target_id,detail) VALUES (?,?,?,?)',
                          (action, target_type, target_id, detail))
        self.conn.commit()

    # ---- 用户 + 角色（P1 RBAC） ----
    def create_user(self, username, password_hash, role='viewer', email=None,
                    full_name=None, must_change_password=0):
        try:
            c = self.conn.cursor()
            c.execute('''INSERT INTO users (username,password_hash,role,email,full_name,must_change_password)
                         VALUES (?,?,?,?,?,?)''',
                      (username, password_hash, role, email, full_name, must_change_password))
            self.conn.commit()
            return c.lastrowid
        except sqlite3.IntegrityError:
            return -1

    def get_user_by_username(self, username):
        r = self.conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        return dict(r) if r else None

    def get_user(self, user_id):
        r = self.conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        return dict(r) if r else None

    def get_users(self, limit=500):
        c = self.conn.cursor()
        c.execute('SELECT id,username,role,email,full_name,active,must_change_password,last_login,created_at FROM users ORDER BY id LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    def update_user(self, user_id, role=None, email=None, full_name=None,
                    active=None, must_change_password=None):
        fields = []
        values = []
        if role is not None:
            fields.append('role=?'); values.append(role)
        if email is not None:
            fields.append('email=?'); values.append(email)
        if full_name is not None:
            fields.append('full_name=?'); values.append(full_name)
        if active is not None:
            fields.append('active=?'); values.append(active)
        if must_change_password is not None:
            fields.append('must_change_password=?'); values.append(must_change_password)
        if not fields:
            return
        values.append(user_id)
        self.conn.execute('UPDATE users SET ' + ', '.join(fields) + ' WHERE id=?', values)
        self.conn.commit()

    def set_user_password(self, user_id, password_hash):
        self.conn.execute('UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?',
                          (password_hash, user_id))
        self.conn.commit()

    def record_login(self, user_id):
        self.conn.execute('UPDATE users SET last_login=datetime(\'now\',\'localtime\') WHERE id=?', (user_id,))
        self.conn.commit()

    def delete_user(self, user_id):
        self.conn.execute('DELETE FROM users WHERE id=?', (user_id,))
        self.conn.commit()

    def get_roles(self, limit=100):
        c = self.conn.cursor()
        c.execute('SELECT * FROM roles ORDER BY id LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_role(self, name):
        r = self.conn.execute('SELECT * FROM roles WHERE name=?', (name,)).fetchone()
        return dict(r) if r else None

    def clear_all(self):
        self.conn.execute('DELETE FROM assets')
        self.conn.execute('DELETE FROM scan_policies')
        self.conn.execute('DELETE FROM reports')
        self.conn.execute('DELETE FROM audit_logs')
        # 注意：不删除 users/roles，避免清库后失去管理员访问权限
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# 6. 合规检查结果数据库
# ============================================================
class ComplianceResultsDB:
    """合规检查结果数据库（等保 / 关基 / 数据安全 三标准共用）

    问卷答案与检查结果分表存放：结果每次检查追加一条历史，
    答案按 (标准, 作用域, 条款) 唯一，跨次检查复用。
    """

    def __init__(self):
        self.conn = _connect('compliance_results.db')
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS compliance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard TEXT NOT NULL,
                standard_name TEXT,
                version TEXT,
                level TEXT DEFAULT 'ALL',
                target TEXT,
                scope_key TEXT DEFAULT 'ORG',
                compliance_rate REAL,
                score INTEGER,
                total INTEGER DEFAULT 0,
                pass_count INTEGER DEFAULT 0,
                partial_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                na_count INTEGER DEFAULT 0,
                unfilled_count INTEGER DEFAULT 0,
                insufficient_count INTEGER DEFAULT 0,
                auto_ratio REAL,
                questionnaire_completion REAL,
                ai_enabled INTEGER DEFAULT 0,
                by_domain_json TEXT,
                summary_json TEXT,
                generated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS compliance_control_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id INTEGER NOT NULL,
                control_id TEXT NOT NULL,
                domain TEXT,
                category TEXT,
                title TEXT,
                requirement TEXT,
                status TEXT,
                severity TEXT,
                weight REAL DEFAULT 1.0,
                mode TEXT,
                verdict_source TEXT,
                ai_status TEXT,
                ai_reasoning TEXT,
                detail TEXT,
                recommendation TEXT,
                evidence_json TEXT,
                FOREIGN KEY (history_id) REFERENCES compliance_history(id)
            )
        ''')
        # UNIQUE 保证同一标准同一作用域下每条款只有一份答案，重复填报走 UPSERT
        c.execute('''
            CREATE TABLE IF NOT EXISTS questionnaire_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard TEXT NOT NULL,
                scope_key TEXT NOT NULL DEFAULT 'ORG',
                control_id TEXT NOT NULL,
                status TEXT,
                note TEXT,
                evidence_ref TEXT,
                answered_by TEXT,
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(standard, scope_key, control_id)
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ch_standard ON compliance_history(standard)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ccr_history ON compliance_control_results(history_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_qa_scope ON questionnaire_answers(standard, scope_key)')
        self.conn.commit()
        logger.info("合规检查结果数据库初始化完成")

    # ---- 检查结果 ----
    def save_result(self, agg, ai_enabled=False):
        """保存一次合规检查（agg 为 ComplianceEngine.evaluate 的返回值）"""
        counts = agg.get('counts', {}) or {}
        c = self.conn.cursor()
        c.execute('''INSERT INTO compliance_history
                     (standard,standard_name,version,level,target,scope_key,
                      compliance_rate,score,total,pass_count,partial_count,fail_count,
                      na_count,unfilled_count,insufficient_count,auto_ratio,
                      questionnaire_completion,ai_enabled,by_domain_json,summary_json,generated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (agg.get('standard', ''), agg.get('standard_name', ''), agg.get('version', ''),
                   agg.get('level', 'ALL'), agg.get('target', ''), agg.get('scope_key', 'ORG'),
                   agg.get('compliance_rate'), agg.get('score'),
                   counts.get('total', 0), counts.get('符合', 0), counts.get('部分符合', 0),
                   counts.get('不符合', 0), counts.get('不适用', 0), counts.get('未填报', 0),
                   counts.get('证据不足', 0), agg.get('auto_ratio'),
                   agg.get('questionnaire_completion'), 1 if ai_enabled else 0,
                   json.dumps(agg.get('by_domain', {}), ensure_ascii=False),
                   json.dumps({'counts': counts,
                               'source_counts': agg.get('source_counts', {}),
                               'ai_counts': agg.get('ai_counts', {}),
                               'scored_total': agg.get('scored_total', 0),
                               'questionnaire_total': agg.get('questionnaire_total', 0)},
                              ensure_ascii=False),
                   agg.get('timestamp') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        history_id = c.lastrowid

        for r in agg.get('results', []):
            evidence = r.get('evidence') or []
            c.execute('''INSERT INTO compliance_control_results
                         (history_id,control_id,domain,category,title,requirement,status,severity,
                          weight,mode,verdict_source,ai_status,ai_reasoning,detail,recommendation,evidence_json)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (history_id, r.get('control_id', ''), r.get('domain', ''),
                       r.get('category', ''), r.get('title', ''), r.get('requirement', ''),
                       r.get('status', ''), r.get('severity', 'INFO'),
                       float(r.get('_weight', 1.0)), r.get('_mode', ''),
                       r.get('verdict_source', ''), r.get('ai_status', ''),
                       (r.get('ai_reasoning', '') or '')[:2000],
                       (r.get('detail', '') or '')[:2000],
                       (r.get('recommendation', '') or '')[:2000],
                       json.dumps(evidence, ensure_ascii=False)))
        self.conn.commit()
        return history_id

    def get_history(self, standard=None, limit=100):
        if standard:
            rows = self.conn.execute(
                '''SELECT * FROM compliance_history WHERE standard=?
                   ORDER BY id DESC LIMIT ?''', (standard, limit)).fetchall()
        else:
            rows = self.conn.execute(
                'SELECT * FROM compliance_history ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_detail(self, history_id):
        """取一次检查的完整结果。不存在时返回 None，不伪造空壳。"""
        head = self.conn.execute(
            'SELECT * FROM compliance_history WHERE id=?', (history_id,)).fetchone()
        if head is None:
            return None
        rows = self.conn.execute(
            'SELECT * FROM compliance_control_results WHERE history_id=? ORDER BY id',
            (history_id,)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d['evidence'] = json.loads(d.get('evidence_json') or '[]')
            except (ValueError, TypeError):
                d['evidence'] = []
            results.append(d)
        head = dict(head)
        for key, col in (('by_domain', 'by_domain_json'), ('summary', 'summary_json')):
            try:
                head[key] = json.loads(head.get(col) or '{}')
            except (ValueError, TypeError):
                head[key] = {}
        return {'history': head, 'results': results}

    def get_latest(self, standard, scope_key='ORG'):
        row = self.conn.execute(
            '''SELECT * FROM compliance_history WHERE standard=? AND scope_key=?
               ORDER BY id DESC LIMIT 1''', (standard, scope_key)).fetchone()
        return dict(row) if row else None

    def delete_result(self, history_id):
        self.conn.execute('DELETE FROM compliance_control_results WHERE history_id=?', (history_id,))
        self.conn.execute('DELETE FROM compliance_history WHERE id=?', (history_id,))
        self.conn.commit()

    # ---- 问卷答案 ----
    def upsert_answer(self, standard, control_id, status, note='',
                      scope_key='ORG', evidence_ref='', answered_by=''):
        """写入或更新一条问卷答案（同一标准+作用域+条款只保留最新一份）"""
        self.conn.execute(
            '''INSERT INTO questionnaire_answers
               (standard,scope_key,control_id,status,note,evidence_ref,answered_by,updated_at)
               VALUES (?,?,?,?,?,?,?,datetime('now','localtime'))
               ON CONFLICT(standard,scope_key,control_id) DO UPDATE SET
                 status=excluded.status,
                 note=excluded.note,
                 evidence_ref=excluded.evidence_ref,
                 answered_by=excluded.answered_by,
                 updated_at=datetime('now','localtime')''',
            (standard, scope_key or 'ORG', control_id, status, note or '',
             evidence_ref or '', answered_by or ''))
        self.conn.commit()

    def get_answers(self, standard, scope_key='ORG', include_org=True):
        """取问卷答案，返回 {control_id: {...}}。

        组织级（ORG）答案对所有业务系统复用；查询某业务系统时先铺 ORG 答案，
        再用该系统自己的答案覆盖，避免组织级条款在每个系统重复填报。
        """
        answers = {}
        scope_key = scope_key or 'ORG'
        keys = ['ORG', scope_key] if (include_org and scope_key != 'ORG') else [scope_key]
        for key in keys:
            rows = self.conn.execute(
                'SELECT * FROM questionnaire_answers WHERE standard=? AND scope_key=?',
                (standard, key)).fetchall()
            for r in rows:
                answers[r['control_id']] = dict(r)
        return answers

    def delete_answer(self, standard, control_id, scope_key='ORG'):
        self.conn.execute(
            'DELETE FROM questionnaire_answers WHERE standard=? AND scope_key=? AND control_id=?',
            (standard, scope_key or 'ORG', control_id))
        self.conn.commit()

    def get_scope_keys(self, standard):
        """已有填报记录的作用域列表（供界面下拉选择业务系统）"""
        rows = self.conn.execute(
            'SELECT DISTINCT scope_key FROM questionnaire_answers WHERE standard=? ORDER BY scope_key',
            (standard,)).fetchall()
        return [r['scope_key'] for r in rows]

    def get_statistics(self):
        total = self.conn.execute('SELECT COUNT(*) AS n FROM compliance_history').fetchone()['n']
        answers = self.conn.execute('SELECT COUNT(*) AS n FROM questionnaire_answers').fetchone()['n']
        rows = self.conn.execute(
            '''SELECT standard, COUNT(*) AS n, MAX(score) AS best, MAX(generated_at) AS last_at
               FROM compliance_history GROUP BY standard''').fetchall()
        return {
            'total_checks': total,
            'total_answers': answers,
            'by_standard': {r['standard']: {'checks': r['n'], 'best_score': r['best'],
                                            'last_at': r['last_at']} for r in rows},
        }

    def clear_all(self):
        self.conn.execute('DELETE FROM compliance_control_results')
        self.conn.execute('DELETE FROM compliance_history')
        self.conn.execute('DELETE FROM questionnaire_answers')
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# 统一数据库管理器
# ============================================================
class Database:
    """六大数据库统一管理"""

    def __init__(self):
        self.scan = ScanResultsDB()
        self.cve = CVEDatabase()
        self.intel = ThreatIntelDB()
        self.audit = AuditResultsDB()
        self.assets = AssetsSystemDB()
        self.compliance = ComplianceResultsDB()
        logger.info("六大数据库全部初始化完成")

    def get_statistics(self):
        scan_stats = self.scan.get_statistics()
        cve_stats = self.cve.get_statistics()
        audit_stats = self.audit.get_statistics()
        return {
            'total_cves': cve_stats['total_cves'],
            'total_assets': self.assets.get_asset_count(),
            'total_tasks': scan_stats['total_tasks'],
            'total_vulns': scan_stats['total_vulns'],
            'critical_count': scan_stats['critical_count'],
            'cve_by_severity': cve_stats['cve_by_severity'],
            'recent_tasks': scan_stats.get('recent_tasks', []),
            'recent_vulns': [dict(r) for r in scan_stats.get('recent_vulns', [])],
            'total_audit_issues': audit_stats['total_issues_found'],
        }

    def get_comprehensive_intel_stats(self):
        """获取综合威胁情报统计，供AI报告生成器使用"""
        stats = {
            'cve': self.cve.get_statistics(),
            'intel': self.intel.get_statistics(),
            'top_cves': self.cve.get_top_recent_cves(limit=50, days=365),
        }
        try:
            stats['kev_count'] = self.intel.conn.execute(
                'SELECT COUNT(*) FROM cisa_kev').fetchone()[0]
        except Exception:
            stats['kev_count'] = 0
        try:
            stats['actor_count'] = self.intel.conn.execute(
                'SELECT COUNT(*) FROM threat_actors').fetchone()[0]
        except Exception:
            stats['actor_count'] = 0
        try:
            stats['ioc_count'] = self.intel.conn.execute(
                'SELECT COUNT(*) FROM iocs').fetchone()[0]
        except Exception:
            stats['ioc_count'] = 0
        return stats

    # 便捷方法 - 委托给对应数据库
    def create_task(self, target, scan_type='quick', config=None):
        return self.scan.create_task(target, scan_type, config)

    def update_task_status(self, task_id, status, vuln_count=0, error=''):
        self.scan.update_task_status(task_id, status, vuln_count, error)

    def add_scan_result(self, task_id, result):
        self.scan.add_scan_result(task_id, result)

    def get_all_tasks(self, limit=100, offset=0):
        return self.scan.get_all_tasks(limit, offset)

    def get_task(self, task_id):
        return self.scan.get_task(task_id)

    def count_tasks(self):
        return self.scan.count_tasks()

    def get_task_results(self, task_id):
        return self.scan.get_task_results(task_id)

    def search_cve(self, keyword=None, min_cvss=0, limit=9990000, offset=0):
        return self.cve.search_cve(keyword, min_cvss, limit, offset)

    def count_cve(self, keyword=None, min_cvss=0):
        return self.cve.count_cve(keyword, min_cvss)

    def search_cve_by_product(self, keyword, limit=100):
        return self.cve.search_cve_by_product(keyword, limit)

    def add_cve_batch(self, cve_list):
        return self.cve.add_cve_batch(cve_list)

    def get_cve_by_severity(self):
        return self.cve.get_cve_by_severity()

    def save_audit_result(self, result):
        return self.audit.save_audit(result)

    def get_audit_history(self, limit=100):
        return self.audit.get_history(limit)

    def get_assets(self, filters=None, limit=9990000):
        return self.assets.get_assets(filters, limit)

    def get_asset(self, asset_id):
        return self.assets.get_asset(asset_id)

    def add_asset(self, asset):
        return self.assets.add_asset(asset)

    def update_asset(self, asset_id, data):
        self.assets.update_asset(asset_id, data)

    def delete_asset(self, asset_id):
        self.assets.delete_asset(asset_id)

    def save_report(self, title, rtype, fmt, content, file_path, task_id=None):
        return self.assets.save_report(title, rtype, fmt, content, file_path, task_id)

    def get_reports(self, limit=50):
        return self.assets.get_reports(limit)

    def delete_report(self, report_id):
        return self.assets.delete_report(report_id)

    def get_setting(self, key, default=None):
        return self.assets.get_setting(key, default)

    def set_setting(self, key, value):
        self.assets.set_setting(key, value)

    def add_audit_log(self, action, target_type=None, target_id=None, detail=None):
        self.assets.add_audit_log(action, target_type, target_id, detail)

    def get_intel_statistics(self):
        return self.intel.get_statistics()

    def get_kev_list(self, limit=1000):
        return self.intel.get_kev_list(limit)

    def is_kev(self, cve_id):
        return self.intel.is_kev(cve_id)

    def get_kev_by_cve(self, cve_id):
        return self.intel.get_kev_by_cve(cve_id)

    def get_epss(self, cve_id):
        return self.intel.get_epss(cve_id)

    def get_weak_passwords(self, protocol=None, limit=500):
        return self.intel.get_weak_passwords(protocol, limit)

    def add_weak_password(self, username, password, protocol='generic'):
        return self.intel.add_weak_password(username, password, protocol)

    # ---- Web 扫描（P1 改进1） ----
    def add_web_scan_result(self, target, result):
        return self.scan.add_web_scan_result(target, result)

    def get_web_scan_results(self, target=None, limit=500):
        return self.scan.get_web_scan_results(target, limit)

    # ---- 漏洞处置工作流（P1） ----
    def create_disposition(self, vuln_ref, vuln_title=None, severity='INFO',
                           assignee=None, source='scan', status='OPEN'):
        return self.scan.create_disposition(vuln_ref, vuln_title, severity, assignee, source, status)

    def get_disposition(self, disposition_id):
        return self.scan.get_disposition(disposition_id)

    def get_dispositions(self, status=None, assignee=None, limit=500):
        return self.scan.get_dispositions(status, assignee, limit)

    def update_disposition(self, disposition_id, status=None, assignee=None,
                           note=None, reopen_reason=None):
        return self.scan.update_disposition(disposition_id, status, assignee, note, reopen_reason)

    # ---- 用户 + RBAC（P1） ----
    def create_user(self, username, password_hash, role='viewer', email=None,
                    full_name=None, must_change_password=0):
        return self.assets.create_user(username, password_hash, role, email, full_name, must_change_password)

    def get_user_by_username(self, username):
        return self.assets.get_user_by_username(username)

    def get_user(self, user_id):
        return self.assets.get_user(user_id)

    def get_users(self, limit=500):
        return self.assets.get_users(limit)

    def update_user(self, user_id, **kwargs):
        return self.assets.update_user(user_id, **kwargs)

    def set_user_password(self, user_id, password_hash):
        return self.assets.set_user_password(user_id, password_hash)

    def record_login(self, user_id):
        return self.assets.record_login(user_id)

    def delete_user(self, user_id):
        return self.assets.delete_user(user_id)

    def get_roles(self, limit=100):
        return self.assets.get_roles(limit)

    # 仪表盘图表数据
    def get_asset_type_counts(self):
        return self.assets.get_asset_type_counts()

    def get_asset_tags(self):
        return self.assets.get_asset_tags()

    def get_scan_type_counts(self):
        return self.scan.get_scan_type_counts()

    def get_today_status_counts(self):
        return self.scan.get_today_status_counts()

    def log_work(self, work_type, status='已完成'):
        """记录一次已结束的工作操作（用于今日工作次数统计）"""
        return self.assets.log_work(work_type, status)

    def start_work(self, work_type):
        """开始一项工作，返回工作会话ID（初始状态=进行中）"""
        return self.assets.start_work(work_type)

    def finish_work(self, work_id, status='已完成'):
        """结束一项工作，更新其状态"""
        return self.assets.finish_work(work_id, status)

    def delete_work(self, work_id):
        """删除一项工作记录"""
        return self.assets.delete_work(work_id)

    def get_today_work_type_counts(self):
        return self.assets.get_today_work_type_counts()

    def get_today_work_counts(self):
        """今日工作统计（按六种工作的次数计算）"""
        scan_count = sum(self.scan.get_today_status_counts().values())
        audit_count = self.audit.get_today_count()
        quality_count = self.assets.get_today_quality_count()
        work_counts = self.assets.get_today_work_type_counts()
        return {
            '漏洞扫描': scan_count,
            'Web扫描': work_counts.get('Web扫描', 0),
            '代码审计': audit_count,
            '代码质量检测': quality_count,
            '漏洞库更新': work_counts.get('漏洞库更新', 0),
            '威胁情报': work_counts.get('威胁情报', 0),
        }

    def get_task_type_counts(self):
        """五类任务历史累计次数（漏洞扫描/Web扫描/AI代码审计/AI代码质量检测/威胁情报）"""
        return {
            '漏洞扫描': self.scan.count_tasks(),
            'Web扫描': self.assets.get_work_type_total('Web扫描'),
            'AI代码审计': self.audit.get_statistics()['total_audits'],
            'AI代码质量检测': self.assets.get_quality_count_total(),
            '威胁情报': self.assets.get_work_type_total('威胁情报'),
        }

    def get_today_work_status_matrix(self):
        """今日工作四状态 × 十类型矩阵（供堆叠柱状图）"""
        statuses = ['已完成', '进行中', '计划中', '被终止']
        work_types = ['漏洞扫描', 'Web扫描', 'AI代码审计', 'AI代码质量检测',
                      '漏洞库更新', '威胁情报', '资产管理', '等保合规', '关基合规', '数据安全合规', '176号合规']
        matrix = {wt: {s: 0 for s in statuses} for wt in work_types}
        # 漏洞扫描：scan_tasks 具备完整状态生命周期
        status_map = {'pending': '计划中', 'running': '进行中', 'completed': '已完成'}
        for status, cnt in self.scan.get_today_status_counts().items():
            bucket = status_map.get(status)
            if bucket is None and status in ('failed', 'stopped', 'cancelled'):
                bucket = '被终止'
            if bucket:
                matrix['漏洞扫描'][bucket] += cnt
        # Web扫描/漏洞库更新/威胁情报/资产管理：work_log 按 (类型, 状态) 计数
        for row in self.assets.get_today_work_status_rows():
            wt = row['work_type']
            if wt in matrix:
                matrix[wt][row['status']] += row['cnt']
        return matrix

    def get_scan_severity_counts(self):
        return self.scan.get_scan_severity_counts()

    def get_vuln_by_task(self, limit=30):
        return self.scan.get_vuln_by_task(limit)

    def get_audit_by_task(self, limit=30):
        return self.audit.get_audit_by_task(limit)

    # 合规检查
    def save_compliance_result(self, agg, ai_enabled=False):
        """保存一次合规检查结果，返回历史ID"""
        return self.compliance.save_result(agg, ai_enabled)

    def get_compliance_history(self, standard=None, limit=100):
        return self.compliance.get_history(standard, limit)

    def get_compliance_detail(self, history_id):
        return self.compliance.get_detail(history_id)

    def get_latest_compliance(self, standard, scope_key='ORG'):
        return self.compliance.get_latest(standard, scope_key)

    def upsert_questionnaire_answer(self, standard, control_id, status, note='',
                                    scope_key='ORG', evidence_ref='', answered_by=''):
        return self.compliance.upsert_answer(standard, control_id, status, note,
                                             scope_key, evidence_ref, answered_by)

    def get_questionnaire_answers(self, standard, scope_key='ORG', include_org=True):
        return self.compliance.get_answers(standard, scope_key, include_org)

    def clear_database(self):
        self.scan.clear_all()
        self.cve.clear_all()
        self.intel.clear_all()
        self.audit.clear_all()
        self.assets.clear_all()
        self.compliance.clear_all()

    def close(self):
        self.scan.close()
        self.cve.close()
        self.intel.close()
        self.audit.close()
        self.assets.close()
        self.compliance.close()

    def get_conn_for_cve_update(self):
        """获取CVE数据库连接用于今日更新统计"""
        return self.cve.conn

    @property
    def conn(self):
        """兼容旧代码 - 返回CVE连接（用于仪表盘统计）"""
        return self.cve.conn
