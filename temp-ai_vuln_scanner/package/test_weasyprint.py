import sys
print("检查 WeasyPrint 安装状态...")

try:
    import weasyprint
    print("✓ WeasyPrint 已成功导入")
    print(f"版本: {weasyprint.__version__}")
    print(f"可用模块: {dir(weasyprint)[:10]}")
    print("\nWeasyPrint 安装成功！")
except ImportError as e:
    print(f"✗ 未找到 WeasyPrint: {e}")
    print("\n请运行以下命令安装:")
    print("  pip install weasyprint")
    sys.exit(1)
except Exception as e:
    print(f"✗ 导入 WeasyPrint 时出错: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
