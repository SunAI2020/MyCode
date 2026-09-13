# -*- coding: utf-8 -*-
"""暴露面检索语法字典 — 对齐《暴露面资产排查报告》6大覆盖维度 + 对外管理入口

占位符约定（与 config.settings.API_ENDPOINTS 的 .format() 一致）：
    {domain}  目标域名，如 sxszyczs.com
    {org}     目标组织名称，如 山西省商务厅
    {query}   已替换好的完整查询串（用于拼平台搜索链接）
    {query_b64} base64 编码后的查询串（用于 FOFA/鹰图等平台链接）
"""
import base64

# ===== 敏感文件扩展名（维度5：高危端口/敏感目录/备份文件） =====
SENSITIVE_FILE_EXTENSIONS = [
    "env","conf","config","yml","yaml","json","xml","toml","ini","cfg",
    "properties","cnf","sql","sql.gz","sql.zip","db","sqlite","sqlite3",
    "mdb","accdb","bak","backup","dump","bson","log","logs","err","error",
    "trace","out","debug","access_log","error_log","pem","key","crt","cer",
    "der","p12","pfx","ppk","ovpn","pub","gpg","asc","p7b","jks","keystore",
    "war","jar","ear","zip","rar","tar","tar.gz","tgz","7z","bz2","xz",
    "doc","docx","xls","xlsx","ppt","pptx","pdf","txt","md","csv",
]

# ===== 敏感目录/路径（维度5，来自报告敏感目录表） =====
SENSITIVE_PATHS = [
    "/.git/HEAD", "/.git/config", "/.svn/entries", "/.DS_Store",
    "/WEB-INF/web.xml", "/WEB-INF/classes/applicationContext.xml",
    "/phpinfo.php", "/info.php", "/test.php",
    "/phpmyadmin/", "/phppgadmin/", "/adminer.php",
    "/.env", "/.env.backup", "/.env.local",
    "/config.php", "/config.php.bak", "/wp-config.php", "/wp-config.bak",
    "/settings.py", "/settings.local.py", "/web.config", "/appsettings.json",
    "/database.sql", "/db.sql", "/dump.sql",
    "/backup/", "/backup.zip", "/backup.tar.gz", "/upload/", "/logs/",
    "/actuator", "/actuator/health", "/actuator/env",
    "/swagger-ui.html", "/swagger-ui/index.html", "/api-docs", "/v2/api-docs",
    "/druid/index.html", "/nacos/", "/admin/", "/console/", "/manager/html",
    "/debug/", "/graphql", "/graphiql", "/robots.txt", "/sitemap.xml",
    "/crossdomain.xml", "/server-status", "/status", "/.well-known/",
    "/jmx-console", "/web-console", "/solr/admin", "/jenkins/login",
    "/kibana", "/grafana", "/.gitlab-ci.yml", "/Dockerfile", "/docker-compose.yml",
]

# ===== 密钥泄露关键词（维度2：代码仓库密钥泄露） =====
KEY_LEAK_KEYWORDS = [
    "password","passwd","pwd","secret","secrets","token","apikey","api_key",
    "accessKeyId","LTAI","AKID","secretId","TENCENT_SECRET_ID","AWS_SECRET_ACCESS_KEY",
    "JWT_SECRET","jwt_secret","DB_PASSWORD","REDIS_PASSWORD","MAIL_PASSWORD",
    "PRIVATE KEY","BEGIN RSA PRIVATE KEY","private_key","xoxb-","xoxp-",
    "connectionString","jdbc:mysql","ClientSecret","app_secret","APP_ID","WX_APPID",
]

