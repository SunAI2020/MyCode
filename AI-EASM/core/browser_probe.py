# -*- coding: utf-8 -*-
"""无头浏览器搜索结果精确计数（Playwright 可选依赖，未安装时优雅降级）。

静态 requests 抓取拿不到结果数量（JS 动态渲染 / 反爬）时，用无头 Chromium
渲染页面后：优先解析站点自报的“找到相关结果约 X 个”等总数字样；否则兜底统计
含关键词的结果链接数量（近似值）。每次调用自包含启动/关闭浏览器，线程安全。
"""
import os, sys, re
from urllib.parse import urlparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False

_COUNT_PATTERNS = (
    r'找到相关结果约\s*([\d,]+)\s*个',
    r'为您找到相关结果约\s*([\d,]+)\s*个',
    r'约\s*([\d,]+)\s*(?:个|条|篇)\s*(?:相关)?结果',
    r'共\s*([\d,]+)\s*(?:个|条|篇)',
    r'([\d,]+)\s*(?:个|条|篇)\s*结果',
    r'相关文档\s*([\d,]+)\s*篇',
    r'找到\s*([\d,]+)\s*篇',
)

# 各站点结果项选择器（精确计数；未列出的站点走通用兜底）
RESULT_SELECTORS = {
    "wenku.baidu.com": ".doc-item-tile",
}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def parse_count_text(text):
    for p in _COUNT_PATTERNS:
        m = re.search(p, text or "")
        if m:
            return int(m.group(1).replace(",", ""))
    return None


class BrowserProbe:
    """渲染 JS 搜索结果页并精确计数（无状态，线程安全）。"""

    def __init__(self, timeout_ms=15000):
        self.timeout_ms = timeout_ms

    @property
    def available(self):
        return HAS_PLAYWRIGHT

    def count_results(self, url, keyword=None):
        """返回 (count:int, exact:bool) 或 None（无法确定）。"""
        if not HAS_PLAYWRIGHT or not url.startswith(("http://", "https://")):
            return None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled",
                          "--no-sandbox", "--disable-dev-shm-usage"])
                try:
                    ctx = browser.new_context(
                        user_agent=_UA, locale="zh-CN",
                        viewport={"width": 1280, "height": 900})
                    page = ctx.new_page()
                    page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("networkidle", timeout=6000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1200)
                    # 1) 站点自报的总结果数（精确）
                    text = page.inner_text("body")
                    cnt = parse_count_text(text)
                    if cnt is not None:
                        return (cnt, True)
                    # 2) 站点结果项选择器精确计数
                    host = urlparse(url).hostname or ""
                    sel = RESULT_SELECTORS.get(host)
                    if sel:
                        try:
                            n = page.locator(sel).count()
                            if n and n > 0:
                                return (n, True)
                        except Exception:
                            pass
                    # 3) 兜底：统计含关键词的结果链接数量（近似）
                    if keyword:
                        n = page.eval_on_selector_all(
                            "a",
                            "(els, kw) => els.filter(e => (e.innerText || '').includes(kw)).length",
                            keyword)
                        if n and n > 0:
                            return (n, False)
                    return None
                finally:
                    try:
                        browser.close()
                    except Exception:
                        pass
        except Exception:
            return None
