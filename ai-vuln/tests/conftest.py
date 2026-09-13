# -*- coding: utf-8 -*-
"""pytest 共享 fixtures — 临时数据库注入"""
import os
import sys
import tempfile
import atexit
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEMP_FILES = []


def _cleanup_temp_files():
    import shutil
    for path in _TEMP_FILES:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                os.unlink(path)
        except Exception:
            pass


atexit.register(_cleanup_temp_files)


def _make_memory_connect():
    """创建自定义 _connect 函数，将所有数据库重定向到临时文件。"""
    import sqlite3
    tmpdir = tempfile.mkdtemp(prefix='ai_vuln_test_')
    _TEMP_FILES.append(tmpdir)

    def _connect(db_name):
        path = os.path.join(tmpdir, db_name)
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA temp_store=2")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    return _connect


@pytest.fixture
def patch_db_connect(monkeypatch):
    """核心 fixture：将 database._connect 替换为临时文件版本。"""
    import database
    mock_connect = _make_memory_connect()
    monkeypatch.setattr(database, '_connect', mock_connect)
    monkeypatch.setenv('SQLITE_TMPDIR', tempfile.mkdtemp(prefix='sqlite_tmp_'))
    return mock_connect


@pytest.fixture
def scan_db(patch_db_connect):
    from database import ScanResultsDB
    db = ScanResultsDB()
    yield db
    db.close()


@pytest.fixture
def cve_db(patch_db_connect):
    from database import CVEDatabase
    db = CVEDatabase()
    yield db
    db.close()


@pytest.fixture
def intel_db(patch_db_connect):
    from database import ThreatIntelDB
    db = ThreatIntelDB()
    yield db
    db.close()


@pytest.fixture
def audit_db(patch_db_connect):
    from database import AuditResultsDB
    db = AuditResultsDB()
    yield db
    db.close()


@pytest.fixture
def compliance_db(patch_db_connect):
    from database import ComplianceResultsDB
    db = ComplianceResultsDB()
    yield db
    db.close()


@pytest.fixture
def assets_db(patch_db_connect):
    from database import AssetsSystemDB
    db = AssetsSystemDB()
    yield db
    db.close()


@pytest.fixture
def db(patch_db_connect):
    """Database 门面类实例 — 最常用的 fixture。"""
    from database import Database
    database = Database()
    yield database
    database.close()


# ============================================================
# 测试数据工厂 fixtures
# ============================================================

@pytest.fixture
def sample_scan_task(db):
    task_id = db.create_task('192.168.1.1', 'quick', {'ports': '80,443'})
    return task_id


@pytest.fixture
def sample_scan_result(db, sample_scan_task):
    result = {
        'host': '192.168.1.1', 'port': 80, 'protocol': 'tcp',
        'state': 'open', 'service': 'http', 'version': 'Apache 2.4.41',
        'cve_id': 'CVE-2021-41733', 'cve_name': 'Apache Path Traversal',
        'cvss_score': 7.5, 'severity': 'HIGH',
        'description': 'Path traversal in Apache HTTP Server',
    }
    db.add_scan_result(sample_scan_task, result)
    return result


@pytest.fixture
def sample_cve_data():
    return [
        {'cve_id': 'CVE-2021-44228', 'name': 'Log4Shell',
         'description': 'RCE in Log4j', 'cvss_score': 10.0,
         'severity': 'CRITICAL', 'published_date': '2021-12-09',
         'modified_date': '2021-12-10',
         'affected_products': 'Apache Log4j 2.x',
         'references': 'https://nvd.nist.gov/vuln/detail/CVE-2021-44228',
         'cwe': 'CWE-502', 'patch_link': ''},
        {'cve_id': 'CVE-2021-41733', 'name': 'Apache Path Traversal',
         'description': 'Path traversal', 'cvss_score': 7.5,
         'severity': 'HIGH', 'published_date': '2021-10-05',
         'modified_date': '2021-10-06',
         'affected_products': 'Apache 2.4.49',
         'references': '', 'cwe': 'CWE-22', 'patch_link': ''},
        {'cve_id': 'CVE-2020-12345', 'name': 'Test Medium CVE',
         'description': 'Medium severity test', 'cvss_score': 5.5,
         'severity': 'MEDIUM', 'published_date': '2020-06-15',
         'modified_date': '2020-07-01',
         'affected_products': 'Test Product 1.0',
         'references': '', 'cwe': 'CWE-200', 'patch_link': ''},
    ]


@pytest.fixture
def sample_asset_data():
    return {
        'name': 'Web Server 01', 'ip': '192.168.1.100',
        'mac': 'AA:BB:CC:DD:EE:FF', 'type': 'SERVER',
        'os': 'Ubuntu 20.04', 'status': 'ACTIVE',
        'tags': 'production,web', 'owner': 'admin',
        'department': 'IT', 'location': 'Datacenter A',
        'importance': 'HIGH',
    }
