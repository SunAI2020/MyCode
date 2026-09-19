# -*- coding: utf-8 -*-
"""AI-PTS 渗透测试报告生成器（HTML）。

生成符合规范要求的完整报告，覆盖：
1. 报告头 / 摘要统计
2. 被测主机情况（IP/MAC/主机名/OS/开放端口/数据库）
3. 测试方法（端口范围 / 工具 / 具体步骤）
4. AI 攻击路径分析
5. 分步攻击详情（工具/配置/命令/结果/证据/人工核验方法/截图）
6. 漏洞汇总表
7. 单个漏洞详细分析 + 补丁链接
8. 修复建议汇总 + 页脚

输入为统一的 context dict（由 build_report_context 从 ScanResult 等聚合），
不依赖 GUI，可被 CLI / GUI 复用。
"""
from __future__ import annotations

import html
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 归一化：把 ScanResult 对象 / 任意 dict 转成报告可消费的纯 dict
# ---------------------------------------------------------------------------

def _get(obj: Any, key: str, default: Any = None) -> Any:
    """兼容 dict 与 dataclass 对象（含 Vulnerability.raw 透传）的取值。"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    if obj is None:
        return default
    if hasattr(obj, key):
        return getattr(obj, key, default)
    return default


def _vuln_to_dict(v: Any) -> Dict:
    """把 Vulnerability 对象/dict 归一化为完整漏洞 dict，优先用 raw（引擎富化后的完整字段）。"""
    raw = _get(v, "raw", None)
    if isinstance(raw, dict) and raw:
        base = dict(raw)
        if not base.get("cve_id"):
            ft = base.get("finding_type")
            if ft:
                base["cve_id"] = f"FINDING:{ft}"
        return base
    return {
        "cve_id": _get(v, "cve_id", ""),
        "description": _get(v, "description", ""),
        "severity": _get(v, "severity", ""),
        "cvss_score": _get(v, "cvss_score", 0.0),
        "product": _get(v, "product", ""),
        "version": _get(v, "version", ""),
        "host": _get(v, "host", ""),
        "port": _get(v, "port", 0),
        "service": _get(v, "service", ""),
        "protocol": _get(v, "protocol", "tcp"),
        "finding_type": _get(v, "finding_type", ""),
        "affected_versions": _get(v, "affected_versions", ""),
        "references_url": _get(v, "references_url", ""),
        "patch_link": _get(v, "patch_link", ""),
        "match_confidence": _get(v, "match_confidence", ""),
        "matched_by": _get(v, "matched_by", ""),
        "cwe": _get(v, "cwe_id", "") or _get(v, "cwe", ""),
        "evidence": _get(v, "evidence", {}) or {},
        "remediation": _get(v, "remediation", {}) or {},
    }


def build_report_context(
    scan_result: Any = None,
    ai_analysis: Optional[Dict] = None,
    attack_steps: Optional[List[Dict]] = None,
) -> Dict:
    """聚合 ScanResult（对象或 dict）、AI 分析、攻击步骤为统一 context。

    scan_result 支持 core.scanner.ScanResult 对象或等价 dict。
    """
    if scan_result is None:
        scan_result = {}
    hosts = _get(scan_result, "hosts", []) or []
    hosts = [h if isinstance(h, dict) else h.__dict__ for h in hosts]
    services = _get(scan_result, "services", []) or []
    services = [s if isinstance(s, dict) else s.__dict__ for s in services]
    vulns = [_vuln_to_dict(v) for v in (_get(scan_result, "vulnerabilities", []) or [])]

    scan = {
        "hosts": hosts,
        "services": services,
        "vulnerabilities": vulns,
        "statistics": _get(scan_result, "statistics", {}) or {},
        "web_findings": _get(scan_result, "web_findings", []) or [],
        "scan_config": _get(scan_result, "scan_config", {}) or {},
    }
    return {
        "scan": scan,
        "ai_analysis": ai_analysis or {},
        "attack_steps": attack_steps or [],
    }


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

_SEV_COLORS = {
    "critical": "#c62828", "high": "#e65100", "medium": "#f9a825",
    "low": "#2e7d32", "info": "#546e7a", "unknown": "#546e7a",
}
_SEV_LABEL = {
    "critical": "严重", "high": "高危", "medium": "中危",
    "low": "低危", "info": "信息", "unknown": "未知",
}

_DB_SERVICES = {
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "pgsql": "PostgreSQL",
    "mysql": "MySQL", "mariadb": "MariaDB", "mssql": "SQL Server",
    "ms-sql-s": "SQL Server", "sql server": "SQL Server",
    "redis": "Redis", "mongodb": "MongoDB", "mongod": "MongoDB",
    "oracle": "Oracle", "elasticsearch": "Elasticsearch",
    "memcached": "Memcached", "rabbitmq": "RabbitMQ",
}

_VERIFY_METHODS = {
    "rce": "登录目标命令行执行 whoami / hostname / ipconfig(ifconfig) 核对身份与权限是否提升",
    "msf": "在 Metasploit 会话执行 sysinfo / getuid / ipconfig，核对 meterpreter 会话是否建立并截图",
    "getshell": "打开反弹 shell 终端，执行 whoami / id 确认取得目标 shell",
    "privesc": "对比提权前后 whoami 输出，确认已从低权限账号提升到 SYSTEM/root",
    "privesc_enum": "查看 linpeas/winpeas 输出中的高亮提权线索（SUID/未引用服务路径/内核版本）",
    "lateral_movement": "在新横向目标执行 whoami / hostname，确认已横向到目标主机",
    "credential_dump": "核对导出的 NTLM/Kerberos 哈希是否包含有效域账户凭据",
    "bloodhound": "在 BloodHound 界面确认目标到域控的最短攻击路径",
    "sql_injection": "浏览器访问注入 URL，观察是否返回数据库报错/越权数据并截图",
    "xss": "浏览器访问注入点，观察弹窗/回显是否触发脚本并截图",
    "auth_bypass": "用低权限/未登录身份访问受保护页面，确认可绕过认证",
    "info_disclosure": "访问泄露页面/接口，确认敏感信息（配置/密钥/用户列表）可见",
    "weak_password": "用命中凭据登录对应服务（SSH/数据库/后台），确认可成功认证",
    "open_service": "核对开放端口的服务名与版本，判断暴露面与后续利用方向",
}


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def _sev_color(sev: str) -> str:
    return _SEV_COLORS.get((sev or "").lower(), "#546e7a")


def _sev_label(sev: str) -> str:
    return _SEV_LABEL.get((sev or "").lower(), str(sev or "未知"))


def _ref_links(vuln: Dict) -> List[str]:
    refs: List[str] = []
    seen = set()

    def add(r):
        r = (r or "").strip()
        if r and r not in seen:
            seen.add(r)
            refs.append(r)

    cid = (vuln.get("cve_id") or "").strip()
    if cid and cid.upper() != "N/A" and not cid.startswith("FINDING:"):
        add(f"https://nvd.nist.gov/vuln/detail/{cid}")
    for u in str(vuln.get("references_url") or "").split(","):
        add(u)
    add(vuln.get("patch_link") or "")
    return refs


def _render_ref_links(refs: List[str]) -> str:
    if not refs:
        return '<span class="muted">暂无</span>'
    parts = []
    for r in refs:
        if r.lower().startswith(("http://", "https://")):
            parts.append(f'<a href="{_esc(r)}" target="_blank">{_esc(r)}</a>')
        else:
            parts.append(_esc(r))
    return "、".join(parts)


def _section_header(title: str, anchor: str = "") -> str:
    aid = f' id="{anchor}"' if anchor else ""
    return f'<div class="section-title"{aid}>{_esc(title)}</div>'


def _render_summary_stats(scan: Dict) -> str:
    stats = scan.get("statistics") or {}
    vulns = scan.get("vulnerabilities") or []
    sev_cnt = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "unknown": 0}
    for v in vulns:
        s = (v.get("severity") or "unknown").lower()
        sev_cnt[s] = sev_cnt.get(s, 0) + 1
    cards = [
        ("总发现", stats.get("vuln_count", len(vulns))),
        ("严重", sev_cnt["critical"]),
        ("高危", sev_cnt["high"]),
        ("中危", sev_cnt["medium"]),
        ("低危", sev_cnt["low"]),
        ("弱口令", stats.get("weak_password_count", 0)),
        ("Web 发现", stats.get("web_finding_count", len(scan.get("web_findings") or []))),
        ("蜜罐", stats.get("honeypot_count", 0)),
    ]
    cells = "".join(
        f'<div class="stat"><div class="stat-num">{_esc(v)}</div><div class="stat-label">{_esc(k)}</div></div>'
        for k, v in cards
    )
    return f'<div class="stats">{cells}</div>'


def _render_host_info(scan: Dict) -> str:
    hosts = scan.get("hosts") or []
    services = scan.get("services") or []
    rows = []
    for h in hosts:
        ip = h.get("ip", "")
        ports = [s for s in services if s.get("host_ip") == ip]
        open_ports = ", ".join(str(s.get("port")) for s in ports)
        dbs = []
        for s in ports:
            svc = (s.get("service_name") or "").lower()
            prod = (s.get("product") or "").lower()
            for k, label in _DB_SERVICES.items():
                if k in svc or k in prod:
                    ver = s.get("version") or ""
                    dbs.append(f"{label} {ver}".strip())
                    break
        rows.append(f"""
        <tr>
          <td>{_esc(ip)}</td>
          <td>{_esc(h.get('mac') or 'N/A')}</td>
          <td>{_esc(h.get('hostname') or '')}</td>
          <td>{_esc(h.get('os') or '未识别（可开启 OS 检测）')}</td>
          <td>{_esc(open_ports) or '无'}</td>
          <td>{_esc('；'.join(dict.fromkeys(dbs)) or '未识别数据库')}</td>
        </tr>""")
    body = "".join(rows)
    return f"""
    <table>
      <thead><tr><th>IP</th><th>MAC 地址</th><th>主机名</th><th>操作系统</th><th>开放端口</th><th>数据库</th></tr></thead>
      <tbody>{body}</tbody>
    </table>"""


def _render_methodology(scan: Dict) -> str:
    cfg = scan.get("scan_config") or {}
    ports = cfg.get("ports") or "1-1000,3306,3389,5432,6379,8080,8443（默认）"

    tools = ["Nmap（端口/服务/版本识别）"]
    if cfg.get("os_detect"):
        tools.append("Nmap -O（操作系统指纹）")
    if cfg.get("web_scan"):
        tools.append("Web 主动漏洞扫描器（SQLi/XSS/SSRF/XXE/路径遍历等 45+ 项 DAST）")
    if cfg.get("weak_pass"):
        tools.append("弱口令爆破器（SSH/FTP/MySQL/PostgreSQL/Redis/MongoDB/HTTP/RDP/Telnet）")
    tools.extend(["Metasploit（getshell）", "Impacket（wmiexec/psexec/secretsdump）",
                  "NetExec（横向移动）", "BloodHound（域攻击路径）", "Mimikatz（凭据提取）"])

    steps = ["扫描主机端口（确定开放端口与协议）", "扫描服务与版本（识别产品及版本指纹）"]
    if cfg.get("os_detect"):
        steps.append("扫描操作系统（Nmap -O 指纹识别）")
    steps.append("识别数据库及版本（PostgreSQL/MySQL/Redis/MongoDB/SQL Server 等）")
    if cfg.get("web_scan"):
        steps.append("Web 应用主动漏洞扫描（注入面发现 + 45+ 项检测）")
    if cfg.get("weak_pass"):
        steps.append("弱口令爆破（对开放认证服务做保守字典爆破）")
    steps.extend([
        "getshell（漏洞利用获取目标 shell）",
        "提升权限（本地提权枚举与利用）",
        "横向移动（凭据喷洒 / 域内横向）",
        "暴力破解 / 凭据提取（Mimikatz / secretsdump）",
    ])

    return f"""
    <p><b>扫描目标：</b>{_esc(cfg.get('target') or '')}</p>
    <p><b>端口范围：</b>{_esc(ports)}</p>
    <p><b>扫描参数：</b>版本检测={bool(cfg.get('version_detect'))}，OS 检测={bool(cfg.get('os_detect'))}，
        Web 扫描={bool(cfg.get('web_scan'))}，弱口令={bool(cfg.get('weak_pass'))}</p>
    <p><b>采用工具：</b>{_esc('、'.join(tools))}</p>
    <p><b>具体步骤：</b></p>
    <ol>{''.join(f'<li>{_esc(s)}</li>' for s in steps)}</ol>"""


def _render_ai_attack_paths(ai: Dict) -> str:
    paths = ai.get("attack_paths") or []
    if not paths:
        return '<p class="muted">未执行 AI 攻击路径分析（可在界面点击「AI 分析」后重新导出）。</p>'
    blocks = []
    for p in paths:
        pid = p.get("path_id", p.get("id", ""))
        steps = p.get("steps", []) or []
        target = p.get("target", "")
        blocks.append(f"""
        <div class="risk-card" style="border-left:5px solid #1a73e8;">
          <div class="risk-card-header"><span class="risk-card-title">攻击路径 {_esc(pid)} → {_esc(target)}</span></div>
          <div class="risk-card-body"><ol>{''.join(f'<li>{_esc(s)}</li>' for s in steps)}</ol></div>
        </div>""")
    return "".join(blocks)


def _render_attack_steps(steps: List[Dict], evidence_dir: str) -> str:
    if not steps:
        return '<p class="muted">本次未执行攻击链（可在界面点击「执行攻击链」后重新导出）。</p>'
    rows = []
    for i, s in enumerate(steps, 1):
        etype = s.get("exploit_type") or s.get("step_id") or ""
        tool = s.get("tool") or "-"
        status = (s.get("status") or "").upper()
        status_color = "#2e7d32" if status in ("SUCCESS", "COMPLETED", "成功") else (
            "#c62828" if status in ("FAILED", "ERROR") else "#f9a825")
        evidence = s.get("evidence") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        ev_html = ""
        if evidence:
            ev_html = '<pre class="evidence">' + _esc("\n".join(str(e) for e in evidence)) + "</pre>"
        shot = s.get("screenshot") or ""
        shot_html = ""
        if shot:
            rel = os.path.relpath(shot, evidence_dir) if os.path.isabs(shot) else shot
            shot_html = f'<p><img src="{_esc(rel)}" style="max-width:100%;border:1px solid #e0e0e0;"/></p>'
        verify = _VERIFY_METHODS.get(etype, "核对攻击输出与目标状态，确认攻击是否成功")
        cmd = s.get("command") or s.get("validation_cmd") or s.get("payload") or "-"
        rows.append(f"""
        <div class="risk-card" style="border-left:5px solid {status_color};">
          <div class="risk-card-header">
            <span class="risk-card-title">#{i} {_esc(etype)} — {_esc(tool)}</span>
            <span style="color:{status_color};font-weight:bold;">{_esc(status)}</span>
          </div>
          <div class="risk-card-body">
            <p><b>目标：</b>{_esc(s.get('target') or '-')}　<b>描述：</b>{_esc(s.get('description') or '-')}</p>
            <p><b>命令/配置：</b><code>{_esc(cmd)}</code></p>
            {ev_html}
            {shot_html}
            <p><b>人工核验方法：</b>{_esc(verify)}（核验后截图保存，供报告佐证）</p>
          </div>
        </div>""")
    return "".join(rows)


def _render_vuln_summary(vulns: List[Dict]) -> str:
    rows = []
    for v in vulns:
        cid = v.get("cve_id") or "-"
        sev = v.get("severity") or "unknown"
        patch = v.get("patch_link") or ""
        if patch.lower().startswith(("http://", "https://")):
            patch_html = f'<a href="{_esc(patch)}" target="_blank">补丁</a>'
        else:
            patch_html = _esc(patch) if patch else "-"
        conf = v.get("match_confidence") or ""
        conf_label = {"high": "高", "medium": "中", "low": "低"}.get(conf, "")
        rows.append(f"""
        <tr>
          <td>{_esc(v.get('host') or '')}</td>
          <td>{_esc(v.get('port') or '')}</td>
          <td>{_esc(v.get('protocol') or 'tcp')}</td>
          <td>{_esc(v.get('service') or '')}</td>
          <td>{_esc(v.get('version') or v.get('product') or '')}</td>
          <td>{_esc(cid)}</td>
          <td><span style="color:{_sev_color(sev)};font-weight:bold;">{_esc(_sev_label(sev))}</span></td>
          <td>{_esc(v.get('cvss_score') or '-')}</td>
          <td>{patch_html}</td>
          <td>{_esc(conf_label)}</td>
        </tr>""")
    body = "".join(rows)
    return f"""
    <table>
      <thead><tr><th>主机</th><th>端口</th><th>协议</th><th>服务</th><th>版本</th><th>CVE</th><th>严重度</th><th>CVSS</th><th>补丁</th><th>置信度</th></tr></thead>
      <tbody>{body}</tbody>
    </table>"""


def _render_vuln_detail(vulns: List[Dict]) -> str:
    cards = []
    for i, v in enumerate(vulns, 1):
        cid = v.get("cve_id") or "服务检测"
        sev = v.get("severity") or "unknown"
        refs = _render_ref_links(_ref_links(v))
        ev = v.get("evidence") or {}
        rem = v.get("remediation") or {}
        rem_steps = rem.get("steps") or ([rem.get("summary")] if rem.get("summary") else [])
        rem_html = "".join(f"<li>{_esc(s)}</li>" for s in rem_steps)
        ev_rows = ""
        if ev:
            for k in ("service", "version", "product", "host", "port", "matched_by", "summary"):
                if ev.get(k):
                    ev_rows += f"<tr><td><b>{_esc(k)}</b></td><td>{_esc(ev.get(k))}</td></tr>"
        cwe = v.get("cwe") or v.get("cwe_id") or ""
        conf = v.get("match_confidence") or ""
        conf_label = {"high": "高", "medium": "中", "low": "低"}.get(conf, "")
        ft = v.get("finding_type") or ""
        ft_badge = f'<span class="badge">{_esc(ft)}</span>' if ft else ""
        cards.append(f"""
        <div class="risk-card" style="border-left:5px solid {_sev_color(sev)};">
          <div class="risk-card-header">
            <span class="risk-card-title">#{i} {_esc(cid)} — {_esc(v.get('service') or '')} 端口{_esc(v.get('port') or '')} {ft_badge}</span>
            <span style="color:{_sev_color(sev)};font-weight:bold;">{_esc(_sev_label(sev))} / CVSS {_esc(v.get('cvss_score') or '-')}</span>
          </div>
          <div class="risk-card-body">
            <p><b>漏洞描述：</b>{_esc(v.get('description') or '')}</p>
            <table class="mini">{ev_rows}
              <tr><td><b>CWE</b></td><td>{_esc(cwe or 'N/A')}</td></tr>
              <tr><td><b>匹配置信度</b></td><td>{_esc(conf_label or 'N/A')}（{_esc(v.get('matched_by') or '')}）</td></tr>
            </table>
            <p><b>修复方案：</b></p><ul>{rem_html}</ul>
            <p><b>参考链接 &amp; 补丁地址：</b>{refs}</p>
          </div>
        </div>""")
    return "".join(cards)


def _render_web_findings(web_findings: List[Dict]) -> str:
    if not web_findings:
        return ""
    rows = []
    for f in web_findings:
        rows.append(f"""
        <tr>
          <td><span style="color:{_sev_color(f.get('severity') or 'medium')};font-weight:bold;">{_esc(_sev_label(f.get('severity') or 'medium'))}</span></td>
          <td>{_esc(f.get('category') or f.get('title') or '-')}</td>
          <td>{_esc(f.get('url') or '-')}</td>
          <td>{_esc(f.get('detail') or f.get('evidence') or '-')}</td>
          <td>{_esc(f.get('remediation') or '-')}</td>
        </tr>""")
    body = "".join(rows)
    return _section_header(f"Web 应用漏洞发现（{len(web_findings)}）", "web-findings") + f"""
    <table>
      <thead><tr><th>严重度</th><th>类型/标题</th><th>URL</th><th>证据</th><th>修复建议</th></tr></thead>
      <tbody>{body}</tbody>
    </table>"""


def _render_remediation_summary(vulns: List[Dict], ai: Dict) -> str:
    # 修复优先级（按紧急度，来自各漏洞 remediation.urgency）
    priorities = []
    for v in vulns:
        rem = v.get("remediation") or {}
        u = rem.get("urgency")
        if u and u not in priorities:
            priorities.append(u)
    urgency_items = [f"<li>{_esc(u)}</li>" for u in priorities]
    if not urgency_items:
        urgency_items = ["<li>优先修复「在野利用(KEV)」与 CVSS≥9.0 的漏洞</li>",
                         "<li>升级受影响服务到安全版本，参照漏洞卡片的补丁链接</li>",
                         "<li>配置防火墙限制暴露面，遵循最小权限原则</li>",
                         "<li>修复后重新扫描验证漏洞已消除</li>"]

    urgency_html = '<h4>修复优先级（按紧急度）</h4><ul>' + "".join(urgency_items) + "</ul>"

    # AI 修复建议（来自 AI 分析，与紧急度优先级整合到本节）
    recs = ai.get("recommendations") or []
    ai_html = ""
    if recs:
        ai_html = '<h4>AI 修复建议</h4><ul>' + "".join(f"<li>{_esc(r)}</li>" for r in recs) + "</ul>"

    return urgency_html + ai_html


_CSS = """
body { font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif; margin: 0; color: #222; background: #fff; }
.container { max-width: 1100px; margin: 0 auto; padding: 24px; }
.hero { background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); color: #fff; padding: 32px 28px; border-radius: 12px; }
.hero h1 { margin: 0 0 8px; font-size: 24px; }
.hero .sub { opacity: .85; font-size: 13px; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
.stat { background: #f5f7fa; border-radius: 8px; padding: 16px; text-align: center; border: 1px solid #e8ecf1; }
.stat-num { font-size: 28px; font-weight: 700; color: #1a73e8; }
.stat-label { color: #666; font-size: 12px; margin-top: 4px; }
.section-title { color: #1a73e8; border-left: 4px solid #1a73e8; padding: 4px 14px; margin: 28px 0 14px; font-size: 18px; font-weight: 600; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }
th, td { border: 1px solid #e0e0e0; padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f5f7fa; }
table.mini td { padding: 4px 8px; font-size: 12px; border: none; }
.risk-card { background: #fafafa; margin: 14px 0; border-radius: 8px; overflow: hidden; }
.risk-card-header { background: #fff; padding: 12px 18px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.risk-card-title { font-weight: 700; font-size: 14px; }
.risk-card-body { padding: 16px 18px; font-size: 13px; line-height: 1.7; }
.badge { background: #eceff1; color: #455a64; font-size: 11px; padding: 1px 8px; border-radius: 10px; margin-left: 6px; }
.muted { color: #888; }
.evidence { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
.footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #eee; color: #999; font-size: 12px; text-align: center; }
a { color: #1a73e8; text-decoration: none; }
code { background: #f0f0f0; padding: 1px 6px; border-radius: 4px; font-size: 12px; }
"""


def build_report_html(context: Dict, evidence_dir: str = "reports") -> str:
    """根据 context 渲染完整 HTML 报告字符串。"""
    scan = context.get("scan") or {}
    ai = context.get("ai_analysis") or {}
    steps = context.get("attack_steps") or []
    vulns = scan.get("vulnerabilities") or []
    cfg = scan.get("scan_config") or {}

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target = cfg.get("target") or "N/A"

    html_body = "".join([
        f'<div class="hero"><h1>AI-PTS 渗透测试报告</h1>'
        f'<div class="sub">目标：{_esc(target)}　|　生成时间：{ts}　|　'
        f'扫描时长：{_esc(cfg.get("duration") or "N/A")} 秒</div></div>',
        _render_summary_stats(scan),
        _section_header("一、被测主机情况", "host"),
        _render_host_info(scan),
        _section_header("二、测试方法", "method"),
        _render_methodology(scan),
        _section_header("三、AI 攻击路径分析", "ai-path"),
        _render_ai_attack_paths(ai),
        _section_header("四、分步攻击详情", "attack"),
        _render_attack_steps(steps, evidence_dir),
        _section_header("五、漏洞汇总表", "summary"),
        _render_vuln_summary(vulns),
        _render_web_findings(scan.get("web_findings") or []),
        _section_header("六、漏洞详细分析 & 补丁链接", "detail"),
        _render_vuln_detail(vulns),
        _section_header("七、修复建议汇总", "remediation"),
        _render_remediation_summary(vulns, ai),
        '<div class="footer">本报告由 AI-PTS 自动生成，仅供参考。部署修复方案前请结合人工核验与实际环境验证。</div>',
    ])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-PTS 渗透测试报告 - {_esc(target)}</title>
<style>{_CSS}</style>
</head>
<body><div class="container">{html_body}</div></body>
</html>"""


def save_report(context: Dict, output_dir: str = "reports", target: str = None,
                timestamp: str = None) -> str:
    """渲染并写盘，返回 HTML 文件路径。"""
    os.makedirs(output_dir, exist_ok=True)
    target = target or (context.get("scan") or {}).get("scan_config", {}).get("target") or "target"
    target = str(target).replace(":", "_").replace("/", "_").replace("\\", "_")
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"渗透测试报告_{target}_{timestamp}.html")
    html_content = build_report_html(context, evidence_dir=output_dir)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return path
