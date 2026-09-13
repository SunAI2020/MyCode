# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 多源威胁情报采集器
支持本地API源 + Web搜索OSINT源，采集时即用AI进行结构化提取和分析"""

import sys
import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── API endpoints (migrated from threat_intel.py) ──
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_API = "https://api.first.org/data/v1/epss"
OTX_PULSES_URL = "https://otx.alienvault.com/api/v1/pulses/subscribed"
ABUSE_URLHAUS = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
ABUSE_MALWARE = "https://mb-api.abuse.ch/api/v1/"


# ═══════════════════════════════════════════════════════════════════
# Base classes
# ═══════════════════════════════════════════════════════════════════

class IntelSource(ABC):
    """威胁情报数据源基类。

    每个子类实现 fetch() 返回结构化数据，可选实现 enrich_with_ai()
    在采集阶段进行AI增强提取。所有数据源必须显式报告状态
    (success/partial/empty/error)，禁止静默失败。
    """

    def __init__(self, db=None):
        self.db = db
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称（用于日志和状态报告）"""
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """'local_api' | 'web_osint'"""
        ...

    @property
    @abstractmethod
    def confidence(self) -> str:
        """可信度评级: P0(官方一手), P1(权威分析), P2(参考)"""
        ...

    @abstractmethod
    def fetch(self) -> Dict:
        """执行数据采集，返回:
        {'status': 'success'|'partial'|'empty'|'error',
         'data': [...], 'summary': str, 'count': int, 'error': str|None}"""
        ...

    def enrich_with_ai(self, raw_result: Dict, ai_client) -> Dict:
        """使用AI对采集结果进行结构化提取和分析（可选重写）。

        返回增强后的 result dict，增加 'ai_summary', 'key_findings',
        'cves_extracted', 'threat_actors_extracted', 'iocs_extracted' 等字段。
        """
        return raw_result


class WebSearchHelper:
    """使用Claude Code CLI的web搜索能力进行OSINT数据采集。

    通过 AIClient.query(max_turns>=4) 让AI执行多轮搜索并返回结构化JSON。
    """

    def __init__(self, ai_client):
        self.ai = ai_client

    def search_and_extract(self, queries: List[str], extraction_schema: str,
                           source_label: str, progress_callback=None) -> Dict:
        """执行web搜索并用AI提取结构化情报。

        Args:
            queries: 搜索查询列表
            extraction_schema: 期望的JSON schema描述
            source_label: 数据源标签
            progress_callback: 进度回调

        Returns:
            {'status': 'success'|'partial'|'error',
             'data': [...], 'summary': str, 'count': int}
        """
        if not self.ai:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': f'{source_label}: AI不可用',
                    'error': 'AI client not available'}

        system_prompt = (
            "你是一名顶级网络安全威胁情报分析专家，为中国网络安全公司"
            "'山西有信网安科技有限公司'工作。\n"
            "你的任务是通过web搜索收集最新的威胁情报信息，并以严格的JSON格式返回。\n"
            "要求：\n"
            "1. 使用web搜索查找最新、最权威的资料来源\n"
            "2. 以JSON格式返回结构化数据，不添加任何额外说明\n"
            "3. 所有CVE编号、IP地址、域名、哈希值必须精确\n"
            "4. 如果无法找到相关信息，返回空列表而非编造数据\n"
            "5. 标注每条信息的可信度和来源URL"
        )

        user_prompt = f"""请搜索以下主题的最新威胁情报信息：

{chr(10).join(f'{i+1}. {q}' for i, q in enumerate(queries))}

{extraction_schema}

请以如下JSON格式返回（不要markdown代码块包裹）：
{{
  "summary": "一句话概述搜索到的关键情报",
  "findings": [
    {{
      "title": "发现标题",
      "description": "详细描述",
      "cves": ["CVE-xxxx-xxxxx"],
      "threat_actors": ["APTxx"],
      "iocs": [{{"type": "ip/domain/url/hash", "value": "xxx", "context": "说明"}}],
      "confidence": "P0/P1/P2",
      "source_url": "https://..."
    }}
  ]
}}"""

        try:
            if progress_callback:
                try:
                    progress_callback(f'  [搜索] {source_label}: AI多轮搜索中...')
                except UnicodeEncodeError:
                    progress_callback(f'  [Search] {source_label}: searching...')
            raw = self.ai.query(
                user_message=user_prompt,
                system_prompt=system_prompt,
                max_turns=6,
                timeout=600
            )
            result = self._parse_json_response(raw)
            result['status'] = 'success' if result.get('findings') else 'empty'
            result['count'] = len(result.get('findings', []))
            result['data'] = result.pop('findings', [])
            if progress_callback:
                try:
                    progress_callback(
                        f'  [完成] {source_label}: 找到 {result["count"]} 条相关情报')
                except UnicodeEncodeError:
                    progress_callback(
                        f'  [Done] {source_label}: {result["count"]} findings')
            return result
        except Exception as e:
            logger.error(f"{source_label} AI搜索失败: {e}")
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': f'{source_label}: {e}', 'error': str(e)}

    def _parse_json_response(self, raw: str) -> Dict:
        """从AI响应中提取JSON。兼容markdown代码块包裹的情况。"""
        text = raw.strip()
        if '```json' in text:
            start = text.index('```json') + 7
            end = text.index('```', start)
            text = text[start:end].strip()
        elif text.startswith('```'):
            end = text.index('```', 3)
            text = text[3:end].strip()
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]
        return json.loads(text)