# ===== 平台搜索链接模板（无 API key 时产出可点击检索链接） =====
SEARCH_PLATFORM_URLS = {
    "google":   "https://www.google.com/search?q={query}",
    "bing":     "https://www.bing.com/search?q={query}",
    "baidu":    "https://www.baidu.com/s?wd={query}",
    "fofa":     "https://fofa.info/result?qbase64={query_b64}",
    "quake":    "https://quake.360.net/quake/#/index",
    "hunter":   "https://hunter.qianxin.com/",
    "censys":   "https://search.censys.io/search?resource=hosts&q={query}",
    "zoomeye":  "https://www.zoomeye.org/searchResult?q={query}",
    "shodan":   "https://www.shodan.io/search?query={query}",
    "github":   "https://github.com/search?q={query}&type=code",
    "gitee":    "https://search.gitee.com/?q={query}&type=code",
    "gitlab":   "https://gitlab.com/search?search={query}",
    "wenku":    "https://wenku.baidu.com/search?word={query}",
    "pan":      "https://pan.baidu.com/disk/main#/search?query={query}",
    "zhihu":    "https://www.zhihu.com/search?type=content&q={query}",
    "csdn":     "https://so.csdn.net/so/search?q={query}",
    "wechat":   "https://weixin.sogou.com/weixin?type=2&query={query}",
    "crtsh":    "https://crt.sh/?q={query}",
    # 搜索引擎（国产补充 + 国际）
    "sogou":    "https://www.sogou.com/web?query={query}",
    "so360":    "https://www.so.com/s?q={query}",
    "shenma":   "https://yz.m.sm.cn/s?q={query}",
    "yandex":   "https://yandex.com/search/?text={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    # 空间测绘（国际 + 国产 CriminalIP）
    "binaryedge": "https://app.binaryedge.io/services/query?query={query}",
    "onyphe":   "https://www.onyphe.io/search/?query={query}",
    "netlas":   "https://app.netlas.io/responses/?q={query}",
    "leakix":   "https://leakix.net/search?scope=leak&q={query}",
    "criminalip": "https://www.criminalip.io/asset/search?query={query}",
    # 代码仓库（国产 GitCode + 国际）
    "gitcode":  "https://gitcode.com/search?keyword={query}",
    "bitbucket": "https://bitbucket.org/repo/all?name={query}",
    "sourcegraph": "https://sourcegraph.com/search?q={query}",
    "searchcode": "https://searchcode.com/?q={query}",
    # 证书透明日志
    "certspotter": "https://sslmate.com/certspotter/api/v1/issuances?domain={query}&include_subdomains=true&expand=dns_names",
    "facebook_ct": "https://developers.facebook.com/tools/ct/{query}",
    # 文库/网盘/社区/职场（中文公开信息泄露）
    "docin":    "https://www.docin.com/search.do?searchcat=2&nkey={query}",
    "doc88":    "https://so.doc88.com/?kw={query}",
    "360doc":   "https://www.360doc.cn/search.aspx?query={query}",
    "vdisk":    "https://vdisk.weibo.com/search/?type=public&keyword={query}",
    "weibo":    "https://s.weibo.com/weibo?q={query}",
    "tieba":    "https://tieba.baidu.com/f/search/res?ie=utf-8&qw={query}",
    "xiaohongshu": "https://www.xiaohongshu.com/search_result?keyword={query}",
    "maimai":   "https://maimai.cn/s?q={query}",
}

