# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - AI增强威胁情报采集流水线
三阶段流程: 本地API(并行) -> Web OSINT(串行AI搜索) -> AI综合分析
采集过程中实时输出数据同步进度，而非硬编码模板"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from intel_sources import (IntelSource, create_local_sources,
                           create_osint_sources, CisaKevSource, NvdCveSource,
                           EpssSource, OtxSource, UrlhausSource,
                           MalwareBazaarSource)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Seed data for threat actors and attack patterns (migrated from threat_intel.py)
_SEED_ACTORS = [
    ('APT29', 'Cozy Bear, The Dukes', '政府间谍', '政府、外交、医疗',
     'WellMess, Sorefang, Sunburst', 'CVE-2021-26855,CVE-2021-26857',
     '俄罗斯对外情报局(SVR)支持的APT组织，以供应链攻击著称', '2020-01-01', '2026-05-01'),
    ('APT41', 'Winnti, Barium', '政府间谍+经济犯罪', '政府、科技、游戏',
     'Winnti, ShadowPad, Gh0st', 'CVE-2021-44228,CVE-2020-1472',
     '中国关联的APT组织，同时从事间谍和经济犯罪活动', '2018-01-01', '2026-05-01'),
    ('LockBit', 'LockBit 3.0', '经济利益', '全行业',
     'LockBit Ransomware, StealBit', 'CVE-2023-0669,CVE-2021-22986',
     '全球最活跃的勒索软件即服务(RaaS)组织', '2022-01-01', '2026-05-01'),
    ('APT28', 'Fancy Bear, Sofacy', '政府间谍', '政府、军事、能源',
     'X-Agent, X-Tunnel, Zebrocy', 'CVE-2022-30190,CVE-2023-23397',
     '俄罗斯总参谋部情报总局(GRU)支持的APT组织', '2015-01-01', '2026-05-01'),
    ('Lazarus Group', 'HIDDEN COBRA, Zinc', '政府间谍+经济利益',
     '金融、政府、加密货币', 'AppleJeus, FallChill, Volgmer',
     'CVE-2022-30190,CVE-2021-34473',
     '朝鲜国家支持的APT组织，以金融攻击和加密货币盗窃著称', '2016-01-01', '2026-05-01'),
    ('FIN7', 'Carbanak, Anunak', '经济利益', '金融、零售、酒店',
     'Carbanak, Cobalt Strike, Lizar', 'CVE-2022-30190,CVE-2022-44789',
     '以经济动机为主的网络犯罪组织，攻击POS系统和银行', '2017-01-01', '2026-05-01'),
    ('BlackCat/ALPHV', 'ALPHV, Noberus', '经济利益', '全行业',
     'BlackCat Ransomware, Exmatter', 'CVE-2023-27350,CVE-2022-21882',
     '高级勒索软件即服务组织，使用Rust编写勒索软件', '2022-06-01', '2026-05-01'),
    ('Kimsuky', 'Thallium, Velvet Chollima', '政府间谍', '政府、智库、学术',
     'BabyShark, AppleSeed, GoldDragon', 'CVE-2022-30190,CVE-2023-38831',
     '朝鲜支持的APT组织，主要针对韩国和美国的智库', '2018-01-01', '2026-05-01'),
]

