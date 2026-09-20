"""
内置知识种子：CVE/漏洞 → 技术 → 工具 映射 + 攻击案例模板。

自包含，随 exe 打包；未来可从 vendor/cve_database.db 或 reports/*.html 增量扩展。
seed(kb) 以鸭子类型操作 kb.store.add / kb.graph.add_node / kb.graph.add_edge。
"""
from __future__ import annotations


def _vuln(kb, nid, label, meta):
    kb.graph.add_node(nid, "vuln", label, meta)


def _tech(kb, nid, label):
    kb.graph.add_node(nid, "technique", label)


def _tool(kb, nid, label, meta):
    kb.graph.add_node(nid, "tool", label, meta)


def seed(kb) -> None:
    """往 KnowledgeBase 灌入内置种子。"""
    # ---- 知识图谱：漏洞 → 技术 → 工具 ----
    # MS17-010 / EternalBlue
    _vuln(kb, "vuln-ms17-010", "MS17-010 EternalBlue SMB 远程代码执行",
          {"cve_id": "MS17-010", "product": "Windows SMB"})
    _tech(kb, "tech-smb-rce", "SMB 远程代码执行")
    _tool(kb, "tool-msf-ms17", "Metasploit ms17_010_eternalblue",
          {"exploit_type": "msf", "tool": "exploit/windows/smb/ms17_010_eternalblue"})
    kb.graph.add_edge("vuln-ms17-010", "tech-smb-rce", "exploitable_by")
    kb.graph.add_edge("tech-smb-rce", "tool-msf-ms17", "uses")

    # CVE-2020-0796 / SMBGhost
    _vuln(kb, "vuln-smbghost", "CVE-2020-0796 SMBGhost SMB 远程代码执行",
          {"cve_id": "CVE-2020-0796", "product": "Windows SMB"})
    _tool(kb, "tool-msf-smbghost", "Metasploit cve_2020_0796_smbghost",
          {"exploit_type": "msf", "tool": "exploit/windows/smb/cve_2020_0796_smbghost"})
    kb.graph.add_edge("vuln-smbghost", "tech-smb-rce", "exploitable_by")
    kb.graph.add_edge("tech-smb-rce", "tool-msf-smbghost", "uses")

    # CVE-2020-1472 / ZeroLogon
    _vuln(kb, "vuln-zerologon", "CVE-2020-1472 ZeroLogon Netlogon 提权",
          {"cve_id": "CVE-2020-1472", "product": "Windows Netlogon"})
    _tech(kb, "tech-netlogon", "Netlogon 提权")
    _tool(kb, "tool-msf-zerologon", "Metasploit cve_2020_1472_zerologon",
          {"exploit_type": "msf", "tool": "exploit/windows/dcerpc/cve_2020_1472_zerologon"})
    kb.graph.add_edge("vuln-zerologon", "tech-netlogon", "exploitable_by")
    kb.graph.add_edge("tech-netlogon", "tool-msf-zerologon", "uses")

    # 弱口令
    _vuln(kb, "vuln-weakpass", "弱口令/默认口令 SMB SSH WinRM",
          {"cve_id": "", "product": "SMB/SSH/WinRM"})
    _tech(kb, "tech-spray", "密码喷洒 / 横向移动")
    _tool(kb, "tool-netexec", "netexec (nxc) 密码喷洒与横向",
          {"exploit_type": "lateral_movement", "tool": "nxc"})
    kb.graph.add_edge("vuln-weakpass", "tech-spray", "exploitable_by")
    kb.graph.add_edge("tech-spray", "tool-netexec", "uses")

    # SQL 注入
    _vuln(kb, "vuln-sqli", "SQL 注入", {"cve_id": "", "product": "Web"})
    _tech(kb, "tech-sqli", "SQL 注入利用")
    _tool(kb, "tool-sqlmap", "sqlmap 自动注入",
          {"exploit_type": "sql_injection", "tool": "sqlmap"})
    kb.graph.add_edge("vuln-sqli", "tech-sqli", "exploitable_by")
    kb.graph.add_edge("tech-sqli", "tool-sqlmap", "uses")

    # 已知凭据
    _vuln(kb, "vuln-knowncreds", "已知凭据远程命令执行",
          {"cve_id": "", "product": "SMB/WMI"})
    _tech(kb, "tech-credexec", "凭据远程命令执行")
    _tool(kb, "tool-wmiexec", "impacket wmiexec.py",
          {"exploit_type": "rce", "tool": "wmiexec.py"})
    kb.graph.add_edge("vuln-knowncreds", "tech-credexec", "exploitable_by")
    kb.graph.add_edge("tech-credexec", "tool-wmiexec", "uses")

    # ---- 知识库条目：攻击案例模板（RAG 检索源） ----
    kb.store.add(
        "attack_case", "MS17-010 EternalBlue 利用",
        "目标开放 445 端口且未打 MS17-010 补丁时，可用 Metasploit 的 "
        "exploit/windows/smb/ms17_010_eternalblue 模块直接获取 SYSTEM 权限。"
        "先确认端口与 OS 版本，再设置 RHOSTS 与 PAYLOAD 后 exploit。",
        {"exploit_type": "msf", "tool": "exploit/windows/smb/ms17_010_eternalblue"},
    )
    kb.store.add(
        "attack_case", "SMBGhost 利用",
        "CVE-2020-0796 影响 Windows SMBv3 压缩功能，可远程代码执行。"
        "确认目标为受影响 Windows 10/Server 版本，用 cve_2020_0796_smbghost 模块。",
        {"exploit_type": "msf", "tool": "exploit/windows/smb/cve_2020_0796_smbghost"},
    )
    kb.store.add(
        "attack_case", "ZeroLogon 提权到域控",
        "CVE-2020-1472 Netlogon 漏洞可把域控机器账户口令置空，进而接管域。"
        "用 cve_2020_1472_zerologon 模块，成功后 secretsdump 提取 NTDS 哈希。",
        {"exploit_type": "msf", "tool": "exploit/windows/dcerpc/cve_2020_1472_zerologon"},
    )
    kb.store.add(
        "attack_case", "SMB 弱口令横向",
        "内网存在弱口令/默认口令时，用 netexec 对 SMB 网段做密码喷洒，"
        "命中后可进一步 wmiexec 拿 shell 或 secretsdump 提哈希横向。",
        {"exploit_type": "lateral_movement", "tool": "nxc"},
    )
    kb.store.add(
        "attack_case", "SQL 注入探测与利用",
        "Web 参数疑似 SQL 注入时，先手工确认注入点，再用 sqlmap 自动化枚举数据库、"
        "提权读写文件或拿 shell。注意确认在授权范围内。",
        {"exploit_type": "sql_injection", "tool": "sqlmap"},
    )
    kb.store.add(
        "attack_case", "已知凭据远程命令执行",
        "拿到目标账户口令/NTLM 哈希后，用 impacket 的 wmiexec.py/psexec.py "
        "远程执行命令确认权限，再决定提权或横向。",
        {"exploit_type": "rce", "tool": "wmiexec.py"},
    )
