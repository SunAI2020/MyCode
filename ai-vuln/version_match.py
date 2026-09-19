# -*- coding: utf-8 -*-
"""CVE 精确匹配工具：产品名一致 + 版本区间判定。

背景：旧实现 `scanner_engine._get_matched_cves` 用关键词召回（对
affected_products/description 做 LIKE），把 Symantec/Palo Alto/RabbitMQ 等
完全无关产品的 CVE 挂到 msrpc/redis 等端口上，产生大量误报。

本模块把匹配收紧为两步：
1. 产品名一致 —— 探测到的 product/service 归一化后必须与 CVE 的
   affected_products 条目（`vendor:product` 或 `product:version` 枚举）中的
   产品名对齐（严格相等），才视为候选；
2. 版本判定 —— 当 affected_products 给出明确版本时做段前缀匹配；无版本时
   回退到 description 的版本区间（`from X until Y` / `before X` 等）二次约束。

召回（SQL LIKE）与判定分离：召回用 `RECALL_TERMS` 里的 DB 真实产品词，判定
用 `cve_applies` 的严格产品名相等 + 版本判定，保证召回偏宽时误报仍被过滤。

说明：与 `supply_chain.py` 的供应链依赖版本匹配不同——那里的 affected 是
`product:spec`（按首个冒号切分、spec 为区间表达式），而 CVE 库的
affected_products 是 `vendor:product` 或 `product:version` 的枚举，二者数据
形态不同，故独立实现（本模块为纯函数、无 IO）。
"""
import re
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 产品名归一化（严格：完整字符串命中别名表，否则返回归一化原串）
# ---------------------------------------------------------------------------

# 常见服务/产品别名 → 规范键。左列覆盖 nmap 常见 banner（含复合名）与 CVE
# affected_products 两种口径，右列是统一后的规范键。仅做「完整字符串」映射，
# 不做 token 级映射，避免 `postgresql_jdbc_driver` 被误归一化成 `postgresql`。
PRODUCT_CANON: Dict[str, str] = {
    # 数据库 / 缓存
    'redis': 'redis',
    'postgresql': 'postgresql', 'postgres': 'postgresql',
    'postgres db': 'postgresql', 'postgresql db': 'postgresql', 'pgsql': 'postgresql',
    'mysql': 'mysql', 'mariadb': 'mysql', 'percona server': 'mysql', 'percona': 'mysql',
    'mongodb': 'mongodb', 'mongo': 'mongodb',
    'ms-sql-s': 'mssql', 'mssql': 'mssql', 'sql server': 'mssql',
    'microsoft sql': 'mssql', 'microsoft sql server': 'mssql',
    'elasticsearch': 'elasticsearch', 'elastic': 'elasticsearch',
    # Web 服务器 / 中间件
    'apache httpd': 'apache_http_server', 'apache http server': 'apache_http_server',
    'httpd': 'apache_http_server', 'apache': 'apache_http_server',
    'apache tomcat': 'tomcat', 'tomcat': 'tomcat', 'jetty': 'jetty',
    'nginx': 'nginx', 'iis': 'iis', 'microsoft iis': 'iis', 'microsoft-iis': 'iis',
    'microsoft iis httpd': 'iis',
    # 远程 / 传输
    'openssh': 'openssh', 'openssh sshd': 'openssh', 'ssh': 'openssh',
    'dropbear': 'dropbear',
    'vsftpd': 'vsftpd', 'proftpd': 'proftpd', 'pure-ftpd': 'pure-ftpd', 'ftp': 'ftp',
    'sendmail': 'sendmail', 'postfix': 'postfix', 'exim': 'exim',
    'dovecot': 'dovecot', 'cyrus': 'cyrus',
    'telnetd': 'telnet', 'telnet': 'telnet',
    # Windows 组件（保守：无明确版本时不做 CVE 召回，交由 open_service 兜底）
    'msrpc': 'msrpc', 'microsoft windows rpc': 'msrpc', 'windows rpc': 'msrpc',
    'dcom': 'msrpc', 'microsoft rpc': 'msrpc',
    'microsoft-ds': 'smb', 'microsoft ds': 'smb', 'samba': 'smb', 'samba smbd': 'smb',
    'smb': 'smb', 'cifs': 'smb', 'netbios': 'smb', 'netbios-ssn': 'smb',
    'ms-wbt-server': 'rdp', 'remote desktop': 'rdp', 'rdp': 'rdp',
    # 其它常见
    'oracle': 'oracle', 'oracledb': 'oracle', 'oracle database': 'oracle',
    'docker': 'docker', 'kubernetes': 'kubernetes', 'k8s': 'kubernetes',
    'jenkins': 'jenkins', 'gitlab': 'gitlab', 'wordpress': 'wordpress',
    'drupal': 'drupal', 'vnc': 'vnc', 'realvnc': 'vnc', 'tightvnc': 'vnc',
    'bind': 'bind', 'named': 'bind', 'dns': 'bind', 'domain': 'bind',
    'memcached': 'memcached', 'rabbitmq': 'rabbitmq',
}

