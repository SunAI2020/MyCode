"""
AI-PTS 配置文件
"""
import json
import os
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"


def load_config(config_file: str = None) -> dict:
    """加载配置文件"""
    if config_file is None:
        config_file = BASE_DIR / "ai-pts.json"

    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # 返回默认配置
    return get_default_config()


def get_default_config() -> dict:
    """获取默认配置"""
    return {
        "database": {
            "path": str(DATA_DIR / "vuln.db"),
            "update_interval": 86400,
            "cve_data_path": None
        },
        "scanner": {
            "common_ports": "1-1000,3306,3389,5432,6379,8080,8443",
            "default_timeout": 30000,
            "max_concurrent": 100,
            "version_detect": True,
            "os_detect": False
        },
        "ai": {
            "provider": "anthropic",
            "model": None,  # 为空时回退环境变量 ANTHROPIC_MODEL（本机 CC Switch 通道）
            "max_tokens": 4096,
            "temperature": 0.7,
            "api_key": None  # 用户需配置
        },
        "exploit": {
            "auto_execute": False,
            "require_confirmation": True,
            "allowed_types": ["rce", "sql_injection", "privesc", "lateral_movement"]
        },
        "tools": {
            "whitelist": [],
            "allow_all": False,
            "require_confirmation": True,
            "max_steps": 20,
            "timeout": 300,
            "impacket_method": "wmiexec.py",
            "metasploit": {
                "rpc_host": "127.0.0.1",
                "rpc_port": 55553,
                "lhost": "127.0.0.1",
                "lport": 4444
            }
        },
        "report": {
            "formats": ["html", "pdf", "json"],
            "output_dir": str(REPORTS_DIR),
            "template": "default"
        },
        "gui": {
            "theme": "dark",
            "window_size": "1200x800"
        }
    }


def save_config(config: dict, config_file: str = None):
    """保存配置"""
    if config_file is None:
        config_file = BASE_DIR / "ai-pts.json"

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


# 预定义配置
DATABASE = load_config()

__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "REPORTS_DIR",
    "LOGS_DIR",
    "load_config",
    "get_default_config",
    "save_config",
    "DATABASE"
]