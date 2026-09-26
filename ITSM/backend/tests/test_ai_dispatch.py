"""AI 分类 / 派单建议单测：规则降级 + 技能匹配排序。"""
from app.models import EngineerSkill, SysUser
from app.services.ai_service import classify_ticket, recommend_assignee


def test_classify_vuln_high():
    r = classify_ticket("紧急：OA系统发现高危漏洞需要扫描")
    assert r["project"] == "漏洞扫描"
    assert r["priority"] == "高"


def test_classify_default():
    r = classify_ticket("日常巡检")
    assert r["project"] == "安全巡检"
    assert r["priority"] == "中"


def test_recommend_assignee_by_level(db):
    u1 = SysUser(username="e1", name="张三", pwd_hash="x")
    u2 = SysUser(username="e2", name="李四", pwd_hash="x")
    db.add_all([u1, u2])
    db.flush()
    db.add(EngineerSkill(user_id=u1.id, skill="漏洞扫描", level="高级"))
    db.add(EngineerSkill(user_id=u2.id, skill="漏洞扫描", level="初级"))
    db.commit()

    r = recommend_assignee(db, "漏洞扫描")
    assert r[0]["user_id"] == u1.id  # 高级排前
    assert r[0]["name"] == "张三"
    assert r[0]["reason"].startswith("技能匹配")


def test_recommend_empty_when_no_skill(db):
    assert recommend_assignee(db, "渗透测试") == []
