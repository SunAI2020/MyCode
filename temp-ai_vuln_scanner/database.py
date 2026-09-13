# -*- coding: utf-8 -*-
"""
AI Vuln Scanner Pro - 数据库模块
负责漏洞库、扫描任务、资产等数据的存储和管理
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VulnDatabase:
    """漏洞扫描系统数据库管理类"""

    def __init__(self, db_path: str = "ai_vuln_scanner.db"):
        """初始化数据库"""
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # CVE漏洞库表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cve (
                cve_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                cvss_score REAL,
                severity TEXT,
                published_date TEXT,
                modified_date TEXT,
                affected_products TEXT,
                references_url TEXT,
                ai_analysis TEXT,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 扫描任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                scan_type TEXT,
                status TEXT DEFAULT 'pending',
                start_time TEXT,
                end_time TEXT,
                vulnerabilities_found INTEGER DEFAULT 0,
                scan_config TEXT,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 扫描结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                host TEXT,
                port INTEGER,
                protocol TEXT,
                service TEXT,
                version TEXT,
                state TEXT,
                vulnerability_cve TEXT,
                vulnerability_name TEXT,
                severity TEXT,
                cvss_score REAL,
                description TEXT,
                recommendation TEXT,
                ai_analysis TEXT,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES scan_tasks(id)
            )
        ''')

        # 资产表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                hostname TEXT,
                mac_address TEXT,
                os TEXT,
                os_version TEXT,
                services TEXT,
                ports TEXT,
                risk_score REAL DEFAULT 0,
                last_scan_time TEXT,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # AI分析历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_type TEXT,
                target TEXT,
                result TEXT,
                vulnerabilities TEXT,
                ai_recommendation TEXT,
                risk_level TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 系统配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                update_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cve_severity ON cve(severity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cve_cvss ON cve(cvss_score)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cve_published ON cve(published_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_tasks_status ON scan_tasks(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_task ON scan_results(task_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_ip ON assets(ip)')

        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")

    def add_cve(self, cve_data: Dict) -> bool:
        """添加CVE记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO cve (
                    cve_id, name, description, cvss_score, severity,
                    published_date, modified_date, affected_products,
                    references_url, ai_analysis
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                cve_data.get('cve_id'),
                cve_data.get('name'),
                cve_data.get('description'),
                cve_data.get('cvss_score'),
                cve_data.get('severity'),
                cve_data.get('published_date'),
                cve_data.get('modified_date'),
                json.dumps(cve_data.get('affected_products', []), ensure_ascii=False),
                json.dumps(cve_data.get('references', []), ensure_ascii=False),
                cve_data.get('ai_analysis')
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加CVE失败: {e}")
            return False

    def add_cve_batch(self, cve_list: List[Dict]) -> int:
        """批量添加CVE"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        count = 0

        for cve_data in cve_list:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO cve (
                        cve_id, name, description, cvss_score, severity,
                        published_date, modified_date, affected_products,
                        references_url, ai_analysis
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cve_data.get('cve_id'),
                    cve_data.get('name'),
                    cve_data.get('description'),
                    cve_data.get('cvss_score'),
                    cve_data.get('severity'),
                    cve_data.get('published_date'),
                    cve_data.get('modified_date'),
                    json.dumps(cve_data.get('affected_products', []), ensure_ascii=False),
                    json.dumps(cve_data.get('references', []), ensure_ascii=False),
                    cve_data.get('ai_analysis')
                ))
                count += 1
            except Exception as e:
                logger.error(f"批量添加CVE失败: {e}")

        conn.commit()
        conn.close()
        return count

    def search_cve(self, keyword: str = None, severity: str = None,
                   min_cvss: float = None, limit: int = 100) -> List[Dict]:
        """搜索CVE"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM cve WHERE 1=1"
        params = []

        if keyword:
            query += " AND (cve_id LIKE ? OR name LIKE ? OR description LIKE ?)"
            params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])

        if severity:
            query += " AND severity = ?"
            params.append(severity)

        if min_cvss is not None:
            query += " AND cvss_score >= ?"
            params.append(min_cvss)

        query += " ORDER BY cvss_score DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'cve_id': row[0],
                'name': row[1],
                'description': row[2],
                'cvss_score': row[3],
                'severity': row[4],
                'published_date': row[5],
                'modified_date': row[6],
                'affected_products': json.loads(row[7]) if row[7] else [],
                'references': json.loads(row[8]) if row[8] else [],
                'ai_analysis': row[9]
            })

        conn.close()
        return results

    def create_task(self, target: str, scan_type: str, config: Dict = None) -> int:
        """创建扫描任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO scan_tasks (target, scan_type, status, scan_config)
            VALUES (?, ?, 'pending', ?)
        ''', (target, scan_type, json.dumps(config) if config else None))

        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def update_task_status(self, task_id: int, status: str,
                          vulnerabilities: int = 0, end_time: str = None):
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status == 'running':
            cursor.execute('''
                UPDATE scan_tasks SET status = ?, start_time = ?
                WHERE id = ?
            ''', (status, datetime.now().isoformat(), task_id))
        elif status in ['completed', 'failed']:
            cursor.execute('''
                UPDATE scan_tasks SET status = ?, end_time = ?,
                vulnerabilities_found = ? WHERE id = ?
            ''', (status, end_time or datetime.now().isoformat(), vulnerabilities, task_id))
        else:
            cursor.execute('UPDATE scan_tasks SET status = ? WHERE id = ?',
                         (status, task_id))

        conn.commit()
        conn.close()

    def add_scan_result(self, task_id: int, result: Dict) -> int:
        """添加扫描结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO scan_results (
                task_id, host, port, protocol, service, version, state,
                vulnerability_cve, vulnerability_name, severity, cvss_score,
                description, recommendation, ai_analysis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id,
            result.get('host'),
            result.get('port'),
            result.get('protocol'),
            result.get('service'),
            result.get('version'),
            result.get('state'),
            result.get('vulnerability_cve'),
            result.get('vulnerability_name'),
            result.get('severity'),
            result.get('cvss_score'),
            result.get('description'),
            result.get('recommendation'),
            result.get('ai_analysis')
        ))

        result_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return result_id

    def get_task_results(self, task_id: int) -> List[Dict]:
        """获取任务扫描结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM scan_results WHERE task_id = ? ORDER BY id', (task_id,))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'task_id': row[1],
                'host': row[2],
                'port': row[3],
                'protocol': row[4],
                'service': row[5],
                'version': row[6],
                'state': row[7],
                'vulnerability_cve': row[8],
                'vulnerability_name': row[9],
                'severity': row[10],
                'cvss_score': row[11],
                'description': row[12],
                'recommendation': row[13],
                'ai_analysis': row[14]
            })

        conn.close()
        return results

    def get_task_info(self, task_id: int) -> Optional[Dict]:
        """获取任务信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM scan_tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()

        if row:
            result = {
                'id': row[0],
                'target': row[1],
                'scan_type': row[2],
                'status': row[3],
                'start_time': row[4],
                'end_time': row[5],
                'vulnerabilities_found': row[6],
                'scan_config': json.loads(row[7]) if row[7] else None
            }
        else:
            result = None

        conn.close()
        return result

    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM scan_tasks ORDER BY id DESC')
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'target': row[1],
                'scan_type': row[2],
                'status': row[3],
                'start_time': row[4],
                'end_time': row[5],
                'vulnerabilities_found': row[6]
            })

        conn.close()
        return results

    def save_asset(self, asset_data: Dict) -> int:
        """保存资产"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO assets (
                ip, hostname, mac_address, os, os_version,
                services, ports, risk_score, last_scan_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            asset_data.get('ip'),
            asset_data.get('hostname'),
            asset_data.get('mac_address'),
            asset_data.get('os'),
            asset_data.get('os_version'),
            json.dumps(asset_data.get('services', []), ensure_ascii=False),
            json.dumps(asset_data.get('ports', []), ensure_ascii=False),
            asset_data.get('risk_score', 0),
            datetime.now().isoformat()
        ))

        asset_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return asset_id

    def get_assets(self) -> List[Dict]:
        """获取所有资产"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM assets ORDER BY risk_score DESC')
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'ip': row[1],
                'hostname': row[2],
                'mac_address': row[3],
                'os': row[4],
                'os_version': row[5],
                'services': json.loads(row[6]) if row[6] else [],
                'ports': json.loads(row[7]) if row[7] else [],
                'risk_score': row[8],
                'last_scan_time': row[9]
            })

        conn.close()
        return results

    def save_ai_analysis(self, analysis_data: Dict) -> int:
        """保存AI分析结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO ai_analysis_history (
                analysis_type, target, result, vulnerabilities,
                ai_recommendation, risk_level
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            analysis_data.get('analysis_type'),
            analysis_data.get('target'),
            analysis_data.get('result'),
            json.dumps(analysis_data.get('vulnerabilities', []), ensure_ascii=False),
            analysis_data.get('ai_recommendation'),
            analysis_data.get('risk_level')
        ))

        analysis_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return analysis_id

    def get_ai_analysis_history(self, limit: int = 50) -> List[Dict]:
        """获取AI分析历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM ai_analysis_history
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'analysis_type': row[1],
                'target': row[2],
                'result': row[3],
                'vulnerabilities': json.loads(row[4]) if row[4] else [],
                'ai_recommendation': row[5],
                'risk_level': row[6],
                'created_at': row[7]
            })

        conn.close()
        return results

    def save_setting(self, key: str, value: str, description: str = None):
        """保存设置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, description, update_time)
            VALUES (?, ?, ?, ?)
        ''', (key, value, description, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def get_setting(self, key: str, default=None) -> str:
        """获取设置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()

        conn.close()
        return row[0] if row else default

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # CVE统计
        cursor.execute('SELECT COUNT(*) FROM cve')
        stats['total_cves'] = cursor.fetchone()[0]

        cursor.execute('SELECT severity, COUNT(*) FROM cve GROUP BY severity')
        stats['cve_by_severity'] = {row[0]: row[1] for row in cursor.fetchall()}

        # 扫描任务统计
        cursor.execute('SELECT COUNT(*) FROM scan_tasks')
        stats['total_tasks'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM scan_tasks WHERE status = 'completed'")
        stats['completed_tasks'] = cursor.fetchone()[0]

        # 资产统计
        cursor.execute('SELECT COUNT(*) FROM assets')
        stats['total_assets'] = cursor.fetchone()[0]

        # 最近7天扫描次数
        cursor.execute('''
            SELECT COUNT(*) FROM scan_tasks
            WHERE start_time >= datetime('now', '-7 days')
        ''')
        stats['scans_last_7_days'] = cursor.fetchone()[0]

        conn.close()
        return stats


# 测试
if __name__ == '__main__':
    db = VulnDatabase('test_vuln.db')

    # 测试添加CVE
    test_cve = {
        'cve_id': 'CVE-2024-0001',
        'name': 'Test CVE',
        'description': 'Test vulnerability',
        'cvss_score': 9.8,
        'severity': 'CRITICAL',
        'published_date': '2024-01-01',
        'affected_products': ['Apache', 'Nginx'],
        'references': ['http://example.com'],
        'ai_analysis': 'This is a critical vulnerability'
    }
    db.add_cve(test_cve)

    # 测试搜索
    results = db.search_cve(severity='CRITICAL')
    print(f"Found {len(results)} critical CVEs")