_SEED_ATTACK_PATTERNS = [
    ('T1190', '利用面向公众的应用', '初始访问', 'Windows/Linux/Web',
     '攻击者利用面向公众的应用获取初始访问',
     '部署WAF/IDS, 及时打补丁, 减少攻击面',
     '定期漏洞扫描, 监控异常HTTP请求'),
    ('T1203', '利用客户端应用', '执行', 'Windows/macOS',
     '攻击者利用客户端软件漏洞执行恶意代码',
     '及时更新软件, 使用应用白名单, 沙箱隔离',
     '监控异常进程创建, EDR检测恶意行为'),
    ('T1068', '利用权限提升', '权限提升', 'Windows/Linux',
     '攻击者利用系统漏洞提升权限至管理员/root',
     '最小权限原则, 补丁管理, UAC配置',
     '审计权限变更, 监控异常进程权限'),
    ('T1210', '利用远程服务', '横向移动', 'Windows/Linux',
     '攻击者利用远程服务漏洞在内部网络横向移动',
     '网络分段, 限制远程服务访问, 强认证',
     '监控异常远程连接, 审计远程访问日志'),
    ('T1566', '钓鱼邮件', '初始访问', 'Windows/macOS/Linux',
     '攻击者发送钓鱼邮件诱骗用户打开恶意附件或链接',
     '邮件过滤, 安全意识培训, 附件沙箱检测',
     '监控邮件附件, URL检测, 异常登录监控'),
    ('T1059', '命令与脚本解释器', '执行', 'Windows/Linux/macOS',
     '攻击者使用PowerShell/Bash/Python等脚本执行命令',
     '限制脚本执行, 日志记录, 应用控制',
     '监控命令行, 检测混淆脚本'),
    ('T1486', '数据加密勒索', '影响', 'Windows/Linux',
     '攻击者加密受害者数据并要求赎金',
     '定期备份, 防病毒软件, 用户教育',
     '监控大量文件修改, 检测加密进程'),
    ('T1041', '通过C2通道数据渗出', '数据渗出', '所有平台',
     '攻击者通过C2通道将窃取数据传送到外部服务器',
     '出站流量过滤, DLP方案, 异常流量检测',
     '监控异常出站流量, DNS隧道检测'),
    ('T1078', '有效账户', '防御绕过/持久化/初始访问', '所有平台',
     '攻击者使用窃取/购买的合法凭据获取访问',
     'MFA, 定期密码轮换, 账户审计',
     '异常登录检测, 不可能旅行检测'),
    ('T1547', '启动/登录自动执行', '持久化/权限提升', 'Windows/Linux/macOS',
     '攻击者配置系统自动执行恶意代码维持持久化',
     '启动项审计, 注册表监控, 应用白名单',
     '监控启动项变更'),
]


class PipelineState:
    """流水线实时状态追踪器。用于驱动数据同步的屏幕输出。"""

    def __init__(self):
        self.phase = 'init'
        self.phase_label = '初始化'
        self.sources_completed = []
        self.sources_failed = []
        self.sources_empty = []
        self.current_source = None
        self.source_details = {}
        self.stats = {
            'kev_total': 0, 'cve_new': 0, 'cve_high_critical': 0,
            'epss_total': 0, 'ioc_total': 0, 'actor_total': 0,
            'pattern_total': 0, 'osint_findings': 0
        }
        self.key_findings = []
        self.warnings = []
        self.start_time = None
        self.end_time = None

    def to_dict(self) -> Dict:
        return {
            'phase': self.phase, 'phase_label': self.phase_label,
            'sources_completed': self.sources_completed,
            'sources_failed': self.sources_failed,
            'sources_empty': self.sources_empty,
            'current_source': self.current_source,
            'source_details': self.source_details,
            'stats': self.stats, 'key_findings': self.key_findings,
            'warnings': self.warnings,
            'start_time': self.start_time, 'end_time': self.end_time
        }


