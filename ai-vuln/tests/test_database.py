# -*- coding: utf-8 -*-
"""数据库层全面测试 — 5 个 DB 类 + Database 门面"""
import pytest


# ============================================================
# ScanResultsDB
# ============================================================
class TestScanResultsDB:
    def test_create_task(self, scan_db):
        tid = scan_db.create_task('192.168.1.1', 'quick', {'ports': '80,443'})
        assert tid > 0
        tasks = scan_db.get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0]['target'] == '192.168.1.1'
        assert tasks[0]['scan_type'] == 'quick'
        assert tasks[0]['status'] == 'running'

    def test_create_task_default_type(self, scan_db):
        tid = scan_db.create_task('10.0.0.1')
        tasks = scan_db.get_all_tasks()
        assert tasks[0]['scan_type'] == 'quick'

    def test_update_task_status_completed(self, scan_db):
        tid = scan_db.create_task('192.168.1.1')
        scan_db.update_task_status(tid, 'completed', vuln_count=5, error='')
        tasks = scan_db.get_all_tasks()
        assert tasks[0]['status'] == 'completed'
        assert tasks[0]['vuln_count'] == 5
        assert tasks[0]['end_time'] is not None

    def test_update_task_status_failed(self, scan_db):
        tid = scan_db.create_task('192.168.1.1')
        scan_db.update_task_status(tid, 'failed', error='Connection timeout')
        tasks = scan_db.get_all_tasks()
        assert tasks[0]['status'] == 'failed'
        assert 'timeout' in tasks[0]['error_message']

    def test_update_task_status_running(self, scan_db):
        tid = scan_db.create_task('192.168.1.1')
        scan_db.update_task_status(tid, 'running', vuln_count=3)
        tasks = scan_db.get_all_tasks()
        assert tasks[0]['status'] == 'running'
        assert tasks[0]['end_time'] is None

    def test_add_scan_result(self, scan_db):
        tid = scan_db.create_task('192.168.1.1')
        scan_db.add_scan_result(tid, {
            'host': '192.168.1.1', 'port': 443, 'service': 'https',
            'version': 'nginx 1.18', 'cve_id': 'CVE-2021-23017',
            'cvss_score': 7.5, 'severity': 'HIGH',
            'description': 'nginx DNS resolver vulnerability',
        })
        results = scan_db.get_task_results(tid)
        assert len(results) == 1
        assert results[0]['port'] == 443
        assert results[0]['severity'] == 'HIGH'

    def test_add_scan_result_defaults(self, scan_db):
        tid = scan_db.create_task('10.0.0.1')
        scan_db.add_scan_result(tid, {'host': '10.0.0.1', 'port': 22, 'service': 'ssh'})
        results = scan_db.get_task_results(tid)
        assert results[0]['protocol'] == 'tcp'
        assert results[0]['state'] == 'open'
        assert results[0]['severity'] == 'INFO'

    def test_get_all_tasks_limit(self, scan_db):
        for i in range(5):
            scan_db.create_task(f'10.0.0.{i}')
        tasks = scan_db.get_all_tasks(limit=3)
        assert len(tasks) == 3

    def test_get_all_tasks_desc_order(self, scan_db):
        scan_db.create_task('10.0.0.1')
        scan_db.create_task('10.0.0.2')
        tasks = scan_db.get_all_tasks()
        assert tasks[0]['id'] > tasks[1]['id']

    def test_get_task_results_empty(self, scan_db):
        assert scan_db.get_task_results(999) == []

    def test_get_task_results_only_own_task(self, scan_db):
        tid1 = scan_db.create_task('10.0.0.1')
        tid2 = scan_db.create_task('10.0.0.2')
        scan_db.add_scan_result(tid1, {'host': '10.0.0.1', 'port': 80, 'service': 'http'})
        scan_db.add_scan_result(tid2, {'host': '10.0.0.2', 'port': 443, 'service': 'https'})
        assert len(scan_db.get_task_results(tid1)) == 1

    def test_get_today_task_count(self, scan_db):
        initial = scan_db.get_today_task_count()
        scan_db.create_task('10.0.0.1')
        assert scan_db.get_today_task_count() == initial + 1

    def test_get_scan_type_counts(self, scan_db):
        scan_db.create_task('10.0.0.1', 'quick')
        scan_db.create_task('10.0.0.2', 'full')
        scan_db.create_task('10.0.0.3', 'quick')
        counts = scan_db.get_scan_type_counts()
        assert counts.get('quick', 0) == 2
        assert counts.get('full', 0) == 1

    def test_get_vuln_by_task(self, scan_db):
        tid = scan_db.create_task('192.168.1.0/24')
        scan_db.update_task_status(tid, 'completed')
        scan_db.add_scan_result(tid, {
            'host': '192.168.1.1', 'port': 80, 'severity': 'CRITICAL',
            'service': 'http', 'cve_id': 'CVE-TEST-001',
        })
        scan_db.add_scan_result(tid, {
            'host': '192.168.1.2', 'port': 443, 'severity': 'HIGH',
            'service': 'https', 'cve_id': 'CVE-TEST-002',
        })
        results = scan_db.get_vuln_by_task(limit=10)
        assert len(results) >= 1

    def test_clear_all(self, scan_db):
        tid = scan_db.create_task('10.0.0.1')
        scan_db.add_scan_result(tid, {'host': '10.0.0.1', 'port': 80, 'service': 'http'})
        scan_db.clear_all()
        assert len(scan_db.get_all_tasks()) == 0
        assert scan_db.get_statistics()['total_tasks'] == 0


