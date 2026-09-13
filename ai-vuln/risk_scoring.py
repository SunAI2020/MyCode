# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 多因子风险评分模块

综合风险 = 资产价值 × 威胁(KEV/EPSS) × 脆弱性(CVSS) × 暴露面(可达性×网络暴露)，
归一化到 0-100，再映射到严重度等级。用于在 CVSS 数值之上叠加资产重要性、
真实威胁情报与漏洞可达性/暴露面（对标 Wiz 的可达性优先思路）。

暴露面系数默认 1.0（无信息不惩罚，保持向后兼容），仅在有明确信号时下调：
- 端口 state 为 closed/filtered → 服务不可达 → 0.1
- 主机为内网 IP → 0.7，本机回环 → 0.3，公网 → 1.0
"""
import ipaddress
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 资产价值系数（importance → 0-1）
ASSET_VALUE_FACTOR = {
    'CRITICAL': 1.0,
    'HIGH': 0.8,
    'MEDIUM': 0.6,
    'LOW': 0.4,
    'INFO': 0.2,
}

# 无 CVSS 时按严重度兜底的脆弱性系数
_SEV_VULN_FACTOR = {
    'CRITICAL': 0.9, 'HIGH': 0.7, 'MEDIUM': 0.5, 'LOW': 0.3, 'INFO': 0.1,
}
# 无 EPSS/KEV 时按严重度兜底的威胁系数
_SEV_THREAT_FACTOR = {
    'CRITICAL': 0.9, 'HIGH': 0.7, 'MEDIUM': 0.5, 'LOW': 0.3, 'INFO': 0.1,
}


def asset_value_factor(importance: Optional[str]) -> float:
    """资产价值系数"""
    return ASSET_VALUE_FACTOR.get((importance or 'MEDIUM').upper(), 0.6)


def threat_factor(vuln: Dict) -> float:
    """威胁系数：KEV 命中=1.0 > EPSS(0-1) > 严重度兜底"""
    if vuln.get('kev'):
        return 1.0
    epss = vuln.get('epss_score')
    if epss is None:
        epss = vuln.get('epss')
    if epss is not None:
        try:
            return max(0.0, min(1.0, float(epss)))
        except (TypeError, ValueError):
            pass
    return _SEV_THREAT_FACTOR.get(str(vuln.get('severity', 'INFO')).upper(), 0.3)


def vulnerability_factor(vuln: Dict) -> float:
    """脆弱性系数：CVSS/10，缺省用严重度兜底"""
    cvss = vuln.get('cvss_score')
    if cvss is not None:
        try:
            return max(0.0, min(1.0, float(cvss) / 10.0))
        except (TypeError, ValueError):
            pass
    return _SEV_VULN_FACTOR.get(str(vuln.get('severity', 'INFO')).upper(), 0.3)


# 网络暴露面系数：公网 > 内网 > 本机回环（对标 Wiz 暴露面优先级）
_NETWORK_EXPOSURE = {
    'public': 1.0,     # 公网可达，暴露面最大
    'private': 0.7,    # 仅内网可达，降低优先级
    'loopback': 0.3,   # 仅本机
    'unknown': 1.0,    # 域名/未知 → 不惩罚
}


def _network_exposure_from_host(host) -> float:
    """从主机 IP 推断网络暴露面系数；域名/非法 IP 返回中性 1.0。"""
    try:
        ip = ipaddress.ip_address(str(host).strip())
    except ValueError:
        return _NETWORK_EXPOSURE['unknown']
    if ip.is_loopback:
        return _NETWORK_EXPOSURE['loopback']
    if ip.is_private or ip.is_link_local or ip.is_reserved:
        return _NETWORK_EXPOSURE['private']
    return _NETWORK_EXPOSURE['public']


def exposure_factor(vuln: Dict) -> float:
    """暴露面系数 = 服务可达性 × 网络暴露面，取值 0-1。

    优先级：显式 exposure 字段 > 端口 state 可达性 × 主机网络暴露面。
    默认 1.0（无任何暴露面信息时不惩罚，保持向后兼容）。
    """
    # 1) 显式覆盖（exposure 可为 0-1 数值）
    exp = vuln.get('exposure')
    if exp is not None:
        try:
            return max(0.0, min(1.0, float(exp)))
        except (TypeError, ValueError):
            pass

    # 2) 服务可达性：关闭/过滤端口不可达
    reach = 1.0
    state = str(vuln.get('state', '')).lower()
    if state in ('closed', 'filtered'):
        reach = 0.1

    # 3) 网络暴露面：公网 1.0 / 内网 0.7 / 回环 0.3
    net = 1.0
    host = vuln.get('host')
    if host:
        net = _network_exposure_from_host(host)

    return reach * net


def risk_level(score: int) -> str:
    """评分 → 严重度等级"""
    if score >= 80:
        return 'CRITICAL'
    if score >= 60:
        return 'HIGH'
    if score >= 40:
        return 'MEDIUM'
    if score >= 20:
        return 'LOW'
    return 'INFO'


class RiskScorer:
    """多因子风险评分器 — 资产价值 × 威胁 × 脆弱性"""

    def score(self, vuln: Dict, asset_importance: str = 'MEDIUM') -> Dict:
        """对单条漏洞评分，返回 {risk_score, risk_level, factors}"""
        av = asset_value_factor(asset_importance)
        tf = threat_factor(vuln)
        vf = vulnerability_factor(vuln)
        ef = exposure_factor(vuln)
        score = int(round(av * tf * vf * ef * 100))
        return {
            'risk_score': score,
            'risk_level': risk_level(score),
            'factors': {'asset_value': av, 'threat': tf, 'vulnerability': vf, 'exposure': ef},
        }

    def score_many(self, vulns: List[Dict], asset_importance: str = 'MEDIUM') -> List[Dict]:
        """为漏洞列表附加 risk_score/risk_level，返回新列表（不改原对象）"""
        out = []
        for v in vulns:
            enriched = dict(v)
            r = self.score(v, asset_importance)
            enriched['risk_score'] = r['risk_score']
            enriched['risk_level'] = r['risk_level']
            out.append(enriched)
        return out
