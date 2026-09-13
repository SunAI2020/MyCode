# -*- coding: utf-8 -*-
"""AI客户端 — 通过本机 Claude Code CLI 调用大模型

默认使用 CC SWITCH 当前配置的模型，无需 API Key。
"""
import os
import re
import logging
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # AI分析可能需要较长时间


def _find_claude_binary() -> Optional[str]:
    """查找 claude 可执行文件路径"""
    env_bin = os.environ.get('CLAUDE_BIN', '')
    if env_bin and (os.path.isfile(env_bin) or shutil.which(env_bin)):
        return env_bin

    for name in ['claude', 'claude.exe', 'claude-code']:
        if shutil.which(name):
            return name

    npm_prefix = os.environ.get('APPDATA', '')
    if npm_prefix:
        npm_claude = os.path.join(npm_prefix, 'npm', 'claude.cmd')
        if os.path.isfile(npm_claude):
            return npm_claude

    return None


class AIClient:
    """AI客户端 — 通过本机 Claude Code CLI 调用，CC SWITCH 切换模型自动生效

    用法:
        client = AIClient()
        result = client.query(prompt, system_prompt=sys_prompt)
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Args:
            api_key: 保留参数（兼容旧代码），实际不使用
            model: 模型名称（可选），不指定则由 CC SWITCH 决定
        """
        self.model = model
        self._cli_binary = _find_claude_binary()
        self._cli_available = self._cli_binary is not None

        if self._cli_available:
            logger.info(f"AI客户端就绪 (CC SWITCH: claude={self._cli_binary})")
        else:
            logger.warning("AI客户端: 未检测到 Claude Code CLI，AI功能不可用")

    def query(self, user_message: str, system_prompt: Optional[str] = None,
              temperature: float = 0.1, max_tokens: int = 1024,
              max_turns: int = 1, timeout: int = DEFAULT_TIMEOUT,
              stop_event: Optional[threading.Event] = None) -> str:
        """发送查询并返回 AI 响应文本

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词（可选）
            temperature: 保留参数（CLI模式下通过提示词控制）
            max_tokens: 保留参数（CLI模式下由模型决定）
            max_turns: 最大交互轮数，>1时启用工具调用（网络搜索等），默认1
            timeout: 超时秒数，默认300秒
            stop_event: 可选 threading.Event，置位后立即终止子进程并抛出 RuntimeError
        """
        if not self._cli_available:
            raise RuntimeError(
                "AI功能不可用：未检测到本机 Claude Code CLI。\n"
                "请确保已安装 Claude Code（https://claude.com/code）"
            )

        prompt = self._build_prompt(user_message, system_prompt)
        cmd = [self._cli_binary, '--max-turns', str(max_turns)]
        if self.model:
            cmd.extend(['--model', self.model])

        logger.info(f"AI调用: 发送请求 (提示词长度={len(prompt)}字符, max_turns={max_turns})...")
        try:
            returncode, stdout, stderr = self._run_claude(cmd, prompt, timeout, stop_event)

            if returncode != 0:
                stderr = stderr.strip() if stderr else '(无错误输出)'
                logger.error(f"CLI调用失败 (返回码={returncode}): {stderr}")
                raise RuntimeError(f"Claude Code CLI 调用失败 (返回码={returncode}): {stderr}")

            output = stdout.strip()
            if not output:
                raise RuntimeError("Claude Code CLI 返回空响应")
            logger.info(f"AI调用完成: 响应长度={len(output)}字符")
            return output

        except FileNotFoundError:
            self._cli_available = False
            raise RuntimeError(f"Claude Code CLI 未找到: {self._cli_binary}")

    def _run_claude(self, cmd, prompt: str, timeout: int,
                    stop_event: Optional[threading.Event]):
        """以可取消的方式运行 Claude Code CLI 子进程。

        使用 Popen + 临时文件重定向 stdout/stderr（避免管道缓冲死锁），
        在 poll 循环中检查 stop_event 与超时，命中即终止子进程。
        返回 (returncode, stdout, stderr)。
        """
        creationflags = 0x08000000 if os.name == 'nt' else 0
        out_path = err_path = None
        proc = None
        try:
            fd_out, out_path = tempfile.mkstemp(prefix='claude_out_', suffix='.txt')
            fd_err, err_path = tempfile.mkstemp(prefix='claude_err_', suffix='.txt')
            os.close(fd_out)
            os.close(fd_err)

            with open(out_path, 'wb') as fo, open(err_path, 'wb') as fe:
                proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE, stdout=fo, stderr=fe,
                    creationflags=creationflags)
                try:
                    proc.stdin.write(prompt.encode('utf-8'))
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass

            deadline = time.time() + timeout
            while proc.poll() is None:
                if stop_event is not None and stop_event.is_set():
                    self._terminate_proc(proc)
                    raise RuntimeError("AI调用已停止")
                if time.time() > deadline:
                    self._terminate_proc(proc)
                    raise RuntimeError(f"Claude Code CLI 调用超时 ({timeout}秒)")
                time.sleep(0.1)

            with open(out_path, 'rb') as fo:
                stdout = fo.read().decode('utf-8', 'replace')
            with open(err_path, 'rb') as fe:
                stderr = fe.read().decode('utf-8', 'replace')
            return proc.returncode, stdout, stderr
        finally:
            if proc is not None and proc.poll() is None:
                self._terminate_proc(proc)
            for p in (out_path, err_path):
                if p:
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    @staticmethod
    def _terminate_proc(proc) -> None:
        """尽力终止子进程（terminate → kill），确保不留孤儿进程。"""
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass

    def _build_prompt(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """合并 system prompt 和 user message"""
        if system_prompt:
            return f"[系统指令]\n{system_prompt}\n\n---\n\n[用户请求]\n{user_message}"
        return user_message

    def query_with_progress(self, user_message: str,
                            system_prompt: Optional[str] = None,
                            temperature: float = 0.1,
                            max_tokens: int = 1024,
                            max_turns: int = 1,
                            timeout: int = 300,
                            progress_callback=None,
                            stop_event: Optional[threading.Event] = None) -> str:
        """带进度回调的查询方法。在同步CLI调用前后发送通知。"""
        if progress_callback:
            progress_callback(f'AI调用中 (超时{timeout}秒, {max_turns}轮)...')
        try:
            result = self.query(user_message, system_prompt,
                                temperature, max_tokens, max_turns, timeout, stop_event)
            if progress_callback:
                progress_callback(f'AI调用完成 ({len(result)}字符)')
            return result
        except Exception as e:
            if progress_callback:
                progress_callback(f'AI调用失败: {e}')
            raise


def is_ai_available() -> bool:
    """检查 AI 功能是否可用"""
    return _find_claude_binary() is not None


def strip_markdown_fences(text: str) -> str:
    """去除 markdown 代码块包裹（```json ... ```），容错散文前缀/后缀。

    用 re.search 而非 re.match，代码块可能出现在响应的任意位置
    （如 AI 响应被环境告警前置语污染时）。
    """
    t = text.strip()
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', t, re.DOTALL)
    if m:
        return m.group(1).strip()
    return t
