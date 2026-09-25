"""种子数据：七级角色 / 字典枚举 / 初始管理员

运行：python -m app.db.seed
"""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import SysDict, SysRole, SysUser, SysUserRole

ROLES = [
    ("sys_admin", "系统管理员", "platform"),
    ("sys_ops", "系统运维人员", "platform"),
    ("ticket_mgr", "工单管理人员", "platform"),
    ("cs_staff", "客服人员", "platform"),
    ("sec_staff", "安服人员", "platform"),
    ("cust_admin", "客户系统管理员", "customer"),
    ("cust_service", "客户服务管理人员", "customer"),
]

# (category, code, name)
DICTS = [
    # 运维项目 16 项
    ("project", "vuln_scan", "漏洞扫描"),
    ("project", "pentest", "渗透测试"),
    ("project", "drill", "应急演练"),
    ("project", "hardening", "安全加固"),
    ("project", "training", "安全培训"),
    ("project", "code_audit", "代码审计"),
    ("project", "baseline", "基线核查"),
    ("project", "inspection", "安全巡检"),
    ("project", "assessment", "安全评估"),
    ("project", "incident", "应急处置"),
    ("project", "on_duty", "重保值守"),
    ("project", "red_blue", "攻防演练"),
    ("project", "defense", "安全防护"),
    ("project", "device_inspection", "设备巡检"),
    ("project", "djcp", "等保测评"),
    ("project", "troubleshoot", "故障排查"),
    # 服务频率 7 项
    ("frequency_unit", "day", "天"),
    ("frequency_unit", "week", "周"),
    ("frequency_unit", "month", "月"),
    ("frequency_unit", "quarter", "季度"),
    ("frequency_unit", "half_year", "半年"),
    ("frequency_unit", "year", "年"),
    ("frequency_unit", "irregular", "不定期"),
    # 工单状态 8 项
    ("work_order_status", "pending_dispatch", "待派单"),
    ("work_order_status", "dispatched", "已派单"),
    ("work_order_status", "planned", "计划中"),
    ("work_order_status", "in_progress", "进行中"),
    ("work_order_status", "pending_accept", "待验收"),
    ("work_order_status", "done", "已完成"),
    ("work_order_status", "closed", "已关闭"),
    ("work_order_status", "cancelled", "已取消"),
    # 合同类型 6 项
    ("contract_type", "security_service", "安全服务"),
    ("contract_type", "security_ops", "安全运维"),
    ("contract_type", "device_upgrade", "设备升级"),
    ("contract_type", "device_purchase", "购买设备"),
    ("contract_type", "room_renovation", "机房改造"),
    ("contract_type", "other", "其他"),
]


def seed() -> None:
    db: Session = SessionLocal()
    try:
        for code, name, scope in ROLES:
            if not db.query(SysRole).filter_by(code=code).first():
                db.add(SysRole(code=code, name=name, scope=scope))

        for category, code, name in DICTS:
            if not db.query(SysDict).filter_by(category=category, code=code).first():
                db.add(SysDict(category=category, code=code, name=name))

        if not db.query(SysUser).filter_by(username="admin").first():
            admin = SysUser(
                username="admin",
                name="系统管理员",
                pwd_hash=hash_password("admin123"),
            )
            db.add(admin)
            db.flush()
            role = db.query(SysRole).filter_by(code="sys_admin").first()
            db.add(SysUserRole(user_id=admin.id, role_id=role.id))

        db.commit()
        print("seed 完成：7 角色 / 37 字典项 / 1 管理员(admin/admin123)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
