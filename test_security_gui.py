#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 测试文件：包含常见的安全漏洞

# 1. SQL注入漏洞示例
user_input = input("请输入用户名：")
exec(f"SELECT * FROM users WHERE username = '{user_input}'")

# 2. 硬编码密码
password = "admin123"
secret_key = "my_secret_key_123"

# 3. 不安全的哈希算法
import hashlib
md5_hash = hashlib.md5(b"password").hexdigest()

# 4. eval函数使用
data = "print('恶意代码执行')"
eval(data)

# 5. XSS漏洞示例
from flask import Flask, request, render_template
app = Flask(__name__)

@app.route('/')
def index():
    name = request.args.get('name')
    return f"Hello, {name}!"

if __name__ == '__main__':
    app.run()
