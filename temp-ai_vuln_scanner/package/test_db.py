import sys
sys.path.insert(0, r'D:\python files\ai_vuln_scanner')

try:
    from database import VulnDatabase
    db = VulnDatabase("test_db.db")
    print("数据库初始化成功!")
    
    # 测试添加CVE
    test_cve = {
        'cve_id': 'TEST-2024-001',
        'name': 'Test Vulnerability',
        'description': 'Test description',
        'cvss_score': 9.8,
        'severity': 'CRITICAL',
        'published_date': '2024-01-01',
        'affected_products': ['Apache', 'Nginx'],
        'references': ['http://example.com'],
        'ai_analysis': 'Test analysis'
    }
    
    if db.add_cve(test_cve):
        print("CVE添加成功!")
    else:
        print("CVE添加失败!")
        
    # 测试搜索
    results = db.search_cve(severity='CRITICAL')
    print(f"找到 {len(results)} 个严重漏洞")
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
