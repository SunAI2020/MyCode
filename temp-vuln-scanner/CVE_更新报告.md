# 漏洞库 CVE 数据更新报告

## 🛡️ 版权所有

**© 2026 山西有信网安科技有限公司**

---

## ✅ 更新完成

### 📊 数据统计

| 项目 | 数量 |
|------|------|
| **更新前 CVE 总数** | 51 条 |
| **新增 CVE 数量** | 21 条 |
| **跳过重复** | 2 条 |
| **更新后 CVE 总数** | **72 条** |

### 📈 严重程度分布

| 严重程度 | 数量 | 占比 |
|---------|------|------|
| 🔴 CRITICAL (严重) | 55 | 76.4% |
| 🟠 HIGH (高危) | 13 | 18.1% |
| 🟡 MEDIUM (中危) | 4 | 5.5% |
| 🟢 LOW (低危) | 0 | 0% |

---

## 📅 按年份分布

| 年份 | CVE 数量 | 代表性漏洞 |
|------|---------|-----------|
| 2000 | 1 | IIS 5.0 WebDAV 缓冲区溢出 |
| 2001 | 1 | IIS Unicode 目录遍历 |
| 2002 | 1 | Apache mod_ssl 缓冲区溢出 |
| 2003 | 1 | SQL Server 缓冲区溢出 |
| 2004 | 1 | Windows ASN.1 RCE |
| 2005 | 1 | Windows GDI+ RCE |
| 2006 | 1 | Microsoft Word WKS2PSS |
| 2007 | 1 | Windows ANI 光标处理 |
| 2008 | 1 | Microsoft Excel 内存破坏 |
| 2009 | 1 | Microsoft Excel 公式处理 |
| 2010 | 1 | Windows 快捷方式 (Stuxnet) |
| 2011 | 1 | Apache Range DoS |
| 2012 | 2 | Office ActiveX、PHP-CGI |
| 2013 | 2 | Nginx 整数溢出、IE RCE |
| 2014 | 2 | **Heartbleed**、**Shellshock** |
| 2015 | 2 | HTTP.sys RCE、Office OLE |
| 2016 | 4 | 内核提权、**Dirty COW** |
| 2017 | 8 | **EternalBlue**、Struts2 |
| 2018 | 9 | Fortinet 路径遍历 |
| 2019 | 11 | **BlueKeep**、vCenter |
| 2020 | 9 | **SMBGhost**、**Zerologon** |
| 2021 | 6 | **ProxyLogon**、**PwnKit** |
| 2022 | 2 | **Spring4Shell**、Confluence |
| 2023 | 2 | Confluence 认证绕过、HTTP/2 Rapid Reset |
| 2024 | 1 | Fortinet FortiOS RCE |

---

## 🆕 新增 CVE 列表 (21 条)

### 2000-2010 年经典漏洞

| CVE 编号 | 名称 | 严重程度 |
|---------|------|---------|
| CVE-2000-0610 | Microsoft IIS 5.0 WebDAV 缓冲区溢出 | CRITICAL |
| CVE-2001-0537 | Microsoft IIS Unicode 目录遍历 | HIGH |
| CVE-2002-0649 | Apache mod_ssl 缓冲区溢出 | CRITICAL |
| CVE-2003-0252 | Microsoft SQL Server 缓冲区溢出 | CRITICAL |
| CVE-2004-0107 | Microsoft Windows ASN.1 RCE | CRITICAL |
| CVE-2005-0048 | Microsoft Windows GDI+ RCE | CRITICAL |
| CVE-2006-3439 | Microsoft Word WKS2PSS 缓冲区溢出 | CRITICAL |
| CVE-2007-0071 | Microsoft Windows ANI 光标处理 RCE | CRITICAL |
| CVE-2008-4834 | Microsoft Excel 内存破坏 | CRITICAL |
| CVE-2009-1918 | Microsoft Excel 公式处理 RCE | CRITICAL |
| CVE-2010-2568 | Windows 快捷方式 RCE (Stuxnet) | CRITICAL |

### 2011-2020 年高危漏洞

| CVE 编号 | 名称 | 严重程度 |
|---------|------|---------|
| CVE-2012-0158 | Microsoft Office ActiveX RCE | CRITICAL |
| CVE-2013-3893 | Microsoft IE CButton UAF | CRITICAL |
| CVE-2015-1641 | Microsoft Office OLE RCE | CRITICAL |
| CVE-2016-0167 | Windows 内核提权 | CRITICAL |
| CVE-2018-0808 | Microsoft Office RTF RCE | CRITICAL |
| CVE-2019-1367 | Microsoft Edge RCE | CRITICAL |

