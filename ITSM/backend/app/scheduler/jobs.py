"""APScheduler 定时任务：每日定期工单生成 + SLA 预警扫描。"""
from datetime import date

from sqlalchemy.orm import Session

from app.models import Contract, ContractItem, ServiceCycle, ServiceReminder, WorkOrder
from app.services.cycle_service import normalize_unit, split_cycles
from app.services.sla_service import scan_sla_alerts
from app.utils.wo_no import next_work_order_no, work_order_no_scope


def run_daily_work_order_generation(db: Session, today: date | None = None) -> int:
    """扫描到期子项，生成 service_cycle + work_order + 启动提醒（幂等）。

    周期可复用（若已由 generate_cycles 预生成）；工单按 (contract_item_id, cycle_no) 幂等。
    """
    today = today or date.today()
    items = db.query(ContractItem).all()
    generated = 0
    with work_order_no_scope(db):
        for item in items:
            if normalize_unit(item.unit) == "irregular":
                continue
            contract = db.get(Contract, item.contract_id)
            if contract is None or contract.start_date is None or contract.end_date is None:
                continue
            if not (contract.start_date <= today <= contract.end_date):
                continue
            for no, s, e in split_cycles(contract.start_date, contract.end_date, item.frequency, item.unit):
                if s != today:
                    continue
                if db.query(WorkOrder).filter_by(contract_item_id=item.id, current_cycle_no=no).first():
                    continue  # 工单已生成
                cycle = db.query(ServiceCycle).filter_by(contract_item_id=item.id, cycle_no=no).first()
                if cycle is None:
                    cycle = ServiceCycle(
                        contract_item_id=item.id, cycle_no=no, service_start=s, service_end=e,
                        status="started", auto_generated=True,
                    )
                    db.add(cycle)
                    db.flush()
                else:
                    cycle.status = "started"
                wo = WorkOrder(
                    no=next_work_order_no(db),
                    type="客户工单",
                    contract_id=item.contract_id,
                    contract_item_id=item.id,
                    ci_id=item.ci_id,
                    project=item.project,
                    status="待派单",
                    current_cycle_no=no,
                )
                db.add(wo)
                db.flush()
                db.add(ServiceReminder(cycle_id=cycle.id, type="启动", level="黄", content=f"第 {no} 次服务已启动"))
                generated += 1
        db.commit()
    return generated


def start_scheduler():
    """启动后台调度器（ENABLE_SCHEDULER 开启时由 main.lifespan 调用）。"""
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.db.session import SessionLocal

    scheduler = BackgroundScheduler()

    def _daily():
        db = SessionLocal()
        try:
            run_daily_work_order_generation(db)
            scan_sla_alerts(db)
        finally:
            db.close()

    scheduler.add_job(_daily, "cron", hour=1, minute=0, id="itsm_daily_job")
    scheduler.start()
    return scheduler
