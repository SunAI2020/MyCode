# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 蜜罐/欺骗资产识别模块

对标 honeydet / Nuclei honeypot 检测能力，为扫描流水线提供
「识别 → 标记 → 提示」能力：命中蜜罐只打标不阻断，避免假阳性与反侦察暴露。

设计原则：
- 纯数据识别可测试（detect_host 无网络 IO）
- 保守不误伤：仅 P0/P1 强信号标记 is_honeypot=True，P2 弱信号只记 evidence
- 复用设备指纹模块（device_fingerprint.py）的四段式结构
"""

import re
import logging
from typing import List, Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- 置信度排序（对齐 intel_sources 的 P0/P1/P2 约定） ----------
_CONFIDENCE_RANK = {'P0': 3, 'P1': 2, 'P2': 1}


# ---------- 签名库（第一代：签名/特征匹配） ----------
# 来源：honeydet / Nuclei honeypot 检测模板（可移植更新）。
# 字段说明：
#   honeypot   蜜罐名称
#   protocol   目标协议/服务（与端口 service 字段匹配）
#   field      匹配位置：banner 在纯数据阶段按 banner_text 匹配；
#              http_title / http_body 需带 IO 的增强探测，detect_host 会跳过
#   pattern    正则
#   confidence 置信度 P0(确定) / P1(强) / P2(弱)
#
# 注意：完整 18 类签名（Cowrie/Kippo/Dionaea/Conpot/Glastopf/Elastichoney/
# Honeyd/HoneyTrap/OpenCanary/T-Pot/Mailoney/Heralding/Amun/SNARE/Tanner/
# Gridpot 等）与多步 hex/string/regex 匹配，应从 honeydet 与 Nuclei 的
# 公开签名库移植。此处仅给出结构示例 + 常见高置信签名。
HONEYPOT_SIGNATURES: List[Dict[str, str]] = [
    # Cowrie / Kippo（SSH/Telnet 蜜罐）—— 默认版本串，管理员常不改
    {'honeypot': 'Cowrie', 'protocol': 'ssh', 'field': 'banner',
     'pattern': r'SSH-2\.0-OpenSSH_6\.0p1 Debian-4\+deb7u2', 'confidence': 'P1'},
    # Conpot（ICS/SCADA 蜜罐）—— 默认 Web 管理页标题/内容
    {'honeypot': 'Conpot', 'protocol': 'http', 'field': 'http_title',
     'pattern': r'(?i)conpot|simatic s7-1200|siemens cp', 'confidence': 'P1'},
    # Glastopf（Web 低交互蜜罐）—— 固定错误页特征
    {'honeypot': 'Glastopf', 'protocol': 'http', 'field': 'http_body',
     'pattern': r'(?i)glastopf|dionaea', 'confidence': 'P2'},
    # Dionaea（多协议蜜罐）—— 默认 HTTP 服务器标识
    {'honeypot': 'Dionaea', 'protocol': 'http', 'field': 'banner',
     'pattern': r'(?i)dionaea|python/2\.7', 'confidence': 'P2'},
    # OpenCanary（轻量多服务蜜罐）—— 默认 FTP banner
    {'honeypot': 'OpenCanary', 'protocol': 'ftp', 'field': 'banner',
     'pattern': r'(?i)opencanary|220 ftp', 'confidence': 'P2'},
]


# ---------- 服务组合签名（第二代：匹配密度/服务组合「过于齐全」） ----------
# 蜜罐常在一台主机上「演戏」出多种互不相干的服务；真实主机很少同时开放
# 这些组合，命中即视为强信号。
HONEYPOT_PORT_SIGNATURES: Dict[str, tuple] = {
    'Honeyd': (22, 80, 443, 21, 25),
    'OpenCanary': (22, 21, 80, 445, 3389),
    'T-Pot': (22, 21, 80, 445, 502, 9200),
}


class HoneypotDetector:
    """蜜罐/欺骗资产识别器 — 签名匹配 + 服务组合 + （可选）TCP 行为"""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    # ---------- 核心：纯数据识别（无网络 IO，可测试） ----------
    def detect_host(self, host: str, ports: List[Dict]) -> Dict[str, Any]:
        """识别单台主机是否为蜜罐。

        :param host: 主机 IP
        :param ports: nmap/socket 扫描返回的端口列表，每项含 port/service/version/product/state
        :return: 蜜罐识别结果 dict（is_honeypot/type/confidence/signals）
        """
        signals: List[Dict[str, str]] = []
        open_ports = set()

        for port_info in ports:
            if port_info.get('state') in ('closed', 'filtered'):
                continue
            port = port_info.get('port')
            if port is not None:
                open_ports.add(port)
            service = (port_info.get('service') or '').lower()
            product = port_info.get('product') or ''
            version = port_info.get('version') or ''
            banner_text = ' '.join([product, version, service])

            # 1) 横幅签名（纯数据阶段只匹配 field=='banner' 的签名；
            #    http_title/http_body 需带 IO 的增强探测，此处跳过避免死签名）
            for sig in HONEYPOT_SIGNATURES:
                if sig.get('field') != 'banner':
                    continue
                if sig['protocol'] != service:
                    continue
                if re.search(sig['pattern'], banner_text, re.IGNORECASE):
                    signals.append({
                        'honeypot': sig['honeypot'],
                        'confidence': sig['confidence'],
                        'evidence': f'横幅: {banner_text[:80]}',
                    })

        # 2) 服务组合签名
        for name, portset in HONEYPOT_PORT_SIGNATURES.items():
            if set(portset).issubset(open_ports):
                signals.append({
                    'honeypot': name,
                    'confidence': 'P1',
                    'evidence': f'服务组合异常: {sorted(portset)}',
                })

        if not signals:
            return self._empty_result(host)

        return self._build_result(host, signals)

    # ---------- 第三代：TCP 行为/时序指纹（实验性，预留接口） ----------
    def detect_tcp_behavior(self, host: str, ports: List[Dict]) -> Optional[Dict[str, Any]]:
        """TCP 时序/握手异常检测（对标 Minerva HDN）。

        当前为预留接口，返回 None（默认关闭）。后续可在此实现：
        - 握手异常：宣称有服务却不完成完整 TCP 三次握手
        - 时序统计：重试 RTT 分布异常均匀（模拟器特征）
        """
        return None

    # ---------- 结果构建 ----------
    @staticmethod
    def _empty_result(host: str) -> Dict[str, Any]:
        return {'host': host, 'is_honeypot': False, 'type': None,
                'confidence': None, 'signals': []}

    @staticmethod
    def _build_result(host: str, signals: List[Dict[str, str]]) -> Dict[str, Any]:
        """从多条信号中聚合出最优判断，按置信度择优。"""
        # 去重：同 honeypot 仅保留置信度最高的一条
        seen: Dict[str, Dict[str, str]] = {}
        for s in signals:
            key = s['honeypot']
            if key not in seen or _CONFIDENCE_RANK.get(s['confidence'], 0) > \
                    _CONFIDENCE_RANK.get(seen[key]['confidence'], 0):
                seen[key] = s
        deduped = list(seen.values())

        best = max(deduped, key=lambda s: _CONFIDENCE_RANK.get(s['confidence'], 0))
        # 保守原则：仅 P0/P1 标记为蜜罐，P2 只记录 evidence 供 AI 二次判断
        strong = _CONFIDENCE_RANK.get(best['confidence'], 0) >= _CONFIDENCE_RANK['P1']

        return {
            'host': host,
            'is_honeypot': strong,
            'type': best['honeypot'],
            'confidence': best['confidence'],
            'signals': deduped,
        }

    # ---------- 批量识别 ----------
    def detect_scan_result(self, scan_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """对扫描结果中的所有存活主机做蜜罐识别，回写 host_info['honeypot']。"""
        hits: List[Dict[str, Any]] = []
        for host_info in scan_result.get('hosts', []):
            if host_info.get('status') not in (None, 'up', 'open'):
                continue
            host = host_info.get('ip') or host_info.get('host', '')
            if not host:
                continue
            result = self.detect_host(host, host_info.get('ports', []))
            host_info['honeypot'] = result
            if result.get('is_honeypot'):
                hits.append(result)
        return hits


def generate_honeypot_findings(host: str, honeypot: Dict[str, Any],
                               ports: List[Dict]) -> List[Dict[str, Any]]:
    """根据蜜罐识别结果生成发现，结构与漏洞列表对齐，可直接并入 vulnerabilities。

    返回的 finding dict 与 device_fingerprint.generate_device_findings 同构，
    走同一套去重/富化/风险评分流水线。
    """
    hp_type = honeypot.get('type') or 'Unknown'
    confidence = honeypot.get('confidence') or 'P2'
    signals = honeypot.get('signals') or []
    evidence = signals[0].get('evidence', '') if signals else ''

    return [{
        'host': host,
        'port': None,
        'protocol': 'tcp',
        'service': '',
        'version': '',
        'product': '',
        'cve_id': None,
        'cve_name': None,
        'cvss_score': None,
        'severity': 'MEDIUM',
        'description': (
            f'[蜜罐告警] 目标疑似 {hp_type} 蜜罐/欺骗资产（置信度 {confidence}）。'
            f'该主机的服务响应可能为伪造，漏洞结果需谨慎采信，且扫描行为可能已被防御方记录。'
            f'证据: {evidence}'
        ),
        'affected_versions': '',
        'references_url': '',
        'honeypot_type': hp_type,
        'finding_type': 'honeypot',
    }]


__all__ = [
    'HONEYPOT_SIGNATURES', 'HONEYPOT_PORT_SIGNATURES',
    'HoneypotDetector', 'generate_honeypot_findings',
]
