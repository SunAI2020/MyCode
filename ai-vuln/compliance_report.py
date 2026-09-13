# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 合规检查报告生成（等保 / 关基 / 数据安全）

风格对齐 report_generator._generate_audit_html：单 f-string + 内联 CSS，
不依赖模板引擎，产物可直接交给 report_converter 转 PDF/Word/MD。

页脚强制披露不可删除：本系统的合规检查是『自动技术检查 + 人工填报 + AI 辅助研判』，
不是有资质机构出具的等级测评结论。把口径写在报告里，避免被当成测评报告使用。
"""
import os
import html
import logging
from datetime import datetime
from typing import Dict, List, Optional

from constants import SEV_COLORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 判定状态 → 颜色
STATUS_COLORS = {
    '符合': '#388e3c',
    '部分符合': '#fbc02d',
    '不符合': '#d32f2f',
    '不适用': '#9e9e9e',
    '未填报': '#1976d2',
    '证据不足': '#7b1fa2',
}

# 判定来源 → 展示名
SOURCE_LABELS = {
    'auto': '技术检查',
    'questionnaire': '人工填报',
    'ai_assisted': 'AI辅助',
}

# AI 研判 → 颜色（未完成必须显眼，它代表『没核验过』而不是『没问题』）
AI_COLORS = {
    '认可': '#388e3c',
    '存疑': '#f57c00',
    '矛盾': '#d32f2f',
    '未完成': '#757575',
    '未运行': '#bdbdbd',
}

_ROW_BG = {'不符合': '#ffcdd2', '证据不足': '#ede7f6', '部分符合': '#fff8e1'}


def _pct(value: Optional[float], digits: int = 1) -> str:
    """比率 → 百分比字符串。None 表示无法计算，显示『—』而不是 0%。"""
    if value is None:
        return '—'
    try:
        return f'{float(value) * 100:.{digits}f}%'
    except (TypeError, ValueError):
        return '—'


def _esc(text) -> str:
    return html.escape(str(text if text is not None else ''))


def _rate_color(rate: Optional[float]) -> str:
    if rate is None:
        return SEV_COLORS['INFO']
    if rate >= 0.9:
        return SEV_COLORS['LOW']
    if rate >= 0.7:
        return SEV_COLORS['MEDIUM']
    if rate >= 0.5:
        return SEV_COLORS['HIGH']
    return SEV_COLORS['CRITICAL']


def _status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, '#607d8b')
    return (f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:4px;font-size:12px;white-space:nowrap;">{_esc(status)}</span>')


def _ai_badge(ai_status: str, reasoning: str = '') -> str:
    if not ai_status or ai_status == '未运行':
        return '<span style="color:#bdbdbd;">—</span>'
    color = AI_COLORS.get(ai_status, '#607d8b')
    tip = f' title="{_esc(reasoning)}"' if reasoning else ''
    return (f'<span{tip} style="background:{color};color:#fff;padding:1px 6px;'
            f'border-radius:4px;font-size:11px;white-space:nowrap;">{_esc(ai_status)}</span>')


def _summary_cards(result: Dict) -> str:
    counts = result.get('counts', {}) or {}
    rate = result.get('compliance_rate')
    score = result.get('score')
    cards = [
        ('合规率', _pct(rate), _rate_color(rate)),
        ('合规得分', '—' if score is None else str(score), _rate_color(rate)),
        ('条款总数', str(counts.get('total', 0)), '#455a64'),
        ('符合', str(counts.get('符合', 0)), STATUS_COLORS['符合']),
        ('部分符合', str(counts.get('部分符合', 0)), STATUS_COLORS['部分符合']),
        ('不符合', str(counts.get('不符合', 0)), STATUS_COLORS['不符合']),
        ('证据不足', str(counts.get('证据不足', 0)), STATUS_COLORS['证据不足']),
        ('未填报', str(counts.get('未填报', 0)), STATUS_COLORS['未填报']),
    ]
    items = ''.join(
        f'''<div style="background:#fff;border:1px solid #e0e0e0;border-left:4px solid {color};
             border-radius:6px;padding:12px 14px;">
            <div style="color:#757575;font-size:12px;">{_esc(label)}</div>
            <div style="color:{color};font-size:24px;font-weight:700;margin-top:4px;">{_esc(value)}</div>
        </div>'''
        for label, value, color in cards)
    return (f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));'
            f'gap:12px;margin:18px 0;">{items}</div>')


def _domain_rows(result: Dict) -> str:
    by_domain = result.get('by_domain', {}) or {}
    if not by_domain:
        return '<tr><td colspan="8" style="text-align:center;color:#757575;">无分层数据</td></tr>'
    rows = []
    # 合规率低的层面排前面；无法计分的层面排最后
    for domain, d in sorted(by_domain.items(),
                            key=lambda kv: (kv[1].get('compliance_rate') is None,
                                            kv[1].get('compliance_rate') or 0)):
        rate = d.get('compliance_rate')
        rows.append(f'''<tr>
            <td><b>{_esc(domain)}</b></td>
            <td style="text-align:center;">{d.get('scored', 0)}</td>
            <td style="text-align:center;color:{STATUS_COLORS['符合']};">{d.get('符合', 0)}</td>
            <td style="text-align:center;color:{STATUS_COLORS['部分符合']};">{d.get('部分符合', 0)}</td>
            <td style="text-align:center;color:{STATUS_COLORS['不符合']};">{d.get('不符合', 0)}</td>
            <td style="text-align:center;color:{STATUS_COLORS['证据不足']};">{d.get('证据不足', 0)}</td>
            <td style="text-align:center;color:{STATUS_COLORS['未填报']};">{d.get('未填报', 0)}</td>
            <td style="text-align:center;font-weight:700;color:{_rate_color(rate)};">{_pct(rate)}</td>
        </tr>''')
    return ''.join(rows)


def _control_rows(results: List[Dict]) -> str:
    if not results:
        return '<tr><td colspan="8" style="text-align:center;color:#757575;">无条款结果</td></tr>'
    # 排序：不符合 → 证据不足 → 部分符合 → 未填报 → 符合 → 不适用（问题优先呈现）
    order = {'不符合': 0, '证据不足': 1, '部分符合': 2, '未填报': 3, '符合': 4, '不适用': 5}
    rows = []
    for r in sorted(results, key=lambda x: (order.get(x.get('status'), 9),
                                            -float(x.get('_weight', x.get('weight', 1.0)) or 1.0))):
        status = r.get('status', '')
        bg = _ROW_BG.get(status, '')
        source = SOURCE_LABELS.get(r.get('verdict_source', ''), r.get('verdict_source', '') or '—')
        weight = r.get('_weight', r.get('weight', 1.0))
        detail = _esc(r.get('detail', ''))[:600]
        rec = r.get('recommendation', '') or ''
        rec_html = (f'<br><small style="color:#2e7d32;">整改：{_esc(rec)[:400]}</small>'
                    if rec else '')
        rows.append(f'''<tr style="{f'background-color:{bg};' if bg else ''}">
            <td style="white-space:nowrap;"><code>{_esc(r.get('control_id'))}</code></td>
            <td>{_esc(r.get('domain'))}<br><small style="color:#757575;">{_esc(r.get('category'))}</small></td>
            <td>{_esc(r.get('title'))}<br><small style="color:#616161;">{_esc(r.get('requirement'))[:200]}</small></td>
            <td style="text-align:center;">{_status_badge(status)}</td>
            <td style="text-align:center;white-space:nowrap;">{_esc(source)}</td>
            <td style="text-align:center;">{_ai_badge(r.get('ai_status'), r.get('ai_reasoning', ''))}</td>
            <td style="text-align:center;">{weight}</td>
            <td><small>{detail}</small>{rec_html}</td>
        </tr>''')
    return ''.join(rows)


def _disclosure(result: Dict) -> str:
    """页脚强制披露：这份报告的结论是怎么来的、哪些部分没被验证过。"""
    ai_counts = result.get('ai_counts', {}) or {}
    counts = result.get('counts', {}) or {}
    doubted = ai_counts.get('存疑', 0)
    conflict = ai_counts.get('矛盾', 0)
    incomplete = ai_counts.get('未完成', 0)
    q_completion = result.get('questionnaire_completion')
    q_total = result.get('questionnaire_total', 0)

    warn = []
    if conflict:
        warn.append(f'<li><b style="color:{AI_COLORS["矛盾"]};">{conflict} 项</b>'
                    f'自评结论与扫描到的技术事实矛盾，已被强制改判为『不符合』。</li>')
    if doubted:
        warn.append(f'<li><b style="color:{AI_COLORS["存疑"]};">{doubted} 项</b>'
                    f'AI 认为填报依据不足（计分时按 50% 折算）。</li>')
    if incomplete:
        warn.append(f'<li><b style="color:{AI_COLORS["未完成"]};">{incomplete} 项</b>'
                    f'AI 研判未完成（调用失败或返回无法解析），这些条款<b>未经过 AI 核验</b>。</li>')
    if counts.get('证据不足'):
        warn.append(f'<li><b style="color:{STATUS_COLORS["证据不足"]};">'
                    f'{counts["证据不足"]} 项</b>因缺少技术证据无法判定，已排除在合规率分母之外——'
                    f'请勿理解为『符合』。</li>')
    if counts.get('未填报'):
        warn.append(f'<li><b style="color:{STATUS_COLORS["未填报"]};">'
                    f'{counts["未填报"]} 项</b>尚未填报，同样未计入合规率。</li>')
    warn_html = f'<ul style="margin:8px 0 0 18px;line-height:1.9;">{"".join(warn)}</ul>' if warn else ''

    return f'''
    <div style="background:#fff8e1;border:1px solid #ffb300;border-radius:8px;padding:16px;margin:24px 0;">
        <div style="font-weight:700;color:#e65100;margin-bottom:8px;">⚠ 结论口径与局限性披露</div>
        <div style="line-height:1.9;color:#424242;">
            本次共 <b>{counts.get('total', 0)}</b> 条条款，其中
            <b>{_pct(result.get('auto_ratio'))}</b> 由系统自动技术检查判定，
            其余依赖人工填报；问卷条款 <b>{q_total}</b> 条，填报完成度
            <b>{_pct(q_completion)}</b>。
            合规率的分母<b>仅包含</b>『符合 / 部分符合 / 不符合』三类
            （共 <b>{result.get('scored_total', 0)}</b> 条），
            『不适用 / 未填报 / 证据不足』一律不计分。
        </div>
        {warn_html}
        <div style="margin-top:12px;padding-top:10px;border-top:1px dashed #ffb300;color:#bf360c;font-weight:600;">
            本报告由自动化工具结合人工填报与 AI 辅助研判生成，
            <u>不构成等级保护测评、认证或第三方审计结论</u>，
            不能替代具备资质的测评机构出具的正式测评报告。
        </div>
    </div>'''


def render_compliance_html(result: Dict, title: str = '') -> str:
    """把一次合规检查结果渲染成完整 HTML 文档"""
    standard_name = result.get('standard_name') or result.get('standard') or '合规检查'
    title = title or f'{standard_name} 合规检查报告'
    level = result.get('level', 'ALL')
    level_text = '全部条款' if level in ('ALL', '', None) else level
    generated = result.get('timestamp') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rate = result.get('compliance_rate')
    source_counts = result.get('source_counts', {}) or {}
    version_html = f'（版本 {_esc(result.get("version"))}）' if result.get('version') else ''
    duration_html = (f'　|　耗时：{result.get("duration")} 秒'
                     if result.get('duration') is not None else '')

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{_esc(title)}</title>
<style>
    body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0;
            padding: 28px; background: #f5f6f8; color: #212121; }}
    .wrap {{ max-width: 1400px; margin: 0 auto; background: #fff; border-radius: 10px;
             box-shadow: 0 2px 10px rgba(0,0,0,.08); padding: 28px; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; color: #1a237e; }}
    h2 {{ font-size: 17px; color: #283593; border-left: 4px solid #3949ab;
          padding-left: 10px; margin: 28px 0 12px; }}
    .meta {{ color: #616161; font-size: 13px; line-height: 1.9; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }}
    th {{ background: #e8eaf6; color: #283593; padding: 9px 8px; text-align: left;
          border: 1px solid #c5cae9; white-space: nowrap; }}
    td {{ padding: 8px; border: 1px solid #e0e0e0; vertical-align: top; }}
    tr:nth-child(even) td {{ background-color: rgba(0,0,0,.015); }}
    code {{ background: #eceff1; padding: 1px 5px; border-radius: 3px; font-size: 12px; }}
    .foot {{ margin-top: 26px; padding-top: 14px; border-top: 1px solid #e0e0e0;
             color: #9e9e9e; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
<div class="wrap">
    <h1>{_esc(title)}</h1>
    <div class="meta">
        标准：<b>{_esc(standard_name)}</b>{version_html}<br>
        适用等级：<b>{_esc(level_text)}</b>　|
        检查对象：<b>{_esc(result.get('target') or '未指定')}</b>　|
        作用域：<b>{_esc(result.get('scope_key') or 'ORG')}</b><br>
        生成时间：{_esc(generated)}{duration_html}
    </div>

    <div style="margin-top:18px;padding:14px 16px;border-radius:8px;
                background:#fafafa;border:1px solid {_rate_color(rate)};">
        <span style="font-size:15px;color:#424242;">总体合规率</span>
        <span style="font-size:32px;font-weight:800;color:{_rate_color(rate)};
                     margin-left:12px;">{_pct(rate)}</span>
        <span style="color:#616161;margin-left:14px;">
            （判定来源：技术检查 {source_counts.get('auto', 0)} 项 /
             人工填报 {source_counts.get('questionnaire', 0)} 项 /
             AI 辅助 {source_counts.get('ai_assisted', 0)} 项）
        </span>
    </div>

    {_summary_cards(result)}

    <h2>按安全层面统计</h2>
    <table>
        <thead><tr>
            <th>安全层面</th><th>计分条款</th><th>符合</th><th>部分符合</th>
            <th>不符合</th><th>证据不足</th><th>未填报</th><th>层面合规率</th>
        </tr></thead>
        <tbody>{_domain_rows(result)}</tbody>
    </table>

    <h2>条款判定明细</h2>
    <table>
        <thead><tr>
            <th>条款</th><th>安全层面</th><th>要求</th><th>判定</th>
            <th>判定来源</th><th>AI研判</th><th>权重</th><th>判定依据 / 整改建议</th>
        </tr></thead>
        <tbody>{_control_rows(result.get('results', []))}</tbody>
    </table>

    {_disclosure(result)}

    <div class="foot">
        本报告由「下一代智能漏洞扫描系统 Pro」自动生成　·　山西有信网安科技有限公司
    </div>
</div>
</body>
</html>'''


def generate_compliance_report(result: Dict, output_dir: str = 'reports',
                               title: str = '', filename_prefix: str = '') -> str:
    """生成合规检查 HTML 报告，返回文件路径。

    Args:
        result: 合规检查结果（ComplianceEngine.evaluate 返回值）
        output_dir: 输出目录，默认 reports
        title: 报告标题（为空则用 standard_name 自动拼装）
        filename_prefix: 文件名前缀（为空则用 compliance_{standard}）
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    standard = (result.get('standard') or 'compliance').replace('/', '_')
    base = filename_prefix or f'compliance_{standard}'
    path = os.path.join(output_dir, f'{base}_{timestamp}.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(render_compliance_html(result, title))
    logger.info(f'合规检查报告已生成: {path}')
    return path
