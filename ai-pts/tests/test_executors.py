"""
专项工具执行器单元测试

覆盖：
- ToolExecutor 基类安全逻辑（主机名校验、白名单 fail-closed、凭据打码）
- 各专项工具的命令构建（impacket / msf / secretsdump / netexec / bloodhound / mimikatz）
- msfconsole resource 脚本注入防护
- 人工确认闸门（require_confirmation + confirm_callback）
"""
import asyncio
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.executors.base import ToolExecutor
from core.executors.getshell import ImpacketExecExecutor, MSFGetShellExecutor
from core.executors.privesc import SecretsDumpExecutor, LinPEASExecutor
from core.executors.lateral import NetExecExecutor, BloodHoundCollector, MimikatzExecutor
from core.workflow import StepInput, StepOutput, StepStatus, ManualReviewExecutor, resolve_step_targets
from core.scanner import _to_vulnerability


def _input(target="10.0.0.1", credentials=None, **creds):
    return StepInput(target=target, credentials=credentials if credentials is not None else creds)


class TestToolExecutorBase(unittest.TestCase):
    """基类安全辅助方法"""

    def test_extract_host(self):
        self.assertEqual(ToolExecutor._extract_host("192.168.1.1:445"), "192.168.1.1")
        self.assertEqual(ToolExecutor._extract_host("http://host/path"), "host")
        self.assertEqual(ToolExecutor._extract_host("host"), "host")
        self.assertEqual(ToolExecutor._extract_host(""), "")

    def test_validate_host(self):
        self.assertTrue(ToolExecutor._validate_host("192.168.1.1"))
        self.assertTrue(ToolExecutor._validate_host("dc01.corp.local"))
        self.assertFalse(ToolExecutor._validate_host("host; rm -rf /"))
        self.assertFalse(ToolExecutor._validate_host("host$(whoami)"))
        self.assertFalse(ToolExecutor._validate_host("host && nc -e /bin/sh"))

    def test_in_whitelist_fail_closed(self):
        # 空白名单 + 非 allow_all = 拒绝
        ex = ToolExecutor(tool_name="echo", whitelist=[], allow_all=False)
        self.assertFalse(ex._in_whitelist("192.168.1.1"))
        # 命中白名单放行
        ex2 = ToolExecutor(tool_name="echo", whitelist=["192.168.1.1"], allow_all=False)
        self.assertTrue(ex2._in_whitelist("192.168.1.1"))
        self.assertFalse(ex2._in_whitelist("10.0.0.1"))

    def test_redact_cmd_masks_credentials(self):
        out = ToolExecutor._redact_cmd(
            ["wmiexec.py", "corp/admin:secret@10.0.0.1", "whoami"]
        )
        self.assertNotIn("secret", out[1])
        self.assertIn("***", out[1])

    def test_redact_cmd_masks_hashes(self):
        out = ToolExecutor._redact_cmd(
            ["secretsdump.py", "-hashes", "aad3b435b51404ee:0x00", "admin@10.0.0.1"]
        )
        self.assertIn("***", out[2])  # -hashes 后的值被替换
        self.assertNotIn("aad3b435b51404ee", out[2])


class TestBuildCommands(unittest.TestCase):
    """各专项工具命令构建"""

    def test_impacket_command(self):
        ex = ImpacketExecExecutor(method="wmiexec.py")
        cmd = ex.build_command(_input(credentials={"username": "admin", "password": "P@ss"}), {})
        # WinError 193 修复后：用解释器执行脚本全路径，而非直接跑 .py
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith("wmiexec.py"))
        self.assertIn("admin:P@ss@10.0.0.1", cmd)

    def test_impacket_tool_override(self):
        ex = ImpacketExecExecutor(method="wmiexec.py")
        cmd = ex.build_command(
            _input(credentials={"username": "admin", "password": "P@ss"}),
            {"tool": "psexec.py"},
        )
        self.assertTrue(cmd[1].endswith("psexec.py"))

    def test_secretsdump_hashes(self):
        ex = SecretsDumpExecutor()
        cmd = ex.build_command(
            _input(credentials={"username": "admin", "hashes": "aad3b435b51404ee:0x00"}),
            {},
        )
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith("secretsdump.py"))
        self.assertIn("-hashes", cmd)

    def test_linpeas_command(self):
        ex = LinPEASExecutor()
        cmd = ex.build_command(_input(credentials={"username": "root"}), {})
        self.assertEqual(cmd[0], "ssh")
        self.assertIn("root@10.0.0.1", cmd)

    def test_msf_rejects_resource_injection(self):
        ex = MSFGetShellExecutor()
        cmd = ex.build_command(_input(), {"exploit": "exploit/multi/handler; rm -rf /"})
        self.assertIsNone(cmd)

    def test_msf_rejects_bad_lhost(self):
        ex = MSFGetShellExecutor()
        cmd = ex.build_command(_input(), {"lhost": "127.0.0.1; touch /tmp/x"})
        self.assertIsNone(cmd)

    def test_msf_valid_command(self):
        ex = MSFGetShellExecutor()
        cmd = ex.build_command(
            _input(),
            {"exploit": "exploit/multi/handler", "payload": "windows/meterpreter/reverse_tcp"},
        )
        self.assertIsNotNone(cmd)
        self.assertIn(cmd[0], ("msfconsole", "docker"))
        self.assertIn("use exploit/multi/handler", cmd[-1])
        self.assertIn("set RHOSTS 10.0.0.1", cmd[-1])

    def test_msf_docker_localhost_translated(self):
        if shutil.which("msfconsole"):
            self.skipTest("本机有原生 msfconsole，跳过 docker 映射测试")
        ex = MSFGetShellExecutor()
        cmd = ex.build_command(_input(target="127.0.0.1"), {"exploit": "exploit/multi/handler"})
        self.assertIsNotNone(cmd)
        self.assertIn("set RHOSTS host.docker.internal", cmd[-1])

    def test_msf_tool_module(self):
        ex = MSFGetShellExecutor()
        cmd = ex.build_command(
            _input(),
            {"tool": "exploit/windows/smb/ms17_010_eternalblue"},
        )
        self.assertIsNotNone(cmd)
        self.assertIn("use exploit/windows/smb/ms17_010_eternalblue", " ".join(cmd))

    def test_msf_tool_rejects_injection(self):
        # tool 字段走与 exploit 相同的 _MSF_NAME_RE 校验，拒绝命令注入字符
        ex = MSFGetShellExecutor()
        cmd = ex.build_command(_input(), {"tool": "exploit/multi/handler; rm -rf /"})
        self.assertIsNone(cmd)

    def test_netexec_command(self):
        ex = NetExecExecutor()
        cmd = ex.build_command(_input(credentials={"username": "admin", "password": "P@ss"}), {})
        # 本机无 nxc 但装 WSL 时，经 wsl 调用
        self.assertIn(cmd[0], ("nxc", "wsl"))
        self.assertIn("-u", cmd)
        self.assertIn("admin", cmd)

    def test_bloodhound_command(self):
        ex = BloodHoundCollector()
        cmd = ex.build_command(
            _input(credentials={"username": "u", "password": "p", "domain": "corp.local"}),
            {},
        )
        self.assertEqual(cmd[0], "bloodhound-python")
        self.assertIn("-d", cmd)
        self.assertIn("corp.local", cmd)

    def test_mimikatz_command(self):
        ex = MimikatzExecutor()
        cmd = ex.build_command(_input(), {})
        self.assertEqual(cmd[0], "mimikatz.exe")
        self.assertIn("sekurlsa::logonpasswords", cmd)


