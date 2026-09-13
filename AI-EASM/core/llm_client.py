# -*- coding: utf-8 -*-
"""统一 LLM 抽象层 — OpenAI 兼容协议，切换服务商只需在「系统设置」改配置，无需改代码"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import LLM_PROVIDERS, LLM_CONFIG
try:
    import requests; HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class LLMClient:
    """OpenAI 兼容 LLM 客户端。provider/base_url/model/api_key 均可在系统设置中配置并切换。"""

    def __init__(self, org_manager=None, config=None):
        self.org_mgr = org_manager
        self.config = config or LLM_CONFIG

    def _resolve(self):
        """解析 provider/base_url/model/api_key，优先 DB system_settings，其次内存 LLM_CONFIG。"""
        cfg = dict(self.config)
        if self.org_mgr:
            for k in ("provider", "base_url", "model"):
                v = self.org_mgr.get_setting(f"llm:{k}", "")
                if v: cfg[k] = v
            key = self.org_mgr.get_setting("llm:api_key", "")
            if key: cfg["api_key"] = key
            temp = self.org_mgr.get_setting("llm:temperature", "")
            if temp:
                try: cfg["temperature"] = float(temp)
                except Exception: pass
        preset = LLM_PROVIDERS.get(cfg.get("provider", "custom"), {})
        base_url = (cfg.get("base_url") or preset.get("base_url", "")).rstrip("/")
        model = cfg.get("model") or preset.get("default_model", "")
        return base_url, model, cfg.get("api_key", ""), cfg.get("temperature", 0.3)

    def available(self):
        base_url, model, api_key, _t = self._resolve()
        if not base_url or not model or not HAS_REQUESTS:
            return False
        enabled = self.config.get("enabled", True)
        if self.org_mgr:
            ev = self.org_mgr.get_setting("llm:enabled", "")
            if ev: enabled = ev.lower() in ("1", "true", "yes", "on")
        if not enabled:
            return False
        # 无 api_key 时仅放行本地端点(本地 Ollama/LM Studio/vLLM/llama.cpp 等)；
        # 云端 provider 必须有 key，避免无鉴权请求
        if not api_key and not self._is_local_endpoint(base_url):
            return False
        return True

    @staticmethod
    def _is_local_endpoint(base_url):
        from urllib.parse import urlparse
        try:
            host = (urlparse(base_url or "").hostname or "").lower()
            return host in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
        except Exception:
            return False

    def chat(self, messages, temperature=None, max_tokens=2000):
        """OpenAI 兼容 /chat/completions 调用，失败返回空串（不抛异常）。"""
        base_url, model, api_key, t = self._resolve()
        if not base_url or not model or not HAS_REQUESTS:
            return ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature if temperature is not None else t,
            "max_tokens": max_tokens,
        }
        try:
            resp = requests.post(f"{base_url}/chat/completions", json=payload,
                                 headers=headers, timeout=60)
            if resp.status_code != 200:
                return ""
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    def complete(self, prompt, **kwargs):
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def assess_risks(self, org_name, findings):
        """AI 风险研判：对高危暴露面给出整体定级、优先处置清单与整改建议。"""
        if not self.available():
            return ""
        lines = [f"组织: {org_name}", "高危暴露面发现:"]
        for f in findings[:15]:
            lines.append(f"- [{f.get('risk_level','')}] {f.get('asset_type','')} "
                         f"{f.get('asset_name','')} | {f.get('asset_value','')} | 来源:{f.get('source','')}")
        prompt = ("你是攻击面管理安全分析师。请对下列暴露面进行风险研判，用中文输出："
                  "1)整体风险定级(高/中/低)；2)列出最需优先处置的3-5项；3)每项一句话整改建议。控制在200字内。\n\n"
                  + "\n".join(lines))
        return self.complete(prompt, max_tokens=500)

    def summarize_findings(self, org_name, stats, findings):
        """基于暴露面统计与高危发现生成自然语言摘要（用于报告摘要）。"""
        if not self.available():
            return ""
        lines = [
            f"组织: {org_name}",
            f"统计: 总暴露面{stats.get('total',0)} CRITICAL {stats.get('CRITICAL',0)} "
            f"HIGH {stats.get('HIGH',0)} MEDIUM {stats.get('MEDIUM',0)} LOW {stats.get('LOW',0)}",
            "高危发现(前10):",
        ]
        for f in findings[:10]:
            lines.append(f"- [{f.get('risk_level','')}] {f.get('asset_name','')} | "
                         f"{f.get('asset_value','')} | {f.get('source','')}")
        prompt = ("你是攻击面管理安全分析师。请基于以下暴露面排查数据，用中文输出一段150字以内的摘要，"
                  "包含：1)总体风险态势一句话；2)最需关注的高危暴露；3)一条首要整改建议。\n\n" + "\n".join(lines))
        return self.complete(prompt, max_tokens=400)
