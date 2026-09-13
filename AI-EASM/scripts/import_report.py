# -*- coding: utf-8 -*-
"""将已核实的《山西省商务厅互联网资产收集报告》目标域名导入 AI-EASM

域名归属已通过站点 title 核实：
  - 山西省商务厅及下属机构: swt.shanxi.gov.cn / sxszyczs.com / singlewindow.sx.cn
                            / shanxixinyong.com / sxkjdspt.com
  - 山西省人民政府:         shanxi.gov.cn

用法: python scripts/import_report.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.org_manager import OrgManager

# 域名 -> (组织名, 组织类型)
DOMAIN_ORG_MAP = {
    "swt.shanxi.gov.cn": ("山西省商务厅", "政府"),
    "sxszyczs.com":      ("山西省商务厅", "政府"),
    "singlewindow.sx.cn": ("山西省商务厅", "政府"),
    "shanxixinyong.com": ("山西省商务厅", "政府"),
    "sxkjdspt.com":      ("山西省商务厅", "政府"),
    "shanxi.gov.cn":     ("山西省人民政府", "政府"),
}


def main():
    org_mgr = OrgManager()
    groups = {}
    for domain, (org_name, _otype) in DOMAIN_ORG_MAP.items():
        groups.setdefault(org_name, []).append(domain)

    for org_name, domains in groups.items():
        oid = None
        for oid_, name in org_mgr.get_org_names():
            if name == org_name:
                oid = oid_
                break
        if not oid:
            oid = org_mgr.add_org(org_name=org_name, org_type="政府",
                                  domain_name=domains[0])
            print(f"新建组织 {org_name} -> {oid}")
        else:
            print(f"复用组织 {org_name} -> {oid}")

        for d in domains:
            org_mgr.add_identifier("domain", d, org_id=oid, source="报告导入(已核实)")
            org_mgr.add_icp_record(org_id=oid, domain_name=d, icp_number="", company_name=org_name,
                                   source="报告导入(ICP待人工核验)")
            print(f"    {d}")

    print(f"\n导入完成: {len(DOMAIN_ORG_MAP)} 个域名, {len(groups)} 个组织")
    print("说明: ICP 备案号留空待人工核验；域名标识符已建立，归属评分 icp_confirm 因子待补 ICP 后生效。")


if __name__ == "__main__":
    main()
