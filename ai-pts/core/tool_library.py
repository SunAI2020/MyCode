# -*- coding: utf-8 -*-
"""AI-PTS 渗透测试工具库（内置目录 + 中文使用方法）。

数据来源：全网权威工具榜单（GitHub awesome-security-tools-2026、SecHub、
OWASP 官方、各工具官方仓库），汇总当前最新、最权威、最流行的开源渗透测试工具。
本模块为纯数据 + 渲染函数，不依赖 PyQt，可被 GUI / CLI 复用。
"""
from typing import List, Dict

# 分类显示顺序
CATEGORIES = [
    "网络扫描与侦察",
    "漏洞扫描",
    "Web 应用测试",
    "漏洞利用框架",
    "口令破解",
    "Active Directory / 域渗透",
    "流量分析",
    "代码与密钥审计",
    "AI 渗透测试工具",
]

# 工具目录：name 名称 / cat 分类 / url 官方地址 / desc 简介 / install 安装 / usage 使用方法
TOOLS: List[Dict[str, str]] = [
    # ---------------- 网络扫描与侦察 ----------------
    {
        "name": "Nmap", "cat": "网络扫描与侦察",
        "url": "https://nmap.org",
        "desc": "最经典的端口/服务/版本/OS 探测与主机发现工具，渗透测试第一步。",
        "install": "Kali 自带；Ubuntu: sudo apt install nmap；Windows 下载官方安装包。",
        "usage": "nmap -sV -T4 目标        # 服务与版本探测\n"
                 "nmap -p 1-65535 目标    # 全端口\n"
                 "nmap -O 目标            # OS 指纹\n"
                 "nmap -sS 目标           # SYN 半开扫描（隐蔽）",
    },
    {
        "name": "Masscan", "cat": "网络扫描与侦察",
        "url": "https://github.com/robertdavidgraham/masscan",
        "desc": "极速全端口扫描器，号称 6 分钟扫完整互联网，适合大网段快速摸底。",
        "install": "sudo apt install masscan",
        "usage": "masscan -p1-65535 目标网段 --rate=10000   # 全端口高速扫描",
    },
    {
        "name": "Amass", "cat": "网络扫描与侦察",
        "url": "https://github.com/owasp-amass/amass",
        "desc": "OWASP 出品的攻击面测绘/子域枚举工具，聚合数十个数据源。",
        "install": "go install github.com/owasp-amass/amass/v4/...@master",
        "usage": "amass enum -d 域名        # 被动+主动子域枚举\n"
                 "amass intel -whois -d 域名",
    },
    {
        "name": "Subfinder", "cat": "网络扫描与侦察",
        "url": "https://github.com/projectdiscovery/subfinder",
        "desc": "快速被动子域发现，ProjectDiscovery 出品，依赖配置各 API 密钥。",
        "install": "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
        "usage": "subfinder -d 域名 -all -silent",
    },

    # ---------------- 漏洞扫描 ----------------
    {
        "name": "Nuclei", "cat": "漏洞扫描",
        "url": "https://github.com/projectdiscovery/nuclei",
        "desc": "基于 YAML 模板的极速漏洞扫描器，社区模板 1.2 万+，支持 CVE/误配置/暴露面检测。",
        "install": "go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
        "usage": "nuclei -u URL                    # 单目标\n"
                 "nuclei -l targets.txt -severity high,critical\n"
                 "nuclei -u URL -t cves/          # 仅 CVE 模板",
    },
    {
        "name": "OpenVAS / Greenbone", "cat": "漏洞扫描",
        "url": "https://www.openvas.org",
        "desc": "最强大的开源基础设施漏洞扫描器（Nessus 的开源替代），6 万+ 漏洞检测。",
        "install": "Docker: docker run -d -p 9392:9392 mikesplain/openvas",
        "usage": "通过 Web 界面（Greenbone Security Assistant）创建任务扫描目标。",
    },
    {
        "name": "Nikto", "cat": "漏洞扫描",
        "url": "https://github.com/sullo/nikto",
        "desc": "Web 服务器配置/过时软件/常见漏洞扫描器。",
        "install": "sudo apt install nikto",
        "usage": "nikto -h http://目标  -o 报告.html",
    },

    # ---------------- Web 应用测试 ----------------
    {
        "name": "Burp Suite", "cat": "Web 应用测试",
        "url": "https://portswigger.net/burp",
        "desc": "业界标准 Web 渗透测试代理，拦截/改包/重放/扫描（Community 免费）。",
        "install": "官网下载安装包；Kali: sudo apt install burpsuite",
        "usage": "浏览器配置代理 127.0.0.1:8080 → 安装 Burp CA 证书 → 拦截并修改请求。",
    },
    {
        "name": "OWASP ZAP", "cat": "Web 应用测试",
        "url": "https://www.zaproxy.org",
        "desc": "OWASP 开源 Web 扫描器与代理，Burp 的免费替代。",
        "install": "sudo apt install zaproxy",
        "usage": "zaproxy -daemon -port 8080 或用 GUI 主动扫描目标 URL。",
    },
    {
        "name": "sqlmap", "cat": "Web 应用测试",
        "url": "https://sqlmap.org",
        "desc": "自动 SQL 注入检测与利用，支持布尔/时间/报错/联合查询等注入。",
        "install": "sudo apt install sqlmap",
        "usage": "sqlmap -u 'http://目标?id=1' --dbs      # 枚举数据库\n"
                 "sqlmap -u '...' --batch --level=5",
    },
    {
        "name": "ffuf", "cat": "Web 应用测试",
        "url": "https://github.com/ffuf/ffuf",
        "desc": "极速目录/文件/参数模糊测试（Go 编写，多线程）。",
        "install": "sudo apt install ffuf",
        "usage": "ffuf -u http://目标/FUZZ -w wordlist.txt -mc 200",
    },
    {
        "name": "Gobuster", "cat": "Web 应用测试",
        "url": "https://github.com/OJ/gobuster",
        "desc": "目录/文件与 DNS 子域爆破工具。",
        "install": "sudo apt install gobuster",
        "usage": "gobuster dir -u http://目标 -w /usr/share/wordlists/dirb/common.txt",
    },
    {
        "name": "WPScan", "cat": "Web 应用测试",
        "url": "https://wpscan.com/wordpress-security-scanner",
        "desc": "WordPress 专项安全扫描（主题/插件/核心漏洞、弱口令）。",
        "install": "sudo apt install wpscan",
        "usage": "wpscan --url http://目标 --enumerate vp,vt,u",
    },

    # ---------------- 漏洞利用框架 ----------------
    {
        "name": "Metasploit Framework", "cat": "漏洞利用框架",
        "url": "https://www.metasploit.com",
        "desc": "事实标准漏洞利用框架，数千个 exploit/payload/module。",
        "install": "sudo apt install metasploit-framework",
        "usage": "msfconsole\n"
                 "use exploit/windows/smb/ms17_010_eternalblue\n"
                 "set RHOSTS 目标\nrun",
    },
    {
        "name": "Sliver", "cat": "漏洞利用框架",
        "url": "https://github.com/BishopFox/sliver",
        "desc": "开源 C2 框架（Cobalt Strike 的开源替代），支持生成植入体与多人协作。",
        "install": "curl https://sliver.sh/install | sudo bash",
        "usage": "sliver-server 启动后，用客户端生成 beacon 并在目标执行。",
    },

    # ---------------- 口令破解 ----------------
    {
        "name": "Hydra", "cat": "口令破解",
        "url": "https://github.com/vanhauser-thc/thc-hydra",
        "desc": "在线密码爆破（SSH/FTP/HTTP 表单/数据库等 50+ 协议）。",
        "install": "sudo apt install hydra",
        "usage": "hydra -l 用户 -P 字典 ssh://目标 -t 4",
    },
    {
        "name": "John the Ripper", "cat": "口令破解",
        "url": "https://www.openwall.com/john/",
        "desc": "离线口令破解（CPU），支持 NTLM/Unix 哈希等，Jumbo 版最全。",
        "install": "sudo apt install john",
        "usage": "john --format=NT hashes.txt\njohn --show hashes.txt",
    },
    {
        "name": "Hashcat", "cat": "口令破解",
        "url": "https://hashcat.net/hashcat/",
        "desc": "GPU 加速的最快口令破解器，支持 300+ 哈希类型。",
        "install": "sudo apt install hashcat",
        "usage": "hashcat -m 1000 hash.txt wordlist.txt    # NTLM\n"
                 "hashcat -m 0 hash.txt wordlist.txt      # MD5",
    },

    # ---------------- Active Directory / 域渗透 ----------------
    {
        "name": "BloodHound", "cat": "Active Directory / 域渗透",
        "url": "https://github.com/SpecterOps/BloodHound",
        "desc": "AD 域攻击路径可视化分析，配合 SharpHound 采集域关系找域控最短路径。",
        "install": "pip install bloodhound；采集端用 SharpHound.exe",
        "usage": "目标执行 SharpHound.exe -c All 采集后，导入 BloodHound 界面分析。",
    },
    {
        "name": "Impacket", "cat": "Active Directory / 域渗透",
        "url": "https://github.com/fortra/impacket",
        "desc": "Python 网络协议套件（psexec/wmiexec/secretsdump 等），域渗透核心工具。",
        "install": "pip install impacket",
        "usage": "impacket-secretsdump 域/用户:密码@目标   # 导出哈希\n"
                 "impacket-wmiexec 域/用户:密码@目标     # 远程命令执行",
    },
    {
        "name": "Responder", "cat": "Active Directory / 域渗透",
        "url": "https://github.com/lgandx/Responder",
        "desc": "LLMNR/NBT-NS/mDNS 投毒，捕获 NTLM 哈希与凭据。",
        "install": "git clone https://github.com/lgandx/Responder",
        "usage": "python Responder.py -I eth0    # 监听内网，捕获投毒响应中的哈希。",
    },
    {
        "name": "NetExec (nxc)", "cat": "Active Directory / 域渗透",
        "url": "https://github.com/Pennyw0rth/NetExec",
        "desc": "多协议 AD 工具（原 CrackMapExec），SMB/WinRM/SSH 密码喷洒与横向移动。",
        "install": "pipx install git+https://github.com/Pennyw0rth/NetExec",
        "usage": "nxc smb 网段 -u 用户 -p 密码   # 密码喷洒\n"
                 "nxc smb 目标 -u 用户 -H 哈希  --exec-method smbexec",
    },
    {
        "name": "Mimikatz", "cat": "Active Directory / 域渗透",
        "url": "https://github.com/gentilkiwi/mimikatz",
        "desc": "从 Windows 内存提取明文口令/NTLM/Kerberos 票据（高危，慎用）。",
        "install": "下载编译好的 mimikatz.exe（会触发杀软，谨慎）",
        "usage": "mimikatz.exe\n"
                 "privilege::debug\n"
                 "sekurlsa::logonpasswords",
    },
    {
        "name": "Kerbrute", "cat": "Active Directory / 域渗透",
        "url": "https://github.com/ropnop/kerbrute",
        "desc": "Kerberos 用户名枚举与密码喷洒。",
        "install": "go install github.com/ropnop/kerbrute@latest",
        "usage": "kerbrute userenum -d 域 --dc 域控 users.txt\n"
                 "kerbrute passwordspray -d 域 users.txt 密码",
    },

    # ---------------- 流量分析 ----------------
    {
        "name": "Wireshark", "cat": "流量分析",
        "url": "https://www.wireshark.org",
        "desc": "标准抓包与网络流量分析工具。",
        "install": "sudo apt install wireshark",
        "usage": "抓包后按协议/主机过滤，分析明文协议与可疑流量。",
    },
    {
        "name": "tcpdump", "cat": "流量分析",
        "url": "https://www.tcpdump.org",
        "desc": "命令行抓包工具，适合服务器/脚本环境。",
        "install": "sudo apt install tcpdump",
        "usage": "tcpdump -i eth0 -w capture.pcap host 目标",
    },

    # ---------------- 代码与密钥审计 ----------------
    {
        "name": "Semgrep", "cat": "代码与密钥审计",
        "url": "https://semgrep.dev",
        "desc": "快速多语言静态分析，海量社区规则，适合 CI 集成。",
        "install": "pip install semgrep",
        "usage": "semgrep --config=p/owasp-top-ten 源码目录",
    },
    {
        "name": "Gitleaks", "cat": "代码与密钥审计",
        "url": "https://github.com/gitleaks/gitleaks",
        "desc": "扫描 git 历史/仓库中的泄露密钥与敏感信息。",
        "install": "go install github.com/gitleaks/gitleaks/v8@latest",
        "usage": "gitleaks detect --source 仓库路径",
    },
    {
        "name": "Trivy", "cat": "代码与密钥审计",
        "url": "https://github.com/aquasecurity/trivy",
        "desc": "容器镜像/依赖/基础设施 IaC 漏洞与密钥扫描。",
        "install": "sudo apt install trivy",
        "usage": "trivy image 镜像名\n"
                 "trivy fs 目录",
    },

    # ---------------- AI 渗透测试工具 ----------------
    {
        "name": "PentestGPT", "cat": "AI 渗透测试工具",
        "url": "https://github.com/GreyDGL/PentestGPT",
        "desc": "开源 LLM 渗透测试助手（USENIX Security 2024），推理/生成/解析三模块。",
        "install": "git clone 后按 README 配置 LLM API 密钥运行。",
        "usage": "交互式对话，输入测试目标，由 LLM 引导渗透测试流程。",
    },
    {
        "name": "Strix", "cat": "AI 渗透测试工具",
        "url": "https://github.com/usestrix/strix",
        "desc": "AI 原生自主渗透框架，自动验证发现并生成可用的 PoC。",
        "install": "pip install strix",
        "usage": "strix 目标URL，自动侦察→利用→验证闭环。",
    },
    {
        "name": "PentAGI", "cat": "AI 渗透测试工具",
        "url": "https://github.com/vxsecurity/PentAGI",
        "desc": "自主多智能体渗透测试，在 Docker 沙箱内调用 20+ 工具。",
        "install": "docker 运行官方镜像（需接入 LLM API）。",
        "usage": "配置 LLM 密钥后启动，输入目标由多智能体自动协同。",
    },
    {
        "name": "HexStrike AI", "cat": "AI 渗透测试工具",
        "url": "https://github.com/vsevex/hexstrike",
        "desc": "把 Claude/GPT 等 LLM 连接到 150+ 安全工具的 MCP 服务器。",
        "install": "npx 或 pip 安装，接入 Claude Code / MCP 客户端。",
        "usage": "在 LLM 客户端加载 HexStrike MCP，用自然语言调度安全工具。",
    },
]


