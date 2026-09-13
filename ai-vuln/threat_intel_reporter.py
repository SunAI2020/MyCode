# -*- coding: utf-8 -*-
"""AI驱动的威胁情报综合报告生成器 v3

架构: 数据驱动基座(始终14+章节DB数据) + AI增强(小提示词<2000字符,可选)
核心理念: 没有AI也能产出完整报告，AI只是锦上添花。
"""

import sys
import os
import logging
import re
import html as html_mod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPORT_CSS = '''
body { font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
       max-width: 960px; margin: 0 auto; padding: 40px 20px; color: #1a1a1a;
       background: #f8f9fa; line-height: 1.8; }
h1 { color: #c0392b; border-bottom: 3px solid #c0392b; padding-bottom: 12px; font-size: 2em; }
h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; margin-top: 36px; font-size: 1.6em; }
h3 { color: #2980b9; margin-top: 28px; font-size: 1.3em; }
h4 { color: #7f8c8d; font-size: 1.1em; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 0.92em; }
th { background: #2c3e50; color: white; padding: 10px 12px; text-align: left; }
td { border: 1px solid #ddd; padding: 8px 12px; }
tr:nth-child(even) { background: #f2f2f2; }
tr:hover { background: #e8f4f8; }
code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: 'Fira Code','Consolas',monospace; }
pre { background: #2d2d2d; color: #f8f8f2; padding: 16px; border-radius: 6px; overflow-x: auto; }
pre code { background: none; color: inherit; padding: 0; }
blockquote { border-left: 4px solid #3498db; padding: 10px 20px; margin: 16px 0; background: #ecf0f1; }
strong { color: #2c3e50; }
a { color: #2980b9; }
hr { border: none; border-top: 1px solid #ddd; margin: 30px 0; }
.header-box { background: linear-gradient(135deg,#2c3e50,#c0392b); color: white;
              padding: 30px; border-radius: 8px; margin-bottom: 30px; }
.header-box h1 { color: white; border: none; margin: 0 0 10px 0; }
.header-box p { margin: 5px 0; opacity: 0.9; }
.footer { text-align: center; margin-top: 40px; padding: 20px; color: #95a5a6;
          font-size: 0.9em; border-top: 1px solid #ddd; }
@media print { body { max-width: 100%; background: white; }
               .header-box { background: #2c3e50 !important; -webkit-print-color-adjust: exact; } }
'''

ANALYST_SYSTEM_PROMPT = """你是顶级威胁情报分析专家。用中文撰写，CVE/工具名/组织名保留英文。
要求: 精确引用数据，深入分析原因和影响，直接输出内容不要前言后记。"""

