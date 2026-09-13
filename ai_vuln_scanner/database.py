# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 五大数据库模块"""
import sqlite3
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _connect(db_name):
    """创建数据库连接"""
    path = os.path.join(BASE_DIR, db_name)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
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
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (task_id) REFERENCES scan_tasks(id)
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
        c = self.conn.cursor()
        c.execute('''INSERT INTO scan_results (task_id,host,port,protocol,state,service,version,cve_id,cve_name,cvss_score,severity,description)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (task_id, result.get('host'), result.get('port'), result.get('protocol','tcp'),
                   result.get('state','open'), result.get('service'), result.get('version'),
                   result.get('cve_id'), result.get('cve_name'), result.get('cvss_score'),
                   result.get('severity','INFO'), result.get('description')))
        self.conn.commit()

    def get_all_tasks(self, limit=100):
        c = self.conn.cursor()
        c.execute('SELECT * FROM scan_tasks ORDER BY id DESC LIMIT ?', (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_task_results(self, task_id):
        c = self.conn.cursor()
        c.execute('SELECT * FROM scan_results WHERE task_id=?', (task_id,))
        return [dict(r) for r in c.fetchall()]

    def get_today_task_count(self):
        today = datetime.now().strftime('%Y-%m-%d')
        return self.conn.execute("SELECT COUNT(*) FROM scan_tasks WHERE start_time LIKE ?", (today+'%',)).fetchone()[0]

    def get_statistics(self):
        return {
            'total_tasks': self.conn.execute('SELECT COUNT(*) FROM scan_tasks').fetchone()[0],
            'total_vulns': self.conn.execute('SELECT COUNT(*) FROM scan_results').fetchone()[0],
            'critical_count': self.conn.execute("SELECT COUNT(*) FROM scan_results WHERE severity IN ('CRITICAL','HIGH')").fetchone()[0],
            'recent_tasks': self.conn.execute('SELECT * FROM scan_tasks ORDER BY id DESC LIMIT 5').fetchall(),
            'recent_vulns': self.conn.execute('SELECT * FROM scan_results ORDER BY id DESC LIMIT 10').fetchall(),
        }

    def clear_all(self):
        self.conn.execute('DELETE FROM scan_results')
        self.conn.execute('DELETE FROM scan_tasks')
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
        self.conn.commit()
        logger.info("CVE漏洞库数据库初始化完成")

    def add_cve_batch(self, cve_list):
        c = self.conn.cursor()
        count = 0
        for cve in cve_list:
            try:
                products = cve.get('affected_products', '')
                if isinstance(products, list):
                    products = ','.join(products)
                refs = cve.get('references', '')
                if isinstance(refs, list):
                    refs = ','.join(refs)
                c.execute('''INSERT OR REPLACE INTO cve_database
                    (cve_id,name,description,cvss_score,severity,published_date,modified_date,affected_products,references_url,ai_analysis)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (cve.get('cve_id'), cve.get('name'), cve.get('description'),
                     cve.get('cvss_score'), cve.get('severity','UNKNOWN'),
                     cve.get('published_date'), cve.get('modified_date'),
                     products, refs, cve.get('ai_analysis')))
                count += 1
            except Exception as e:
                logger.error(f"插入CVE失败 {cve.get('cve_id')}: {e}")
        self.conn.commit()
        return count

    def search_cve(self, keyword=None, min_cvss=0, limit=9990000):
        c = self.conn.cursor()
        query = 'SELECT * FROM cve_database WHERE 1=1'
        params = []
        if keyword:
            query += ' AND (cve_id LIKE ? OR description LIKE ? OR affected_products LIKE ?)'
            kw = f'%{keyword}%'
            params.extend([kw, kw, kw])
        if min_cvss > 0:
            query += ' AND cvss_score >= ?'
            params.append(min_cvss)
        query += ' ORDER BY cvss_score DESC LIMIT ?'
        params.append(limit)
        c.execute(query, params)
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
        for t in ['cisa_kev','epss_scores','threat_actors','iocs','attack_patterns','weak_passwords','threat_settings','threat_feeds']:
            self.conn.execute(f'DELETE FROM {t}')
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
        self.conn.commit()
        logger.info("AI审计结果数据库初始化完成")

    def save_audit(self, result):
        import json
        c = self.conn.cursor()
        # 如果表结构是旧的 (total_files)，先尝试兼容
        c.execute('''INSERT INTO audit_history (target,total_files_scanned,total_vulnerabilities,risk_level,recommendation,severity_json,generated_at)
                     VALUES (?,?,?,?,?,?,?)''',
                  (result.get('target',''), result.get('total_files_scanned',0),
                   result.get('total_vulnerabilities',0), result.get('risk_level',''),
                   result.get('recommendation',''),
                   json.dumps(result.get('severity_summary',{}), ensure_ascii=False),
                   result.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
        self.conn.commit()
        return c.lastrowid

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
            records.append(d)
        return records

    def get_statistics(self):
        return {
            'total_audits': self.conn.execute('SELECT COUNT(*) FROM audit_history').fetchone()[0],
            'total_issues_found': self.conn.execute('SELECT COALESCE(SUM(total_vulnerabilities),0) FROM audit_history').fetchone()[0],
        }

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
        # 默认设置
        c.execute('''INSERT OR IGNORE INTO system_settings (key,value) VALUES
                     ("company_name","山西有信网安科技有限公司"),
                     ("app_version","2.0.0"),("scan_timeout","5"),
                     ("scan_concurrent","10"),("auto_update_cve","true"),
                     ("report_retention_days","90")''')
        self.conn.commit()
        logger.info("资产及系统数据库初始化完成")

    # ---- 资产 ----
    def add_asset(self, asset):
        c = self.conn.cursor()
        try:
            c.execute('''INSERT INTO assets (name,ip,mac,type,os,status,tags,owner,department,location,importance)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                      (asset.get('name'), asset.get('ip'), asset.get('mac'), asset.get('type','SERVER'),
                       asset.get('os'), asset.get('status','ACTIVE'), asset.get('tags'),
                       asset.get('owner'), asset.get('department'), asset.get('location'),
                       asset.get('importance','MEDIUM')))
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
        query += ' ORDER BY updated_at DESC LIMIT ?'
        params.append(limit)
        c.execute(query, params)
        return [dict(r) for r in c.fetchall()]

    def get_asset(self, asset_id):
        r = self.conn.execute('SELECT * FROM assets WHERE id=?', (asset_id,)).fetchone()
        return dict(r) if r else None

    def update_asset(self, asset_id, data):
        fields = ', '.join(f'{k}=?' for k in data)
        values = list(data.values()) + [asset_id]
        self.conn.execute(f'UPDATE assets SET {fields}, updated_at=datetime("now","localtime") WHERE id=?', values)
        self.conn.commit()

    def delete_asset(self, asset_id):
        self.conn.execute('DELETE FROM assets WHERE id=?', (asset_id,))
        self.conn.commit()

    def get_asset_count(self):
        return self.conn.execute('SELECT COUNT(*) FROM assets').fetchone()[0]

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

    def clear_all(self):
        for t in ['assets','scan_policies','reports','audit_logs']:
            self.conn.execute(f'DELETE FROM {t}')
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# 统一数据库管理器
# ============================================================
class Database:
    """五大数据库统一管理"""

    def __init__(self):
        self.scan = ScanResultsDB()
        self.cve = CVEDatabase()
        self.intel = ThreatIntelDB()
        self.audit = AuditResultsDB()
        self.assets = AssetsSystemDB()
        logger.info("五大数据库全部初始化完成")

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

    # 便捷方法 - 委托给对应数据库
    def create_task(self, target, scan_type='quick', config=None):
        return self.scan.create_task(target, scan_type, config)

    def update_task_status(self, task_id, status, vuln_count=0, error=''):
        self.scan.update_task_status(task_id, status, vuln_count, error)

    def add_scan_result(self, task_id, result):
        self.scan.add_scan_result(task_id, result)

    def get_all_tasks(self, limit=100):
        return self.scan.get_all_tasks(limit)

    def get_task_results(self, task_id):
        return self.scan.get_task_results(task_id)

    def search_cve(self, keyword=None, min_cvss=0, limit=9990000):
        return self.cve.search_cve(keyword, min_cvss, limit)

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

    def clear_database(self):
        self.scan.clear_all()
        self.cve.clear_all()
        self.intel.clear_all()
        self.audit.clear_all()
        self.assets.clear_all()

    def close(self):
        self.scan.close()
        self.cve.close()
        self.intel.close()
        self.audit.close()
        self.assets.close()

    def get_conn_for_cve_update(self):
        """获取CVE数据库连接用于今日更新统计"""
        return self.cve.conn

    @property
    def conn(self):
        """兼容旧代码 - 返回CVE连接（用于仪表盘统计）"""
        return self.cve.conn
