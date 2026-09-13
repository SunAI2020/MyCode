# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - AI扫描增强模块 (增强版)

使用本机 Claude Code（默认）或 Anthropic API（回退）对网络漏洞扫描结果进行智能核验和分析：
1. 批量核验 CVE 匹配准确性（版本是否真正受影响）
2. 智能风险重评估（超越 CVSS 数值）
3. 生成针对性修复建议
4. 过滤误报（版本不匹配、产品不相关、服务类型错误）
5. 支持版本范围预过滤以减少AI调用
"""
import json
import re
import logging
import threading
from typing import List, Dict, Optional, Callable, Tuple

from ai_client import AIClient, strip_markdown_fences

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# 增强版漏洞核验提示词
# ============================================================
VERIFY_VULN_SYSTEM_PROMPT = """你是资深网络安全专家，核验漏洞扫描器发现的 CVE 匹配是否为真实威胁。

误报类型（is_real=false）：产品不匹配；版本不在受影响范围；仅凭端口推断但实际服务不同；关键词巧合；已修复版本；OS/平台不匹配；组件未启用。

确认条件：产品一致或高度相关；版本在影响范围内或未知（保守）；KEV 已知利用倾向真实；CVSS>=7 且产品匹配倾向真实。

返回 JSON 数组（每个漏洞一个对象，按输入顺序）：
[{"cve_id":"CVE-xxxx","is_real":true/false,"confidence":0.0-1.0,"reasoning":"理由（中文简短）","actual_risk":"CRITICAL/HIGH/MEDIUM/LOW/INFO","remediation":"修复建议（一行）"}]

confidence>=0.7 高度确信；0.5-0.7 中等；<0.5 低确信倾向保守保留。信息不足时默认 is_real=true, confidence=0.5。"""

# Web 主动检测误报核验提示词（针对 web_vuln 结果，非 CVE 匹配）
WEB_VERIFY_SYSTEM_PROMPT = """你是资深 Web 渗透测试专家，核验 Web 主动扫描发现的漏洞是否为真实可利用威胁。

常见误报（is_real=false）：
- 反射型 XSS：payload 反射回响应但位于不可执行上下文（如属性值已转义、<textarea> 内文本、JSON 字符串已正确编码）
- 安全头缺失（CSP/HSTS/X-Frame-Options 等）：属于加固建议而非漏洞
- CORS 反射任意 Origin 但未携带凭据（无 Access-Control-Allow-Credentials: true）
- 指纹/信息泄露类：产品版本指纹本身不构成漏洞
- 指示符巧合：payload 未实际执行，仅字符串相似
- 认证绕过/IDOR：响应差异源于正常业务数据，无越权证据

确认条件（is_real=true）：payload 在可执行上下文被原样反射；SQL/命令/模板错误信息真实泄露；存在越权访问不同对象数据的证据；错误信息明确指向该漏洞。

返回 JSON 数组（每个 finding 一个对象，按输入顺序，index 与输入一致）：
[{"index":1,"is_real":true/false,"confidence":0.0-1.0,"reasoning":"理由（中文简短）","remediation":"修复建议（一行，可为空）"}]

confidence>=0.7 高度确信；<0.5 低确信倾向保守保留。证据不足时默认 is_real=true, confidence=0.5。"""

# ============================================================
# 风险分析提示词
# ============================================================
ANALYZE_SYSTEM_PROMPT = """你是一位资深安全分析师。请基于漏洞扫描结果，生成一份专业的安全分析报告。

你需要：
1. 评估目标系统的整体安全态势
2. 识别最关键的威胁和攻击向量
3. 提供有优先级的修复路线图
4. 给出可操作的具体修复步骤

