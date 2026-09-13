"""
AI分析引擎 - 使用Claude进行智能渗透测试分析
核心功能：
1. 扫描结果分析
2. 攻击路径规划
3. Payload生成
4. 影响评估
"""
import anthropic
import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ExploitType(Enum):
    RCE = "rce"               # 远程代码执行
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    AUTH_BYPASS = "auth_bypass"
    PRIV_ESC = "privesc"         # 权限提升
    LATERAL_MOVEMENT = "lateral_movement"  # 横向移动
    INFO_DISCLOSURE = "info_disclosure"


@dataclass
class ScannedService:
    """扫描到的服务"""
    host_ip: str
    port: int
    protocol: str = "tcp"
    service_name: str = ""
    product: str = ""
    version: str = ""
    banner: str = ""


@dataclass
class Vulnerability:
    """漏洞信息"""
    cve_id: str
    description: str
    severity: str
    cvss_score: float
    product: str
    version: str
    cwe_id: str = ""
    exploit_available: bool = False
    patch_available: bool = True


@dataclass
class ExploitStep:
    """渗透步骤"""
    step_id: str
    order: int
    exploit_type: str
    target: str
    description: str
    payload: str = ""
    validation_cmd: str = ""
    risk_level: str = "medium"
    success_probability: float = 0.5


@dataclass
class ExploitPlan:
    """渗透计划"""
    plan_id: str
    target: str
    steps: List[ExploitStep]
    overall_success_probability: float
    estimated_time: str
    risks: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AnalysisReport:
    """分析报告"""
    vulnerabilities: List[Dict]
    priority_sorted: bool
    attack_paths: List[Dict]
    recommendations: List[str]
    risk_summary: Dict


class AIAnalyzer:
    """AI分析引擎"""

    # 系统提示词
    SYSTEM_PROMPT = """你是一名高级渗透测试专家，拥有20年以上的安全评估经验。你的专长包括：
1. 漏洞分析和优先级排序
2. 渗透攻击路径规划
3. Exploit开发与定制
4. 风险评估和影响分析

在分析扫描结果时，你需要：
1. 评估每个漏洞的实际可利用性（考虑版本、配置、环境）
2. 根据CVSS评分和实际利用难度排序优先级
3. 规划从初始入口到目标权限的最短攻击路径
4. 评估攻击成功后的潜在影响（数据泄露、权限提升、持久化）

重要原则：
- 只推荐合法、授权的渗透测试操作
- 不生成恶意利用代码
- 强调防御建议
- 考虑法律和道德边界"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        初始化AI分析器

        Args:
            api_key: Claude API密钥
            model: 使用的模型
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze_scan_results(
        self,
        services: List[ScannedService],
        vulns: List[Vulnerability]
    ) -> AnalysisReport:
        """
        分析扫描结果，生成风险评估

        Args:
            services: 扫描到的服务列表
            vulns: 发现的漏洞列表

        Returns:
            AnalysisReport: 分析报告
        """
        logger.info(f"开始分析 {len(services)} 个服务 和 {len(vulns)} 个漏洞")

        # 构建输入数据
        analysis_input = self._build_analysis_input(services, vulns)

        # 调用Claude进行分析
        prompt = f"""请分析以下扫描结果，并提供详细的安全分析报告：

{analysis_input}

请以JSON格式返回分析结果，包含以下字段：
{{
    "vulnerabilities": [
        {{
            "cve_id": "CVE-XXXX-XXXX",
            "severity": "critical/high/medium/low",
            "priority": 1,
            "exploitability": "高/中/低",
            "description": "漏洞描述"
        }}
    ],
    "attack_paths": [
        {{
            "path_id": 1,
            "entry_point": "服务名",
            "steps": ["步骤1", "步骤2", "步骤3"],
            "success_probability": 0.8,
            "risk_level": "high"
        }}
    ],
    "recommendations": ["建议1", "建议2"],
    "risk_summary": {{
        "critical_count": 0,
        "high_count": 0,
        "overall_risk": "high"
    }}
}}

