# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 合规 AI 研判层

四种能力：
  suggest_answers      —— 依据技术证据给出问卷建议答案（仅建议，不落库）
  review_answers       —— 复核人工填报的合理性 → 认可 / 存疑
  cross_check          —— 把填报结论与扫描到的硬事实比对 → 矛盾
  generate_remediation —— 为不符合项生成整改建议

⚠️ 失败方向与 ai_scan_enhancer 相反，务必注意：
  ai_scan_enhancer 面对『AI 调用失败』时**保留漏洞**（保守 = 不漏报）；
  本模块面对『AI 调用失败』时返回 ai_status='未完成'，**绝不返回'认可'**。
  原因：合规研判里『认可』是一项声明——声称 AI 已核验过这条自评。
  调用失败却回填『认可』，等于凭空捏造一次并不存在的核验，
  会让报告里的『AI 已核验 N 条』变成谎报。宁可显式说没跑完。
"""
import logging
from typing import List, Dict, Optional, Any, Callable

from ai_client import AIClient, is_ai_available, strip_markdown_fences
from compliance_engine import (
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA,
    AI_NOT_RUN, AI_ENDORSED, AI_DOUBTED, AI_CONFLICT, AI_INCOMPLETE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是中国网络安全等级保护与数据安全合规测评专家，熟悉 GB/T 22239-2019、"
    "GB/T 39204-2022、《数据安全法》《个人信息保护法》。"
    "你的判断必须基于给出的技术证据与填报内容，不得臆测未提供的事实。"
    "证据不足时如实说明，不得为了让结论好看而给出乐观判断。"
    "只输出 JSON，不要输出任何解释性文字。"
)

# AI 研判允许的结论（不含『未完成』——那是失败兜底，模型不该主动返回）
_REVIEW_STATUSES = (AI_ENDORSED, AI_DOUBTED, AI_CONFLICT)


def _clip(text: Any, limit: int = 300) -> str:
    s = str(text or '').replace('\n', ' ').strip()
    return s[:limit]


def evidence_digest(evidence, limit: int = 12) -> str:
    """把 EvidenceBundle 压成给模型看的简报。无证据时明说，不留空白让模型脑补。"""
    if evidence is None:
        return '（本次未提供技术证据）'
    parts = []
    ports = getattr(evidence, 'open_ports', None) or []
    if ports:
        items = [f"{p.get('port')}/{p.get('service', '') or '未知'}" for p in ports[:limit]]
        parts.append(f"开放端口({len(ports)}): " + '、'.join(items))
    vulns = getattr(evidence, 'vulnerabilities', None) or []
    if vulns:
        sev: Dict[str, int] = {}
        for v in vulns:
            key = str(v.get('severity', '')).upper() or '未分级'
            sev[key] = sev.get(key, 0) + 1
        parts.append(f"漏洞({len(vulns)}): " + '、'.join(f'{k}×{n}' for k, n in sev.items()))
    kev = [v for v in vulns if v.get('kev')]
    if kev:
        parts.append("在野利用漏洞: " + '、'.join(_clip(v.get('cve_id'), 20) for v in kev[:limit]))
    weak = getattr(evidence, 'weak_passwords', None) or []
    if weak:
        parts.append(f"弱口令: {len(weak)} 处")
    tls = getattr(evidence, 'tls_findings', None) or []
    if tls:
        parts.append(f"加密缺陷: {len(tls)} 项")
    devices = getattr(evidence, 'devices', None) or []
    if devices:
        names = [_clip(d.get('device_type') or d.get('vendor'), 20) for d in devices[:limit]]
        parts.append(f"识别设备({len(devices)}): " + '、'.join(n for n in names if n))
    web = getattr(evidence, 'web_findings', None) or []
    if web:
        parts.append(f"Web 安全问题: {len(web)} 项")
    return '；'.join(parts) if parts else '（扫描已执行，但未发现上述任何技术证据）'


def _parse_json(raw: str) -> Optional[Any]:
    """解析模型输出。解析不出来就返回 None，由调用方走『未完成』兜底。"""
    import json
    if not raw:
        return None
    text = strip_markdown_fences(raw).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # 容错：截取最外层 JSON 片段
    for opener, closer in (('[', ']'), ('{', '}')):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except (ValueError, TypeError):
                continue
    logger.warning('AI 返回无法解析为 JSON，按未完成处理')
    return None


# 合并多轮 AI 结论时的严重度排序（值越小越严重）。
# 『未完成』排在最后：它不是一个结论，任何实质结论都应压过它。
_VERDICT_RANK = {AI_CONFLICT: 0, AI_DOUBTED: 1, AI_ENDORSED: 2,
                 AI_INCOMPLETE: 3, AI_NOT_RUN: 4}


def merge_verdicts(*verdict_maps: Dict[str, Dict]) -> Dict[str, Dict]:
    """合并多轮 AI 研判结果，同一条款取较严重者。

    不能用 dict.update() —— 那是后写覆盖前写：复核判『存疑』的条款
    若交叉比对未发现硬矛盾而给了『认可』，存疑就被抹掉了，
    等于把『拿不准』悄悄升级成『没问题』，与本模块的保守方向相悖。
    """
    merged: Dict[str, Dict] = {}
    for vmap in verdict_maps:
        for cid, verdict in (vmap or {}).items():
            if not verdict:
                continue
            current = merged.get(cid)
            if current is None:
                merged[cid] = verdict
                continue
            new_rank = _VERDICT_RANK.get(verdict.get('ai_status'), 9)
            cur_rank = _VERDICT_RANK.get(current.get('ai_status'), 9)
            if new_rank < cur_rank:
                merged[cid] = verdict
    return merged


def _as_items(parsed: Any) -> List[Dict]:
    """把模型返回归一化成 list[dict]"""
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        for key in ('results', 'items', 'verdicts', 'answers', 'data'):
            val = parsed.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        if 'control_id' in parsed:
            return [parsed]
    return []


class ComplianceAI:
    """合规 AI 研判器（批量 + 并行，失败一律降级为『未完成』）"""

    BATCH_SIZE = 4
    PARALLEL_BATCHES = 3

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 timeout: int = 300):
        self.client = AIClient(api_key=api_key, model=model)
        self.timeout = timeout
        logger.info(f"合规AI研判器初始化完成 (模型: {model or 'CLI默认'}, 批次: {self.BATCH_SIZE})")

    @property
    def available(self) -> bool:
        return is_ai_available()

    # ------------------------------------------------------------
    # 内部：批量并行执行
    # ------------------------------------------------------------
    def _run_batches(self, items: List[Any], build_prompt: Callable[[List[Any]], str],
                     handle: Callable[[List[Any], Optional[Any]], Dict],
                     progress_callback: Callable[[str], None] = None,
                     label: str = 'AI研判') -> Dict:
        """把 items 切批并行送模型。任一批失败只影响该批，由 handle 决定兜底值。"""
        out: Dict = {}
        if not items:
            return out

        batches = [items[i:i + self.BATCH_SIZE] for i in range(0, len(items), self.BATCH_SIZE)]
        if progress_callback:
            progress_callback(f"{label}: {len(items)} 条，共 {len(batches)} 批，"
                              f"并行 {self.PARALLEL_BATCHES} 批...")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _one(batch):
            try:
                raw = self.client.query(build_prompt(batch),
                                        system_prompt=SYSTEM_PROMPT,
                                        max_turns=1, timeout=self.timeout)
                return batch, _parse_json(raw)
            except Exception as e:
                logger.error(f'{label} 批次失败: {e}')
                return batch, None

        done = 0
        with ThreadPoolExecutor(max_workers=self.PARALLEL_BATCHES) as ex:
            futures = [ex.submit(_one, b) for b in batches]
            for fut in as_completed(futures):
                batch, parsed = fut.result()
                out.update(handle(batch, parsed))
                done += 1
                if progress_callback:
                    progress_callback(f"{label}: 已完成 {done}/{len(batches)} 批")
        return out

    # ------------------------------------------------------------
    # 1. 建议答案
    # ------------------------------------------------------------
    def suggest_answers(self, controls: List[Any], evidence=None,
                        progress_callback: Callable[[str], None] = None) -> Dict[str, Dict]:
        """为待填条款生成建议答案。

        返回 {control_id: {'status', 'note', 'confidence', 'reason', 'ai_status'}}。
        仅供人工参考，调用方必须经人确认后才可落库——AI 不能替填报人签字。
        """
        if not controls:
            return {}
        if not self.available:
            logger.warning('AI 不可用，跳过问卷建议')
            return {}

        digest = evidence_digest(evidence)

        def build(batch):
            lines = []
            for c in batch:
                lines.append(
                    f"- 条款ID: {c.id}\n"
                    f"  安全域: {c.domain} / {c.category}\n"
                    f"  标题: {c.title}\n"
                    f"  要求: {_clip(c.requirement, 500)}\n"
                    f"  问题: {c.question}\n"
                    f"  可选状态: {'、'.join(c.options)}"
                )
            return (
                f"以下是本次合规检查的技术证据简报：\n{digest}\n\n"
                "请为下列合规条款给出建议填报状态。\n" + '\n'.join(lines) + "\n\n"
                "规则：\n"
                "1. 技术证据能支撑的，据实给出状态；证据不涉及该条款的，"
                "status 一律给 null 并在 reason 说明需要人工确认，不要猜测。\n"
                "2. confidence 为 0~1 的小数，代表你对该建议的把握。\n"
                "3. note 是给填报人的一句话提示，说明需要准备什么证明材料。\n"
                '输出 JSON 数组：[{"control_id":"","status":"符合|部分符合|不符合|不适用|null",'
                '"confidence":0.0,"note":"","reason":""}]'
            )

        def handle(batch, parsed):
            res = {}
            if parsed is None:
                # 失败：不给任何建议，让界面显示『AI 未完成』而不是伪造一条建议
                for c in batch:
                    res[c.id] = {'status': None, 'note': '', 'confidence': 0.0,
                                 'reason': 'AI 调用失败或返回无法解析，未生成建议',
                                 'ai_status': AI_INCOMPLETE}
                return res
            by_id = {str(x.get('control_id', '')): x for x in _as_items(parsed)}
            for c in batch:
                item = by_id.get(c.id)
                if not item:
                    res[c.id] = {'status': None, 'note': '', 'confidence': 0.0,
                                 'reason': 'AI 未返回该条款的建议', 'ai_status': AI_INCOMPLETE}
                    continue
                status = item.get('status')
                if status not in (STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA):
                    status = None
                try:
                    conf = max(0.0, min(1.0, float(item.get('confidence', 0) or 0)))
                except (TypeError, ValueError):
                    conf = 0.0
                res[c.id] = {'status': status, 'note': _clip(item.get('note'), 400),
                             'confidence': conf, 'reason': _clip(item.get('reason'), 600),
                             'ai_status': AI_ENDORSED}
            return res

        return self._run_batches(list(controls), build, handle, progress_callback, 'AI建议填报')

    # ------------------------------------------------------------
    # 2. 复核填报
    # ------------------------------------------------------------
    def review_answers(self, results: List[Dict],
                       progress_callback: Callable[[str], None] = None) -> Dict[str, Dict]:
        """复核人工填报的合理性 → {control_id: {'ai_status','reasoning','recommendation'}}

        只复核有人工结论的条款；『未填报/不适用/证据不足』无从复核，直接跳过。
        """
        targets = [r for r in (results or [])
                   if r.get('status') in (STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL)]
        if not targets:
            return {}
        if not self.available:
            logger.warning('AI 不可用，跳过填报复核')
            return {r['control_id']: self._incomplete('AI 不可用，未执行复核') for r in targets}

        def build(batch):
            lines = []
            for r in batch:
                lines.append(
                    f"- 条款ID: {r.get('control_id')}\n"
                    f"  标题: {r.get('title')}\n"
                    f"  要求: {_clip(r.get('requirement'), 400)}\n"
                    f"  当前结论: {r.get('status')}\n"
                    f"  依据/说明: {_clip(r.get('detail'), 500) or '（填报人未填写说明）'}"
                )
            return (
                "请复核下列合规条款的结论是否站得住脚。\n" + '\n'.join(lines) + "\n\n"
                "规则：\n"
                "1. 说明能支撑该结论 → ai_status='认可'。\n"
                "2. 说明空泛、与要求不对应、或明显夸大 → ai_status='存疑'，"
                "并在 reasoning 指出缺什么证据。\n"
                "3. 说明内容自相矛盾或与条款要求正面冲突 → ai_status='矛盾'。\n"
                "4. 不确定时给『存疑』，不要给『认可』。\n"
                '输出 JSON 数组：[{"control_id":"","ai_status":"认可|存疑|矛盾",'
                '"reasoning":"","recommendation":""}]'
            )

        return self._run_batches(targets, build,
                                 lambda b, p: self._handle_verdicts(b, p, '复核'),
                                 progress_callback, 'AI复核填报')

    # ------------------------------------------------------------
    # 3. 交叉比对
    # ------------------------------------------------------------
    def cross_check(self, results: List[Dict], evidence=None,
                    progress_callback: Callable[[str], None] = None) -> Dict[str, Dict]:
        """把人工填报与扫描到的硬事实比对，找出矛盾。

        只比对自评为『符合/部分符合』的条款——自评已经承认不符合的无需再挑刺。
        """
        targets = [r for r in (results or [])
                   if r.get('status') in (STATUS_PASS, STATUS_PARTIAL)]
        if not targets:
            return {}
        if not self.available:
            logger.warning('AI 不可用，跳过交叉比对')
            return {r['control_id']: self._incomplete('AI 不可用，未执行交叉比对') for r in targets}

        digest = evidence_digest(evidence)

        def build(batch):
            lines = []
            for r in batch:
                lines.append(
                    f"- 条款ID: {r.get('control_id')}\n"
                    f"  要求: {_clip(r.get('requirement'), 400)}\n"
                    f"  自评结论: {r.get('status')}\n"
                    f"  自评说明: {_clip(r.get('detail'), 400) or '（无）'}"
                )
            return (
                f"本次扫描获得的技术事实：\n{digest}\n\n"
                "请判断下列条款的自评结论是否与上述技术事实冲突。\n" + '\n'.join(lines) + "\n\n"
                "规则：\n"
                "1. 技术事实直接推翻自评（例如自评『已全程加密』但扫到 Telnet 明文端口）"
                " → ai_status='矛盾'，reasoning 必须引用具体技术事实。\n"
                "2. 技术事实无法证实也无法推翻 → ai_status='存疑'。\n"
                "3. 技术事实与自评一致 → ai_status='认可'。\n"
                "4. 不得仅凭『没扫到问题』就判矛盾——没有证据不等于违规。\n"
                '输出 JSON 数组：[{"control_id":"","ai_status":"认可|存疑|矛盾",'
                '"reasoning":"","recommendation":""}]'
            )

        return self._run_batches(targets, build,
                                 lambda b, p: self._handle_verdicts(b, p, '交叉比对'),
                                 progress_callback, 'AI交叉比对')

    # ------------------------------------------------------------
    # 4. 整改建议
    # ------------------------------------------------------------
    def generate_remediation(self, results: List[Dict], top_n: int = 20,
                             progress_callback: Callable[[str], None] = None) -> Dict[str, str]:
        """为不符合/部分符合项生成整改建议 → {control_id: 建议文本}

        按权重降序取前 top_n 条，避免一次性把上百条塞给模型。
        被截断的条目会记日志并回调告知，不伪装成『全部已生成』。
        """
        targets = [r for r in (results or [])
                   if r.get('status') in (STATUS_FAIL, STATUS_PARTIAL)]
        targets.sort(key=lambda r: float(r.get('_weight', 1.0) or 1.0), reverse=True)
        dropped = max(0, len(targets) - top_n)
        targets = targets[:top_n]
        if dropped:
            logger.info(f'整改建议仅覆盖权重最高的 {top_n} 条，另有 {dropped} 条未生成')
            if progress_callback:
                progress_callback(f"整改建议覆盖前 {top_n} 条高权重问题，剩余 {dropped} 条未生成")
        if not targets:
            return {}
        if not self.available:
            logger.warning('AI 不可用，跳过整改建议生成')
            return {}

        def build(batch):
            lines = []
            for r in batch:
                lines.append(
                    f"- 条款ID: {r.get('control_id')}\n"
                    f"  标题: {r.get('title')}\n"
                    f"  要求: {_clip(r.get('requirement'), 400)}\n"
                    f"  当前状态: {r.get('status')}\n"
                    f"  问题描述: {_clip(r.get('detail'), 500)}"
                )
            return (
                "请为下列不达标的合规条款给出整改建议。\n" + '\n'.join(lines) + "\n\n"
                "要求：每条建议给出可执行的动作、涉及的责任角色、以及整改完成后应留存的证明材料，"
                "控制在 150 字以内，不要重复条款原文。\n"
                '输出 JSON 数组：[{"control_id":"","remediation":""}]'
            )

        def handle(batch, parsed):
            if parsed is None:
                return {}      # 失败就不给建议，界面沿用条款内置建议
            by_id = {str(x.get('control_id', '')): x for x in _as_items(parsed)}
            out = {}
            for r in batch:
                item = by_id.get(r.get('control_id'))
                text = _clip(item.get('remediation'), 800) if item else ''
                if text:
                    out[r['control_id']] = text
            return out

        return self._run_batches(targets, build, handle, progress_callback, 'AI整改建议')

    # ------------------------------------------------------------
    # 兜底
    # ------------------------------------------------------------
    @staticmethod
    def _incomplete(reason: str) -> Dict:
        """AI 未能给出结论时的统一返回。

        必须是『未完成』——回填『认可』等于谎报一次并不存在的核验。
        """
        return {'ai_status': AI_INCOMPLETE, 'reasoning': reason, 'recommendation': ''}

    def _handle_verdicts(self, batch: List[Dict], parsed: Optional[Any], label: str) -> Dict:
        if parsed is None:
            return {r['control_id']: self._incomplete(f'AI {label}调用失败或返回无法解析')
                    for r in batch}
        by_id = {str(x.get('control_id', '')): x for x in _as_items(parsed)}
        out = {}
        for r in batch:
            cid = r.get('control_id')
            item = by_id.get(cid)
            if not item:
                out[cid] = self._incomplete(f'AI 未返回该条款的{label}结论')
                continue
            status = item.get('ai_status')
            if status not in _REVIEW_STATUSES:
                # 模型给了无法识别的结论：同样按未完成处理，不擅自归入『认可』
                out[cid] = self._incomplete(f'AI 返回了无法识别的结论: {_clip(status, 40)!r}')
                continue
            out[cid] = {'ai_status': status,
                        'reasoning': _clip(item.get('reasoning'), 800),
                        'recommendation': _clip(item.get('recommendation'), 800)}
        return out
