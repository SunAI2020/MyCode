#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量漏洞库更新脚本
获取2000年以来的所有CVE数据
"""
import sys
import os
import json
import time
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import VulnDatabase
from threat_intel import ThreatIntelCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_severity(cvss):
    """解析CVSS分数"""
    try:
        score = float(cvss)
        if score >= 9.0:
            return 'CRITICAL'
        elif score >= 7.0:
            return 'HIGH'
        elif score >= 4.0:
            return 'MEDIUM'
        else:
            return 'LOW'
    except:
        return 'UNKNOWN'


def fetch_all_cve():
    """获取所有CVE数据"""
    print("=" * 60)
    print("全量漏洞库更新")
    print("目标: 2000年至今所有CVE")
    print("=" * 60)

    db = VulnDatabase('ai_vuln_scanner.db')
    collector = ThreatIntelCollector(db)

    # 获取已有CVE数量
    stats = db.get_statistics()
    existing = stats.get('total_cves', 0)
    print(f"\n当前数据库: {existing} 条CVE")

    # 定义时间段获取
    periods = [
        ('最近7天', 7),
        ('最近30天', 30),
        ('最近90天', 90),
        ('最近180天', 180),
        ('最近1年', 365),
        ('最近2年', 730),
        ('最近3年', 1095),
    ]

    total_new = 0

    for period_name, days in periods:
        print(f"\n[{period_name}] 正在获取...")

        try:
            cves = collector.fetch_recent_cve(days=days, max_results=5000)

            if not cves:
                print(f"  无新数据")
                continue

            # 过滤已存在的CVE
            existing_cves = db.search_cve(limit=50000)
            existing_ids = set(c['cve_id'] for c in existing_cves)

            new_cves = [c for c in cves if c['cve_id'] not in existing_ids]
            print(f"  获取 {len(cves)} 条, 新增 {len(new_cves)} 条")

            # 批量添加
            if new_cves:
                count = db.add_cve_batch(new_cves)
                total_new += count
                print(f"  已添加 {count} 条")

        except Exception as e:
            logger.error(f"获取失败: {e}")
            continue

        # 避免API限流
        time.sleep(2)

    # 最终统计
    stats = db.get_statistics()
    print("\n" + "=" * 60)
    print("更新完成!")
    print(f"  原有: {existing} 条")
    print(f"  新增: {total_new} 条")
    print(f"  当前: {stats['total_cves']} 条")

    # 按严重程度统计
    print("\n按严重程度分布:")
    for sev, count in stats.get('cve_by_severity', {}).items():
        print(f"  {sev}: {count}")

    print("=" * 60)


def update_from_multiple_sources():
    """从多个数据源更新"""
    print("=" * 60)
    print("多数据源漏洞库更新")
    print("=" * 60)

    db = VulnDatabase('ai_vuln_scanner.db')
    collector = ThreatIntelCollector(db)

    # 获取2000年至今的数据
    start_year = 2000
    current_year = datetime.now().year

    total_added = 0

    # 按年份获取
    for year in range(current_year, start_year - 1, -1):
        print(f"\n[{year}年] 正在获取...")

        try:
            # 获取该年的CVE
            start_date = f"{year}-01-01T00:00:00"
            end_date = f"{year+1}-01-01T00:00:00"

            cves = collector.fetch_nvd_cve(
                pub_start_date=start_date,
                pub_end_date=end_date,
                max_results=5000
            )

            print(f"  获取 {len(cves)} 条")

            if cves:
                # 过滤已存在
                existing = db.search_cve(limit=100000)
                existing_ids = set(c['cve_id'] for c in existing)

                new_cves = [c for c in cves if c['cve_id'] not in existing_ids]

                if new_cves:
                    count = db.add_cve_batch(new_cves)
                    total_added += count
                    print(f"  新增 {count} 条")
                else:
                    print(f"  全部已存在")

        except Exception as e:
            print(f"  错误: {e}")
            continue

        time.sleep(1)

    # 最终统计
    stats = db.get_statistics()
    print("\n" + "=" * 60)
    print(f"总计: 新增 {total_added} 条")
    print(f"数据库总量: {stats['total_cves']} 条")
    print("=" * 60)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='全量漏洞库更新')
    parser.add_argument('--mode', default='quick', choices=['quick', 'full'],
                        help='更新模式: quick=增量, full=全量')
    args = parser.parse_args()

    if args.mode == 'full':
        update_from_multiple_sources()
    else:
        fetch_all_cve()