只返回JSON，不要其他内容。"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=[{"type": "text", "text": self.SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": prompt}]
            )

            # 解析响应
            result_text = response.content[0].text
            result = self._parse_json_response(result_text)

            return AnalysisReport(
                vulnerabilities=result.get("vulnerabilities", []),
                priority_sorted=True,
                attack_paths=result.get("attack_paths", []),
                recommendations=result.get("recommendations", []),
                risk_summary=result.get("risk_summary", {})
            )

        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return self._fallback_analysis(services, vulns)

    def plan_exploit_path(
        self,
        services: List[ScannedService],
        vulns: List[Vulnerability],
        target_goal: str = "get_shell"
    ) -> ExploitPlan:
        """
        规划渗透攻击路径

        Args:
            services: 扫描到的服务
            vulns: 发现的漏洞
            target_goal: 目标 (get_shell, get_root, data_access)

        Returns:
            ExploitPlan: 渗透计划
        """
        logger.info(f"规划渗透路径，目标: {target_goal}")

        # 构建输入数据
        plan_input = self._build_planning_input(services, vulns, target_goal)

        prompt = f"""基于以下扫描结果，请规划从初始入口到目标的渗透攻击路径：

{plan_input}

目标: {target_goal}

请以JSON格式返回详细的攻击计划：
{{
    "plan_id": "plan_001",
    "target": "目标描述",
    "overall_success_probability": 0.75,
    "estimated_time": "30分钟",
    "steps": [
        {{
            "step_id": "step_1",
            "order": 1,
            "exploit_type": "rce/sql_injection/privesc",
            "target": "目标服务",
            "description": "步骤描述",
            "payload": "示例payload（不执行，仅���分��）",
            "validation_cmd": "验证命令",
            "risk_level": "high",
            "success_probability": 0.8
        }}
    ],
    "risks": ["风险1", "风险2"],
    "prerequisites": ["前置条件1"]
}}

只返回JSON格式。"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=[{"type": "text", "text": self.SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            result = self._parse_json_response(result_text)

            # 构建ExploitPlan
            steps = []
            for i, step_data in enumerate(result.get("steps", [])):
                steps.append(ExploitStep(
                    step_id=step_data.get("step_id", f"step_{i+1}"),
                    order=step_data.get("order", i+1),
                    exploit_type=step_data.get("exploit_type", ""),
                    target=step_data.get("target", ""),
                    description=step_data.get("description", ""),
                    payload=step_data.get("payload", ""),
                    validation_cmd=step_data.get("validation_cmd", ""),
                    risk_level=step_data.get("risk_level", "medium"),
                    success_probability=step_data.get("success_probability", 0.5)
                ))

            return ExploitPlan(
                plan_id=result.get("plan_id", "plan_001"),
                target=result.get("target", target_goal),
                steps=steps,
                overall_success_probability=result.get("overall_success_probability", 0.5),
                estimated_time=result.get("estimated_time", "未知"),
                risks=result.get("risks", [])
            )

        except Exception as e:
            logger.error(f"规划失败: {e}")
            return self._fallback_plan(services, vulns)

    def generate_payload(
        self,
        vuln: Vulnerability,
        target: ScannedService,
        context: Dict = None
    ) -> str:
        """
        生成针对特定漏洞的利用Payload

        Args:
            vuln: 目标漏洞
            target: 目标服务
            context: 额外上下文

        Returns:
            str: Payload建议（非实际执行代码）
        """
        logger.info(f"为 {vuln.cve_id} 生成Payload建议")

        prompt = f"""作为安全专家，请为以下漏洞场景提供利用思路分析：

漏洞信息:
- CVE: {vuln.cve_id}
- 描述: {vuln.description}
- 产品: {vuln.product} {vuln.version}
- CVSS: {vuln.cvss_score}

目标服务:
- IP: {target.host_ip}
- 端口: {target.port}
- 服务: {target.service_name} {target.version}

请提供：
1. 利用前提条件
2. 攻击步骤分析（仅供防御测试）
3. 验证方法
4. 风险警示
5. 防御建议

注意：只提供防御和验证思路，不提供实际攻击代码。"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=[{"type": "text", "text": "你是一名安全专家，提供防御建议而非攻击工具。"}],
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"生成失败: {e}")
            return f"Payload生成失败: {e}"

    def validate_exploit(
        self,
        vuln: Vulnerability,
        target: ScannedService
    ) -> Dict:
        """
        验证漏洞可利用性

        Args:
            vuln: 漏洞
            target: 目标

        Returns:
            Dict: 验证结果
        """
        logger.info(f"验证 {vuln.cve_id} 可利用性")

        prompt = f"""请评估以下漏洞的可利用性：

CVE: {vuln.cve_id}
产品: {vuln.product} {vuln.version}
目标: {target.host_ip}:{target.port} ({target.service_name})

请返回JSON格式：
{{
    "exploitable": true/false,
    "confidence": "high/medium/low",
    "reasons": ["原因1"],
    "requirements": ["要求1"],
    "difficulty": "easy/medium/hard"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            return self._parse_json_response(response.content[0].text)

        except Exception as e:
            logger.error(f"验证失败: {e}")
            return {"exploitable": False, "error": str(e)}

    def evaluate_impact(
        self,
        vulns: List[Vulnerability],
        target_services: List[ScannedService]
    ) -> Dict:
        """
        评估漏洞影响范围

        Args:
            vulns: 漏洞列表
            target_services: 目标服务

        Returns:
            Dict: 影响评估
        """
        logger.info(f"评估影响范围，{len(vulns)} 个漏洞，{len(target_services)} 个服务")

        impact_input = self._build_impact_input(vulns, target_services)

        prompt = f"""请评估以下漏洞组合的潜在影响：

{impact_input}

