"""
智能体基类

Phase 1（多智能体角色化）的共享基类：每个角色 Agent 持有注入的 LLM 调用
（llm(system_prompt, user_prompt) -> Dict），decide() 组装 prompt 并调用，
异常时回退到角色各自的 fallback()（安全默认值）。
"""
from __future__ import annotations

import logging
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class BaseAgent:
    """智能体基类。"""

    SYSTEM_PROMPT = ""

    def __init__(self, llm: Callable[[str, str], Dict], role: str = ""):
        self.llm = llm
        self.role = role or self.__class__.__name__

    def fallback(self) -> Dict:
        """LLM 调用失败时的安全默认返回。子类应覆盖。"""
        return {"decision": "stop", "reason": "LLM 不可用"}

    def decide(self, user_prompt: str) -> Dict:
        """调用 LLM 返回结构化 dict；异常时回退。"""
        try:
            result = self.llm(self.SYSTEM_PROMPT, user_prompt)
            if not isinstance(result, dict):
                return self.fallback()
            return result
        except Exception as e:  # noqa: BLE001
            logger.warning("%s 调用失败，回退默认: %s", self.role, e)
            return self.fallback()