class IntelPipeline:
    """AI增强威胁情报采集流水线。

    三阶段流程:
      Phase 1: 本地API源并行采集 (6个源)
      Phase 2: Web OSINT源串行AI搜索 (7个源)
      Phase 3: AI综合分析 + 交叉验证 + 结构化语料生成
    """

    def __init__(self, db, ai_client=None):
        self.db = db
        self.ai = ai_client
        self.progress_callback: Optional[Callable[[str], None]] = None
        self._cancelled = False
        self.state = PipelineState()

    def cancel(self):
        self._cancelled = True

    def _emit(self, msg: str):
        if self.progress_callback:
            try:
                self.progress_callback(msg)
            except UnicodeEncodeError:
                # Fallback for non-unicode terminals
                self.progress_callback(msg.encode('ascii', errors='replace').decode('ascii'))

    # ── Phase 1: 本地API并行采集 ──

    def _run_phase1_local(self, days=None, start_date=None, end_date=None) -> Dict:
        self.state.phase = 'phase_1_local'
        self.state.phase_label = 'Phase 1: 本地API数据源采集'
        self._emit('══ Phase 1/3: 本地API数据源采集 ══')

        sources = create_local_sources(self.db, days=days,
                                       start_date=start_date, end_date=end_date)
        phase_results = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._run_single_source, src): src
                for src in sources
            }
            for future in as_completed(futures):
                if self._cancelled:
                    for f in futures:
                        f.cancel()
                    break
                src = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = {'status': 'error', 'data': [], 'count': 0,
                              'summary': f'{src.source_name}: {e}', 'error': str(e)}
                phase_results[src.source_name] = result
                self._process_source_result(src, result)

        nvd_result = phase_results.get('NVD CVE', {})
        kev_result = phase_results.get('CISA KEV', {})
        epss_result = phase_results.get('EPSS', {})
        otx_result = phase_results.get('AlienVault OTX', {})
        urlhaus_result = phase_results.get('URLhaus', {})
        bazaar_result = phase_results.get('MalwareBazaar', {})

        self.state.stats['kev_total'] = kev_result.get('count', 0)
        self.state.stats['cve_new'] = nvd_result.get('count', 0)
        self.state.stats['cve_high_critical'] = nvd_result.get('high_critical_count', 0)
        self.state.stats['epss_total'] = epss_result.get('count', 0)
        self.state.stats['ioc_total'] = (
            otx_result.get('count', 0) +
            urlhaus_result.get('count', 0) +
            bazaar_result.get('count', 0)
        )

        if nvd_result.get('high_critical_count', 0) > 0:
            self.state.key_findings.append(
                f"NVD采集到 {nvd_result['high_critical_count']} 个高危/严重CVE (CVSS>=7.0)")
        if kev_result.get('count', 0) > 0:
            self.state.key_findings.append(
                f"CISA KEV目录共 {kev_result['count']} 条已知被利用漏洞")

        self._emit(f'── Phase 1 完成: KEV {kev_result.get("count",0)}条 | '
                   f'CVE新增 {nvd_result.get("count",0)}条 | '
                   f'IOC {self.state.stats["ioc_total"]}个 ──')
        return phase_results

    def _run_single_source(self, src: IntelSource) -> Dict:
        self.state.current_source = src.source_name
        self._emit(f'  [{src.source_name}] 采集开始 '
                   f'(类型: {src.source_type}, 可信度: {src.confidence})')
        return src.fetch()

    def _process_source_result(self, src: IntelSource, result: Dict):
        src_name = src.source_name
        status = result.get('status', 'error')
        count = result.get('count', 0)

        self.state.source_details[src_name] = {
            'status': status, 'count': count,
            'summary': result.get('summary', ''),
            'type': src.source_type, 'confidence': src.confidence
        }

        if status == 'success':
            self.state.sources_completed.append(src_name)
            synced = 0
            if hasattr(src, 'sync_to_db') and result.get('data'):
                synced = src.sync_to_db(result['data'])
            self._emit(f'  ✅ [{src_name}]: {count} 条 (同步 {synced} 条)')
        elif status == 'partial':
            self.state.sources_completed.append(src_name)
            self.state.warnings.append(f'{src_name}: 部分数据 ({count} 条)，可能不完整')
            self._emit(f'  ⚠️ [{src_name}]: 部分数据 ({count} 条)')
        elif status == 'empty':
            self.state.sources_empty.append(src_name)
            self.state.warnings.append(f'{src_name}: 返回空数据，请检查数据源可用性')
            self._emit(f'  ⚪ [{src_name}]: 返回空')
        else:
            self.state.sources_failed.append(src_name)
            self.state.warnings.append(f'{src_name}: {result.get("error", "未知错误")}')
            self._emit(f'  ❌ [{src_name}]: 采集失败 - {result.get("error", "未知")}')

    # ── Phase 2: Web OSINT串行采集 ──

    def _run_phase2_osint(self) -> Dict:
        self.state.phase = 'phase_2_osint'
        self.state.phase_label = 'Phase 2: 权威公开报告AI搜索采集'

        if not self.ai:
            self._emit('══ Phase 2/3: 跳过 (AI不可用) ══')
            return {}

        self._emit('══ Phase 2/3: 权威公开报告AI搜索采集 ══')
        self._emit('  数据源: CISA Alerts | Check Point | Sysdig | '
                   'Trend Micro | MS | Cisco Talos | Mandiant')

        sources = create_osint_sources(self.db, self.ai)
        phase_results = {}

        for src in sources:
            if self._cancelled:
                break
            self.state.current_source = src.source_name
            self._emit(f'  [{src.source_name}] AI搜索中 (可信度: {src.confidence})...')
            try:
                result = src.fetch()
            except Exception as e:
                result = {'status': 'error', 'data': [], 'count': 0,
                          'summary': f'{src.source_name}: {e}', 'error': str(e)}
            phase_results[src.source_name] = result

            status = result.get('status', 'error')
            count = result.get('count', 0)
            self.state.source_details[src.source_name] = {
                'status': status, 'count': count,
                'summary': result.get('summary', ''),
                'type': src.source_type, 'confidence': src.confidence
            }

            if status == 'success':
                self.state.sources_completed.append(src.source_name)
                self.state.stats['osint_findings'] += count
                self._emit(f'  ✅ [{src.source_name}]: {count} 条情报发现')
            elif status == 'empty':
                self.state.sources_completed.append(src.source_name)
                self._emit(f'  ⚪ [{src.source_name}]: 无相关发现')
            else:
                self.state.sources_failed.append(src.source_name)
                self._emit(f'  ❌ [{src.source_name}]: {result.get("error", "搜索失败")}')

        self._emit(f'── Phase 2 完成: {self.state.stats["osint_findings"]} 条外部情报发现 ──')
        return phase_results

    # ── Phase 3: AI综合分析 ──

    def _run_phase3_ai_enrichment(self, phase1: Dict, phase2: Dict) -> Dict:
        self.state.phase = 'phase_3_ai_enrich'
        self.state.phase_label = 'Phase 3: AI综合分析'
        self._emit('══ Phase 3/3: AI综合分析中 ══')

        corpus = self._build_enriched_corpus(phase1, phase2)
        self._validate_corpus(corpus)
        self._seed_base_data()

        if self.ai and (corpus['summary']['total_cve_new'] > 0 or
                        self.state.stats['osint_findings'] > 0):
            self._emit('  [AI] 综合分析中 (交叉验证+去重+优先级排序)...')
            corpus = self._ai_enrich_corpus(corpus)

        self._emit(f'── Phase 3 完成: '
                   f'{corpus["summary"]["total_sources"]} 数据源, '
                   f'{corpus["summary"]["total_cve_new"]} 新增CVE, '
                   f'{corpus["summary"]["total_ioc"]} IOC ──')

        for warning in self.state.warnings[:5]:
            self._emit(f'  ⚠️ 数据预警: {warning}')

        return corpus

    def _build_enriched_corpus(self, phase1: Dict, phase2: Dict) -> Dict:
        nvd = phase1.get('NVD CVE', {})
        kev = phase1.get('CISA KEV', {})
        epss = phase1.get('EPSS', {})
        otx = phase1.get('AlienVault OTX', {})
        urlhaus = phase1.get('URLhaus', {})
        bazaar = phase1.get('MalwareBazaar', {})

        top_cves = sorted(
            nvd.get('data', []),
            key=lambda c: c.get('cvss_score') or 0, reverse=True
        )[:50]

        all_iocs = []
        for src_result in [otx, urlhaus, bazaar]:
            all_iocs.extend(src_result.get('data', []))

        osint_findings = []
        for name, result in phase2.items():
            for f in result.get('data', []):
                f['_source'] = name
            osint_findings.extend(result.get('data', []))

        corpus = {
            'collection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'top_cves': top_cves,
            'all_cves': nvd.get('data', []),
            'kev_entries': kev.get('data', []),
            'epss_scores': epss.get('data', []),
            'all_iocs': all_iocs,
            'osint_findings': osint_findings,
            'source_status': dict(self.state.source_details),
            'pipeline_warnings': list(self.state.warnings),
            'key_findings': list(self.state.key_findings),
            'summary': {
                'total_sources': len(self.state.source_details),
                'sources_success': len(self.state.sources_completed),
                'sources_empty': len(self.state.sources_empty),
                'sources_failed': len(self.state.sources_failed),
                'total_cve_new': nvd.get('count', 0),
                'total_cve_high_critical': nvd.get('high_critical_count', 0),
                'total_kev': kev.get('count', 0),
                'total_epss': epss.get('count', 0),
                'total_ioc': len(all_iocs),
                'total_osint_findings': self.state.stats['osint_findings'],
                'total_actors': self.state.stats['actor_total'],
            }
        }
        return corpus

    def _ai_enrich_corpus(self, corpus: Dict) -> Dict:
        if not self.ai:
            return corpus

        cve_summaries = []
        for c in corpus['top_cves'][:30]:
            cve_summaries.append(
                f"  {c['cve_id']} (CVSS {c.get('cvss_score','?')}, "
                f"{c.get('severity','?')}): {c.get('description','')[:120]}")

        osint_summaries = []
        for f in corpus['osint_findings'][:20]:
            osint_summaries.append(
                f"  [{f.get('_source','?')}] {f.get('title','')}: "
                f"{f.get('description','')[:150]}")

        prompt = f"""你是一名顶级威胁情报分析师。请基于以下采集数据进行AI增强分析。

## CVE数据（Top 30）
{chr(10).join(cve_summaries) if cve_summaries else '(无新数据)'}

## 外部情报发现
{chr(10).join(osint_summaries) if osint_summaries else '(无外部发现)'}

## 数据源状态
成功: {len(self.state.sources_completed)} | 空: {len(self.state.sources_empty)} | 失败: {len(self.state.sources_failed)}

请以JSON格式返回（不含markdown代码块）：
{{
  "cross_referenced_cves": [
    {{"cve_id": "CVE-xxxx-xxxxx", "actor": "APTxx", "target_industry": "金融/政府",
      "exploit_status": "活跃利用/概念验证/理论", "priority": "HIGH/MEDIUM/LOW",
      "patch_deadline": "YYYY-MM-DD"}}
  ],
  "key_narratives": ["发现1", "发现2"],
  "prioritized_actions": [
    {{"rank": 1, "action": "...", "cve": "CVE-xxxx", "deadline": "...", "rationale": "..."}}
  ],
  "trend_summary": "一句话趋势总结"
}}"""

        try:
            self._emit('  [AI] 正在分析...')
            raw = self.ai.query(
                user_message=prompt,
                system_prompt=(
                    "你是顶级威胁情报分析师。返回严格JSON，不编造数据。"
                    "如果输入数据不足，在相应字段标注'数据不足'。"
                ),
                max_turns=1, timeout=300
            )
            text = raw.strip()
            if '```' in text:
                start = (text.index('```json') + 7 if '```json' in text
                         else text.index('```') + 3)
                end = text.index('```', start)
                text = text[start:end].strip()
            ai_analysis = json.loads(
                text[text.find('{'):text.rfind('}') + 1])
            corpus['ai_analysis'] = ai_analysis
            for narrative in ai_analysis.get('key_narratives', [])[:5]:
                self.state.key_findings.append(f"[AI] {narrative}")
            self._emit(f'  [AI] 分析完成: '
                       f'{len(ai_analysis.get("cross_referenced_cves",[]))} 条CVE关联, '
                       f'{len(ai_analysis.get("prioritized_actions",[]))} 条优先行动')
        except Exception as e:
            logger.error(f"AI增强分析失败: {e}")
            self.state.warnings.append(f'AI增强分析失败: {e}')
            corpus['ai_analysis'] = None

        return corpus

    def _validate_corpus(self, corpus: Dict):
        s = corpus['summary']

        if s['total_cve_new'] > 0 and s['total_cve_high_critical'] == 0:
            actual_high = sum(
                1 for c in corpus['all_cves'] if (c.get('cvss_score') or 0) >= 7.0)
            if actual_high > 0:
                self.state.warnings.append(
                    f'数据一致性警告: {s["total_cve_new"]} 个CVE中有 {actual_high} 个CVSS>=7.0')

        ioc_sources = set(ioc.get('source', '') for ioc in corpus['all_iocs'])
        if len(ioc_sources) <= 1 and s['total_ioc'] > 0:
            self.state.warnings.append(f'IOC来源单一: 仅来自 {ioc_sources}')

        if s['sources_empty'] > 0:
            empty_names = ', '.join(self.state.sources_empty)
            self.state.warnings.append(f'数据源返回空: {empty_names}')

        if s['total_ioc'] == 0 and s['total_cve_new'] == 0 and s['total_kev'] == 0:
            self.state.warnings.append(
                '严重: 所有本地数据源均未获取到有效数据，请检查网络连接和API可用性')

    def _seed_base_data(self):
        if not self.db:
            return
        for a in _SEED_ACTORS:
            try:
                self.db.intel.add_threat_actor({
                    'name': a[0], 'aliases': a[1], 'motivation': a[2],
                    'target_sectors': a[3], 'known_tools': a[4],
                    'associated_cves': a[5], 'description': a[6],
                    'first_seen': a[7], 'last_seen': a[8]
                })
            except:
                pass
        for p in _SEED_ATTACK_PATTERNS:
            try:
                self.db.intel.add_attack_pattern({
                    'id': p[0], 'name': p[1], 'tactic': p[2],
                    'platform': p[3], 'description': p[4],
                    'mitigation': p[5], 'detection': p[6]
                })
            except:
                pass
        try:
            self.state.stats['actor_total'] = self.db.intel.conn.execute(
                'SELECT COUNT(*) FROM threat_actors').fetchone()[0]
            self.state.stats['pattern_total'] = self.db.intel.conn.execute(
                'SELECT COUNT(*) FROM attack_patterns').fetchone()[0]
        except:
            pass

    # ── 主入口 ──

    def run_pipeline(self, days=None, start_date=None, end_date=None) -> Dict:
        """运行完整的AI增强威胁情报采集流水线。

        Returns:
            向后兼容的 results dict (含 corpus, pipeline_state, warnings, key_findings)
        """
        self._cancelled = False
        self.state = PipelineState()
        self.state.start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self._emit('全球威胁情报采集流水线启动')
        self._emit(f'  时间范围: {start_date or "最近7天"} ~ {end_date or "今天"}')
        self._emit(f'  数据源: 6 本地API + 7 Web OSINT (AI增强)')

        phase1 = self._run_phase1_local(days=days, start_date=start_date,
                                        end_date=end_date)

        phase2 = {}
        if not self._cancelled:
            phase2 = self._run_phase2_osint()

        corpus = {}
        if not self._cancelled:
            corpus = self._run_phase3_ai_enrichment(phase1, phase2)

        self.state.end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.state.phase = 'complete'

        s = corpus.get('summary', {})
        self._emit(f'采集完成: {s.get("total_sources", 0)} 数据源, '
                   f'{s.get("total_cve_new", 0)} CVE, '
                   f'{s.get("total_ioc", 0)} IOC')

        return {
            'collection_time': corpus.get('collection_time', ''),
            'sources': {k: v.get('summary', '') for k, v in
                        self.state.source_details.items()},
            'total_cve': s.get('total_cve_new', 0),
            'total_kev': s.get('total_kev', 0),
            'total_epss': s.get('total_epss', 0),
            'total_ioc': s.get('total_ioc', 0),
            'total_threat_actors': s.get('total_actors', 0),
            'total_attack_patterns': self.state.stats.get('pattern_total', 0),
            'high_critical_cve': s.get('total_cve_high_critical', 0),
            'collection_log': [],
            'corpus': corpus,
            'pipeline_state': self.state.to_dict(),
            'warnings': list(self.state.warnings),
            'key_findings': list(self.state.key_findings),
        }


