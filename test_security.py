#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试代码安全审计程序的测试文件
包含一些常见的安全漏洞
"""

# 测试SQL注入
def test_sql_injection():
    user_input = input("请输入用户名:")
    # 不安全的SQL查询
    query = f"SELECT * FROM users WHERE username = '{user_input}'"
    print("执行查询:", query)

# 测试硬编码密码
def test_hardcoded_password():
    # 硬编码的密码
    password = "password123"
    secret_key = "my_secret_key_12345"
    print("密码:", password)
    print("密钥:", secret_key)

# 测试不安全的哈希算法
def test_insecure_hash():
    import hashlib
    # 使用不安全的MD5算法
    password = "test_password"
    hash_value = hashlib.md5(password.encode()).hexdigest()
    print("MD5哈希:", hash_value)

# 测试eval使用
def test_eval_usage():
    user_input = input("请输入表达式:")
    # 不安全的eval使用
    result = eval(user_input)
    print("计算结果:", result)

if __name__ == "__main__":
    test_sql_injection()
    test_hardcoded_password()
    test_insecure_hash()
    test_eval_usage()
