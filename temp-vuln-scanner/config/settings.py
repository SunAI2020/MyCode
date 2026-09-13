"""
配置文件 - 系统设置
版权所有：山西有信网安科技有限公司
"""
import os
from pathlib import Path

# 版本信息
VERSION = "1.0.0"
BUILD = "2026.03"
COMPANY = "山西有信网安科技有限公司"
COPYRIGHT = f"© 2026 {COMPANY}"

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库配置
DATABASE = {
    'path': BASE_DIR / 'data' / 'vuln_database.db',
    'cve_data_path': BASE_DIR / 'data' / 'cve_samples.json',
}

# 扫描配置
SCAN = {
    'default_timeout': 300,  # 默认扫描超时时间（秒）
    'max_concurrent_hosts': 10,  # 最大并发主机数
    'max_concurrent_ports': 100,  # 最大并发端口数
    'port_scan_technique': 'S',  # TCP SYN 扫描
    'version_detection': True,  # 版本检测
    'os_detection': True,  # 操作系统检测
    'common_ports': [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 3306, 3389, 5432, 8080, 8443],
    'full_port_range': (1, 65535),
}

# 报告配置
REPORT = {
    'output_dir': BASE_DIR / 'reports',
    'template_dir': BASE_DIR / 'templates',
    'formats': ['html', 'json', 'pdf'],
    'default_format': 'html',
}

# 日志配置
LOGGING = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': BASE_DIR / 'logs' / 'vuln_scanner.log',
}

# CVSS 严重程度阈值
CVSS_THRESHOLDS = {
    'CRITICAL': (9.0, 10.0),
    'HIGH': (7.0, 8.9),
    'MEDIUM': (4.0, 6.9),
    'LOW': (0.1, 3.9),
    'INFO': (0.0, 0.0),
}

# 法律合规
LEGAL = {
    'license_required': True,
    'disclaimer': '''
⚠️  法律免责声明
本工具仅用于授权的安全测试和漏洞评估。
使用前请确保：
1. 您拥有目标系统的所有权或已获得书面授权
2. 您的使用符合当地法律法规
3. 您了解并承担使用本工具的全部责任

未经授权扫描他人系统是违法行为！
''',
}