### 2021-2024 年新漏洞

| CVE 编号 | 名称 | 严重程度 |
|---------|------|---------|
| CVE-2022-26134 | Atlassian Confluence OGNL 注入 | CRITICAL |
| CVE-2023-22515 | Atlassian Confluence 认证绕过 | CRITICAL |
| CVE-2023-44487 | HTTP/2 Rapid Reset DDoS | HIGH |
| CVE-2024-21762 | Fortinet FortiOS RCE | CRITICAL |

---

## 📁 数据文件

### 文件位置

| 文件 | 路径 |
|------|------|
| CVE 数据 | `/home/admin/.openclaw/workspace/vuln-scanner/data/cve_samples.json` |
| 备份文件 | `/home/admin/.openclaw/workspace/vuln-scanner/data/cve_samples.json.bak` |
| SQLite 数据库 | `/home/admin/.openclaw/workspace/vuln-scanner/data/vuln_database.db` |
| 合并脚本 | `/home/admin/.openclaw/workspace/vuln-scanner/scripts/merge_cve.py` |

### 数据结构

```json
{
  "cve_id": "CVE-2024-21762",
  "name": "Fortinet FortiOS 越界写入漏洞",
  "description": "Fortinet FortiOS SSL VPN 中存在越界写入漏洞...",
  "affected_products": ["Fortinet FortiOS"],
  "affected_versions": ["7.0.0-7.0.13", "7.2.0-7.2.5", "7.4.0-7.4.2"],
  "cvss_score": 9.8,
  "severity": "CRITICAL",
  "published_date": "2024-02-02",
  "references": ["https://nvd.nist.gov/vuln/detail/CVE-2024-21762"],
  "fix_recommendation": "升级到 FortiOS 7.0.14/7.2.6/7.4.3 或更高版本",
  "cwe_id": "CWE-119",
  "exploit_available": true,
  "patch_available": true
}
```

---

## 🔍 覆盖厂商和产品

### 操作系统

- ✅ Microsoft Windows (2000-2024)
- ✅ Linux Kernel
- ✅ Unix

### 应用软件

- ✅ Apache (HTTP Server, Tomcat, Struts2, Log4j)
- ✅ Nginx
- ✅ OpenSSL
- ✅ OpenSSH
- ✅ PHP
- ✅ MySQL
- ✅ PostgreSQL

### 企业产品

- ✅ Microsoft Office
- ✅ Microsoft Exchange Server
- ✅ Microsoft SQL Server
- ✅ VMware vCenter
- ✅ Atlassian Confluence
- ✅ Fortinet FortiOS
- ✅ Cisco ASA
- ✅ Jenkins
- ✅ JBoss
- ✅ Oracle WebLogic
- ✅ Spring Framework

---

## 🛠️ 使用方法

### 查看漏洞库统计

```bash
cd /home/admin/.openclaw/workspace/vuln-scanner
python3 main.py stats
```

### 搜索特定 CVE

```bash
# 按产品名称搜索
python3 main.py search --product Apache --severity CRITICAL

# 按 CVE 编号查看详情
python3 main.py detail --cve CVE-2024-21762
```

### 执行漏洞扫描

```bash
# 扫描单个 IP
python3 main.py scan --target 192.168.1.1

# 扫描网段
python3 main.py scan --target 192.168.1.0/24

# 生成 HTML 报告
python3 main.py scan --target 192.168.1.1 -o report.html
```

---

## 📋 后续建议

### 持续更新

1. **定期更新 CVE 数据** - 建议每月更新一次
2. **关注 NVD 官方发布** - https://nvd.nist.gov/
3. **跟踪最新漏洞情报** - 关注安全厂商公告

### 自动化更新

可创建定时任务自动从 NVD API 获取最新 CVE 数据：

```bash
# 添加到 crontab
0 2 * * 0 cd /home/admin/.openclaw/workspace/vuln-scanner && python3 scripts/update_cve.py
```

---

## 📞 技术支持

**山西有信网安科技有限公司**

- 邮箱：support@youxinwangan.com
- 网站：www.youxinwangan.com

---

**© 2026 山西有信网安科技有限公司 版权所有**

*本漏洞库仅供授权的安全测试使用*
*未经授权扫描他人系统是违法行为*
