# -*- coding: utf-8 -*-
"""PostgreSQL DDL — 20 tables + indexes + seed data"""
import logging; logger = logging.getLogger(__name__)

TABLES = {
    'scan_tasks': '''CREATE TABLE IF NOT EXISTS scan_tasks (
        id SERIAL PRIMARY KEY, name TEXT, target TEXT NOT NULL,
        scan_type TEXT DEFAULT 'quick', status TEXT DEFAULT 'pending',
        progress INTEGER DEFAULT 0, vuln_count INTEGER DEFAULT 0,
        start_time TEXT, end_time TEXT, error_message TEXT, config TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'scan_results': '''CREATE TABLE IF NOT EXISTS scan_results (
        id SERIAL PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES scan_tasks(id),
        host TEXT, port INTEGER, protocol TEXT DEFAULT 'tcp',
        state TEXT DEFAULT 'open', service TEXT, version TEXT,
        cve_id TEXT, cve_name TEXT, cvss_score REAL, severity TEXT DEFAULT 'INFO',
        description TEXT, evidence TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'cve_database': '''CREATE TABLE IF NOT EXISTS cve_database (
        id SERIAL PRIMARY KEY, cve_id TEXT NOT NULL UNIQUE, name TEXT,
        description TEXT, cvss_score REAL, severity TEXT DEFAULT 'UNKNOWN',
        published_date TEXT, modified_date TEXT, affected_products TEXT,
        references_url TEXT, ai_analysis TEXT, exploit_available INTEGER DEFAULT 0,
        cwe TEXT, patch_link TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'vendor_advisories': '''CREATE TABLE IF NOT EXISTS vendor_advisories (
        id SERIAL PRIMARY KEY, vendor TEXT NOT NULL, advisory_id TEXT,
        cve_id TEXT, package_name TEXT, severity TEXT, status TEXT,
        published_date TEXT, description TEXT, link TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'cvss_distribution': '''CREATE TABLE IF NOT EXISTS cvss_distribution (
        score_range TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''',
    'cisa_kev': '''CREATE TABLE IF NOT EXISTS cisa_kev (
        id SERIAL PRIMARY KEY, cve_id TEXT NOT NULL UNIQUE,
        vulnerability_name TEXT, date_added TEXT, due_date TEXT,
        required_action TEXT, known_ransomware INTEGER DEFAULT 0, notes TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'epss_scores': '''CREATE TABLE IF NOT EXISTS epss_scores (
        cve_id TEXT PRIMARY KEY, epss_score REAL, percentile REAL,
        updated_date TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'threat_actors': '''CREATE TABLE IF NOT EXISTS threat_actors (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, aliases TEXT,
        motivation TEXT, target_sectors TEXT, known_tools TEXT,
        associated_cves TEXT, description TEXT, first_seen TEXT, last_seen TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'iocs': '''CREATE TABLE IF NOT EXISTS iocs (
        id SERIAL PRIMARY KEY, ioc_type TEXT NOT NULL, ioc_value TEXT NOT NULL,
        threat_actor TEXT, malware_family TEXT, confidence TEXT DEFAULT 'medium',
        first_seen TEXT, last_seen TEXT, source TEXT, description TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'),
        UNIQUE(ioc_type, ioc_value))''',
    'attack_patterns': '''CREATE TABLE IF NOT EXISTS attack_patterns (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, tactic TEXT, platform TEXT,
        description TEXT, detection TEXT, mitigation TEXT)''',
    'threat_feeds': '''CREATE TABLE IF NOT EXISTS threat_feeds (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, url TEXT,
        feed_type TEXT, update_frequency TEXT, enabled INTEGER DEFAULT 1,
        last_updated TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'weak_passwords': '''CREATE TABLE IF NOT EXISTS weak_passwords (
        id SERIAL PRIMARY KEY, username TEXT, password TEXT,
        protocol TEXT DEFAULT 'generic', source TEXT DEFAULT 'builtin',
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'threat_settings': '''CREATE TABLE IF NOT EXISTS threat_settings (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'audit_history': '''CREATE TABLE IF NOT EXISTS audit_history (
        id SERIAL PRIMARY KEY, target TEXT NOT NULL,
        total_files_scanned INTEGER DEFAULT 0, total_vulnerabilities INTEGER DEFAULT 0,
        risk_level TEXT, recommendation TEXT, severity_json TEXT,
        generated_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'audit_issues': '''CREATE TABLE IF NOT EXISTS audit_issues (
        id SERIAL PRIMARY KEY, audit_id INTEGER NOT NULL REFERENCES audit_history(id),
        file TEXT, line INTEGER, category TEXT, severity TEXT,
        code TEXT, recommendation TEXT)''',
    'assets': '''CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL, ip TEXT NOT NULL, mac TEXT,
        type TEXT DEFAULT 'SERVER', os TEXT, status TEXT DEFAULT 'ACTIVE',
        tags TEXT, owner TEXT, department TEXT, location TEXT,
        importance TEXT DEFAULT 'MEDIUM',
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'),
        updated_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'),
        UNIQUE(ip, mac))''',
    'scan_policies': '''CREATE TABLE IF NOT EXISTS scan_policies (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
        ports TEXT, scan_type TEXT DEFAULT 'quick', intensity TEXT DEFAULT 'medium',
        timeout INTEGER DEFAULT 5, concurrent INTEGER DEFAULT 10,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'reports': '''CREATE TABLE IF NOT EXISTS reports (
        id SERIAL PRIMARY KEY, title TEXT NOT NULL, type TEXT DEFAULT 'scan',
        format TEXT DEFAULT 'html', content TEXT, file_path TEXT, task_id INTEGER,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'system_settings': '''CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
    'audit_logs': '''CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY, action TEXT NOT NULL, "user" TEXT DEFAULT 'admin',
        target_type TEXT, target_id INTEGER, detail TEXT, ip_address TEXT,
        created_at TEXT DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS'))''',
}

INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_sr_task ON scan_results(task_id)',
    'CREATE INDEX IF NOT EXISTS idx_sr_sev ON scan_results(severity)',
    'CREATE INDEX IF NOT EXISTS idx_st_status ON scan_tasks(status)',
    'CREATE INDEX IF NOT EXISTS idx_cve_cvss ON cve_database(cvss_score)',
    'CREATE INDEX IF NOT EXISTS idx_cve_mod ON cve_database(modified_date)',
    'CREATE INDEX IF NOT EXISTS idx_cve_sev ON cve_database(severity)',
    'CREATE INDEX IF NOT EXISTS idx_kev_date ON cisa_kev(date_added)',
    'CREATE INDEX IF NOT EXISTS idx_ai_audit ON audit_issues(audit_id)',
    'CREATE INDEX IF NOT EXISTS idx_assets_ip ON assets(ip)',
]

DEFAULT_FEEDS = [
    ("CISA KEV Catalog","https://www.cisa.gov/known-exploited-vulnerabilities-catalog","KEV","daily",1),
    ("FIRST EPSS","https://www.first.org/epss/","EPSS","daily",1),
    ("MITRE ATT&CK","https://attack.mitre.org/","Attack Patterns","weekly",1),
    ("AlienVault OTX","https://otx.alienvault.com/","IoC","hourly",1),
    ("Abuse.ch URLhaus","https://urlhaus.abuse.ch/","Malware URLs","hourly",1),
    ("MalwareBazaar","https://bazaar.abuse.ch/","Malware Samples","hourly",1),
]

DEFAULT_PASSWORDS = [
    ('admin','admin','generic'),('admin','123456','generic'),
    ('admin','password','generic'),('root','root','generic'),
    ('root','123456','generic'),('root','password','generic'),
    ('admin','admin123','generic'),('sa','sa','mssql'),
    ('system','manager','oracle'),('scott','tiger','oracle'),
    ('postgres','postgres','postgresql'),
]

DEFAULT_SETTINGS = [
    ('company_name','山西有信网安科技有限公司'),('app_version','2.1.0'),
    ('scan_timeout','5'),('scan_concurrent','10'),
    ('auto_update_cve','true'),('report_retention_days','90'),
]


def create_all_tables(conn):
    cur = conn.cursor()
    for name, ddl in TABLES.items():
        try: cur.execute(ddl); logger.info(f'  OK {name}')
        except Exception as e: logger.error(f'  FAIL {name}: {e}')
    for idx in INDEXES:
        try: cur.execute(idx)
        except Exception: pass
    for f in DEFAULT_FEEDS:
        try: cur.execute('INSERT INTO threat_feeds(name,url,feed_type,update_frequency,enabled) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(name) DO NOTHING', f)
        except Exception: pass
    for p in DEFAULT_PASSWORDS:
        try: cur.execute('INSERT INTO weak_passwords(username,password,protocol) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING', p)
        except Exception: pass
    for s in DEFAULT_SETTINGS:
        try: cur.execute('INSERT INTO system_settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING', s)
        except Exception: pass
    conn.commit()
    logger.info(f'Schema: {len(TABLES)} tables, {len(INDEXES)} indexes created')
