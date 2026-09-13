# -*- coding: utf-8 -*-
"""目标域名真实归属核验 — 输出 DNS/WHOIS/ICP/SSL/crt.sh 结论（联网，需放行 whois:43 与 HTTPS 出站）

用法: python scripts/verify_domains.py
"""
import os, sys, socket
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.org_manager import OrgManager
from core.enrichment_engine import EnrichmentEngine

TARGET_DOMAINS = [
    "sxszyczs.com", "singlewindow.sx.cn", "shanxixinyong.com",
    "sxkjdspt.com", "swt.shanxi.gov.cn", "shanxi.gov.cn",
]
ORG_NAME = "山西省商务厅"


def main():
    org_mgr = OrgManager()
    eng = EnrichmentEngine(org_manager=org_mgr)
    header = f"{'域名':<22}{'解析IP':<17}{'注册主体/注册商':<30}{'ICP备案/主体':<34}{'证书CN':<20}子域数"
    print(header)
    print("-" * len(header))
    for d in TARGET_DOMAINS:
        # DNS 解析
        ip = ""
        try:
            ip = socket.gethostbyname(d)
        except Exception:
            ip = "未解析"

        # WHOIS（在线 + socket 兜底，结果同时落库 whois_records）
        w = eng.query_whois(d) or {}
        reg = (w.get("registrant_org") or w.get("registrar") or "未获取")[:28]

        # ICP 在线查询（best-effort）
        icp = eng.query_icp_online(d) or {}
        icp_txt = (f"{icp.get('icp_number','')}/{icp.get('company_name','')}"
                   if icp.get("icp_number") else "需人工核验(登录备案系统)")
        icp_txt = icp_txt[:32]

        # SSL 证书
        cert = eng.query_ssl_certificate(d) or {}
        cn = (cert.get("cn") or "")[:18]

        # crt.sh 子域名数量
        subs = eng.query_crtsh(d)

        print(f"{d:<22}{ip:<17}{reg:<30}{icp_txt:<34}{cn:<20}{len(subs)}")

    print("\n归属判定参考: 注册主体/ICP 主体/证书 CN 是否含「商务厅」「山西」等关键词；")
    print("全部解析失败或主体为第三方(如 CDN/域名服务商)需人工研判。")
    print("注意: ICP 在线查询为 best-effort(icp.chinaz.com)，失败不代表无备案，需登录 beian.miit.gov.cn 人工核验。")


if __name__ == "__main__":
    main()
