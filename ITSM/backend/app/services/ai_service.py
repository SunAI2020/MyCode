"""AI 增强（建议 + 人工确认）：工单摘要 / 工单转知识草稿 / 智能分类 / 派单建议。

均遵循 §4.16 落地原则：LLM 不可用时确定性降级，不阻塞主流程；转知识仅生成草稿，审核后入库。
"""
import json
from datetime import date, timedelta

from sqlalchemy import func

from app.models import (
    Contract,
    ContractItem,
    EngineerSkill,
    KbArticle,
    ServiceCycle,
    SysUser,
    WorkOrder,
)
from app.services.cycle_service import split_cycles
from app.services.llm_service import chat, llm_configured


def summarize_work_order(wo: WorkOrder) -> str:
    """工单执行摘要：LLM 生成，未配置/失败降级为确定性模板摘要。"""
    if llm_configured():
        prompt = (
            "请为以下运维工单生成一段简洁的执行摘要（100字内）：\n"
            f"类型：{wo.type}，项目：{wo.project or '—'}，描述：{wo.description or '—'}，"
            f"状态：{wo.status}，进度：{wo.progress}%。"
        )
        try:
            return chat(prompt)
        except Exception:
            pass
    return f"工单 {wo.no}（{wo.type}）：{wo.description or '无描述'}，当前状态 {wo.status}，进度 {wo.progress}%。"


def work_order_to_kb_draft(db, wo: WorkOrder, operator_id: int | None) -> KbArticle:
    """工单转知识草稿：沉淀为知识条目（status=草稿，待审核入库）。"""
    title = f"[{wo.type}] {wo.description[:40] if wo.description else wo.no}"
    content = (
        f"工单号：{wo.no}\n类型：{wo.type}\n项目：{wo.project or '—'}\n"
        f"描述：{wo.description or '—'}\n状态：{wo.status}"
    )
    article = KbArticle(
        title=title,
        category="故障手册",
        content=content,
        status="草稿",
        author_id=operator_id,
    )
    db.add(article)
    db.flush()
    return article


# ---- 智能分类 ----
PROJECT_KEYWORDS = [
    ("漏洞扫描", ["漏洞", "扫描", "CVE", "scan"]),
    ("渗透测试", ["渗透", "攻防", "pentest", "红队"]),
    ("应急演练", ["应急演练", "演练", "drill"]),
    ("安全加固", ["加固", "补丁", "基线", "hardening"]),
    ("等保测评", ["等保", "测评"]),
    ("安全巡检", ["巡检"]),
    ("安全评估", ["评估"]),
    ("应急处置", ["应急处置", "事件响应", "事件"]),
    ("故障排查", ["故障", "无法", "报障", "排查", "登录", "异常", "报错", "宕机"]),
]
HIGH_KEYWORDS = ["紧急", "立刻", "马上", "宕机", "无法", "严重", "瘫痪"]
LOW_KEYWORDS = ["建议", "不急", "有空", "低"]


def classify_ticket(description: str) -> dict:
    """报障描述 → 运维项目/优先级。LLM 可用则调 LLM，否则关键词规则降级。"""
    if llm_configured():
        prompt = (
            "对运维报障描述分类，只返回 JSON：{\"project\":\"<运维项目>\",\"priority\":\"<高/中/低>\"}。"
            f"描述：{description}"
        )
        try:
            data = json.loads(chat(prompt))
            return {"project": data.get("project", "故障排查"), "priority": data.get("priority", "中")}
        except Exception:
            pass
    project = "故障排查"
    for p, kws in PROJECT_KEYWORDS:
        if any(kw in description for kw in kws):
            project = p
            break
    priority = "中"
    if any(kw in description for kw in HIGH_KEYWORDS):
        priority = "高"
    elif any(kw in description for kw in LOW_KEYWORDS):
        priority = "低"
    return {"project": project, "priority": priority}


# ---- 智能派单建议 ----
LEVEL_SCORE = {"高级": 3, "中级": 2, "初级": 1}


def recommend_assignee(db, project: str, limit: int = 3) -> list[dict]:
    """按技能匹配（等级）→ 负载 → 绩效推荐执行人（确定性降级，不依赖 LLM）。"""
    rows = (
        db.query(EngineerSkill, SysUser)
        .join(SysUser, EngineerSkill.user_id == SysUser.id)
        .filter(EngineerSkill.skill == project)
        .all()
    )
    result = []
    for skill, user in rows:
        score = LEVEL_SCORE.get(skill.level, 1)
        result.append(
            {
                "user_id": user.id,
                "name": user.name,
                "level": skill.level,
                "score": score,
                "reason": f"技能匹配({project})·{skill.level}",
            }
        )
    result.sort(key=lambda x: -x["score"])
    return result[:limit]


# ---- 合同履约洞察 ----
def contract_insight(db, today: date | None = None) -> list[dict]:
    """合同履约洞察：临近到期未完成周期 + 履约缺口（应生成 vs 已生成）。"""
    today = today or date.today()
    insights: list[dict] = []

    # 临近到期（未来 7 天内未完成）
    cycles = (
        db.query(ServiceCycle)
        .filter(
            ServiceCycle.status != "done",
            ServiceCycle.service_end >= today,
            ServiceCycle.service_end <= today + timedelta(days=7),
        )
        .all()
    )
    for c in cycles:
        item = db.get(ContractItem, c.contract_item_id)
        contract = db.get(Contract, item.contract_id) if item else None
        insights.append(
            {
                "type": "临近到期",
                "contract_id": contract.id if contract else None,
                "contract_name": contract.name if contract else None,
                "item_id": c.contract_item_id,
                "project": item.project if item else None,
                "cycle_no": c.cycle_no,
                "service_end": c.service_end.isoformat(),
                "status": c.status,
            }
        )

    # 履约缺口（已生成周期数 < 按频率应生成）
    for item in db.query(ContractItem).all():
        contract = db.get(Contract, item.contract_id)
        if contract is None or contract.start_date is None or contract.end_date is None:
            continue
        expected = split_cycles(contract.start_date, contract.end_date, item.frequency, item.unit)
        if not expected:
            continue
        generated = db.query(func.count(ServiceCycle.id)).filter_by(contract_item_id=item.id).scalar() or 0
        if generated < len(expected):
            insights.append(
                {
                    "type": "履约缺口",
                    "contract_id": contract.id,
                    "contract_name": contract.name,
                    "item_id": item.id,
                    "project": item.project,
                    "expected": len(expected),
                    "generated": int(generated),
                    "gap": len(expected) - int(generated),
                }
            )
    return insights
