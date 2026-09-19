"""
AI 计划 → 执行器 的能力目录与确定性路由。

单一事实源：AI 规划 prompt 的「可用工具清单」、关键词/CVE 兜底路由、执行器注册
三处共用本模块，避免词表漂移。

本模块不 import 任何 core 模块，可被 ai_analyzer / workflow 安全单向引用。
"""
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 能力目录：每种 exploit_type -> 给 AI 看的元信息
#   exploit_type : 与 ExecutorRegistry 注册键一致（core/orchestrator.py）
#   label        : 人类可读标签
#   tool         : 实际调用的工具（给 AI 看的名称）
#   desc         : 适用场景说明
#   param        : 需要 AI 用 "tool" 字段回填的具体参数（可选）
#   manual       : True 表示暂无自动化工具，需人工验证
# ---------------------------------------------------------------------------
CAPABILITIES: List[Dict[str, str]] = [
    {
        "exploit_type": "msf",
        "label": "Metasploit 漏洞利用（远程代码执行）",
        "tool": "msfconsole",
        "desc": "有现成 Metasploit 模块的 CVE，如 MS17-010/EternalBlue、SMBGhost(CVE-2020-0796)、"
                "BlueKeep(CVE-2019-0708)、ZeroLogon(CVE-2020-1472)、PrintNightmare",
        "param": "module",
    },
    {
        "exploit_type": "rce",
        "label": "impacket 远程命令执行",
        "tool": "wmiexec.py / psexec.py / smbexec.py / atexec.py",
        "desc": "已知凭据时，通过 SMB/WMI 在目标远程执行命令",
        "param": "method",
    },
    {
        "exploit_type": "privesc",
        "label": "凭据哈希提取（secretsdump）",
        "tool": "secretsdump.py",
        "desc": "提取 SAM/LSA/NTDS 凭据哈希，作为提权/横向的凭据来源",
    },
    {
        "exploit_type": "privesc_enum",
        "label": "PEAS 提权枚举",
        "tool": "ssh + linpeas/winpeas",
        "desc": "在目标上枚举提权线索",
    },
    {
        "exploit_type": "lateral_movement",
        "label": "横向移动 / 密码喷洒",
        "tool": "netexec (nxc)",
        "desc": "SMB/WinRM/SSH 密码喷洒与横向移动",
    },
    {
        "exploit_type": "bloodhound",
        "label": "域关系采集",
        "tool": "bloodhound-python",
        "desc": "采集 AD 域关系",
    },
    {
        "exploit_type": "credential_dump",
        "label": "凭据抓取",
        "tool": "mimikatz",
        "desc": "内存凭据抓取（高危，慎用）",
    },
    {
        "exploit_type": "sql_injection",
        "label": "SQL 注入",
        "tool": "人工验证",
        "desc": "暂无自动化工具",
        "manual": "true",
    },
    {
        "exploit_type": "xss",
        "label": "跨站脚本",
        "tool": "人工验证",
        "desc": "暂无自动化工具",
        "manual": "true",
    },
    {
        "exploit_type": "auth_bypass",
        "label": "认证绕过",
        "tool": "人工验证",
        "desc": "暂无自动化工具",
        "manual": "true",
    },
    {
        "exploit_type": "info_disclosure",
        "label": "信息泄露",
        "tool": "人工验证",
        "desc": "暂无自动化工具",
        "manual": "true",
    },
]

# 合法 exploit_type 集合（路由校验用）
VALID_TYPES = {c["exploit_type"] for c in CAPABILITIES}

# 无自动化工具、需人工验证的类型（执行器注册用，替代 orchestrator 里的硬编码 tuple）
MANUAL_TYPES = [c["exploit_type"] for c in CAPABILITIES if c.get("manual") == "true"]

# ---------------------------------------------------------------------------
# 关键词/CVE 兜底路由表：(关键词小写, exploit_type, tool)
# 只收录有把握的知名模块路径，宁缺毋滥；命中首个即覆盖。
# ---------------------------------------------------------------------------
ROUTE_TABLE: List[Tuple[str, str, str]] = [
    ("ms17-010", "msf", "exploit/windows/smb/ms17_010_eternalblue"),
    ("eternalblue", "msf", "exploit/windows/smb/ms17_010_eternalblue"),
    ("smbghost", "msf", "exploit/windows/smb/cve_2020_0796_smbghost"),
    ("cve-2020-0796", "msf", "exploit/windows/smb/cve_2020_0796_smbghost"),
    ("bluekeep", "msf", "exploit/windows/rdp/cve_2019_0708_bluekeep_rce"),
    ("cve-2019-0708", "msf", "exploit/windows/rdp/cve_2019_0708_bluekeep_rce"),
    ("zerologon", "msf", "exploit/windows/dcerpc/cve_2020_1472_zerologon"),
    ("cve-2020-1472", "msf", "exploit/windows/dcerpc/cve_2020_1472_zerologon"),
    ("printnightmare", "msf", "exploit/windows/local/cve_2021_1675_printnightmare"),
    ("cve-2021-1675", "msf", "exploit/windows/local/cve_2021_1675_printnightmare"),
    # 以下为「提权/凭据」类，无单一模块名，映射到 secretsdump 收哈希
    ("netlogon", "privesc", ""),
    ("cve-2022-38023", "privesc", ""),
    ("cve-2022-37966", "privesc", ""),
    ("cve-2022-37967", "privesc", ""),
    ("kerberos", "privesc", ""),
    ("rc4-hmac", "privesc", ""),
]


def build_capability_prompt() -> str:
    """渲染「可用 exploit_type 及其对应工具」清单，供 AI 规划 prompt 使用。"""
    lines = []
    for c in CAPABILITIES:
        manual = "（人工验证）" if c.get("manual") == "true" else ""
        param_hint = f"，tool 字段需填 {c['param']}" if c.get("param") else "，tool 字段留空"
        lines.append(
            f"- {c['exploit_type']}: {c['label']}（工具: {c['tool']}）{manual}\n"
            f"  {c['desc']}{param_hint}"
        )
    return "\n".join(lines)


def route_ai_steps(steps: List[Dict]) -> List[Dict]:
    """确定性兜底路由：修正 AI 输出的 exploit_type / tool。

    顺序：
    1. exploit_type 合法且 tool 非空 -> 视为完整结构化答案，信任不覆盖；
    2. 否则扫描 description + payload 命中的关键词，首个命中覆盖 exploit_type + tool；
    3. 最终 exploit_type 仍不合法 -> 回退 rce。

    Args:
        steps: WorkflowBuilder.from_ai_plan 产出的步骤列表（含 tool 键）。

    Returns:
        就地修改后的 steps（同时返回，便于链式调用）。
    """
    for s in steps:
        etype = s.get("exploit_type") or ""
        tool = s.get("tool") or ""

        # 已给出完整结构化答案：跳过关键词覆盖
        if etype in VALID_TYPES and tool:
            continue

        blob = " ".join([
            s.get("description") or "",
            s.get("payload") or "",
        ]).lower()
        for kw, new_type, new_tool in ROUTE_TABLE:
            if kw in blob:
                s["exploit_type"] = new_type
                if new_tool:
                    s["tool"] = new_tool
                break

        if (s.get("exploit_type") or "") not in VALID_TYPES:
            s["exploit_type"] = "rce"
    return steps
