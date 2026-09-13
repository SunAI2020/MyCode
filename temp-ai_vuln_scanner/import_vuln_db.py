#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入漏洞库到AI漏洞扫描系统
"""
import sys
import os
import json

# 添加AI漏洞扫描系统路径
sys.path.insert(0, 'd:/python files/ai_vuln_scanner')

from database import VulnDatabase

def parse_cvss(cvss_str):
    """安全解析CVSS分数"""
    try:
        if not cvss_str:
            return None
        # 提取数字部分
        import re
        match = re.search(r'(\d+\.?\d*)', str(cvss_str))
        if match:
            return float(match.group(1))
        return None
    except:
        return None

def parse_severity(cvss):
    """解析CVSS分数确定严重程度"""
    score = parse_cvss(cvss)
    if score is None:
        return 'UNKNOWN'
    if score >= 9.0:
        return 'CRITICAL'
    elif score >= 7.0:
        return 'HIGH'
    elif score >= 4.0:
        return 'MEDIUM'
    else:
        return 'LOW'

def import_vuln_db():
    """导入漏洞库"""

    # 读取JSON文件
    json_path = 'D:/0有信网安/open claw/漏洞库.json'

    print(f"正在读取: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"JSON keys: {list(data.keys())}")

    # 初始化数据库
    db = VulnDatabase('d:/python files/ai_vuln_scanner/ai_vuln_scanner.db')
    print("数据库初始化完成")

    total_imported = 0

    # 1. 提取高危漏洞
    high_risk = data.get('高危漏洞', [])
    print(f"高危漏洞数量: {len(high_risk)}")

    for item in high_risk:
        cve_id = item.get('CVE', '')
        if not cve_id:
            continue

        cvss = parse_cvss(item.get('CVSS', ''))

        cve_data = {
            'cve_id': cve_id,
            'name': cve_id,
            'description': item.get('描述', ''),
            'cvss_score': cvss,
            'severity': parse_severity(item.get('CVSS', '')),
            'published_date': item.get('发布时间', '')[:10] if item.get('发布时间') else None,
            'modified_date': item.get('发布时间', '')[:10] if item.get('发布时间') else None,
            'affected_products': [item.get('厂商', '')] if item.get('厂商') else [],
            'references': [f"https://nvd.nist.gov/vuln/detail/{cve_id}"],
            'ai_analysis': f"状态: {item.get('状态', '')}"
        }

        if db.add_cve(cve_data):
            total_imported += 1

    print(f"已导入 {total_imported} 条高危漏洞")

    # 2. 提取NVD 4周内的数据
    nvd_data = data.get('NVD 4 周内更新漏洞', [])
    if nvd_data:
        print(f"NVD 4周内更新: {len(nvd_data)}")

        for item in nvd_data[:2000]:  # 限制数量
            cve_id = item.get('CVE', '')
            if not cve_id:
                continue

            cvss = parse_cvss(item.get('CVSS', ''))

            cve_data = {
                'cve_id': cve_id,
                'name': cve_id,
                'description': item.get('描述', ''),
                'cvss_score': cvss,
                'severity': parse_severity(item.get('CVSS', '')),
                'published_date': item.get('发布时间', '')[:10] if item.get('发布时间') else None,
                'modified_date': item.get('更新时间', '')[:10] if item.get('更新时间') else None,
                'affected_products': [item.get('厂商', '')] if item.get('厂商') else [],
                'references': [f"https://nvd.nist.gov/vuln/detail/{cve_id}"],
                'ai_analysis': f"状态: {item.get('状态', '')}"
            }

            if db.add_cve(cve_data):
                total_imported += 1

    # 3. 提取软件包相关漏洞
    sw_vulns = data.get('软件包相关漏洞', [])
    if sw_vulns:
        print(f"软件包漏洞: {len(sw_vulns)}")

        for item in sw_vulns[:2000]:
            # 可能是列表格式
            if isinstance(item, list):
                cve_ids = item[0].get('CVE', []) if item and isinstance(item[0], dict) else []
                for cve_id in cve_ids[:10]:
                    cvss = parse_cvss(item[0].get('CVSS', ''))
                    cve_data = {
                        'cve_id': cve_id,
                        'name': cve_id,
                        'description': item[0].get('描述', ''),
                        'cvss_score': cvss,
                        'severity': parse_severity(item[0].get('CVSS', '')),
                        'published_date': item[0].get('发布时间', '')[:10] if item[0].get('发布时间') else None,
                        'modified_date': None,
                        'affected_products': [item[0].get('软件包', '')] if isinstance(item[0], dict) and item[0].get('软件包') else [],
                        'references': [f"https://nvd.nist.gov/vuln/detail/{cve_id}"],
                        'ai_analysis': f"严重性: {item[0].get('严重性', '')}"
                    }
                    if db.add_cve(cve_data):
                        total_imported += 1

    print(f"\n共导入 {total_imported} 条CVE漏洞")

    # 显示统计
    stats = db.get_statistics()
    print(f"\n=== 数据库统计 ===")
    print(f"CVE总数: {stats.get('total_cves', 0)}")
    print(f"按严重程度: {stats.get('cve_by_severity', {})}")


if __name__ == '__main__':
    import_vuln_db()