# 规范键 → affected_products 召回词（DB 里实际出现、可被 LIKE 子串命中的产品词）。
# 仅用于 SQL 召回候选，最终由 cve_applies 严格判定。
RECALL_TERMS: Dict[str, List[str]] = {
    'redis': ['redis'],
    'postgresql': ['postgresql', 'postgres'],
    'mysql': ['mysql', 'mariadb'],
    'mssql': ['sql server', 'mssql'],
    'apache_http_server': ['apache', 'http server', 'httpd'],
    'tomcat': ['tomcat'], 'jetty': ['jetty'], 'nginx': ['nginx'], 'iis': ['iis'],
    'openssh': ['openssh', 'ssh'], 'dropbear': ['dropbear'],
    'ftp': ['ftp', 'vsftpd', 'proftpd', 'pure-ftpd'],
    'sendmail': ['sendmail'], 'postfix': ['postfix'], 'exim': ['exim'],
    'dovecot': ['dovecot'], 'cyrus': ['cyrus'], 'telnet': ['telnet'],
    'smb': ['samba', 'smb', 'cifs'],
    'msrpc': ['windows rpc', 'rpc', 'dcom'],
    'rdp': ['remote desktop', 'rdp'],
    'oracle': ['oracle'],
    'docker': ['docker'], 'kubernetes': ['kubernetes'],
    'jenkins': ['jenkins'], 'gitlab': ['gitlab'],
    'wordpress': ['wordpress'], 'drupal': ['drupal'],
    'vnc': ['vnc'], 'bind': ['bind', 'named'],
    'memcached': ['memcached'], 'rabbitmq': ['rabbitmq'],
    'elasticsearch': ['elasticsearch'], 'mongodb': ['mongodb'],
}


# 泛化服务名：过于通用、无法对应具体产品，detect_product_key 应跳过
_GENERIC_KEYS = {'http', 'https', 'http-proxy', 'web', 'ssl', 'tls', 'tcp', 'udp',
                 'smtp', 'pop3', 'imap', 'www'}


def normalize_token(s: str) -> str:
    """小写、把 `_`/`-` 折叠为空格、压缩空白。"""
    s = (s or '').strip().lower()
    s = s.replace('_', ' ').replace('-', ' ').replace('  ', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def canonical_product(name: str) -> str:
    """完整字符串别名映射；未知时返回归一化原串。"""
    key = normalize_token(name)
    return PRODUCT_CANON.get(key, key)


def product_name_matches(detected: str, cve_product: str) -> bool:
    """探测产品名与 CVE 受影响产品名是否一致（严格相等，别名已由 canonical_product 收敛）。"""
    d = canonical_product(detected)
    c = canonical_product(cve_product)
    return bool(d) and d == c


def detect_product_key(product: str, service: str) -> Optional[str]:
    """从 nmap 的 product/service 推导规范产品键；无法识别返回 None。

    优先 service（nmap 服务名更规范），再 product。过于泛化的服务名
    （http/https 等）不视为具体产品，返回 None，交由 open_service 兜底。
    """
    for raw in (service, product):
        if not raw or raw.lower() in ('unknown',):
            continue
        key = canonical_product(raw)
        if key and key not in _GENERIC_KEYS:
            return key
    return None


def recall_terms(key: str) -> List[str]:
    """规范键 → DB 召回词（无映射时用键本身）。"""
    return RECALL_TERMS.get(key, [key])


# ---------------------------------------------------------------------------
# affected_products 解析（`vendor:product` 或 `product:version` 枚举）
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r'^\d+(?:\.\d+)*[a-z0-9.]*$')


def is_version_token(s: str) -> bool:
    """判断一个条目尾段是否为版本号（以数字开头）。"""
    return bool(_VERSION_RE.match((s or '').strip()))


def split_affected_entry(entry: str) -> Tuple[str, Optional[str]]:
    """解析单条 affected_products 条目 → (产品名, 版本|None)。

    规则：按最后一个冒号切分。
      - 尾段是版本号（数字开头）→ 头为产品、尾为版本（如 `PostgreSQL:9.6`）。
      - 尾段不是版本号 → `vendor:product`，产品取尾段（如 `redis:redis`、
        `postgresql:postgresql_jdbc_driver`），无版本。
    """
    entry = (entry or '').strip()
    if not entry:
        return '', None
    if ':' in entry:
        head, tail = entry.rsplit(':', 1)
        head = head.strip()
        tail = tail.strip()
        if is_version_token(tail):
            return head, tail
        return tail, None
    return entry, None


def split_affected_products(affected: str) -> List[Tuple[str, Optional[str]]]:
    """把逗号分隔的 affected_products 文本解析为 [(产品名, 版本|None), ...]。"""
    result: List[Tuple[str, Optional[str]]] = []
    for entry in (affected or '').split(','):
        name, ver = split_affected_entry(entry)
        if name:
            result.append((name, ver))
    return result


