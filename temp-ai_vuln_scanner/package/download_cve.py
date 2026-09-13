#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CVE数据下载工具
从官方源下载完整的CVE数据
"""
import sys
import os
import json
import requests
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CVE API端点
CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def fetch_cve_by_year(year, max_results=2000):
    """按年份获取CVE"""
    results = []

    params = {
        'pubStartDate': f'{year}-01-01T00:00:00',
        'pubEndDate': f'{year+1}-01-01T00:00:00',
        'resultsPerPage': min(max_results, 2000)
    }

    try:
        resp = requests.get(CVE_API, params=params, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('vulnerabilities', [])
    except Exception as e:
        logger.error(f"获取{year}年失败: {e}")

    return results


def convert_cve_items(items):
    """转换CVE数据"""
    cve_list = []

    for item in items:
        try:
            cve = item.get('cve', {})
            cve_id = cve.get('id')

            # 描述
            descs = cve.get('descriptions', [])
            desc = ''
            for d in descs:
                if d.get('lang') == 'en':
                    desc = d.get('value', '')
                    break

            # CVSS
            cvss_score = None
            severity = 'UNKNOWN'
            metrics = cve.get('metrics', {})

            for key in ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']:
                if key in metrics and metrics[key]:
                    cvss = metrics[key][0].get('cvssData', {})
                    cvss_score = cvss.get('baseScore')
                    severity = cvss.get('baseSeverity', severity)
                    break

            # 发布时间
            published = cve.get('published', '')

            # 厂商/产品
            products = []
            configs = cve.get('configurations', [])
            for cfg in configs:
                for node in cfg.get('nodes', []):
                    for match in node.get('cpeMatch', []):
                        criteria = match.get('criteria', '')
                        if criteria:
                            parts = criteria.split(':')
                            if len(parts) >= 5:
                                products.append(f"{parts[3]}:{parts[4]}")

            cve_list.append({
                'cve_id': cve_id,
                'name': cve_id,
                'description': desc,
                'cvss_score': cvss_score,
                'severity': severity,
                'published_date': published[:10] if published else None,
                'modified_date': cve.get('lastModified', '')[:10] if cve.get('lastModified') else None,
                'affected_products': list(set(products))[:10],
                'references': [],
                'ai_analysis': None
            })

        except Exception as e:
            continue

    return cve_list


def download_year(year, db):
    """下载并导入指定年份的CVE"""
    print(f"[{year}年] 正在获取...")

    try:
        items = fetch_cve_by_year(year)
        if not items:
            print(f"  无数据")
            return 0

        cve_list = convert_cve_items(items)
        print(f"  获取 {len(cve_list)} 条")

        # 过滤已存在
        existing = db.search_cve(limit=100000)
        existing_ids = set(c['cve_id'] for c in existing)

        new_cves = [c for c in cve_list if c['cve_id'] not in existing_ids]
        print(f"  新增 {len(new_cves)} 条")

        if new_cves:
            count = db.add_cve_batch(new_cves)
            return count

    except Exception as e:
        print(f"  错误: {e}")

    return 0


def main():
    """主函数"""
    print("=" * 50)
    print("CVE官方数据下载工具")
    print("=" * 50)

    from database import VulnDatabase
    db = VulnDatabase('ai_vuln_scanner.db')

    stats = db.get_statistics()
    print(f"当前: {stats['total_cves']} 条CVE\n")

    # 下载近5年数据
    current_year = datetime.now().year
    total_new = 0

    for year in range(current_year, current_year - 5, -1):
        count = download_year(year, db)
        total_new += count
        time.sleep(1)  # 避免API限流

    # 统计
    stats = db.get_statistics()
    print("\n" + "=" * 50)
    print(f"新增: {total_new} 条")
    print(f"总量: {stats['total_cves']} 条")
    print("按严重程度:")
    for sev, count in stats.get('cve_by_severity', {}).items():
        print(f"  {sev}: {count}")


if __name__ == '__main__':
    main()