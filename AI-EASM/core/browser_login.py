# -*- coding: utf-8 -*-
"""浏览器人工登录会话管理 — Playwright 有头浏览器 + 持久化 profile。

在后台线程启动有头 Chromium，打开登录页让用户人工登录/过滑块；
用户点击"继续"后在同一条线程内抓取 cookie + storage_state，经 CredentialStore 加密落库。
所有 Playwright 对象只在其专属 worker 线程内访问，避免跨线程调用 sync API。
"""
import os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import BROWSER_PROFILE_DIR, BROWSER_LOGIN_TIMEOUT

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 反自动化检测：抹掉 navigator.webdriver 等特征，规避爱企查/百度「请关闭调试窗口」拦截
_STEALTH_JS = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    "window.chrome = window.chrome || {runtime: {}};"
    "Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});"
    "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});"
    "try { localStorage.setItem('devtool', 'open'); } catch (e) {}"
)


class BrowserLoginManager:
    """有头浏览器登录会话。start_login 开浏览器 → signal_capture 抓取落库。"""

    def __init__(self, credential_store, profile_dir=None):
        self.store = credential_store
        self.profile_dir = profile_dir or BROWSER_PROFILE_DIR
        self.site = None
        self._open_evt = threading.Event()
        self._capture_evt = threading.Event()
        self._done_evt = threading.Event()
        self._should_capture = False
        self._error = None
        self._capture_ok = False
        self._thread = None

    @property
    def available(self):
        return HAS_PLAYWRIGHT and self.store.available

    @property
    def open_event(self):
        return self._open_evt

    @property
    def done_event(self):
        return self._done_evt

    @property
    def error(self):
        return self._error

    @property
    def capture_ok(self):
        return self._capture_ok

    def start_login(self, site, url):
        """非阻塞：启动后台线程打开有头浏览器。"""
        # 若上一次会话仍在运行（用户上次未点取消/关闭），先解除并等待其退出，避免 profile 被占用
        if self.is_running():
            self.cancel()
            try:
                self._thread.join(timeout=5)
            except Exception:
                pass
        self.site = site
        self._open_evt.clear(); self._capture_evt.clear(); self._done_evt.clear()
        self._should_capture = False; self._error = None; self._capture_ok = False
        self._thread = threading.Thread(target=self._worker, args=(url,), daemon=True)
        self._thread.start()

    def _worker(self, url):
        pw = ctx = None
        try:
            pw = sync_playwright().start()
            os.makedirs(self.profile_dir, exist_ok=True)
            launch_kwargs = dict(
                headless=False,
                viewport={"width": 1280, "height": 900},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                args=["--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled",
                      "--disable-infobars"])
            # 优先用系统 Chrome/Edge（真实浏览器指纹，规避爱企查/百度反爬），回退到自带 Chromium
            ctx = None
            for channel in ("chrome", "msedge"):
                prof = os.path.join(self.profile_dir, f"{self.site}_{channel}")
                os.makedirs(prof, exist_ok=True)
                try:
                    ctx = pw.chromium.launch_persistent_context(prof, channel=channel, **launch_kwargs)
                    break
                except Exception:
                    continue
            if ctx is None:
                prof = os.path.join(self.profile_dir, self.site)
                os.makedirs(prof, exist_ok=True)
                launch_kwargs["user_agent"] = _UA
                ctx = pw.chromium.launch_persistent_context(prof, **launch_kwargs)
            ctx.add_init_script(_STEALTH_JS)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            self._open_evt.set()
            # 等待用户完成登录/验证后点击"继续"，或取消/超时
            if self._capture_evt.wait(timeout=BROWSER_LOGIN_TIMEOUT) and self._should_capture:
                cookies = ctx.cookies()
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}" for c in cookies
                    if c.get("name") and c.get("value"))
                self.store.set_cookie(self.site, cookie_str)
                try:
                    self.store.set_storage_state(self.site, ctx.storage_state())
                except Exception:
                    pass
                self._capture_ok = True
        except Exception as e:
            self._error = str(e)
        finally:
            try:
                if ctx: ctx.close()
            except Exception:
                pass
            try:
                if pw: pw.stop()
            except Exception:
                pass
            self._done_evt.set()

    def signal_capture(self):
        """用户已登录，通知 worker 抓取并落库。"""
        self._should_capture = True
        self._capture_evt.set()

    def cancel(self):
        """用户取消：解除 worker 阻塞，不抓取。"""
        self._should_capture = False
        self._capture_evt.set()

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()
