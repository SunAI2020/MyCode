"""种子数据：七级角色 / 字典枚举 / 初始管理员

运行：python -m app.db.seed
管理员初始密码取 ADMIN_INITIAL_PASSWORD；未设置时生成强随机口令并打印（登录后请立即修改）。
"""

import os
import secrets

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.regulatory_templates import seed_templates
from app.db.session import SessionLocal
from app.models import KbArticle, SlaPolicy, SysDict, SysPermission, SysRole, SysRolePermission, SysUser, SysUserRole

ROLES = [
    ("sys_admin", "系统管理员", "platform"),
    ("sys_ops", "系统运维人员", "platform"),
    ("ticket_mgr", "工单管理人员", "platform"),
    ("cs_staff", "客服人员", "platform"),
    ("sec_staff", "工程师", "platform"),
    ("cust_admin", "客户系统管理员", "customer"),
    ("cust_service", "客户服务管理人员", "customer"),
    ("outsource", "外包人员", "platform"),  # 外包账号（§9.3 隔离）
]

# (code, name, type)  权限点：type = menu(菜单/模块可见) / action(写操作)
PERMISSIONS = [
    ("dashboard", "仪表盘", "menu"),
    ("customers", "客户管理", "menu"),
    ("contracts", "项目管理", "menu"),
    ("work_orders", "工单管理", "menu"),
    ("personnel", "人员管理", "menu"),
    ("sla", "SLA/周期管理", "menu"),
    ("issues", "安全隐患管理", "menu"),
    ("compliance", "合规运营", "menu"),
    ("portal", "自助门户", "menu"),
    ("knowledge", "知识库", "menu"),
    ("workflows", "工作流", "menu"),
    ("user:write", "人员增删改", "action"),
    ("role:write", "角色/权限矩阵配置", "action"),
    ("customer:write", "客户增改", "action"),
    ("customer:delete", "客户删除", "action"),
    ("contract:write", "合同/子项/CI 增改", "action"),
    ("contract:delete", "合同/子项/CI 删除", "action"),
    ("work_order:write", "工单创建/派单/转派", "action"),
    ("issue:write", "隐患增改/整改", "action"),
    ("issue:delete", "隐患删除", "action"),
    ("compliance:write", "合规台账/证据/报告增改", "action"),
    ("compliance:delete", "合规要求删除", "action"),
    ("kb:write", "知识库增改", "action"),
    ("kb:delete", "知识库删除", "action"),
    ("workflow:write", "工作流规则增删改", "action"),
    ("sla:write", "SLA 增改", "action"),
    ("sla:delete", "SLA 删除", "action"),
    ("approval:write", "审批同意/驳回", "action"),
]

_MENU_ALL = ["dashboard", "customers", "contracts", "work_orders", "personnel", "sla", "issues", "compliance", "portal", "knowledge", "workflows"]

# 角色默认权限矩阵（role_code -> permission codes），逐条翻译现有 require_role 白名单与前端 MENU_ITEMS，
# 保证首次 seed 后行为与现状等价。
ROLE_PERMISSIONS = {
    "sys_admin": [code for code, _, _ in PERMISSIONS],
    "sys_ops": [
        "dashboard", "work_orders", "personnel", "sla", "issues", "compliance", "portal", "knowledge",
        "user:write", "customer:write", "contract:write", "work_order:write",
        "issue:write", "issue:delete", "compliance:write", "compliance:delete",
        "kb:write", "kb:delete", "sla:write",
    ],
    "ticket_mgr": _MENU_ALL + ["work_order:write", "issue:write", "compliance:write", "kb:write", "approval:write"],
    "cs_staff": ["dashboard", "work_orders", "knowledge"],
    "sec_staff": ["work_orders", "issues", "compliance", "knowledge", "issue:write", "compliance:write"],
    "cust_admin": ["dashboard", "work_orders", "portal", "knowledge"],
    "cust_service": ["dashboard", "work_orders", "portal", "knowledge"],
    "outsource": [],
}

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


