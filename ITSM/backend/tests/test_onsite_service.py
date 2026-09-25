"""驻场服务单测：日报周/月报聚合。"""
from datetime import date

from app.models import OnsiteDailyReport, OnsiteService
from app.services.onsite_service import summarize_reports


def _mk_onsite(db, customer_id=1):
    os = OnsiteService(contract_id=1, customer_id=customer_id, headcount=2)
    db.add(os)
    db.flush()
    return os


def test_summarize_reports_by_work_type(db):
    os = _mk_onsite(db)
    db.add_all([
        OnsiteDailyReport(onsite_id=os.id, user_id=1, report_date=date(2026, 9, 1), work_type="设备巡检", content="x"),
        OnsiteDailyReport(onsite_id=os.id, user_id=1, report_date=date(2026, 9, 2), work_type="设备巡检", content="y"),
        OnsiteDailyReport(onsite_id=os.id, user_id=2, report_date=date(2026, 9, 3), work_type="漏洞打补丁", content="z"),
    ])
    db.commit()

    r = summarize_reports(db, os.id)
    by_type = {x["work_type"]: x["count"] for x in r["by_type"]}
    assert by_type == {"设备巡检": 2, "漏洞打补丁": 1}
    assert r["total"] == 3


def test_summarize_reports_date_range(db):
    os = _mk_onsite(db)
    db.add(OnsiteDailyReport(onsite_id=os.id, user_id=1, report_date=date(2026, 9, 1), work_type="设备巡检", content="x"))
    db.add(OnsiteDailyReport(onsite_id=os.id, user_id=1, report_date=date(2026, 10, 1), work_type="设备巡检", content="y"))
    db.commit()

    r = summarize_reports(db, os.id, start=date(2026, 10, 1), end=date(2026, 10, 31))
    assert r["total"] == 1
    assert r["by_type"][0]["work_type"] == "设备巡检"
