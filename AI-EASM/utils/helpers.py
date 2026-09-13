# -*- coding: utf-8 -*-
"""工具函数"""
import re, ipaddress, uuid
from datetime import datetime

def validate_ip(ip_str):
    try: ipaddress.ip_address(ip_str.strip()); return True
    except ValueError: return False

def validate_ip_range(ip_range):
    ip_range = ip_range.strip()
    if '/' in ip_range:
        try: ipaddress.ip_network(ip_range, strict=False); return True
        except ValueError: return False
    if '-' in ip_range:
        parts = ip_range.split('-')
        if len(parts)==2: return validate_ip(parts[0]) and (parts[1].isdigit() or validate_ip(parts[1]))
    return validate_ip(ip_range)

def parse_port_string(port_str):
    ports = []
    for part in port_str.replace(' ','').split(','):
        if '-' in part:
            try:
                s,e = part.split('-'); ports.extend(range(int(s),int(e)+1))
            except: continue
        else:
            try: ports.append(int(part))
            except: continue
    return sorted(set(ports))

def parse_ip_range(ip_range):
    ips = []
    for part in ip_range.replace(' ','').split(','):
        part = part.strip()
        if '/' in part:
            try:
                net = ipaddress.ip_network(part, strict=False)
                ips.extend([str(ip) for ip in net.hosts()])
            except: continue
        elif '-' in part:
            p = part.split('-')
            if len(p)==2 and validate_ip(p[0]):
                try:
                    base = '.'.join(p[0].split('.')[:3])
                    start = int(p[0].split('.')[-1])
                    end = int(p[1]) if p[1].isdigit() else int(p[1].split('.')[-1])
                    ips.extend([f'{base}.{i}' for i in range(start,end+1)])
                except: continue
        elif validate_ip(part): ips.append(part)
    return ips

def format_timestamp(ts=None):
    return ts if ts else datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def generate_id(prefix=''):
    return f'{prefix}-{uuid.uuid4().hex[:12].upper()}' if prefix else uuid.uuid4().hex[:16].upper()

def severity_to_score(sev):
    m = {'CRITICAL':5,'HIGH':4,'MEDIUM':3,'LOW':2,'INFO':1}
    return m.get(sev.upper(),0)

def cvss_to_severity(score):
    if score>=9.0: return 'CRITICAL'
    if score>=7.0: return 'HIGH'
    if score>=4.0: return 'MEDIUM'
    if score>=0.1: return 'LOW'
    return 'INFO'