请直接返回JSON格式，不要包含任何其他文本：
{
  "risk_score": 0-100,
  "risk_level": "CRITICAL/HIGH/MEDIUM/LOW/INFO",
  "executive_summary": "执行摘要(2-3句话)",
  "key_findings": ["发现1", "发现2", ...],
  "attack_surface": "攻击面分析(简要)",
  "remediation_priority": [
    {"rank": 1, "action": "修复动作", "cve_ids": ["CVE-xxx"], "urgency": "紧急/高/中/低", "timeframe": "时间范围"}
  ],
  "overall_recommendation": "综合建议"
}"""


class AIScanEnhancer:
    """AI扫描增强器 — 使用本机Claude Code（默认）或API Key（回退）批量核验漏洞并增强分析"""

    # 批次大小：每批发送给AI的漏洞数
    BATCH_SIZE = 6
    # 并行批次数：同时处理的AI批次数量
    PARALLEL_BATCHES = 3

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 db=None, stop_event: Optional[threading.Event] = None):
        """
        初始化AI扫描增强器

        Args:
            api_key: Anthropic API密钥（可选，默认使用本机Claude Code CLI）
            model: 使用的模型（可选，CLI模式下由CC SWITCH决定）
            db: Database实例（用于获取CVE详细信息）
            stop_event: 可选 threading.Event，置位后中断AI核验
        """
        self.client = AIClient(api_key=api_key, model=model)
        self.model = model
        self.db = db
        self.stop_event = stop_event
        self.verified_count = 0
        self.confirmed_count = 0
        self.excluded_count = 0
        self.pre_filtered_count = 0
        logger.info(f"AI扫描增强器初始化完成 (模型: {model or 'CLI默认'}, 批次大小: {self.BATCH_SIZE})")

    # ============ 版本范围预过滤 ============
    @staticmethod
    def _pre_filter_version(vuln: Dict) -> Tuple[bool, str]:
        """
        基于版本号与产品名快速预过滤明显不匹配的CVE匹配。
        返回 (是否应排除, 原因)
        """
        version = vuln.get('version', '').strip()

        # ---- 阶段1: 版本区间判断 ----
        # 目标版本至少含两段数字（X.Y），过短视为不可靠，不做区间排除
        target_version = None
        ver_match = re.search(r'(\d+(?:\.\d+){1,})', version)
        if ver_match:
            try:
                target_version = _parse_version(ver_match.group(1))
            except ValueError:
                target_version = None

        if target_version:
            desc = (vuln.get('description', '') or '').lower()
            affected = (vuln.get('affected_versions', '') or '').lower()
            text = f"{affected} | {desc}"

            min_ver, min_inclusive, max_ver, max_inclusive = _parse_affected_range(text)

            # 高于受影响上限 → 已修复 → 排除
            if max_ver is not None:
                if target_version > max_ver or (not max_inclusive and target_version == max_ver):
                    return True, f"目标版本 {version} 高于受影响范围上限 (已修复)"

            # 低于受影响下限 → 不受影响 → 排除
            if min_ver is not None:
                if target_version < min_ver or (not min_inclusive and target_version == min_ver):
                    return True, f"目标版本 {version} 低于受影响范围下限"

        # ---- 阶段2: 产品矛盾判断 ----
        # 仅当目标有【明确 product 字段】时才做产品矛盾排除。product 为空时
        # （socket 扫描只填 service/version），用 service 名宽泛映射判断会误排
        # Percona(MySQL)、Elasticsearch(端口9200报http) 等真实 CVE，故跳过。
        if (vuln.get('product') or '').strip():
            cve_products = _extract_cve_products(vuln)
            target_products = _extract_target_products(vuln)
            if cve_products and target_products and cve_products.isdisjoint(target_products):
                service = vuln.get('service', '')
                cve_list = ', '.join(sorted(cve_products))
                return True, f"CVE影响产品({cve_list})与目标服务({service})不匹配"

        return False, ''

    # ============ 批量核验 ============
    def verify_vulnerabilities(
        self,
        vulnerabilities: List[Dict],
        scan_context: str = "",
        progress_callback: Callable[[str], None] = None
    ) -> Dict:
        """
        批量核验漏洞列表，分离真实漏洞和误报（支持批量AI调用）

        Args:
            vulnerabilities: 漏洞列表
            scan_context: 扫描上下文描述
            progress_callback: 进度回调

        Returns:
            {'confirmed': [...], 'excluded': [...], 'pre_filtered': [...], 'stats': {...}}
        """
        if not vulnerabilities:
            return {'confirmed': [], 'excluded': [], 'pre_filtered': [], 'stats': {}}

        # 阶段0: 版本号预过滤（快速排除明显不符的CVE）
        candidates = []
        pre_filtered = []
        for vuln in vulnerabilities:
            should_exclude, reason = self._pre_filter_version(vuln)
            if should_exclude:
                vuln['ai_verified'] = True
                vuln['ai_confidence'] = 0.9
                vuln['ai_reasoning'] = reason
                vuln['excluded_reason'] = f'版本预过滤: {reason}'
                vuln['pre_filtered'] = True
                pre_filtered.append(vuln)
                self.pre_filtered_count += 1
            else:
                candidates.append(vuln)

        if progress_callback and pre_filtered:
            progress_callback(f"版本预过滤: {len(pre_filtered)} 个明显不匹配 → 已排除")

        if not candidates:
            return {
                'confirmed': [],
                'excluded': pre_filtered,
                'pre_filtered': pre_filtered,
                'stats': {
                    'total': len(vulnerabilities),
                    'confirmed': 0,
                    'excluded': len(pre_filtered),
                    'pre_filtered': len(pre_filtered),
                    'ai_verified': 0,
                    'exclusion_rate': 1.0,
                }
            }

        # 阶段1: 批量AI核验（并行处理多个批次）
        confirmed = []
        excluded = list(pre_filtered)
        total = len(candidates)
        batch_count = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE

        # 准备所有批次
        batches = []
        for batch_idx in range(batch_count):
            start = batch_idx * self.BATCH_SIZE
            end = min(start + self.BATCH_SIZE, total)
            batches.append((batch_idx, candidates[start:end]))

        if progress_callback:
            progress_callback(
                f"AI核验: 共 {batch_count} 个批次, {total} 个漏洞, "
                f"并行 {self.PARALLEL_BATCHES} 个批次..."
            )

        # 并行处理批次
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        _lock = threading.Lock()

        def _process_batch(batch_idx, batch):
            batch_num = batch_idx + 1
            try:
                batch_results = self._verify_batch(batch, scan_context)
                vuln_results = []
                for i, vuln in enumerate(batch):
                    result = batch_results[i] if i < len(batch_results) else None
                    vuln_results.append((vuln, result))
                return (batch_num, True, vuln_results, None)
            except Exception as e:
                logger.error(f"AI批量核验失败 (批次{batch_num}): {e}")
                vuln_results = [(vuln, None) for vuln in batch]
                return (batch_num, False, vuln_results, str(e))

        with ThreadPoolExecutor(max_workers=self.PARALLEL_BATCHES) as executor:
            futures = {executor.submit(_process_batch, bi, b): bi for bi, b in batches}
            for future in as_completed(futures):
                batch_num, ok, vuln_results, error = future.result()

                for vuln, result in vuln_results:
                    if result is None:
                        vuln['ai_verified'] = False
                        vuln['ai_confidence'] = 0.3
                        vuln['ai_reasoning'] = f'AI核验失败: {error or "解析失败"}，保守保留'
                        with _lock:
                            confirmed.append(vuln)
                        continue

                    vuln['ai_verified'] = True
                    vuln['ai_confidence'] = result.get('confidence', 0)
                    vuln['ai_reasoning'] = result.get('reasoning', '')

                    if not result.get('is_real') and result.get('confidence', 0) >= 0.5:
                        vuln['excluded_reason'] = result.get('reasoning', 'AI判定为误报')
                        with _lock:
                            excluded.append(vuln)
                            self.excluded_count += 1
                    else:
                        vuln['ai_assessed_risk'] = result.get('actual_risk', vuln.get('severity', 'INFO'))
                        vuln['ai_remediation'] = result.get('remediation', '')
                        with _lock:
                            confirmed.append(vuln)
                            self.confirmed_count += 1

                    with _lock:
                        self.verified_count += 1

                if progress_callback:
                    with _lock:
                        prog_confirmed = len(confirmed)
                        prog_excluded = len(excluded) - len(pre_filtered)
                    progress_callback(
                        f"AI核验批次 {batch_num}/{batch_count} 完成 | "
                        f"确认: {prog_confirmed}, 排除: {prog_excluded}"
                    )

        if progress_callback:
            progress_callback(
                f"AI核验完成: {total}个候选 → "
                f"{len(confirmed)}个确认, {len(excluded) - len(pre_filtered)}个AI排除, "
                f"{len(pre_filtered)}个预过滤"
            )

        return {
            'confirmed': confirmed,
            'excluded': excluded,
            'pre_filtered': pre_filtered,
            'stats': {
                'total': len(vulnerabilities),
                'confirmed': len(confirmed),
                'excluded': len(excluded),
                'pre_filtered': len(pre_filtered),
                'ai_verified': self.verified_count,
                'exclusion_rate': len(excluded) / len(vulnerabilities) if vulnerabilities else 0,
            }
        }

    def _verify_batch(self, vulns: List[Dict], scan_context: str) -> List[Dict]:
        """
        批量核验一组漏洞（一次AI调用处理多个CVE）

        Args:
            vulns: 漏洞列表（最多 BATCH_SIZE 个）
            scan_context: 扫描上下文

        Returns:
            核验结果列表（与输入顺序对应）
        """
        vuln_descriptions = []
        for i, v in enumerate(vulns, 1):
            desc = self._build_vuln_description(i, v)
            vuln_descriptions.append(desc)

        prompt = f"""请核验以下 {len(vulns)} 个漏洞是否为真实威胁：

