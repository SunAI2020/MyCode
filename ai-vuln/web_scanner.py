# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - Web 应用安全扫描模块

包含：Web 指纹识别（CMS/框架/中间件）、自定义 HTTP 请求探测、
目录枚举 + 备份文件检测、OWASP ZAP 被动扫描集成。
"""
import re
import time
import logging
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from web_vuln_scanner import WebVulnScanner, ScanStopped

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _verify_for_url(url: str) -> bool:
    """按目标归属决定 TLS 证书校验：公网强制校验，内网关闭。

    复用 ssrf_guard 的地址归属判定；导入失败时回退到不校验（旧行为），
    避免因加固引入的依赖把扫描功能整个打挂。
    """
    try:
        from ssrf_guard import tls_verify
        return tls_verify(url)
    except ImportError:
        return False


# 抑制自签名证书告警
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Vuln-Scanner/2.1'

# 扫描器目标多为自签名/内部证书，与 Nessus/Qualys/ZAP 等一致，
# 探测阶段关闭 TLS 证书校验（并非用于建立受信通道）。生产环境如需
# 校验证书，可将下方各 verify=False 改为 verify=True 并按需注入 CA。



# ============================================================
# 1. Web 指纹识别
# ============================================================
class WebFingerprinter:
    """Web 指纹识别 — 通过响应头 + 响应体特征识别 CMS/框架/中间件版本"""

    # 中间件指纹：Server 头正则 → (product, category)
    SERVER_PATTERNS = [
        (r'nginx/([\d.]+)', 'nginx', 'middleware'),
        (r'Apache/([\d.]+)', 'Apache HTTP Server', 'middleware'),
        (r'Microsoft-IIS/([\d.]+)', 'Microsoft IIS', 'middleware'),
        (r'Apache-Coyote/([\d.]+)', 'Apache Tomcat', 'middleware'),
        (r'Jetty\(([\d.]+)', 'Jetty', 'middleware'),
        (r'openresty/([\d.]+)', 'OpenResty', 'middleware'),
        (r'lighttpd/([\d.]+)', 'lighttpd', 'middleware'),
        (r'Caddy', 'Caddy', 'middleware'),
        (r'cloudflare', 'Cloudflare', 'middleware'),
    ]

    # 响应头特征：header 名 → [(正则, product, category)]
    HEADER_SIGNATURES = [
        ('X-Powered-By', [(r'PHP/([\d.]+)', 'PHP', 'language'),
                           (r'ASP\.NET', 'ASP.NET', 'framework'),
                           (r'Express', 'Express', 'framework'),
                           (r'Next\.js', 'Next.js', 'framework'),
                           (r'JBoss', 'JBoss', 'middleware')]),
        ('X-AspNet-Version', [(r'([\d.]+)', 'ASP.NET', 'framework')]),
        ('X-Drupal-Cache', [(r'(.*)', 'Drupal', 'cms')]),
        ('X-Generator', [(r'Drupal', 'Drupal', 'cms'),
                         (r'WordPress', 'WordPress', 'cms'),
                         (r'Joomla!', 'Joomla', 'cms')]),
        ('Set-Cookie', [(r'laravel_session', 'Laravel', 'framework'),
                        (r'PHPSESSID', 'PHP', 'language'),
                        (r'JSESSIONID', 'Java Servlet', 'framework'),
                        (r'ASP\.NET_SessionId', 'ASP.NET', 'framework')]),
        ('X-Drupal-Dynamic-Cache', [(r'(.*)', 'Drupal', 'cms')]),
        ('X-Varnish', [(r'(.*)', 'Varnish', 'middleware')]),
    ]

    # 响应体特征：正则 → (product, category, confidence)
    BODY_SIGNATURES = [
        (r'wp-content/', 'WordPress', 'cms', 'high'),
        (r'wp-includes/', 'WordPress', 'cms', 'high'),
        (r'/wp-json/', 'WordPress', 'cms', 'high'),
        (r'wp-login\.php', 'WordPress', 'cms', 'high'),
        (r'__VIEWSTATE', 'ASP.NET WebForms', 'framework', 'high'),
        (r'csrfmiddlewaretoken', 'Django', 'framework', 'high'),
        (r'XSRF-TOKEN', 'Laravel', 'framework', 'medium'),
        (r'Drupal\.settings', 'Drupal', 'cms', 'high'),
        (r'joomla!', 'Joomla', 'cms', 'medium'),
        (r'com_content', 'Joomla', 'cms', 'medium'),
        (r'Spring Security', 'Spring', 'framework', 'medium'),
        (r'Powered by Shopify', 'Shopify', 'cms', 'high'),
        (r'ghost\.io', 'Ghost', 'cms', 'medium'),
        (r'discourse', 'Discourse', 'cms', 'medium'),
        (r'/_next/static', 'Next.js', 'framework', 'high'),
        (r'data-reactroot', 'React', 'framework', 'medium'),
        (r'__NEXT_DATA__', 'Next.js', 'framework', 'high'),
        (r'angular', 'Angular', 'framework', 'medium'),
        (r'vue\.js', 'Vue.js', 'framework', 'low'),
    ]

    def __init__(self, timeout: int = 8):
        self.timeout = timeout

    def fingerprint(self, url: str) -> Dict[str, Any]:
        """对目标 URL 做指纹识别"""
        result: Dict[str, Any] = {'url': url, 'products': [], 'title': '', 'status': None}
        try:
            # 不跟随重定向：初始 URL 已过 SSRF 校验，但重定向目标没有，
            # 跟随会让公网 URL 一个 302 跳回内网/云元数据，借扫描器完成 SSRF。
            # 对安全扫描器而言，重定向本身就是一个该报告给用户的结果。
            resp = requests.get(url, timeout=self.timeout, verify=_verify_for_url(url),
                                allow_redirects=False, headers={'User-Agent': DEFAULT_UA})
            result['status'] = resp.status_code
            if resp.is_redirect or resp.is_permanent_redirect:
                result['redirect'] = resp.headers.get('Location', '')
            result['title'] = self._extract_title(resp.text)
            self._match_headers(resp.headers, result['products'])
            self._match_body(resp.text, result['products'])
        except requests.RequestException as e:
            result['error'] = str(e)
        return result

    def _extract_title(self, body: str) -> str:
        m = re.search(r'<title[^>]*>(.*?)</title>', body, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip()[:200] if m else ''

    def _match_headers(self, headers, products: List[Dict]):
        server = headers.get('Server', '')
        for pattern, product, category in self.SERVER_PATTERNS:
            m = re.search(pattern, server, re.IGNORECASE)
            if m:
                products.append({'product': product, 'category': category,
                                 'version': m.group(1) if m.lastindex else '',
                                 'confidence': 'high', 'evidence': f'Server: {server}'})

        for header_name, patterns in self.HEADER_SIGNATURES:
            value = headers.get(header_name, '')
            if not value:
                continue
            for pattern, product, category in patterns:
                m = re.search(pattern, value, re.IGNORECASE)
                if m:
                    products.append({'product': product, 'category': category,
                                     'version': m.group(1) if m.lastindex else '',
                                     'confidence': 'medium',
                                     'evidence': f'{header_name}: {value}'})
                    break

    def _match_body(self, body: str, products: List[Dict]):
        for pattern, product, category, confidence in self.BODY_SIGNATURES:
            if re.search(pattern, body, re.IGNORECASE):
                products.append({'product': product, 'category': category,
                                 'version': '', 'confidence': confidence,
                                 'evidence': f'body match: {pattern}'})

    @staticmethod
    def dedupe(products: List[Dict]) -> List[Dict]:
        """去重：同 product 只保留置信度最高的一条"""
        seen: Dict[str, Dict] = {}
        rank = {'high': 3, 'medium': 2, 'low': 1}
        for p in products:
            key = p['product']
            if key not in seen or rank.get(p['confidence'], 0) > rank.get(seen[key]['confidence'], 0):
                seen[key] = p
        return list(seen.values())


# ============================================================
# 2. 自定义 HTTP 请求探测
# ============================================================
class HTTPProber:
    """自定义 HTTP 请求探测 — 支持任意 method/headers/body"""

    # 内建高危敏感路径
    HIGH_RISK_PATHS = [
        ('/.git/config', 'Git 仓库配置泄露', 'HIGH'),
        ('/.env', '环境变量文件泄露', 'CRITICAL'),
        ('/.svn/entries', 'SVN 元数据泄露', 'MEDIUM'),
        ('/.DS_Store', 'macOS 元数据泄露', 'LOW'),
        ('/actuator/env', 'Spring Boot Actuator 暴露', 'HIGH'),
        ('/actuator/health', 'Spring Boot Actuator 暴露', 'LOW'),
        ('/server-status', 'Apache server-status 暴露', 'MEDIUM'),
        ('/phpinfo.php', 'PHP 信息泄露', 'MEDIUM'),
        ('/WEB-INF/web.xml', 'Java WEB-INF 配置泄露', 'HIGH'),
        ('/robots.txt', 'robots.txt 敏感路径', 'INFO'),
    ]

    def __init__(self, timeout: int = 8):
        self.timeout = timeout

    def probe(self, url: str, method: str = 'GET', headers: Optional[Dict] = None,
              body: Optional[str] = None, follow_redirects: bool = True) -> Dict[str, Any]:
        """执行自定义 HTTP 请求"""
        started = time.time()
        result: Dict[str, Any] = {'url': url, 'method': method, 'status': None}
        try:
            resp = requests.request(method, url, headers=headers, data=body,
                                    timeout=self.timeout, verify=_verify_for_url(url),
                                    allow_redirects=follow_redirects)
            elapsed = round(time.time() - started, 3)
            result.update({
                'status': resp.status_code,
                'headers': dict(resp.headers),
                'body': resp.text,
                'preview': resp.text[:500],
                'elapsed': elapsed,
            })
        except requests.RequestException as e:
            result['error'] = str(e)
        return result

    def probe_high_risk_paths(self, base_url: str, stop_event=None) -> List[Dict]:
        """探测内建高危敏感路径，返回命中列表（支持协作式停止）"""
        base_url = base_url.rstrip('/')
        findings = []
        for path, title, severity in self.HIGH_RISK_PATHS:
            if stop_event is not None and stop_event.is_set():
                break
            r = self.probe(base_url + path, method='GET')
            status = r.get('status')
            # 敏感文件命中通常返回 200 或 401/403（存在但受限）
            if status in (200, 401, 403):
                findings.append({'path': path, 'title': title, 'severity': severity,
                                 'status': status, 'evidence': (r.get('preview') or '')[:200]})
        return findings


# ============================================================
# 3. 目录枚举 + 备份文件检测
# ============================================================
class DirectoryEnumerator:
    """目录枚举 + 备份文件检测"""

    COMMON_DIRS = [
        'admin', 'administrator', 'backup', 'bak', 'config', 'test', 'upload',
        'uploads', 'logs', 'log', 'data', 'db', 'database', 'tmp', 'temp',
        'static', 'assets', 'css', 'js', 'images', 'img', 'api', 'v1',
        'docs', 'doc', 'src', 'old', 'private', 'secret', 'web', 'public',
        '.git', '.svn', '.hg',
    ]

    BACKUP_EXTENSIONS = ['.bak', '.old', '~', '.swp', '.sql', '.zip', '.tar',
                         '.tar.gz', '.7z', '.rar', '.gz', '.orig', '.save',
                         '.backup', '.conf', '.ini', '.log']

    def __init__(self, timeout: int = 6, max_workers: int = 10):
        self.timeout = timeout
        self.max_workers = max_workers

    @staticmethod
    def build_paths(base_word: str) -> List[str]:
        """根据基准词生成待探测路径（目录 + 备份文件变体）"""
        paths = [f'/{base_word}/', f'/{base_word}']
        for ext in DirectoryEnumerator.BACKUP_EXTENSIONS:
            paths.append(f'/{base_word}{ext}')
        return paths

    @staticmethod
    def classify(path: str, status_code: int) -> Optional[Dict]:
        """根据状态码分类命中结果"""
        if status_code in (200, 301, 302, 403):
            is_backup = any(path.endswith(e) for e in DirectoryEnumerator.BACKUP_EXTENSIONS)
            return {
                'path': path, 'status': status_code,
                'type': 'backup_file' if is_backup else 'directory',
                'severity': 'HIGH' if (is_backup and status_code == 200) else ('MEDIUM' if status_code in (200, 403) else 'LOW'),
            }
        return None

    def _probe_path(self, base_url: str, path: str) -> Optional[Dict]:
        url = base_url.rstrip('/') + path
        try:
            resp = requests.get(url, timeout=self.timeout, verify=_verify_for_url(url),
                                allow_redirects=False, headers={'User-Agent': DEFAULT_UA})
            return self.classify(path, resp.status_code)
        except requests.RequestException:
            return None

    def enumerate(self, base_url: str, wordlist: Optional[List[str]] = None,
                  progress_callback=None, stop_event=None) -> List[Dict]:
        """执行目录枚举，返回命中列表（支持协作式停止）"""
        words = wordlist or self.COMMON_DIRS
        # 展开所有待探测路径
        all_paths: List[str] = []
        for w in words:
            all_paths.extend(self.build_paths(w))

        findings: List[Dict] = []
        total = len(all_paths)
        done = 0
        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            futures = {executor.submit(self._probe_path, base_url, p): p for p in all_paths}
            for future in as_completed(futures):
                if stop_event is not None and stop_event.is_set():
                    break
                done += 1
                r = future.result()
                if r:
                    findings.append(r)
                if progress_callback and done % 20 == 0:
                    progress_callback(f'目录枚举进度 {done}/{total}')
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return findings


# ============================================================
# 4. OWASP ZAP 被动扫描
# ============================================================
class ZAPScanner:
    """OWASP ZAP 被动扫描集成（REST API，零新依赖）"""

    SEVERITY_MAP = {
        'High': 'HIGH', 'Medium': 'MEDIUM', 'Low': 'LOW', 'Informational': 'INFO',
    }

    def __init__(self, zap_host: str = '127.0.0.1', zap_port: int = 8080,
                 apikey: Optional[str] = None, timeout: int = 5):
        self.base_url = f'http://{zap_host}:{zap_port}'
        self.apikey = apikey
        self.timeout = timeout

    def _params(self) -> Dict:
        params = {}
        if self.apikey:
            params['apikey'] = self.apikey
        return params

    def is_available(self) -> bool:
        try:
            r = requests.get(f'{self.base_url}/JSON/core/view/version/',
                             params=self._params(), timeout=self.timeout)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def passive_scan(self, target_url: str, spider: bool = True) -> Dict[str, Any]:
        """执行被动扫描：打开目标 → （可选）spider → passiveScan → 拉取 alerts"""
        if not self.is_available():
            return {'available': False, 'reason': 'ZAP 未启动或不可达', 'alerts': []}

        try:
            # 1. 打开目标 URL，建立访问记录
            requests.get(f'{self.base_url}/JSON/core/action/accessUrl/',
                         params={**self._params(), 'url': target_url, 'followRedirects': 'true'},
                         timeout=self.timeout)
            # 2. 可选：spider 爬取
            if spider:
                requests.get(f'{self.base_url}/JSON/spider/action/scan/',
                             params={**self._params(), 'url': target_url, 'maxChildren': '5'},
                             timeout=self.timeout)
                self._wait_spider()
            # 3. 等待被动扫描完成
            requests.get(f'{self.base_url}/JSON/pscan/action/scanOnlyInScope/',
                         params={**self._params(), 'scanOnlyInScope': 'false'}, timeout=self.timeout)
            time.sleep(2)
            # 4. 拉取告警
            r = requests.get(f'{self.base_url}/JSON/core/view/alerts/',
                             params={**self._params(), 'baseurl': target_url, 'start': '0', 'count': '500'},
                             timeout=self.timeout)
            raw_alerts = r.json().get('alerts', [])
            alerts = [self._map_alert(a) for a in raw_alerts]
            return {'available': True, 'alerts': alerts, 'count': len(alerts)}
        except requests.RequestException as e:
            return {'available': False, 'reason': f'ZAP 调用失败: {e}', 'alerts': []}

    def _wait_spider(self, max_wait: int = 15):
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                r = requests.get(f'{self.base_url}/JSON/spider/view/status/',
                                 params=self._params(), timeout=self.timeout)
                if r.json().get('status') == '100':
                    break
            except requests.RequestException:
                break
            time.sleep(1)

    def _map_alert(self, alert: Dict) -> Dict:
        return {
            'name': alert.get('alert', ''),
            'severity': self.SEVERITY_MAP.get(alert.get('risk', 'Informational'), 'INFO'),
            'confidence': alert.get('confidence', ''),
            'url': alert.get('url', ''),
            'description': (alert.get('description', '') or '')[:500],
            'solution': (alert.get('solution', '') or '')[:300],
            'cwe_id': str(alert.get('cweid', '')),
        }


# ============================================================
# 5. Web 安全扫描编排器
# ============================================================
class WebSecurityScanner:
    """Web 安全扫描编排器 — 指纹 → 高危路径 → 目录枚举 → ZAP"""

    def __init__(self, db=None, zap_host: str = '127.0.0.1', zap_port: int = 8080,
                 ai_enabled: bool = False):
        self.db = db
        self.ai_enabled = ai_enabled
        self.fingerprinter = WebFingerprinter()
        self.prober = HTTPProber()
        self.enumerator = DirectoryEnumerator()
        self.zap = ZAPScanner(zap_host=zap_host, zap_port=zap_port)
        self.vuln_scanner = WebVulnScanner()

    def scan(self, target_url: str, do_directory: bool = True, do_zap: bool = True,
             do_active: bool = True, progress_callback=None, ai_enabled: Optional[bool] = None,
             stop_event=None) -> Dict[str, Any]:
        """执行完整 Web 安全扫描（指纹 → 高危路径 → 目录 → ZAP → 主动漏洞检测）"""
        if ai_enabled is None:
            ai_enabled = self.ai_enabled
        target_url = target_url.rstrip('/')
        result: Dict[str, Any] = {
            'target': target_url,
            'fingerprint': {}, 'high_risk': [], 'directories': [], 'zap': {'available': False},
            'active': [], 'findings': [],
        }

        if progress_callback:
            progress_callback('Web 指纹识别中...')
        fp = self.fingerprinter.fingerprint(target_url)
        fp['products'] = WebFingerprinter.dedupe(fp.get('products', []))
        result['fingerprint'] = fp

        if stop_event is not None and stop_event.is_set():
            if progress_callback:
                progress_callback('Web 扫描已停止')
            result['findings'] = self._aggregate_findings(result)
            result['stopped'] = True
            return result

        if progress_callback:
            progress_callback('高危敏感路径探测中...')
        result['high_risk'] = self.prober.probe_high_risk_paths(target_url, stop_event=stop_event)

        try:
            if do_directory:
                if stop_event is not None and stop_event.is_set():
                    raise ScanStopped()
                if progress_callback:
                    progress_callback('目录枚举中...')
                result['directories'] = self.enumerator.enumerate(target_url, progress_callback=progress_callback,
                                                                  stop_event=stop_event)

            if do_zap:
                if stop_event is not None and stop_event.is_set():
                    raise ScanStopped()
                if progress_callback:
                    progress_callback('ZAP 被动扫描中...')
                result['zap'] = self.zap.passive_scan(target_url)

            if do_active:
                if stop_event is not None and stop_event.is_set():
                    raise ScanStopped()
                if progress_callback:
                    progress_callback('主动 Web 漏洞检测中...')
                result['active'] = self.vuln_scanner.scan(
                    target_url, progress_callback=progress_callback, stop_event=stop_event)
        except ScanStopped:
            if progress_callback:
                progress_callback('Web 扫描已停止')
            result['findings'] = self._aggregate_findings(result)
            result['stopped'] = True
            return result

        result['findings'] = self._aggregate_findings(result)

        # AI 误报核验（可选）：仅核验 web_vuln 活跃检测项中的中高危发现
        if ai_enabled:
            if progress_callback:
                progress_callback('AI 误报核验中...')
            result['ai_stats'] = self._ai_verify(result, stop_event)

        self._persist(target_url, result)
        return result

    def _ai_verify(self, result: Dict, stop_event=None) -> Dict:
        """对 web_vuln 活跃发现做 AI 误报核验，合并回 result['findings'] 并返回 stats。"""
        from ai_scan_enhancer import AIScanEnhancer
        enhancer = AIScanEnhancer(db=self.db, stop_event=stop_event)
        verify = enhancer.verify_web_findings(
            result.get('findings', []),
            target=result.get('target', ''),
        )
        # confirmed（含跳过项）+ excluded（带 excluded_reason）全部保留并落库
        result['findings'] = list(verify.get('confirmed', [])) + list(verify.get('excluded', []))
        result['ai_excluded'] = list(verify.get('excluded', []))
        return verify.get('stats', {})

    def _aggregate_findings(self, result: Dict) -> List[Dict]:
        """聚合所有发现为统一格式"""
        findings: List[Dict] = []
        # 指纹发现
        for p in result['fingerprint'].get('products', []):
            findings.append({'category': 'fingerprint', 'title': p['product'],
                             'severity': 'INFO', 'evidence': p.get('evidence', ''),
                             'detail': f"{p.get('category', '')} {p.get('version', '')}".strip()})
        # 高危路径
        for h in result.get('high_risk', []):
            findings.append({'category': 'high_risk_path', 'title': h['title'],
                             'severity': h['severity'], 'url': h['path'],
                             'evidence': h.get('evidence', '')})
        # 目录枚举
        for d in result.get('directories', []):
            findings.append({'category': d.get('type', 'directory'), 'title': f"发现{d['type']} {d['path']}",
                             'severity': d['severity'], 'url': d['path'],
                             'detail': f"HTTP {d['status']}"})
        # ZAP 告警
        for a in result.get('zap', {}).get('alerts', []):
            findings.append({'category': 'zap', 'title': a['name'],
                             'severity': a['severity'], 'url': a.get('url', ''),
                             'detail': a.get('description', '')})
        # 主动漏洞检测（web_vuln_scanner 已输出统一 finding 格式）
        for a in result.get('active', []):
            findings.append(a)
        return findings

    def _persist(self, target: str, result: Dict):
        """将扫描结果写入数据库（若提供 db）"""
        if not self.db:
            return
        try:
            for f in result.get('findings', []):
                self.db.add_web_scan_result(target, {
                    'scan_type': f.get('scan_type', 'web'), 'category': f.get('category'),
                    'title': f.get('title'), 'severity': f.get('severity'),
                    'detail': f.get('detail', ''), 'evidence': f.get('evidence', ''),
                    'url': f.get('url', ''),
                    'parameter': f.get('parameter', ''), 'payload': f.get('payload', ''),
                    'remediation': f.get('remediation') or f.get('ai_remediation', ''),
                    'ai_verified': 1 if f.get('ai_verified') else 0,
                    'ai_confidence': f.get('ai_confidence'),
                    'ai_reasoning': f.get('ai_reasoning', ''),
                    'excluded_reason': f.get('excluded_reason', ''),
                })
        except Exception as e:
            logger.warning(f"Web 扫描结果持久化失败: {e}")
