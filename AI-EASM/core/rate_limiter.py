# -*- coding: utf-8 -*-
"""Token Bucket限流器"""
import time, threading

class RateLimiter:
    def __init__(self):
        self._buckets = {}; self._lock = threading.Lock()

    def configure(self, api_name, max_tokens, refill_rate, refill_period=3600):
        with self._lock:
            self._buckets[api_name] = {"tokens":float(max_tokens),"max":float(max_tokens),
                "rate":refill_rate,"period":refill_period,"last":time.time()}

    def _refill(self, a):
        b = self._buckets.get(a)
        if not b: return
        now = time.time(); e = now - b["last"]
        if e > 0:
            b["tokens"] = min(b["max"], b["tokens"] + b["rate"] * e / b["period"])
            b["last"] = now

    def acquire(self, api_name):
        with self._lock:
            if api_name not in self._buckets: return True
            self._refill(api_name)
            if self._buckets[api_name]["tokens"] >= 1:
                self._buckets[api_name]["tokens"] -= 1; return True
            return False

    def wait_and_acquire(self, api_name, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.acquire(api_name): return True
            time.sleep(0.5)
        return False

    def remaining(self, api_name):
        with self._lock:
            self._refill(api_name)
            return self._buckets.get(api_name,{}).get("tokens",0)