# ============================================================
# CVEDatabase
# ============================================================
class TestCVEDatabase:
    def test_add_cve_batch(self, cve_db, sample_cve_data):
        count = cve_db.add_cve_batch(sample_cve_data)
        assert count == 3

    def test_add_cve_batch_upsert(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data[:1])
        updated = [{
            'cve_id': 'CVE-2021-44228', 'name': 'Log4Shell Updated',
            'description': 'Updated', 'cvss_score': 9.8,
            'severity': 'CRITICAL', 'published_date': '2021-12-09',
            'modified_date': '2022-01-01', 'affected_products': 'Log4j 2.x',
            'references': '', 'cwe': '', 'patch_link': '',
        }]
        cve_db.add_cve_batch(updated)
        results = cve_db.search_cve(keyword='Log4Shell')
        assert len(results) == 1
        assert results[0]['name'] == 'Log4Shell Updated'

    def test_search_cve_by_keyword_in_id(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        results = cve_db.search_cve(keyword='44228')
        assert len(results) == 1

    def test_search_cve_by_keyword_in_description(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        results = cve_db.search_cve(keyword='Log4j')
        assert len(results) >= 1

    def test_search_cve_by_keyword_in_products(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        results = cve_db.search_cve(keyword='Apache')
        assert len(results) >= 2

    def test_search_cve_by_min_cvss(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        results = cve_db.search_cve(min_cvss=8.0)
        assert len(results) == 1
        assert results[0]['cve_id'] == 'CVE-2021-44228'

    def test_search_cve_pagination(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        page1 = cve_db.search_cve(limit=2, offset=0)
        page2 = cve_db.search_cve(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) >= 1

    def test_count_cve(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        assert cve_db.count_cve() == 3
        assert cve_db.count_cve(keyword='Apache') >= 2
        assert cve_db.count_cve(min_cvss=9.0) == 1

    def test_search_cve_by_product(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        results = cve_db.search_cve_by_product('Log4j')
        assert len(results) >= 1

    def test_get_cve_by_severity(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        dist = cve_db.get_cve_by_severity()
        assert dist.get('CRITICAL', 0) >= 1
        assert dist.get('HIGH', 0) >= 1
        assert dist.get('MEDIUM', 0) >= 1

    def test_update_cvss_distribution(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        cve_db.update_cvss_distribution()
        stats = cve_db.get_statistics()
        assert stats['total_cves'] == 3

    def test_get_top_recent_cves(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        recent = cve_db.get_top_recent_cves(limit=10, days=9999)
        assert len(recent) >= 1
        assert recent[0]['cvss_score'] is not None

    def test_add_vendor_advisory(self, cve_db):
        aid = cve_db.add_vendor_advisory({
            'vendor': 'Apache', 'advisory_id': 'APACHE-2021-001',
            'cve_id': 'CVE-2021-44228', 'package_name': 'log4j',
            'severity': 'CRITICAL', 'status': 'Fixed',
            'published_date': '2021-12-10', 'description': 'Log4Shell advisory',
            'link': 'https://httpd.apache.org/security/',
        })
        assert aid > 0
        advisories = cve_db.get_vendor_advisories(vendor='Apache')
        assert len(advisories) == 1

    def test_empty_search(self, cve_db):
        assert cve_db.search_cve() == []

    def test_clear_all(self, cve_db, sample_cve_data):
        cve_db.add_cve_batch(sample_cve_data)
        cve_db.clear_all()
        assert cve_db.count_cve() == 0


# ============================================================
# ThreatIntelDB
# ============================================================
class TestThreatIntelDB:
    def test_default_feeds_seeded(self, intel_db):
        feeds = intel_db.get_enabled_feeds()
        assert len(feeds) >= 6

    def test_default_passwords_seeded(self, intel_db):
        assert intel_db.check_weak_password('admin', 'admin')

    def test_add_kev(self, intel_db):
        intel_db.add_kev({
            'cve_id': 'CVE-2021-44228', 'vulnerability_name': 'Log4Shell',
            'date_added': '2021-12-24', 'due_date': '2022-06-24',
            'required_action': 'Update Log4j to 2.17.0+',
            'known_ransomware': 1, 'notes': 'Actively exploited',
        })
        assert intel_db.is_kev('CVE-2021-44228')
        assert not intel_db.is_kev('CVE-9999-99999')

    def test_get_kev_list(self, intel_db):
        intel_db.add_kev({
            'cve_id': 'CVE-2021-44228', 'vulnerability_name': 'Log4Shell',
            'date_added': '2021-12-24', 'due_date': '2022-06-24',
            'required_action': 'Update', 'known_ransomware': 0, 'notes': '',
        })
        kev_list = intel_db.get_kev_list()
        assert len(kev_list) >= 1

    def test_add_epss(self, intel_db):
        intel_db.add_epss('CVE-2021-44228', 0.975, 0.999)
        epss = intel_db.get_epss('CVE-2021-44228')
        assert epss is not None
        assert epss['epss_score'] == 0.975
        assert epss['percentile'] == 0.999

    def test_get_epss_nonexistent(self, intel_db):
        assert intel_db.get_epss('CVE-DOES-NOT-EXIST') is None

    def test_add_threat_actor(self, intel_db):
        aid = intel_db.add_threat_actor({
            'name': 'APT29', 'aliases': 'Cozy Bear',
            'motivation': 'Espionage', 'target_sectors': 'Government',
            'known_tools': 'Cobalt Strike', 'associated_cves': 'CVE-2021-1234',
            'description': 'State-sponsored threat group',
            'first_seen': '2014-01-01', 'last_seen': '2024-01-01',
        })
        assert aid > 0
        actors = intel_db.get_threat_actors()
        assert len(actors) >= 1

    def test_add_ioc(self, intel_db):
        ioc_id = intel_db.add_ioc({
            'ioc_type': 'ip', 'ioc_value': '192.168.1.100',
            'threat_actor': 'APT29', 'malware_family': 'Cobalt Strike',
            'confidence': 'high', 'first_seen': '2024-01-01',
            'last_seen': '2024-06-01', 'source': 'OTX',
            'description': 'C2 server',
        })
        assert ioc_id > 0

    def test_add_ioc_duplicate(self, intel_db):
        intel_db.add_ioc({'ioc_type': 'domain', 'ioc_value': 'evil.com'})
        dup_id = intel_db.add_ioc({'ioc_type': 'domain', 'ioc_value': 'evil.com'})
        assert dup_id == -1

    def test_search_iocs(self, intel_db):
        intel_db.add_ioc({'ioc_type': 'ip', 'ioc_value': '10.0.0.99', 'source': 'test'})
        intel_db.add_ioc({'ioc_type': 'domain', 'ioc_value': 'evil.com', 'source': 'test'})
        assert len(intel_db.search_iocs(keyword='10.0.0')) == 1
        assert len(intel_db.search_iocs(ioc_type='domain')) == 1

    def test_add_attack_pattern(self, intel_db):
        intel_db.add_attack_pattern({
            'id': 'T1059', 'name': 'Command and Scripting Interpreter',
            'tactic': 'Execution', 'platform': 'Windows,Linux,macOS',
            'description': 'Execute commands/scripts',
            'detection': 'Monitor command-line', 'mitigation': 'App control',
        })
        patterns = intel_db.get_attack_patterns(tactic='Execution')
        assert len(patterns) >= 1

    def test_get_setting_default(self, intel_db):
        assert intel_db.get_setting('nonexistent', 'default_val') == 'default_val'

    def test_set_and_get_setting(self, intel_db):
        intel_db.set_setting('test_key', 'test_value')
        assert intel_db.get_setting('test_key') == 'test_value'

    def test_check_weak_password(self, intel_db):
        assert intel_db.check_weak_password('admin', 'admin')
        assert not intel_db.check_weak_password('stronguser', 'Str0ng!P@ss')

    def test_get_statistics(self, intel_db):
        stats = intel_db.get_statistics()
        for k in ['kev_count', 'ioc_count', 'actor_count']:
            assert k in stats

    def test_clear_all(self, intel_db):
        intel_db.add_kev({
            'cve_id': 'CVE-TEST', 'vulnerability_name': 'Test',
            'date_added': '2024-01-01', 'due_date': '2024-07-01',
            'required_action': 'None', 'known_ransomware': 0, 'notes': '',
        })
        intel_db.clear_all()
        assert intel_db.get_statistics()['kev_count'] == 0


# ============================================================
# AuditResultsDB
# ============================================================
class TestAuditResultsDB:
    def test_save_audit_with_issues(self, audit_db):
        result = {
            'target': 'D:/projects/test-app',
            'total_files_scanned': 10, 'total_vulnerabilities': 3,
            'risk_level': 'high_risk',
            'recommendation': 'Fix SQL injection immediately',
            'severity_summary': {'CRITICAL': 1, 'HIGH': 0, 'MEDIUM': 2, 'LOW': 0},
            'generated_at': '2026-08-08 12:00:00',
            'issues': [
                {'file': 'app.py', 'line': 42, 'category': 'SQL注入',
                 'severity': 'CRITICAL', 'code': 'execute(f"SELECT...")',
                 'recommendation': 'Use parameterized queries'},
            ],
        }
        audit_id = audit_db.save_audit(result)
        assert audit_id > 0
        history = audit_db.get_history()
        assert len(history) == 1
        assert history[0]['risk_level'] == 'high_risk'
        assert len(history[0]['issues']) == 1

    def test_save_audit_empty_issues(self, audit_db):
        result = {
            'target': 'D:/projects/safe-app', 'total_files_scanned': 5,
            'total_vulnerabilities': 0, 'risk_level': 'safe',
            'recommendation': '', 'severity_summary': {},
            'generated_at': '2026-08-08 12:00:00', 'issues': [],
        }
        assert audit_db.save_audit(result) > 0

    def test_get_audit_by_task(self, audit_db):
        result = {
            'target': 'D:/projects/app', 'total_files_scanned': 3,
            'total_vulnerabilities': 2, 'risk_level': 'medium_risk',
            'recommendation': '', 'severity_summary': {},
            'generated_at': '2026-08-08',
            'issues': [
                {'file': 'a.py', 'line': 1, 'category': 'SQL注入',
                 'severity': 'CRITICAL', 'code': 'x', 'recommendation': 'x'},
            ],
        }
        audit_db.save_audit(result)
        chart = audit_db.get_audit_by_task(limit=10)
        assert len(chart) >= 1

    def test_get_statistics(self, audit_db):
        stats = audit_db.get_statistics()
        assert 'total_audits' in stats

    def test_clear_all(self, audit_db):
        audit_db.save_audit({
            'target': 'test', 'total_files_scanned': 1,
            'total_vulnerabilities': 1, 'risk_level': 'test',
            'recommendation': '', 'severity_summary': {},
            'generated_at': '', 'issues': [],
        })
        audit_db.clear_all()
        assert audit_db.get_statistics()['total_audits'] == 0


# ============================================================
# AssetsSystemDB
# ============================================================
class TestAssetsSystemDB:
    def test_add_asset(self, assets_db, sample_asset_data):
        aid = assets_db.add_asset(sample_asset_data)
        assert aid > 0
        asset = assets_db.get_asset(aid)
        assert asset['name'] == 'Web Server 01'

    def test_add_asset_duplicate_ip_mac(self, assets_db, sample_asset_data):
        assets_db.add_asset(sample_asset_data)
        assert assets_db.add_asset(sample_asset_data) == -1

    def test_add_asset_with_url(self, assets_db):
        aid = assets_db.add_asset({'name': 'Web 站点', 'ip': '10.0.0.5',
                                   'url': 'https://example.com', 'type': 'WEB'})
        assert assets_db.get_asset(aid)['url'] == 'https://example.com'

    def test_update_asset_url(self, assets_db):
        aid = assets_db.add_asset({'name': 'A', 'ip': '10.0.0.6', 'url': 'https://old.com'})
        assets_db.update_asset(aid, {'url': 'https://new.com'})
        assert assets_db.get_asset(aid)['url'] == 'https://new.com'

    def test_get_asset_nonexistent(self, assets_db):
        assert assets_db.get_asset(999) is None

    def test_get_assets_with_filters(self, assets_db):
        assets_db.add_asset({'name': 'A', 'ip': '10.0.0.1', 'type': 'SERVER', 'status': 'ACTIVE', 'importance': 'HIGH'})
        assets_db.add_asset({'name': 'B', 'ip': '10.0.0.2', 'type': 'PRINTER', 'status': 'INACTIVE', 'importance': 'LOW'})
        assert len(assets_db.get_assets(filters={'type': 'SERVER'})) == 1
        assert len(assets_db.get_assets(filters={'keyword': '10.0.0.1'})) == 1

    def test_get_assets_default(self, assets_db):
        assert assets_db.get_assets() == []

    def test_update_asset(self, assets_db):
        aid = assets_db.add_asset({'name': 'Old', 'ip': '10.0.0.1', 'type': 'SERVER'})
        assets_db.update_asset(aid, {'name': 'New', 'status': 'INACTIVE'})
        updated = assets_db.get_asset(aid)
        assert updated['name'] == 'New'
        assert updated['status'] == 'INACTIVE'

    def test_update_asset_illegal_column_rejected(self, assets_db):
        aid = assets_db.add_asset({'name': 'Test', 'ip': '10.0.0.1'})
        assets_db.update_asset(aid, {'name': 'Safe', 'hacked_column': 'evil'})
        assert assets_db.get_asset(aid)['name'] == 'Safe'

    def test_delete_asset(self, assets_db):
        aid = assets_db.add_asset({'name': 'To Delete', 'ip': '10.0.0.99'})
        assets_db.delete_asset(aid)
        assert assets_db.get_asset(aid) is None

    def test_get_asset_count(self, assets_db):
        assert assets_db.get_asset_count() == 0
        assets_db.add_asset({'name': 'A', 'ip': '10.0.0.1'})
        assert assets_db.get_asset_count() == 1

    def test_get_asset_type_counts(self, assets_db):
        assets_db.add_asset({'name': 'A', 'ip': '10.0.0.1', 'type': 'SERVER'})
        assets_db.add_asset({'name': 'B', 'ip': '10.0.0.2', 'type': 'SERVER'})
        assets_db.add_asset({'name': 'C', 'ip': '10.0.0.3', 'type': 'WORKSTATION'})
        counts = assets_db.get_asset_type_counts()
        assert counts.get('SERVER', 0) == 2

    def test_save_and_get_reports(self, assets_db):
        rid = assets_db.save_report('Scan Report', 'scan', 'html', '<html></html>', 'reports/s.html', task_id=1)
        assert rid > 0
        assert len(assets_db.get_reports()) == 1

    def test_delete_report(self, assets_db):
        rid = assets_db.save_report('Test', 'scan', 'html', '', 'reports/test.html')
        assert assets_db.delete_report(rid) == 1
        assert assets_db.delete_report(999) == 0

    def test_default_settings_seeded(self, assets_db):
        assert assets_db.get_setting('company_name') == '山西有信网安科技有限公司'
        assert assets_db.get_setting('app_version') == '2.0.0'

    def test_set_and_get_setting(self, assets_db):
        assets_db.set_setting('custom_key', 'custom_value')
        assert assets_db.get_setting('custom_key') == 'custom_value'

    def test_get_setting_default(self, assets_db):
        assert assets_db.get_setting('nonexistent', 'fallback') == 'fallback'

    def test_add_audit_log(self, assets_db):
        assets_db.add_audit_log('scan_started', 'scan_task', 1, 'User initiated scan')

    def test_clear_all(self, assets_db):
        assets_db.add_asset({'name': 'A', 'ip': '10.0.0.1'})
        assets_db.save_report('R', 'scan', 'html', '', 'r.html')
        assets_db.clear_all()
        assert assets_db.get_asset_count() == 0
        assert len(assets_db.get_reports()) == 0


# ============================================================
# Database 门面类
# ============================================================
class TestDatabaseFacade:
    def test_all_sub_dbs_initialized(self, db):
        for attr in ['scan', 'cve', 'intel', 'audit', 'assets']:
            assert getattr(db, attr) is not None

    def test_delegation_create_task(self, db):
        tid = db.create_task('10.0.0.1', 'full')
        assert len(db.get_all_tasks()) == 1

    def test_delegation_update_task_status(self, db):
        tid = db.create_task('10.0.0.1')
        db.update_task_status(tid, 'completed', vuln_count=3)
        assert db.get_all_tasks()[0]['status'] == 'completed'

    def test_delegation_add_scan_result(self, db):
        tid = db.create_task('10.0.0.1')
        db.add_scan_result(tid, {'host': '10.0.0.1', 'port': 80, 'service': 'http'})
        assert len(db.get_task_results(tid)) == 1

    def test_delegation_search_cve(self, db):
        db.add_cve_batch([{
            'cve_id': 'CVE-2024-0001', 'name': 'Test', 'description': 'Test',
            'cvss_score': 7.0, 'severity': 'HIGH',
            'published_date': '2024-01-01', 'modified_date': '2024-01-02',
            'affected_products': 'Test', 'references': '', 'cwe': '', 'patch_link': '',
        }])
        assert len(db.search_cve(keyword='2024')) == 1

    def test_delegation_assets_crud(self, db, sample_asset_data):
        aid = db.add_asset(sample_asset_data)
        assert aid > 0
        assert db.get_asset(aid) is not None
        db.update_asset(aid, {'name': 'Updated'})
        assert db.get_asset(aid)['name'] == 'Updated'
        db.delete_asset(aid)
        assert db.get_asset(aid) is None

    def test_delegation_reports(self, db):
        rid = db.save_report('Test', 'scan', 'html', '', 'test.html')
        assert rid > 0
        assert len(db.get_reports()) == 1
        db.delete_report(rid)
        assert len(db.get_reports()) == 0

    def test_delegation_settings(self, db):
        db.set_setting('test', 'value')
        assert db.get_setting('test') == 'value'

    def test_delegation_intel(self, db):
        stats = db.get_intel_statistics()
        assert 'kev_count' in stats

    def test_get_statistics(self, db):
        stats = db.get_statistics()
        for k in ['total_cves', 'total_assets', 'total_tasks', 'total_vulns', 'critical_count']:
            assert k in stats

    def test_get_comprehensive_intel_stats(self, db):
        stats = db.get_comprehensive_intel_stats()
        for k in ['cve', 'intel', 'top_cves']:
            assert k in stats

    def test_clear_database(self, db):
        db.create_task('10.0.0.1')
        db.add_asset({'name': 'A', 'ip': '10.0.0.1'})
        db.clear_database()
        assert db.get_statistics()['total_tasks'] == 0

    def test_conn_property(self, db):
        assert db.conn is not None

    def test_dashboard_chart_methods(self, db):
        assert db.get_asset_type_counts() == {}
        assert db.get_scan_type_counts() == {}
        assert isinstance(db.get_today_status_counts(), dict)
        assert db.get_vuln_by_task() == []
        assert db.get_audit_by_task() == []

    def test_full_scan_workflow(self, db):
        """端到端扫描工作流"""
        tid = db.create_task('192.168.1.0/24', 'full', {'ports': '1-1000'})
        db.add_scan_result(tid, {
            'host': '192.168.1.1', 'port': 22, 'service': 'ssh',
            'version': 'OpenSSH 8.9', 'severity': 'LOW',
        })
        db.add_scan_result(tid, {
            'host': '192.168.1.1', 'port': 443, 'service': 'https',
            'version': 'nginx 1.18', 'cve_id': 'CVE-2021-23017',
            'cvss_score': 7.5, 'severity': 'HIGH',
        })
        db.update_task_status(tid, 'completed', vuln_count=2)
        assert db.get_all_tasks()[0]['status'] == 'completed'
        assert len(db.get_task_results(tid)) == 2
