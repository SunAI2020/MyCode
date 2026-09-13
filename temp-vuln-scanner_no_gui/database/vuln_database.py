"""
漏洞数据库管理模块
负责 CVE 数据的存储、查询和管理
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .models import CVE, Severity
from config.settings import DATABASE

logger = logging.getLogger(__name__)


class VulnerabilityDatabase:
    """漏洞数据库管理类"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径，默认使用配置路径
        """
        self.db_path = db_path or str(DATABASE['path'])
        self._ensure_db_dir()
        self._init_database()
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建 CVE 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cve (
                cve_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                cvss_score REAL,
                severity TEXT,
                published_date TEXT,
                modified_date TEXT,
                cwe_id TEXT,
                exploit_available BOOLEAN DEFAULT 0,
                patch_available BOOLEAN DEFAULT 1
            )
        ''')
        
        # 创建受影响产品表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS affected_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT,
                product_name TEXT,
                product_version TEXT,
                FOREIGN KEY (cve_id) REFERENCES cve(cve_id)
            )
        ''')
        
        # 创建参考链接表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "references" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT,
                url TEXT,
                FOREIGN KEY (cve_id) REFERENCES cve(cve_id)
            )
        ''')
        
        # 创建修复建议表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fix_recommendations (
                cve_id TEXT PRIMARY KEY,
                recommendation TEXT,
                FOREIGN KEY (cve_id) REFERENCES cve(cve_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cve_severity ON cve(severity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cve_cvss ON cve(cvss_score)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_name ON affected_products(product_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_version ON affected_products(product_version)')
        
        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成：{self.db_path}")
    
    def add_cve(self, cve: CVE) -> bool:
        """
        添加单个 CVE 记录
        
        Args:
            cve: CVE 对象
            
        Returns:
            bool: 是否添加成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 插入 CVE 基本信息
            cursor.execute('''
                INSERT OR REPLACE INTO cve 
                (cve_id, name, description, cvss_score, severity, published_date, 
                 modified_date, cwe_id, exploit_available, patch_available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                cve.cve_id, cve.name, cve.description, cve.cvss_score,
                cve.severity.value, cve.published_date, cve.modified_date,
                cve.cwe_id, cve.exploit_available, cve.patch_available
            ))
            
            # 删除旧的关联数据
            cursor.execute('DELETE FROM affected_products WHERE cve_id = ?', (cve.cve_id,))
            cursor.execute('DELETE FROM "references" WHERE cve_id = ?', (cve.cve_id,))
            
            # 插入受影响产品
            for product in cve.affected_products:
                for version in cve.affected_versions:
                    cursor.execute('''
                        INSERT INTO affected_products (cve_id, product_name, product_version)
                        VALUES (?, ?, ?)
                    ''', (cve.cve_id, product, version))
            
            # 插入参考链接
            for ref in cve.references:
                cursor.execute('''
                    INSERT INTO "references" (cve_id, url)
                    VALUES (?, ?)
                ''', (cve.cve_id, ref))
            
            # 插入修复建议
            cursor.execute('''
                INSERT OR REPLACE INTO fix_recommendations (cve_id, recommendation)
                VALUES (?, ?)
            ''', (cve.cve_id, cve.fix_recommendation))
            
            conn.commit()
            conn.close()
            logger.debug(f"CVE 添加成功：{cve.cve_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加 CVE 失败 {cve.cve_id}: {e}")
            return False
    
    def add_cve_batch(self, cves: List[CVE]) -> int:
        """
        批量添加 CVE 记录
        
        Args:
            cves: CVE 对象列表
            
        Returns:
            int: 成功添加的数量
        """
        success_count = 0
        for cve in cves:
            if self.add_cve(cve):
                success_count += 1
        return success_count
    
    def get_cve(self, cve_id: str) -> Optional[CVE]:
        """
        查询单个 CVE
        
        Args:
            cve_id: CVE 编号
            
        Returns:
            Optional[CVE]: CVE 对象，不存在返回 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 查询 CVE 基本信息
        cursor.execute('SELECT * FROM cve WHERE cve_id = ?', (cve_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # 查询受影响产品
        cursor.execute('''
            SELECT product_name, product_version 
            FROM affected_products 
            WHERE cve_id = ?
        ''', (cve_id,))
        products_rows = cursor.fetchall()
        
        products = list(set([r[0] for r in products_rows]))
        versions = list(set([r[1] for r in products_rows]))
        
        # 查询参考链接
        cursor.execute('SELECT url FROM "references" WHERE cve_id = ?', (cve_id,))
        references = [r[0] for r in cursor.fetchall()]
        
        # 查询修复建议
        cursor.execute('SELECT recommendation FROM fix_recommendations WHERE cve_id = ?', (cve_id,))
        fix_row = cursor.fetchone()
        fix_recommendation = fix_row[0] if fix_row else ""
        
        conn.close()
        
        return CVE(
            cve_id=row[0],
            name=row[1],
            description=row[2],
            affected_products=products,
            affected_versions=versions,
            cvss_score=row[3],
            severity=Severity(row[4]),
            published_date=row[5],
            modified_date=row[6],
            references=references,
            fix_recommendation=fix_recommendation,
            cwe_id=row[7],
            exploit_available=bool(row[8]),
            patch_available=bool(row[9]),
        )
    
    def search_vulnerabilities(
        self,
        product: Optional[str] = None,
        severity: Optional[Severity] = None,
        min_cvss: Optional[float] = None,
        max_cvss: Optional[float] = None,
        version: Optional[str] = None,
        limit: int = 100
    ) -> List[CVE]:
        """
        搜索漏洞
        
        Args:
            product: 产品名称
            severity: 严重程度
            min_cvss: 最小 CVSS 分数
            max_cvss: 最大 CVSS 分数
            version: 版本号
            limit: 返回数量限制
            
        Returns:
            List[CVE]: 漏洞列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT DISTINCT c.cve_id, c.name, c.description, c.cvss_score, 
                   c.severity, c.published_date, c.modified_date, c.cwe_id,
                   c.exploit_available, c.patch_available
            FROM cve c
            LEFT JOIN affected_products ap ON c.cve_id = ap.cve_id
            WHERE 1=1
        '''
        params = []
        
        if product:
            query += ' AND ap.product_name LIKE ?'
            params.append(f'%{product}%')
        
        if severity:
            query += ' AND c.severity = ?'
            params.append(severity.value)
        
        if min_cvss is not None:
            query += ' AND c.cvss_score >= ?'
            params.append(min_cvss)
        
        if max_cvss is not None:
            query += ' AND c.cvss_score <= ?'
            params.append(max_cvss)
        
        if version:
            query += ' AND ap.product_version LIKE ?'
            params.append(f'%{version}%')
        
        query += ' ORDER BY c.cvss_score DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        cves = []
        for row in rows:
            cve_id = row[0]
            
            # 获取产品和版本
            cursor.execute('''
                SELECT product_name, product_version 
                FROM affected_products 
                WHERE cve_id = ?
            ''', (cve_id,))
            prod_rows = cursor.fetchall()
            products = list(set([r[0] for r in prod_rows]))
            versions = list(set([r[1] for r in prod_rows]))
            
            # 获取参考链接
            cursor.execute('SELECT url FROM "references" WHERE cve_id = ?', (cve_id,))
            references = [r[0] for r in cursor.fetchall()]
            
            # 获取修复建议
            cursor.execute('SELECT recommendation FROM fix_recommendations WHERE cve_id = ?', (cve_id,))
            fix_row = cursor.fetchone()
            fix_recommendation = fix_row[0] if fix_row else ""
            
            cves.append(CVE(
                cve_id=row[0],
                name=row[1],
                description=row[2],
                affected_products=products,
                affected_versions=versions,
                cvss_score=row[3],
                severity=Severity(row[4]),
                published_date=row[5],
                modified_date=row[6],
                references=references,
                fix_recommendation=fix_recommendation,
                cwe_id=row[7],
                exploit_available=bool(row[8]),
                patch_available=bool(row[9]),
            ))
        
        conn.close()
        return cves
    
    def match_vulnerability(
        self,
        product: str,
        version: str
    ) -> List[CVE]:
        """
        根据产品和版本匹配漏洞
        
        Args:
            product: 产品名称
            version: 版本号
            
        Returns:
            List[CVE]: 匹配的漏洞列表
        """
        return self.search_vulnerabilities(
            product=product,
            version=version,
            limit=1000
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            Dict: 统计信息
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # 总 CVE 数量
        cursor.execute('SELECT COUNT(*) FROM cve')
        stats['total_cves'] = cursor.fetchone()[0]
        
        # 按严重程度统计
        cursor.execute('''
            SELECT severity, COUNT(*) 
            FROM cve 
            GROUP BY severity
        ''')
        stats['by_severity'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 按年份统计
        cursor.execute('''
            SELECT strftime('%Y', published_date) as year, COUNT(*)
            FROM cve
            WHERE published_date IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        ''')
        stats['by_year'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 有利用代码的漏洞数量
        cursor.execute('SELECT COUNT(*) FROM cve WHERE exploit_available = 1')
        stats['with_exploit'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def load_from_json(self, json_path: str) -> int:
        """
        从 JSON 文件加载 CVE 数据
        
        Args:
            json_path: JSON 文件路径
            
        Returns:
            int: 成功加载的数量
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cves = [CVE.from_dict(item) for item in data]
        return self.add_cve_batch(cves)
    
    def export_to_json(self, output_path: str, limit: Optional[int] = None) -> int:
        """
        导出 CVE 数据到 JSON 文件
        
        Args:
            output_path: 输出文件路径
            limit: 导出数量限制
            
        Returns:
            int: 导出数量
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT cve_id FROM cve ORDER BY cvss_score DESC'
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query)
        cve_ids = [row[0] for row in cursor.fetchall()]
        
        cves = []
        for cve_id in cve_ids:
            cve = self.get_cve(cve_id)
            if cve:
                cves.append(cve.to_dict())
        
        conn.close()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cves, f, ensure_ascii=False, indent=2)
        
        return len(cves)
    
    def clear_database(self):
        """清空数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM "references"')
        cursor.execute('DELETE FROM fix_recommendations')
        cursor.execute('DELETE FROM affected_products')
        cursor.execute('DELETE FROM cve')
        
        conn.commit()
        conn.close()
        logger.info("数据库已清空")
