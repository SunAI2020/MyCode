#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析投标文件和响应文件，生成投标文件
"""

import os
import docx
from docx import Document
import win32com.client
import pythoncom

# 定义文件路径
SHANMEI_FILE = r"D:\0有信网安\投标文件\山煤\ZC2026SJZB202601001采购文件.doc"
TAIYUAN_FILE = r"D:\0有信网安\投标文件\太原天然气\响应文件（信息化安全设备采购）.docx"

# 检查文件是否存在
def check_files():
    print("检查文件是否存在...")
    if os.path.exists(SHANMEI_FILE):
        print(f"✓ 山煤采购文件存在: {SHANMEI_FILE}")
    else:
        print(f"✗ 山煤采购文件不存在: {SHANMEI_FILE}")
        return False
    
    if os.path.exists(TAIYUAN_FILE):
        print(f"✓ 太原天然气响应文件存在: {TAIYUAN_FILE}")
    else:
        print(f"✗ 太原天然气响应文件不存在: {TAIYUAN_FILE}")
        return False
    
    return True

# 读取山煤采购文件
def read_shanmei_file():
    print("\n读取山煤采购文件...")
    try:
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(SHANMEI_FILE)
        
        # 提取文本内容
        content = doc.Content.Text
        paragraphs = content.split('\n')
        print(f"✓ 成功读取山煤采购文件")
        print(f"段落数: {len([p for p in paragraphs if p.strip()])}")
        
        # 提取关键信息
        print("\n文件内容摘要:")
        count = 0
        for i, para in enumerate(paragraphs):
            if para.strip():
                print(f"{count+1}. {para.strip()}")
                count += 1
                if count >= 20:  # 只显示前20段
                    break
        
        doc.Close()
        word.Quit()
        pythoncom.CoUninitialize()
        
        return paragraphs
    except Exception as e:
        print(f"✗ 读取山煤采购文件失败: {e}")
        return None

# 读取太原天然气响应文件
def read_taiyuan_file():
    print("\n读取太原天然气响应文件...")
    try:
        doc = Document(TAIYUAN_FILE)
        print(f"✓ 成功读取太原天然气响应文件")
        print(f"页数: {len(doc.paragraphs)}")
        
        # 提取关键信息
        print("\n文件内容摘要:")
        for i, para in enumerate(doc.paragraphs[:20]):  # 只显示前20段
            if para.text.strip():
                print(f"{i+1}. {para.text}")
        
        return doc
    except Exception as e:
        print(f"✗ 读取太原天然气响应文件失败: {e}")
        return None

# 分析文件内容
def analyze_files(shanmei_doc, taiyuan_doc):
    print("\n分析文件内容...")
    
    # 分析山煤采购文件的关键要求
    print("\n山煤采购文件关键要求:")
    # 提取山煤采购文件中的关键信息
    if shanmei_doc:
        # 查找采购项目名称、要求、技术参数等
        project_name = ""
        requirements = []
        
        for i, para in enumerate(shanmei_doc):
            if para.strip():
                # 查找项目名称
                if "项目名称" in para or "采购名称" in para:
                    project_name = para.strip()
                    print(f"项目名称: {project_name}")
                # 查找技术要求
                elif "技术要求" in para or "技术参数" in para:
                    # 收集接下来的技术要求
                    for j in range(i+1, min(i+10, len(shanmei_doc))):
                        if shanmei_doc[j].strip():
                            requirements.append(shanmei_doc[j].strip())
        
        if requirements:
            print("\n技术要求:")
            for req in requirements:
                print(f"- {req}")
    
    # 分析太原天然气响应文件的结构
    print("\n太原天然气响应文件结构:")
    if taiyuan_doc:
        # 提取太原天然气响应文件的结构
        sections = []
        for para in taiyuan_doc.paragraphs:
            if para.text.strip():
                # 查找章节标题
                if para.text.strip().endswith("：") or para.text.strip().endswith(":"):
                    sections.append(para.text.strip())
        
        if sections:
            print("\n响应文件结构:")
            for section in sections[:10]:  # 只显示前10个章节
                print(f"- {section}")

# 生成投标文件
def generate_tender():
    print("\n生成投标文件...")
    
    try:
        # 创建新的投标文件
        doc = Document()
        
        # 添加标题
        doc.add_heading('投标文件', 0)
        
        # 添加项目信息
        doc.add_heading('一、项目信息', level=1)
        doc.add_paragraph('项目名称：山煤采购项目')
        doc.add_paragraph('采购编号：ZC2026SJZB202601001')
        doc.add_paragraph('投标人：有信网安')
        
        # 添加响应文件结构（参考太原天然气响应文件）
        doc.add_heading('二、响应文件结构', level=1)
        doc.add_paragraph('1. 投标函')
        doc.add_paragraph('2. 法定代表人身份证明')
        doc.add_paragraph('3. 授权委托书')
        doc.add_paragraph('4. 营业执照')
        doc.add_paragraph('5. 技术响应方案')
        doc.add_paragraph('6. 报价单')
        doc.add_paragraph('7. 服务承诺')
        doc.add_paragraph('8. 其他相关材料')
        
        # 添加技术响应方案
        doc.add_heading('三、技术响应方案', level=1)
        doc.add_paragraph('根据山煤采购文件的技术要求，我公司提供以下技术响应：')
        doc.add_paragraph('1. 产品符合国家相关标准和行业规范')
        doc.add_paragraph('2. 提供完整的技术支持和售后服务')
        doc.add_paragraph('3. 确保产品质量和性能满足采购要求')
        
        # 添加报价单
        doc.add_heading('四、报价单', level=1)
        doc.add_paragraph('详细报价见附件')
        
        # 添加服务承诺
        doc.add_heading('五、服务承诺', level=1)
        doc.add_paragraph('1. 提供7×24小时技术支持')
        doc.add_paragraph('2. 质保期为验收合格后12个月')
        doc.add_paragraph('3. 提供免费的技术培训')
        
        # 保存投标文件
        output_file = r"D:\0有信网安\投标文件\山煤\有信网安投标文件.docx"
        doc.save(output_file)
        print(f"✓ 成功生成投标文件: {output_file}")
        
    except Exception as e:
        print(f"✗ 生成投标文件失败: {e}")

if __name__ == "__main__":
    if check_files():
        shanmei_doc = read_shanmei_file()
        taiyuan_doc = read_taiyuan_file()
        if shanmei_doc and taiyuan_doc:
            analyze_files(shanmei_doc, taiyuan_doc)
            generate_tender()
        else:
            print("\n无法分析文件，生成投标文件失败")
    else:
        print("\n文件不存在，无法继续")
