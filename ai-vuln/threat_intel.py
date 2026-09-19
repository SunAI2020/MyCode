# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 威胁情报模块
全球威胁情报收集：多源API + Web OSINT AI增强采集
数据采集即分析，AI全量归纳生成报告"""

import sys
import os
import html
import logging
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from intel_pipeline import IntelPipeline, generate_data_driven_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Legacy URL constants (kept for backward compatibility with main_window.py settings)
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_API = "https://api.first.org/data/v1/epss"
OTX_PULSES_URL = "https://otx.alienvault.com/api/v1/pulses/subscribed"
ABUSE_URLHAUS = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
ABUSE_MALWARE = "https://mb-api.abuse.ch/api/v1/"

NVD_API_KEY = ""


class ThreatIntelCollector:
    """全球威胁情报收集器 — 委托给 IntelPipeline 实现AI增强多源采集。

    保持与原有API的完全向后兼容，新增:
    - 13个数据源 (6本地API + 7 Web OSINT AI搜索)
    - 采集即AI分析
    - 数据同步的实时屏幕输出
    - 显式的数据源状态报告 (停止静默失败)
    """

    def __init__(self, db=None):
        self.db = db
        self._stop_requested = False
        self._collecting = False
        self.progress_callback = None
        self.collection_log = []
        self.sources_status = {}
        self._pipeline = None
        self._ai_client = None
        logger.info("威胁情报收集器初始化完成 (AI增强多源采集模式)")

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def stop(self):
        self._stop_requested = True
        if self._pipeline:
            self._pipeline.cancel()

    def is_collecting(self):
        return self._collecting

    def _log(self, msg):
        """记录日志并回调"""
        self.collection_log.append(msg)
        if self.progress_callback:
            self.progress_callback(msg)

    def _get_ai_client(self):
        """延迟初始化AI客户端（避免循环导入）"""
        if self._ai_client is None:
            try:
                from ai_client import AIClient, is_ai_available
                if is_ai_available():
                    self._ai_client = AIClient()
                else:
                    self._log('  ⚠️ AI客户端不可用，将跳过OSINT源和AI增强分析')
            except Exception as e:
                self._log(f'  ⚠️ AI客户端初始化失败: {e}')
        return self._ai_client

    # ============ 多源威胁情报收集 (AI增强) ============
    def collect_all_intel(self, days=None, start_date=None, end_date=None) -> Dict:
        """从13个数据源收集全球威胁情报 — AI增强流水线。

        6个本地API (并行) + 7个Web OSINT (AI搜索) → AI综合分析
        """
        self._stop_requested = False
        self._collecting = True
        self.collection_log = []
        self.sources_status = {}

        ai = self._get_ai_client()
        self._pipeline = IntelPipeline(self.db, ai_client=ai)
        self._pipeline.progress_callback = self._log

        try:
            results = self._pipeline.run_pipeline(
                days=days, start_date=start_date, end_date=end_date)
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            results = {
                'collection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'sources': {}, 'total_cve': 0, 'total_kev': 0,
                'total_epss': 0, 'total_ioc': 0, 'total_threat_actors': 0,
                'total_attack_patterns': 0, 'high_critical_cve': 0,
                'collection_log': self.collection_log,
                'corpus': {}, 'pipeline_state': {}, 'warnings': [str(e)],
                'key_findings': [],
            }

        results['collection_log'] = self.collection_log.copy()
        self.sources_status = results.get('sources', {})
        self._collecting = False

        if not self._stop_requested:
            self._log(f'采集完成: {len(self.sources_status)} 数据源, '
                      f'{results.get("total_cve", 0)} CVE, '
                      f'{results.get("total_ioc", 0)} IOC')
        return results

    # ============ 向后兼容的独立采集方法 (供 main_window.py CVE更新使用) ============
    def fetch_recent_cve(self, days=None, start_date=None, end_date=None, limit=500):
        """从NVD获取最近CVE (兼容旧API)"""
        from intel_sources import NvdCveSource
        src = NvdCveSource(db=self.db, days=days, start_date=start_date,
                           end_date=end_date, limit=limit)
        src._stop_requested = self._stop_requested
        result = src.fetch()
        return result.get('data', [])

    def sync_to_database(self, cve_list):
        """同步CVE到数据库 (兼容旧API)"""
        from intel_sources import NvdCveSource
        src = NvdCveSource(db=self.db)
        return src.sync_to_db(cve_list)

    def fetch_cisa_kev(self):
        """获取CISA KEV (兼容旧API)"""
        from intel_sources import CisaKevSource
        src = CisaKevSource(db=self.db)
        result = src.fetch()
        return result.get('data', [])

    def sync_cisa_kev(self, kev_list):
        """同步KEV到数据库 (兼容旧API)"""
        from intel_sources import CisaKevSource
        src = CisaKevSource(db=self.db)
        return src.sync_to_db(kev_list)

    def fetch_epss_scores(self, cve_ids):
        """获取EPSS评分 (兼容旧API)"""
        from intel_sources import EpssSource
        src = EpssSource(db=self.db, cve_ids=cve_ids)
        result = src.fetch()
        return result.get('data', [])

    def sync_epss_scores(self, epss_list):
        """同步EPSS到数据库 (兼容旧API)"""
        from intel_sources import EpssSource
        src = EpssSource(db=self.db)
        return src.sync_to_db(epss_list)

    def fetch_otx_pulses(self):
        """获取OTX脉冲 (兼容旧API)"""
        from intel_sources import OtxSource
        src = OtxSource(db=self.db)
        result = src.fetch()
        return len(result.get('data', []))

    def fetch_urlhaus(self):
        """获取URLhaus (兼容旧API)"""
        from intel_sources import UrlhausSource
        src = UrlhausSource(db=self.db)
        result = src.fetch()
        return len(result.get('data', []))

    def fetch_malware_bazaar(self):
        """获取MalwareBazaar (兼容旧API)"""
        from intel_sources import MalwareBazaarSource
        src = MalwareBazaarSource(db=self.db)
        result = src.fetch()
        return len(result.get('data', []))


class VulnMatcher:
    """漏洞匹配器 - 增强版：基于服务和版本的智能CVE匹配"""

    def __init__(self, db=None):
        self.db = db

    def match_vulnerabilities(self, host, ports):
        """匹配漏洞 - 对每个开放端口进行全面的CVE匹配，附带丰富元数据供AI核验"""
        vulnerabilities = []
        for port_info in ports:
            if port_info.get('state') != 'open':
                continue
            service = port_info.get('service', '')
            version = port_info.get('version', '')
            product = port_info.get('product', '')
            port = port_info.get('port')

            cves = self._match_cve(service, version, product, port)
            if cves:
                for cve in cves:
                    cve_id = cve.get('cve_id', '')
                    is_kev = self.db.is_kev(cve_id) if self.db else False
                    affected_raw = cve.get('affected_products', '') or ''
                    if isinstance(affected_raw, list):
                        affected_raw = ', '.join(affected_raw)
                    vulnerabilities.append({
                        'host': host, 'port': port,
                        'protocol': port_info.get('protocol', 'tcp'),
                        'service': service,
                        'version': version or product or '',
                        'product': product or '',
                        'cve_id': cve_id, 'cve_name': cve.get('name'),
                        'cvss_score': cve.get('cvss_score'),
                        'severity': cve.get('severity', 'INFO'),
                        'description': (cve.get('description', '') or '')[:500],
                        'affected_versions': affected_raw[:300],
                        'references_url': (cve.get('references_url', '') or '')[:300],
                        'kev': is_kev,
                        'patch_link': cve.get('patch_link', '') or '',
                        'cwe': cve.get('cwe', '') or '',
                        'match_confidence': cve.get('_match_confidence', ''),
                        'matched_by': cve.get('_matched_by', ''),
                    })
            else:
                # 无 CVE 命中（版本未知/无法识别产品）：输出开放服务兜底发现，不再堆 CVE
                vulnerabilities.append({
                    'host': host, 'port': port,
                    'protocol': port_info.get('protocol', 'tcp'),
                    'service': service,
                    'version': version or product or '',
                    'product': product or '',
                    'cve_id': None, 'severity': 'INFO',
                    'description': f'开放服务: {service} {version or product or ""} (端口{port})',
                    'affected_versions': '',
                    'references_url': '',
                    'kev': False,
                    'finding_type': 'open_service',
                })
        return vulnerabilities

    def _match_cve(self, service, version='', product='', port=None):
        """智能CVE匹配 - 精确匹配（产品名一致 + 版本判定）。

        旧实现为关键词召回（对 affected_products/description 做 LIKE + 版本号全文搜索），
        会把 Symantec/Palo Alto/RabbitMQ 等无关产品的 CVE 挂到 msrpc/redis 端口，产生误报。
        现改为：1) version_match.detect_product_key 归一化产品；2) 按召回词 LIKE 召回候选；
        3) version_match.cve_applies 严格校验产品名 + 版本，命中才返回。
        无法识别产品时返回空（由 match_vulnerabilities 输出 open_service 兜底）。
        """
        if not self.db:
            return []
        from version_match import detect_product_key, recall_terms, cve_applies

        key = detect_product_key(product, service)
        if not key:
            return []

        candidates = {}
        for term in recall_terms(key):
            try:
                rows = self.db.search_cve_by_product(term, limit=300)
            except Exception:
                continue
            for cve in rows:
                cve_id = cve.get('cve_id', '')
                if cve_id and cve_id not in candidates:
                    candidates[cve_id] = cve

        matched = []
        detected_name = product or service
        for cve in candidates.values():
            verdict = cve_applies(cve, detected_name, version)
            if not verdict:
                continue
            item = dict(cve)
            item['_match_confidence'] = verdict['confidence']
            item['_matched_by'] = verdict['matched_by']
            matched.append(item)

        matched.sort(key=lambda x: (x.get('cvss_score') or 0), reverse=True)
        return matched


def ai_analyze_threat_data(results: Dict, db=None) -> Dict:
    """AI增强威胁数据分析 — 从流水线语料库提取深度洞察。

    如果 results 包含 AI 分析结果 (corpus.ai_analysis)，直接返回；
    否则基于统计数据生成模板化分析（向后兼容）。
    """
    corpus = results.get('corpus', {})
    ai_analysis = corpus.get('ai_analysis')

    if ai_analysis:
        return {
            'risk_assessment': ai_analysis.get('trend_summary', ''),
            'priority_actions': [
                f"[{a.get('rank', '?')}] {a.get('action', '')} ({a.get('cve', '')})"
                for a in ai_analysis.get('prioritized_actions', [])
            ],
            'trend_analysis': ai_analysis.get('trend_summary', ''),
            'key_findings': ai_analysis.get('key_narratives', []),
            'attack_surface_summary': (
                f"交叉引用 {len(ai_analysis.get('cross_referenced_cves', []))} 个CVE，"
                f"关联到多个威胁行为者"
            ),
        }

    # 向后兼容：基于统计数据的模板化分析
    return {
        'risk_assessment': f"基于 {results.get('total_kev', 0)} 个KEV和 "
                           f"{results.get('high_critical_cve', 0)} 个高危CVE的态势评估",
        'priority_actions': results.get('key_findings', []),
        'trend_analysis': f"{results.get('total_kev', 0)} 个漏洞活跃利用中",
        'key_findings': results.get('key_findings', []),
        'attack_surface_summary': f"{len(results.get('sources', {}))} 数据源采集完成",
    }


def generate_threat_intel_report(results: Dict, db=None) -> str:
    """生成基于实时采集数据的威胁情报摘要HTML。

    不再使用硬编码模板——通过 generate_data_driven_summary()
    读取实际采集结果动态生成内容。
    """
    from intel_pipeline import generate_data_driven_summary

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = generate_data_driven_summary(results)

    # 构建简洁的HTML摘要
    css = """body{font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
max-width:960px;margin:0 auto;padding:40px 20px;color:#1a1a1a;background:#f8f9fa;line-height:1.8}
h1{color:#c0392b;border-bottom:3px solid #c0392b;padding-bottom:12px}
.header-box{background:linear-gradient(135deg,#2c3e50,#c0392b);color:#fff;padding:30px;border-radius:8px;margin-bottom:30px}
.header-box h1{color:#fff;border:none;margin:0 0 10px}
pre{background:#f4f4f4;padding:16px;border-radius:6px;font-family:'Fira Code',Consolas,monospace;font-size:0.9em;white-space:pre-wrap}
.footer{text-align:center;margin-top:40px;padding:20px;color:#95a5a6;font-size:.9em;border-top:1px solid #ddd}"""

    source_status_html = ''
    for name, detail in results.get('corpus', {}).get('source_status', {}).items():
        status_icon = {'success': '✅', 'partial': '⚠️', 'empty': '⚪'}.get(
            detail.get('status', ''), '❌')
        source_status_html += (
            f'<tr><td>{html.escape(str(name))}</td>'
            f'<td>{status_icon} {html.escape(str(detail.get("status", "")))}</td>'
            f'<td>{detail.get("count", 0)}</td>'
            f'<td>{html.escape(str(detail.get("confidence", "")))}</td></tr>')

    summary_text = '\n'.join(lines)
    h = []
    h.append(f'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
             f'<title>全球威胁情报采集摘要</title>\n<style>\n{css}\n</style>\n</head>\n<body>')
    h.append(f'<div class="header-box"><h1>全球威胁情报采集摘要</h1>'
             f'<p><strong>采集时间：{results.get("collection_time", now)}</strong></p>'
             f'<p><strong>数据源：{len(results.get("sources", {}))} 个</strong></p>'
             f'<p>AI增强分析 | 山西有信网安科技有限公司</p></div>')
    h.append(f'<h2>采集摘要</h2><pre>{html.escape(summary_text)}</pre>')

    if source_status_html:
        h.append(f'<h2>数据源详情</h2><table><tr><th>数据源</th><th>状态</th>'
                 f'<th>数量</th><th>可信度</th></tr>{source_status_html}</table>')

    # 警告
    warnings = results.get('warnings', [])
    if warnings:
        h.append('<h2>预警信息</h2><ul>')
        for w in warnings[:10]:
            h.append(f'<li>{html.escape(str(w))}</li>')
        h.append('</ul>')

    h.append('<div class="footer">CISA KEV | NVD | EPSS | OTX | URLhaus | '
             'MalwareBazaar | Check Point | Sysdig | Trend Micro | MS | '
             'Cisco Talos | Mandiant | MITRE ATT&CK<br>'
             'AI分析: Claude Code Security | 山西有信网安科技有限公司 &copy; 2026</div>\n</body>\n</html>')
    return ''.join(h)
