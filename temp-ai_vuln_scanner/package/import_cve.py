#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CVE数据批量导入工具
支持从本地JSON文件导入
"""
import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import VulnDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_severity(cvss):
    """解析CVSS"""
    try:
        score = float(str(cvss).replace('.', '').replace(' ', '')[:3])
        if score >= 9.0:
            return 'CRITICAL'
        elif score >= 7.0:
            return 'HIGH'
        elif score >= 4.0:
            return 'MEDIUM'
        elif score > 0:
            return 'LOW'
        else:
            return 'NONE'
    except:
        return 'UNKNOWN'


def import_from_file(filepath):
    """从JSON文件导入CVE"""
    print(f"正在读取: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    db = VulnDatabase('ai_vuln_scanner.db')

    # 获取已有CVE
    existing = db.search_cve(limit=100000)
    existing_ids = set(c['cve_id'] for c in existing)

    cve_list = []

    # 解析数据
    if isinstance(data, dict):
        # 查找CVE列表
        for key in data.keys():
            if isinstance(data[key], list):
                items = data[key]
                for item in items:
                    if isinstance(item, dict):
                        cve_id = item.get('CVE') or item.get('cve_id') or item.get('cve')
                        if cve_id and cve_id not in existing_ids:
                            cve_list.append(item)
                            existing_ids.add(cve_id)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cve_id = item.get('CVE') or item.get('cve_id')
                if cve_id and cve_id not in existing_ids:
                    cve_list.append(item)
                    existing_ids.add(cve_id)

    print(f"发现 {len(cve_list)} 条新CVE")

    # 转换格式
    converted = []
    for item in cve_list:
        cvss = item.get('CVSS', item.get('cvss_score', 0))
        cvss_score = None
        try:
            cvss_score = float(str(cvss).replace('.', '').replace(' ', '')[:3])
        except:
            pass

        cve_data = {
            'cve_id': item.get('CVE', item.get('cve_id', '')),
            'name': item.get('CVE', item.get('cve_id', '')),
            'description': item.get('描述', item.get('description', '')),
            'cvss_score': cvss_score,
            'severity': parse_severity(cvss),
            'published_date': item.get('发布时间', item.get('published', ''))[:10] if item.get('发布时间') else None,
            'modified_date': item.get('更新时间', item.get('modified', ''))[:10] if item.get('更新时间') else None,
            'affected_products': [item.get('厂商', item.get('product', ''))] if item.get('厂商') else [],
            'references': [item.get('链接', item.get('url', ''))] if item.get('链接') else [],
            'ai_analysis': f"状态: {item.get('状态', '')}"
        }

        if cve_data['cve_id']:
            converted.append(cve_data)

    # 批量导入
    if converted:
        count = db.add_cve_batch(converted)
        print(f"已导入 {count} 条CVE")

    # 统计
    stats = db.get_statistics()
    print(f"\n数据库总量: {stats['total_cves']} 条")
    print("按严重程度:")
    for sev, count in stats.get('cve_by_severity', {}).items():
        print(f"  {sev}: {count}")


if __name__ == '__main__':
    # 尝试导入本地漏洞库
    paths = [
        'D:/0有信网安/open claw/漏洞库.json',
        '../漏洞库.json',
        '../../漏洞库.json',
    ]

    for path in paths:
        if os.path.exists(path):
            import_from_file(path)
            break
    else:
        print("未找到漏洞库文件")
        print("可从以下地址下载CVE数据:")
        print("  - https://nvd.nist.gov/")
        print("  - https://www.cnnvd.org.cn/")
        print("  - https://cve.mitre.org/data/downloads/")