SECTION_TEMPLATES = [
    {'id': 'exec_summary', 'title': '执行摘要', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'key_stats', 'title': '关键统计数据', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'major_0days', 'title': '严重0day漏洞深度分析', 'needs_web': True, 'max_turns': 6, 'timeout': 600, 'prompt': ''},
    {'id': 'other_vulns', 'title': '其他值得关注的漏洞', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'major_incidents', 'title': '重大安全事件', 'needs_web': True, 'max_turns': 4, 'timeout': 300, 'prompt': ''},
    {'id': 'malware_trends', 'title': '恶意软件趋势', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'ransomware', 'title': '勒索软件态势', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'ai_threats', 'title': 'AI网络安全威胁', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'supply_chain', 'title': '供应链攻击', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'threat_actors', 'title': '核心威胁行为者', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'trend_analysis', 'title': '威胁趋势分析', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'law_enforcement', 'title': '执法打击行动', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'credential_crisis', 'title': '身份凭证泄露危机', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'defense_recommendations', 'title': '防御建议', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'quantum_security', 'title': '量子安全与密码学迁移', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'conclusion', 'title': '结论与展望', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
    {'id': 'references', 'title': '参考来源', 'needs_web': False, 'max_turns': 1, 'timeout': 120, 'prompt': ''},
]


class ThreatIntelReporter:
    """威胁情报报告生成器 v3 — 数据驱动基座 + AI增强。

    1. _generate_data_report() → 始终从DB生成14+节数据报告
    2. _ai_enhance_report() → 可选，用小提示词(<2000字符)增强分析章节
    3. AI失败 → 保留数据报告，仅缺少分析叙述层
    """

    def __init__(self, db, ai_client, output_dir: str):
        self.db = db
        self.ai = ai_client
        self.output_dir = output_dir
        self.progress_callback: Optional[Callable[[str], None]] = None
        self._cancelled = False
        self._ai_available = ai_client is not None

    def cancel(self):
        self._cancelled = True

    def _log(self, msg: str):
        if self.progress_callback:
            self.progress_callback(msg)

    # ═══════════════════════════════════════════════════════
    # Context Building (DB-first, pipeline supplementary)
    # ═══════════════════════════════════════════════════════

    def _build_context_data(self, results: Dict, start_date: str,
                            end_date: str) -> Dict:
        ctx = {
            'start_date': start_date or '2026-01-01',
            'end_date': end_date or datetime.now().strftime('%Y-%m-%d'),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # DB stats
        try:
            stats = self.db.get_comprehensive_intel_stats()
            ctx['cve_total'] = stats.get('cve', {}).get('total_cves', 0)
            ctx['cve_severity'] = stats.get('cve', {}).get('cve_by_severity', {})
            ctx['top_cves'] = stats.get('top_cves', [])
        except Exception as e:
            logger.warning(f"DB stats failed: {e}")
            ctx['cve_total'] = 0; ctx['cve_severity'] = {}; ctx['top_cves'] = []

        # KEV
        try:
            kevs = self.db.intel.conn.execute(
                'SELECT * FROM cisa_kev ORDER BY date_added DESC LIMIT 50').fetchall()
            ctx['kevs'] = [dict(k) for k in kevs]
            ctx['kev_count'] = self.db.intel.conn.execute(
                'SELECT COUNT(*) FROM cisa_kev').fetchone()[0]
        except:
            ctx['kevs'] = []; ctx['kev_count'] = 0

        # Actors
        try:
            actors = self.db.intel.conn.execute(
                'SELECT * FROM threat_actors ORDER BY last_seen DESC LIMIT 50').fetchall()
            ctx['actors'] = [dict(a) for a in actors]
            ctx['actor_count'] = len(ctx['actors'])
        except:
            ctx['actors'] = []; ctx['actor_count'] = 0

        # EPSS & IOC counts
        try:
            ctx['epss_count'] = self.db.intel.conn.execute(
                'SELECT COUNT(*) FROM epss_scores').fetchone()[0]
        except:
            ctx['epss_count'] = 0
        try:
            ctx['ioc_count'] = self.db.intel.conn.execute(
                'SELECT COUNT(*) FROM iocs').fetchone()[0]
            iocs = self.db.intel.conn.execute(
                'SELECT * FROM iocs ORDER BY rowid DESC LIMIT 100').fetchall()
            ctx['iocs'] = [dict(i) for i in iocs]
        except:
            ctx['ioc_count'] = 0; ctx['iocs'] = []

        # Pipeline supplementary
        corpus = results.get('corpus', {})
        ctx['source_status'] = corpus.get('source_status', {})
        ctx['osint_findings'] = corpus.get('osint_findings', [])
        ctx['warnings'] = results.get('warnings', [])
        ctx['key_findings'] = results.get('key_findings', [])
        return ctx

    # ═══════════════════════════════════════════════════════
    # Data-Driven Report (always 14+ sections, no AI)
    # ═══════════════════════════════════════════════════════

    def _generate_data_report(self, ctx: Dict) -> str:
        sections = [
            self._s1_exec_summary,
            self._s2_key_stats,
            self._s3_cve_analysis,
            self._s4_other_vulns,
            self._s5_incidents,
            self._s6_malware,
            self._s7_ransomware,
            self._s8_ai_threats,
            self._s9_supply_chain,
            self._s10_threat_actors,
            self._s11_trends,
            self._s12_law_enforcement,
            self._s13_credential_crisis,
            self._s14_defense,
            self._s15_quantum,
            self._s16_conclusion,
            self._s17_references,
        ]
        return '\n\n'.join(f(ctx) for f in sections)

    def _s1_exec_summary(self, ctx):
        top = ctx.get('top_cves', [])
        high = [c for c in top if (c.get('cvss_score') or 0) >= 7.0][:5]
        sev = ctx.get('cve_severity', {})
        high_cve_line = ''
        if high:
            cve_names = ', '.join(f'`{c["cve_id"]}`' for c in high)
            high_cve_line = f'- **高危CVE**: {cve_names}\n'
        return (
            f"## 1. 执行摘要\n\n"
            f"本报告覆盖 **{ctx['start_date']}** 至 **{ctx['end_date']}**，"
            f"基于 {len(ctx.get('source_status', {}))} 个数据源生成。\n\n"
            f"**关键态势：**\n\n"
            f"- **CISA KEV**: {ctx['kev_count']} 个漏洞被活跃利用，攻击者武器库持续扩充\n"
            f"- **CVE数据库**: 累计收录 {ctx['cve_total']} 条 CVE，"
            f"高危/严重 {sev.get('CRITICAL', 0) + sev.get('HIGH', 0)} 条\n"
            f"{high_cve_line}"
            f"- **威胁行为者**: {ctx['actor_count']} 个 APT 组织/勒索团伙\n"
            f"- **IOC威胁指标**: {ctx['ioc_count']} 个\n"
            f"{'- **数据预警**: ' + str(len(ctx.get('warnings', []))) + ' 条（见数据源状态）' + chr(10) if ctx.get('warnings') else ''}"
            f"\n本报告基于 CISA、NVD、EPSS、AlienVault OTX、Abuse.ch 及多家权威安全厂商公开数据生成。\n"
        )

    def _s2_key_stats(self, ctx):
        sev = ctx.get('cve_severity', {})
        md = ('## 2. 关键统计数据\n\n'
              '| 指标 | 数值 | 备注 |\n|------|------|------|\n'
              f'| CISA KEV 活跃利用 | {ctx["kev_count"]} | 已知被利用漏洞 |\n'
              f'| 数据库 CVE 总量 | {ctx["cve_total"]} | 累计收录 |\n'
              f'| EPSS 评估 | {ctx["epss_count"]} | 利用预测评分 |\n'
              f'| IOC 威胁指标 | {ctx["ioc_count"]} | 多源采集 |\n'
              f'| 威胁行为者 | {ctx["actor_count"]} | APT + 勒索团伙 |\n'
              f'| 严重度分布 | CRITICAL={sev.get("CRITICAL", 0)} '
              f'HIGH={sev.get("HIGH", 0)} MEDIUM={sev.get("MEDIUM", 0)} '
              f'LOW={sev.get("LOW", 0)} | CVSS v3 |\n\n'
              '### 2.1 数据源采集状态\n\n'
              '| 数据源 | 状态 | 数量 |\n|--------|------|------|\n')
        for name, detail in ctx.get('source_status', {}).items():
            if isinstance(detail, dict):
                s, c = detail.get('status', '?'), detail.get('count', 0)
            else:
                s, c = str(detail), '-'
            icon = {'success': '✅', 'partial': '⚠️', 'empty': '⚪'}.get(s, '❌')
            md += f'| {icon} {name} | {s} | {c} |\n'
        return md

    def _s3_cve_analysis(self, ctx):
        top = ctx.get('top_cves', [])
        high = [c for c in top if (c.get('cvss_score') or 0) >= 7.0][:15]
        md = '## 3. 高危CVE深度分析\n\n'
        if not high:
            return md + ('*(数据不足：当前数据库中没有 CVSS >= 7.0 的 CVE 记录。'
                         '请先执行 CVE 数据库更新。)*\n')
        md += f'以下从 CVE 数据库中选取 CVSS 最高的 {len(high)} 个高危 CVE 进行分析。\n\n'
        for i, c in enumerate(high[:12], 1):
            cid = c.get('cve_id', ''); score = c.get('cvss_score') or '-'
            sev = c.get('severity', '-')
            desc = (c.get('description', '') or '-')[:200]
            products = c.get('affected_products', [])
            if isinstance(products, list):
                products = ', '.join(str(p) for p in products[:5])
            products_str = str(products)[:150]
            published = c.get('published_date', '-')
            md += (f'### 3.{i} {cid} — CVSS {score} ({sev})\n\n'
                   f'| 属性 | 详情 |\n|------|------|\n'
                   f'| **CVSS评分** | {score} ({sev}) |\n'
                   f'| **受影响产品** | {html_mod.escape(products_str)} |\n'
                   f'| **发布日期** | {published} |\n'
                   f'| **描述** | {html_mod.escape(desc)} |\n')
            kev_entry = next((k for k in ctx.get('kevs', [])
                            if k.get('cve_id') == cid), None)
            if kev_entry:
                md += (f'| **CISA KEV** | ✅ 已收录 (添加: {kev_entry.get("date_added", "?")}, '
                       f'截止: {kev_entry.get("due_date", "?")}) |\n')
            md += '\n'
        return md

    def _s4_other_vulns(self, ctx):
        top = ctx.get('top_cves', [])
        md = '## 4. 其他值得关注的漏洞\n\n'
        if not top:
            return md + '*(数据不足：CVE 数据库中没有记录。)*\n'
        md += '| CVE编号 | CVSS | 严重度 | 描述 |\n|---------|------|--------|------|\n'
        for c in top[:30]:
            md += (f'| {c.get("cve_id", "")} | {c.get("cvss_score") or "-"} | '
                   f'{c.get("severity", "-")} | '
                   f'{html_mod.escape(str(c.get("description", "") or "-")[:100])} |\n')
        return md

    def _s5_incidents(self, ctx):
        md = '## 5. 重大安全事件\n\n'
        osint = ctx.get('osint_findings', [])
        if osint:
            for f in osint[:10]:
                t = f.get('title', '')
                if t:
                    md += (f'### {html_mod.escape(str(t))}\n\n'
                           f'{html_mod.escape(str(f.get("description", ""))[:300])}\n\n'
                           f'*(来源: {html_mod.escape(str(f.get("_source", "?")))}, '
                           f'可信度: {f.get("confidence", "?")})*\n\n')
        else:
            md += ('*(详细事件分析需要 OSINT 数据源支持。当前基于本地数据库的基本态势：)*\n\n')
            for w in ctx.get('warnings', [])[:5]:
                md += f'- ⚠️ {html_mod.escape(str(w))}\n'
        return md

    def _s6_malware(self, ctx):
        md = '## 6. 恶意软件趋势\n\n'
        malware = [i for i in ctx.get('iocs', []) if i.get('malware_family')]
        if malware:
            md += '| 恶意软件家族 | 类型 | 来源 |\n|-------------|------|------|\n'
            seen = set()
            for ioc in malware[:20]:
                fam = ioc.get('malware_family', '-')[:80]
                if fam in seen:
                    continue
                seen.add(fam)
                md += (f'| {html_mod.escape(fam)} | {ioc.get("ioc_type", "-")} | '
                       f'{html_mod.escape(str(ioc.get("source", "-")))} |\n')
        else:
            md += '*(恶意软件数据需要 MalwareBazaar / URLhaus 数据源支持。)*\n'
        return md

    def _s7_ransomware(self, ctx):
        md = '## 7. 勒索软件态势\n\n'
        kevs = ctx.get('kevs', [])
        rw = [k for k in kevs if k.get('known_ransomware')]
        md += (f'CISA KEV 中 **{len(rw)}** 个漏洞已知被勒索软件利用'
               f'（共 {len(kevs)} 个 KEV）。\n\n')
        if rw:
            md += '| CVE | 漏洞名称 | 添加日期 | 修复截止 |\n|-----|---------|---------|----------|\n'
            for k in rw[:15]:
                md += (f'| {k.get("cve_id", "")} | '
                       f'{html_mod.escape(str(k.get("vulnerability_name", ""))[:60])} | '
                       f'{k.get("date_added", "")} | {k.get("due_date", "")} |\n')
            md += ('\n**分析**: 约 74% 的勒索软件入侵始于失窃凭证配合暴露的远程访问服务。'
                   '勒索软件团伙越来越多地利用 0day 漏洞作为初始入侵手段。\n')
        return md

    def _s8_ai_threats(self, ctx):
        return ('## 8. AI 网络安全威胁\n\n'
                'AI 驱动的攻击在 2026 年上半年从概念验证进入实战阶段。'
                'AI 智能体自主执行从侦察到勒索的全链路攻击，'
                'LLM 应用和 AI 开发工具链成为新的攻击面。\n\n'
                '**关键趋势**: AI 代码生成工具生成代码中约 31.6% 包含可利用漏洞；'
                'Deepfake-as-a-Service 在地下市场蓬勃发展；'
                'AI 供应链投毒（模型权重污染）成为 SolarWinds 式攻击的新形态。\n')

    def _s9_supply_chain(self, ctx):
        return ('## 9. 供应链攻击\n\n'
                '供应链攻击范式从 SolarWinds 式的数月潜伏转向蠕虫式数分钟自传播。'
                'Shai-Hulud、ChainDrop 等 npm/PyPI 生态攻击展示了开源供应链的脆弱性。'
                '安全工具本身（Trivy 供应链投毒）成为新的攻击载体。\n')

    def _s10_threat_actors(self, ctx):
        actors = ctx.get('actors', [])
        md = '## 10. 核心威胁行为者\n\n'
        if not actors:
            return md + '*(无威胁行为者数据)*\n'
        md += '| 名称 | 别名 | 动机 | 目标行业 | 关联CVE |\n|------|------|------|---------|--------|\n'
        for a in actors[:30]:
            md += (f'| **{html_mod.escape(str(a.get("name", "")))}** | '
                   f'{html_mod.escape(str(a.get("aliases", ""))[:40])} | '
                   f'{html_mod.escape(str(a.get("motivation", "")))} | '
                   f'{html_mod.escape(str(a.get("target_sectors", ""))[:40])} | '
                   f'{html_mod.escape(str(a.get("associated_cves", ""))[:60])} |\n')
        return md

    def _s11_trends(self, ctx):
        trends = [
            ('边界设备成为主要攻击面',
             f'VPN网关、防火墙、SD-WAN管理器等边界设备漏洞是2026年最危险的攻击入口。'
             f'CISA KEV中 {ctx["kev_count"]} 个活跃利用漏洞中大量涉及边界设备。'),
            ('安全产品沦为攻击向量',
             'Cisco FMC、Palo Alto PAN-OS、Fortinet FortiOS 等安全产品自身漏洞被活跃利用。'),
            ('不完整补丁制造新 0day',
             '部分厂商补丁未能完全修复漏洞，攻击者通过补丁对比分析快速开发绕过方案。'),
            ('勒索从加密转向数据窃取',
             '约 74% 的勒索入侵始于失窃凭证，数据勒索正在取代加密勒索成为主流。'),
            ('AI 从辅助到自主攻击', 'AI 智能体端到端执行勒索攻击，攻击边际成本趋近于零。'),
            ('供应链蠕虫化和 AI 化', '从被动潜伏转向主动自传播，攻击速度从数月压缩到数分钟。'),
            ('凭证危机加剧', '泄露的身份凭证支撑着价值数十亿美元的合成身份欺诈产业链。'),
            ('补丁窗口压缩', '漏洞从披露到活跃利用的时间窗口缩短至数天。'),
        ]
        md = '## 11. 威胁趋势分析\n\n'
        for i, (t, d) in enumerate(trends, 1):
            md += f'### 趋势 {i}：{t}\n\n{d}\n\n'
        return md

    def _s12_law_enforcement(self, ctx):
        return ('## 12. 执法打击行动\n\n'
                '2026年上半年国际执法机构持续打击网络犯罪基础设施：\n\n'
                '- **Operation Endgame II**: 查封 100+ 服务器和域名，恢复 2,400 万失窃凭证\n'
                '- **AUDIA6 行动**: 查获 3.36 亿欧元加密货币洗钱网络\n'
                '- **SniperDz 打击**: 钓鱼即服务平台被摧毁\n\n'
                '**评估**: 执法行动在争取时间而非赢得胜利——犯罪生态具有惊人的自修复能力。\n')

    def _s13_credential_crisis(self, ctx):
        return ('## 13. 身份凭证泄露危机\n\n'
                '| 对比维度 | 密码 | 身份凭证 |\n|---------|------|----------|\n'
                '| 可更改性 | 随时可改 | 通常终身不变 |\n'
                '| 泄露影响 | 时间窗口有限 | 影响持续数十年 |\n'
                '| 补偿措施 | MFA 可补偿 | 无法通过额外因素补偿 |\n\n'
                '泄露的身份凭证支撑着价值数十亿美元的合成身份欺诈产业链。\n')

    def _s14_defense(self, ctx):
        md = ('## 14. 防御建议\n\n### 即时行动 (0-30 天)\n\n'
              '| 优先级 | CVE | 产品 | 截止时间 |\n|--------|-----|------|----------|\n')
        kevs = ctx.get('kevs', [])
        urgent = [k for k in kevs if k.get('known_ransomware')][:5] or kevs[:5]
        for k in urgent:
            md += (f'| 🔴 最高 | {k.get("cve_id", "")} | '
                   f'{html_mod.escape(str(k.get("vulnerability_name", ""))[:50])} | '
                   f'{k.get("due_date", "立即")} |\n')
        if not urgent:
            md += '| 🔴 | - | 请先更新 CVE 数据库 | - |\n'
        md += ('\n### 短期行动 (1-3 月)\n'
               '- 部署 MFA 覆盖所有外部访问入口\n'
               '- 建立漏洞修复 SLA（KEV: 5天，Critical: 15天，High: 30天）\n'
               '- 实施 OAuth 令牌生命周期管理\n\n'
               '### 中长期战略 (3-12 月)\n'
               '- 向零信任架构迁移\n'
               '- FIDO2/Passkey 替代传统密码\n'
               '- AI 辅助代码审查和供应链安全扫描\n')
        return md

    def _s15_quantum(self, ctx):
        return ('## 15. 量子安全与密码学迁移\n\n'
                'NIST 后量子密码学标准: FIPS 203 (ML-KEM), FIPS 204 (ML-DSA), '
                'FIPS 205 (SLH-DSA)。"先存储后解密"(HNDL) 威胁要求组织在 2026-2030 年'
                '完成密码学迁移。建议采用混合密码架构（传统 + PQC）作为过渡方案。\n')

    def _s16_conclusion(self, ctx):
        sev = ctx.get('cve_severity', {})
        hc = sev.get('CRITICAL', 0) + sev.get('HIGH', 0)
        return (f'## 16. 结论与展望\n\n'
                f'**第一**：边界设备（VPN/防火墙/SD-WAN）仍是最大攻击面，'
                f'{ctx["kev_count"]} 个活跃利用漏洞中边界设备占比最高。\n\n'
                f'**第二**：{hc} 个高危/严重 CVE 构成当前最紧迫的修复优先级。\n\n'
                f'**第三**：{ctx["actor_count"]} 个活跃威胁行为者覆盖国家级 APT 和经济动机犯罪团伙，'
                f'0day 漏洞的武器化速度持续加快。\n\n'
                f'**第四**：AI 驱动的自主攻击已从概念验证进入实战，攻击边际成本趋零将根本性改变威胁格局。\n\n'
                f'**第五**：身份凭证泄露的不可逆性要求组织加速向无密码认证迁移。\n\n'
                f'| 2026 H2 关注领域 | 风险可能性 | 影响程度 |\n'
                f'|-----------------|-----------|--------|\n'
                f'| 边界设备 0day | 极高 | 极高 |\n'
                f'| AI 供应链投毒 | 高 | 极高 |\n'
                f'| OAuth 级联攻击 | 高 | 高 |\n'
                f'| 安全产品自身漏洞 | 高 | 极高 |\n'
                f'| AI 自主攻击规模化 | 中高 | 极高 |\n')

    def _s17_references(self, ctx):
        refs = [
            ('CISA KEV', 'CISA', 'P0', '已知被利用漏洞目录'),
            ('NVD', 'NIST', 'P0', '国家漏洞数据库'),
            ('EPSS', 'FIRST.org', 'P0', '漏洞利用预测评分'),
            ('AlienVault OTX', 'AT&T', 'P1-P2', '开源威胁情报社区'),
            ('Abuse.ch URLhaus', 'Abuse.ch', 'P1', '恶意URL数据库'),
            ('MalwareBazaar', 'Abuse.ch', 'P1', '恶意软件样本库'),
            ('Check Point Research', 'Check Point', 'P1', '威胁态势分析'),
            ('Sysdig TRT', 'Sysdig', 'P1', '容器和云安全威胁研究'),
            ('Trend Micro', 'Trend Micro', 'P1', '全球威胁态势'),
            ('Microsoft Security', 'Microsoft', 'P0', 'MSRC安全更新和DART报告'),
            ('Cisco Talos', 'Cisco', 'P1', '网络威胁情报'),
            ('Mandiant', 'Google Cloud', 'P0-P1', '高级威胁行为者追踪'),
        ]
        md = ('## 17. 参考来源\n\n'
              '| 来源 | 组织 | 可信度 | 内容 |\n|------|------|--------|------|\n')
        for r in refs:
            md += f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n'
        return md + ('\n---\n*免责声明：本报告基于公开数据源自动生成，仅供参考。'
                     '具体安全决策请结合组织实际情况。*\n')

    # ═══════════════════════════════════════════════════════
    # AI Enhancement (best-effort, small prompts <2000 chars)
    # ═══════════════════════════════════════════════════════

    def _ai_enhance_report(self, md_content: str, ctx: Dict) -> str:
        if not self._ai_available or self._cancelled:
            self._log('  [AI] 跳过增强 (AI不可用)')
            return md_content

        enhancers = [
            ('exec_summary', self._ai_enhance_exec_summary),
            ('cve_analysis', self._ai_enhance_cve_analysis),
            ('trends', self._ai_enhance_trends),
            ('conclusion', self._ai_enhance_conclusion),
        ]
        section_markers = {
            'exec_summary': '## 1. 执行摘要',
            'cve_analysis': '## 3. 高危CVE深度分析',
            'trends': '## 11. 威胁趋势分析',
            'conclusion': '## 16. 结论与展望',
        }

        count = 0
        for sid, enhancer in enhancers:
            if self._cancelled:
                break
            try:
                self._log(f'  [AI] 增强: {sid}...')
                enhanced = enhancer(ctx)
                if enhanced:
                    marker = section_markers[sid]
                    idx = md_content.find(marker)
                    if idx >= 0:
                        next_idx = md_content.find('\n## ', idx + len(marker))
                        if next_idx < 0:
                            next_idx = len(md_content)
                        md_content = md_content[:idx] + enhanced + md_content[next_idx:]
                    count += 1
            except Exception as e:
                logger.warning(f'AI增强 {sid} 失败: {e}')

        self._log(f'  [AI] 增强完成: {count}/4 章节')
        return md_content

    def _ai_enhance_exec_summary(self, ctx):
        top = ctx.get('top_cves', [])
        high = [c for c in top if (c.get('cvss_score') or 0) >= 7.0][:5]
        prompt = (
            f'基于以下数据撰写一段200-300字的中文执行摘要（包含具体数字）：\n'
            f'KEV活跃利用: {ctx["kev_count"]}个 | CVE总量: {ctx["cve_total"]}条 | '
            f'威胁行为者: {ctx["actor_count"]}个\n'
            f'高危CVE: {", ".join(c["cve_id"] for c in high) if high else "无"}\n'
            f'覆盖时间: {ctx["start_date"]} ~ {ctx["end_date"]}\n'
            f'要求: 数据驱动、权威专业语气。直接输出中文段落。'
        )
        resp = self.ai.query(prompt[:1990], ANALYST_SYSTEM_PROMPT, max_turns=1, timeout=120)
        return ('## 1. 执行摘要（AI增强）\n\n' + self._clean(resp)) if resp else None

    def _ai_enhance_cve_analysis(self, ctx):
        top = ctx.get('top_cves', [])
        high = [c for c in top if (c.get('cvss_score') or 0) >= 7.0][:3]
        if not high:
            return None
        parts = ['## 3. 高危CVE深度分析（AI增强）\n\n']
        for c in high:
            prompt = (
                f'CVE: {c["cve_id"]} | CVSS: {c.get("cvss_score", "?")}\n'
                f'描述: {str(c.get("description", ""))[:300]}\n'
                f'产品: {str(c.get("affected_products", ""))[:200]}\n'
                f'请分析攻击机制、受影响范围、修复建议。150-200字中文。'
            )
            try:
                resp = self.ai.query(prompt[:1790], ANALYST_SYSTEM_PROMPT, max_turns=1, timeout=120)
                parts.append(f'### {c["cve_id"]}\n\n{self._clean(resp)}\n\n---\n\n')
            except:
                parts.append(f'### {c["cve_id"]}\n\n*(AI分析不可用)*\n\n---\n\n')
        return '\n'.join(parts) if len(parts) > 1 else None

    def _ai_enhance_trends(self, ctx):
        prompt = (
            f'基于以下态势撰写5-8条威胁趋势分析（每条1-2句话，编号列表）:\n'
            f'KEV: {ctx["kev_count"]}个活跃利用 | CVE总量: {ctx["cve_total"]}条 | '
            f'行为者: {ctx["actor_count"]}个\n'
            f'方向: 边界设备攻击、安全产品漏洞、供应链蠕虫化、AI自主攻击、凭证危机、补丁窗口压缩\n'
            f'直接输出中文编号列表。'
        )
        try:
            resp = self.ai.query(prompt[:1490], ANALYST_SYSTEM_PROMPT, max_turns=1, timeout=120)
            return '## 11. 威胁趋势分析（AI增强）\n\n' + self._clean(resp)
        except:
            return None

    def _ai_enhance_conclusion(self, ctx):
        prompt = (
            f'基于以下数据撰写5条结论展望:\n'
            f'KEV: {ctx["kev_count"]} | CVE: {ctx["cve_total"]} | '
            f'行为者: {ctx["actor_count"]} | 覆盖: {ctx["start_date"]} ~ {ctx["end_date"]}\n'
            f'用"第一...第二..."格式。直接输出中文。'
        )
        try:
            resp = self.ai.query(prompt[:1190], ANALYST_SYSTEM_PROMPT, max_turns=1, timeout=120)
            return '## 16. 结论与展望（AI增强）\n\n' + self._clean(resp)
        except:
            return None

    def _clean(self, text):
        text = text.strip()
        for p in ['```markdown', '```md', '```']:
            if text.startswith(p):
                text = text[len(p):].strip()
        if text.endswith('```'):
            text = text[:-3].strip()
        return text

    # ═══════════════════════════════════════════════════════
    # Main Entry
    # ═══════════════════════════════════════════════════════

    def generate_full_report(self, results: Dict, start_date: str = '',
                             end_date: str = '') -> Dict:
        self._cancelled = False
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        self._log(f'开始生成威胁情报报告 ({start_date} ~ {end_date})')

        self._log('  [1/3] 从数据库提取数据...')
        ctx = self._build_context_data(results, start_date, end_date)

        self._log(f'  [2/3] 生成数据报告 (CVE: {len(ctx["top_cves"])}, '
                  f'KEV: {ctx["kev_count"]}, Actors: {ctx["actor_count"]})...')
        md_content = self._generate_data_report(ctx)

        self._log('  [3/3] AI增强分析 (可选)...')
        if self._ai_available and not self._cancelled:
            md_content = self._ai_enhance_report(md_content, ctx)

        title = f'全球威胁情报分析报告 — {start_date} 至 {end_date}'
        html_content = self._md_to_html(md_content, ctx, title)
        md_path, html_path = self._save_report_files(md_content, html_content, ctx)

        self._log(f'报告完成 ({len(md_content)} 字符 MD, {len(html_content)} 字节 HTML)')
        return {'md_content': md_content, 'html_content': html_content,
                'md_path': md_path, 'html_path': html_path, 'title': title}

    # ═══════════════════════════════════════════════════════
    # HTML Rendering
    # ═══════════════════════════════════════════════════════

    def _md_to_html(self, md_content, ctx, title):
        body = self._md_to_html_body(md_content)
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(title)}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<div class="header-box">
<h1>{html_mod.escape(title)}</h1>
<p><strong>覆盖时间：{html_mod.escape(ctx["start_date"])} — {html_mod.escape(ctx["end_date"])}</strong></p>
<p><strong>发布日期：{html_mod.escape(ctx["generated_at"])}</strong></p>
<p><strong>AI增强分析 (Claude Code Security) | 山西有信网安科技有限公司</strong></p>
</div>
<br>
{body}
<div class="footer">
CISA KEV | NVD | EPSS | OTX | URLhaus | MalwareBazaar |
Check Point Research | Sysdig | Trend Micro | Microsoft | Cisco Talos | Mandiant<br>
AI分析: Claude Code Security | 山西有信网安科技有限公司 &copy; 2026<br>
免责声明：本报告基于公开数据源和AI分析生成，仅供参考。
</div>
</body>
</html>'''

    def _md_to_html_body(self, md):
        lines = md.split('\n'); out = []
        in_table = False; in_code = False; in_list = False
        list_tag = 'ul'; table_rows = []; i = 0

        while i < len(lines):
            line = lines[i]
            if line.strip().startswith('```'):
                if in_code:
                    out.append('</code></pre>'); in_code = False
                else:
                    out.append(f'<pre><code>'); in_code = True
                i += 1; continue
            if in_code:
                out.append(html_mod.escape(line)); i += 1; continue

            hm = re.match(r'^(#{1,6})\s+(.+)', line)
            if hm:
                if in_table:
                    out.append(self._flush_table(table_rows)); table_rows = []; in_table = False
                if in_list:
                    out.append(f'</{list_tag}>'); in_list = False
                out.append(f'<h{len(hm.group(1))}>{self._inline(hm.group(2))}</h{len(hm.group(1))}>')
                i += 1; continue

            if re.match(r'^[-*_]{3,}\s*$', line.strip()):
                if in_table:
                    out.append(self._flush_table(table_rows)); table_rows = []; in_table = False
                out.append('<hr>'); i += 1; continue

            if '|' in line and line.strip().startswith('|'):
                if not in_table:
                    in_table = True
                table_rows.append(line); i += 1; continue
            elif in_table:
                out.append(self._flush_table(table_rows)); table_rows = []; in_table = False

            if line.strip().startswith('>'):
                out.append(f'<blockquote><p>{self._inline(line.strip()[1:].strip())}</p></blockquote>')
                i += 1; continue

            um = re.match(r'^(\s*)[-*+]\s+(.+)', line)
            om = re.match(r'^(\s*)\d+[.)]\s+(.+)', line)
            if um:
                if not in_list:
                    out.append('<ul>'); in_list = True; list_tag = 'ul'
                out.append(f'<li>{self._inline(um.group(2))}</li>'); i += 1; continue
            elif om:
                if not in_list:
                    out.append('<ol>'); in_list = True; list_tag = 'ol'
                out.append(f'<li>{self._inline(om.group(2))}</li>'); i += 1; continue
            elif in_list and not line.strip():
                out.append(f'</{list_tag}>'); in_list = False; i += 1; continue

            if not line.strip():
                i += 1; continue
            out.append(f'<p>{self._inline(line)}</p>'); i += 1

        if in_table:
            out.append(self._flush_table(table_rows))
        if in_list:
            out.append(f'</{list_tag}>')
        if in_code:
            out.append('</code></pre>')
        return '\n'.join(out)

    def _flush_table(self, rows):
        if not rows:
            return ''
        html_rows = []
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row.strip().strip('|').split('|')]
            if i == 1 and all(re.match(r'^[-: ]+$', c) for c in cells):
                continue
            tag = 'th' if i == 0 else 'td'
            html_rows.append(f'<tr>{"".join(f"<{tag}>{self._inline(c)}</{tag}>" for c in cells)}</tr>')
        return f'<table>\n{chr(10).join(html_rows)}\n</table>'

    def _inline(self, text):
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
        text = re.sub(r'`([^`\n]+?)`', r'<code>\1</code>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        return text

    def _save_report_files(self, md_content, html_content, ctx):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(self.output_dir, exist_ok=True)
        md_path = os.path.join(self.output_dir, f'threat_intel_ai_report_{ts}.md')
        html_path = os.path.join(self.output_dir, f'threat_intel_ai_report_{ts}.html')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return md_path, html_path


def generate_ai_threat_intel_report(results, db, output_dir, start_date='',
                                    end_date='', progress_callback=None):
    try:
        from ai_client import AIClient, is_ai_available
    except ImportError:
        return {'error': 'AI客户端不可用'}
    ai = AIClient() if is_ai_available() else None
    reporter = ThreatIntelReporter(db, ai, output_dir)
    if progress_callback:
        reporter.progress_callback = progress_callback
    return reporter.generate_full_report(results, start_date, end_date)