# ═══════════════════════════════════════════════════════════════════
# 数据驱动的屏幕摘要生成器 (替换硬编码"战略层/运营层/战术层")
# ═══════════════════════════════════════════════════════════════════

def generate_data_driven_summary(results: Dict) -> List[str]:
    """基于实际采集数据生成屏幕输出。"""
    lines = []
    s = results.get('corpus', {}).get('summary', {})

    lines.append('═' * 50)
    lines.append('  全球威胁情报采集完成')
    lines.append('═' * 50)
    lines.append(f'  采集时间: {results.get("collection_time", "N/A")}')
    lines.append('')

    lines.append('── 数据源状态 ──')
    source_details = results.get('corpus', {}).get('source_status', {})
    for name, detail in source_details.items():
        status = detail.get('status', 'error')
        count = detail.get('count', 0)
        conf = detail.get('confidence', '?')
        icon = {'success': '✅', 'partial': '⚠️', 'empty': '⚪'}.get(status, '❌')
        lines.append(f'  {icon} {name} [{conf}]: {count} 条')
    lines.append('')

    lines.append('── 统计摘要 ──')
    lines.append(f'  活跃利用漏洞(KEV): {s.get("total_kev", 0)} 条')
    lines.append(f'  本次新增CVE: {s.get("total_cve_new", 0)} 条 '
                 f'(高危/严重: {s.get("total_cve_high_critical", 0)})')
    lines.append(f'  EPSS评估: {s.get("total_epss", 0)} 条')
    lines.append(f'  威胁指标(IOC): {s.get("total_ioc", 0)} 个')
    lines.append(f'  威胁行为者: {s.get("total_actors", 0)} 个')
    lines.append(f'  外部情报发现: {s.get("total_osint_findings", 0)} 条')
    lines.append('')

    key_findings = results.get('key_findings', [])
    if key_findings:
        lines.append('── 关键发现 ──')
        for i, finding in enumerate(key_findings[:10], 1):
            lines.append(f'  [{i}] {finding}')
        lines.append('')

    ai_analysis = results.get('corpus', {}).get('ai_analysis')
    if ai_analysis:
        actions = ai_analysis.get('prioritized_actions', [])
        if actions:
            lines.append('── AI优先行动建议 ──')
            for action in actions[:5]:
                lines.append(f'  [{action["rank"]}] {action.get("action", "")} '
                             f'({action.get("cve", "")})')
            lines.append('')

    warnings = results.get('warnings', [])
    if warnings:
        lines.append('── 数据预警 ──')
        for w in warnings[:10]:
            lines.append(f'  ⚠️  {w}')
        lines.append('')

    lines.append('═' * 50)
    return lines
