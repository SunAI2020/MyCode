"""为七级角色各创建本地测试账号（便于前端切换角色联调）。

运行：cd backend && python -m scripts.create_test_users
默认口令：Test@123（仅本地联调用，生产勿用）。

说明：
- seed 只种了 admin（sys_admin）一个账号；其余角色无账号，项目暂无「用户管理」界面。
- customer 侧角色（cust_admin / cust_service）绑定到第一个客户做行级隔离。
- outsource 角色除 sys_user 外还需 outsource_user 名册记录（§9.3 隔离锚点）。
幂等：已存在的账号跳过。
"""
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models import Customer, OutsourceUser, SysRole, SysUser, SysUserRole

# username -> (显示名, 角色 code, 是否客户侧)
ACCOUNTS = [
    ("ops", "系统运维人员", "sys_ops", False),
    ("ticketmgr", "工单管理人员", "ticket_mgr", False),
    ("cs", "客服人员", "cs_staff", False),
    ("sec", "安服人员", "sec_staff", False),
    ("custadmin", "客户系统管理员", "cust_admin", True),
    ("custsvc", "客户服务管理人员", "cust_service", True),
    ("outsource", "外包人员", "outsource", False),
]

PASSWORD = "Test@123"


def run() -> None:
    db = SessionLocal()
    try:
        first_customer = db.query(Customer).order_by(Customer.id).first()
        created = []
        for username, name, role_code, is_customer in ACCOUNTS:
            if db.query(SysUser).filter_by(username=username).first():
                continue
            role = db.query(SysRole).filter_by(code=role_code).first()
            if role is None:
                print(f"  跳过 {username}：角色 {role_code} 不存在")
                continue
            user = SysUser(username=username, name=name, pwd_hash=hash_password(PASSWORD))
            db.add(user)
            db.flush()
            customer_id = first_customer.id if (is_customer and first_customer) else None
            db.add(SysUserRole(user_id=user.id, role_id=role.id, customer_id=customer_id))
            if role_code == "outsource":
                # 外包账号需名册记录，才能被 outsourcing_scope_of 识别做行级隔离
                db.add(OutsourceUser(name=name, org="测试外包单位", user_id=user.id))
            created.append((username, role_code, customer_id))

        db.commit()
        print("测试账号创建完成：")
        for username, role_code, customer_id in created:
            scope = f"customer_id={customer_id}" if customer_id else "platform"
            print(f"  {username} / {PASSWORD}  ->  {role_code}  ({scope})")
        if not created:
            print("  （无新增，账号均已存在）")
    finally:
        db.close()


if __name__ == "__main__":
    run()