# ═══════════════════════════════════════════════════════════════════
# Local API sources (migrated and enhanced from threat_intel.py)
# ═══════════════════════════════════════════════════════════════════

class CisaKevSource(IntelSource):
    """CISA KEV — 已知被利用漏洞目录。官方一手数据，可信度P0。"""

    source_name = "CISA KEV"
    source_type = "local_api"
    confidence = "P0"

    def fetch(self) -> Dict:
        results = []
        try:
            resp = requests.get(CISA_KEV_URL, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for vuln in data.get('vulnerabilities', []):
                    results.append({
                        'cve_id': vuln.get('cveID'),
                        'vulnerability_name': vuln.get('vulnerabilityName', ''),
                        'date_added': (vuln.get('dateAdded', '') or '')[:10],
                        'due_date': (vuln.get('dueDate', '') or '')[:10],
                        'required_action': vuln.get('requiredAction', ''),
                        'known_ransomware': 1 if vuln.get(
                            'knownRansomwareCampaignUse') == 'Known' else 0,
                        'notes': vuln.get('notes', '')
                    })
                return {
                    'status': 'success' if results else 'empty',
                    'data': results, 'count': len(results),
                    'summary': f'CISA KEV: {len(results)} 条已知被利用漏洞',
                    'error': None
                }
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': f'CISA KEV HTTP {resp.status_code}',
                    'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"KEV失败: {e}")
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': f'CISA KEV失败: {e}', 'error': str(e)}
        return {'status': 'error', 'data': [], 'count': 0,
                'summary': 'CISA KEV: 非200状态码', 'error': 'Non-200 response'}

    def sync_to_db(self, data: List[Dict]) -> int:
        if not self.db:
            return 0
        count = 0
        for kev in data:
            try:
                self.db.intel.add_kev(kev)
                count += 1
            except:
                pass
        return count


class NvdCveSource(IntelSource):
    """NVD CVE — 国家漏洞数据库。官方一手数据，可信度P0。"""

    source_name = "NVD CVE"
    source_type = "local_api"
    confidence = "P0"

    def __init__(self, db=None, days=None, start_date=None, end_date=None, limit=500):
        super().__init__(db)
        self.days = days
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit

    def fetch(self) -> Dict:
        results = []
        if self.start_date and self.end_date:
            dt_end = datetime.strptime(self.end_date, '%Y-%m-%d')
            dt_start = datetime.strptime(self.start_date, '%Y-%m-%d')
        else:
            d = self.days if self.days is not None else 7
            dt_end = datetime.utcnow()
            dt_start = dt_end - timedelta(days=d)

        params = {
            'pubStartDate': dt_start.strftime('%Y-%m-%dT00:00:00.000'),
            'pubEndDate': dt_end.strftime('%Y-%m-%dT23:59:59.000'),
            'resultsPerPage': min(self.limit, 100),
            'startIndex': 0
        }

        retry_count = 0
        max_retries = 5

        try:
            while True:
                if self._stop_requested:
                    break
                try:
                    resp = requests.get(NVD_API, params=params, timeout=(10, 60))
                except (requests.exceptions.SSLError,
                        requests.exceptions.ConnectionError,
                        requests.exceptions.ReadTimeout,
                        requests.exceptions.ChunkedEncodingError) as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error(f"NVD获取失败(已重试{max_retries}次): {e}")
                        break
                    delay = 2 * (2 ** (retry_count - 1))
                    logger.warning(f"NVD网络错误: {e}，{delay}秒后重试({retry_count}/{max_retries})")
                    time.sleep(delay)
                    continue

                if resp.status_code == 200:
                    retry_count = 0
                    data = resp.json()
                    items = data.get('vulnerabilities', [])
                    if not items:
                        break
                    for item in items:
                        cve_data = self._parse_cve_item(item)
                        if cve_data:
                            results.append(cve_data)
                    if len(items) < params['resultsPerPage']:
                        break
                    params['startIndex'] += params['resultsPerPage']
                    time.sleep(0.6)
                elif resp.status_code == 429:
                    retry_count += 1
                    if retry_count > max_retries:
                        break
                    time.sleep(6)
                else:
                    break
        except Exception as e:
            logger.error(f"NVD获取失败: {e}")
            return {'status': 'error', 'data': results, 'count': len(results),
                    'summary': f'NVD CVE失败: {e}', 'error': str(e)}

        status = 'success' if results else 'empty'
        high_count = sum(1 for c in results if (c.get('cvss_score') or 0) >= 7.0)
        return {
            'status': status,
            'data': results, 'count': len(results),
            'summary': f'NVD CVE: {len(results)} 条 (高危/严重 {high_count} 条)',
            'high_critical_count': high_count,
            'error': None
        }

    def _parse_cve_item(self, item):
        try:
            cve = item.get('cve', {})
            cve_id = cve.get('id', '')
            if not cve_id:
                return None
            desc = ''
            for d in cve.get('descriptions', []):
                if d.get('lang') == 'en':
                    desc = d.get('value', '')[:500]
            cvss_score = None
            severity = 'UNKNOWN'
            metrics = cve.get('metrics', {})
            for key in ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']:
                if key in metrics and metrics[key]:
                    cvss_data = metrics[key][0].get('cvssData', {})
                    cvss_score = cvss_data.get('baseScore')
                    severity = cvss_data.get('baseSeverity', severity).upper()
                    break
            published = (cve.get('published', '') or '')[:10]
            products = []
            for cfg in cve.get('configurations', []):
                for node in cfg.get('nodes', []):
                    for match in node.get('cpeMatch', []):
                        criteria = match.get('criteria', '')
                        if criteria:
                            parts = criteria.split(':')
                            if len(parts) >= 5:
                                products.append(f"{parts[3]}:{parts[4]}")
            refs = []
            for ref in cve.get('references', [])[:5]:
                refs.append(ref.get('url', ''))
            return {
                'cve_id': cve_id, 'name': cve_id, 'description': desc,
                'cvss_score': cvss_score, 'severity': severity,
                'published_date': published,
                'modified_date': (cve.get('lastModified', '') or '')[:10],
                'affected_products': list(set(products))[:10],
                'references': refs, 'ai_analysis': None
            }
        except:
            return None

    def sync_to_db(self, data: List[Dict]) -> int:
        if not self.db:
            return 0
        cve_ids = [c.get('cve_id') for c in data if c.get('cve_id')]
        if not cve_ids:
            return 0
        # 分批 IN 查询现有 CVE，避免 search_cve(limit=9990000) 全表入内存
        existing_ids = set()
        conn = self.db.conn  # Database.conn → CVEDatabase.conn
        for i in range(0, len(cve_ids), 500):
            chunk = cve_ids[i:i + 500]
            placeholders = ','.join(['?'] * len(chunk))
            rows = conn.execute(
                f'SELECT cve_id FROM cve_database WHERE cve_id IN ({placeholders})',
                chunk
            ).fetchall()
            existing_ids.update(r['cve_id'] for r in rows)
        new_cves = [c for c in data if c.get('cve_id') not in existing_ids]
        if new_cves:
            return self.db.add_cve_batch(new_cves)
        return 0


class EpssSource(IntelSource):
    """EPSS — 漏洞利用预测评分系统。可信度P1。"""

    source_name = "EPSS"
    source_type = "local_api"
    confidence = "P1"

    def __init__(self, db=None, cve_ids=None):
        super().__init__(db)
        self.cve_ids = cve_ids

    def fetch(self) -> Dict:
        results = []
        try:
            # 优先使用调用方显式传入的 CVE 列表，否则回退到 DB 中 CVSS>=7.0 的 CVE
            if self.cve_ids:
                cve_ids = list(self.cve_ids)
            elif self.db:
                recent_cves = self.db.search_cve(min_cvss=7.0, limit=200)
                cve_ids = [c['cve_id'] for c in recent_cves]
            else:
                cve_ids = []
            if not cve_ids:
                return {'status': 'empty', 'data': [], 'count': 0,
                        'summary': 'EPSS: 无CVE可供查询', 'error': None}
            for i in range(0, len(cve_ids), 100):
                if self._stop_requested:
                    break
                batch = cve_ids[i:i + 100]
                resp = requests.get(EPSS_API,
                                    params={'cve': ','.join(batch)},
                                    timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get('data', []):
                        results.append({
                            'cve_id': item.get('cve'),
                            'epss_score': float(item.get('epss', 0)),
                            'percentile': float(item.get('percentile', 0))
                        })
            return {
                'status': 'success' if results else 'empty',
                'data': results, 'count': len(results),
                'summary': f'EPSS: {len(results)} 条利用预测评分',
                'error': None
            }
        except Exception as e:
            logger.error(f"EPSS失败: {e}")
            return {'status': 'error', 'data': results, 'count': len(results),
                    'summary': f'EPSS失败: {e}', 'error': str(e)}

    def sync_to_db(self, data: List[Dict]) -> int:
        if not self.db:
            return 0
        count = 0
        for ep in data:
            try:
                self.db.intel.add_epss(ep['cve_id'], ep['epss_score'],
                                       ep.get('percentile'))
                count += 1
            except:
                pass
        return count


class OtxSource(IntelSource):
    """AlienVault OTX — 开源威胁情报社区。可信度P1-P2。"""

    source_name = "AlienVault OTX"
    source_type = "local_api"
    confidence = "P1-P2"

    def fetch(self) -> Dict:
        results = []
        try:
            headers = {'User-Agent': 'AI-Vuln-Scanner/2.0'}
            resp = requests.get(OTX_PULSES_URL, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for pulse in data.get('results', [])[:100]:
                    for indicator in pulse.get('indicators', [])[:5]:
                        ioc_type = indicator.get('type', 'unknown')
                        ioc_value = indicator.get('indicator', '')
                        if ioc_type and ioc_value:
                            results.append({
                                'ioc_type': ioc_type,
                                'ioc_value': ioc_value,
                                'threat_actor': pulse.get('author_name', ''),
                                'confidence': 'medium',
                                'source': 'AlienVault OTX',
                                'description': pulse.get('name', '')[:200]
                            })
                status = 'success' if results else 'empty'
                return {
                    'status': status, 'data': results,
                    'count': len(results),
                    'summary': f'AlienVault OTX: {len(results)} 个威胁指标',
                    'error': None
                }
        except Exception as e:
            logger.error(f"OTX失败: {e}")
            return {'status': 'error', 'data': results, 'count': 0,
                    'summary': f'AlienVault OTX失败: {e}', 'error': str(e)}
        return {'status': 'error', 'data': results, 'count': 0,
                'summary': 'AlienVault OTX: 非200状态码', 'error': 'Non-200 response'}

    def sync_to_db(self, data: List[Dict]) -> int:
        if not self.db:
            return 0
        count = 0
        for ioc in data:
            try:
                self.db.intel.add_ioc(ioc)
                count += 1
            except:
                pass
        return count


class UrlhausSource(IntelSource):
    """Abuse.ch URLhaus — 恶意URL数据库。可信度P1。"""

    source_name = "URLhaus"
    source_type = "local_api"
    confidence = "P1"

    def fetch(self) -> Dict:
        results = []
        try:
            resp = requests.get(ABUSE_URLHAUS, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for url in data.get('urls', [])[:50]:
                    results.append({
                        'ioc_type': 'url',
                        'ioc_value': url.get('url', ''),
                        'malware_family': url.get('threat', ''),
                        'confidence': 'high',
                        'source': 'Abuse.ch URLhaus',
                        'description': f"恶意URL: {url.get('url_status', '')}"
                    })
                status = 'success' if results else 'empty'
                return {
                    'status': status, 'data': results,
                    'count': len(results),
                    'summary': f'URLhaus: {len(results)} 个恶意URL',
                    'error': None
                }
        except Exception as e:
            logger.error(f"URLhaus失败: {e}")
            return {'status': 'error', 'data': results, 'count': 0,
                    'summary': f'URLhaus失败: {e}', 'error': str(e)}
        return {'status': 'error', 'data': results, 'count': 0,
                'summary': 'URLhaus: 非200状态码', 'error': 'Non-200 response'}

    def sync_to_db(self, data: List[Dict]) -> int:
        if not self.db:
            return 0
        count = 0
        for ioc in data:
            try:
                self.db.intel.add_ioc(ioc)
                count += 1
            except:
                pass
        return count


class MalwareBazaarSource(IntelSource):
    """Abuse.ch MalwareBazaar — 恶意软件样本库。可信度P1。"""

    source_name = "MalwareBazaar"
    source_type = "local_api"
    confidence = "P1"

    def fetch(self) -> Dict:
        results = []
        try:
            req_data = {'query': 'get_recent', 'selector': 'time'}
            resp = requests.post(ABUSE_MALWARE, data=req_data, timeout=20)
            if resp.status_code == 200:
                result = resp.json()
                for item in result.get('data', [])[:50]:
                    sha256 = item.get('sha256_hash', '')
                    if sha256:
                        results.append({
                            'ioc_type': 'file_hash',
                            'ioc_value': sha256,
                            'malware_family': (item.get('signature', '') or '')[:100],
                            'confidence': 'high',
                            'source': 'MalwareBazaar',
                            'description': f"{item.get('file_type', '')} - {item.get('tags', '')}"
                        })
                status = 'success' if results else 'empty'
                return {
                    'status': status, 'data': results,
                    'count': len(results),
                    'summary': f'MalwareBazaar: {len(results)} 个恶意样本',
                    'error': None
                }
        except Exception as e:
            logger.error(f"MalwareBazaar失败: {e}")
            return {'status': 'error', 'data': results, 'count': 0,
                    'summary': f'MalwareBazaar失败: {e}', 'error': str(e)}
        return {'status': 'error', 'data': results, 'count': 0,
                'summary': 'MalwareBazaar: 非200状态码', 'error': 'Non-200 response'}

    def sync_to_db(self, data: List[Dict]) -> int:
        if not self.db:
            return 0
        count = 0
        for ioc in data:
            try:
                self.db.intel.add_ioc(ioc)
                count += 1
            except:
                pass
        return count


# ═══════════════════════════════════════════════════════════════════
# Web-search OSINT sources (AI-powered, uses Claude Code CLI web search)
# ═══════════════════════════════════════════════════════════════════

class CisaAlertsSource(IntelSource):
    """CISA 安全警报 — 通过AI web搜索获取最新CISA公告。可信度P0-P1。"""

    source_name = "CISA Alerts"
    source_type = "web_osint"
    confidence = "P0-P1"

    def __init__(self, db=None, ai_client=None):
        super().__init__(db)
        self.ai = ai_client
        self.searcher = WebSearchHelper(ai_client) if ai_client else None

    def fetch(self) -> Dict:
        if not self.searcher:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': 'CISA Alerts: AI不可用', 'error': 'AI not available'}
        return self.searcher.search_and_extract(
            queries=[
                "CISA emergency directive 2026 latest alerts",
                "CISA known exploited vulnerabilities catalog 2026 new additions",
                "CISA BOD binding operational directive 2026"
            ],
            extraction_schema=(
                "提取所有2026年CISA发布的安全警报、紧急指令(ED)、"
                "约束性操作指令(BOD)。重点关注：涉及的具体CVE编号、"
                "受影响产品、修复截止日期、是否为勒索软件利用。"
            ),
            source_label="CISA Alerts"
        )


class CheckPointResearchSource(IntelSource):
    """Check Point Research — 权威威胁情报分析。可信度P1。"""

    source_name = "Check Point Research"
    source_type = "web_osint"
    confidence = "P1"

    def __init__(self, db=None, ai_client=None):
        super().__init__(db)
        self.ai = ai_client
        self.searcher = WebSearchHelper(ai_client) if ai_client else None

    def fetch(self) -> Dict:
        if not self.searcher:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': 'Check Point Research: AI不可用',
                    'error': 'AI not available'}
        return self.searcher.search_and_extract(
            queries=[
                "Check Point Research 2026 H1 threat landscape report ransomware",
                "Check Point Research 2026 Qilin ransomware analysis VPN exploitation",
                "Check Point Research 2026 global cyber attack trends statistics"
            ],
            extraction_schema=(
                "从Check Point Research的2026年H1报告中提取："
                "1. 勒索软件团伙排名及受害者数量（Qilin, Akira, The Gentlemen等）"
                "2. VPN和边界设备漏洞被利用的具体数据和趋势"
                "3. 全球网络攻击的同比增长率和关键统计数字"
                "4. 涉及的关键CVE编号和攻击向量"
            ),
            source_label="Check Point Research"
        )


class SysdigSource(IntelSource):
    """Sysdig — 容器和云安全威胁研究。可信度P1。"""

    source_name = "Sysdig"
    source_type = "web_osint"
    confidence = "P1"

    def __init__(self, db=None, ai_client=None):
        super().__init__(db)
        self.ai = ai_client
        self.searcher = WebSearchHelper(ai_client) if ai_client else None

    def fetch(self) -> Dict:
        if not self.searcher:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': 'Sysdig: AI不可用', 'error': 'AI not available'}
        return self.searcher.search_and_extract(
            queries=[
                "Sysdig 2026 JADEPUFFER AI agent ransomware attack analysis",
                "Sysdig TRT 2026 cloud security container threats report",
                "Sysdig 2026 supply chain attack CVE-2026-33634 Trivy compromise"
            ],
            extraction_schema=(
                "从Sysdig威胁研究团队的2026年报告中提取："
                "1. JADEPUFFER AI自主勒索攻击的完整技术分析（攻击链、时间线、影响）"
                "2. 2026年容器和云原生环境的主要威胁趋势"
                "3. 供应链攻击的具体案例和技术细节"
                "4. 涉及的关键CVE编号"
            ),
            source_label="Sysdig"
        )


class TrendMicroSource(IntelSource):
    """Trend Micro — 全球威胁态势分析。可信度P1。"""

    source_name = "Trend Micro"
    source_type = "web_osint"
    confidence = "P1"

    def __init__(self, db=None, ai_client=None):
        super().__init__(db)
        self.ai = ai_client
        self.searcher = WebSearchHelper(ai_client) if ai_client else None

    def fetch(self) -> Dict:
        if not self.searcher:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': 'Trend Micro: AI不可用', 'error': 'AI not available'}
        return self.searcher.search_and_extract(
            queries=[
                "Trend Micro 2026 H1 cybersecurity threat landscape report",
                "Trend Micro 2026 QLNX Linux malware developer RAT analysis",
                "Trend Micro 2026 ransomware APT group activity report"
            ],
            extraction_schema=(
                "从Trend Micro 2026年H1报告中提取："
                "1. 全球威胁态势的关键统计数据和趋势分析"
                "2. 新型恶意软件家族的技术分析（QLNX等）"
                "3. APT组织和勒索软件团伙的最新活动"
                "4. 涉及的关键CVE编号和攻击技术(MITRE ATT&CK)"
            ),
            source_label="Trend Micro"
        )


class MicrosoftSecuritySource(IntelSource):
    """Microsoft Security Response Center — 月度安全更新和威胁情报。可信度P0。"""

    source_name = "Microsoft Security"
    source_type = "web_osint"
    confidence = "P0"

    def __init__(self, db=None, ai_client=None):
        super().__init__(db)
        self.ai = ai_client
        self.searcher = WebSearchHelper(ai_client) if ai_client else None

    def fetch(self) -> Dict:
        if not self.searcher:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': 'Microsoft Security: AI不可用', 'error': 'AI not available'}
        return self.searcher.search_and_extract(
            queries=[
                "Microsoft Security Response Center 2026 July Patch Tuesday 569 CVE record",
                "Microsoft 2026 zero-day vulnerabilities CVE-2026-56155 CVE-2026-56164 exploited",
                "Microsoft DART 2026 threat intelligence report APT activity"
            ],
            extraction_schema=(
                "从Microsoft Security Response Center 2026年报告中提取："
                "1. 2026年每月的Patch Tuesday CVE数量（特别是7月的569个CVE记录）"
                "2. 所有2026年在野利用的0day漏洞（含CVE编号、CVSS评分、影响产品）"
                "3. DART团队发现的关键威胁和事件响应案例"
                "4. 涉及AD FS、SharePoint、Office等企业产品的关键漏洞"
            ),
            source_label="Microsoft Security"
        )


class CiscoTalosSource(IntelSource):
    """Cisco Talos — 网络威胁情报。可信度P1。"""

    source_name = "Cisco Talos"
    source_type = "web_osint"
    confidence = "P1"

    def __init__(self, db=None, ai_client=None):
        super().__init__(db)
        self.ai = ai_client
        self.searcher = WebSearchHelper(ai_client) if ai_client else None

    def fetch(self) -> Dict:
        if not self.searcher:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': 'Cisco Talos: AI不可用', 'error': 'AI not available'}
        return self.searcher.search_and_extract(
            queries=[
                "Cisco Talos 2026 threat intelligence report XenShell attack chain",
                "Cisco Talos 2026 SD-WAN CVE-2026-20127 exploitation clusters",
                "Cisco Talos 2026 APT group activity ransomware trends"
            ],
            extraction_schema=(
                "从Cisco Talos 2026年报告中提取："
                "1. XenShell攻击链（CVE-2026-20127/20128/20133/20122）的完整技术分析"
                "2. 至少10个威胁集群利用Cisco SD-WAN漏洞的详情"
                "3. 2026年APT组织和勒索软件的最新TTP"
                "4. 涉及Cisco产品的所有关键CVE和安全公告"
            ),
            source_label="Cisco Talos"
        )


class MandiantSource(IntelSource):
    """Mandiant (Google Cloud) — 高级威胁行为者追踪。可信度P0-P1。"""

    source_name = "Mandiant"
    source_type = "web_osint"
    confidence = "P0-P1"

    def __init__(self, db=None, ai_client=None):
        super().__init__(db)
        self.ai = ai_client
        self.searcher = WebSearchHelper(ai_client) if ai_client else None

    def fetch(self) -> Dict:
        if not self.searcher:
            return {'status': 'error', 'data': [], 'count': 0,
                    'summary': 'Mandiant: AI不可用', 'error': 'AI not available'}
        return self.searcher.search_and_extract(
            queries=[
                "Mandiant 2026 APT threat actor activity report Fancy Bear APT28",
                "Mandiant 2026 China APT Storm-1175 UNC threat groups operations",
                "Mandiant 2026 Iran MuddyWater Static Kitten cyber operations"
            ],
            extraction_schema=(
                "从Mandiant 2026年威胁行为者追踪报告中提取："
                "1. 俄罗斯APT（APT28/APT29）的最新活动和利用的CVE"
                "2. 中国APT（Storm-1175, Salt Typhoon等）的最新操作"
                "3. 伊朗APT（MuddyWater, Handala等）的攻击活动和TTP"
                "4. 新兴威胁行为者和攻击模式的识别"
            ),
            source_label="Mandiant"
        )


# ═══════════════════════════════════════════════════════════════════
# Source registry & factory functions
# ═══════════════════════════════════════════════════════════════════

LOCAL_API_SOURCES = [CisaKevSource, NvdCveSource, EpssSource,
                     OtxSource, UrlhausSource, MalwareBazaarSource]

WEB_OSINT_SOURCES = [CisaAlertsSource, CheckPointResearchSource, SysdigSource,
                     TrendMicroSource, MicrosoftSecuritySource,
                     CiscoTalosSource, MandiantSource]

ALL_SOURCE_CLASSES = LOCAL_API_SOURCES + WEB_OSINT_SOURCES


def create_local_sources(db, days=None, start_date=None, end_date=None) -> List[IntelSource]:
    """创建所有本地API数据源实例"""
    sources = []
    for cls in LOCAL_API_SOURCES:
        if cls is NvdCveSource:
            sources.append(cls(db=db, days=days, start_date=start_date,
                               end_date=end_date))
        else:
            sources.append(cls(db=db))
    return sources


def create_osint_sources(db, ai_client) -> List[IntelSource]:
    """创建所有Web搜索OSINT数据源实例"""
    return [cls(db=db, ai_client=ai_client) for cls in WEB_OSINT_SOURCES]
