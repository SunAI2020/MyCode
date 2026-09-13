# -*- coding: utf-8 -*-
"""星海EASM 系统配置"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SYSTEM_DB_PATH = os.path.join(DATA_DIR, "exposure_system.db")
CACHE_DB_PATH = os.path.join(DATA_DIR, "cache.db")
CVE_DB_PATH = os.path.join(DATA_DIR, "cve_database.db")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

APP_NAME = "睿思慧眼互联网资产管理系统"
APP_VERSION = "1.0.0"
COMPANY_NAME = "山西有信网安科技有限公司"
COPYRIGHT = f"Copyright (C) {COMPANY_NAME} 版权所有"
LOGO_PATH = os.path.join(BASE_DIR, "logo.jpg")
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
FULLSCREEN = True

# ===== API Key 配置 =====
API_KEYS = {
    "shodan": "", "securitytrails": "", "github": "",
    "whoisxmlapi": "", "hunter": "", "alienvault_otx": "", "bgpview": "",
    "fofa": "", "quake": "", "qianxin_hunter": "",
    "censys_id": "", "censys_secret": "", "zoomeye": "",
    "gitee": "", "gitlab": "",
    "tianyancha_token": "", "aiqicha_cookie": "",
}
API_ENDPOINTS = {
    "crtsh": "https://crt.sh/?q=%25.{domain}&output=json",
    "bgpview_ip": "https://api.bgpview.io/ip/{ip}",
    "bgpview_asn": "https://api.bgpview.io/asn/{asn}",
    "alienvault_otx": "https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns",
    "shodan_host": "https://api.shodan.io/shodan/host/{ip}?key={key}",
    "securitytrails_domain": "https://api.securitytrails.com/v1/domain/{domain}",
    "github_search_code": "https://api.github.com/search/code?q={query}",
    "hunter_domain": "https://api.hunter.io/v2/domain-search?domain={domain}&api_key={key}",
    "tianyancha_search": "https://www.tianyancha.com/search?key={query}",
    "qichacha_search": "https://www.qichacha.com/search?key={query}",
    # 天眼查开放平台 API（token 认证）
    "tianyancha_holder": "https://open.api.tianyancha.com/services/open/ic/holder/2.0?keyword={query}",
    "tianyancha_invest": "https://open.api.tianyancha.com/services/open/ic/invest/2.0?keyword={query}",
    "tianyancha_baseinfo": "https://open.api.tianyancha.com/services/open/ic/baseinfo/normal?keyword={query}",
    # 爱企查（百度）登录态 cookie 复用接口
    "aiqicha_search": "https://aiqicha.baidu.com/s/advanceFilterAjax?q={query}&p=1&t=0",
    "aiqicha_baseinfo": "https://aiqicha.baidu.com/detail/basicAjax?pid={pid}",
    "aiqicha_invest": "https://aiqicha.baidu.com/detail/investAjax?pid={pid}&p=1",
    # 空间测绘平台（FOFA/鹰图/QUAKE/Censys/ZoomEye）
    "fofa_search": "https://fofa.info/api/v1/search/all?key={key}&qbase64={query_b64}&size=100&fields=host,ip,port,protocol,title,domain,icp",
    "quake_search": "https://quake.360.net/api/v3/search/quake_service",
    "qianxin_hunter_search": "https://hunter.qianxin.com/openApi/search?api-key={key}&search={query_b64}&page=1&page_size=20",
    "censys_search": "https://search.censys.io/api/v2/hosts/search",
    "zoomeye_search": "https://api.zoomeye.org/host/search?query={query}&page=1&page_size=20",
    # 代码仓库（Gitee/GitLab）
    "gitee_search": "https://gitee.com/api/v5/search/repositories?q={query}",
    "gitlab_search": "https://gitlab.com/api/v4/projects?search={query}",
    # ICP 备案在线查询（公开第三方查询页，best-effort 抓取）
    "icp_lookup": "https://icp.chinaz.com/{domain}",
}
CACHE_TTL = {
    "dns": 86400 * 30, "whois": 86400 * 7, "crtsh": 86400,
    "icp": 86400 * 30, "github": 3600, "shodan": 86400,
    "profile": 86400 * 7,
}

# ===== 浅色主题(兼容) =====
COLORS = {
    "header_bg": "#283C5A", "header_fg": "#FFFFFF",
    "sidebar_bg": "#ECEEF1", "sidebar_fg": "#333333",
    "sidebar_active": "#FFFFFF", "main_bg": "#F5F6F8",
    "card_bg": "#FFFFFF", "card_border": "#E8EAED",
    "primary": "#3370FF", "primary_hover": "#2860E0", "primary_fg": "#FFFFFF",
    "success": "#34C759", "warning": "#FF9800", "danger": "#F54A45",
    "text_primary": "#1F2329", "text_secondary": "#646A73", "text_dim": "#8F959E",
    "text_white": "#FFFFFF", "border": "#E5E6EB", "divider": "#F0F1F3",
    "table_header_bg": "#EBF0FA", "table_header_fg": "#1F2329",
    "table_row_hover": "#F5F7FA", "table_stripe": "#FAFBFC",
    "critical": "#F54A45", "high": "#FF8800", "medium": "#FFCC00",
    "low": "#3370FF", "info": "#8F959E",
    "input_bg": "#FFFFFF", "input_border": "#D0D3D9", "input_focus": "#3370FF",
}

# ===== 主题(Windows浅色风格) =====
DARK_THEME = {
    "bg_primary": "#F0F0F0", "bg_secondary": "#E5E5E5",
    "bg_card": "#FFFFFF", "bg_header": "#F0F0F0", "bg_sidebar": "#E1E1E1",
    "accent_primary": "#0078D7", "accent_secondary": "#2B88D8",
    "accent_danger": "#C42B1C",
    "text_primary": "#1F1F1F", "text_secondary": "#5A5A5A", "text_muted": "#8A8A8A",
    "risk_critical": "#C42B1C", "risk_high": "#E88A00",
    "risk_medium": "#FFB900", "risk_low": "#107C10", "risk_info": "#0078D4",
    "chart_colors": ["#0078D7","#2B88D8","#6CB8E6","#44BBAA","#FFB900","#E88A00","#C42B1C"],
}
THEME_MODE = "light"
FONT_FAMILY = "Microsoft YaHei"
FONT_SIZES = {"stat_number":36,"stat_label":11,"panel_title":16,
              "table_header":10,"table_cell":9,"log":8}

# ===== 企业信息配置 =====
GOVERNMENT_KEYWORDS = [
    '局','厅','部','委','办','处','中心','所','院',
    '政府','行政','管理','监督','执法','服务',
    '人民','公安','检察','法院','司法',
    '教育','卫生','交通','建设','规划','环保',
    '大学','学院','医院','研究所','设计院',
]
ENTERPRISE_INFO_SOURCES = ["gsxt","aiqicha","tianyancha","qichacha","qixinbao","beian"]
MAX_EQUITY_CHAIN_DEPTH = 4
MIN_EQUITY_RATIO = 0.30
MAX_RECURSIVE_SEARCH_DEPTH = 3

# ===== 扫描配置 =====
DEFAULT_PORTS = "21-23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017"
COMMON_PORTS = {21:"FTP",22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",80:"HTTP",110:"POP3",143:"IMAP",443:"HTTPS",445:"SMB",993:"IMAPS",995:"POP3S",1433:"MSSQL",1521:"Oracle",3306:"MySQL",3389:"RDP",5432:"PostgreSQL",5900:"VNC",6379:"Redis",8080:"HTTP-Proxy",8443:"HTTPS-Alt",27017:"MongoDB",2181:"ZooKeeper",9200:"Elasticsearch",9092:"Kafka"}
TOP_QUICK_PORTS = [21,22,23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017,2181,9200,9092]
TOP_SUBDOMAIN_WORDLIST = ["www","mail","ftp","api","admin","vpn","oa","erp","crm","sso","portal","test","dev","blog","m","app","cdn","download","wap","news","bbs","shop","pay","img","static","monitor","git","wiki","docs","jenkins","jira","confluence","nagios","zabbix","grafana","kibana","log","sentry","staging","pre","uat","prod","demo","sandbox","backup","db","data","ns1","ns2","mx","remote","secure","partner","vendor"]
SCAN_TIMEOUT = 5
MAX_CONCURRENT_HOSTS = 10
MAX_CONCURRENT_PORTS = 100

# ===== 无头浏览器精确计数（可选，需 playwright + chromium） =====
ENABLE_BROWSER_PROBE = True
BROWSER_PROBE_TIMEOUT = 15

# ===== 人在环浏览器登录兜底（凭证失效时弹窗引导人工登录/验证） =====
LOGIN_URLS = {
    "aiqicha": "https://aiqicha.baidu.com/",
    "tianyancha": "https://www.tianyancha.com/",
    "gsxt": "https://www.gsxt.gov.cn/",
}
BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, "browser_profiles")
BROWSER_LOGIN_TIMEOUT = 600  # 等待用户完成登录/验证的最长秒数
ORG_TYPES = ["企业","政府","教育","金融","能源","交通","医疗","其他"]
SECURITY_LEVELS = ["S1A1G1","S2A2G2","S3A3G3","S4A4G4"]
# 组织线索类型（组织管理模块可自定义增删的精准搜索线索）
ORG_CLUE_TYPES = [
    "统一社会信用代码", "法人代表", "实际受益人", "注册地址",
    "联系邮箱", "联系电话", "曾用名", "品牌/产品",
    "公众号名称", "APP名称", "关键词", "其他",
]

# 名称型线索 —— 可作为多名称搜索词并入全网检索
NAME_LIKE_CLUE_TYPES = {"法人代表", "实际受益人", "曾用名", "品牌/产品", "公众号名称", "APP名称", "关键词"}
SEVERITY_LEVELS = ["CRITICAL","HIGH","MEDIUM","LOW","INFO"]
SEVERITY_COLORS = {"CRITICAL":"#F54A45","HIGH":"#FF8800","MEDIUM":"#FFCC00","LOW":"#3370FF","INFO":"#8F959E"}
CVSS_THRESHOLDS = {"CRITICAL":9.0,"HIGH":7.0,"MEDIUM":4.0,"LOW":0.1,"INFO":0.0}

# ===== 数据泄露检测模式 =====
LEAK_PATTERNS = {
    "credential": {
        "db_connection": r'(jdbc|mysql|postgresql|mongodb|redis)://[^:]+:[^@]+@[\w.]+',
        "password_assignment": r'(password|passwd|pwd|secret)\s*[:=]\s*["\'][^"\']{3,}["\']',
        "api_key": r'(api[_-]?key|apikey|token|secret)\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}["\']',
        "aws_key": r'AKIA[0-9A-Z]{16}',
        "private_key": r'-----BEGIN (RSA |EC )?PRIVATE KEY-----',
        "connection_string": r'Server=\w+;Database=\w+;User=\w+;Password=[^;]+',
        "jwt_token": r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}',
        "config_file": r'\b(config\.php|wp-config\.php|\.env|application\.properties|settings\.py|web\.config)\b',
        "backup_file": r'\b(backup|dump|export|\.sql\.gz|\.tar\.gz|\.bak)\b',
    },
    "architecture": {
        "network_topology": r'(网络拓扑|network topology|网络架构|network architecture)',
        "security_port": r'(端口.*开放|firewall.*rule|安全组|security group)',
        "device_model": r'(防火墙.*型号|交换机.*型号|路由器.*型号|WAF.*型号)',
        "ip_planning": r'(IP.*规划|IP.*分配|VLAN.*规划)',
        "project_doc": r'(实施方案|技术方案|标书|投标|项目.*方案)',
    },
}

# ===== AI置信度评分权重 =====
CONFIDENCE_WEIGHTS = {
    "dns_verified": 0.25, "cert_match": 0.20, "name_similarity": 0.15,
    "multi_source": 0.15, "icp_confirm": 0.10, "fingerprint_match": 0.10,
    "whois_match": 0.05,
}

# ===== LLM 大模型配置（统一抽象层，OpenAI 兼容协议） =====
LLM_PROVIDERS = {
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-chat"},
    "qwen":     {"name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-plus"},
    "moonshot": {"name": "Kimi (Moonshot)", "base_url": "https://api.moonshot.cn/v1", "default_model": "moonshot-v1-8k"},
    "openai":   {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"},
    "ollama":   {"name": "Ollama (本地)", "base_url": "http://localhost:11434/v1", "default_model": "qwen2.5:7b"},
    "custom":   {"name": "自定义(OpenAI兼容)", "base_url": "", "default_model": ""},
}
LLM_CONFIG = {
    "provider": "deepseek",
    "api_key": "",
    "base_url": "",
    "model": "",
    "temperature": 0.3,
    "enabled": True,
}