# ---------------------------------------------------------------------------
# 版本匹配
# ---------------------------------------------------------------------------

def _version_tuple(v: str) -> Optional[Tuple[int, ...]]:
    """提取前导数字段为整数元组，如 '9.6.0' → (9,6,0)。"""
    m = re.match(r'^(\d+(?:\.\d+)*)', (v or '').strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split('.'))


def version_matches(detected: str, affected: str) -> bool:
    """段前缀匹配：affected 是 detected 的段前缀即视为命中。

    例：detected='9.6.0' affected='9.6' → True；affected='2.2' 匹配 '2.2.15'。
    affected 为空/None 表示全版本，返回 True。
    """
    if not affected:
        return True
    d = _version_tuple(detected)
    a = _version_tuple(affected)
    if not d or not a:
        return True  # 无法解析 → 不排除
    return d[:len(a)] == a


# ---------------------------------------------------------------------------
# description 版本区间约束（无版本条目时的二次校验）
# ---------------------------------------------------------------------------

_RANGE_RE = re.compile(
    r'from\s+([\d.]+)\s+(?:until|to|up to|through)\s+([\d.]+)', re.I)
_BEFORE_RE = re.compile(
    r'(?:before|prior to|earlier than|before version)\s+([\d.]+)', re.I)
_FIXED_RE = re.compile(
    r'(?:patched in|fixed in|addressed in|as of)\s+(?:version\s+)?([\d.]+)', re.I)
_AND_EARLIER_RE = re.compile(
    r'([\d.]+)\s+(?:and|or)\s+(?:earlier|before|below)', re.I)


def parse_version_constraints(text: str) -> List[Tuple[str, str, Optional[str]]]:
    """从 description 提取版本约束，返回 [(op, a, b)]，op ∈ range/lt/lte。"""
    text = text or ''
    cons: List[Tuple[str, str, Optional[str]]] = []
    for m in _RANGE_RE.finditer(text):
        cons.append(('range', m.group(1), m.group(2)))
    for m in _BEFORE_RE.finditer(text):
        cons.append(('lt', m.group(1), None))
    for m in _FIXED_RE.finditer(text):
        cons.append(('lt', m.group(1), None))
    for m in _AND_EARLIER_RE.finditer(text):
        cons.append(('lte', m.group(1), None))
    return cons


def version_satisfies(detected: str, constraints: List[Tuple[str, str, Optional[str]]]) -> bool:
    """detected 是否满足所有约束；无约束或无法解析时返回 True（不排除）。"""
    d = _version_tuple(detected)
    if not d:
        return True
    for op, a, b in constraints:
        if op == 'range':
            lo = _version_tuple(a)
            hi = _version_tuple(b) if b else None
            if lo and d < lo:
                return False
            if hi and d >= hi:  # 'until Y' 语义为 < Y，略宽松为 >= Y 排除
                return False
        elif op == 'lt':
            x = _version_tuple(a)
            if x and d >= x:
                return False
        elif op == 'lte':
            x = _version_tuple(a)
            if x and d > x:
                return False
    return True


# ---------------------------------------------------------------------------
# 主判定：CVE 是否适用于探测到的服务
# ---------------------------------------------------------------------------

def cve_applies(cve: Dict, detected_product: str, detected_version: str) -> Optional[Dict]:
    """判定 CVE 是否适用于探测到的 (product, version)。

    返回 None（不适用）或
    {'applies': True, 'confidence': 'high|medium|low', 'matched_by': 'product+version|product'}。
    """
    entries = split_affected_products(cve.get('affected_products') or '')
    if not entries:
        return None

    product_match = False
    has_versioned_entry = False
    unversioned_ok = False
    for prod, ver in entries:
        if not product_name_matches(detected_product, prod):
            continue
        product_match = True
        if ver:
            has_versioned_entry = True
            if detected_version and version_matches(detected_version, ver):
                return {'applies': True, 'confidence': 'high',
                        'matched_by': 'product+version'}
        else:
            # 无版本条目 = 全版本；先做 description 区间校验，但不立即返回，
            # 以免同产品存在版本化条目时「全版本」误报覆盖版本排除。
            if detected_version:
                cons = parse_version_constraints(cve.get('description') or '')
                if cons and not version_satisfies(detected_version, cons):
                    continue
            unversioned_ok = True

    if not product_match:
        return None
    # 仅当无版本化条目时才接受「全版本」命中；有版本化条目则以版本判定为准
    if unversioned_ok and not has_versioned_entry:
        return {'applies': True, 'confidence': 'medium', 'matched_by': 'product'}
    if has_versioned_entry and not detected_version:
        return {'applies': True, 'confidence': 'low', 'matched_by': 'product'}
    return None