目标上下文: {scan_context or '无额外上下文'}

{chr(10).join(vuln_descriptions)}

请对每个漏洞返回一个JSON对象（放在数组中），格式为：
[{{"cve_id": "CVE-xxxx", "is_real": true/false, "confidence": 0.0-1.0, "reasoning": "理由", "actual_risk": "CRITICAL/HIGH/MEDIUM/LOW/INFO", "remediation": "修复建议"}}, ...]

严格要求：
1. 必须返回与输入相同数量的JSON对象
2. 按输入顺序返回
3. 每个CVE独立判断
4. 只返回JSON数组，不要其他文字"""

        response_text = self.client.query(
            prompt,
            system_prompt=VERIFY_VULN_SYSTEM_PROMPT,
            stop_event=self.stop_event,
        )

        return self._parse_batch_response(response_text, len(vulns))

    def _build_vuln_description(self, index: int, vuln: Dict) -> str:
        """构建单个漏洞的详细描述（供批量核验使用，精简字段以降低 token 消耗）"""
        parts = [f"--- 漏洞 {index} ---", f"CVE编号: {vuln.get('cve_id', 'N/A')}"]

        service = vuln.get('service', '')
        if service:
            parts.append(f"服务: {service}")

        port = vuln.get('port', '')
        if port:
            parts.append(f"端口: {port}")

        version = vuln.get('version', '')
        if version:
            parts.append(f"版本: {version}")

        product = vuln.get('product', '')
        if product:
            parts.append(f"产品: {product}")

        cvss = vuln.get('cvss_score', '')
        if cvss:
            parts.append(f"CVSS: {cvss}")

        parts.append(f"严重度: {vuln.get('severity', 'INFO')}")
        parts.append(f"KEV: {'是' if vuln.get('kev') else '否'}")

        cve_desc = (vuln.get('description', '') or '').strip()
        if cve_desc:
            parts.append(f"描述: {cve_desc[:200]}")

        affected_ver = vuln.get('affected_versions', '')
        if affected_ver:
            parts.append(f"受影响版本: {affected_ver[:120]}")

        return '\n'.join(parts)

    def _parse_batch_response(self, text: str, expected_count: int) -> List[Dict]:
        """解析批量核验的JSON响应"""
        text = strip_markdown_fences(text)
        # 尝试直接解析整个响应为JSON数组
        try:
            results = json.loads(text)
            if isinstance(results, list):
                if len(results) == expected_count:
                    return results
                elif len(results) < expected_count:
                    logger.warning(
                        f"批量响应不完整: 期望{expected_count}个，实际{len(results)}个"
                    )
                    while len(results) < expected_count:
                        results.append({
                            'is_real': True, 'confidence': 0.3,
                            'reasoning': '批量响应缺失此项，保守保留',
                            'actual_risk': 'MEDIUM', 'remediation': ''
                        })
                    return results
                else:
                    return results[:expected_count]
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON数组
        array_match = re.search(r'\[.*\]', text, re.DOTALL)
        if array_match:
            try:
                results = json.loads(array_match.group(0))
                if isinstance(results, list):
                    while len(results) < expected_count:
                        results.append({
                            'is_real': True, 'confidence': 0.3,
                            'reasoning': '解析不完整，保守保留',
                            'actual_risk': 'MEDIUM', 'remediation': ''
                        })
                    return results[:expected_count]
            except json.JSONDecodeError:
                pass

        # 尝试逐个提取JSON对象
        individual_results = []
        for match in re.finditer(r'\{[^{}]*"is_real"[^{}]*\}', text):
            try:
                individual_results.append(json.loads(match.group(0)))
            except json.JSONDecodeError:
                continue

        if individual_results:
            while len(individual_results) < expected_count:
                individual_results.append({
                    'is_real': True, 'confidence': 0.3,
                    'reasoning': '部分解析失败，保守保留',
                    'actual_risk': 'MEDIUM', 'remediation': ''
                })
            return individual_results[:expected_count]

        # 完全解析失败，返回保守默认值
        logger.warning(f"批量响应完全解析失败: {text[:200]}")
        return [{
            'is_real': True, 'confidence': 0.3,
            'reasoning': 'AI响应解析失败，保守保留',
            'actual_risk': 'MEDIUM', 'remediation': ''
        }] * expected_count

    # ============ Web 主动检测误报核验 ============
    def verify_web_findings(self, findings: List[Dict], target: str = "",
                            progress_callback: Callable[[str], None] = None) -> Dict:
        """核验 Web 主动扫描发现（web_vuln 类）是否为真实威胁。

        仅核验 category == 'web_vuln' 且 severity 为 CRITICAL/HIGH/MEDIUM 的活跃检测项；
        指纹/安全头/目录等确定性配置发现直接跳过（非误报高发，节省 token）。
        """
        candidates = []
        skipped = []
        for f in findings:
            cat = f.get('category', '')
            sev = str(f.get('severity', '')).upper()
            if cat == 'web_vuln' and sev in ('CRITICAL', 'HIGH', 'MEDIUM'):
                candidates.append(f)
            else:
                skipped.append(f)

        if progress_callback:
            progress_callback(f"AI核验: 待核验 {len(candidates)} 项, 跳过 {len(skipped)} 项(确定性/低危)")

        if not candidates:
            return {
                'confirmed': skipped,
                'excluded': [],
                'skipped': skipped,
                'stats': {
                    'total': len(findings), 'confirmed': len(skipped),
                    'excluded': 0, 'skipped': len(skipped),
                    'ai_verified': 0, 'exclusion_rate': 0.0,
                }
            }

        total = len(candidates)
        batch_count = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE
        batches = []
        for batch_idx in range(batch_count):
            start = batch_idx * self.BATCH_SIZE
            end = min(start + self.BATCH_SIZE, total)
            batches.append((batch_idx, candidates[start:end]))

        if progress_callback:
            progress_callback(f"AI核验: {batch_count} 批, {total} 项, 并行 {self.PARALLEL_BATCHES}")

        confirmed = []
        excluded = []

        def _process_batch(batch_idx, batch):
            try:
                batch_results = self._verify_web_batch(batch, target)
                out = []
                for i, f in enumerate(batch):
                    r = batch_results[i] if i < len(batch_results) else None
                    out.append((f, r))
                return (batch_idx, out)
            except Exception as e:
                logger.error(f"Web核验批次{batch_idx + 1}异常: {e}")
                return (batch_idx, [(f, None) for f in batch])

        from concurrent.futures import ThreadPoolExecutor, as_completed
        # 先收集各批次结果，再按批次序号顺序装配，保证最终 finding 顺序确定
        batch_outputs = {}
        with ThreadPoolExecutor(max_workers=self.PARALLEL_BATCHES) as executor:
            futures = {executor.submit(_process_batch, bi, b): bi for bi, b in batches}
            for future in as_completed(futures):
                batch_idx, out = future.result()
                batch_outputs[batch_idx] = out
                if progress_callback:
                    progress_callback(f"AI核验批次 {batch_idx + 1}/{batch_count} 完成")

        for batch_idx in range(batch_count):
            _, batch = batches[batch_idx]
            out = batch_outputs.get(batch_idx, [(f, None) for f in batch])
            for f, r in out:
                if r is None:
                    f['ai_verified'] = False
                    f['ai_confidence'] = 0.3
                    f['ai_reasoning'] = 'AI核验失败/停止，保守保留'
                    confirmed.append(f)
                    continue
                f['ai_verified'] = True
                f['ai_confidence'] = r.get('confidence', 0)
                f['ai_reasoning'] = r.get('reasoning', '')
                # 仅在高确信判误报(is_real=False 且 confidence>=0.5)时排除；
                # 其余（含解析失败/低确信）一律保守保留
                is_confident_fp = (not r.get('is_real')) and r.get('confidence', 0) >= 0.5
                if is_confident_fp:
                    f['excluded_reason'] = r.get('reasoning', 'AI判定为误报')
                    excluded.append(f)
                else:
                    f['ai_remediation'] = r.get('remediation', '') or f.get('remediation', '')
                    confirmed.append(f)

        all_confirmed = confirmed + skipped
        ai_verified = total  # 所有候选均已 AI 核验
        if progress_callback:
            progress_callback(
                f"AI核验完成: {total}候选 → {len(confirmed)}确认, {len(excluded)}排除, {len(skipped)}跳过")

        return {
            'confirmed': all_confirmed,
            'excluded': excluded,
            'skipped': skipped,
            'stats': {
                'total': len(findings),
                'confirmed': len(all_confirmed),
                'excluded': len(excluded),
                'skipped': len(skipped),
                'ai_verified': ai_verified,
                'exclusion_rate': len(excluded) / ai_verified if ai_verified else 0.0,
            }
        }

    def _verify_web_batch(self, findings: List[Dict], target: str) -> List[Dict]:
        """单批核验 web findings，返回与输入顺序一致的核验结果列表。"""
        lines = [self._build_web_finding_description(i, f) for i, f in enumerate(findings, 1)]
        prompt = (
            f"请核验以下 {len(findings)} 个 Web 扫描发现是否为真实可利用漏洞：\n\n"
            f"目标: {target or '未知'}\n\n"
            + "\n".join(lines)
            + "\n\n请对每个发现返回一个 JSON 对象（放在数组中，index 与输入一致）：\n"
              '[{"index":1,"is_real":true/false,"confidence":0.0-1.0,"reasoning":"理由","remediation":"修复建议"}]'
        )
        response_text = self.client.query(
            prompt,
            system_prompt=WEB_VERIFY_SYSTEM_PROMPT,
            stop_event=self.stop_event,
        )
        return self._parse_web_batch_response(response_text, len(findings))

    @staticmethod
    def _build_web_finding_description(index: int, f: Dict) -> str:
        parts = [
            f"--- 发现 {index} ---",
            f"类型: {f.get('title', 'N/A')}",
            f"严重度: {f.get('severity', 'INFO')}",
        ]
        url = f.get('url', '')
        if url:
            parts.append(f"URL: {url}")
        param = f.get('parameter', '')
        if param:
            parts.append(f"参数: {param}")
        payload = f.get('payload', '')
        if payload:
            parts.append(f"Payload: {str(payload)[:200]}")
        evidence = f.get('evidence', '')
        if evidence:
            parts.append(f"证据: {str(evidence)[:200]}")
        detail = f.get('detail', '')
        if detail:
            parts.append(f"描述: {str(detail)[:200]}")
        return "\n".join(parts)

    @staticmethod
    def _parse_web_batch_response(text: str, expected_count: int) -> List[Dict]:
        text = strip_markdown_fences(text)
        results = None
        try:
            results = json.loads(text)
            if not isinstance(results, list):
                results = None
        except json.JSONDecodeError:
            results = None
        if results is None:
            m = re.search(r'\[.*\]', text, re.DOTALL)
            if m:
                try:
                    results = json.loads(m.group(0))
                except json.JSONDecodeError:
                    results = None

        final = []
        if isinstance(results, list):
            by_index = {}
            for obj in results:
                if isinstance(obj, dict):
                    try:
                        by_index[int(obj.get('index', -1))] = obj
                    except (TypeError, ValueError):
                        continue
            for i in range(1, expected_count + 1):
                final.append(by_index.get(i, {
                    'is_real': True, 'confidence': 0.3,
                    'reasoning': '批量响应缺失此项，保守保留', 'remediation': '',
                }))
        else:
            for i in range(1, expected_count + 1):
                final.append({
                    'is_real': True, 'confidence': 0.3,
                    'reasoning': 'AI响应解析失败，保守保留', 'remediation': '',
                })
        return final

    # ============ 逐条核验（回退模式） ============
    def _verify_single(self, vuln: Dict, scan_context: str) -> Dict:
        """逐条核验单个漏洞（当批量模式不可用时的回退）"""
        prompt = self._build_single_prompt(vuln, scan_context)

        response_text = self.client.query(
            prompt,
            system_prompt=VERIFY_VULN_SYSTEM_PROMPT
        )

        return self._parse_single_response(response_text)

    def _build_single_prompt(self, vuln: Dict, scan_context: str) -> str:
        """构建单个漏洞核验提示词"""
        parts = [
            f"目标信息: {scan_context or '无额外上下文'}",
            "",
            "漏洞详情:",
            f"- CVE编号: {vuln.get('cve_id', 'N/A')}",
            f"- 服务: {vuln.get('service', 'unknown')}",
            f"- 端口: {vuln.get('port', 'unknown')}",
            f"- 版本: {vuln.get('version', 'unknown')}",
            f"- 产品: {vuln.get('product', 'unknown')}",
            f"- CVSS评分: {vuln.get('cvss_score', 'N/A')}",
            f"- 严重度: {vuln.get('severity', 'INFO')}",
            f"- CVE描述: {vuln.get('description', '')[:300]}",
            f"- 是否KEV: {'是(已知被利用)' if vuln.get('kev') else '否'}",
        ]

        affected_ver = vuln.get('affected_versions', '')
        if affected_ver:
            parts.append(f"- 受影响版本: {affected_ver}")

        return '\n'.join(parts) + '\n\n请判断该CVE是否真实影响此目标，以JSON格式返回。'

    def _parse_single_response(self, text: str) -> Dict:
        """解析单个核验的JSON响应"""
        text = strip_markdown_fences(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{[^{}]*"is_real"[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法解析AI核验响应: {text[:200]}")
        return {
            'is_real': True,
            'confidence': 0.5,
            'reasoning': 'AI响应解析失败，保守保留',
            'actual_risk': 'MEDIUM',
            'remediation': '请手动评估此漏洞'
        }

    # ============ AI风险分析报告 ============
    def generate_ai_analysis(self, scan_result: Dict) -> Dict:
        """
        AI生成风险分析报告（替代纯规则引擎的分析）

        Args:
            scan_result: 扫描结果字典（含已核验的漏洞列表）

        Returns:
            AI生成的分析报告
        """
        vulns = scan_result.get('vulnerabilities', [])

        # 使用已确认的漏洞
        confirmed_vulns = [v for v in vulns if not v.get('excluded_reason')]
        if not confirmed_vulns:
            confirmed_vulns = vulns

        prompt = self._build_analysis_prompt(scan_result, confirmed_vulns)
        if not prompt:
            return self._fallback_analysis(scan_result)

        try:
            response_text = self.client.query(
                prompt,
                system_prompt=ANALYZE_SYSTEM_PROMPT,
                temperature=0.3,
                stop_event=self.stop_event,
            )
            return self._parse_analysis_response(response_text)

        except Exception as e:
            logger.error(f"AI分析生成失败: {e}")
            return self._fallback_analysis(scan_result)

    def _build_analysis_prompt(self, scan_result: Dict, confirmed_vulns: List[Dict]) -> str:
        """构建风险分析提示词"""
        summary = scan_result.get('summary', {})
        target = scan_result.get('target', 'Unknown')
        ai_stats = scan_result.get('ai_stats', {})

        sorted_vulns = sorted(
            confirmed_vulns,
            key=lambda x: (x.get('cvss_score') or 0),
            reverse=True
        )

        vuln_lines = []
        for i, v in enumerate(sorted_vulns[:20]):
            kev_tag = ' [KEV!]' if v.get('kev') else ''
            ai_risk = v.get('ai_assessed_risk', '')
            risk_note = f' AI评估:{ai_risk}' if ai_risk else ''
            vuln_lines.append(
                f"{i+1}. {v.get('cve_id', 'N/A')} | {v.get('service', '?')}:{v.get('port', '?')} "
                f"| CVSS:{v.get('cvss_score', '?')} | {v.get('severity', '?')}{kev_tag}{risk_note} "
                f"| {v.get('description', '')[:100]}"
            )

        if not vuln_lines:
            return ''

        parts = [
            f"扫描目标: {target}",
            f"确认漏洞数: {len(confirmed_vulns)}",
            f"严重度分布: {json.dumps(summary.get('by_severity', {}), ensure_ascii=False)}",
            f"高危+严重: {summary.get('high_critical', 0)}个",
        ]

        if ai_stats:
            parts.append(
                f"AI核验统计: 原始{ai_stats.get('total', '?')}个 → "
                f"确认{ai_stats.get('confirmed', '?')}个, "
                f"排除{ai_stats.get('excluded', '?')}个 "
                f"(误报率: {ai_stats.get('exclusion_rate', 0):.1%})"
            )

        parts.append('')
        parts.append('漏洞列表:')
        parts.append('\n'.join(vuln_lines))
        parts.append('')
        parts.append('请返回JSON格式的风险分析报告。')

        return '\n'.join(parts)

    def _parse_analysis_response(self, text: str) -> Dict:
        """解析AI分析响应"""
        text = strip_markdown_fences(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法解析AI分析响应: {text[:200]}")
        return {}

    def _fallback_analysis(self, scan_result: Dict) -> Dict:
        """当AI分析失败时的回退分析"""
        summary = scan_result.get('summary', {})
        ai_stats = scan_result.get('ai_stats', {})

        total = summary.get('total', 0)
        high_crit = summary.get('high_critical', 0)
        critical_count = summary.get('by_severity', {}).get('CRITICAL', 0)

        return {
            'risk_score': min(high_crit * 15 + critical_count * 10, 100),
            'risk_level': 'CRITICAL' if critical_count > 0 else (
                'HIGH' if high_crit > 3 else 'MEDIUM' if high_crit > 0 else 'LOW'
            ),
            'executive_summary': (
                f"AI分析暂时不可用。扫描发现{total}个漏洞，"
                f"其中{high_crit}个高危/严重漏洞。"
                f"{'AI核验已排除部分误报。' if ai_stats else ''}"
                f"请手动审核漏洞列表。"
            ),
            'key_findings': [
                f'发现{high_crit}个高危/严重漏洞需立即关注',
                'AI分析服务不可用，建议稍后启用AI核验重试',
            ],
            'attack_surface': '分析未完成',
            'remediation_priority': [],
            'overall_recommendation': (
                '建议启用AI核验获取详细分析和修复建议，或人工审核漏洞列表。'
                '优先修复CRITICAL和KEV标记的漏洞。'
            )
        }

    def get_statistics(self) -> Dict:
        """获取核验统计"""
        total_excluded = self.excluded_count + self.pre_filtered_count
        total_processed = self.verified_count + self.pre_filtered_count
        return {
            'total_verified': self.verified_count,
            'confirmed': self.confirmed_count,
            'excluded': self.excluded_count,
            'pre_filtered': self.pre_filtered_count,
            'total_excluded': total_excluded,
            'total_processed': total_processed,
            'fp_rate': total_excluded / total_processed if total_processed > 0 else 0,
        }


# ============ 产品归一化映射表 ============
# 规范产品名 -> 别名集合。数据基础取自 threat_intel.py `_match_cve` 的
# product_keywords / nmap_service_map / port_specific_map，组织成反向索引供预过滤复用。
_PRODUCT_ALIASES = {
    'openssh': {'openssh', 'openssh server', 'openssh-server', 'ssh'},
    'dropbear': {'dropbear', 'dropbear ssh'},
    'apache_httpd': {'apache', 'httpd', 'apache2', 'libapache2', 'apache http server', 'apache httpd'},
    'nginx': {'nginx'},
    'iis': {'iis', 'microsoft iis', 'internet information services', 'internet information'},
    'lighttpd': {'lighttpd'},
    'caddy': {'caddy'},
    'tomcat': {'tomcat', 'catalina', 'apache tomcat', 'apache-tomcat'},
    'jetty': {'jetty'},
    'squid': {'squid'},
    'openssl': {'openssl', 'libssl'},
    'mysql': {'mysql', 'mysqld', 'mysql server', 'mysql-server'},
    'mariadb': {'mariadb', 'mariadb server', 'mariadb-server'},
    'percona': {'percona', 'percona server', 'percona-server'},
    'postgresql': {'postgresql', 'postgres', 'postgresql server'},
    'redis': {'redis', 'redis server', 'redis-server'},
    'mongodb': {'mongodb', 'mongod', 'mongodb server'},
    'mssql': {'mssql', 'sql server', 'microsoft sql server', 'microsoft sql'},
    'oracle': {'oracle', 'oracledb', 'oracle database'},
    'php': {'php'},
    'python': {'python', 'cpython'},
    'nodejs': {'node.js', 'nodejs'},
    'java': {'java', 'jre', 'jdk', 'openjdk'},
    'samba': {'samba', 'smbd', 'nmbd', 'smb', 'cifs'},
    'vsftpd': {'vsftpd'},
    'proftpd': {'proftpd'},
    'pureftpd': {'pure-ftpd', 'pureftpd'},
    'sendmail': {'sendmail'},
    'postfix': {'postfix'},
    'exim': {'exim'},
    'dovecot': {'dovecot'},
    'bind': {'bind', 'named', 'bind9', 'dns server'},
    'elasticsearch': {'elasticsearch'},
    'kibana': {'kibana'},
    'logstash': {'logstash'},
    'docker': {'docker', 'docker engine', 'docker-engine'},
    'kubernetes': {'kubernetes', 'kube-apiserver', 'kubelet'},
    'jenkins': {'jenkins'},
    'gitlab': {'gitlab'},
    'wordpress': {'wordpress'},
    'drupal': {'drupal'},
    'rabbitmq': {'rabbitmq'},
    'memcached': {'memcached'},
    'django': {'django'},
    'flask': {'flask'},
    'spring': {'spring', 'spring boot', 'spring-boot', 'spring framework', 'spring-framework'},
    'laravel': {'laravel'},
    'vnc': {'vnc', 'realvnc', 'tightvnc'},
    'rdp': {'rdp', 'remote desktop', 'rdesktop', 'terminal services'},
    'telnet': {'telnet', 'telnetd'},
    'snmp': {'snmp', 'snmpd'},
    'openldap': {'openldap', 'ldap'},
    'kerberos': {'kerberos', 'krb5'},
    'dhcp': {'dhcp', 'dhcpd'},
    'nfs': {'nfs', 'nfsd'},
}

# nmap 服务名 -> 该服务可能的规范产品集合。仅收录能明确映射到具体产品的服务；
# 未收录的泛服务（如 msrpc/epmap/rpcbind）返回 None，不参与产品矛盾判断（保守）。
_SERVICE_TO_PRODUCTS = {
    'ssh': {'openssh', 'dropbear'},
    'http': {'apache_httpd', 'nginx', 'iis', 'lighttpd', 'caddy', 'tomcat', 'jetty'},
    'https': {'apache_httpd', 'nginx', 'iis', 'lighttpd', 'caddy', 'openssl'},
    'http-proxy': {'nginx', 'tomcat', 'jetty', 'squid'},
    'https-alt': {'openssl', 'tomcat', 'jetty'},
    'ssl': {'openssl'},
    'mysql': {'mysql', 'mariadb'},
    'postgresql': {'postgresql'},
    'mongod': {'mongodb'},
    'redis': {'redis'},
    'ftp': {'vsftpd', 'proftpd', 'pureftpd'},
    'smtp': {'sendmail', 'postfix', 'exim'},
    'smtps': {'sendmail', 'postfix', 'exim'},
    'pop3': {'dovecot'},
    'imap': {'dovecot'},
    'imaps': {'dovecot'},
    'pop3s': {'dovecot'},
    'domain': {'bind'},
    'netbios-ssn': {'samba'},
    'microsoft-ds': {'samba'},
    'ms-wbt-server': {'rdp'},
    'ms-sql-s': {'mssql'},
    'oracle': {'oracle'},
    'vnc': {'vnc'},
    'telnet': {'telnet'},
    'snmp': {'snmp'},
    'ldap': {'openldap'},
    'kerberos-sec': {'kerberos'},
    'nfs': {'nfs'},
}


# ============ 工具函数 ============
def _parse_version(ver_str: str) -> Tuple[int, ...]:
    """解析版本号字符串为可比较的元组（补齐到3段）。

    剥离预发布/构建后缀（如 -p1/-a1/-rc1/+/+deb10u1），只保留数字与点拆分；
    不足3段补0，超过4段截断。无法解析出任何数字段时抛 ValueError。

    支持单个字母补丁后缀（如 1.1.1k / 1.0.2a）：字母追加为其 ASCII 码，
    使 1.1.1k > 1.1.1 且 1.1.1a < 1.1.1k。
    """
    orig = ver_str.strip()
    ver_str = re.sub(r'[-+_].*$', '', orig)
    # 提取末尾单个字母（a-z）作为补丁后缀
    letter = ''
    m = re.search(r'([a-z])$', ver_str, re.IGNORECASE)
    if m:
        letter = m.group(1).lower()
        ver_str = ver_str[:m.start()]
    ver_str = re.sub(r'[^0-9.].*$', '', ver_str)
    parts = [p for p in ver_str.split('.') if p.isdigit()]
    if not parts:
        raise ValueError(f'无效版本号: {orig}')
    while len(parts) < 3:
        parts.append('0')
    result = [int(p) for p in parts[:4]]
    if letter:
        result.append(ord(letter))
    return tuple(result)


def _parse_affected_range(text: str) -> Tuple[Optional[Tuple[int, ...]], bool, Optional[Tuple[int, ...]], bool]:
    """从 CVE 文本解析受影响版本区间。

    返回 (下限, 下限边界是否含在受影响范围, 上限, 上限边界是否含在受影响范围)。
    None 表示未识别到对应边界。
    """
    ver = r'(\d+(?:\.\d+){1,}[a-z]?)'
    min_ver = None
    min_inclusive = False
    max_ver = None
    max_inclusive = False

    # 上限：before/prior to/earlier than X、< X（X 不含在受影响范围）；<= X（X 含在受影响范围）
    for pat, incl in [
        (r'(?:before|prior\s+to|earlier\s+than)\s+' + ver, False),
        (r'<=\s*' + ver, True),
        (r'<(?!\s*=)\s*' + ver, False),
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                max_ver = _parse_version(m.group(1))
                max_inclusive = incl
                break
            except ValueError:
                pass

    # 下限：>= X（X 含在受影响范围）；> X（X 不含）
    for pat, incl in [
        (r'>=\s*' + ver, True),
        (r'>(?!\s*=)\s*' + ver, False),
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                min_ver = _parse_version(m.group(1))
                min_inclusive = incl
                break
            except ValueError:
                pass

    # 区间：X through Y / X to Y（两端均含在受影响范围）
    m = re.search(ver + r'\s*(?:through|to)\s*' + ver, text, re.IGNORECASE)
    if m:
        try:
            min_ver = _parse_version(m.group(1))
            min_inclusive = True
            max_ver = _parse_version(m.group(2))
            max_inclusive = True
        except ValueError:
            pass

    return min_ver, min_inclusive, max_ver, max_inclusive


def _normalize_product(text: str) -> Optional[set]:
    """从文本提取规范产品名集合。

    对每个已知产品的别名做「词边界」子串匹配，命中则将规范产品加入结果。
    未命中任何已知产品返回 None（保守：调用方不做矛盾判断）。
    """
    if not text:
        return None
    text_lower = text.lower()
    matched = set()
    for canonical, aliases in _PRODUCT_ALIASES.items():
        for alias in aliases:
            pattern = r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])'
            if re.search(pattern, text_lower):
                matched.add(canonical)
                break
    return matched if matched else None


def _extract_cve_products(vuln: Dict) -> Optional[set]:
    """从漏洞条目提取 CVE 受影响产品集合。

    优先用 affected_versions 字段（实为 affected_products 文本），回退 description；
    两者都无法归一化返回 None。
    """
    affected = (vuln.get('affected_versions', '') or '').strip()
    if affected:
        prods = _normalize_product(affected)
        if prods:
            return prods
    desc = (vuln.get('description', '') or '').strip()
    if desc:
        return _normalize_product(desc)
    return None


def _extract_target_products(vuln: Dict) -> Optional[set]:
    """从漏洞条目提取目标（服务/产品）可能的规范产品集合。

    优先级：product 字段明确 → 收窄到该产品；否则用 service 的宽泛映射；
    再回退从 version 字符串提取。无法识别返回 None。
    """
    product = (vuln.get('product', '') or '').strip()
    if product:
        prods = _normalize_product(product)
        if prods:
            return prods

    service = (vuln.get('service', '') or '').strip().lower()
    if service and service in _SERVICE_TO_PRODUCTS:
        return set(_SERVICE_TO_PRODUCTS[service])

    version = (vuln.get('version', '') or '').strip()
    if version:
        return _normalize_product(version)
    return None
