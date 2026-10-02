"""合同原件内容识别：PDF/Word 抽文本 + LLM 结构化抽取（无 LLM 降级为人工补录）。

遵循 §4.16 落地原则：LLM 未配置或调用失败不阻塞主流程，返回空字段由前端编辑补充。
"""
import io
import json
import os
import re
import tempfile
from datetime import date

from app.core.config import settings
from app.services.llm_service import chat, llm_configured


class MineruTokenExpired(Exception):
    """MinerU token 已过期 / 无效（90 天有效期），需提示用户重新获取。"""


EXTRACT_SYSTEM = "你是合同信息抽取助手，仅依据给定合同文本抽取字段，不编造。输出严格 JSON，不要输出任何解释。"

EXTRACT_PROMPT_TMPL = (
    "请从下面合同文本中抽取字段，输出一个 JSON 对象（字段缺失用 null/[]），键名固定如下：\n"
    "name(合同名称)、customer_name(客户名称，注意取「需方/甲方/采购方/招标方/买方/采购人」即采购方)、"
    "contract_no(合同号)、sign_date(合同签署日期,YYYY-MM-DD)、"
    "amount(合同金额,数字)、has_onsite(是否驻场服务,true/false)、"
    "service_period(服务期限文本,如 '2026-01-01 至 2026-12-31')、service_location(服务地点)、"
    "staff_requirement(人员要求)、accept_standard(验收标准)、delivery_docs(交付文档)、"
    "acceptance_report_format(验收报告格式)、"
    "service_objects(服务对象名称的字符串数组)、"
    "service_items(服务项目数组，每项为 {{project,frequency,unit,price,service_object}}，"
    "frequency 为数字、unit 为 天/周/月/季度/半年/年/不定期、service_object 关联服务对象名)。\n"
    "【抽取要求】字段值只填「值本身」，禁止混入字段标签前缀（如「合同名称：」「委托方（甲方）：」「甲方：」）、"
    "章节标题（如「一、服务内容」）或 markdown 符号（##、**、- 等）。"
    "service_items 的 project 只填简洁的服务项目名词短语（如「网络安全备案咨询服务」「漏洞扫描」），"
    "不要填「为甲方提供…服务」这类句子或章节标题。\n"
    "合同文本：\n{text}"
)


def extract_text(filename: str, data: bytes) -> tuple[str, bool]:
    """按扩展名抽取纯文本，返回 (text, mineru_expired)；.doc（旧二进制格式）不支持。"""
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(data)
    if lower.endswith(".docx"):
        return _extract_docx(data), False
    if lower.endswith((".jpg", ".jpeg", ".png")):
        return _extract_image(data, lower)
    raise ValueError("仅支持 PDF / Word(.docx) / 图片(jpg/png) 文件")


def _extract_pdf(data: bytes) -> tuple[str, bool]:
    expired = False
    try:
        text = _extract_mineru(data, ".pdf")
    except MineruTokenExpired:
        expired = True
        text = ""
    if text:
        return text, expired
    # MinerU 未取到文本（含 token 过期）时仍回退本地 pypdf，保证文字版 PDF 可用
    return _extract_pdf_pypdf(data), expired


def _extract_image(data: bytes, ext: str) -> tuple[str, bool]:
    """图片 OCR：走 MinerU 云端；token 过期抛 MineruTokenExpired，否则失败返回空串（前端人工补录）。"""
    try:
        return _extract_mineru(data, ext), False
    except MineruTokenExpired:
        return "", True


def _extract_mineru(data: bytes, suffix: str) -> str:
    """MinerU 云端解析（PDF/图片，含扫描件 OCR）。

    未配置 token 或其它失败返回空串；token 无效/过期抛 MineruTokenExpired。
    """
    if not getattr(settings, "MINERU_TOKEN", ""):
        return ""
    try:
        from mineru import MinerU
        from mineru.exceptions import AuthError
    except ImportError:
        return ""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            tmp = f.name
        client = MinerU(settings.MINERU_TOKEN)
        # flash 快速 OCR 模式（秒级返回）；普通 extract(v4) 云端排队极慢、易超时，扫描件尤其如此
        result = client.flash_extract(tmp, is_ocr=True, timeout=300)
        return (result.markdown or "").strip()
    except AuthError:
        raise MineruTokenExpired() from None
    except Exception:
        return ""
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _extract_pdf_pypdf(data: bytes) -> str:
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


# 字段值里常见的「标签前缀」（LLM/OCR 易把「委托方（甲方）：」「## 一服务内容：」带进值里）
_MD_HEAD_RE = re.compile(r"^[#>\s]+")
_LABEL_RE = re.compile(
    r"^[一二三四五六七八九十]*[、.．]?\s*"
    r"(?:服务内容|服务项目|运维项目|项目名称|合同名称|客户名称|委托方|甲方|乙方|需方|供方|采购方|采购人|招标方|买方|卖方|单位名称|服务对象)"
    r"(?:[（(][^）)]*[）)])?\s*[:：]\s*"
)


def _clean_field(value) -> str | None:
    """剥离混入字段值的 markdown 符号与标签前缀（如「委托方（甲方）：」「## 一服务内容：」）。"""
    if value is None:
        return None
    s = str(value).strip().replace("**", "").replace("`", "")
    s = _MD_HEAD_RE.sub("", s).strip()
    for _ in range(2):  # 最多剥两层标签
        s = _LABEL_RE.sub("", s, count=1).strip()
    return s or None