请返回JSON格式：
{{
    "impact_level": "critical/high/medium/low",
    "affected_systems": ["系统1"],
    "potential_damage": ["影响1"],
    "recommendations": ["建议1"],
    "urgent_actions": ["动作1"]
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            return self._parse_json_response(response.content[0].text)

        except Exception as e:
            logger.error(f"评估失败: {e}")
            return {"impact_level": "unknown", "error": str(e)}

    # 辅助方法

    def _build_analysis_input(
        self,
        services: List[ScannedService],
        vulns: List[Vulnerability]
    ) -> str:
        """构建分析输入"""
        service_info = "\n".join([
            f"- {s.host_ip}:{s.port} - {s.service_name} {s.product} {s.version}"
            for s in services
        ])

        vuln_info = "\n".join([
            f"- {v.cve_id} [{v.severity.upper()}] CVSS:{v.cvss_score} - {v.description[:100]}"
            for v in vulns
        ])

        return f"""发现的服务:
{service_info}

发现的漏洞:
{vuln_info}"""

    def _build_planning_input(
        self,
        services: List[ScannedService],
        vulns: List[Vulnerability],
        target_goal: str
    ) -> str:
        """构建规划输入"""
        return self._build_analysis_input(services, vulns) + f"\n\n目标: {target_goal}"

    def _build_impact_input(
        self,
        vulns: List[Vulnerability],
        services: List[ScannedService]
    ) -> str:
        """构建影响评估输入"""
        vuln_info = "\n".join([
            f"- {v.cve_id}: {v.description[:80]}"
            for v in vulns
        ])

        service_info = "\n".join([
            f"- {s.host_ip}:{s.port} ({s.service_name})"
            for s in services
        ])

        return f"""漏洞: \n{vuln_info}\n\n受影响服务:\n{service_info}"""

    def _parse_json_response(self, text: str) -> Dict:
        """解析JSON响应"""
        try:
            # 尝试提取JSON块
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]

            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return {}

    def _fallback_analysis(
        self,
        services: List[ScannedService],
        vulns: List[Vulnerability]
    ) -> AnalysisReport:
        """备用分析（当AI失败时）"""
        vulns_by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for v in vulns:
            if v.severity.upper() in vulns_by_severity:
                vulns_by_severity[v.severity.upper()].append(v)

        return AnalysisReport(
            vulnerabilities=[
                {
                    "cve_id": v.cve_id,
                    "severity": v.severity,
                    "priority": i + 1
                }
                for severity in ["critical", "high", "medium", "low"]
                for i, v in enumerate(vulns_by_severity[severity])
            ],
            priority_sorted=True,
            attack_paths=[],
            recommendations=["使用专业工具进行进一步分析"],
            risk_summary={
                "critical_count": len(vulns_by_severity["critical"]),
                "high_count": len(vulns_by_severity["high"]),
                "overall_risk": "high" if vulns_by_severity["critical"] else "medium"
            }
        )

    def _fallback_plan(
        self,
        services: List[ScannedService],
        vulns: List[Vulnerability]
    ) -> ExploitPlan:
        """备用计划"""
        steps = []
        for i, v in enumerate(vulns[:5]):
            steps.append(ExploitStep(
                step_id=f"step_{i+1}",
                order=i+1,
                exploit_type="rce",
                target=f"{v.product} {v.version}",
                description=v.description[:100],
                risk_level=v.severity,
                success_probability=v.cvss_score / 10.0
            ))

        return ExploitPlan(
            plan_id="fallback_plan",
            target="unknown",
            steps=steps,
            overall_success_probability=0.3,
            estimated_time="需要进一步分析",
            risks=["需要人工确认"]
        )


def create_analyzer(api_key: str, model: str = "claude-sonnet-4-20250514") -> AIAnalyzer:
    """创建AI分析器实例"""
    return AIAnalyzer(api_key=api_key, model=model)


# 测试
if __name__ == "__main__":
    # 示例用法
    print("AI分析引擎模块")
    print("=" * 50)

    # 创建示例数据
    services = [
        ScannedService(
            host_ip="192.168.1.100",
            port=80,
            service_name="http",
            product="Apache",
            version="2.4.50",
            banner="Apache/2.4.50"
        ),
        ScannedService(
            host_ip="192.168.1.100",
            port=22,
            service_name="ssh",
            product="OpenSSH",
            version="8.9",
            banner="OpenSSH_8.9"
        )
    ]

    vulns = [
        Vulnerability(
            cve_id="CVE-2025-49125",
            description="Apache Tomcat RCE漏洞",
            severity="critical",
            cvss_score=9.8,
            product="Apache Tomcat",
            version="9.0.0-10.0.0"
        ),
        Vulnerability(
            cve_id="CVE-2025-32803",
            description="OpenSSH权限提升",
            severity="high",
            cvss_score=7.5,
            product="OpenSSH",
            version="8.0-8.9"
        )
    ]

    print("\n示例数据:")
    print(f"  服务: {len(services)} 个")
    print(f"  漏洞: {len(vulns)} 个")

    print("\n使用方法:")
    print("""">
from core.ai_analyzer import create_analyzer, ScannedService, Vulnerability

# 初始化
ai = create_analyzer(api_key="sk-ant-...")

# 分析扫描结果
report = ai.analyze_scan_results(services, vulns)

# 规划攻击路径
plan = ai.plan_exploit_path(services, vulns, target_goal="get_shell")

# 生成Payload建议
payload = ai.generate_payload(vulns[0], services[0])
""")