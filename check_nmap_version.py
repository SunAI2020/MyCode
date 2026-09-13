import subprocess

# 运行nmap命令，捕获完整输出
try:
    # 尝试直接运行nmap命令
    result = subprocess.run('nmap', capture_output=True, text=True, shell=True)
    print("直接运行nmap的输出:")
    print(result.stdout)
    print("错误输出:")
    print(result.stderr)
    
    # 尝试运行nmap --help命令
    print("\n运行nmap --help的输出:")
    result_help = subprocess.run('nmap --help', capture_output=True, text=True, shell=True)
    print(result_help.stdout[:1000])  # 只打印前1000个字符
    
    # 尝试运行nmap -V命令
    print("\n运行nmap -V的输出:")
    result_v = subprocess.run('nmap -V', capture_output=True, text=True, shell=True)
    print(result_v.stdout)
    print("错误输出:")
    print(result_v.stderr)
    
except Exception as e:
    print(f"Error: {e}")