def _normalize(parsed: dict) -> dict:
    out: dict = {}
    for k in (
        "name", "customer_name", "contract_no", "sign_date", "service_period",
        "service_location", "staff_requirement", "accept_standard", "delivery_docs",
        "acceptance_report_format",
    ):
        out[k] = _clean_field(parsed.get(k))
    out["amount"] = _as_number(parsed.get("amount"))
    out["has_onsite"] = _as_bool(parsed.get("has_onsite"))

    objs = parsed.get("service_objects") or []
    out["service_objects"] = (
        [c for c in (_clean_field(o) for o in objs) if c] if isinstance(objs, list) else []
    )

    items: list[dict] = []
    raw_items = parsed.get("service_items") or []
    if isinstance(raw_items, list):
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            project = (_clean_field(it.get("project")) or "").strip("。；;，,")
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
                "unit": _clean_field(it.get("unit")) or "月",
                "price": _as_number(it.get("price")),
                "service_object": _clean_field(it.get("service_object")),
            })
    out["service_items"] = items
    return out


def _extract_service(text: str, out: dict) -> None:
    """从「提供 X 维保及 Y 服务」类描述抽取 服务对象(X) + 服务项目(X维保、Y服务)。"""
    m = re.search(
        r"提供\s*([一-龥A-Za-z0-9]+?)\s*维保\s*[及和与、]\s*([一-龥A-Za-z0-9]+?)\s*服务",
        text,
    )
    if m:
        obj = m.group(1).strip()
        svc = m.group(2).strip()
        if obj and obj not in out["service_objects"]:
            out["service_objects"].append(obj)
        out["service_items"].append({"project": f"{obj}维保", "frequency": 1, "unit": "月", "price": None, "service_object": obj})
        out["service_items"].append({"project": f"{svc}服务", "frequency": 1, "unit": "月", "price": None, "service_object": obj})
        return
    m = re.search(r"提供\s*([一-龥A-Za-z0-9]+?)\s*维保服务", text)
    if m:
        obj = m.group(1).strip()
        if obj not in out["service_objects"]:
            out["service_objects"].append(obj)
        out["service_items"].append({"project": f"{obj}维保服务", "frequency": 1, "unit": "月", "price": None, "service_object": obj})


def _rule_extract(text: str) -> dict:
    """无 LLM 时的确定性降级：正则/关键词抽取常见字段，供人工核对补充。"""
    out = {
        "name": None, "customer_name": None, "contract_no": None, "sign_date": None,
        "amount": None, "has_onsite": None, "service_period": None,
        "service_location": None,
        "staff_requirement": None, "accept_standard": None, "delivery_docs": None,
        "acceptance_report_format": None, "service_objects": [], "service_items": [],
    }
    if not text:
        return out

    # 合同名称：首行标题（+ 第二行若以「合同/协议」结尾则拼接）
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        name = lines[0]
        if len(lines) > 1 and re.search(r"(合同|协议)$", lines[1]):
            name = name + lines[1]
        out["name"] = name

    # 客户名称：需方/甲方/采购方/采购人/招标方/买方/委托方 均为客户的称谓
    m = re.search(r"(?:需方|甲方|采购方|采购人|招标方|买方|委托方)\s*[:：]?\s*([^\n\r：:]+)", text)
    if m:
        out["customer_name"] = m.group(1).strip()

    m = re.search(r"(?:合同编号|合同号|合同NO\.?|Contract\s*No\.?)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)", text, re.I)
    if m:
        out["contract_no"] = m.group(1).strip()

    m = re.search(
        r"(?:合同金额|合同总价|总价|金额|价款|¥|￥)\s*[:：]?\s*(?:人民币|RMB)?\s*(?:¥|￥)?\s*([0-9][0-9,.]*)\s*(万|万元|元)?",
        text,
    )
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

    # 验收标准：交验 节下的编号条目（到「验收交付文档」或下一节为止）
    m = re.search(r"交验[^\n]*\n(.*?)(?=\d+、验收交付文档|[一二三四五六七八九十]+、|\Z)", text, re.S)
    if m:
        out["accept_standard"] = m.group(1).strip()

    # 服务地点
    m = re.search(r"服务地点\s*[:：]?\s*([^\n\r]+)", text)
    if m:
        out["service_location"] = m.group(1).strip()

    # 交付文档：验收交付文档/交付文档 后的清单
    m = re.search(r"(?:验收交付文档|交付文档)\s*[:：]?\s*(.+)", text)
    if m:
        out["delivery_docs"] = m.group(1).strip()

    # 服务对象 / 服务项目：优先从「提供 X 维保及 Y 服务」类描述抽取
    _extract_service(text, out)

    # 服务对象兜底：「服务对象：」列表
    if not out["service_objects"]:
        m = re.search(r"(?:服务对象|维护对象|运维对象)\s*[:：]?\s*([^\n\r]+)", text)
        if m:
            objs = re.split(r"[、,，;；]", m.group(1))
            out["service_objects"] = [o.strip() for o in objs if o.strip()]

    return out


def _sanitize_customer_name(base: dict) -> dict:
    """纯数字（规则/OCR 误识别的「6」「7」等）或空白客户名称置空，避免建出垃圾客户。"""
    name = base.get("customer_name")
    if name:
        name = str(name).strip()
        if re.fullmatch(r"\d+", name):
            base["customer_name"] = None
    return base


def extract_contract_fields(text: str) -> dict:
    """抽取 14 类字段：LLM 优先，未配置/失败降级为规则抽取（llm_used=False）。"""
    if llm_configured() and text.strip():
        try:
            raw = chat(EXTRACT_PROMPT_TMPL.format(text=text[:8000]), system=EXTRACT_SYSTEM)
            parsed = _parse_json(raw)
            if parsed:
                base = _normalize(parsed)
                base["llm_used"] = True
                return _sanitize_customer_name(base)
        except Exception:
            pass
    base = _rule_extract(text)
    base["llm_used"] = False
    return _sanitize_customer_name(base)


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
