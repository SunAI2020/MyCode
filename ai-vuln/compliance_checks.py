# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 合规自动评估器（三个标准共用）

每个评估器签名: fn(evidence: EvidenceBundle, control: ComplianceControl) -> Dict
返回 {'status', 'detail', 'evidence', 'recommendation'}

原则：没有证据 ≠ 合规。判不出来就返回『证据不足』，绝不默认『符合』。
"""
import logging
from typing import List, Dict

from compliance_engine import (
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_INSUFFICIENT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# 端口/协议特征表
# ============================================================
# 明文传输协议：账号口令与数据在网络上裸奔
CLEARTEXT_PORTS = {
    21: 'FTP', 23: 'Telnet', 25: 'SMTP(明文)', 69: 'TFTP',
    110: 'POP3', 143: 'IMAP', 512: 'rexec', 513: 'rlogin', 514: 'rsh',
    873: 'rsync', 2049: 'NFS',
}

# 明文身份鉴别协议（身份鉴别条款专用，比 CLEARTEXT_PORTS 更聚焦）
CLEARTEXT_AUTH_PORTS = {21: 'FTP', 23: 'Telnet', 110: 'POP3', 143: 'IMAP',
                        512: 'rexec', 513: 'rlogin', 514: 'rsh'}

# 数据库服务端口（含国产数据库）
DATABASE_PORTS = {
    3306: 'MySQL', 5432: 'PostgreSQL', 1433: 'SQL Server', 1521: 'Oracle',
    6379: 'Redis', 27017: 'MongoDB', 9200: 'Elasticsearch', 11211: 'Memcached',
    5236: '达梦DM', 54321: 'KingbaseES', 5000: 'Sybase', 50000: 'DB2',
}

# 无认证/易未授权访问的数据服务（暴露即高危）
UNAUTH_PRONE_PORTS = {6379: 'Redis', 27017: 'MongoDB', 9200: 'Elasticsearch',
                      11211: 'Memcached', 2375: 'Docker API'}

# 远程管理端口（对外暴露需强管控）
REMOTE_ADMIN_PORTS = {3389: 'RDP', 5900: 'VNC', 5985: 'WinRM', 5986: 'WinRM(HTTPS)'}

# 工业控制协议端口（关基核心关注点，与 device_fingerprint.PORT_SIGNATURES 对齐）
OT_PROTOCOL_PORTS = {
    502: 'Modbus TCP', 102: 'S7comm', 44818: 'EtherNet/IP', 47808: 'BACnet',
    20000: 'DNP3', 2404: 'IEC 60870-5-104', 4840: 'OPC UA',
    34962: 'PROFINET', 34964: 'PROFINET', 789: 'Red Lion', 1911: 'Niagara Fox',
    9600: 'OMRON FINS', 5006: 'MELSEC', 5007: 'MELSEC',
}

_HIGH_SEV = ('CRITICAL', 'HIGH')
_MEDIUM_SEV = ('MEDIUM',)


# ============================================================
# 工具函数
# ============================================================
def _sev(v: Dict) -> str:
    return str(v.get('severity', '')).upper()


def _high_vulns(evidence) -> List[Dict]:
    return [v for v in evidence.vulnerabilities if _sev(v) in _HIGH_SEV]


def _kev_vulns(evidence) -> List[Dict]:
    """命中 CISA KEV（已知被在野利用）的漏洞"""
    out = [v for v in evidence.vulnerabilities if v.get('kev')]
    if out:
        return out
    kev_ids = {str(k.get('cve_id', '')).upper() for k in evidence.kev}
    return [v for v in evidence.vulnerabilities
            if str(v.get('cve_id', '')).upper() in kev_ids] if kev_ids else []


def _ports_matching(evidence, table: Dict[int, str]) -> List[Dict]:
    hits = []
    for p in evidence.open_ports:
        try:
            port = int(p.get('port'))
        except (TypeError, ValueError):
            continue
        if port in table:
            hits.append({**p, '_proto_name': table[port]})
    return hits


def _fmt_ports(hits: List[Dict], limit: int = 8) -> str:
    items = [f"{h.get('_proto_name')}/{h.get('port')}@{h.get('host', '')}".rstrip('@')
             for h in hits[:limit]]
    more = f" 等{len(hits)}项" if len(hits) > limit else ''
    return '、'.join(items) + more


def _tls_issues(evidence, severities=_HIGH_SEV) -> List[Dict]:
    return [f for f in evidence.tls_findings if _sev(f) in severities]


# ============================================================
# 评估器
# ============================================================
def check_transport_encryption(evidence, control) -> Dict:
    """通信传输加密：明文协议端口 + TLS/加密套件缺陷

    对应：等保 安全通信网络-通信传输；关基 数据传输；数据安全 传输加密
    """
    clear = _ports_matching(evidence, CLEARTEXT_PORTS)
    tls_high = _tls_issues(evidence)                    # 严重/高危
    # 中危必须计入：TLS1.0/1.1、RC4/3DES 等弱算法被扫描器普遍评为中危，
    # 只看高危会让这类真实的加密缺陷被判成『符合』，属于漏报。
    tls_medium = _tls_issues(evidence, _MEDIUM_SEV)

    if not evidence.open_ports and not evidence.tls_findings:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '未获取到端口与加密检测证据，无法判定传输加密情况',
                'evidence': [], 'recommendation': '请先对目标执行端口扫描'}

    fix_tls = ('禁用 SSLv2/SSLv3/TLS1.0/1.1 及 RC4/DES/3DES/MD5/SHA1 等弱算法，'
               '统一启用 TLS 1.2+ 并配置前向安全套件')

    if clear:
        return {
            'status': STATUS_FAIL,
            'detail': f'检测到 {len(clear)} 个明文传输服务：{_fmt_ports(clear)}，'
                      f'账号口令与业务数据以明文在网络中传输',
            'evidence': clear,
            'recommendation': '关闭明文协议，改用 SSH/SFTP/FTPS/HTTPS 等加密通道；'
                              '确需保留的应限制源地址并加密隧道封装',
        }
    if tls_high:
        names = '、'.join({f.get('category', '加密缺陷') for f in tls_high})
        return {
            'status': STATUS_FAIL,
            'detail': f'未发现明文协议，但存在 {len(tls_high)} 项高危加密配置缺陷（{names}），'
                      f'传输保密性无法保证',
            'evidence': tls_high,
            'recommendation': fix_tls,
        }
    if tls_medium:
        names = '、'.join({f.get('category', '加密缺陷') for f in tls_medium})
        return {
            'status': STATUS_PARTIAL,
            'detail': f'未发现明文协议与高危缺陷，但存在 {len(tls_medium)} 项中危加密配置缺陷（{names}）',
            'evidence': tls_medium,
            'recommendation': fix_tls,
        }
    return {
        'status': STATUS_PASS,
        'detail': f'已检查 {len(evidence.open_ports)} 个开放端口，未发现明文传输服务与加密配置缺陷',
        'evidence': [], 'recommendation': '',
    }


def check_identity_auth(evidence, control) -> Dict:
    """身份鉴别：弱口令/默认口令 + 明文身份鉴别协议"""
    weak = evidence.weak_passwords or []
    clear_auth = _ports_matching(evidence, CLEARTEXT_AUTH_PORTS)

    if evidence.scan_result is None:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '无扫描证据，无法判定身份鉴别情况',
                'evidence': [], 'recommendation': '请先对目标执行扫描'}

    if weak:
        detail_items = '、'.join(
            f"{w.get('service', w.get('protocol', '服务'))}@{w.get('host', '')}:{w.get('port', '')}"
            for w in weak[:6])
        return {
            'status': STATUS_FAIL,
            'detail': f'检测到 {len(weak)} 处弱口令/默认口令：{detail_items}',
            'evidence': weak,
            'recommendation': '立即修改为高强度口令（大小写+数字+符号，长度≥8），'
                              '启用登录失败锁定与口令定期更换策略',
        }
    if clear_auth:
        return {
            'status': STATUS_PARTIAL,
            'detail': f'未探测到弱口令，但存在明文身份鉴别协议：{_fmt_ports(clear_auth)}，'
                      f'鉴别信息可被网络嗅探截获',
            'evidence': clear_auth,
            'recommendation': '停用 Telnet/FTP 等明文鉴别协议，改用 SSH/SFTP',
        }
    return {
        'status': STATUS_PASS,
        'detail': '未探测到弱口令/默认口令，未发现明文身份鉴别协议',
        'evidence': [], 'recommendation': '',
    }


def check_intrusion_prevention(evidence, control) -> Dict:
    """入侵防范：外部可达的高危漏洞与在野利用漏洞"""
    if evidence.scan_result is None:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '无扫描证据，无法判定入侵防范有效性',
                'evidence': [], 'recommendation': '请先对目标执行漏洞扫描'}

    high = _high_vulns(evidence)
    kev = _kev_vulns(evidence)

    if kev:
        ids = '、'.join(sorted({str(v.get('cve_id')) for v in kev if v.get('cve_id')})[:6])
        return {
            'status': STATUS_FAIL,
            'detail': f'存在 {len(kev)} 个已知被在野利用漏洞（CISA KEV）：{ids}，'
                      f'边界防护未能有效阻断已知攻击面',
            'evidence': kev,
            'recommendation': '按 KEV 要求优先修复上述漏洞；在关键网络节点部署 IPS/WAF 并保持规则库更新',
        }
    if high:
        ids = '、'.join(sorted({str(v.get('cve_id')) for v in high if v.get('cve_id')})[:6])
        return {
            'status': STATUS_FAIL,
            'detail': f'存在 {len(high)} 个高危/严重漏洞：{ids}，攻击面未收敛',
            'evidence': high,
            'recommendation': '优先修复高危漏洞；在关键网络节点部署入侵检测/防御设备并开启阻断',
        }
    return {
        'status': STATUS_PASS,
        'detail': f'已检查 {len(evidence.vulnerabilities)} 条漏洞记录，未发现高危/严重及在野利用漏洞',
        'evidence': [], 'recommendation': '',
    }


def check_vuln_remediation(evidence, control) -> Dict:
    """漏洞修复及时性：高危漏洞存量"""
    if evidence.scan_result is None:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '无扫描证据，无法判定漏洞修复情况',
                'evidence': [], 'recommendation': '请先对目标执行漏洞扫描'}

    high = _high_vulns(evidence)
    total = len(evidence.vulnerabilities)
    if not high:
        if total == 0:
            return {'status': STATUS_PASS,
                    'detail': '本次扫描未发现已知漏洞',
                    'evidence': [], 'recommendation': ''}
        return {'status': STATUS_PASS,
                'detail': f'共 {total} 条漏洞记录，均为中低危，无高危/严重未修复漏洞',
                'evidence': [], 'recommendation': ''}
    critical = [v for v in high if _sev(v) == 'CRITICAL']
    status = STATUS_FAIL if critical else STATUS_PARTIAL
    return {
        'status': status,
        'detail': f'存在未修复高危漏洞 {len(high)} 个（其中严重 {len(critical)} 个），占总量 {total} 条',
        'evidence': high,
        'recommendation': '建立漏洞闭环管理流程：严重漏洞 24 小时内、高危 7 日内完成修复或缓解',
    }


def check_kev_due(evidence, control) -> Dict:
    """已知被利用漏洞按期修复（依据 CISA KEV due_date）"""
    if evidence.scan_result is None:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '无扫描证据，无法判定 KEV 修复时限',
                'evidence': [], 'recommendation': '请先对目标执行漏洞扫描'}

    kev = _kev_vulns(evidence)
    if not kev:
        return {'status': STATUS_PASS,
                'detail': '未发现命中 CISA KEV 目录的在野利用漏洞',
                'evidence': [], 'recommendation': ''}

    from datetime import datetime
    today = datetime.now().date()
    overdue = []
    for v in kev:
        due = v.get('kev_due_date') or ''
        try:
            if due and datetime.strptime(str(due)[:10], '%Y-%m-%d').date() < today:
                overdue.append(v)
        except ValueError:
            continue

    ransom = [v for v in kev if v.get('known_ransomware')]
    if overdue:
        ids = '、'.join(sorted({str(v.get('cve_id')) for v in overdue if v.get('cve_id')})[:6])
        return {
            'status': STATUS_FAIL,
            'detail': f'{len(overdue)} 个在野利用漏洞已超过 KEV 规定修复期限：{ids}'
                      + (f'；其中 {len(ransom)} 个与勒索软件活动关联' if ransom else ''),
            'evidence': overdue,
            'recommendation': '立即按 CISA KEV 的 required_action 完成处置，并复核修复有效性',
        }
    return {
        'status': STATUS_PARTIAL,
        'detail': f'存在 {len(kev)} 个在野利用漏洞但尚未超期'
                  + (f'，其中 {len(ransom)} 个与勒索软件关联' if ransom else ''),
        'evidence': kev,
        'recommendation': '在到期日前完成修复，勒索软件关联漏洞应优先处置',
    }


def check_malicious_code_defense(evidence, control) -> Dict:
    """恶意代码防范：勒索软件关联漏洞暴露面

    说明：杀毒软件部署状态无法通过网络扫描探测，此评估器只覆盖
    『可被恶意代码利用的已知漏洞』这一侧面，因此最好判定为部分符合。
    """
    if evidence.scan_result is None:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '无扫描证据，无法判定恶意代码暴露面',
                'evidence': [], 'recommendation': '请先对目标执行漏洞扫描'}

    ransom = [v for v in evidence.vulnerabilities if v.get('known_ransomware')]
    if ransom:
        ids = '、'.join(sorted({str(v.get('cve_id')) for v in ransom if v.get('cve_id')})[:6])
        return {
            'status': STATUS_FAIL,
            'detail': f'存在 {len(ransom)} 个与勒索软件活动关联的漏洞：{ids}',
            'evidence': ransom,
            'recommendation': '立即修复上述漏洞；部署并更新防恶意代码软件，开启实时防护与定期全盘扫描',
        }
    return {
        'status': STATUS_PARTIAL,
        'detail': '未发现勒索软件关联漏洞；但防恶意代码软件的部署与更新状态无法通过网络扫描确认，'
                  '需结合人工填报判定',
        'evidence': [],
        'recommendation': '请在问卷中补充防恶意代码软件的部署范围、版本与病毒库更新周期',
    }


def check_boundary_access_control(evidence, control) -> Dict:
    """边界访问控制：远程管理端口与未授权访问服务的暴露"""
    if not evidence.open_ports:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '未获取到端口证据，无法判定边界访问控制',
                'evidence': [], 'recommendation': '请先对目标执行端口扫描'}

    unauth = _ports_matching(evidence, UNAUTH_PRONE_PORTS)
    admin = _ports_matching(evidence, REMOTE_ADMIN_PORTS)

    if unauth:
        return {
            'status': STATUS_FAIL,
            'detail': f'检测到易未授权访问的数据服务对外开放：{_fmt_ports(unauth)}',
            'evidence': unauth,
            'recommendation': '这些服务默认无认证，应绑定内网地址、启用认证并通过防火墙限制访问源',
        }
    if admin:
        return {
            'status': STATUS_PARTIAL,
            'detail': f'检测到远程管理端口开放：{_fmt_ports(admin)}，需确认已限制访问源',
            'evidence': admin,
            'recommendation': '远程管理端口应仅对运维网段开放，启用多因素认证并记录操作日志',
        }
    return {
        'status': STATUS_PASS,
        'detail': f'已检查 {len(evidence.open_ports)} 个开放端口，未发现未授权访问服务与裸露的远程管理端口',
        'evidence': [], 'recommendation': '',
    }


def check_db_exposure(evidence, control) -> Dict:
    """数据存储安全：数据库服务暴露与弱口令"""
    if not evidence.open_ports:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '未获取到端口证据，无法判定数据库暴露情况',
                'evidence': [], 'recommendation': '请先对目标执行端口扫描'}

    dbs = _ports_matching(evidence, DATABASE_PORTS)
    if not dbs:
        return {'status': STATUS_PASS,
                'detail': '未发现对外开放的数据库服务端口',
                'evidence': [], 'recommendation': ''}

    db_ports = {int(h['port']) for h in dbs}
    db_weak = [w for w in (evidence.weak_passwords or [])
               if str(w.get('port', '')).isdigit() and int(w['port']) in db_ports]
    unauth = [h for h in dbs if int(h['port']) in UNAUTH_PRONE_PORTS]

    if db_weak or unauth:
        parts = []
        if db_weak:
            parts.append(f'{len(db_weak)} 个数据库存在弱口令')
        if unauth:
            parts.append(f'{len(unauth)} 个免认证数据服务暴露（{_fmt_ports(unauth)}）')
        return {
            'status': STATUS_FAIL,
            'detail': f'数据库暴露风险：{"；".join(parts)}',
            'evidence': db_weak + unauth,
            'recommendation': '数据库不应直接对外暴露；应绑定内网、强制强口令与认证、'
                              '按最小权限分配账号，并开启访问审计',
        }
    return {
        'status': STATUS_PARTIAL,
        'detail': f'检测到 {len(dbs)} 个数据库服务端口开放（{_fmt_ports(dbs)}），'
                  f'未发现弱口令，但对外暴露本身即为风险',
        'evidence': dbs,
        'recommendation': '确认这些端口是否必须对外开放；建议通过防火墙限制访问源地址',
    }


def check_data_classification(evidence, control) -> Dict:
    """数据分类分级标识：依据资产的 data_classification 字段"""
    asset = evidence.asset
    if not asset:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '本次检查未关联资产记录，无法核对数据分类分级标识。'
                          '请在资产管理中登记该目标并填写"数据分类"字段',
                'evidence': [], 'recommendation': '在资产管理页登记资产并设置数据分类分级'}

    cls = (asset.get('data_classification') or '').strip()
    biz = (asset.get('business_system') or '').strip()
    if not cls:
        return {
            'status': STATUS_FAIL,
            'detail': f'资产「{asset.get("name", "")}」未填写数据分类分级标识',
            'evidence': [{'asset': asset.get('name'), 'ip': asset.get('ip')}],
            'recommendation': '按《数据安全法》要求建立数据分类分级制度，'
                              '在资产管理中标注核心数据/重要数据/一般数据/个人信息',
        }
    if not biz:
        return {
            'status': STATUS_PARTIAL,
            'detail': f'已标注数据分类为「{cls}」，但未关联业务系统，分级管理粒度不足',
            'evidence': [{'asset': asset.get('name'), 'data_classification': cls}],
            'recommendation': '补充"业务系统"字段，以便按系统维度实施分级保护与责任落实',
        }
    return {
        'status': STATUS_PASS,
        'detail': f'资产「{asset.get("name", "")}」已标注数据分类「{cls}」，归属业务系统「{biz}」',
        'evidence': [], 'recommendation': '',
    }


def check_ot_protocol_exposure(evidence, control) -> Dict:
    """工业控制协议暴露（关键信息基础设施专项）

    工控协议普遍缺乏认证与加密设计，一旦可达即可直接下发控制指令。
    """
    if not evidence.open_ports:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '未获取到端口证据，无法判定工控协议暴露情况',
                'evidence': [], 'recommendation': '请先对目标执行端口扫描'}

    ot = _ports_matching(evidence, OT_PROTOCOL_PORTS)
    ot_devices = [d for d in evidence.devices if d.get('category') == 'OT']

    if ot:
        return {
            'status': STATUS_FAIL,
            'detail': f'检测到 {len(ot)} 个工业控制协议端口暴露：{_fmt_ports(ot)}。'
                      f'此类协议无认证与加密机制，可达即可下发控制指令',
            'evidence': ot,
            'recommendation': '工控网络必须与办公网/互联网物理或逻辑隔离；'
                              '部署工控防火墙与协议深度解析，严格限制可访问源地址',
        }
    if ot_devices:
        return {
            'status': STATUS_PARTIAL,
            'detail': f'识别到 {len(ot_devices)} 台工控设备但未发现工控协议端口暴露，'
                      f'需人工确认隔离措施',
            'evidence': ot_devices,
            'recommendation': '确认工控区域边界隔离措施与访问控制策略的有效性',
        }
    return {
        'status': STATUS_PASS,
        'detail': '未检测到工业控制协议端口暴露',
        'evidence': [], 'recommendation': '',
    }


def check_domestic_adaptation(evidence, control) -> Dict:
    """国产化适配情况（关基/信创关注点）

    只做识别与陈述，不因"未使用国产化产品"直接判为不符合——
    是否强制国产化取决于行业主管要求，应由人工填报确认。
    """
    domestic = [d for d in evidence.devices if d.get('category') == 'DOMESTIC_OS']
    if not evidence.devices:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '未获取到设备指纹证据，无法识别国产化适配情况',
                'evidence': [], 'recommendation': '请先对目标执行扫描以采集设备指纹'}
    if domestic:
        names = '、'.join(filter(None, {f"{d.get('vendor', '')}{d.get('product', '')}"
                                        for d in domestic}))
        return {
            'status': STATUS_PASS,
            'detail': f'识别到 {len(domestic)} 项国产化系统/数据库组件：{names}',
            'evidence': domestic, 'recommendation': '',
        }
    return {
        'status': STATUS_PARTIAL,
        'detail': f'在 {len(evidence.devices)} 台设备中未识别到国产化系统组件；'
                  f'是否需强制国产化替代由行业主管要求决定，需人工确认',
        'evidence': [],
        'recommendation': '请在问卷中说明本单位国产化替代规划与当前进度',
    }


def check_web_security_headers(evidence, control) -> Dict:
    """Web 安全防护：安全响应头与 Web 侧高危问题"""
    header_findings = [f for f in evidence.tls_findings
                       if 'HTTP' in str(f.get('category', '')).upper()
                       or '安全头' in str(f.get('category', ''))]
    web_high = [f for f in evidence.web_findings if _sev(f) in _HIGH_SEV]

    if not evidence.tls_findings and not evidence.web_findings:
        return {'status': STATUS_INSUFFICIENT,
                'detail': '无 Web 侧检测证据，无法判定 Web 安全防护情况',
                'evidence': [], 'recommendation': '请先对目标执行 Web 扫描'}

    if web_high:
        return {
            'status': STATUS_FAIL,
            'detail': f'Web 应用存在 {len(web_high)} 个高危/严重问题',
            'evidence': web_high,
            'recommendation': '优先修复 Web 高危漏洞，并部署 WAF 提供虚拟补丁防护',
        }
    if header_findings:
        return {
            'status': STATUS_PARTIAL,
            'detail': f'未发现 Web 高危漏洞，但存在 {len(header_findings)} 项安全响应头缺失',
            'evidence': header_findings,
            'recommendation': '补齐 HSTS、X-Frame-Options、X-Content-Type-Options、CSP 等安全响应头',
        }
    return {
        'status': STATUS_PASS,
        'detail': '未发现 Web 高危问题与安全响应头缺失',
        'evidence': [], 'recommendation': '',
    }


# ============================================================
# 注册表（条款目录 JSON 的 check 字段引用这里的键）
# ============================================================
CHECK_REGISTRY = {
    'check_transport_encryption': check_transport_encryption,
    'check_identity_auth': check_identity_auth,
    'check_intrusion_prevention': check_intrusion_prevention,
    'check_vuln_remediation': check_vuln_remediation,
    'check_kev_due': check_kev_due,
    'check_malicious_code_defense': check_malicious_code_defense,
    'check_boundary_access_control': check_boundary_access_control,
    'check_db_exposure': check_db_exposure,
    'check_data_classification': check_data_classification,
    'check_ot_protocol_exposure': check_ot_protocol_exposure,
    'check_domestic_adaptation': check_domestic_adaptation,
    'check_web_security_headers': check_web_security_headers,
}
