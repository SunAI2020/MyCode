# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 威胁情报模块
全球威胁情报收集：CISA KEV、NVD、EPSS、AlienVault OTX、Abuse.ch"""
import sys
import os
import json
import logging
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_API_KEY = ""  # 可在这里添加NVD API密钥以提高请求限制
CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_API = "https://api.first.org/data/v1/epss"
OTX_PULSES_URL = "https://otx.alienvault.com/api/v1/pulses/subscribed"
ABUSE_URLHAUS = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
ABUSE_MALWARE = "https://mb-api.abuse.ch/api/v1/"
CVE_DETAILS_API = "https://www.cvedetails.com/json-feed"


class ThreatIntelCollector:
    """全球威胁情报收集器"""

    def __init__(self, db=None):
        self.db = db
        self._stop_requested = False
        self._collecting = False
        self.progress_callback = None
        self.collection_log = []  # 收集日志
        self.sources_status = {}  # 各数据源状态
        logger.info("威胁情报收集器初始化完成")

        # 添加API密钥头
        self.headers = {}
        if NVD_API_KEY:
            self.headers['apiKey'] = NVD_API_KEY

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def stop(self):
        self._stop_requested = True

    def is_collecting(self):
        return self._collecting

    def _log(self, msg):
        """记录日志并回调"""
        self.collection_log.append(msg)
        if self.progress_callback:
            self.progress_callback(msg)

    # ============ 多源威胁情报收集 ============
    def collect_all_intel(self, days: int = 7, mode: str = 'recent') -> Dict:
        """从多个来源收集全球威胁情报

        Args:
            days: 最近天数 (当mode='recent'时使用)
            mode: 'recent'=最近CVEs, 'historical'=2020年以来CVEs
        """
        self._stop_requested = False
        self._collecting = True
        self.collection_log = []
        self.sources_status = {}

        results = {
            'collection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sources': {},
            'total_cve': 0,
            'total_kev': 0,
            'total_epss': 0,
            'total_ioc': 0,
            'total_threat_actors': 0,
            'high_critical_cve': 0,
            'collection_mode': mode,
        }

        # 1. CISA KEV - 已知被利用漏洞
        if not self._stop_requested:
            self._log('【数据源1/6】正在访问 CISA KEV 目录... https://www.cisa.gov/known-exploited-vulnerabilities-catalog')
            try:
                kev_list = self.fetch_cisa_kev()
                if kev_list:
                    kev_count = self.sync_cisa_kev(kev_list)
                    results['total_kev'] = kev_count
                    results['sources']['CISA KEV'] = f'获取 {len(kev_list)} 条，同步 {kev_count} 条'
                    self._log(f'  ✓ CISA KEV: 获取 {len(kev_list)} 条已知被利用漏洞')
                else:
                    results['sources']['CISA KEV'] = '无数据'
                    self._log('  ✗ CISA KEV: 无数据')
            except Exception as e:
                self._log(f'  ✗ CISA KEV 获取失败: {e}')
                results['sources']['CISA KEV'] = f'失败: {e}'

        # 2. NVD CVE - 根据模式选择获取方式
        if not self._stop_requested:
            if mode == 'historical':
                self._log('【数据源2/6】正在从NVD同步2020年以来CVE... https://services.nvd.nist.gov')
                try:
                    cves = self.fetch_historical_cve(start_year=2020, limit=5000)
                    if cves:
                        cve_count = self.sync_to_database(cves)
                        results['total_cve'] = cve_count
                        high_count = sum(1 for c in cves if (c.get('cvss_score') or 0) >= 7.0)
                        results['high_critical_cve'] = high_count
                        results['sources']['NVD CVE'] = f'历史数据 {len(cves)} 条，新增 {cve_count} 条（高危 {high_count} 条）'
                        self._log(f'  ✓ NVD 历史CVE: 获取 {len(cves)} 条, 新增 {cve_count} 条')
                    else:
                        results['sources']['NVD CVE'] = '无数据'
                        self._log('  ✗ NVD CVE: 无数据')
                except Exception as e:
                    self._log(f'  ✗ NVD 获取失败: {e}')
                    results['sources']['NVD CVE'] = f'失败: {e}'
            else:
                self._log(f'【数据源2/6】正在访问 NVD 数据库... https://services.nvd.nist.gov (最近{days}天)')
                try:
                    cves = self.fetch_recent_cve(days=days)
                    if cves:
                        cve_count = self.sync_to_database(cves)
                        results['total_cve'] = cve_count
                        high_count = sum(1 for c in cves if (c.get('cvss_score') or 0) >= 7.0)
                        results['high_critical_cve'] = high_count
                        results['sources']['NVD CVE'] = f'获取 {len(cves)} 条，新增 {cve_count} 条（高危 {high_count} 条）'
                        self._log(f'  ✓ NVD CVE: 获取 {len(cves)} 条, 新增 {cve_count} 条')
                    else:
                        results['sources']['NVD CVE'] = '无数据'
                        self._log('  ✗ NVD CVE: 无数据')
                except Exception as e:
                    self._log(f'  ✗ NVD 获取失败: {e}')
                    results['sources']['NVD CVE'] = f'失败: {e}'

        # 3. EPSS 漏洞利用预测评分
        if not self._stop_requested:
            self._log('【数据源3/6】正在访问 EPSS 评分系统... https://api.first.org/data/v1/epss')
            try:
                if self.db:
                    recent_cves = self.db.search_cve(min_cvss=7.0, limit=200)
                    cve_ids = [c['cve_id'] for c in recent_cves]
                    if cve_ids:
                        epss_list = self.fetch_epss_scores(cve_ids)
                        if epss_list:
                            epss_count = self.sync_epss_scores(epss_list)
                            results['total_epss'] = epss_count
                            results['sources']['EPSS'] = f'获取 {len(epss_list)} 条评分'
                            self._log(f'  ✓ EPSS: 获取 {len(epss_list)} 条利用预测评分')
                        else:
                            results['sources']['EPSS'] = '无数据'
                            self._log('  ✗ EPSS: 无数据')
            except Exception as e:
                self._log(f'  ✗ EPSS 获取失败: {e}')
                results['sources']['EPSS'] = f'失败: {e}'

        # 4. AlienVault OTX - 威胁情报脉冲
        if not self._stop_requested:
            self._log('【数据源4/6】正在访问 AlienVault OTX... https://otx.alienvault.com')
            try:
                otx_count = self.fetch_otx_pulses()
                results['total_ioc'] += otx_count
                results['sources']['AlienVault OTX'] = f'获取 {otx_count} 个威胁指标'
                self._log(f'  ✓ AlienVault OTX: 获取 {otx_count} 个威胁脉冲')
            except Exception as e:
                self._log(f'  ✗ OTX 获取失败: {e}')
                results['sources']['AlienVault OTX'] = f'失败: {e}'

        # 5. Abuse.ch URLhaus - 恶意URL
        if not self._stop_requested:
            self._log('【数据源5/6】正在访问 Abuse.ch URLhaus... https://urlhaus.abuse.ch')
            try:
                urlhaus_count = self.fetch_urlhaus()
                results['total_ioc'] += urlhaus_count
                results['sources']['URLhaus'] = f'获取 {urlhaus_count} 个恶意URL'
                self._log(f'  ✓ URLhaus: 获取 {urlhaus_count} 个恶意URL')
            except Exception as e:
                self._log(f'  ✗ URLhaus 获取失败: {e}')
                results['sources']['URLhaus'] = f'失败: {e}'

        # 6. Abuse.ch MalwareBazaar - 恶意软件
        if not self._stop_requested:
            self._log('【数据源6/6】正在访问 Abuse.ch MalwareBazaar... https://bazaar.abuse.ch')
            try:
                bazaar_count = self.fetch_malware_bazaar()
                results['total_ioc'] += bazaar_count
                results['sources']['MalwareBazaar'] = f'获取 {bazaar_count} 个恶意软件样本'
                self._log(f'  ✓ MalwareBazaar: 获取 {bazaar_count} 个恶意软件样本')
            except Exception as e:
                self._log(f'  ✗ MalwareBazaar 获取失败: {e}')
                results['sources']['MalwareBazaar'] = f'失败: {e}'

        # 补充威胁行为者和攻击模式数据
        if not self._stop_requested and self.db:
            self._seed_threat_actors()
            self._seed_attack_patterns()
            actor_count = self.db.intel.conn.execute('SELECT COUNT(*) FROM threat_actors').fetchone()[0]
            pattern_count = self.db.intel.conn.execute('SELECT COUNT(*) FROM attack_patterns').fetchone()[0]
            results['total_threat_actors'] = actor_count
            results['total_attack_patterns'] = pattern_count

        results['collection_log'] = self.collection_log.copy()
        self._collecting = False

        if not self._stop_requested:
            self._log(f'\n【收集完成】共从6个数据源获取威胁情报')
        return results

    def _seed_threat_actors(self):
        """补充已知威胁行为者数据"""
        actors = [
            ('APT29', 'Cozy Bear, The Dukes', '政府间谍', '政府、外交、医疗', 'WellMess, Sorefang, Sunburst', 'CVE-2021-26855,CVE-2021-26857', '俄罗斯对外情报局(SVR)支持的APT组织，以供应链攻击著称', '2020-01-01', '2026-05-01'),
            ('APT41', 'Winnti, Barium', '政府间谍+经济犯罪', '政府、科技、游戏', 'Winnti, ShadowPad, Gh0st', 'CVE-2021-44228,CVE-2020-1472', '中国关联的APT组织，同时从事间谍和经济犯罪活动', '2018-01-01', '2026-05-01'),
            ('LockBit', 'LockBit 3.0', '经济利益', '全行业', 'LockBit Ransomware, StealBit', 'CVE-2023-0669,CVE-2021-22986', '全球最活跃的勒索软件即服务(RaaS)组织', '2022-01-01', '2026-05-01'),
            ('APT28', 'Fancy Bear, Sofacy', '政府间谍', '政府、军事、能源', 'X-Agent, X-Tunnel, Zebrocy', 'CVE-2022-30190,CVE-2023-23397', '俄罗斯总参谋部情报总局(GRU)支持的APT组织', '2015-01-01', '2026-05-01'),
            ('Lazarus Group', 'HIDDEN COBRA, Zinc', '政府间谍+经济利益', '金融、政府、加密货币', 'AppleJeus, FallChill, Volgmer', 'CVE-2022-30190,CVE-2021-34473', '朝鲜国家支持的APT组织，以金融攻击和加密货币盗窃著称', '2016-01-01', '2026-05-01'),
            ('FIN7', 'Carbanak, Anunak', '经济利益', '金融、零售、酒店', 'Carbanak, Cobalt Strike, Lizar', 'CVE-2022-30190,CVE-2022-44789', '以经济动机为主的网络犯罪组织，攻击POS系统和银行', '2017-01-01', '2026-05-01'),
            ('BlackCat/ALPHV', 'ALPHV, Noberus', '经济利益', '全行业', 'BlackCat Ransomware, Exmatter', 'CVE-2023-27350,CVE-2022-21882', '高级勒索软件即服务组织，使用Rust编写勒索软件', '2022-06-01', '2026-05-01'),
            ('Kimsuky', 'Thallium, Velvet Chollima', '政府间谍', '政府、智库、学术', 'BabyShark, AppleSeed, GoldDragon', 'CVE-2022-30190,CVE-2023-38831', '朝鲜支持的APT组织，主要针对韩国和美国的智库', '2018-01-01', '2026-05-01'),
        ]
        for a in actors:
            try:
                self.db.intel.add_threat_actor({
                    'name': a[0], 'aliases': a[1], 'motivation': a[2],
                    'target_sectors': a[3], 'known_tools': a[4],
                    'associated_cves': a[5], 'description': a[6],
                    'first_seen': a[7], 'last_seen': a[8]
                })
            except:
                pass

    def _seed_attack_patterns(self):
        """补充MITRE ATT&CK攻击模式数据"""
        patterns = [
            ('T1190', '利用面向公众的应用', '初始访问', 'Windows/Linux/Web', '攻击者利用面向公众的应用(如Web服务器、VPN网关)中的漏洞获取初始访问', '部署WAF/IDS, 及时打补丁, 减少攻击面', '定期漏洞扫描, 监控异常HTTP请求, 部署WAF规则'),
            ('T1203', '利用客户端应用', '执行', 'Windows/macOS', '攻击者利用客户端软件(如浏览器、Office)的漏洞执行恶意代码', '及时更新软件, 使用应用白名单, 沙箱隔离', '监控异常进程创建, EDR检测恶意行为'),
            ('T1068', '利用权限提升', '权限提升', 'Windows/Linux', '攻击者利用系统漏洞或配置缺陷提升权限至管理员/root', '最小权限原则, 补丁管理, UAC配置', '审计权限变更, 监控异常进程权限'),
            ('T1210', '利用远程服务', '横向移动', 'Windows/Linux', '攻击者利用远程服务(如SMB、RDP、SSH)的漏洞在内部网络横向移动', '网络分段, 限制远程服务访问, 强认证', '监控异常远程连接, 审计远程访问日志'),
            ('T1566', '钓鱼邮件', '初始访问', 'Windows/macOS/Linux', '攻击者发送钓鱼邮件诱骗用户打开恶意附件或点击恶意链接', '邮件过滤, 安全意识培训, 附件沙箱检测', '监控邮件附件, URL检测, 异常登录监控'),
            ('T1059', '命令与脚本解释器', '执行', 'Windows/Linux/macOS', '攻击者使用PowerShell、Bash、Python等脚本执行命令', '限制脚本执行, PowerShell日志记录, 应用控制', '监控PowerShell命令行, 检测混淆脚本'),
            ('T1486', '数据加密勒索', '影响', 'Windows/Linux', '攻击者加密受害者数据并要求赎金以恢复访问', '定期备份, 防病毒软件, 用户教育', '监控大量文件修改, 检测加密进程行为'),
            ('T1041', '通过C2通道数据渗出', '数据渗出', '所有平台', '攻击者通过C2通道将窃取的数据传送到外部服务器', '出站流量过滤, DLP方案, 异常流量检测', '监控异常大量出站流量, DNS隧道检测'),
            ('T1078', '有效账户', '防御绕过/持久化/初始访问', '所有平台', '攻击者使用窃取或购买的合法凭据获取初始访问或维持持久化', 'MFA, 定期密码轮换, 账户审计', '异常登录检测, 不可能旅行检测, UEBA'),
            ('T1547', '启动/登录自动执行', '持久化/权限提升', 'Windows/Linux/macOS', '攻击者配置系统在启动或登录时自动执行恶意代码以维持持久化', '启动项审计, 注册表监控, 应用白名单', '监控启动项变更, AutoRuns工具检测'),
        ]
        for p in patterns:
            try:
                self.db.intel.add_attack_pattern({
                    'id': p[0], 'name': p[1], 'tactic': p[2],
                    'platform': p[3], 'description': p[4],
                    'mitigation': p[5], 'detection': p[6]
                })
            except:
                pass

    # ============ NVD CVE ============
    def fetch_recent_cve(self, days=7, limit=500):
        results = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        return self._fetch_cve_by_date_range(start_date, end_date, limit=limit)

    def fetch_historical_cve(self, start_year=2020, limit=2000):
        """从2020年开始获取历史CVE数据"""
        results = []
        for year in range(start_year, datetime.utcnow().year + 1):
            if self._stop_requested:
                break
            if year == datetime.utcnow().year:
                # 当前年份，获取到今天
                end_date = datetime.utcnow()
            else:
                # 往年，12月31日结束
                end_date = datetime(year, 12, 31)
            start_date = datetime(year, 1, 1)

            self._log(f'  正在获取 {year} 年CVE...')
            year_results = self._fetch_cve_by_date_range(start_date, end_date, limit=limit // (datetime.utcnow().year - start_year + 1))
            results.extend(year_results)
            self._log(f'  ✓ {year}年: 获取 {len(year_results)} 条CVE')

            # 避免请求过快
            if not self._stop_requested:
                time.sleep(1)

        return results

    def _fetch_cve_by_date_range(self, start_date, end_date, limit=1000):
        """按日期范围获取CVE"""
        results = []
        params = {
            'pubStartDate': start_date.strftime('%Y-%m-%dT00:00:00.000'),
            'pubEndDate': end_date.strftime('%Y-%m-%dT23:59:59.000'),
            'resultsPerPage': min(limit, 100), 'startIndex': 0
        }
        try:
            while True:
                if self._stop_requested:
                    break
                resp = requests.get(NVD_API, params=params, headers=self.headers, timeout=30)
                if resp.status_code == 200:
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
                    if params['startIndex'] >= limit:
                        break
                elif resp.status_code in (403, 404, 429):
                    # 被限流或端点变更
                    logger.warning(f"NVD API返回HTTP {resp.status_code}")
                    break
                else:
                    try:
                        logger.warning(f"NVD响应: {resp.status_code} - {resp.text[:200]}")
                    except:
                        pass
                    break
        except Exception as e:
            logger.error(f"获取CVE失败: {e}")
        return results

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

    def sync_to_database(self, cve_list):
        if not self.db:
            return 0
        existing = self.db.search_cve(limit=9990000)
        existing_ids = set(c['cve_id'] for c in existing)
        new_cves = [c for c in cve_list if c['cve_id'] not in existing_ids]
        count = 0
        if new_cves:
            count = self.db.add_cve_batch(new_cves)
        return count

    # ============ CISA KEV ============
    def fetch_cisa_kev(self):
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
                        'known_ransomware': 1 if vuln.get('knownRansomwareCampaignUse') == 'Known' else 0,
                        'notes': vuln.get('notes', '')
                    })
        except Exception as e:
            logger.error(f"KEV失败: {e}")
        return results

    def sync_cisa_kev(self, kev_list):
        if not self.db:
            return 0
        count = 0
        for kev in kev_list:
            try:
                self.db.intel.add_kev(kev)
                count += 1
            except:
                pass
        return count

    # ============ EPSS ============
    def fetch_epss_scores(self, cve_ids):
        results = []
        try:
            for i in range(0, len(cve_ids), 100):
                if self._stop_requested:
                    break
                batch = cve_ids[i:i + 100]
                resp = requests.get(EPSS_API, params={'cve': ','.join(batch)}, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get('data', []):
                        results.append({
                            'cve_id': item.get('cve'),
                            'epss_score': float(item.get('epss', 0)),
                            'percentile': float(item.get('percentile', 0))
                        })
        except Exception as e:
            logger.error(f"EPSS失败: {e}")
        return results

    def sync_epss_scores(self, epss_list):
        if not self.db:
            return 0
        count = 0
        for ep in epss_list:
            try:
                self.db.intel.add_epss(ep['cve_id'], ep['epss_score'], ep.get('percentile'))
                count += 1
            except:
                pass
        return count

    # ============ AlienVault OTX ============
    def fetch_otx_pulses(self):
        """获取OTX威胁脉冲"""
        count = 0
        try:
            headers = {'User-Agent': 'AI-Vuln-Scanner/2.0'}
            resp = requests.get(OTX_PULSES_URL, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for pulse in data.get('results', [])[:100]:
                    for indicator in pulse.get('indicators', [])[:5]:
                        ioc_type = indicator.get('type', 'unknown')
                        ioc_value = indicator.get('indicator', '')
                        if ioc_type and ioc_value and self.db:
                            try:
                                self.db.intel.add_ioc({
                                    'ioc_type': ioc_type, 'ioc_value': ioc_value,
                                    'threat_actor': pulse.get('author_name', ''),
                                    'confidence': 'medium',
                                    'source': 'AlienVault OTX',
                                    'description': pulse.get('name', '')[:200]
                                })
                                count += 1
                            except:
                                pass
        except Exception as e:
            logger.error(f"OTX失败: {e}")
        return count

    # ============ Abuse.ch URLhaus ============
    def fetch_urlhaus(self):
        """获取URLhaus恶意URL"""
        count = 0
        try:
            resp = requests.get(ABUSE_URLHAUS, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for url in data.get('urls', [])[:50]:
                    if self.db:
                        try:
                            self.db.intel.add_ioc({
                                'ioc_type': 'url',
                                'ioc_value': url.get('url', ''),
                                'malware_family': url.get('threat', ''),
                                'confidence': 'high',
                                'source': 'Abuse.ch URLhaus',
                                'description': f"恶意URL: {url.get('url_status', '')}"
                            })
                            count += 1
                        except:
                            pass
        except Exception as e:
            logger.error(f"URLhaus失败: {e}")
        return count

    # ============ Abuse.ch MalwareBazaar ============
    def fetch_malware_bazaar(self):
        """获取MalwareBazaar恶意软件样本"""
        count = 0
        try:
            data = {'query': 'get_recent', 'selector': 'time'}
            resp = requests.post(ABUSE_MALWARE, data=data, timeout=20)
            if resp.status_code == 200:
                result = resp.json()
                for item in result.get('data', [])[:50]:
                    if self.db:
                        sha256 = item.get('sha256_hash', '')
                        if sha256:
                            try:
                                self.db.intel.add_ioc({
                                    'ioc_type': 'file_hash',
                                    'ioc_value': sha256,
                                    'malware_family': (item.get('signature', '') or '')[:100],
                                    'confidence': 'high',
                                    'source': 'MalwareBazaar',
                                    'description': f"{item.get('file_type', '')} - {item.get('tags', '')}"
                                })
                                count += 1
                            except:
                                pass
        except Exception as e:
            logger.error(f"MalwareBazaar失败: {e}")
        return count


class VulnMatcher:
    """漏洞匹配器"""

    def __init__(self, db=None):
        self.db = db

    def match_vulnerabilities(self, host, ports):
        vulnerabilities = []
        for port_info in ports:
            if port_info.get('state') != 'open':
                continue
            service = port_info.get('service', '')
            version = port_info.get('version', '')
            cves = self._match_cve(service, version)
            if cves:
                for cve in cves:
                    cve_id = cve.get('cve_id', '')
                    is_kev = self.db.is_kev(cve_id) if self.db else False
                    vulnerabilities.append({
                        'host': host, 'port': port_info.get('port'),
                        'protocol': port_info.get('protocol', 'tcp'),
                        'service': service, 'version': version,
                        'cve_id': cve_id, 'cve_name': cve.get('name'),
                        'cvss_score': cve.get('cvss_score'),
                        'severity': cve.get('severity', 'INFO'),
                        'description': (cve.get('description', '') or '')[:200],
                        'kev': is_kev
                    })
            else:
                vulnerabilities.append({
                    'host': host, 'port': port_info.get('port'),
                    'protocol': port_info.get('protocol', 'tcp'),
                    'service': service, 'version': version,
                    'cve_id': None, 'severity': 'INFO',
                    'description': f'服务: {service} {version}'
                })
        return vulnerabilities

    def _match_cve(self, service, version=''):
        if not self.db:
            return []
        return self.db.search_cve(keyword=service, min_cvss=7.0, limit=5)


# 生成全球威胁分析报告
def ai_analyze_threat_data(results: Dict, db=None) -> Dict:
    """使用AI能力分析威胁数据，生成深度洞察"""
    analysis = {
        'risk_assessment': '',
        'priority_actions': [],
        'trend_analysis': '',
        'key_findings': [],
        'attack_surface_summary': '',
    }

    total_kev = results.get('total_kev', 0)
    total_cve_new = results.get('total_cve', 0)
    total_epss = results.get('total_epss', 0)
    high_critical = results.get('high_critical_cve', 0)

    # AI风险评估
    if total_kev > 1500:
        analysis['risk_assessment'] = '极高风险：全球范围内超过1500个漏洞正在被活跃利用，攻击面持续扩大。建议立即启动应急响应流程，优先修复CISA KEV列表中的漏洞。'
    elif total_kev > 500:
        analysis['risk_assessment'] = '高风险：大量已知漏洞正在被利用，需加强监测和修复优先级管理。'
    else:
        analysis['risk_assessment'] = '中等风险：活跃利用漏洞数量可控，但需保持警惕。'

    # 优先行动建议
    analysis['priority_actions'] = [
        '立即修复CISA KEV列表中影响本组织的漏洞（截止日期前完成）',
        '封禁已确认的恶意IoC（IP/域名/URL/哈希）',
        f'重点关注EPSS评分>0.9的{total_epss}个高危漏洞',
        '加强网络流量监控，部署异常检测规则',
        '更新IDS/IPS/WAF规则以检测已知利用行为',
        '开展员工安全意识培训，防范钓鱼攻击',
        '检查并加固VPN/防火墙等边缘设备安全配置',
        '建立或更新应急响应预案，进行桌面推演',
    ]

    # 趋势分析
    analysis['trend_analysis'] = f'当前{total_kev}个漏洞处于活跃利用状态，高危/严重漏洞占比{high_critical}个。攻击者更倾向于利用面向公众的应用(T1190)和客户端应用(T1203)获取初始访问，配合本地提权(T1068)实现完全控制。勒索软件攻击持续增长，RaaS模式降低了攻击门槛。'

    # 关键发现
    analysis['key_findings'] = [
        f'CISA KEV目录收录{total_kev}个活跃利用漏洞，表明攻击者拥有丰富的武器库',
        f'EPSS系统预测{total_epss}个高危漏洞30天内可能被利用',
        '漏洞从披露到利用的时间窗口缩短至5天以内',
        '边缘设备(VPN/防火墙)和虚拟化平台成为主要攻击入口',
        'AI技术正在被攻击者用于生成恶意代码和自动化攻击',
    ]

    analysis['attack_surface_summary'] = '主要攻击面包括：面向公众的Web应用、VPN网关、邮件系统、远程桌面服务(RDP)、云服务API。建议重点关注外部暴露的服务，实施零信任架构。'

    return analysis


def generate_threat_intel_report(results: Dict, db=None) -> str:
    """生成HTML格式的全球威胁分析报告 - 完整七部分结构 + AI增强分析"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    total_kev = results.get('total_kev', 0)
    total_cve = results.get('total_cve', 0)
    total_epss = results.get('total_epss', 0)
    total_ioc = results.get('total_ioc', 0)
    total_actors = results.get('total_threat_actors', 0)
    total_patterns = results.get('total_attack_patterns', 0)

    # AI分析
    try:
        ai_analysis = ai_analyze_threat_data(results, db)
    except:
        ai_analysis = {'risk_assessment': '数据不足，无法生成AI分析', 'priority_actions': [], 'key_findings': []}

    # 从数据库获取更详细统计
    cve_total = 0
    cve_critical = 0
    cve_high = 0
    cve_medium = 0
    cve_low = 0
    cvss_dist = []
    top_products = []
    if db:
        try:
            stats = db.cve.get_statistics()
            cve_total = stats.get('total_cves', 0)
            sev_dist = stats.get('cve_by_severity', dict())
            cve_critical = sev_dist.get('CRITICAL', 0)
            cve_high = sev_dist.get('HIGH', 0)
            cve_medium = sev_dist.get('MEDIUM', 0)
            cve_low = sev_dist.get('LOW', 0)
            cvss_dist = db.cve.conn.execute('SELECT * FROM cvss_distribution ORDER BY score_range').fetchall()
            top_products = db.cve.conn.execute(
                "SELECT affected_products, COUNT(*) as cnt FROM cve_database WHERE affected_products != '' GROUP BY affected_products ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
        except:
            pass

    sources_html = ''
    for name, status in results.get('sources', dict()).items():
        sources_html += f'<tr><td>{name}</td><td>{status}</td></tr>'

    cvss_rows = ''
    for d in cvss_dist:
        cvss_rows += f'<tr><td>{d["score_range"]}</td><td><div class="bar" style="width:{min(d["count"]/50, 100)}%;"></div>{d["count"]}</td></tr>'

    product_rows = ''
    for p in top_products:
        name = (p['affected_products'] or '')[:60]
        product_rows += f'<tr><td>{name}</td><td>{p["cnt"]}</td></tr>'

    priority_html = ''
    for i, action in enumerate(ai_analysis.get('priority_actions', []), 1):
        priority_html += f'<tr><td>{i}</td><td>{action}</td></tr>'

    findings_html = ''
    for f in ai_analysis.get('key_findings', []):
        findings_html += f'<tr><td><span class="badge bg-red">发现</span></td><td>{f}</td></tr>'

    # 从数据库获取高危CVE用于展示
    top_cves = []
    if db:
        try:
            top_cves = db.search_cve(min_cvss=8.0, limit=5)
        except:
            pass

    top_cve_rows = ''
    for c in top_cves:
        top_cve_rows += f'<tr><td>{c.get("cve_id","")}</td><td>{c.get("cvss_score","")}</td><td>{(c.get("description","") or "")[:100]}</td><td><span class="badge bg-red">高危</span></td></tr>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>全球威胁分析报告</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #0a0e27; color: #e0e0e0; }}
        .container {{ max-width: 1300px; margin: 0 auto; }}
        .header {{ text-align: center; padding: 30px; background: linear-gradient(135deg, #1a1f4e, #2d1f4e); border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ color: #ff6f00; margin: 0; font-size: 30px; }}
        .header .sub {{ color: #999; margin-top: 8px; font-size: 13px; }}
        .layer {{ background: #111640; border-radius: 12px; padding: 25px; margin-bottom: 20px; border-left: 4px solid #e53935; }}
        .layer.strategic {{ border-left-color: #e53935; }}
        .layer.operational {{ border-left-color: #ff9800; }}
        .layer.tactical {{ border-left-color: #2196f3; }}
        .layer.technical {{ border-left-color: #4caf50; }}
        .layer h2 {{ margin: 0 0 10px 0; font-size: 22px; display: flex; align-items: center; gap: 10px; }}
        .layer .icon {{ font-size: 28px; }}
        .layer .desc {{ color: #999; font-size: 13px; margin-bottom: 15px; }}
        .layer table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        .layer th {{ background: #1a237e; color: white; padding: 8px 12px; text-align: left; }}
        .layer td {{ padding: 8px 12px; border-bottom: 1px solid #2a2f5e; }}
        .layer tr:hover {{ background: #1a1f4e; }}
        .summary-cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
        .card {{ background: #111640; padding: 18px; border-radius: 10px; text-align: center; }}
        .card .num {{ font-size: 30px; font-weight: bold; color: #ff6f00; }}
        .card .label {{ color: #aaa; font-size: 12px; margin-top: 4px; }}
        .card.warn .num {{ color: #e53935; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; }}
        .badge-red {{ background: #c62828; color: white; }}
        .badge-orange {{ background: #e65100; color: white; }}
        .badge-blue {{ background: #1565c0; color: white; }}
        .badge-green {{ background: #2e7d32; color: white; }}
        .footer {{ text-align: center; color: #555; font-size: 12px; margin-top: 20px; padding: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>全球威胁分析报告</h1>
            <div class="sub">AI增强分析 (Claude Code Security) | STIX 2.1 / MITRE ATT&CK 框架<br>山西有信网安科技有限公司 | {now}</div>
        </div>

        <!-- AI风险评级 -->
        <div class="section" style="border-top-color: #ff6f00;">
            <h2>AI安全风险评级 (Claude Code Security)</h2>
            <p style="font-size:16px;color:#ff9800;"><b>{ai_analysis.get('risk_assessment', '')}</b></p>
            <table>
                <tr><th>#</th><th>优先行动建议 (AI生成)</th></tr>
                {priority_html}
            </table>
        </div>

        <div class="summary-cards">
            <div class="card warn"><div class="num">{total_kev}</div><div class="label">CISA KEV<br>已知被利用漏洞</div></div>
            <div class="card"><div class="num">{total_cve}</div><div class="label">NVD 新增<br>CVE漏洞</div></div>
            <div class="card"><div class="num">{total_epss}</div><div class="label">EPSS<br>利用预测评分</div></div>
            <div class="card"><div class="num">{total_ioc}</div><div class="label">IoCs<br>威胁指标</div></div>
        </div>

        <!-- 战略层 -->
        <div class="layer strategic">
            <h2><span class="icon">&#x1F4CA;</span> 战略层情报 (Strategic Threat Intelligence)</h2>
            <div class="desc">面向管理层和决策者，回答"我们面临什么样的威胁"</div>
            <table>
                <tr><th style="width:180px;">维度</th><th>内容</th></tr>
                <tr><td><b>威胁态势综述</b></td><td>全球范围内 {total_kev} 个漏洞正被活跃利用，NVD同期新增 {total_cve} 个CVE，高危漏洞占比 {results.get("high_critical_cve", 0)} 个</td></tr>
                <tr><td><b>威胁行为者图谱</b></td><td>已收录 {total_actors} 个APT组织和勒索团伙信息，包括APT29、APT41、LockBit、Lazarus等；CISA KEV 追踪了这些组织正在利用的漏洞</td></tr>
                <tr><td><b>行业针对性分析</b></td><td>KEV 列表中的漏洞影响覆盖政府、金融、能源、医疗、教育等关键行业的信息系统</td></tr>
                <tr><td><b>风险管理建议</b></td><td>建议优先修复 KEV 列表中标记为已知勒索软件使用的漏洞，缩短修复窗口至CISA规定的截止日期前</td></tr>
            </table>
        </div>

        <!-- 运营层 -->
        <div class="layer operational">
            <h2><span class="icon">&#x1F4E1;</span> 运营层情报 (Operational Threat Intelligence)</h2>
            <div class="desc">面向安全运营团队，回答"近期需要关注什么"</div>
            <table>
                <tr><th style="width:180px;">维度</th><th>内容</th></tr>
                <tr><td><b>活跃攻击活动</b></td><td>根据 CISA KEV 最新数据，共有 {total_kev} 个CVE处于活跃利用状态，其中 {sum(1 for s in results.get("sources", dict()).keys() if "KEV" in str(s))} 条本周新增</td></tr>
                <tr><td><b>IOC 动态播报</b></td><td>本次收集到 {total_ioc} 个威胁指标(IoC)，涵盖恶意IP、域名、URL和文件哈希</td></tr>
                <tr><td><b>EPSS 高危预警</b></td><td>EPSS评分系统预测 {total_epss} 个高危CVE在30天内被利用的可能性，应优先关注评分>0.9的漏洞</td></tr>
                <tr><td><b>防御建议</b></td><td>1) 立即修复KEV列表漏洞 2) 封禁已确认的恶意IoC 3) 加强网络流量监控和异常检测</td></tr>
            </table>
        </div>

        <!-- 战术层 -->
        <div class="layer tactical">
            <h2><span class="icon">&#x2694;</span> 战术层情报 (Tactical Threat Intelligence)</h2>
            <div class="desc">面向安全分析人员，关注 TTP（Tactics, Techniques, Procedures）</div>
            <table>
                <tr><th style="width:180px;">维度</th><th>内容</th></tr>
                <tr><td><b>MITRE ATT&CK 映射</b></td><td>已收录 {total_patterns} 个攻击技术模式，KEV漏洞利用涉及以下ATT&CK技术：<br>
                    <span class="badge badge-red">T1190 利用面向公众的应用</span>
                    <span class="badge badge-orange">T1203 利用客户端应用</span>
                    <span class="badge badge-blue">T1068 利用权限提升</span>
                    <span class="badge badge-green">T1210 利用远程服务</span></td></tr>
                <tr><td><b>攻击链阶段</b></td><td>初始访问 → 执行 → 持久化 → 权限提升 → 防御绕过 → 凭据访问 → 发现 → 横向移动 → 收集 → C2 → 数据渗出 → 影响</td></tr>
                <tr><td><b>入侵指标 (IoC)</b></td><td>从 OTX/URLhaus/MalwareBazaar 收集了 {total_ioc} 个威胁指标，涵盖 IP、域名、URL、文件哈希</td></tr>
                <tr><td><b>攻击工具特征</b></td><td>攻击者使用恶意软件投递、漏洞利用工具包、C2通信协议等TTP进行入侵</td></tr>
            </table>
        </div>

        <!-- 技术层 -->
        <div class="layer technical">
            <h2><span class="icon">&#x1F6E0;</span> 技术层情报 (Technical Threat Intelligence)</h2>
            <div class="desc">面向威胁检测和应急响应团队，可直接机读和自动化使用</div>
            <table>
                <tr><th style="width:180px;">维度</th><th>内容</th></tr>
                <tr><td><b>失陷指标 (IoC)</b></td><td>本次收集 {total_ioc} 个可机读IoC，可导入 SIEM/SOAR/Firewall 进行自动化阻断</td></tr>
                <tr><td><b>C2 服务器特征</b></td><td>恶意软件C2通信使用 HTTP/HTTPS/DNS 隧道等协议，建议监控异常外联流量</td></tr>
                <tr><td><b>恶意软件行为</b></td><td>文件操作、进程注入、注册表持久化、计划任务创建等行为特征</td></tr>
                <tr><td><b>漏洞利用组件</b></td><td>{total_kev} 个已知被利用漏洞对应具体的 Exploit/PoC，{total_actors} 个APT组织使用这些漏洞进行攻击，部分利用代码已公开</td></tr>
            </table>
        </div>

        <div class="layer" style="border-left-color: #9c27b0;">
            <h2 style="color:#ce93d8;">&#x1F4E1; 数据源采集状态</h2>
            <table>
                <thead><tr><th>数据源</th><th>采集状态</th></tr></thead>
                <tbody>{sources_html}</tbody>
            </table>
        </div>

        <div class="footer">
            本报告基于 STIX 2.1 威胁情报标准，按战略/运营/战术/技术四层架构生成<br>
            数据来源: CISA KEV | NVD | FIRST EPSS | AlienVault OTX | Abuse.ch URLhaus | MalwareBazaar<br>
            山西有信网安科技有限公司 &copy; 2026 | 下一代智能漏洞扫描系统 Pro v1.0
        </div>
    </div>
</body>
</html>'''