# ===== 暴露面检索语法库（按 维度 -> 平台 -> [(规则名, 查询模板)]） =====
SEARCH_DORK_TEMPLATES = {
    # 维度1：搜索引擎（Google/Bing/百度）域名及敏感信息暴露
    "search_engine": {
        "google": [
            ("基础域名收录", "site:{domain}"),
            ("子域名枚举", "site:{domain} -www -mail -cdn"),
            ("孤立子域名", "site:*.{domain} -site:www.{domain}"),
            ("敏感后台目录", "site:{domain} inurl:admin OR inurl:login OR inurl:manage"),
            ("敏感文件", "site:{domain} filetype:pdf OR filetype:doc OR filetype:xls OR filetype:sql OR filetype:bak"),
            ("配置文件", "site:{domain} inurl:config OR inurl:conf OR inurl:env"),
            ("敏感信息", 'site:{domain} intext:"password" OR intext:"@163.com"'),
        ],
        "bing": [
            ("基础域名收录", "site:{domain}"),
            ("敏感文件", "site:{domain} filetype:pdf OR filetype:doc OR filetype:bak"),
            ("管理入口", "site:{domain} inurl:admin OR inurl:login"),
        ],
        "baidu": [
            ("基础域名收录", "site:{domain}"),
            ("敏感文件", "site:{domain} filetype:doc OR filetype:pdf OR filetype:sql"),
        ],
        "sogou": [
            ("基础域名收录", "site:{domain}"),
            ("敏感文件", "site:{domain} filetype:doc OR filetype:pdf OR filetype:sql"),
        ],
        "so360": [
            ("基础域名收录", "site:{domain}"),
            ("敏感文件", "site:{domain} filetype:doc OR filetype:pdf"),
        ],
        "shenma": [
            ("基础域名收录", "site:{domain}"),
        ],
        "yandex": [
            ("基础域名收录", "site:{domain}"),
        ],
        "duckduckgo": [
            ("基础域名收录", "site:{domain}"),
        ],
    },
    # 维度3：空间测绘平台（FOFA/鹰图/QUAKE/Censys/ZoomEye/Shodan）全域资产
    "space_mapping": {
        "fofa": [
            ("域名资产", 'domain="{domain}"'),
            ("子域名资产", 'host=".{domain}"'),
            ("证书关联", 'cert="{domain}"'),
            ("标题关联", 'title="{org}"'),
            ("正文关联", 'body="{org}"'),
        ],
        "quake": [
            ("域名资产", 'domain:"{domain}"'),
            ("证书关联", 'cert:"{domain}"'),
            ("标题关联", 'title:"{org}"'),
        ],
        "hunter": [
            ("域名资产", 'domain="{domain}"'),
            ("备案主体", 'icp.name="{org}"'),
        ],
        "censys": [
            ("域名资产", "{domain}"),
            ("证书域名", "parsed.names:{domain}"),
        ],
        "zoomeye": [
            ("域名资产", "site:{domain}"),
            ("主机名", "hostname:{domain}"),
            ("证书关联", 'ssl.cert.subject.cn:"{domain}"'),
        ],
        "shodan": [
            ("主机名资产", "hostname:{domain}"),
            ("证书关联", 'ssl.cert.subject.cn:"{domain}"'),
        ],
        "binaryedge": [
            ("域名资产", "web.host:{domain}"),
            ("证书关联", "web.tls.certificate.subject.CN:{domain}"),
        ],
        "onyphe": [
            ("域名资产", "domain:{domain}"),
            ("主机名", "hostname:{domain}"),
        ],
        "netlas": [
            ("域名资产", "domain:{domain}"),
            ("证书关联", "certificate.subject.common_name:{domain}"),
        ],
        "leakix": [
            ("主机名资产", 'hostname:"{domain}"'),
        ],
        "criminalip": [
            ("域名资产", 'hostname:"{domain}"'),
            ("备案主体", 'icp.name:"{org}"'),
        ],
    },
    # 维度2：公开代码仓库（GitHub/Gitee/GitLab）源码及密钥泄露
    "code_repo": {
        "github": [
            ("组织源码", '"{org}"'),
            ("域名引用", '"{domain}"'),
            ("密码泄露", '"{org}" password OR secret'),
            ("云密钥泄露", '"{org}" accessKeyId OR LTAI OR AKID'),
            ("JWT密钥", '"{org}" JWT_SECRET OR jwt_secret'),
            ("私钥泄露", '"{org}" "BEGIN RSA PRIVATE KEY"'),
        ],
        "gitee": [
            ("组织源码", '"{org}"'),
            ("密码泄露", '"{org}" password OR secret'),
            ("云密钥泄露", '"{org}" accessKeyId OR LTAI'),
        ],
        "gitlab": [
            ("组织源码", '"{org}"'),
            ("密码泄露", '"{org}" password OR secret'),
            ("连接串泄露", '"{org}" connectionString OR jdbc'),
        ],
        "gitcode": [
            ("组织源码", '"{org}"'),
            ("密码泄露", '"{org}" password OR secret'),
        ],
        "bitbucket": [
            ("组织源码", '"{org}"'),
        ],
        "sourcegraph": [
            ("组织源码", '"{org}"'),
            ("密码泄露", '"{org}" password OR secret'),
        ],
        "searchcode": [
            ("组织源码", '"{org}"'),
        ],
    },
    # 横切维度：对外系统管理入口（后台/运维接口/API文档）
    "mgmt_entry": {
        "google": [
            ("后台登录页", "site:{domain} inurl:login OR inurl:admin OR inurl:manage OR inurl:backend"),
            ("phpMyAdmin", 'site:{domain} inurl:phpmyadmin OR intitle:phpMyAdmin'),
            ("Jenkins", 'site:{domain} intitle:"Dashboard [Jenkins]" OR inurl:jenkins/login'),
            ("Kibana", 'site:{domain} inurl:kibana OR intitle:"Kibana"'),
            ("Grafana", 'site:{domain} inurl:grafana OR intitle:"Grafana"'),
            ("Tomcat管理", 'site:{domain} intitle:"Apache Tomcat" OR inurl:manager/html'),
            ("WebLogic", 'site:{domain} inurl:console intitle:"Oracle WebLogic"'),
            ("Solr管理", 'site:{domain} inurl:solr/admin OR intitle:"Solr Admin"'),
            ("Swagger文档", "site:{domain} inurl:swagger-ui OR inurl:api-docs"),
            ("SpringActuator", "site:{domain} inurl:actuator OR inurl:actuator/health"),
            ("GitLab", 'site:{domain} inurl:gitlab/users/sign_in OR intitle:"GitLab"'),
            ("Jira/Confluence", "site:{domain} inurl:jira OR inurl:confluence"),
        ],
        "shodan": [
            ("登录/后台标题", 'http.title:"{org}" http.title:"登录"'),
            ("OA/管理后台", 'http.title:"{org}" http.title:"后台"'),
        ],
    },
    # 维度4：SSL证书透明度日志（crt.sh/Censys）关联子域名
    "cert_transparency": {
        "crtsh": [
            ("证书子域名", "%25.{domain}"),
            ("组织证书", "{org}"),
        ],
        "censys": [
            ("证书域名", "parsed.names:{domain}"),
            ("组织证书", "subject.organization:{org}"),
        ],
        "certspotter": [
            ("证书子域名", "{domain}"),
            ("组织证书", "{org}"),
        ],
        "facebook_ct": [
            ("证书子域名", "{domain}"),
        ],
    },
    # 维度6：文库/网盘/社区公开信息泄露
    "doc_leak": {
        "wenku": [
            ("百度文库", "{org}"),
            ("百度文库-安全", "{org} 安全"),
            ("百度文库-信息泄露", "{org} 信息泄露"),
        ],
        "pan": [
            ("网盘-配置", "{org} 配置文件"),
            ("网盘-数据库", "{org} 数据库"),
        ],
        "zhihu": [
            ("知乎-公司", "{org}"),
            ("知乎-安全", "{org} 安全"),
        ],
        "csdn": [
            ("CSDN-源码", "{org} 源码"),
            ("CSDN-密钥", "{org} 密钥 OR token"),
        ],
        "wechat": [
            ("公众号/小程序", "{org}"),
        ],
        "docin": [
            ("豆丁-公司", "{org}"),
            ("豆丁-方案", "{org} 技术方案 OR 实施方案"),
        ],
        "doc88": [
            ("道客巴巴-公司", "{org}"),
        ],
        "360doc": [
            ("360doc-公司", "{org}"),
        ],
        "vdisk": [
            ("微盘-配置", "{org} 配置 OR 数据库"),
        ],
        "weibo": [
            ("微博-公司", "{org}"),
            ("微博-员工", "{org} 员工 OR 招聘"),
        ],
        "tieba": [
            ("贴吧-公司", "{org}"),
        ],
        "xiaohongshu": [
            ("小红书-公司", "{org}"),
        ],
        "maimai": [
            ("脉脉-公司", "{org}"),
            ("脉脉-安全", "{org} 安全 OR 运维"),
        ],
    },
}


def build_query(template, domain="", org=""):
    """将模板中的 {domain}/{org} 占位符替换为实际值。"""
    try:
        return template.format(domain=domain or "", org=org or "")
    except (KeyError, ValueError, IndexError):
        return template


def build_platform_url(platform, query):
    """构造平台搜索链接（对 fofa 等需 base64 的平台特殊处理）。"""
    tpl = SEARCH_PLATFORM_URLS.get(platform)
    if not tpl:
        return ""
    kwargs = {"query": query}
    if "{query_b64}" in tpl:
        kwargs["query_b64"] = base64.b64encode(query.encode("utf-8")).decode("ascii")
    try:
        return tpl.format(**kwargs)
    except (KeyError, ValueError):
        return tpl
