"""
AI-PTS 专项工具执行器插件包

每个专项工具（getshell / 提权 / 横向移动）实现为一个 BaseExecutor 子类，
注册进 ExecutorRegistry，由工作流引擎与编排器调度。
"""
from .base import ToolExecutor
from .getshell import ImpacketExecExecutor, MSFGetShellExecutor
from .privesc import SecretsDumpExecutor, LinPEASExecutor
from .lateral import NetExecExecutor, BloodHoundCollector, MimikatzExecutor

__all__ = [
    "ToolExecutor",
    "ImpacketExecExecutor",
    "MSFGetShellExecutor",
    "SecretsDumpExecutor",
    "LinPEASExecutor",
    "NetExecExecutor",
    "BloodHoundCollector",
    "MimikatzExecutor",
]
