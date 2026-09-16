#!/usr/bin/env python3
"""
AI-PTS 启动入口
支持CLI和GUI模式
"""
import sys
import os

# 确保项目路径正确
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


def run_gui():
    """运行GUI"""
    from gui.main_window import main as gui_main
    gui_main()


def run_cli():
    """运行CLI"""
    from main import main as cli_main
    cli_main()


def check_dependencies():
    """检查依赖"""
    missing = []

    # 检查必需模块
    required = {
        "PyQt5": "PyQt5",
        "nmap": "python-nmap",
        "anthropic": "anthropic"
    }

    for mod, pkg in required.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        print("缺少依赖，请安装:")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI-PTS (AI Penetration Testing System)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python aipts.py                    # 启动GUI
  python aipts.py -t 192.168.1.1      # CLI扫描单个IP
  python aipts.py -t 192.168.1.0/24  # CLI扫描网段
  python aipts.py --console           # CLI交互模式
        """
    )

    parser.add_argument(
        "mode",
        nargs="?",
        choices=["gui", "cli"],
        default="gui",
        help="运行模式 (默认: gui)"
    )

    # 扫描选项
    parser.add_argument("-t", "--target", help="扫描目标 (IP/CIDR/域名)")
    parser.add_argument("-p", "--ports", help="端口范围")
    parser.add_argument("-k", "--api-key", help="Anthropic API Key")
    parser.add_argument("--analyze", action="store_true", help="执行AI分析")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    # CLI模式需要目标
    if args.mode == "cli" and not args.target:
        parser.print_help()
        return

    # 检查依赖
    if not check_dependencies():
        return

    # 设置API Key
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    elif "ANTHROPIC_API_KEY" not in os.environ:
        # 尝试从配置文件读取
        config_file = os.path.join(PROJECT_DIR, "settings.json")
        if os.path.exists(config_file):
            import json
            with open(config_file) as f:
                config = json.load(f)
                if config.get("api_key"):
                    os.environ["ANTHROPIC_API_KEY"] = config["api_key"]

    # 运行
    if args.mode == "gui" or (not args.target and args.mode != "cli"):
        print("正在启动 AI-PTS GUI...")
        run_gui()
    else:
        print("正在启动 AI-PTS CLI...")
        run_cli()


if __name__ == "__main__":
    main()