def tools_by_category() -> Dict[str, List[Dict[str, str]]]:
    """按分类聚合工具，保持 CATEGORIES 顺序。"""
    grouped: Dict[str, List[Dict[str, str]]] = {c: [] for c in CATEGORIES}
    for t in TOOLS:
        grouped.setdefault(t["cat"], []).append(t)
    return grouped


def render_catalog() -> str:
    """渲染工具目录（名称/简介/官网/安装）。"""
    lines = ["【渗透测试工具库】\n"]
    for cat in CATEGORIES:
        items = [t for t in TOOLS if t["cat"] == cat]
        if not items:
            continue
        lines.append(f"\n■ {cat}")
        for t in items:
            lines.append(f"  ● {t['name']} — {t['desc']}")
            lines.append(f"      官网: {t['url']}")
            lines.append(f"      安装: {t['install']}")
    lines.append(f"\n共 {len(TOOLS)} 款工具，使用方法见「渗透测试工具使用方法」。")
    return "\n".join(lines)


def render_usage() -> str:
    """渲染各工具的中文使用方法。"""
    lines = ["【渗透测试工具使用方法】\n"]
    for cat in CATEGORIES:
        items = [t for t in TOOLS if t["cat"] == cat]
        if not items:
            continue
        lines.append(f"\n■ {cat}")
        for t in items:
            lines.append(f"\n  ● {t['name']}（{t['url']}）")
            lines.append(f"      用法:\n{t['usage']}")
    return "\n".join(lines)
