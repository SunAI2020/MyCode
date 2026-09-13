#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CVE 数据合并脚本
将新的 CVE 数据添加到漏洞库中
版权所有：山西有信网安科技有限公司
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import VulnerabilityDatabase

def merge_cve_data():
    """合并 CVE 数据到漏洞库"""
    
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    
    # 现有 CVE 数据文件
    existing_file = data_dir / 'cve_samples.json'
    # 新增 CVE 数据文件
    additional_file = data_dir / 'cve_additional.json'
    # 合并后的输出文件
    output_file = data_dir / 'cve_samples_merged.json'
    
    print("="*60)
    print("  CVE 数据合并工具")
    print("  © 山西有信网安科技有限公司")
    print("="*60)
    print()
    
    # 加载现有 CVE 数据
    existing_cves = []
    if existing_file.exists():
        with open(existing_file, 'r', encoding='utf-8') as f:
            existing_cves = json.load(f)
        print(f"✓ 已加载现有 CVE 数据：{len(existing_cves)} 条")
    else:
        print("✗ 未找到现有 CVE 数据文件")
        return
    
    # 加载新增 CVE 数据
    additional_cves = []
    if additional_file.exists():
        with open(additional_file, 'r', encoding='utf-8') as f:
            additional_cves = json.load(f)
        print(f"✓ 已加载新增 CVE 数据：{len(additional_cves)} 条")
    else:
        print("✗ 未找到新增 CVE 数据文件")
        return
    
    # 创建 CVE ID 集合用于去重
    existing_ids = {cve['cve_id'] for cve in existing_cves}
    
    # 合并数据（去重）
    merged_cves = existing_cves.copy()
    added_count = 0
    skipped_count = 0
    
    for cve in additional_cves:
        if cve['cve_id'] not in existing_ids:
            merged_cves.append(cve)
            added_count += 1
        else:
            skipped_count += 1
            print(f"  - 跳过重复：{cve['cve_id']}")
    
    print()
    print(f"✓ 新增 CVE: {added_count} 条")
    print(f"✓ 跳过重复：{skipped_count} 条")
    print(f"✓ 合并后总计：{len(merged_cves)} 条")
    print()
    
    # 按 CVE 年份和编号排序
    merged_cves.sort(key=lambda x: x['cve_id'])
    
    # 统计严重程度
    severity_stats = {}
    for cve in merged_cves:
        sev = cve['severity']
        severity_stats[sev] = severity_stats.get(sev, 0) + 1
    
    print("📊 严重程度统计:")
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = severity_stats.get(sev, 0)
        print(f"  {sev}: {count}")
    print()
    
    # 保存合并后的数据
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_cves, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 合并数据已保存到：{output_file}")
    print()
    
    # 询问是否替换原文件
    response = input("是否替换原有 CVE 数据文件？(yes/no): ")
    if response.lower() in ['yes', 'y']:
        # 备份原文件
        backup_file = existing_file.with_suffix('.json.bak')
        existing_file.rename(backup_file)
        print(f"✓ 已备份原文件到：{backup_file}")
        
        # 替换文件
        output_file.rename(existing_file)
        print(f"✓ 已更新 CVE 数据文件：{existing_file}")
        
        # 删除临时文件
        output_file.unlink(missing_ok=True)
    else:
        print("⚠️  保留原文件，合并结果保存在：", output_file)
    
    print()
    print("="*60)
    print("  合并完成!")
    print("="*60)
    
    return len(merged_cves)


def update_database():
    """更新 SQLite 数据库"""
    
    print()
    print("正在更新 SQLite 数据库...")
    print()
    
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'data' / 'vuln_database.db'
    cve_data_path = base_dir / 'data' / 'cve_samples.json'
    
    # 创建数据库实例
    db = VulnerabilityDatabase(str(db_path))
    
    # 加载 CVE 数据
    with open(cve_data_path, 'r', encoding='utf-8') as f:
        cve_data = json.load(f)
    
    # 导入到数据库
    count = db.load_from_json(str(cve_data_path))
    
    print(f"✓ 数据库已更新：{count} 条 CVE 记录")
    
    # 显示统计
    stats = db.get_statistics()
    print()
    print("📊 数据库统计:")
    print(f"  总 CVE 数：{stats['total_cves']}")
    print(f"  严重：{stats['by_severity'].get('CRITICAL', 0)}")
    print(f"  高危：{stats['by_severity'].get('HIGH', 0)}")
    print(f"  中危：{stats['by_severity'].get('MEDIUM', 0)}")
    print(f"  低危：{stats['by_severity'].get('LOW', 0)}")
    
    return count


if __name__ == '__main__':
    total = merge_cve_data()
    if total > 0:
        update_database()
    else:
        print("⚠️  没有新数据需要合并")
