# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 多类型设备专项检测模块

补齐 FR-11「多类型资产漏洞扫描」能力，针对五类资产做专项识别与风险检测：
  1. 网络设备      (NETWORK_DEVICE) 各品牌路由器 / 交换机 / 负载均衡
  2. 网络安全设备  (SECURITY_DEVICE) 各厂家防火墙 / IPS / WAF / UTM
  3. 物联网设备    (IOT)            摄像头 / 打印机 / 智能家居
  4. 工控设备      (OT)             PLC / SCADA / DCS / 工业协议
  5. 国产化系统    (DOMESTIC_OS)    麒麟 / 统信 / 达梦 / 人大金仓 / 欧拉 等

检测手段（由强到弱，保守原则，降低误报）：
  1. 端口签名    —— 工业协议 / 私有 SDK 端口等强特征端口（Modbus 502、S7comm 102、
                    BACnet 47808、达梦 5236、海康 8000、大华 37777 …）
  2. 横幅关键字  —— nmap -sV 的 product/version 字段中的厂商/产品关键词
  3. Web 管理界面指纹 —— 设备管理页 title/body/Server 头（可选，实时探测）

输出：设备分类（类别/厂商/产品/置信度/证据）+ 设备专项风险发现。

厂商/协议清单来源：《漏洞扫描系统需求规格说明书 v1.1》FR-11（多类型资产漏洞扫描）。
"""
import re
import logging
from typing import List, Dict, Optional, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _verify_for_url(url: str) -> bool:
    """按目标归属决定 TLS 证书校验：公网强制校验，内网关闭。

    复用 ssrf_guard 的地址归属判定；导入失败回退到不校验（旧行为）。
    """
    try:
        from ssrf_guard import tls_verify
        return tls_verify(url)
    except ImportError:
        return False

# ============================================================
# 1. 设备类别定义
# ============================================================
DEVICE_CATEGORIES: Dict[str, str] = {
    'NETWORK_DEVICE': '网络设备',
    'SECURITY_DEVICE': '网络安全设备',
    'IOT': '物联网设备',
    'OT': '工控设备',
    'DOMESTIC_OS': '国产化系统',
}

CATEGORY_LABELS: Dict[str, str] = {
    'NETWORK_DEVICE': '网络设备（路由器/交换机/负载均衡）',
    'SECURITY_DEVICE': '网络安全设备（防火墙/IPS/WAF/UTM）',
    'IOT': '物联网设备（摄像头/打印机/智能家居）',
    'OT': '工控设备（PLC/SCADA/DCS）',
    'DOMESTIC_OS': '国产化系统（麒麟/统信/达梦等）',
}

# 置信度排序权重（用于多信号聚合时择优）
_CONFIDENCE_RANK = {'high': 3, 'medium': 2, 'low': 1}


# ============================================================
# 2. 端口签名（强特征端口 → 设备线索）
# 仅收录协议特异性强、误报率低的端口；SNMP/SSH/Telnet 等通用端口不在此列。
# ============================================================
PORT_SIGNATURES: Dict[int, List[Dict[str, str]]] = {
    # ---- 工控 OT / 工业协议 ----
    502:    [{'vendor': 'Modbus', 'product': 'Modbus TCP', 'category': 'OT', 'confidence': 'high'}],
    102:    [{'vendor': 'Siemens', 'product': 'S7comm PLC', 'category': 'OT', 'confidence': 'high'}],
    44818:  [{'vendor': 'Rockwell/Allen-Bradley', 'product': 'EtherNet/IP', 'category': 'OT', 'confidence': 'high'}],
    47808:  [{'vendor': 'BACnet', 'product': 'BACnet/IP 楼宇自控', 'category': 'OT', 'confidence': 'high'}],
    20000:  [{'vendor': 'DNP3', 'product': 'DNP3 SCADA', 'category': 'OT', 'confidence': 'high'}],
    2404:   [{'vendor': 'IEC 60870-5-104', 'product': '电力远动规约', 'category': 'OT', 'confidence': 'high'}],
    4840:   [{'vendor': 'OPC UA', 'product': 'OPC UA 工业协议', 'category': 'OT', 'confidence': 'medium'}],
    34962:  [{'vendor': 'Profinet', 'product': 'PROFINET 工业以太网', 'category': 'OT', 'confidence': 'medium'}],
    34964:  [{'vendor': 'Profinet', 'product': 'PROFINET 工业以太网', 'category': 'OT', 'confidence': 'medium'}],
    789:    [{'vendor': 'Red Lion', 'product': 'Crimson 工业协议', 'category': 'OT', 'confidence': 'low'}],
    1911:   [{'vendor': 'Niagara', 'product': 'Niagara Fox 工业协议', 'category': 'OT', 'confidence': 'low'}],
    4911:   [{'vendor': 'Niagara', 'product': 'Niagara Fox 工业协议', 'category': 'OT', 'confidence': 'low'}],
    # ---- 国产化系统 / 国产数据库 ----
    5236:   [{'vendor': '达梦 DM', 'product': '达梦数据库 (DM)', 'category': 'DOMESTIC_OS', 'confidence': 'high'}],
    54321:  [{'vendor': '人大金仓', 'product': 'KingbaseES 数据库', 'category': 'DOMESTIC_OS', 'confidence': 'medium'}],
    # ---- 物联网设备 / 摄像头 / 打印机 ----
    8000:   [{'vendor': '海康威视', 'product': '海康威视设备 (SDK/Web)', 'category': 'IOT', 'confidence': 'medium'}],
    37777:  [{'vendor': '大华', 'product': '大华 DVR/NVR', 'category': 'IOT', 'confidence': 'high'}],
    34567:  [{'vendor': '大华', 'product': '大华设备', 'category': 'IOT', 'confidence': 'medium'}],
    554:    [{'vendor': 'RTSP', 'product': '网络摄像头 / 视频监控 (RTSP)', 'category': 'IOT', 'confidence': 'medium'}],
    9000:   [{'vendor': '海康威视', 'product': '海康威视 SDK', 'category': 'IOT', 'confidence': 'medium'}],
    9100:   [{'vendor': '打印机', 'product': '网络打印机 (raw 9100)', 'category': 'IOT', 'confidence': 'high'}],
    515:    [{'vendor': '打印机', 'product': '网络打印机 (LPR)', 'category': 'IOT', 'confidence': 'medium'}],
    631:    [{'vendor': '打印机', 'product': '网络打印机 (IPP)', 'category': 'IOT', 'confidence': 'medium'}],
    # ---- 网络设备（协议特异性端口）----
    4786:   [{'vendor': 'Cisco', 'product': 'Cisco Smart Install', 'category': 'NETWORK_DEVICE', 'confidence': 'high'}],
    830:    [{'vendor': 'NETCONF', 'product': '网络设备 NETCONF 管理接口', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'}],
    2222:   [{'vendor': '网络设备', 'product': 'SSH 备用管理端口', 'category': 'NETWORK_DEVICE', 'confidence': 'low'}],
    10001:  [{'vendor': '华为', 'product': '华为设备管理 (UniMgr/HTTP)', 'category': 'NETWORK_DEVICE', 'confidence': 'low'}],
}


# ============================================================
# 3. 横幅关键字签名（product/version 关键词 → 设备线索）
# 匹配对象：nmap -sV 返回的 product、version、service 字段（小写）。
# ============================================================
BANNER_SIGNATURES: List[Dict[str, str]] = [
    # ---- 网络设备 ----
    {'keyword': 'cisco ios', 'vendor': 'Cisco', 'product': 'Cisco IOS 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'ios-xe', 'vendor': 'Cisco', 'product': 'Cisco IOS-XE', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'nx-os', 'vendor': 'Cisco', 'product': 'Cisco NX-OS', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'asa', 'vendor': 'Cisco', 'product': 'Cisco ASA', 'category': 'SECURITY_DEVICE', 'confidence': 'medium'},
    {'keyword': 'cisco', 'vendor': 'Cisco', 'product': 'Cisco 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'juniper', 'vendor': 'Juniper', 'product': 'Juniper 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'junos', 'vendor': 'Juniper', 'product': 'Junos OS 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'huawei vrp', 'vendor': '华为', 'product': '华为 VRP 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'vrp ', 'vendor': '华为', 'product': '华为 VRP 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'huawei', 'vendor': '华为', 'product': '华为设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'h3c', 'vendor': 'H3C', 'product': 'H3C 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'comware', 'vendor': 'H3C', 'product': 'H3C Comware 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'ruijie', 'vendor': '锐捷', 'product': '锐捷设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'zte', 'vendor': '中兴', 'product': '中兴设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'zxr10', 'vendor': '中兴', 'product': '中兴 ZXR10 路由交换', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'mikrotik', 'vendor': 'MikroTik', 'product': 'MikroTik RouterOS', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'routeros', 'vendor': 'MikroTik', 'product': 'MikroTik RouterOS', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'tp-link', 'vendor': 'TP-Link', 'product': 'TP-Link 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'tplink', 'vendor': 'TP-Link', 'product': 'TP-Link 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'd-link', 'vendor': 'D-Link', 'product': 'D-Link 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'netgear', 'vendor': 'Netgear', 'product': 'Netgear 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'ubiquiti', 'vendor': 'Ubiquiti', 'product': 'Ubiquiti 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'edgeos', 'vendor': 'Ubiquiti', 'product': 'Ubiquiti EdgeOS', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'big-ip', 'vendor': 'F5', 'product': 'F5 BIG-IP', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'f5 networks', 'vendor': 'F5', 'product': 'F5 BIG-IP', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'keyword': 'aruba', 'vendor': 'Aruba', 'product': 'Aruba 网络设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'brocade', 'vendor': 'Brocade', 'product': 'Brocade 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'keyword': 'sonicwall', 'vendor': 'SonicWall', 'product': 'SonicWall 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},

    # ---- 网络安全设备 ----
    {'keyword': 'fortigate', 'vendor': 'Fortinet', 'product': 'FortiGate 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'fortios', 'vendor': 'Fortinet', 'product': 'FortiGate 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'fortinet', 'vendor': 'Fortinet', 'product': 'Fortinet 安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'medium'},
    {'keyword': 'palo alto', 'vendor': 'Palo Alto', 'product': 'Palo Alto 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'pan-os', 'vendor': 'Palo Alto', 'product': 'Palo Alto PAN-OS', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'check point', 'vendor': 'Check Point', 'product': 'Check Point 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'checkpoint', 'vendor': 'Check Point', 'product': 'Check Point 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'sophos', 'vendor': 'Sophos', 'product': 'Sophos 安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'medium'},
    {'keyword': 'watchguard', 'vendor': 'WatchGuard', 'product': 'WatchGuard 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'medium'},
    {'keyword': 'barracuda', 'vendor': 'Barracuda', 'product': 'Barracuda 安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'medium'},
    {'keyword': 'imperva', 'vendor': 'Imperva', 'product': 'Imperva WAF', 'category': 'SECURITY_DEVICE', 'confidence': 'medium'},
    {'keyword': 'sangfor', 'vendor': '深信服', 'product': '深信服安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': '深信服', 'vendor': '深信服', 'product': '深信服安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'topsec', 'vendor': '天融信', 'product': '天融信安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': '天融信', 'vendor': '天融信', 'product': '天融信安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'hillstone', 'vendor': '山石网科', 'product': '山石网科防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': '山石', 'vendor': '山石网科', 'product': '山石网科防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'nsfocus', 'vendor': '绿盟科技', 'product': '绿盟安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': '绿盟', 'vendor': '绿盟科技', 'product': '绿盟安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'venustech', 'vendor': '启明星辰', 'product': '启明星辰安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': '启明星辰', 'vendor': '启明星辰', 'product': '启明星辰安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'qianxin', 'vendor': '奇安信', 'product': '奇安信安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': '奇安信', 'vendor': '奇安信', 'product': '奇安信安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'usg', 'vendor': '华为', 'product': '华为 USG 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'medium'},
    {'keyword': 'huawei usg', 'vendor': '华为', 'product': '华为 USG 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': 'symantec', 'vendor': '赛门铁克', 'product': '赛门铁克安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'keyword': '赛门铁克', 'vendor': '赛门铁克', 'product': '赛门铁克安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},

    # ---- 物联网设备 ----
    {'keyword': 'hikvision', 'vendor': '海康威视', 'product': '海康威视摄像头', 'category': 'IOT', 'confidence': 'high'},
    {'keyword': '海康威视', 'vendor': '海康威视', 'product': '海康威视摄像头', 'category': 'IOT', 'confidence': 'high'},
    {'keyword': 'dahua', 'vendor': '大华', 'product': '大华摄像头/DVR', 'category': 'IOT', 'confidence': 'high'},
    {'keyword': '大华', 'vendor': '大华', 'product': '大华摄像头/DVR', 'category': 'IOT', 'confidence': 'high'},
    {'keyword': 'uniview', 'vendor': '宇视', 'product': '宇视摄像头', 'category': 'IOT', 'confidence': 'high'},
    {'keyword': '宇视', 'vendor': '宇视', 'product': '宇视摄像头', 'category': 'IOT', 'confidence': 'high'},
    {'keyword': 'axis', 'vendor': 'Axis', 'product': 'Axis 网络摄像头', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'xiaomi', 'vendor': '小米', 'product': '小米智能设备', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': '小米', 'vendor': '小米', 'product': '小米智能设备', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'tuya', 'vendor': '涂鸦智能', 'product': '涂鸦智能设备', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': '涂鸦', 'vendor': '涂鸦智能', 'product': '涂鸦智能设备', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'sonoff', 'vendor': 'Sonoff', 'product': 'Sonoff 智能家居', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'broadlink', 'vendor': 'BroadLink', 'product': 'BroadLink 智能家居', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'jetdirect', 'vendor': 'HP', 'product': 'HP 打印机 (JetDirect)', 'category': 'IOT', 'confidence': 'high'},
    {'keyword': 'hp printer', 'vendor': 'HP', 'product': 'HP 打印机', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'canon', 'vendor': 'Canon', 'product': 'Canon 打印机', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'epson', 'vendor': 'Epson', 'product': 'Epson 打印机', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'brother', 'vendor': 'Brother', 'product': 'Brother 打印机', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'ricoh', 'vendor': 'Ricoh', 'product': 'Ricoh 打印机', 'category': 'IOT', 'confidence': 'medium'},
    {'keyword': 'xerox', 'vendor': 'Xerox', 'product': 'Xerox 打印机', 'category': 'IOT', 'confidence': 'medium'},

    # ---- 工控设备（厂商横幅）----
    {'keyword': 'simatic', 'vendor': 'Siemens', 'product': 'Siemens SIMATIC PLC', 'category': 'OT', 'confidence': 'high'},
    {'keyword': 's7-', 'vendor': 'Siemens', 'product': 'Siemens S7 PLC', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'siemens', 'vendor': 'Siemens', 'product': 'Siemens 工控设备', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'modicon', 'vendor': 'Schneider', 'product': 'Schneider Modicon PLC', 'category': 'OT', 'confidence': 'high'},
    {'keyword': 'schneider', 'vendor': 'Schneider', 'product': 'Schneider 工控设备', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'rockwell', 'vendor': 'Rockwell', 'product': 'Rockwell 工控设备', 'category': 'OT', 'confidence': 'high'},
    {'keyword': 'allen-bradley', 'vendor': 'Allen-Bradley', 'product': 'Allen-Bradley PLC', 'category': 'OT', 'confidence': 'high'},
    {'keyword': 'omron', 'vendor': 'Omron', 'product': 'Omron PLC', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'mitsubishi', 'vendor': '三菱', 'product': '三菱 PLC (MELSEC)', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'melsec', 'vendor': '三菱', 'product': '三菱 MELSEC PLC', 'category': 'OT', 'confidence': 'high'},
    {'keyword': 'abb', 'vendor': 'ABB', 'product': 'ABB 工控设备', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'beckhoff', 'vendor': 'Beckhoff', 'product': 'Beckhoff 工控设备', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'advantech', 'vendor': '研华', 'product': '研华工控设备', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'moxa', 'vendor': 'Moxa', 'product': 'Moxa 工业网络设备', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'hirschmann', 'vendor': 'Hirschmann', 'product': 'Hirschmann 工业交换机', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'phoenix contact', 'vendor': 'Phoenix Contact', 'product': 'Phoenix Contact 工控设备', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'wago', 'vendor': 'WAGO', 'product': 'WAGO PLC', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'delta', 'vendor': '台达', 'product': '台达 PLC', 'category': 'OT', 'confidence': 'low'},
    {'keyword': 'iec 61850', 'vendor': 'IEC 61850', 'product': 'IEC 61850 电力自动化 (MMS)', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': '61850', 'vendor': 'IEC 61850', 'product': 'IEC 61850 电力自动化', 'category': 'OT', 'confidence': 'low'},
    {'keyword': 'profibus', 'vendor': 'Profibus', 'product': 'Profibus 现场总线 (DCS)', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'foundation fieldbus', 'vendor': 'Foundation Fieldbus', 'product': 'Foundation Fieldbus 现场总线 (DCS)', 'category': 'OT', 'confidence': 'medium'},
    {'keyword': 'fieldbus', 'vendor': 'Fieldbus', 'product': '工业现场总线 (DCS)', 'category': 'OT', 'confidence': 'low'},

    # ---- 国产化系统 / 国产软件 ----
    {'keyword': 'dm database', 'vendor': '达梦 DM', 'product': '达梦数据库 (DM)', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'dm8', 'vendor': '达梦 DM', 'product': '达梦数据库 (DM8)', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': '达梦', 'vendor': '达梦 DM', 'product': '达梦数据库', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'kingbase', 'vendor': '人大金仓', 'product': '人大金仓 KingbaseES', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': '人大金仓', 'vendor': '人大金仓', 'product': '人大金仓数据库', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': '中标麒麟', 'vendor': '麒麟软件', 'product': '中标麒麟操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': '银河麒麟', 'vendor': '麒麟软件', 'product': '银河麒麟操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'kylin', 'vendor': '麒麟软件', 'product': '麒麟 (Kylin) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': '麒麟', 'vendor': '麒麟软件', 'product': '麒麟操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': '统信', 'vendor': '统信软件', 'product': '统信 UOS 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'uos', 'vendor': '统信软件', 'product': '统信 UOS 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': 'deepin', 'vendor': '统信软件', 'product': '深度 (deepin) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': 'openeuler', 'vendor': '华为', 'product': 'openEuler 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'euler', 'vendor': '华为', 'product': '欧拉 (Euler) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': '欧拉', 'vendor': '华为', 'product': '欧拉操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': 'anolis', 'vendor': '龙蜥社区', 'product': '龙蜥 (Anolis) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': '龙蜥', 'vendor': '龙蜥社区', 'product': '龙蜥操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': '凝思', 'vendor': '凝思软件', 'product': '凝思 (Linx) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'linx', 'vendor': '凝思软件', 'product': '凝思 (Linx) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': '红旗', 'vendor': '红旗软件', 'product': '红旗 (RedFlag) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'redflag', 'vendor': '红旗软件', 'product': '红旗 (RedFlag) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': '中兴新支点', 'vendor': '中兴', 'product': '中兴新支点 (NewStart) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'newstart', 'vendor': '中兴', 'product': '中兴新支点 (NewStart) 操作系统', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': '神通', 'vendor': '神通', 'product': '神通数据库 (OSCAR)', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'oscar', 'vendor': '神通', 'product': '神通数据库 (OSCAR)', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
    {'keyword': '南大通用', 'vendor': '南大通用', 'product': '南大通用 GBase 数据库', 'category': 'DOMESTIC_OS', 'confidence': 'high'},
    {'keyword': 'gbase', 'vendor': '南大通用', 'product': '南大通用 GBase 数据库', 'category': 'DOMESTIC_OS', 'confidence': 'medium'},
]


# ============================================================
# 4. Web 管理界面指纹（实时 HTTP 探测，可选增强）
# ============================================================
HTTP_SIGNATURES: List[Dict[str, str]] = [
    # (匹配位置 title|body|server, 正则, 厂商, 产品, 类别, 置信度)
    {'where': 'title', 'pattern': r'海康威视|hikvision', 'vendor': '海康威视', 'product': '海康威视摄像头', 'category': 'IOT', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'Dahua|大华', 'vendor': '大华', 'product': '大华摄像头/DVR', 'category': 'IOT', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'TP-LINK|TP-Link', 'vendor': 'TP-Link', 'product': 'TP-Link 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'D-Link|Dlink', 'vendor': 'D-Link', 'product': 'D-Link 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'NETGEAR', 'vendor': 'Netgear', 'product': 'Netgear 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'Cisco', 'vendor': 'Cisco', 'product': 'Cisco 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'where': 'title', 'pattern': r'HUAWEI|华为', 'vendor': '华为', 'product': '华为设备', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
    {'where': 'title', 'pattern': r'H3C', 'vendor': 'H3C', 'product': 'H3C 设备', 'category': 'NETWORK_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'FortiGate|Fortinet', 'vendor': 'Fortinet', 'product': 'FortiGate 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'Palo Alto', 'vendor': 'Palo Alto', 'product': 'Palo Alto 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'Check Point', 'vendor': 'Check Point', 'product': 'Check Point 防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'SANGFOR|深信服', 'vendor': '深信服', 'product': '深信服安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'天融信|TOPSEC', 'vendor': '天融信', 'product': '天融信安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'Hillstone|山石', 'vendor': '山石网科', 'product': '山石网科防火墙', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'绿盟|NSFOCUS', 'vendor': '绿盟科技', 'product': '绿盟安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'奇安信|Qianxin', 'vendor': '奇安信', 'product': '奇安信安全设备', 'category': 'SECURITY_DEVICE', 'confidence': 'high'},
    {'where': 'title', 'pattern': r'VMware|vSphere', 'vendor': 'VMware', 'product': 'VMware 虚拟化', 'category': 'NETWORK_DEVICE', 'confidence': 'medium'},
]


# ============================================================
# 5. 设备专项风险规则（开放端口暴露 → 风险发现）
# ============================================================
PORT_RISK_RULES: Dict[int, Dict[str, str]] = {
    502: {
        'severity': 'HIGH', 'title': 'Modbus TCP 工业协议暴露',
        'description': 'Modbus TCP (端口502) 对外可达，协议本身无认证机制，攻击者可读写 PLC 寄存器/线圈，导致工业过程被操控。',
        'remediation': '将 Modbus 端口隔离在工控内网，部署工业防火墙/网关做协议深度检测与白名单访问控制。',
    },
    102: {
        'severity': 'HIGH', 'title': '西门子 S7comm PLC 暴露',
        'description': '西门子 S7comm (端口102) 对外可达，攻击者可连接 PLC 进行启停、程序上传下载等未授权操作。',
        'remediation': '隔离 PLC 于 OT 网络，禁用远程编程端口，使用 S7 认证与网络分段。',
    },
    44818: {
        'severity': 'HIGH', 'title': 'EtherNet/IP 工业协议暴露',
        'description': 'EtherNet/IP (端口44818) 对外可达，可用于未授权读写 Allen-Bradley 等控制器标签数据。',
        'remediation': '隔离 EtherNet/IP 流量于工控网段，限制 CIP 连接源地址。',
    },
    47808: {
        'severity': 'MEDIUM', 'title': 'BACnet/IP 楼宇自控协议暴露',
        'description': 'BACnet/IP (端口47808) 对外可达，攻击者可能控制 HVAC、门禁等楼宇自动化系统。',
        'remediation': '将 BACnet 网络隔离，限制 BACnet 广播域与访问来源。',
    },
    20000: {
        'severity': 'HIGH', 'title': 'DNP3 SCADA 协议暴露',
        'description': 'DNP3 (端口20000) 对外可达，电力/水务 SCADA 主站-终端通信暴露，存在被操控风险。',
        'remediation': '隔离 DNP3 于 SCADA 专网，启用 DNP3 Secure Authentication。',
    },
    2404: {
        'severity': 'HIGH', 'title': 'IEC 60870-5-104 电力远动协议暴露',
        'description': 'IEC 104 (端口2404) 对外可达，电力调度自动化远动通信暴露。',
        'remediation': '隔离于调度数据专网，部署纵向加密认证装置。',
    },
    4840: {
        'severity': 'MEDIUM', 'title': 'OPC UA 工业协议暴露',
        'description': 'OPC UA (端口4840) 对外可达，工业数据采集与监控接口暴露，可能泄露工艺数据。',
        'remediation': '启用 OPC UA 证书认证与加密，限制访问来源。',
    },
    4786: {
        'severity': 'HIGH', 'title': 'Cisco Smart Install 未授权访问',
        'description': 'Cisco Smart Install (端口4786) 开放，存在 CVE-2018-0171 等未授权配置下发风险。',
        'remediation': '执行 "no vstack" 关闭 Smart Install 服务，或在接口 ACL 中限制该端口。',
    },
    5236: {
        'severity': 'HIGH', 'title': '达梦数据库 (DM) 端口暴露',
        'description': '达梦数据库默认端口 5236 对外可达，可能遭受未授权连接或弱口令暴力破解。',
        'remediation': '限制数据库端口访问来源，禁用默认账号 SYSDBA 弱口令，启用安全审计。',
    },
    554: {
        'severity': 'MEDIUM', 'title': 'RTSP 视频流暴露',
        'description': 'RTSP (端口554) 对外可达，未授权用户可能实时查看摄像头视频流。',
        'remediation': '为摄像头启用 RTSP 认证，限制访问来源，关闭公网暴露。',
    },
    9100: {
        'severity': 'MEDIUM', 'title': '打印机 raw 端口 (9100) 暴露',
        'description': '打印机 9100 端口对外可达，存在未授权打印/打印机固件攻击风险。',
        'remediation': '限制打印端口访问，部署打印服务器统一管控。',
    },
    515: {
        'severity': 'LOW', 'title': '打印机 LPR 端口 (515) 暴露',
        'description': '打印机 LPR 端口对外可达，存在未授权打印风险。',
        'remediation': '限制 LPR 端口访问来源。',
    },
    631: {
        'severity': 'LOW', 'title': '打印机 IPP 端口 (631) 暴露',
        'description': '打印机 IPP 端口对外可达，可能泄露打印队列与设备信息。',
        'remediation': '限制 IPP 端口访问，关闭不必要的打印协议。',
    },
}


# 厂商默认口令风险提示（仅提示需核验，不直接判漏洞，避免误报）
VENDOR_DEFAULT_CRED_HINTS: Dict[str, Dict[str, str]] = {
    '海康威视': {'severity': 'MEDIUM', 'title': '海康威视设备可能存在默认口令',
                 'description': '海康威视设备默认口令 (admin/12345 等) 若未修改，可被未授权接管。',
                 'remediation': '核查并修改默认口令，启用强密码策略与固件升级。'},
    '大华': {'severity': 'MEDIUM', 'title': '大华设备可能存在默认口令',
             'description': '大华设备默认口令 (admin/admin 等) 若未修改，可被未授权接管。',
             'remediation': '核查并修改默认口令，关闭不必要的网络服务。'},
    'Cisco': {'severity': 'MEDIUM', 'title': 'Cisco 设备可能存在默认口令',
              'description': 'Cisco 设备若保留默认口令或启用未加固的 telnet/SNMP，存在被接管风险。',
              'remediation': '核查口令策略，关闭 telnet，启用 SSH 与 AAA 认证。'},
    '华为': {'severity': 'MEDIUM', 'title': '华为设备可能存在默认口令',
             'description': '华为设备默认口令 (admin/Admin@huawei 等) 若未修改，存在被接管风险。',
             'remediation': '核查并修改默认口令，关闭不必要的管理端口。'},
    'Siemens': {'severity': 'MEDIUM', 'title': '西门子 PLC 可能存在默认口令',
                'description': '西门子 PLC 若未设置访问保护，可被未授权程序读写。',
                'remediation': '启用 PLC 访问保护与口令，隔离编程接口。'},
    'TP-Link': {'severity': 'LOW', 'title': 'TP-Link 设备可能存在默认口令',
                'description': 'TP-Link 设备默认口令 (admin/admin) 若未修改，存在被接管风险。',
                'remediation': '核查并修改默认口令，升级固件。'},
    'D-Link': {'severity': 'LOW', 'title': 'D-Link 设备可能存在默认口令',
               'description': 'D-Link 设备默认口令若未修改，存在被接管风险。',
               'remediation': '核查并修改默认口令，升级固件。'},
    'Netgear': {'severity': 'LOW', 'title': 'Netgear 设备可能存在默认口令',
                'description': 'Netgear 设备默认口令 (admin/password) 若未修改，存在被接管风险。',
                'remediation': '核查并修改默认口令，升级固件。'},
}


def _lower(s: Any) -> str:
    return (s or '').lower()


class DeviceFingerprinter:
    """多类型设备指纹识别器 — 端口签名 + 横幅关键字 + （可选）Web 管理界面探测"""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    # ---------- 核心：纯数据识别（无网络 IO，可测试） ----------
    def identify_host(self, host: str, ports: List[Dict]) -> Dict[str, Any]:
        """识别单台主机的设备类型。

        :param host: 主机 IP
        :param ports: nmap/socket 扫描返回的端口列表，每项含 port/service/version/product
        :return: 设备分类结果 dict
        """
        signals: List[Dict[str, str]] = []

        for port_info in ports:
            if port_info.get('state') == 'closed':
                continue
            port = port_info.get('port')
            # port 可能为字符串（DB/JSON 往返），统一转 int 以命中 int 键的签名表
            try:
                port = int(port)
            except (TypeError, ValueError):
                port = None
            service = port_info.get('service', '')
            version = port_info.get('version', '')
            product = port_info.get('product', '')

            # 1) 端口签名
            if port in PORT_SIGNATURES:
                for sig in PORT_SIGNATURES[port]:
                    signals.append({**sig, 'evidence': f'端口 {port} ({service})'})

            # 2) 横幅关键字签名（product/version/service 综合匹配）
            banner_text = ' '.join([product, version, service])
            for sig in BANNER_SIGNATURES:
                if sig['keyword'] in _lower(banner_text):
                    signals.append({**sig, 'evidence': f'横幅: {banner_text[:80]}'})

        if not signals:
            return self._empty_result(host)

        return self._build_result(host, signals)

    def identify_host_with_http(self, host: str, ports: List[Dict]) -> Dict[str, Any]:
        """识别主机设备类型（含 Web 管理界面实时探测增强）。"""
        result = self.identify_host(host, ports)
        if result.get('category'):
            return result

        # 仅当横幅/端口未识别出设备时，探测 Web 管理界面（80/443/8080/8443/8000）
        for port_info in ports:
            if port_info.get('state') == 'closed':
                continue
            port = port_info.get('port')
            if port not in (80, 443, 8080, 8443, 8000):
                continue
            scheme = 'https' if port in (443, 8443) else 'http'
            sig = self._http_probe(host, port, scheme)
            if sig:
                result = self._build_result(host, [sig])
                break
        return result

    # ---------- Web 管理界面指纹 ----------
    def _http_probe(self, host: str, port: int, scheme: str) -> Optional[Dict[str, str]]:
        """探测单个 Web 管理端口，返回命中的设备签名（未命中返回 None）。"""
        try:
            import requests
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except ImportError:
            return None

        url = f'{scheme}://{host}:{port}/'
        try:
            resp = requests.get(url, timeout=self.timeout, verify=_verify_for_url(url),
                                allow_redirects=False,
                                headers={'User-Agent': 'AI-Vuln-Scanner/2.1'})
        except requests.RequestException:
            return None

        title = self._extract_title(resp.text)
        server = resp.headers.get('Server', '')
        body = resp.text[:20000]

        for sig in HTTP_SIGNATURES:
            where = sig['where']
            if where == 'title' and title and re.search(sig['pattern'], title, re.IGNORECASE):
                return {k: sig[k] for k in ('vendor', 'product', 'category', 'confidence')} \
                    | {'evidence': f'Web标题: {title[:80]}'}
            if where == 'server' and re.search(sig['pattern'], server, re.IGNORECASE):
                return {k: sig[k] for k in ('vendor', 'product', 'category', 'confidence')} \
                    | {'evidence': f'Server: {server[:80]}'}
            if where == 'body' and re.search(sig['pattern'], body, re.IGNORECASE):
                return {k: sig[k] for k in ('vendor', 'product', 'category', 'confidence')} \
                    | {'evidence': f'Web内容匹配: {sig["pattern"]}'}
        return None

    @staticmethod
    def _extract_title(body: str) -> str:
        m = re.search(r'<title[^>]*>(.*?)</title>', body, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip()[:200] if m else ''

    # ---------- 结果构建 ----------
    @staticmethod
    def _empty_result(host: str) -> Dict[str, Any]:
        return {'host': host, 'category': None, 'category_label': None,
                'vendor': None, 'product': None, 'confidence': None, 'signals': []}

    @staticmethod
    def _build_result(host: str, signals: List[Dict[str, str]]) -> Dict[str, Any]:
        """从多条信号中聚合出最佳设备分类。"""
        # 去重：同 (vendor, product) 仅保留置信度最高的一条
        seen: Dict[Tuple[str, str], Dict[str, str]] = {}
        for s in signals:
            key = (s['vendor'], s['product'])
            if key not in seen or _CONFIDENCE_RANK.get(s['confidence'], 0) > \
                    _CONFIDENCE_RANK.get(seen[key]['confidence'], 0):
                seen[key] = s
        deduped = list(seen.values())

        # 按置信度降序，取最优
        best = max(deduped, key=lambda s: _CONFIDENCE_RANK.get(s['confidence'], 0))

        return {
            'host': host,
            'category': best['category'],
            'category_label': CATEGORY_LABELS.get(best['category'], best['category']),
            'vendor': best['vendor'],
            'product': best['product'],
            'confidence': best['confidence'],
            'signals': deduped,
        }

    # ---------- 批量识别 ----------
    def identify_scan_result(self, scan_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """对扫描结果中的所有存活主机做设备识别，返回设备分类列表。

        同时将识别结果回写到各 host_info['device'] 字段。
        """
        devices: List[Dict[str, Any]] = []
        for host_info in scan_result.get('hosts', []):
            if host_info.get('status') not in (None, 'up', 'open'):
                continue
            host = host_info.get('ip') or host_info.get('host', '')
            if not host:
                continue
            device = self.identify_host(host, host_info.get('ports', []))
            host_info['device'] = device
            if device.get('category'):
                devices.append(device)
        return devices


def generate_device_findings(host: str, device: Dict[str, Any],
                             ports: List[Dict]) -> List[Dict[str, Any]]:
    """根据设备识别结果 + 开放端口，生成设备专项风险发现。

    返回的 finding dict 与漏洞列表结构对齐，可直接并入扫描漏洞结果。
    """
    findings: List[Dict[str, Any]] = []
    category = device.get('category')
    vendor = device.get('vendor') or ''
    product = device.get('product') or ''

    # 1) 开放端口暴露风险（协议特异性端口）
    for port_info in ports:
        if port_info.get('state') == 'closed':
            continue
        port = port_info.get('port')
        if port in PORT_RISK_RULES:
            rule = PORT_RISK_RULES[port]
            findings.append({
                'host': host, 'port': port,
                'protocol': port_info.get('protocol', 'tcp'),
                'service': port_info.get('service', ''),
                'version': port_info.get('version', '') or port_info.get('product', ''),
                'product': product,
                'cve_id': None, 'cve_name': None, 'cvss_score': None,
                'severity': rule['severity'],
                'description': f"[{rule['title']}] {rule['description']} 修复建议: {rule['remediation']}",
                'affected_versions': '', 'references_url': '',
                'device_type': category, 'vendor': vendor,
                'finding_type': 'device',
            })

    # 2) 厂商默认口令风险提示（仅提示核验）
    if vendor and vendor in VENDOR_DEFAULT_CRED_HINTS:
        hint = VENDOR_DEFAULT_CRED_HINTS[vendor]
        findings.append({
            'host': host, 'port': None,
            'protocol': 'tcp', 'service': '', 'version': '',
            'product': product,
            'cve_id': None, 'cve_name': None, 'cvss_score': None,
            'severity': hint['severity'],
            'description': f"[{hint['title']}] {hint['description']} 修复建议: {hint['remediation']}",
            'affected_versions': '', 'references_url': '',
            'device_type': category, 'vendor': vendor,
            'finding_type': 'device',
        })

    return findings


__all__ = [
    'DEVICE_CATEGORIES', 'CATEGORY_LABELS',
    'PORT_SIGNATURES', 'BANNER_SIGNATURES', 'HTTP_SIGNATURES',
    'PORT_RISK_RULES', 'VENDOR_DEFAULT_CRED_HINTS',
    'DeviceFingerprinter', 'generate_device_findings',
]
