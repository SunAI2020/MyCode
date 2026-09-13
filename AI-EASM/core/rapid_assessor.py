# -*- coding: utf-8 -*-
"""1小时快速评估 — 4阶段+并行搜索+实时进度+自动报告"""
import os, sys, threading, time, json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class RapidAssessor:
    def __init__(self, org_manager, enrichment_engine, equity_engine, ai_engine, leak_detector,
                 shadow_detector=None, report_manager=None):
        self.org_mgr = org_manager; self.enrichment = enrichment_engine
        self.equity_engine = equity_engine; self.ai_engine = ai_engine
        self.leak_detector = leak_detector; self.shadow_detector = shadow_detector
        self.report_mgr = report_manager
        self._log_cb = self._progress_cb = self._phase_cb = None
        self._stop = threading.Event()

    def set_callbacks(self, log_cb=None, progress_cb=None, phase_cb=None):
        self._log_cb = log_cb; self._progress_cb = progress_cb; self._phase_cb = phase_cb
    def _log(self, m):
        if self._log_cb: self._log_cb(f"[{datetime.now().strftime('%H:%M:%S')}] {m}")
    def _phase(self, name, pct, stats=None, elapsed=0):
        if self._phase_cb: self._phase_cb(name, pct, stats or {}, elapsed)
    def stop(self): self._stop.set()

    def run(self, org_id, company_name):
        self._stop.clear()
        sid = self.org_mgr.create_rapid_assessment(org_id, company_name)
        stats = {"subsidiaries":0,"assets":0,"leaks":0,"shadows":0}
        t_start = time.time(); domain = ""; profile = {}; all_assets = []

        try:
            # Phase 0: 架构发现
            t0 = time.time()
            self._phase("Phase0: 企业架构发现", 5, stats, 0)
            self._log(f"开始评估: {company_name}")
            profile = self.equity_engine.extract_enterprise_profile(company_name)
            pid = self.org_mgr.save_enterprise_profile({"org_id":org_id,**profile})
            idfs = []; idf_map = [("name","full_name"),("short_name","short_name"),
                ("legal_person","legal_person"),("email","emails"),("phone","phones"),("mobile","mobile_numbers")]
            for t,k in idf_map[:2]:  # name + short_name
                v = profile.get(k,"")
                if v: idfs.append({"type":t,"value":v,"profile_id":pid,"org_id":org_id})
            lp = profile.get("legal_person","")
            if lp: idfs.append({"type":"legal_person","value":str(lp),"profile_id":pid,"org_id":org_id})
            for em in (profile.get("emails") or [])[:5]: idfs.append({"type":"email","value":str(em),"profile_id":pid,"org_id":org_id})
            for ph in (profile.get("phones") or [])[:5]: idfs.append({"type":"phone","value":str(ph),"profile_id":pid,"org_id":org_id})
            for mb in (profile.get("mobile_numbers") or [])[:5]: idfs.append({"type":"mobile","value":str(mb),"profile_id":pid,"org_id":org_id})
            self.org_mgr.add_identifier_batch(idfs)
            # 更名历史
            if self.equity_engine.is_government_entity(company_name):
                changes = self.equity_engine.track_name_history(company_name)
                for c in changes:
                    self.org_mgr.add_name_change(profile_id=pid, org_id=org_id,
                        old_name=c.get("old_name",""), new_name=c.get("new_name",""),
                        change_date=c.get("change_date",""), source=c.get("source",""))
                if changes: self._log(f"  更名历史: {len(changes)}条")
            # 股权穿透
            subs, rels = self.equity_engine.discover_subsidiaries(company_name)
            self.org_mgr.add_subsidiary_batch([{"parent_org_id":org_id,**s} for s in subs])
            for rl in rels:
                self.org_mgr.add_relation(from_org_id=org_id,to_entity_name=rl["to_name"],
                    relation_type=rl["relation_type"],equity_ratio=rl["equity_ratio"],
                    chain_level=rl["chain_level"],source="equity_engine")
            stats["subsidiaries"] = len(subs)
            e0 = time.time()-t0
            self._phase("Phase0完成", 25, stats, e0)
            self._log(f"Phase0 ({e0:.1f}s): {len(subs)}子公司 {len(rels)}关系 {len(idfs)}标识符")
            if self._stop.is_set(): return sid

            # Phase 1: 并行资产枚举
            t1 = time.time()
            self._phase("Phase1: 资产并行枚举", 30, stats, e0)
            for idf in idfs:
                if idf["type"]=="name": domain = idf["value"]; break
            if not domain:
                icp = self.enrichment.query_icp_by_company(company_name)
                if icp: domain = icp[0].get("domain_name","")
            search_names = self.equity_engine.search_by_all_names(company_name)
            self._log(f"Phase1: {len(search_names)}名称变体 并行搜索")
            dims = [d[0] for d in self.ai_engine.ASSET_DIMENSIONS]
            all_assets = []
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {pool.submit(self.ai_engine.search, org_id, sn, domain, dims, False): sn
                    for sn in search_names[:5]}
                for f in as_completed(futures):
                    sn = futures[f]
                    try: all_assets.extend(f.result(timeout=180))
                    except Exception as e: self._log(f"  [warn] '{sn}': {e}")
                    if self._stop.is_set(): break
            stats["assets"] = len(all_assets)
            e1 = time.time()-t1
            self._phase("Phase1完成", 60, stats, e0+e1)
            self._log(f"Phase1 ({e1:.1f}s): {len(all_assets)}资产")

            # Phase 2: 网络映射 + 影子资产
            t2 = time.time()
            self._phase("Phase2: 网络映射+影子检测", 65, stats, e0+e1)
            ips = list(set(a["asset_value"] for a in all_assets if a.get("asset_type")=="ip"))
            with ThreadPoolExecutor(max_workers=5) as pool:
                bgp_f = {pool.submit(self.enrichment.query_asn_bgp, ip): ip for ip in ips[:30]}
                for f in as_completed(bgp_f):
                    try:
                        bgp = f.result(timeout=10)
                        if bgp:
                            self.org_mgr.add_network_range(org_id=org_id,ip_range=bgp.get("ip_range",""),
                                asn_number=bgp.get("asn_number",""),asn_name=bgp.get("asn_name",""),
                                isp=bgp.get("isp",""),country=bgp.get("country",""),source="BGPView")
                    except: pass
            if self.shadow_detector:
                known = [domain] + [d for d in search_names if "." in d]
                shadows = self.shadow_detector.detect_shadow_assets(known, all_assets)
                stats["shadows"] = len(shadows)
            e2 = time.time()-t2
            self._phase("Phase2完成", 80, stats, e0+e1+e2)
            self._log(f"Phase2 ({e2:.1f}s): {len(ips)}IPs {stats['shadows']}影子")

            # Phase 3: 泄露扫描
            t3 = time.time()
            self._phase("Phase3: 数据泄露扫描", 85, stats, e0+e1+e2)
            leaks = self.leak_detector.full_leak_scan(company_name, domain, org_id)
            for sn in search_names[1:3]:
                if not self._stop.is_set():
                    leaks.extend(self.leak_detector.full_leak_scan(sn, domain, org_id))
            stats["leaks"] = len(leaks)
            e3 = time.time()-t3
            self._phase("Phase3完成", 95, stats, e0+e1+e2+e3)
            self._log(f"Phase3 ({e3:.1f}s): {len(leaks)}泄露")

            total = time.time()-t_start
            stats["total_time"] = total
            self._log(f"完成: {total/60:.1f}分钟 子公司{stats['subsidiaries']} 资产{stats['assets']} 影子{stats['shadows']} 泄露{stats['leaks']}")
            self.org_mgr.update_rapid_assessment(sid, status="completed",
                end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                subsidiaries_found=stats["subsidiaries"], assets_found=stats["assets"],
                leaks_found=stats["leaks"])
            # 自动生成报告
            if self.report_mgr:
                try:
                    rpt = self.report_mgr.generate_rapid_assessment_report(
                        sid, company_name, stats, profile, subs, all_assets, leaks)
                    if rpt: self._log(f"报告: {rpt}")
                except: pass
            self._phase("评估完成!", 100, stats, total)
        except Exception as e:
            import traceback
            self._log(f"[FAIL] {traceback.format_exc()}")
            self.org_mgr.update_rapid_assessment(sid, status="failed",
                end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self._phase("评估失败", 0, stats, time.time()-t_start)
        return sid

    def get_summary(self, session_id):
        s = self.org_mgr.get_rapid_assessment(session_id)
        if not s: return None
        oid = s["org_id"]
        return {"session":dict(s),
            "exposures": len(self.org_mgr.list_exposures(org_id=oid)),
            "leaks": len(self.org_mgr.list_leak_evidence(org_id=oid)),
            "subsidiaries": len(self.org_mgr.list_subsidiaries(parent_org_id=oid)),
            "confidence": self.ai_engine.get_confidence_distribution(org_id=oid)}
