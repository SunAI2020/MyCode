"""合同原件内容识别：PDF/Word 抽文本 + LLM 结构化抽取（无 LLM 降级为人工补录）。

遵循 §4.16 落地原则：LLM 未配置或调用失败不阻塞主流程，返回空字段由前端编辑补充。
"""
import io
import json
import re
from datetime import date

from app.services.llm_service import chat, llm_configured

EXTRACT_SYSTEM = "你是合同信息抽取助手，仅依据给定合同文本抽取字段，不编造。输出严格 JSON，不要输出任何解释。"

EXTRACT_PROMPT_TMPL = (
    "请从下面合同文本中抽取字段，输出一个 JSON 对象（字段缺失用 null/[]），键名固定如下：\n"
    "customer_name(客户名称)、contract_no(合同号)、sign_date(合同签署日期,YYYY-MM-DD)、"
    "amount(合同金额,数字)、has_onsite(是否驻场服务,true/false)、"
    "service_period(服务期限文本,如 '2026-01-01 至 2026-12-31')、"
    "staff_requirement(人员要求)、accept_standard(验收标准)、delivery_docs(交付文档)、"
    "acceptance_report_format(验收报告格式)、"
    "service_objects(服务对象名称的字符串数组)、"
    "service_items(服务项目数组，每项为 {{project,frequency,unit,price,service_object}}，"
    "frequency 为数字、unit 为 天/周/月/季度/半年/年/不定期、service_object 关联服务对象名)。\n"
    "合同文本：\n{text}"
)


def extract_text(filename: str, data: bytes) -> str:
    """按扩展名抽取纯文本；.doc（旧二进制格式）不支持。"""
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(data)
    if lower.endswith(".docx"):
        return _extract_docx(data)
    raise ValueError("仅支持 PDF / Word(.docx) 文件")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    parts: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
    except Exception:
        return ""
    return "\n".join(parts).strip()


def _extract_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError:
        return ""
    parts: list[str] = []
    try:
        document = docx.Document(io.BytesIO(data))
        for p in document.paragraphs:
            if p.text.strip():
                parts.append(p.text.strip())
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                parts.append("\t".join(cells))
    except Exception:
        return ""
    return "\n".join(parts).strip()


def _parse_json(raw: str) -> dict:
    """从 LLM 输出中稳健提取 JSON 对象（容忍 markdown 代码围栏 / 前后杂字）。"""
    if not raw:
        return {}
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


def _as_number(value) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "是", "1", "yes", "有", "y")
    return None


def _normalize(parsed: dict) -> dict:
    out: dict = {}
    for k in (
        "customer_name", "contract_no", "sign_date", "service_period",
        "staff_requirement", "accept_standard", "delivery_docs",
        "acceptance_report_format",
    ):
        v = parsed.get(k)
        out[k] = str(v).strip() if v not in (None, "") else None
    out["amount"] = _as_number(parsed.get("amount"))
    out["has_onsite"] = _as_bool(parsed.get("has_onsite"))

    objs = parsed.get("service_objects") or []
    out["service_objects"] = (
        [str(o).strip() for o in objs if str(o).strip()] if isinstance(objs, list) else []
    )

    items: list[dict] = []
    raw_items = parsed.get("service_items") or []
    if isinstance(raw_items, list):
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            project = str(it.get("project") or "").strip()
            if not project:
                continue
            freq = it.get("frequency")
            try:
                freq = int(freq) if freq not in (None, "") else 1
            except (TypeError, ValueError):
                freq = 1
            items.append({
                "project": project,
                "frequency": freq,
                "unit": str(it.get("unit") or "").strip() or "月",
                "price": _as_number(it.get("price")),
                "service_object": str(it.get("service_object") or "").strip() or None,
            })
    out["service_items"] = items
    return out


def _rule_extract(text: str) -> dict:
    """无 LLM 时的确定性降级：正则/关键词抽取常见字段，供人工核对补充。"""
    out = {
        "customer_name": None, "contract_no": None, "sign_date": None,
        "amount": None, "has_onsite": None, "service_period": None,
        "staff_requirement": None, "accept_standard": None, "delivery_docs": None,
        "acceptance_report_format": None, "service_objects": [], "service_items": [],
    }
    if not text:
        return out

    m = re.search(r"(?:合同编号|合同号|合同NO\.?|Contract\s*No\.?)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)", text, re.I)
    if m:
        out["contract_no"] = m.group(1).strip()

    m = re.search(r"甲方\s*[:：]?\s*([^\n\r：:]+)", text)
    if m:
        out["customer_name"] = m.group(1).strip()

    m = re.search(r"(?:合同金额|合同总价|总价|金额|价款|¥|￥)\s*[:：]?\s*([0-9][0-9,.]*)\s*(万|万元|元)?", text)
    if m:
        amt = m.group(1).replace(",", "")
        try:
            val = float(amt)
            if m.group(2) in ("万", "万元"):
                val *= 10000
            out["amount"] = val
        except ValueError:
            pass

    norm_dates: list[date] = []
    for d in re.findall(r"\d{4}[-./年]\d{1,2}[-./月]\d{1,2}日?", text):
        s = d.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
        try:
            norm_dates.append(date.fromisoformat(s))
        except ValueError:
            continue
    if norm_dates:
        norm_dates.sort()
        out["sign_date"] = norm_dates[0].isoformat()
        if len(norm_dates) >= 2:
            out["service_period"] = f"{norm_dates[0].isoformat()} 至 {norm_dates[-1].isoformat()}"

    if re.search(r"驻场|现场服务|驻点", text):
        out["has_onsite"] = True

    m = re.search(r"(?:服务对象|维护对象|运维对象|服务内容)\s*[:：]?\s*([^\n\r]+)", text)
    if m:
        objs = re.split(r"[、,，;；]", m.group(1))
        out["service_objects"] = [o.strip() for o in objs if o.strip()]

    return out


def extract_contract_fields(text: str) -> dict:
    """抽取 14 类字段：LLM 优先，未配置/失败降级为规则抽取（llm_used=False）。"""
    if llm_configured() and text.strip():
        try:
            raw = chat(EXTRACT_PROMPT_TMPL.format(text=text[:8000]), system=EXTRACT_SYSTEM)
            parsed = _parse_json(raw)
            if parsed:
                base = _normalize(parsed)
                base["llm_used"] = True
                return base
        except Exception:
            pass
    base = _rule_extract(text)
    base["llm_used"] = False
    return base


def parse_period(text: str | None) -> tuple[date | None, date | None]:
    """从「YYYY-MM-DD 至 YYYY-MM-DD」等文本解析服务期限起止日期。"""
    if not text:
        return None, None
    pats = re.findall(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", text)
    dates: list[date] = []
    for p in pats:
        s = p.replace("/", "-").replace(".", "-")
        try:
            dates.append(date.fromisoformat(s))
        except ValueError:
            continue
    if not dates:
        return None, None
    dates.sort()
    if len(dates) == 1:
        return dates[0], None
    return dates[0], dates[-1]
