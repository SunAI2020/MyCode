#!/usr/bin/env python3
# 测试NVD API分页获取
import sys
sys.path.insert(0, 'd:/python files/ai_vuln_scanner')

from threat_intel import ThreatIntelCollector
from database import VulnDatabase

db = VulnDatabase('d:/python files/ai_vuln_scanner/ai_vuln_scanner.db')
collector = ThreatIntelCollector(db)

print("正在从NVD获取最近7天的CVE...")
cves = collector.fetch_recent_cve(days=7, max_results=500)
print(f"获取到 {len(cves)} 条CVE")

# 同步到数据库
print("正在同步到数据库...")
existing = db.search_cve(limit=10000)
existing_ids = set(c['cve_id'] for c in existing)

new_cves = [c for c in cves if c['cve_id'] not in existing_ids]
print(f"新CVE: {len(new_cves)} 条")

count = db.add_cve_batch(new_cves)
print(f"已添加 {count} 条")

# 统计
stats = db.get_statistics()
print(f"\n数据库统计: {stats}")