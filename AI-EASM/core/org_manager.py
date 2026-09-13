# -*- coding: utf-8 -*-
"""组织单元管理 — 数据库Schema + CRUD"""
import sqlite3, os, sys, uuid, json, threading
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import SYSTEM_DB_PATH

def generate_id(prefix=''):
    return f'{prefix}-{uuid.uuid4().hex[:12].upper()}' if prefix else uuid.uuid4().hex[:16].upper()

def dict_to_json(val):
    if isinstance(val, (dict, list)): return json.dumps(val, ensure_ascii=False)
    return val

class OrgManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or SYSTEM_DB_PATH
        self._lock = threading.Lock()
        self._credential_store = None
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id TEXT PRIMARY KEY, org_name TEXT NOT NULL,
                    org_type TEXT DEFAULT "企业", parent_org_id TEXT DEFAULT "",
                    network_ranges TEXT DEFAULT "", domain_name TEXT DEFAULT "",
                    contact_person TEXT DEFAULT "", contact_phone TEXT DEFAULT "",
                    security_level TEXT DEFAULT "S2A2G2", notes TEXT DEFAULT "",
                    status TEXT DEFAULT 'ACTIVE', created_at TEXT, updated_at TEXT
                );
                -- 组织线索（自定义键值对，用于精准暴露面搜索）
                CREATE TABLE IF NOT EXISTS org_clues (
                    clue_id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
                    clue_type TEXT NOT NULL, clue_value TEXT DEFAULT '',
                    source TEXT DEFAULT '', sort_order INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                CREATE INDEX IF NOT EXISTS idx_clues_org
                    ON org_clues(org_id);
                CREATE TABLE IF NOT EXISTS scan_tasks (
                    task_id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
                    task_name TEXT, task_type TEXT DEFAULT 'quick',
                    target_range TEXT, port_range TEXT,
                    status TEXT DEFAULT 'pending', progress_pct INTEGER DEFAULT 0,
                    hosts_found INTEGER DEFAULT 0, services_found INTEGER DEFAULT 0,
                    risks_found INTEGER DEFAULT 0, start_time TEXT, end_time TEXT,
                    created_at TEXT,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                CREATE TABLE IF NOT EXISTS exposures (
                    exposure_id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
                    asset_type TEXT, asset_name TEXT, asset_value TEXT,
                    source TEXT, detail TEXT, risk_level TEXT DEFAULT 'INFO',
                    confidence REAL DEFAULT 0.5, confidence_factors TEXT DEFAULT '',
                    status TEXT DEFAULT 'OPEN', discovered_at TEXT,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY, value TEXT
                );
                -- 企业全维度档案
                CREATE TABLE IF NOT EXISTS enterprise_profiles (
                    profile_id TEXT PRIMARY KEY, org_id TEXT, sub_id TEXT,
                    full_name TEXT NOT NULL, short_name TEXT DEFAULT '',
                    former_names TEXT DEFAULT '', english_name TEXT DEFAULT '',
                    legal_person TEXT DEFAULT '',
                    shareholders TEXT DEFAULT '',
                    beneficial_owners TEXT DEFAULT '',
                    actual_controllers TEXT DEFAULT '',
                    key_executives TEXT DEFAULT '',
                    emails TEXT DEFAULT '', phones TEXT DEFAULT '',
                    mobile_numbers TEXT DEFAULT '',
                    registered_address TEXT DEFAULT '',
                    business_scope TEXT DEFAULT '',
                    registered_capital TEXT DEFAULT '',
                    established_date TEXT DEFAULT '',
                    credit_code TEXT DEFAULT '',
                    source TEXT DEFAULT '', last_updated TEXT, created_at TEXT,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                -- 股权链子公司
                CREATE TABLE IF NOT EXISTS subsidiaries (
                    sub_id TEXT PRIMARY KEY, parent_org_id TEXT NOT NULL,
                    sub_name TEXT NOT NULL, equity_ratio REAL DEFAULT 0.0,
                    chain_level INTEGER DEFAULT 1,
                    relationship_type TEXT DEFAULT 'holding',
                    source TEXT DEFAULT '',
                    registered_address TEXT DEFAULT '',
                    legal_person TEXT DEFAULT '',
                    business_scope TEXT DEFAULT '',
                    created_at TEXT,
                    FOREIGN KEY (parent_org_id) REFERENCES organizations(org_id)
                );
                -- 企业关系图谱
                CREATE TABLE IF NOT EXISTS enterprise_relations (
                    relation_id TEXT PRIMARY KEY,
                    from_org_id TEXT, from_profile_id TEXT,
                    to_entity_name TEXT NOT NULL,
                    to_entity_type TEXT DEFAULT 'company',
                    relation_type TEXT NOT NULL,
                    relation_detail TEXT DEFAULT '',
                    equity_ratio REAL DEFAULT 0.0,
                    chain_path TEXT DEFAULT '', chain_level INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 0.5,
                    source TEXT DEFAULT '', created_at TEXT
                );
                -- 标识符反向索引
                CREATE TABLE IF NOT EXISTS identifier_index (
                    index_id TEXT PRIMARY KEY,
                    identifier_type TEXT NOT NULL,
                    identifier_value TEXT NOT NULL,
                    profile_id TEXT, org_id TEXT,
                    source TEXT DEFAULT '', created_at TEXT,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                CREATE INDEX IF NOT EXISTS idx_ident_type_val
                    ON identifier_index(identifier_type, identifier_value);
                -- ICP备案
                CREATE TABLE IF NOT EXISTS icp_records (
                    icp_id TEXT PRIMARY KEY, org_id TEXT, sub_id TEXT,
                    domain_name TEXT NOT NULL, icp_number TEXT DEFAULT '',
                    company_name TEXT NOT NULL, site_name TEXT DEFAULT '',
                    site_homepage TEXT DEFAULT '', approval_date TEXT DEFAULT '',
                    source TEXT DEFAULT 'beian.miit.gov.cn', created_at TEXT,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                -- WHOIS
                CREATE TABLE IF NOT EXISTS whois_records (
                    whois_id TEXT PRIMARY KEY, domain_name TEXT NOT NULL,
                    registrar TEXT DEFAULT '', creation_date TEXT DEFAULT '',
                    expiration_date TEXT DEFAULT '', registrant_org TEXT DEFAULT '',
                    registrant_email TEXT DEFAULT '', name_servers TEXT DEFAULT '',
                    raw_text TEXT DEFAULT '', created_at TEXT
                );
                -- IP段/ASN
                CREATE TABLE IF NOT EXISTS network_ranges (
                    range_id TEXT PRIMARY KEY, org_id TEXT, sub_id TEXT,
                    ip_range TEXT NOT NULL, asn_number TEXT DEFAULT '',
                    asn_name TEXT DEFAULT '', isp TEXT DEFAULT '',
                    country TEXT DEFAULT '', source TEXT DEFAULT '', created_at TEXT
                );
                -- 网站指纹
                CREATE TABLE IF NOT EXISTS site_fingerprints (
                    fingerprint_id TEXT PRIMARY KEY, org_id TEXT,
                    domain TEXT NOT NULL, title TEXT DEFAULT '',
                    favicon_hash TEXT DEFAULT '', tech_stack TEXT DEFAULT '',
                    header_signature TEXT DEFAULT '', body_hashes TEXT DEFAULT '',
                    screenshot_path TEXT DEFAULT '', created_at TEXT
                );
                -- 数据泄露证据
                CREATE TABLE IF NOT EXISTS leak_evidence (
                    leak_id TEXT PRIMARY KEY, org_id TEXT, exposure_id TEXT,
                    leak_category TEXT NOT NULL,
                    leak_pattern TEXT NOT NULL,
                    matched_content_snippet TEXT DEFAULT '',
                    source_url TEXT DEFAULT '', confidence REAL DEFAULT 0.5,
                    severity TEXT DEFAULT 'HIGH', discovered_at TEXT,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                -- 快速评估
                CREATE TABLE IF NOT EXISTS rapid_assessments (
                    session_id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
                    target_name TEXT NOT NULL, status TEXT DEFAULT 'running',
                    start_time TEXT, end_time TEXT,
                    subsidiaries_found INTEGER DEFAULT 0,
                    assets_found INTEGER DEFAULT 0,
                    leaks_found INTEGER DEFAULT 0,
                    total_dimensions INTEGER DEFAULT 15,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );
                -- 更名历史
                CREATE TABLE IF NOT EXISTS name_change_history (
                    change_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL, org_id TEXT,
                    old_name TEXT NOT NULL, new_name TEXT NOT NULL,
                    change_date TEXT DEFAULT '', change_reason TEXT DEFAULT '',
                    change_type TEXT DEFAULT 'rename',
                    source TEXT DEFAULT '', source_url TEXT DEFAULT '',
                    created_at TEXT,
                    FOREIGN KEY (profile_id) REFERENCES enterprise_profiles(profile_id)
                );
                -- 机构沿革索引
                CREATE TABLE IF NOT EXISTS org_timeline_index (
                    index_id TEXT PRIMARY KEY,
                    keyword TEXT NOT NULL,
                    current_org_id TEXT, current_name TEXT NOT NULL,
                    timeline TEXT DEFAULT '', created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_timeline_kw
                    ON org_timeline_index(keyword);
                -- 企业图谱查询日志
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_type TEXT DEFAULT 'equity',
                    query_text TEXT DEFAULT '',
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_query_log_time
                    ON query_log(created_at);
            ''')
            try: conn.execute("ALTER TABLE exposures ADD COLUMN confidence_factors TEXT DEFAULT ''")
            except: pass
            conn.commit()
    def add_org(self, **kwargs):
        org_id = kwargs.get("org_id") or generate_id("ORG")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO organizations
                (org_id,org_name,org_type,parent_org_id,network_ranges,domain_name,
                 contact_person,contact_phone,security_level,notes,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (org_id, kwargs.get("org_name",""), kwargs.get("org_type","企业"),
                 kwargs.get("parent_org_id",""), kwargs.get("network_ranges",""),
                 kwargs.get("domain_name",""), kwargs.get("contact_person",""),
                 kwargs.get("contact_phone",""), kwargs.get("security_level","S2A2G2"),
                 kwargs.get("notes",""), kwargs.get("status","ACTIVE"), now, now))
            conn.commit()
        return org_id
    def update_org(self, org_id, **kwargs):
        valid = ["org_name","org_type","parent_org_id","network_ranges","domain_name",
                 "contact_person","contact_phone","security_level","notes","status"]
        fields = [f"{k}=?" for k in kwargs if k in valid]
        values = [v for k,v in kwargs.items() if k in valid]
        if not fields: return False
        fields.append("updated_at=?")
        values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        values.append(org_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE organizations SET {','.join(fields)} WHERE org_id=?", values)
            conn.commit()
        return True
    def delete_org(self, org_id):
        with self._connect() as conn:
            # 1) 依赖 enterprise_profiles 的更名历史
            conn.execute("DELETE FROM name_change_history WHERE profile_id IN "
                         "(SELECT profile_id FROM enterprise_profiles WHERE org_id=?)", (org_id,))
            # 2) 外键引用 organizations 的业务表
            for tbl, col in [("enterprise_profiles","org_id"),("subsidiaries","parent_org_id"),
                ("identifier_index","org_id"),("icp_records","org_id"),
                ("rapid_assessments","org_id"),("leak_evidence","org_id"),
                ("exposures","org_id"),("scan_tasks","org_id"),
                ("org_clues","org_id")]:
                conn.execute(f"DELETE FROM {tbl} WHERE {col}=?", (org_id,))
            # 3) 无外键但含组织引用的表（顺带清理）
            for tbl, col in [("enterprise_relations","from_org_id"),
                             ("network_ranges","org_id"),
                             ("site_fingerprints","org_id"),
                             ("org_timeline_index","current_org_id")]:
                conn.execute(f"DELETE FROM {tbl} WHERE {col}=?", (org_id,))
            # 4) 最后删组织本身
            conn.execute("DELETE FROM organizations WHERE org_id=?", (org_id,))
            conn.commit()
    def get_org(self, org_id):
        with self._connect() as conn:
            return conn.execute("SELECT * FROM organizations WHERE org_id=?", (org_id,)).fetchone()
    def list_orgs(self, status=None):
        with self._connect() as conn:
            if status:
                return conn.execute("SELECT * FROM organizations WHERE status=? ORDER BY org_name", (status,)).fetchall()
            return conn.execute("SELECT * FROM organizations ORDER BY org_name").fetchall()
    def get_org_names(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT org_id, org_name FROM organizations WHERE status='ACTIVE' ORDER BY org_name").fetchall()
        return [(r["org_id"], r["org_name"]) for r in rows]

    # ===== 组织线索 (org_clues) =====
    def add_clue(self, org_id, clue_type, clue_value, source="", sort_order=0):
        clue_id = generate_id("CLU")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO org_clues
                (clue_id,org_id,clue_type,clue_value,source,sort_order,created_at)
                VALUES (?,?,?,?,?,?,?)''',
                (clue_id, org_id, clue_type, clue_value, source, sort_order, now))
            conn.commit()
        return clue_id

    def delete_clue(self, clue_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM org_clues WHERE clue_id=?", (clue_id,))
            conn.commit()

    def list_clues(self, org_id):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM org_clues WHERE org_id=? ORDER BY sort_order, created_at",
                (org_id,)).fetchall()

    def save_clues(self, org_id, clues):
        """整体替换组织的线索集合。clues: [{"type":..,"value":..}, ...]"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("DELETE FROM org_clues WHERE org_id=?", (org_id,))
            for i, c in enumerate(clues or []):
                t = (c.get("type") or "").strip()
                v = (c.get("value") or "").strip()
                if not t and not v: continue
                conn.execute('''INSERT INTO org_clues
                    (clue_id,org_id,clue_type,clue_value,source,sort_order,created_at)
                    VALUES (?,?,?,?,?,?,?)''',
                    (generate_id("CLU"), org_id, t, v, c.get("source",""), i, now))
            conn.commit()

    def get_org_clue_keywords(self, org_id):
        """返回组织用于精准搜索的线索关键词（去空去重）"""
        kws, seen = [], set()
        for c in self.list_clues(org_id):
            v = (c["clue_value"] or "").strip()
            if v and v not in seen:
                seen.add(v); kws.append(v)
        return kws
    def add_exposure_batch(self, exposures):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            for e in exposures:
                conn.execute('''INSERT INTO exposures
                    (exposure_id,org_id,asset_type,asset_name,asset_value,source,detail,risk_level,confidence,confidence_factors,discovered_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                    (generate_id("EXP"), e["org_id"], e.get("asset_type",""),
                     e.get("asset_name",""), e.get("asset_value",""),
                     e.get("source",""), e.get("detail",""),
                     e.get("risk_level","INFO"), e.get("confidence",0.5),
                     e.get("confidence_factors",""), now))
            conn.commit()
    def list_exposures(self, org_id=None, asset_type=None, risk_level=None, limit=500):
        sql = "SELECT * FROM exposures WHERE 1=1"
        params = []
        if org_id: sql += " AND org_id=?"; params.append(org_id)
        if asset_type: sql += " AND asset_type=?"; params.append(asset_type)
        if risk_level: sql += " AND risk_level=?"; params.append(risk_level)
        sql += " ORDER BY discovered_at DESC LIMIT ?"; params.append(limit)
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()
    def get_exposure_stats(self, org_id=None):
        sql = "SELECT risk_level, COUNT(*) as cnt FROM exposures WHERE 1=1"
        params = []
        if org_id: sql += " AND org_id=?"; params.append(org_id)
        sql += " GROUP BY risk_level"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        stats = {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0,"INFO":0,"total":0}
        for r in rows:
            if r["risk_level"] in stats:
                stats[r["risk_level"]] = r["cnt"]
            stats["total"] += r["cnt"]
        return stats
    def add_task(self, org_id, task_name, task_type, target_range, port_range=""):
        task_id = generate_id("TSK")
        with self._connect() as conn:
            conn.execute('''INSERT INTO scan_tasks
                (task_id,org_id,task_name,task_type,target_range,port_range,status,start_time)
                VALUES (?,?,?,?,?,?,?,?)''',
                (task_id, org_id, task_name, task_type, target_range, port_range,
                 "running", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        return task_id
    def update_task(self, task_id, **kwargs):
        valid = ["status","progress_pct","hosts_found","services_found","risks_found","end_time"]
        fields = [f"{k}=?" for k in kwargs if k in valid]
        values = [v for k,v in kwargs.items() if k in valid]
        if not fields: return
        values.append(task_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE scan_tasks SET {','.join(fields)} WHERE task_id=?", values)
            conn.commit()
    def list_tasks(self, org_id=None, limit=50):
        sql = """SELECT t.*, o.org_name FROM scan_tasks t
                 LEFT JOIN organizations o ON t.org_id=o.org_id WHERE 1=1"""
        params = []
        if org_id: sql += " AND t.org_id=?"; params.append(org_id)
        sql += " ORDER BY t.created_at DESC LIMIT ?"; params.append(limit)
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()
    def get_dashboard_stats(self):
        with self._connect() as conn:
            org_count = conn.execute("SELECT COUNT(*) FROM organizations WHERE status='ACTIVE'").fetchone()[0]
            exp_count = conn.execute("SELECT COUNT(*) FROM exposures").fetchone()[0]
            high_risk = conn.execute("SELECT COUNT(*) FROM exposures WHERE risk_level IN ('CRITICAL','HIGH')").fetchone()[0]
            task_count = conn.execute("SELECT COUNT(*) FROM scan_tasks").fetchone()[0]
        return {"org_count":org_count,"exp_count":exp_count,"high_risk":high_risk,"task_count":task_count}
    def log_query(self, query_type, query_text):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("INSERT INTO query_log (query_type, query_text, created_at) VALUES (?,?,?)",
                         (query_type, query_text, now))
            conn.commit()
    def get_query_trend(self, limit=10):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT substr(created_at,1,10) d, COUNT(*) c FROM query_log "
                "GROUP BY d ORDER BY d DESC LIMIT ?", (limit,)).fetchall()
        return [(r["d"], r["c"]) for r in reversed(rows)]
    def set_setting(self, key, value):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO system_settings (key,value) VALUES (?,?)", (key,value))
            conn.commit()
    def get_setting(self, key, default=""):
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM system_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    # ===== 浏览器登录凭证（Fernet 加密落库，走 CredentialStore）=====
    @property
    def credential_store(self):
        if self._credential_store is None:
            from core.credential_store import CredentialStore
            self._credential_store = CredentialStore(self)
        return self._credential_store

    def set_browser_cookie(self, site, cookie_str):
        self.credential_store.set_cookie(site, cookie_str)

    def get_browser_cookie(self, site):
        return self.credential_store.get_cookie(site)

    def set_browser_state(self, site, state_dict):
        self.credential_store.set_storage_state(site, state_dict)

    def get_browser_state(self, site):
        return self.credential_store.get_storage_state(site)

    # ===== 企业档案 (enterprise_profiles) =====
    def save_enterprise_profile(self, data):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pid = data.get("profile_id") or generate_id("EPF")
        with self._connect() as conn:
            existing = conn.execute("SELECT profile_id FROM enterprise_profiles WHERE profile_id=?", (pid,)).fetchone()
            if existing:
                cols = ["full_name","short_name","former_names","english_name","legal_person",
                    "shareholders","beneficial_owners","actual_controllers","key_executives",
                    "emails","phones","mobile_numbers","registered_address","business_scope",
                    "registered_capital","established_date","credit_code","source","last_updated"]
                sets = [f"{c}=?" for c in cols]
                vals = [dict_to_json(data.get(c,"")) for c in cols]
                vals.append(now); vals.append(pid)
                conn.execute(f"UPDATE enterprise_profiles SET {','.join(sets)},last_updated=? WHERE profile_id=?", vals)
            else:
                conn.execute('''INSERT INTO enterprise_profiles
                    (profile_id,org_id,sub_id,full_name,short_name,former_names,english_name,
                     legal_person,shareholders,beneficial_owners,actual_controllers,key_executives,
                     emails,phones,mobile_numbers,registered_address,business_scope,
                     registered_capital,established_date,credit_code,source,last_updated,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (pid, data.get("org_id",""), data.get("sub_id",""),
                     data.get("full_name",""), data.get("short_name",""),
                     dict_to_json(data.get("former_names","")), data.get("english_name",""),
                     data.get("legal_person",""), dict_to_json(data.get("shareholders","")),
                     dict_to_json(data.get("beneficial_owners","")),
                     dict_to_json(data.get("actual_controllers","")),
                     dict_to_json(data.get("key_executives","")),
                     dict_to_json(data.get("emails","")), dict_to_json(data.get("phones","")),
                     dict_to_json(data.get("mobile_numbers","")),
                     data.get("registered_address",""), data.get("business_scope",""),
                     data.get("registered_capital",""), data.get("established_date",""),
                     data.get("credit_code",""), data.get("source",""), now, now))
            conn.commit()
        return pid

    def get_enterprise_profile(self, profile_id=None, org_id=None):
        with self._connect() as conn:
            if profile_id:
                return conn.execute("SELECT * FROM enterprise_profiles WHERE profile_id=?", (profile_id,)).fetchone()
            if org_id:
                return conn.execute("SELECT * FROM enterprise_profiles WHERE org_id=?", (org_id,)).fetchone()
        return None

    def delete_enterprise_profile(self, profile_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM enterprise_profiles WHERE profile_id=?", (profile_id,))
            conn.execute("DELETE FROM identifier_index WHERE profile_id=?", (profile_id,))
            conn.execute("DELETE FROM name_change_history WHERE profile_id=?", (profile_id,))
            conn.commit()

    # ===== 子公司 =====
    def add_subsidiary(self, **kwargs):
        sub_id = kwargs.get("sub_id") or generate_id("SUB")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO subsidiaries
                (sub_id,parent_org_id,sub_name,equity_ratio,chain_level,relationship_type,
                 source,registered_address,legal_person,business_scope,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (sub_id, kwargs.get("parent_org_id",""), kwargs.get("sub_name",""),
                 kwargs.get("equity_ratio",0.0), kwargs.get("chain_level",1),
                 kwargs.get("relationship_type","holding"), kwargs.get("source",""),
                 kwargs.get("registered_address",""), kwargs.get("legal_person",""),
                 kwargs.get("business_scope",""), now))
            conn.commit()
        return sub_id

    def add_subsidiary_batch(self, subs):
        for s in subs: self.add_subsidiary(**s)

    def list_subsidiaries(self, parent_org_id=None, chain_level=None):
        with self._connect() as conn:
            sql, params = "SELECT * FROM subsidiaries WHERE 1=1", []
            if parent_org_id: sql += " AND parent_org_id=?"; params.append(parent_org_id)
            if chain_level is not None: sql += " AND chain_level=?"; params.append(chain_level)
            sql += " ORDER BY chain_level, equity_ratio DESC"
            return conn.execute(sql, params).fetchall()

    # ===== 企业关系 =====
    def add_relation(self, **kwargs):
        rid = kwargs.get("relation_id") or generate_id("REL")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO enterprise_relations
                (relation_id,from_org_id,from_profile_id,to_entity_name,to_entity_type,
                 relation_type,relation_detail,equity_ratio,chain_path,chain_level,confidence,source,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (rid, kwargs.get("from_org_id",""), kwargs.get("from_profile_id",""),
                 kwargs.get("to_entity_name",""), kwargs.get("to_entity_type","company"),
                 kwargs.get("relation_type",""), dict_to_json(kwargs.get("relation_detail","")),
                 kwargs.get("equity_ratio",0.0), kwargs.get("chain_path",""),
                 kwargs.get("chain_level",1), kwargs.get("confidence",0.5),
                 kwargs.get("source",""), now))
            conn.commit()
        return rid

    def list_relations(self, from_org_id=None, relation_type=None, limit=200):
        with self._connect() as conn:
            sql, params = "SELECT * FROM enterprise_relations WHERE 1=1", []
            if from_org_id: sql += " AND from_org_id=?"; params.append(from_org_id)
            if relation_type: sql += " AND relation_type=?"; params.append(relation_type)
            sql += " ORDER BY chain_level, confidence DESC LIMIT ?"; params.append(limit)
            return conn.execute(sql, params).fetchall()

    # ===== 标识符反向索引 =====
    def add_identifier(self, identifier_type, identifier_value, profile_id=None, org_id=None, source=""):
        if not identifier_value or not identifier_value.strip(): return None
        idx_id = generate_id("IDX")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            exist = conn.execute(
                "SELECT index_id FROM identifier_index WHERE identifier_type=? AND identifier_value=?",
                (identifier_type, identifier_value)).fetchone()
            if exist: return exist["index_id"]
            conn.execute('''INSERT INTO identifier_index
                (index_id,identifier_type,identifier_value,profile_id,org_id,source,created_at)
                VALUES (?,?,?,?,?,?,?)''',
                (idx_id, identifier_type, identifier_value, profile_id, org_id, source, now))
            conn.commit()
        return idx_id

    def add_identifier_batch(self, identifiers):
        for idf in identifiers:
            self.add_identifier(idf.get("type",""), idf.get("value",""),
                idf.get("profile_id"), idf.get("org_id"), idf.get("source",""))

    def resolve_identifier(self, identifier_value):
        with self._connect() as conn:
            return conn.execute('''SELECT i.*, p.full_name, p.short_name
                FROM identifier_index i
                LEFT JOIN enterprise_profiles p ON i.profile_id=p.profile_id
                WHERE i.identifier_value=?''', (identifier_value,)).fetchall()

    def get_all_identifiers_for_org(self, org_id):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM identifier_index WHERE org_id=? ORDER BY identifier_type",
                (org_id,)).fetchall()

    # ===== ICP备案 =====
    def add_icp_record(self, **kwargs):
        icp_id = kwargs.get("icp_id") or generate_id("ICP")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO icp_records
                (icp_id,org_id,sub_id,domain_name,icp_number,company_name,site_name,
                 site_homepage,approval_date,source,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (icp_id, kwargs.get("org_id",""), kwargs.get("sub_id",""),
                 kwargs.get("domain_name",""), kwargs.get("icp_number",""),
                 kwargs.get("company_name",""), kwargs.get("site_name",""),
                 kwargs.get("site_homepage",""), kwargs.get("approval_date",""),
                 kwargs.get("source","beian.miit.gov.cn"), now))
            conn.commit()
        return icp_id

    def list_icp_records(self, org_id=None, domain_name=None, limit=100):
        with self._connect() as conn:
            sql, params = "SELECT * FROM icp_records WHERE 1=1", []
            if org_id: sql += " AND org_id=?"; params.append(org_id)
            if domain_name: sql += " AND domain_name LIKE ?"; params.append(f"%{domain_name}%")
            sql += " ORDER BY created_at DESC LIMIT ?"; params.append(limit)
            return conn.execute(sql, params).fetchall()

    # ===== WHOIS =====
    def add_whois_record(self, **kwargs):
        wid = kwargs.get("whois_id") or generate_id("WHS")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO whois_records
                (whois_id,domain_name,registrar,creation_date,expiration_date,
                 registrant_org,registrant_email,name_servers,raw_text,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (wid, kwargs.get("domain_name",""), kwargs.get("registrar",""),
                 kwargs.get("creation_date",""), kwargs.get("expiration_date",""),
                 kwargs.get("registrant_org",""), kwargs.get("registrant_email",""),
                 kwargs.get("name_servers",""), kwargs.get("raw_text",""), now))
            conn.commit()
        return wid

    def get_whois(self, domain_name):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM whois_records WHERE domain_name=? ORDER BY created_at DESC",
                (domain_name,)).fetchone()

    # ===== IP段/ASN =====
    def add_network_range(self, **kwargs):
        rid = kwargs.get("range_id") or generate_id("NTR")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO network_ranges
                (range_id,org_id,sub_id,ip_range,asn_number,asn_name,isp,country,source,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (rid, kwargs.get("org_id",""), kwargs.get("sub_id",""),
                 kwargs.get("ip_range",""), kwargs.get("asn_number",""),
                 kwargs.get("asn_name",""), kwargs.get("isp",""),
                 kwargs.get("country",""), kwargs.get("source",""), now))
            conn.commit()
        return rid

    def list_network_ranges(self, org_id=None):
        with self._connect() as conn:
            if org_id:
                return conn.execute(
                    "SELECT * FROM network_ranges WHERE org_id=? ORDER BY ip_range", (org_id,)).fetchall()
            return conn.execute("SELECT * FROM network_ranges ORDER BY ip_range").fetchall()

    # ===== 网站指纹 =====
    def add_site_fingerprint(self, **kwargs):
        fid = kwargs.get("fingerprint_id") or generate_id("FP")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO site_fingerprints
                (fingerprint_id,org_id,domain,title,favicon_hash,tech_stack,header_signature,body_hashes,screenshot_path,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (fid, kwargs.get("org_id",""), kwargs.get("domain",""),
                 kwargs.get("title",""), kwargs.get("favicon_hash",""),
                 dict_to_json(kwargs.get("tech_stack","")),
                 kwargs.get("header_signature",""), kwargs.get("body_hashes",""),
                 kwargs.get("screenshot_path",""), now))
            conn.commit()
        return fid

    # ===== 数据泄露 =====
    def add_leak_evidence(self, **kwargs):
        lid = kwargs.get("leak_id") or generate_id("LEK")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO leak_evidence
                (leak_id,org_id,exposure_id,leak_category,leak_pattern,matched_content_snippet,source_url,confidence,severity,discovered_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (lid, kwargs.get("org_id",""), kwargs.get("exposure_id",""),
                 kwargs.get("leak_category",""), kwargs.get("leak_pattern",""),
                 kwargs.get("matched_content_snippet",""), kwargs.get("source_url",""),
                 kwargs.get("confidence",0.5), kwargs.get("severity","HIGH"), now))
            conn.commit()
        return lid

    def add_leak_batch(self, leaks):
        for lk in leaks: self.add_leak_evidence(**lk)

    def list_leak_evidence(self, org_id=None, leak_category=None, severity=None, limit=200):
        with self._connect() as conn:
            sql, params = "SELECT * FROM leak_evidence WHERE 1=1", []
            if org_id: sql += " AND org_id=?"; params.append(org_id)
            if leak_category: sql += " AND leak_category=?"; params.append(leak_category)
            if severity: sql += " AND severity=?"; params.append(severity)
            sql += " ORDER BY discovered_at DESC LIMIT ?"; params.append(limit)
            return conn.execute(sql, params).fetchall()

    # ===== 快速评估 =====
    def create_rapid_assessment(self, org_id, target_name):
        sid = generate_id("RAS")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO rapid_assessments
                (session_id,org_id,target_name,status,start_time)
                VALUES (?,?,?,?,?)''', (sid, org_id, target_name, "running", now))
            conn.commit()
        return sid

    def update_rapid_assessment(self, session_id, **kwargs):
        valid = ["status","end_time","subsidiaries_found","assets_found","leaks_found"]
        fields = [f"{k}=?" for k in kwargs if k in valid]
        values = [v for k,v in kwargs.items() if k in valid]
        if not fields: return
        values.append(session_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE rapid_assessments SET {','.join(fields)} WHERE session_id=?", values)
            conn.commit()

    def get_rapid_assessment(self, session_id):
        with self._connect() as conn:
            return conn.execute("SELECT * FROM rapid_assessments WHERE session_id=?", (session_id,)).fetchone()

    # ===== 更名历史 =====
    def add_name_change(self, **kwargs):
        cid = kwargs.get("change_id") or generate_id("NCH")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute('''INSERT INTO name_change_history
                (change_id,profile_id,org_id,old_name,new_name,change_date,change_reason,change_type,source,source_url,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (cid, kwargs.get("profile_id",""), kwargs.get("org_id",""),
                 kwargs.get("old_name",""), kwargs.get("new_name",""),
                 kwargs.get("change_date",""), kwargs.get("change_reason",""),
                 kwargs.get("change_type","rename"), kwargs.get("source",""),
                 kwargs.get("source_url",""), now))
            conn.commit()
        return cid

    def get_name_history(self, profile_id=None, org_id=None):
        with self._connect() as conn:
            if profile_id:
                return conn.execute(
                    "SELECT * FROM name_change_history WHERE profile_id=? ORDER BY change_date",
                    (profile_id,)).fetchall()
            if org_id:
                return conn.execute(
                    "SELECT * FROM name_change_history WHERE org_id=? ORDER BY change_date",
                    (org_id,)).fetchall()
        return []

    # ===== 机构沿革索引 =====
    def add_timeline_entry(self, keyword, current_org_id, current_name, timeline):
        idx_id = generate_id("OTI")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            exist = conn.execute(
                "SELECT index_id FROM org_timeline_index WHERE keyword=? AND current_org_id=?",
                (keyword, current_org_id)).fetchone()
            if exist: return exist["index_id"]
            conn.execute('''INSERT INTO org_timeline_index
                (index_id,keyword,current_org_id,current_name,timeline,created_at)
                VALUES (?,?,?,?,?,?)''',
                (idx_id, keyword, current_org_id, current_name, dict_to_json(timeline), now))
            conn.commit()
        return idx_id

    def resolve_timeline(self, keyword):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM org_timeline_index WHERE keyword=? ORDER BY created_at DESC",
                (keyword,)).fetchall()