# (name, customer_level, response_limit, resolve_limit, escalation_chain)
SLA_POLICIES = [
    ("金牌 SLA", "金牌", "15分钟", "4小时", "执行人→经理→负责人"),
    ("银牌 SLA", "银牌", "30分钟", "8小时", "执行人→经理"),
    ("普通 SLA", "普通", "2小时", "24小时", "执行人→经理"),
]

# (title, category, content, tags)
KB_ARTICLES = [
    ("系统无法登录排查", "故障手册", "1. 确认账号密码无误；2. 检查账号是否被停用；3. 联系管理员重置密码。", "登录,故障"),
    ("工单提交流程", "SOP", "客户报障 → 接单 → 派单 → 执行 → 验收 → 完成，全程可在工单列表追踪进度。", "工单,流程"),
    ("常见漏洞整改指引", "整改方案", "高危漏洞优先整改，按 CVSS 排序，先修复互联网暴露面，再内网，整改后复测验证。", "漏洞,整改"),
]


def seed() -> None:
    db: Session = SessionLocal()
    try:
        for code, name, scope in ROLES:
            role = db.query(SysRole).filter_by(code=code).first()
            if role is None:
                db.add(SysRole(code=code, name=name, scope=scope))
            else:
                role.name = name  # 角色显示名以 seed 为准，幂等更新

        for pcode, pname, ptype in PERMISSIONS:
            if not db.query(SysPermission).filter_by(code=pcode).first():
                db.add(SysPermission(code=pcode, name=pname, type=ptype))

        # 角色默认权限矩阵：仅首次初始化（整表为空）时播种，避免覆盖管理员后续通过权限界面做的修改
        # （含把某角色权限清空的「锁定」操作）
        db.flush()
        perm_by_code = {p.code: p.id for p in db.query(SysPermission).all()}
        role_by_code = {r.code: r.id for r in db.query(SysRole).all()}
        if db.query(SysRolePermission.id).first() is None:
            for rcode, pcodes in ROLE_PERMISSIONS.items():
                rid = role_by_code.get(rcode)
                if rid is None:
                    continue
                for pc in pcodes:
                    pid = perm_by_code.get(pc)
                    if pid is not None:
                        db.add(SysRolePermission(role_id=rid, permission_id=pid))

        for category, code, name in DICTS:
            if not db.query(SysDict).filter_by(category=category, code=code).first():
                db.add(SysDict(category=category, code=code, name=name))

        for name, level, resp, resolve, chain in SLA_POLICIES:
            if not db.query(SlaPolicy).filter_by(name=name).first():
                db.add(SlaPolicy(
                    name=name, customer_level=level, response_limit=resp,
                    resolve_limit=resolve, escalation_chain=chain,
                ))

        for title, category, content, tags in KB_ARTICLES:
            if not db.query(KbArticle).filter_by(title=title).first():
                db.add(KbArticle(title=title, category=category, content=content, tags=tags, status="已发布"))

        admin_pwd = None
        if not db.query(SysUser).filter_by(username="admin").first():
            # 不设弱默认口令：未配置时生成强随机口令，仅本次打印
            admin_pwd = os.environ.get("ADMIN_INITIAL_PASSWORD") or secrets.token_urlsafe(12)
            admin = SysUser(
                username="admin",
                name="系统管理员",
                pwd_hash=hash_password(admin_pwd),
            )
            db.add(admin)
            db.flush()
            role = db.query(SysRole).filter_by(code="sys_admin").first()
            db.add(SysUserRole(user_id=admin.id, role_id=role.id))

        added_tpl = seed_templates(db)
        db.commit()
        print("seed 完成：8 角色 / 28 权限点 / 37 字典项 / 3 SLA 模板 / 3 知识条目 / 1 管理员(admin)")
        if added_tpl:
            print(f"  监管要求模板库：新增 {added_tpl} 条（等保2.0/密码测评/数据安全/公安部176号令）")
        if admin_pwd:
            print(f"  admin 初始密码：{admin_pwd}（请登录后立即修改）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
