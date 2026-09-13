# -*- coding: utf-8 -*-
"""报告管理"""
import os, sys, json, re, html
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import REPORT_DIR, APP_NAME, APP_VERSION, COPYRIGHT


def _register_cjk_font():
    """注册一个中文字体用于 PDF 生成，返回字体名；找不到则返回 None。"""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None
    candidates = [
        ("SimHei",  "C:/Windows/Fonts/simhei.ttf"),
        ("SimFang", "C:/Windows/Fonts/simfang.ttf"),
        ("KaiTi",   "C:/Windows/Fonts/simkai.ttf"),
        ("MSYH",    "C:/Windows/Fonts/msyh.ttc"),
        ("SimSun",  "C:/Windows/Fonts/simsun.ttc"),
        ("NotoCJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ("NotoCJK2", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return None


def _safe_name(s):
    """清理不可信名称：用于文件名与 HTML，防路径穿越。"""
    return re.sub(r'[\\/:*?"<>|\r\n]+', '_', str(s or '')).strip('.') or 'org'


def _esc(v):
    """HTML 转义动态数据，防止报告文件被注入脚本/标签（存储型 XSS）。"""
    return html.escape("" if v is None else str(v))


def _xml_esc(v):
    """XML 转义（reportlab Paragraph/Table 文本用），只转义 & < >，不转义引号。"""
    return html.escape("" if v is None else str(v), quote=False)


def _report_filename(org_name, type_cn, ext):
    """报告命名: 组织名称 + 报告类型 — XXXX年XX月XX日xx时xx分xx秒.ext（含秒，避免同分钟覆盖）"""
    return f"{_safe_name(org_name)}{type_cn}—{datetime.now().strftime('%Y年%m月%d日%H时%M分%S秒')}.{ext}"


class ReportManager:
    def __init__(self, org_manager):
        self.org_mgr = org_manager
        os.makedirs(REPORT_DIR, exist_ok=True)
    def generate_html_report(self, org_id, title=None):
        org = self.org_mgr.get_org(org_id)
        if not org: return None
        org_name = org["org_name"]
        title = title or f"{org_name} - 数据资产暴露面排查报告"
        exposures = self.org_mgr.list_exposures(org_id=org_id)
        stats = self.org_mgr.get_exposure_stats(org_id=org_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exp_html = ""
        for e in exposures:
            sev_color = {"CRITICAL":"#d50000","HIGH":"#ff6d00","MEDIUM":"#ffd600","LOW":"#00c853","INFO":"#2979ff"}.get(e["risk_level"],"#999")
            exp_html += f"""<tr>
                <td>{_esc(e["asset_type"])}</td><td>{_esc(e["asset_name"])}</td><td>{_esc(e["asset_value"])}</td>
                <td><span style="color:{sev_color};font-weight:bold">{_esc(e["risk_level"])}</span></td>
                <td>{_esc(e["source"])}</td><td>{_esc(e["detail"] or "")}</td><td>{_esc(e["discovered_at"])}</td></tr>"""
        # AI 摘要（若已配置 LLM）
        ai_summary_html = ""
        try:
            from core.llm_client import LLMClient
            summary = LLMClient(org_manager=self.org_mgr).summarize_findings(org_name, stats, exposures)
            if summary:
                ai_summary_html = (f'<div style="background:#fff;padding:20px;border-radius:8px;'
                                   f'box-shadow:0 1px 3px rgba(0,0,0,0.1);margin-bottom:20px;text-align:left">'
                                   f'<h3 style="margin:0 0 8px">AI 风险摘要</h3>'
                                   f'<p style="margin:0;line-height:1.6;white-space:pre-wrap">{_esc(summary)}</p></div>')
        except Exception:
            ai_summary_html = ""
        html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>{_esc(title)}</title><style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
.header{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:30px;border-radius:8px;margin-bottom:20px}}
.header h1{{margin:0;font-size:24px}}.header p{{margin:5px 0 0;opacity:0.7}}
.cards{{display:flex;gap:15px;margin-bottom:20px}}
.card{{flex:1;background:#fff;padding:20px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);text-align:center}}
.card .num{{font-size:36px;font-weight:bold}}
.card .label{{color:#666;margin-top:5px}}
.card.critical .num{{color:#d50000}}.card.high .num{{color:#ff6d00}}.card.total .num{{color:#1a1a2e}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)}}
th{{background:#1a1a2e;color:#fff;padding:12px;text-align:left}}
td{{padding:10px 12px;border-bottom:1px solid #eee}}
tr:hover{{background:#f5f7fa}}.footer{{text-align:center;padding:20px;color:#999;font-size:12px}}
</style></head><body>
<div class="header"><h1>{_esc(title)}</h1><p>生成时间: {now} | 组织: {_esc(org_name)}</p></div>
<div class="cards">
<div class="card total"><div class="num">{stats["total"]}</div><div class="label">总暴露面</div></div>
<div class="card critical"><div class="num">{stats["CRITICAL"]}</div><div class="label">严重风险</div></div>
<div class="card high"><div class="num">{stats["HIGH"]}</div><div class="label">高风险</div></div>
<div class="card"><div class="num">{stats["MEDIUM"]}</div><div class="label">中风险</div></div>
</div>
{ai_summary_html}
<h2>暴露面清单</h2><table><thead><tr><th>资产类型</th><th>资产名称</th><th>资产值</th><th>风险等级</th><th>来源</th><th>搜索结果</th><th>发现时间</th></tr></thead><tbody>{exp_html}</tbody></table>
<div class="footer">{APP_NAME} v{APP_VERSION} - {COPYRIGHT}</div></body></html>"""
        filename = _report_filename(org_name, "暴露面综合报告", "html")
        filepath = os.path.join(REPORT_DIR, filename)
        with open(filepath,'w',encoding='utf-8') as fp:
            fp.write(html)
        return filepath

    def generate_report(self, org_id, fmt="html"):
        """按格式生成综合报告，fmt ∈ {html, md, docx, pdf}。"""
        fmt = (fmt or "html").lower()
        if fmt == "md": return self.generate_md_report(org_id)
        if fmt == "docx": return self.generate_docx_report(org_id)
        if fmt == "pdf": return self.generate_pdf_report(org_id)
        return self.generate_html_report(org_id)

    def _report_data(self, org_id):
        org = self.org_mgr.get_org(org_id)
        if not org: return None
        return {
            "org_name": org["org_name"],
            "exposures": self.org_mgr.list_exposures(org_id=org_id),
            "stats": self.org_mgr.get_exposure_stats(org_id=org_id),
            "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def _md_cell(s):
        return str(s or "").replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    def generate_md_report(self, org_id):
        d = self._report_data(org_id)
        if not d: return None
        s = d["stats"]
        lines = [
            f"# {d['org_name']} - 数据资产暴露面排查报告",
            "", f"> 生成时间: {d['now']} | {APP_NAME} v{APP_VERSION}",
            "", "## 风险汇总",
            f"- 总暴露面: {s['total']}",
            f"- 严重(CRITICAL): {s['CRITICAL']}",
            f"- 高风险(HIGH): {s['HIGH']}",
            f"- 中风险(MEDIUM): {s['MEDIUM']}",
            f"- 低风险(LOW): {s['LOW']}",
            "", "## 暴露面清单",
            "| 资产类型 | 资产名称 | 资产值 | 风险等级 | 来源 | 搜索结果 | 发现时间 |",
            "|---|---|---|---|---|---|---|",
        ]
        for e in d["exposures"]:
            lines.append(f"| {self._md_cell(e['asset_type'])} | {self._md_cell(e['asset_name'])} | "
                         f"{self._md_cell(e['asset_value'])} | {e['risk_level']} | {self._md_cell(e['source'])} | "
                         f"{self._md_cell(e['detail'] or '')} | {self._md_cell(e['discovered_at'])} |")
        filename = _report_filename(d["org_name"], "暴露面综合报告", "md")
        fp = os.path.join(REPORT_DIR, filename)
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        return fp

    def generate_docx_report(self, org_id):
        d = self._report_data(org_id)
        if not d: return None
        try:
            from docx import Document
        except ImportError:
            return None
        doc = Document()
        doc.add_heading(f"{d['org_name']} - 数据资产暴露面排查报告", 0)
        doc.add_paragraph(f"生成时间: {d['now']} | {APP_NAME} v{APP_VERSION}")
        doc.add_heading("风险汇总", level=1)
        s = d["stats"]
        doc.add_paragraph(f"总暴露面: {s['total']} | 严重: {s['CRITICAL']} | 高: {s['HIGH']} "
                          f"| 中: {s['MEDIUM']} | 低: {s['LOW']}")
        doc.add_heading("暴露面清单", level=1)
        table = doc.add_table(rows=1, cols=7)
        try: table.style = 'Light Grid Accent 1'
        except Exception: pass
        for i, h in enumerate(["资产类型", "资产名称", "资产值", "风险等级", "来源", "搜索结果", "发现时间"]):
            table.rows[0].cells[i].text = h
        for e in d["exposures"]:
            row = table.add_row().cells
            for i, v in enumerate([e["asset_type"], e["asset_name"], e["asset_value"],
                                   e["risk_level"], e["source"], e["detail"] or "", e["discovered_at"] or ""]):
                row[i].text = str(v)
        filename = _report_filename(d["org_name"], "暴露面综合报告", "docx")
        fp = os.path.join(REPORT_DIR, filename)
        doc.save(fp)
        return fp

    def generate_pdf_report(self, org_id):
        d = self._report_data(org_id)
        if not d: return None
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib import colors
        except ImportError:
            return None
        font = _register_cjk_font() or 'Helvetica'
        st_title = ParagraphStyle('t', fontName=font, fontSize=18, leading=24, spaceAfter=12)
        st_body = ParagraphStyle('b', fontName=font, fontSize=10, leading=14)
        s = d["stats"]
        filename = _report_filename(d["org_name"], "暴露面综合报告", "pdf")
        fp = os.path.join(REPORT_DIR, filename)
        doc = SimpleDocTemplate(fp, pagesize=A4)
        story = [
            Paragraph(f"{_xml_esc(d['org_name'])} - 数据资产暴露面排查报告", st_title),
            Paragraph(f"生成时间: {d['now']} | 总暴露面 {s['total']} | 严重 {s['CRITICAL']} | "
                      f"高 {s['HIGH']} | 中 {s['MEDIUM']} | 低 {s['LOW']}", st_body),
            Spacer(1, 10),
        ]
        data = [["资产类型", "资产名称", "资产值", "风险", "来源", "搜索结果", "时间"]]
        for e in d["exposures"][:200]:
            data.append([_xml_esc(e["asset_type"]), _xml_esc((e["asset_name"] or "")[:20]), _xml_esc((e["asset_value"] or "")[:30]),
                         _xml_esc(e["risk_level"]), _xml_esc((e["source"] or "")[:14]), _xml_esc((e["detail"] or "")[:40]), _xml_esc(e["discovered_at"] or "")])
        tbl = Table(data, colWidths=[18*6, 45*6, 55*6, 16*6, 32*6, 50*6, 36*6])
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ]))
        story.append(tbl)
        doc.build(story)
        return fp

    def export_excel(self, org_id=None):
        try:
            import csv
            filename = f"exposures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(REPORT_DIR, filename)
            exposures = self.org_mgr.list_exposures(org_id=org_id)
            with open(filepath,'w',encoding='utf-8-sig',newline='') as f:
                w = csv.writer(f)
                w.writerow(["资产类型","资产名称","资产值","来源","风险等级","搜索结果","可信度","发现时间"])
                for e in exposures:
                    w.writerow([e["asset_type"],e["asset_name"],e["asset_value"],
                        e["source"],e["risk_level"],e["detail"] or "",e["confidence"],e["discovered_at"] or ""])
            return filepath
        except Exception as ex:
            print(f"CSV导出失败: {ex}")
            return None

    def generate_rapid_assessment_report(self, session_id, target_name, stats, profile,
                                          subsidiaries, assets, leaks):
        """生成快速评估HTML报告(深色主题)"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_time = stats.get("total_time", 0)
        # 资产类型分布
        type_dist = {}
        for a in assets:
            t = a.get("asset_type", "unknown")
            type_dist[t] = type_dist.get(t, 0) + 1
        type_rows = "".join(f"<tr><td>{_esc(t)}</td><td>{c}</td></tr>"
            for t, c in sorted(type_dist.items(), key=lambda x: -x[1])[:10])
        leak_rows = "".join(f"""<tr><td>{_esc(lk.get('leak_category',''))}</td>
            <td>{_esc(lk.get('leak_pattern',''))}</td>
            <td style="color:{'#FF4444' if lk.get('severity')=='CRITICAL' else '#FF8800'}">
            {_esc(lk.get('severity',''))}</td></tr>""" for lk in leaks[:20])
        sub_rows = "".join(f"""<tr><td>{_esc(s.get('sub_name',''))}</td>
            <td>{_esc(s.get('chain_level',''))}</td>
            <td>{s.get('equity_ratio',0)*100:.0f}%</td></tr>""" for s in subsidiaries[:30])

        html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>快速评估报告 - {_esc(target_name)}</title><style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#00143C;color:#E8ECF1;margin:0;padding:20px}}
.header{{background:linear-gradient(135deg,#000A1E,#00143C);padding:30px;border-radius:8px;margin-bottom:20px;border:1px solid #0A1E40}}
.header h1{{margin:0;color:#226ED8}} .header p{{margin:5px 0 0;opacity:0.7}}
.cards{{display:flex;gap:15px;margin-bottom:20px}}
.card{{flex:1;background:#0A1E40;padding:20px;border-radius:8px;text-align:center}}
.card .num{{font-size:32px;font-weight:bold;color:#226ED8}}
.card .label{{color:#8899AA;margin-top:5px}}
h2{{color:#226ED8;margin-top:25px}}
table{{width:100%;border-collapse:collapse;background:#0A1E40;border-radius:8px;overflow:hidden;margin:10px 0}}
th{{background:#000A1E;color:#E8ECF1;padding:10px;text-align:left}}
td{{padding:8px 10px;border-bottom:1px solid #00143C}}
tr:hover{{background:#00143C}}
.footer{{text-align:center;padding:20px;color:#556677;font-size:11px}}
</style></head><body>
<div class="header"><h1>⚡ 1小时快速评估报告: {_esc(target_name)}</h1>
<p>生成: {now} | 耗时: {total_time/60:.1f}分钟 | {APP_NAME} v{APP_VERSION}</p></div>
<div class="cards">
<div class="card"><div class="num">{stats.get('subsidiaries',0)}</div><div class="label">子公司/关联</div></div>
<div class="card"><div class="num">{stats.get('assets',0)}</div><div class="label">发现资产</div></div>
<div class="card"><div class="num">{stats.get('shadows',0)}</div><div class="label">疑似影子</div></div>
<div class="card"><div class="num" style="color:#FF4444">{stats.get('leaks',0)}</div><div class="label">泄露证据</div></div>
</div>
<h2>企业档案</h2>
<table><tr><th>字段</th><th>值</th></tr>
<tr><td>全称</td><td>{_esc(profile.get('full_name',target_name))}</td></tr>
<tr><td>法人</td><td>{_esc(profile.get('legal_person','-'))}</td></tr>
<tr><td>注册资本</td><td>{_esc(profile.get('registered_capital','-'))}</td></tr>
</table>
<h2>资产类型分布</h2>
<table><tr><th>类型</th><th>数量</th></tr>{type_rows or '<tr><td colspan=2>无数据</td></tr>'}</table>
<h2>子公司 (前30)</h2>
<table><tr><th>名称</th><th>层级</th><th>股权</th></tr>{sub_rows or '<tr><td colspan=3>无</td></tr>'}</table>
<h2>泄露证据 (前20)</h2>
<table><tr><th>类别</th><th>模式</th><th>严重</th></tr>{leak_rows or '<tr><td colspan=3>无</td></tr>'}</table>
<div class="footer">{APP_NAME} v{APP_VERSION} 自动生成 | {now}</div></body></html>"""

        filename = f"rapid_{_safe_name(target_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(REPORT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as fp:
            fp.write(html)
        return filepath

    def generate_equity_chain_report(self, org_id):
        """股权穿透报告 — 4级控股树+每个子公司资产汇总"""
        org = self.org_mgr.get_org(org_id)
        if not org: return None
        org_name = org["org_name"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subs = self.org_mgr.list_subsidiaries(parent_org_id=org_id)
        rels = self.org_mgr.list_relations(from_org_id=org_id)
        # 按层级分组
        by_level = {}
        for s in subs:
            lv = s["chain_level"]
            if lv not in by_level: by_level[lv] = []
            by_level[lv].append(s)
        sub_rows = ""
        for lv in sorted(by_level.keys()):
            for s in by_level[lv]:
                indent = "　" * (lv-1)
                sub_rows += f"""<tr><td style="padding-left:{20+lv*20}px">{indent}├ {_esc(s['sub_name'])}</td>
                    <td>L{lv}</td><td>{s['equity_ratio']*100:.1f}%</td>
                    <td>{_esc(s.get('legal_person','-'))}</td></tr>"""
        rel_rows = "".join(f"""<tr><td>{_esc(r['to_entity_name'])}</td><td>{_esc(r.get('relation_type',''))}</td>
            <td>{r.get('equity_ratio',0)*100:.0f}%</td><td>L{_esc(r.get('chain_level',''))}</td>
            <td>{_esc(r.get('source',''))}</td></tr>""" for r in rels[:50])

        html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>股权穿透报告 - {_esc(org_name)}</title><style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#00143C;color:#E8ECF1;margin:0;padding:20px}}
.header{{background:linear-gradient(135deg,#000A1E,#00143C);padding:30px;border-radius:8px;margin-bottom:20px}}
.header h1{{margin:0;color:#8B5CF6}} .header p{{opacity:0.7}}
.card{{background:#0A1E40;padding:20px;border-radius:8px;margin:15px 0}}
.card h3{{color:#8B5CF6;margin:0 0 10px}}
table{{width:100%;border-collapse:collapse;background:#0A1E40;border-radius:8px;overflow:hidden;margin:10px 0}}
th{{background:#000A1E;color:#E8ECF1;padding:10px;text-align:left}}
td{{padding:8px 10px;border-bottom:1px solid #00143C}}
tr:hover{{background:#00143C}}
.footer{{text-align:center;padding:20px;color:#556677;font-size:11px}}
</style></head><body>
<div class="header"><h1> 股权穿透报告: {_esc(org_name)}</h1>
<p>生成: {now} | {len(subs)}个子公司 {len(rels)}条关系 | {APP_NAME} v{APP_VERSION}</p></div>
<div class="card"><h3>4级控股树 ({len(subs)}个实体)</h3>
<table><tr><th>企业名称</th><th>层级</th><th>股权</th><th>法人</th></tr>
{sub_rows or '<tr><td colspan=4>暂无数据</td></tr>'}</table></div>
<div class="card"><h3>全量关系图谱 ({len(rels)}条)</h3>
<table><tr><th>目标实体</th><th>关系类型</th><th>股权</th><th>层级</th><th>来源</th></tr>
{rel_rows or '<tr><td colspan=5>暂无数据</td></tr>'}</table></div>
<div class="footer">{APP_NAME} v{APP_VERSION} | {now}</div></body></html>"""
        fp = os.path.join(REPORT_DIR, _report_filename(org_name, "股权穿透报告", "html"))
        with open(fp, 'w', encoding='utf-8') as f: f.write(html)
        return fp

    def generate_leak_report(self, org_id=None):
        """数据泄露报告 — 凭证泄露/架构文档/源码暴露分类"""
        leaks = self.org_mgr.list_leak_evidence(org_id=org_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 分类统计
        cat_stats = {}
        for lk in leaks:
            cat = lk.get("leak_category","other")
            cat_stats[cat] = cat_stats.get(cat, 0) + 1
        cat_cards = "".join(f"""<div class="ccard"><div class="num" style="color:{'#FF4444' if c=='credential' else '#FF8800'}">{n}</div>
            <div class="label">{_esc(c)}</div></div>""" for c, n in cat_stats.items())
        leak_rows = "".join(f"""<tr><td>{_esc(lk.get('leak_category',''))}</td>
            <td>{_esc(lk.get('leak_pattern',''))}</td>
            <td style="max-width:300px;overflow:hidden">{_esc(lk.get('matched_content_snippet','')[:100])}</td>
            <td style="color:{'#FF4444' if lk.get('severity')=='CRITICAL' else '#FF8800'}">{_esc(lk.get('severity',''))}</td>
            <td style="font-size:10px">{_esc(lk.get('source_url','')[:60])}</td></tr>""" for lk in leaks[:100])
        org_name = "全部组织"
        if org_id:
            org = self.org_mgr.get_org(org_id)
            if org: org_name = org["org_name"]

        html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>数据泄露报告 - {_esc(org_name)}</title><style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#00143C;color:#E8ECF1;margin:0;padding:20px}}
.header{{background:linear-gradient(135deg,#000A1E,#300010);padding:30px;border-radius:8px;margin-bottom:20px}}
.header h1{{margin:0;color:#FF4444}} .header p{{opacity:0.7}}
.ccards{{display:flex;gap:15px;margin-bottom:20px}}
.ccard{{flex:1;background:#0A1E40;padding:20px;border-radius:8px;text-align:center}}
.ccard .num{{font-size:32px;font-weight:bold}}
.ccard .label{{color:#8899AA;margin-top:5px}}
h2{{color:#FF4444;margin-top:25px}}
table{{width:100%;border-collapse:collapse;background:#0A1E40;border-radius:8px;overflow:hidden;margin:10px 0}}
th{{background:#200010;color:#E8ECF1;padding:10px;text-align:left;font-size:12px}}
td{{padding:8px 10px;border-bottom:1px solid #00143C;font-size:11px}}
tr:hover{{background:#00143C}}
.footer{{text-align:center;padding:20px;color:#556677;font-size:11px}}
</style></head><body>
<div class="header"><h1>⚠ 数据泄露报告: {_esc(org_name)}</h1>
<p>生成: {now} | 共{len(leaks)}条泄露证据 | {APP_NAME} v{APP_VERSION}</p></div>
<div class="ccards">{cat_cards}</div>
<h2>泄露证据清单 (前100条)</h2>
<table><tr><th>类别</th><th>模式</th><th>内容片段</th><th>严重</th><th>来源</th></tr>
{leak_rows or '<tr><td colspan=5>未发现泄露证据</td></tr>'}</table>
<div class="footer">{APP_NAME} v{APP_VERSION} | {now} | 建议立即修复CRITICAL级别泄露</div></body></html>"""
        fp = os.path.join(REPORT_DIR, _report_filename(org_name, "数据泄露报告", "html"))
        with open(fp, 'w', encoding='utf-8') as f: f.write(html)
        return fp

    def generate_network_map_report(self, org_id=None):
        """网络资产拓扑报告 — IP段/ASN/端口"""
        ranges = self.org_mgr.list_network_ranges(org_id=org_id)
        exps = self.org_mgr.list_exposures(org_id=org_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # IP段统计
        range_rows = "".join(f"""<tr><td>{_esc(r.get('ip_range',''))}</td><td>AS{_esc(r.get('asn_number',''))}</td>
            <td>{_esc(r.get('asn_name',''))}</td><td>{_esc(r.get('isp',''))}</td>
            <td>{_esc(r.get('country',''))}</td></tr>""" for r in ranges[:50])
        # 端口服务
        ports = [e for e in exps if e["asset_type"] in ("port_service","network_device")]
        port_rows = "".join(f"""<tr><td>{_esc(e['asset_type'])}</td><td>{_esc(e['asset_name'])}</td>
            <td>{_esc(e['asset_value'])}</td><td style="color:{'#FF8800' if e['risk_level']=='HIGH' else '#8899AA'}">
            {_esc(e['risk_level'])}</td></tr>""" for e in ports[:50])
        org_name = "全部组织"
        if org_id:
            org = self.org_mgr.get_org(org_id)
            if org: org_name = org["org_name"]

        html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>网络资产拓扑 - {_esc(org_name)}</title><style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#00143C;color:#E8ECF1;margin:0;padding:20px}}
.header{{background:linear-gradient(135deg,#000A1E,#0A1E30);padding:30px;border-radius:8px;margin-bottom:20px}}
.header h1{{margin:0;color:#FF8844}} .header p{{opacity:0.7}}
h2{{color:#FF8844;margin-top:25px}}
table{{width:100%;border-collapse:collapse;background:#0A1E40;border-radius:8px;overflow:hidden;margin:10px 0}}
th{{background:#0A1E30;color:#E8ECF1;padding:10px;text-align:left;font-size:12px}}
td{{padding:8px 10px;border-bottom:1px solid #00143C;font-size:11px}}
tr:hover{{background:#00143C}}
.footer{{text-align:center;padding:20px;color:#556677;font-size:11px}}
</style></head><body>
<div class="header"><h1> 网络资产拓扑: {_esc(org_name)}</h1>
<p>生成: {now} | {len(ranges)}个IP段 {len(ports)}个端口服务 | {APP_NAME} v{APP_VERSION}</p></div>
<h2>IP段与ASN映射 ({len(ranges)}条)</h2>
<table><tr><th>IP段</th><th>ASN</th><th>ASN名称</th><th>ISP</th><th>国家</th></tr>
{range_rows or '<tr><td colspan=5>暂无数据</td></tr>'}</table>
<h2>端口与服务暴露 ({len(ports)}条)</h2>
<table><tr><th>类型</th><th>名称</th><th>地址</th><th>风险</th></tr>
{port_rows or '<tr><td colspan=4>暂无数据</td></tr>'}</table>
<div class="footer">{APP_NAME} v{APP_VERSION} | {now}</div></body></html>"""
        fp = os.path.join(REPORT_DIR, _report_filename(org_name, "网络资产报告", "html"))
        with open(fp, 'w', encoding='utf-8') as f: f.write(html)
        return fp
