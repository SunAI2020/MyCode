# -*- coding: utf-8 -*-
"""凭证加密存储 — 用 Fernet 对称加密把浏览器 Cookie / storage_state 落库。

密钥存 data/secret.key（首次运行自动生成，与 DB 一样不打入 exe）。
凭证写入复用 org_manager.system_settings 表（键 browser_cookie:{site} / browser_state:{site}），
值一律为 Fernet 密文，避免明文 Cookie 落库。
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import DATA_DIR

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

DEFAULT_KEY_PATH = os.path.join(DATA_DIR, "secret.key")


class CredentialStore:
    """Fernet 加密凭证存取，密钥落 data/secret.key。"""

    def __init__(self, org_mgr, key_path=None):
        self.org_mgr = org_mgr
        self.key_path = key_path or DEFAULT_KEY_PATH
        self._fernet = self._load_fernet()

    @property
    def available(self):
        return HAS_CRYPTO and self._fernet is not None

    def _load_fernet(self):
        if not HAS_CRYPTO:
            return None
        if not os.path.exists(self.key_path):
            key = Fernet.generate_key()
            try:
                os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
                with open(self.key_path, "wb") as f:
                    f.write(key)
                try:
                    os.chmod(self.key_path, 0o600)  # 收紧密钥文件权限（POSIX 生效，Windows 近似 no-op）
                except Exception:
                    pass
            except Exception:
                return None
        else:
            try:
                with open(self.key_path, "rb") as f:
                    key = f.read().strip()
            except Exception:
                return None
        try:
            return Fernet(key)
        except Exception:
            return None

    def _encrypt(self, s):
        if not s:
            return ""
        if not self._fernet:
            return ""  # 无加密能力时拒绝落库明文
        return self._fernet.encrypt(s.encode("utf-8")).decode("ascii")

    def _decrypt(self, s):
        if not s or not self._fernet:
            return ""
        try:
            return self._fernet.decrypt(s.encode("ascii")).decode("utf-8")
        except Exception:
            return ""

    def set_cookie(self, site, cookie_str):
        self.org_mgr.set_setting(f"browser_cookie:{site}", self._encrypt(cookie_str or ""))

    def get_cookie(self, site):
        return self._decrypt(self.org_mgr.get_setting(f"browser_cookie:{site}", ""))

    def set_storage_state(self, site, state_dict):
        if state_dict is None:
            self.org_mgr.set_setting(f"browser_state:{site}", "")
            return
        try:
            s = json.dumps(state_dict, ensure_ascii=False)
        except Exception:
            s = ""
        self.org_mgr.set_setting(f"browser_state:{site}", self._encrypt(s))

    def get_storage_state(self, site):
        raw = self._decrypt(self.org_mgr.get_setting(f"browser_state:{site}", ""))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def clear(self, site):
        self.org_mgr.set_setting(f"browser_cookie:{site}", "")
        self.org_mgr.set_setting(f"browser_state:{site}", "")
