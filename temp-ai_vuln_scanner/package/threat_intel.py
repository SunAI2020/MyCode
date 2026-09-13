# -*- coding: utf-8 -*-
"""
AI Vuln Scanner Pro - 威胁情报模块
自动从NVD/CNVD等源收集漏洞情报
"""
import os
import json
import logging
import requests
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThreatIntelCollector:
    """威胁情报收集器 - 自动从网络获取CVE数据"""

    NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    NVD_API_KEY = os.environ.get('NVD_API_KEY', '')

    SOURCES = {
        'nvd': {'name': 'NVD', 'url': 'https://nvd.nist.gov/vuln/data-feeds'},
        'cnnvd': {'name': 'CNNVD', 'url': 'https://www.cnnvd.org.cn'},
    }

    def __init__(self, db_manager=None, api_key: str = None):
        self.db = db_manager
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AI-Vuln-Scanner-Pro/1.0', 'Accept': 'application/json'})
        self._update_thread = None
        self._stop_update = False
        logger.info("威胁情报收集器初始化完成")

    def fetch_nvd_cve(self, start_index: int = 0, results_per_page: int = 100,
                     pub_start_date: str = None, pub_end_date: str = None,
                     keyword: str = None, max_results: int = 2000) -> List[Dict]:
        """从NVD获取CVE数据，支持分页"""
        all_cves = []
        current_start = start_index
        total_limit = max_results

        while current_start < total_limit:
            batch_size = min(results_per_page, total_limit - current_start)

            params = {
                'startIndex': current_start,
                'resultsPerPage': batch_size
            }

            if pub_start_date:
                params['pubStartDate'] = pub_start_date
            if pub_end_date:
                params['pubEndDate'] = pub_end_date
            if keyword:
                params['keywordSearch'] = keyword

            headers = {}
            if self.NVD_API_KEY:
                headers['apiKey'] = self.NVD_API_KEY

            try:
                response = self.session.get(
                    self.NVD_API_URL,
                    params=params,
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    cves = self._parse_nvd_cve(data)

                    total_results = data.get('totalResults', 0)
                    if not cves or current_start + batch_size >= total_results:
                        all_cves.extend(cves)
                        break

                    all_cves.extend(cves)
                    current_start += batch_size
                    logger.info(f"已获取 {len(all_cves)} / {total_results} 条CVE...")
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"NVD API限流，等待 {retry_after} 秒后重试...")
                    time.sleep(retry_after)
                else:
                    logger.error(f"NVD API请求失败: {response.status_code}")
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"网络请求失败: {e}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"解析NVD CVE数据失败: {e}")
                break

            time.sleep(0.5)  # 避免API限流

        return all_cves

    def fetch_recent_cve(self, days: int = 7, max_results: int = 2000) -> List[Dict]:
        """获取最近N天的CVE"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        return self.fetch_nvd_cve(
            pub_start_date=start_date.isoformat(),
            pub_end_date=end_date.isoformat(),
            max_results=max_results
        )

    def _parse_nvd_cve(self, data: Dict) -> List[Dict]:
        """解析NVD API返回的数据"""
        cves = []

        if 'vulnerabilities' not in data:
            return cves

        for item in data['vulnerabilities']:
            try:
                cve_item = item.get('cve', {})
                cve_id = cve_item.get('id')

                descriptions = cve_item.get('descriptions', [])
                description = ''
                for desc in descriptions:
                    if desc.get('lang') == 'en':
                        description = desc.get('value', '')
                        break
                if not description and descriptions:
                    description = descriptions[0].get('value', '')

                cvss_score = None
                severity = 'UNKNOWN'
                metrics = cve_item.get('metrics', {})

                if 'cvssMetricV31' in metrics and metrics['cvssMetricV31']:
                    cvss_data = metrics['cvssMetricV31'][0].get('cvssData', {})
                    cvss_score = cvss_data.get('baseScore')
                    severity = cvss_data.get('baseSeverity', 'UNKNOWN')
                elif 'cvssMetricV30' in metrics and metrics['cvssMetricV30']:
                    cvss_data = metrics['cvssMetricV30'][0].get('cvssData', {})
                    cvss_score = cvss_data.get('baseScore')
                    severity = cvss_data.get('baseSeverity', 'UNKNOWN')
                elif 'cvssMetricV2' in metrics and metrics['cvssMetricV2']:
                    cvss_data = metrics['cvssMetricV2'][0].get('cvssData', {})
                    cvss_score = cvss_data.get('baseScore')
                    severity = cvss_data.get('baseSeverity', 'UNKNOWN')

                published = cve_item.get('published', '')
                modified = cve_item.get('lastModified', '')

                cves.append({
                    'cve_id': cve_id,
                    'name': cve_id,
                    'description': description,
                    'cvss_score': cvss_score,
                    'severity': severity,
                    'published_date': published[:10] if published else None,
                    'modified_date': modified[:10] if modified else None,
                    'affected_products': [],
                    'references': [],
                    'ai_analysis': None
                })
            except Exception as e:
                logger.error(f"解析CVE失败: {e}")
                continue

        return cves

    def sync_to_database(self, cves: List[Dict]) -> int:
        """同步CVE到数据库"""
        if not self.db:
            logger.warning("未配置数据库，跳过同步")
            return 0

        count = 0
        for cve in cves:
            if self.db.add_cve(cve):
                count += 1

        logger.info(f"同步完成: {count}/{len(cves)} 条CVE")
        return count

    def auto_update(self, interval_hours: int = 24):
        """启动自动更新任务"""
        def update_job():
            logger.info("开始自动更新漏洞库...")
            try:
                recent_cves = self.fetch_recent_cve(days=7, max_results=2000)
                if recent_cves:
                    count = self.sync_to_database(recent_cves)
                    logger.info(f"自动更新完成，新增 {count} 条CVE")
            except Exception as e:
                logger.error(f"自动更新失败: {e}")

        update_job()
        schedule.every(interval_hours).hours.do(update_job)

        def run_scheduler():
            while not self._stop_update:
                schedule.run_pending()
                time.sleep(60)

        self._update_thread = threading.Thread(target=run_scheduler, daemon=True)
        self._update_thread.start()
        logger.info(f"自动更新任务已启动，每 {interval_hours} 小时执行一次")

    def stop_auto_update(self):
        self._stop_update = True


class VulnMatcher:
    """漏洞匹配器"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.service_product_map = {
            'http': ['apache', 'nginx', 'iis'],
            'ssh': ['openssh', 'dropbear'],
            'ftp': ['vsftpd', 'proftpd'],
            'mysql': ['mysql', 'mariadb'],
            'postgresql': ['postgresql'],
            'redis': ['redis'],
            'mongodb': ['mongodb'],
        }

    def match_service_vulns(self, service: str, version: str = None) -> List[Dict]:
        if not self.db:
            return []

        service_lower = service.lower()
        products = self.service_product_map.get(service_lower, [service_lower])

        all_vulns = []
        for product in products:
            cves = self.db.search_cve(keyword=product, min_cvss=7.0, limit=20)
            all_vulns.extend(cves)

        seen = set()
        unique_vulns = []
        for cve in all_vulns:
            cve_id = cve['cve_id']
            if cve_id not in seen:
                seen.add(cve_id)
                unique_vulns.append(cve)

        return unique_vulns[:10]


if __name__ == '__main__':
    collector = ThreatIntelCollector()
    print("测试获取最近7天CVE...")
    cves = collector.fetch_recent_cve(days=7, max_results=500)
    print(f"获取到 {len(cves)} 条CVE")