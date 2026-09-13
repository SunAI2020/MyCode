# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 合规检查引擎核心（等保2.0 / 关键信息基础设施 / 数据安全）

三阶判定：自动技术检查 → 问卷式人工填报 → AI 辅助研判。
条款目录外置为 JSON（compliance_controls/*.json），扩充纯问卷条款无需改代码。
"""
import os
import sys
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 状态常量
# ============================================================
STATUS_PASS = '符合'
STATUS_PARTIAL = '部分符合'
STATUS_FAIL = '不符合'
STATUS_NA = '不适用'
STATUS_UNFILLED = '未填报'
STATUS_INSUFFICIENT = '证据不足'

ALL_STATUSES = (STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL,
                STATUS_NA, STATUS_UNFILLED, STATUS_INSUFFICIENT)

# 计入合规率分母的状态（不适用/未填报/证据不足 一律排除）
SCORED_STATUSES = (STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL)

# AI 研判状态
AI_NOT_RUN = '未运行'
AI_ENDORSED = '认可'
AI_DOUBTED = '存疑'
AI_CONFLICT = '矛盾'
AI_INCOMPLETE = '未完成'

# 判定来源
SOURCE_AUTO = 'auto'
SOURCE_QUESTIONNAIRE = 'questionnaire'
SOURCE_AI_ASSISTED = 'ai_assisted'

# 条款判定模式
MODE_AUTO = 'auto'
MODE_QUESTIONNAIRE = 'questionnaire'
MODE_HYBRID = 'hybrid'

# 合并 hybrid 结论时用于"取较差者"的排序（值越小越差）
_STATUS_RANK = {STATUS_FAIL: 0, STATUS_PARTIAL: 1, STATUS_PASS: 2}


def _has_human_answer(result: Dict) -> bool:
    """该条款是否真的有人作答（用于问卷完成度，不可用状态反推）。

    优先看 _evaluate_control 打的 _answered 标记；对手工拼装的结果字典
    （测试、外部调用）回退到检查 answer 子字典，两者都没有才算未答。
    """
    if '_answered' in result:
        return bool(result['_answered'])
    return (result.get('answer') or {}).get('status') in ALL_STATUSES


def severity_for(status: str, weight: float = 1.0) -> str:
    """状态 → 严重程度（供表格/报告着色，复用 constants.SEV_COLORS 的键）"""
    if status == STATUS_FAIL:
        return 'CRITICAL' if weight >= 2.0 else 'HIGH'
    if status == STATUS_PARTIAL:
        return 'MEDIUM'
    if status == STATUS_PASS:
        return 'LOW'
    return 'INFO'


def score_factor(status: str, ai_status: str = AI_NOT_RUN) -> Optional[float]:
    """计分系数。返回 None 表示该条款不计入合规率分母。

    ⚠️ AI 降级规则（改动须同步 tests/test_compliance_engine.py）：
      符合 + 认可/未运行/未完成 → 1.0
      符合 + 存疑               → 0.5
      符合 + 矛盾               → 0.0（状态已在 apply_ai_verdicts 中被强制改判为不符合）
      部分符合 + 任意           → 0.5
      不符合 + 任意             → 0.0
    """
    if status == STATUS_PASS:
        if ai_status == AI_DOUBTED:
            return 0.5
        if ai_status == AI_CONFLICT:
            return 0.0
        return 1.0
    if status == STATUS_PARTIAL:
        return 0.5
    if status == STATUS_FAIL:
        return 0.0
    return None


# ============================================================
# 数据模型
# ============================================================
@dataclass
class ComplianceControl:
    """单个合规控制项（由条款目录 JSON 反序列化）"""
    id: str
    standard: str
    domain: str
    category: str
    title: str
    requirement: str
    levels: Set[str] = field(default_factory=lambda: {'ALL'})
    weight: float = 1.0
    mode: str = MODE_AUTO
    check: Optional[str] = None
    evidence_type: Optional[str] = None
    scope: str = 'system'          # org=组织级全局复用 | system=按业务系统
    question: str = ''
    options: List[str] = field(default_factory=list)
    evidence_hint: str = ''
    ai_reviewable: bool = False
    ai_cross_check: bool = False

    @classmethod
    def from_dict(cls, d: Dict, standard: str) -> 'ComplianceControl':
        return cls(
            id=d['id'],
            standard=standard,
            domain=d.get('domain', ''),
            category=d.get('category', ''),
            title=d.get('title', ''),
            requirement=d.get('requirement', ''),
            levels=set(d.get('levels', ['ALL'])),
            weight=float(d.get('weight', 1.0)),
            mode=d.get('mode', MODE_AUTO),
            check=d.get('check'),
            evidence_type=d.get('evidence_type'),
            scope=d.get('scope', 'system'),
            question=d.get('question', ''),
            options=list(d.get('options', [])) or [STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA],
            evidence_hint=d.get('evidence_hint', ''),
            ai_reviewable=bool(d.get('ai_reviewable', False)),
            ai_cross_check=bool(d.get('ai_cross_check', False)),
        )

    @property
    def needs_questionnaire(self) -> bool:
        return self.mode in (MODE_QUESTIONNAIRE, MODE_HYBRID)

    @property
    def has_auto_check(self) -> bool:
        return self.mode in (MODE_AUTO, MODE_HYBRID) and bool(self.check)

    def applies_to_level(self, level: str) -> bool:
        if 'ALL' in self.levels or not level or level == 'ALL':
            return True
        return level in self.levels


@dataclass
class EvidenceBundle:
    """喂给自动评估器的归一化技术证据"""
    standard: str = ''
    level: str = 'ALL'
    target: str = ''
    scope_key: str = 'ORG'
    asset: Optional[Dict] = None
    scan_result: Optional[Dict] = None
    vulnerabilities: List[Dict] = field(default_factory=list)
    open_ports: List[Dict] = field(default_factory=list)
    devices: List[Dict] = field(default_factory=list)
    tls_findings: List[Dict] = field(default_factory=list)
    weak_passwords: List[Dict] = field(default_factory=list)
    kev: List[Dict] = field(default_factory=list)
    web_findings: List[Dict] = field(default_factory=list)

    def has(self, evidence_type: Optional[str]) -> bool:
        """判断某类证据是否存在，用于区分『符合』与『证据不足』。

        没有证据 ≠ 合规。缺证据必须报『证据不足』，不能默认判为符合。
        """
        if not evidence_type:
            return True
        mapping = {
            'port_scan': self.open_ports,
            'vuln': self.scan_result is not None,
            'tls': self.tls_findings or self.open_ports,
            'device': self.devices,
            'weak_password': self.scan_result is not None,
            'kev': self.scan_result is not None,
            'web': self.web_findings,
            'asset': self.asset is not None,
        }
        val = mapping.get(evidence_type, True)
        return bool(val)


# ============================================================
# 证据装配
# ============================================================
# scan_results 一行既可能是开放端口记录，也可能是漏洞记录（带 cve_id），
# 这里按特征分流。识别不出的类别留空 —— 留空会让相关条款判『证据不足』，
# 这是有意为之：宁可说不知道，也不能默认合规。
_TLS_HINTS = ('TLS', 'SSL', '证书', '加密套件', 'CIPHER', 'HTTPS')
_WEAK_PWD_HINTS = ('弱口令', '默认口令', '空口令', 'WEAK PASSWORD', 'DEFAULT CREDENTIAL')


def build_evidence(scan_rows: Optional[List[Dict]] = None,
                   asset: Optional[Dict] = None,
                   target: str = '', scope_key: str = 'ORG',
                   standard: str = '', level: str = 'ALL',
                   devices: Optional[List[Dict]] = None,
                   web_findings: Optional[List[Dict]] = None,
                   kev: Optional[List[Dict]] = None) -> EvidenceBundle:
    """把一次扫描的结果行归一化成 EvidenceBundle，供自动评估器消费。

    scan_rows 为 None 表示『本次没有技术证据』——与传空列表不同，
    后者代表『扫过了但什么都没发现』。二者在 has() 里的语义不同。
    """
    ev = EvidenceBundle(standard=standard, level=level, target=target,
                        scope_key=scope_key, asset=asset,
                        devices=list(devices or []),
                        web_findings=list(web_findings or []),
                        kev=list(kev or []))
    if scan_rows is None:
        return ev

    ev.scan_result = {'rows': len(scan_rows)}
    seen_ports = set()
    for row in scan_rows:
        text = ' '.join(str(row.get(k) or '') for k in
                        ('cve_name', 'description', 'service', 'evidence')).upper()
        port = row.get('port')
        if port not in (None, '', 0):
            key = (row.get('host'), port, row.get('protocol'))
            if key not in seen_ports:
                seen_ports.add(key)
                ev.open_ports.append({'host': row.get('host'), 'port': port,
                                      'protocol': row.get('protocol', 'tcp'),
                                      'state': row.get('state', 'open'),
                                      'service': row.get('service', ''),
                                      'version': row.get('version', '')})
        if row.get('cve_id'):
            ev.vulnerabilities.append(dict(row))
        if any(h in text for h in _WEAK_PWD_HINTS):
            ev.weak_passwords.append(dict(row))
        if any(h in text for h in _TLS_HINTS):
            ev.tls_findings.append(dict(row))

    if not ev.devices and ev.open_ports:
        ev.devices = _derive_devices(ev.open_ports)
    return ev


def _derive_devices(open_ports: List[Dict]) -> List[Dict]:
    """从开放端口重新推导设备指纹。

    scan_results 表只存端口与漏洞，不落设备识别结果，而设备指纹是
    国产化适配、工控暴露等条款的判定依据。若不在这里补推导，
    这些条款拿不到证据、永远只能报『证据不足』。
    指纹模块不可用时返回空列表——照旧走『证据不足』，不臆造设备。
    """
    try:
        from device_fingerprint import DeviceFingerprinter
    except ImportError as e:
        logger.warning(f'设备指纹模块不可用，合规检查将缺少设备证据: {e}')
        return []

    by_host: Dict[str, List[Dict]] = {}
    for p in open_ports:
        by_host.setdefault(p.get('host') or '', []).append(p)

    fingerprinter = DeviceFingerprinter()
    devices = []
    for host, ports in by_host.items():
        if not host:
            continue
        try:
            device = fingerprinter.identify_host(host, ports)
        except Exception as e:
            logger.error(f'设备指纹识别失败 {host}: {e}')
            continue
        if device.get('category'):
            devices.append(device)
    return devices


# ============================================================
# 条款目录加载
# ============================================================
def controls_dir() -> str:
    """条款目录路径。

    优先 BASE_DIR/compliance_controls（用户可编辑、可扩充），
    回退 PyInstaller 内置资源目录，最后回退模块同级目录。
    """
    candidates = [os.path.join(BASE_DIR, 'compliance_controls')]
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(os.path.join(meipass, 'compliance_controls'))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compliance_controls'))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


def _validate_standard(standard: str) -> str:
    """校验标准标识，防止路径穿越。

    standard 来自 REST 请求（路径参数与 JSON body）并被拼进文件路径，
    不校验则 '..\\..\\config' 之类的输入可读到条款目录之外的任意 .json 文件
    （Windows 上 '\\' 是合法的 URL 路径段字符，却是 os.path.join 的分隔符）。
    先挡分隔符与点段，再对现存目录做白名单匹配。
    """
    name = str(standard or '')
    if (not name or name in ('.', '..')
            or os.path.basename(name) != name
            or any(sep in name for sep in ('/', '\\'))):
        raise FileNotFoundError(f'非法的合规标准标识: {standard!r}')
    if name not in available_standards():
        raise FileNotFoundError(f'合规条款目录不存在: {name}')
    return name


def load_catalog(standard: str) -> Dict:
    """加载某标准的条款目录 JSON，返回 {standard, standard_name, version, controls:[ComplianceControl]}"""
    standard = _validate_standard(standard)
    path = os.path.join(controls_dir(), f'{standard}.json')
    if not os.path.isfile(path):
        raise FileNotFoundError(f'合规条款目录不存在: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    controls = [ComplianceControl.from_dict(c, standard) for c in raw.get('controls', [])]
    seen, dupes = set(), []
    for c in controls:
        if c.id in seen:
            dupes.append(c.id)
        seen.add(c.id)
    if dupes:
        logger.warning(f'{standard} 条款目录存在重复ID: {dupes}')
    return {
        'standard': raw.get('standard', standard),
        'standard_name': raw.get('standard_name', standard),
        'version': raw.get('version', ''),
        'controls': controls,
    }


def available_standards() -> List[str]:
    d = controls_dir()
    if not os.path.isdir(d):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.json'))


# ============================================================
# 引擎
# ============================================================
class ComplianceEngine:
    """合规检查引擎：加载条款 → 自动判定 → 合并问卷 → 应用AI研判 → 汇总计分"""

    def __init__(self, standard: str):
        self.standard = standard
        catalog = load_catalog(standard)
        self.standard_name = catalog['standard_name']
        self.version = catalog['version']
        self.controls: List[ComplianceControl] = catalog['controls']
        logger.info(f'合规引擎初始化: {self.standard_name}，条款 {len(self.controls)} 条')

    # ---- 条款筛选 ----
    def controls_for_level(self, level: str = 'ALL') -> List[ComplianceControl]:
        return [c for c in self.controls if c.applies_to_level(level)]

    def questionnaire_controls(self, level: str = 'ALL') -> List[ComplianceControl]:
        return [c for c in self.controls_for_level(level) if c.needs_questionnaire]

    # ---- 单条款判定 ----
    def _run_auto_check(self, control: ComplianceControl, evidence: EvidenceBundle) -> Optional[Dict]:
        """执行自动评估器。返回 None 表示该条款没有自动判定能力。"""
        if not control.has_auto_check:
            return None
        from compliance_checks import CHECK_REGISTRY
        fn = CHECK_REGISTRY.get(control.check)
        if fn is None:
            logger.warning(f'条款 {control.id} 指定的评估器不存在: {control.check}')
            return {'status': STATUS_INSUFFICIENT,
                    'detail': f'未实现的评估器: {control.check}',
                    'evidence': [], 'recommendation': ''}
        if not evidence.has(control.evidence_type):
            return {'status': STATUS_INSUFFICIENT,
                    'detail': f'缺少 {control.evidence_type} 类证据，无法自动判定。请先对目标执行扫描。',
                    'evidence': [], 'recommendation': ''}
        try:
            out = fn(evidence, control) or {}
            return {
                'status': out.get('status', STATUS_INSUFFICIENT),
                'detail': out.get('detail', ''),
                'evidence': out.get('evidence', []),
                'recommendation': out.get('recommendation', ''),
            }
        except Exception as e:
            logger.error(f'条款 {control.id} 自动评估异常: {e}')
            # 评估器崩溃不得静默判为符合
            return {'status': STATUS_INSUFFICIENT,
                    'detail': f'自动评估异常: {e}',
                    'evidence': [], 'recommendation': ''}

    @staticmethod
    def _merge_hybrid(auto_status: str, manual_status: str) -> str:
        """hybrid 条款合并技术判定与人工填报：取较差者（保守）。

        技术侧无结论时用人工侧，人工侧未填报时用技术侧。
        """
        auto_ok = auto_status in _STATUS_RANK
        manual_ok = manual_status in _STATUS_RANK
        if auto_ok and manual_ok:
            return auto_status if _STATUS_RANK[auto_status] <= _STATUS_RANK[manual_status] else manual_status
        if auto_ok:
            return auto_status
        if manual_ok:
            return manual_status
        # 两侧都无计分结论时，人工给出的明确判断优先于技术侧的『证据不足』：
        # 『不适用』是填报人对适用性的定论，『未填报』是可操作的待办，
        # 二者都比『证据不足』信息量大；早期版本只保住了『未填报』，
        # 导致人工明确标注的『不适用』被静默改写成『证据不足』。
        if manual_status in (STATUS_NA, STATUS_UNFILLED):
            return manual_status
        return auto_status

    def _evaluate_control(self, control: ComplianceControl,
                          evidence: EvidenceBundle,
                          answers: Dict[str, Dict]) -> Dict:
        auto = self._run_auto_check(control, evidence)
        answer = answers.get(control.id)

        manual_status = STATUS_UNFILLED
        if control.needs_questionnaire:
            if answer and answer.get('status') in ALL_STATUSES:
                manual_status = answer['status']

        if control.mode == MODE_AUTO:
            status = auto['status'] if auto else STATUS_INSUFFICIENT
            source = SOURCE_AUTO
            detail = auto['detail'] if auto else '该条款未配置自动评估器'
            ev = auto['evidence'] if auto else []
            rec = auto['recommendation'] if auto else ''
        elif control.mode == MODE_QUESTIONNAIRE:
            status = manual_status
            source = SOURCE_QUESTIONNAIRE
            detail = (answer or {}).get('note', '') or '尚未填报'
            ev = []
            rec = ''
        else:  # hybrid
            auto_status = auto['status'] if auto else STATUS_INSUFFICIENT
            status = self._merge_hybrid(auto_status, manual_status)
            source = SOURCE_AUTO if (auto and status == auto_status) else SOURCE_QUESTIONNAIRE
            parts = []
            if auto and auto.get('detail'):
                parts.append(f'[技术检查] {auto["detail"]}')
            if answer and answer.get('note'):
                parts.append(f'[人工填报] {answer["note"]}')
            detail = ' | '.join(parts) or '尚未填报且无技术证据'
            ev = auto['evidence'] if auto else []
            rec = auto['recommendation'] if auto else ''

        return {
            'control_id': control.id,
            'domain': control.domain,
            'category': control.category,
            'title': control.title,
            'requirement': control.requirement,
            'status': status,
            'severity': severity_for(status, control.weight),
            'evidence': ev,
            'detail': detail,
            'recommendation': rec,
            'verdict_source': source,
            'ai_status': AI_NOT_RUN,
            'ai_reasoning': '',
            'answer': answer or {},
            '_weight': control.weight,
            '_mode': control.mode,
            # 是否真的有人作答。不能用 status != 未填报 代替：hybrid 条款只要
            # 自动检查出了结论，合并后状态就不是『未填报』，据此统计会把
            # 『机器判出来的』算成『人填的』，虚报问卷完成度。
            '_answered': control.needs_questionnaire and manual_status != STATUS_UNFILLED,
        }

    # ---- 主入口 ----
    def evaluate(self, evidence: EvidenceBundle,
                 answers: Optional[Dict[str, Dict]] = None,
                 level: str = 'ALL') -> Dict:
        """执行合规判定（不含 AI）。AI 研判请在此之后调用 apply_ai_verdicts + summarize。"""
        started = datetime.now()
        answers = answers or {}
        controls = self.controls_for_level(level)
        results = [self._evaluate_control(c, evidence, answers) for c in controls]
        agg = self.summarize(results)
        agg.update({
            'standard': self.standard,
            'standard_name': self.standard_name,
            'version': self.version,
            'level': level,
            'target': evidence.target,
            'scope_key': evidence.scope_key,
            'timestamp': started.strftime('%Y-%m-%d %H:%M:%S'),
            'duration': round((datetime.now() - started).total_seconds(), 2),
        })
        return agg

    @staticmethod
    def apply_ai_verdicts(results: List[Dict], verdicts: Dict[str, Dict]) -> List[Dict]:
        """把 AI 研判结论合入结果。

        ⚠️ 『矛盾』会强制把状态改判为不符合——AI 发现填报与技术事实冲突时，
        自评不得凌驾于扫描到的硬事实之上。
        """
        for r in results:
            v = verdicts.get(r['control_id'])
            if not v:
                continue
            ai_status = v.get('ai_status', AI_NOT_RUN)
            r['ai_status'] = ai_status
            r['ai_reasoning'] = v.get('reasoning', '')
            if v.get('recommendation'):
                r['recommendation'] = v['recommendation']
            if ai_status == AI_CONFLICT and r['status'] in (STATUS_PASS, STATUS_PARTIAL):
                r['status'] = STATUS_FAIL
                r['severity'] = severity_for(STATUS_FAIL, r.get('_weight', 1.0))
                r['detail'] = (r.get('detail', '') +
                               ' | [AI交叉比对] 填报结论与技术证据矛盾，已强制改判为不符合').strip(' |')
            if ai_status in (AI_ENDORSED, AI_DOUBTED, AI_CONFLICT):
                r['verdict_source'] = SOURCE_AI_ASSISTED
        return results

    @staticmethod
    def summarize(results: List[Dict]) -> Dict:
        """汇总计分。分母排除 不适用/未填报/证据不足。"""
        counts = {s: 0 for s in ALL_STATUSES}
        counts['total'] = len(results)
        source_counts = {SOURCE_AUTO: 0, SOURCE_QUESTIONNAIRE: 0, SOURCE_AI_ASSISTED: 0}
        ai_counts = {AI_NOT_RUN: 0, AI_ENDORSED: 0, AI_DOUBTED: 0,
                     AI_CONFLICT: 0, AI_INCOMPLETE: 0}

        num = den = 0.0
        by_domain: Dict[str, Dict] = {}

        for r in results:
            st = r.get('status', STATUS_INSUFFICIENT)
            if st in counts:
                counts[st] += 1
            src = r.get('verdict_source', SOURCE_AUTO)
            if src in source_counts:
                source_counts[src] += 1
            ai = r.get('ai_status', AI_NOT_RUN)
            if ai in ai_counts:
                ai_counts[ai] += 1

            dom = r.get('domain', '未分类')
            d = by_domain.setdefault(dom, {s: 0 for s in ALL_STATUSES})
            d.setdefault('_num', 0.0)
            d.setdefault('_den', 0.0)
            d.setdefault('_cnt', 0)
            d[st] = d.get(st, 0) + 1

            w = float(r.get('_weight', 1.0))
            factor = score_factor(st, ai)
            if factor is not None:
                num += factor * w
                den += w
                d['_num'] += factor * w
                d['_den'] += w
                d['_cnt'] += 1

        for dom, d in by_domain.items():
            dn, dd, dc = d.pop('_num', 0.0), d.pop('_den', 0.0), d.pop('_cnt', 0)
            d['compliance_rate'] = round(dn / dd, 4) if dd else None
            d['scored'] = int(dc)

        scored_total = counts[STATUS_PASS] + counts[STATUS_PARTIAL] + counts[STATUS_FAIL]
        total = counts['total'] or 1
        auto_judged = source_counts[SOURCE_AUTO]

        q_controls = [r for r in results if r.get('_mode') in (MODE_QUESTIONNAIRE, MODE_HYBRID)]
        q_filled = [r for r in q_controls if _has_human_answer(r)]

        rate = round(num / den, 4) if den else None
        return {
            'counts': counts,
            'source_counts': source_counts,
            'ai_counts': ai_counts,
            'scored_total': scored_total,
            'auto_ratio': round(auto_judged / total, 4),
            'questionnaire_total': len(q_controls),
            'questionnaire_completion': round(len(q_filled) / len(q_controls), 4) if q_controls else None,
            'compliance_rate': rate,
            'score': int(round(rate * 100)) if rate is not None else None,
            'by_domain': by_domain,
            'results': results,
        }
