"""
确定性路由单元测试：AI 输出的 exploit_type / tool 应被 route_ai_steps 正确修正。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.capabilities import route_ai_steps, build_capability_prompt, VALID_TYPES


def _step(exploit_type="rce", tool="", description="", payload=""):
    return {
        "exploit_type": exploit_type,
        "tool": tool,
        "description": description,
        "payload": payload,
    }


class TestRouteAI(unittest.TestCase):
    """关键词/CVE 兜底路由"""

    def test_ms17_010_routed_to_msf(self):
        steps = [_step(exploit_type="rce", description="利用 MS17-010 EternalBlue 漏洞")]
        route_ai_steps(steps)
        self.assertEqual(steps[0]["exploit_type"], "msf")
        self.assertEqual(steps[0]["tool"], "exploit/windows/smb/ms17_010_eternalblue")

    def test_smbghost_routed_to_msf(self):
        steps = [_step(exploit_type="rce", description="尝试 SMBGhost CVE-2020-0796")]
        route_ai_steps(steps)
        self.assertEqual(steps[0]["exploit_type"], "msf")
        self.assertEqual(steps[0]["tool"], "exploit/windows/smb/cve_2020_0796_smbghost")

    def test_netlogon_routed_to_privesc(self):
        steps = [_step(exploit_type="rce", description="利用 Netlogon 特权提升 CVE-2022-38023")]
        route_ai_steps(steps)
        self.assertEqual(steps[0]["exploit_type"], "privesc")

    def test_complete_structured_answer_not_overridden(self):
        steps = [_step(
            exploit_type="msf",
            tool="exploit/windows/smb/ms17_010_eternalblue",
            description="MS17-010",
        )]
        route_ai_steps(steps)
        self.assertEqual(steps[0]["exploit_type"], "msf")
        self.assertEqual(steps[0]["tool"], "exploit/windows/smb/ms17_010_eternalblue")

    def test_invalid_type_falls_back_to_rce(self):
        steps = [_step(exploit_type="something_weird", description="无关键词")]
        route_ai_steps(steps)
        self.assertEqual(steps[0]["exploit_type"], "rce")


class TestCapabilities(unittest.TestCase):
    """能力目录完整性"""

    def test_prompt_lists_all_types(self):
        text = build_capability_prompt()
        for t in VALID_TYPES:
            self.assertIn(t, text)

    def test_manual_types_present(self):
        for t in ("sql_injection", "xss", "auth_bypass", "info_disclosure"):
            self.assertIn(t, VALID_TYPES)


if __name__ == "__main__":
    unittest.main()