class TestValidationGate(unittest.TestCase):
    """白名单 + 人工确认闸门"""

    def test_validate_rejects_non_whitelisted(self):
        ex = ImpacketExecExecutor(whitelist=["10.0.0.1"], allow_all=False)
        ex._tool_available = lambda tool=None: True  # 屏蔽"工具未安装"检查
        ok = asyncio.run(ex.validate(_input(target="192.168.1.1")))
        self.assertFalse(ok)

    def test_validate_accepts_whitelisted(self):
        ex = ImpacketExecExecutor(whitelist=["10.0.0.1"], allow_all=False)
        ex._tool_available = lambda tool=None: True
        ok = asyncio.run(ex.validate(_input(target="10.0.0.1")))
        self.assertTrue(ok)

    def test_execute_requires_confirmation_callback(self):
        ex = ImpacketExecExecutor(
            whitelist=["10.0.0.1"], allow_all=False, require_confirmation=True
        )
        ex._tool_available = lambda tool=None: True
        out = asyncio.run(ex.execute(_input(target="10.0.0.1"), {}))
        self.assertEqual(out.status, StepStatus.SKIPPED)

    def test_execute_confirmation_denied(self):
        ex = ImpacketExecExecutor(
            whitelist=["10.0.0.1"], allow_all=False,
            require_confirmation=True, confirm_callback=lambda host: False,
        )
        ex._tool_available = lambda tool=None: True
        out = asyncio.run(ex.execute(_input(target="10.0.0.1"), {}))
        self.assertEqual(out.status, StepStatus.SKIPPED)


class TestManualReviewExecutor(unittest.TestCase):
    """暂无自动化专项工具的漏洞类型（sql_injection/xss/...）"""

    def test_returns_skipped_with_note(self):
        ex = ManualReviewExecutor()
        out = asyncio.run(ex.execute(_input(), {}))
        self.assertEqual(out.status, StepStatus.SKIPPED)
        self.assertIn("人工验证", out.error)


class TestResolveStepTargets(unittest.TestCase):
    """AI/fallback 计划的描述性 target 应归一化为真实主机 IP"""

    def test_descriptive_target_falls_back_to_host(self):
        steps = [{"target": "Microsoft Windows RPC"}, {"target": "Apache HTTPD"}]
        resolve_step_targets(steps, ["10.0.0.1"])
        self.assertEqual(steps[0]["target"], "10.0.0.1")
        self.assertEqual(steps[1]["target"], "10.0.0.1")

    def test_host_port_normalized(self):
        steps = [{"target": "192.168.1.100:8080"}, {"target": "http://host/path"}]
        resolve_step_targets(steps, [])
        self.assertEqual(steps[0]["target"], "192.168.1.100")
        self.assertEqual(steps[1]["target"], "host")

    def test_no_hosts_and_descriptive_yields_empty(self):
        steps = [{"target": "some description"}]
        resolve_step_targets(steps, [])
        self.assertEqual(steps[0]["target"], "")


class TestVulnMapping(unittest.TestCase):
    """非 CVE 发现（弱口令/蜜罐/设备指纹）不应被丢弃"""

    def test_finding_type_preserved(self):
        v = _to_vulnerability({
            "cve_id": None, "finding_type": "weak_password",
            "severity": "HIGH", "description": "[弱口令] ...",
        })
        self.assertIsNotNone(v)
        self.assertEqual(v.cve_id, "FINDING:weak_password")
        self.assertEqual(v.severity, "high")

    def test_plain_cve_preserved(self):
        v = _to_vulnerability({
            "cve_id": "CVE-2025-0001", "severity": "critical",
            "cvss_score": 9.8, "description": "x",
        })
        self.assertEqual(v.cve_id, "CVE-2025-0001")

    def test_empty_finding_dropped(self):
        self.assertIsNone(_to_vulnerability({"cve_id": None}))


if __name__ == "__main__":
    unittest.main()
