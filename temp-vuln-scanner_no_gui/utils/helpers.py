"""
工具函数模块
提供通用辅助功能
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import ipaddress

from colorama import init, Fore, Style

# 初始化 colorama
init()


def setup_logging(
    level: str = 'INFO',
    log_file: Optional[str] = None,
    format_str: Optional[str] = None
) -> logging.Logger:
    """
    配置日志系统
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        format_str: 日志格式
        
    Returns:
        logging.Logger: 根日志记录器
    """
    if format_str is None:
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 创建处理器
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_str,
        handlers=handlers
    )
    
    return logging.getLogger()


def print_banner():
    """打印程序横幅"""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║                                              ║
║     🔒  漏洞扫描系统 v1.0                      ║
║     Vulnerability Scanner System              ║
║                                              ║
║     仅供授权的安全测试使用                    ║
║     For Authorized Security Testing Only      ║
║                                              ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def print_disclaimer():
    """打印免责声明"""
    disclaimer = f"""
{Fore.YELLOW}⚠️  法律免责声明{Style.RESET_ALL}
{Fore.RED}本工具仅用于授权的安全测试和漏洞评估。{Style.RESET_ALL}
使用前请确保：
  1. 您拥有目标系统的所有权或已获得书面授权
  2. 您的使用符合当地法律法规
  3. 您了解并承担使用本工具的全部责任

{Fore.RED}未经授权扫描他人系统是违法行为！{Style.RESET_ALL}
"""
    print(disclaimer)


def confirm_license() -> bool:
    """
    确认使用许可
    
    Returns:
        bool: 用户是否同意
    """
    print_disclaimer()
    
    while True:
        response = input(f"{Fore.YELLOW}是否同意上述条款并继续？(yes/no): {Style.RESET_ALL}").strip().lower()
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            return False
        else:
            print("请输入 yes 或 no")


def format_cvss(score: float) -> str:
    """
    格式化 CVSS 分数显示
    
    Args:
        score: CVSS 分数
        
    Returns:
        str: 带颜色的分数显示
    """
    if score >= 9.0:
        return f"{Fore.RED}{score:.1f}{Style.RESET_ALL}"
    elif score >= 7.0:
        return f"{Fore.MAGENTA}{score:.1f}{Style.RESET_ALL}"
    elif score >= 4.0:
        return f"{Fore.YELLOW}{score:.1f}{Style.RESET_ALL}"
    elif score > 0:
        return f"{Fore.GREEN}{score:.1f}{Style.RESET_ALL}"
    else:
        return f"{Fore.WHITE}{score:.1f}{Style.RESET_ALL}"


def format_severity(severity: str) -> str:
    """
    格式化严重程度显示
    
    Args:
        severity: 严重程度字符串
        
    Returns:
        str: 带颜色的显示
    """
    colors = {
        'CRITICAL': Fore.RED,
        'HIGH': Fore.MAGENTA,
        'MEDIUM': Fore.YELLOW,
        'LOW': Fore.GREEN,
        'INFO': Fore.WHITE,
    }
    color = colors.get(severity, Fore.WHITE)
    return f"{color}{severity}{Style.RESET_ALL}"


def validate_ip(ip_str: str) -> bool:
    """
    验证 IP 地址
    
    Args:
        ip_str: IP 地址字符串
        
    Returns:
        bool: 是否有效
    """
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def validate_cidr(cidr_str: str) -> bool:
    """
    验证 CIDR 格式
    
    Args:
        cidr_str: CIDR 字符串
        
    Returns:
        bool: 是否有效
    """
    try:
        ipaddress.ip_network(cidr_str, strict=False)
        return True
    except ValueError:
        return False


def parse_ip_range(range_str: str) -> List[str]:
    """
    解析 IP 范围
        
    Args:
        range_str: IP 范围字符串，如 "192.168.1.1-100"
        
    Returns:
        List[str]: IP 地址列表
    """
    ips = []
    
    if '-' in range_str:
        parts = range_str.split('-')
        if len(parts) == 2:
            try:
                start_parts = parts[0].split('.')
                end_parts = parts[1].split('.')
                
                if len(start_parts) == 4 and len(end_parts) == 4:
                    base = '.'.join(start_parts[:3])
                    start = int(start_parts[3])
                    end = int(end_parts[3])
                    
                    for i in range(start, end + 1):
                        ips.append(f"{base}.{i}")
            except (ValueError, IndexError):
                pass
    
    return ips


def get_human_readable_size(size_bytes: int) -> str:
    """
    获取人类可读的文件大小
    
    Args:
        size_bytes: 字节数
        
    Returns:
        str: 可读的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def get_human_readable_time(seconds: float) -> str:
    """
    获取人类可读的时间
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 可读的时间字符串
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def truncate_string(s: str, max_length: int = 50, suffix: str = '...') -> str:
    """
    截断字符串
    
    Args:
        s: 原始字符串
        max_length: 最大长度
        suffix: 后缀
        
    Returns:
        str: 截断后的字符串
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def safe_get(d: dict, *keys, default=None):
    """
    安全获取嵌套字典的值
    
    Args:
        d: 字典
        *keys: 键路径
        default: 默认值
        
    Returns:
        值或默认值
    """
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d
