# -*- coding: utf-8 -*-
"""
创建太原市网络空间安全协会2025年度财务报告PPT
科技感风格
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from io import BytesIO
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
plt.rcParams['axes.unicode_minus'] = False

# 创建演示文稿
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# 科技感配色
DARK_BLUE = RGBColor(10, 20, 50)
CYAN = RGBColor(0, 255, 255)
LIGHT_CYAN = RGBColor(100, 200, 255)
WHITE = RGBColor(255, 255, 255)
GRAY = RGBColor(180, 180, 180)
DEEP_PURPLE = RGBColor(30, 10, 60)
NEON_GREEN = RGBColor(0, 255, 128)
RED = RGBColor(255, 60, 60)
ORANGE = RGBColor(255, 165, 0)
LIGHT_GREEN = RGBColor(144, 238, 144)

# 配色常量
COLOR_BG = RGBColor(5, 15, 40)
COLOR_CARD_BG = RGBColor(0, 40, 80)
COLOR_ACCENT = RGBColor(0, 200, 255)

def add_matplotlib_image(slide, fig, left, top, width, height):
    """将matplotlib图表转换为图片并添加到PPT"""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=('#050f28'), edgecolor='none')
    buf.seek(0)
    slide.shapes.add_picture(buf, left, top, width, height)
    plt.close(fig)

def set_tech_background(slide):
    """设置科技感渐变背景"""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = COLOR_BG

def add_grid_lines(slide):
    """添加网格背景线"""
    for i in range(0, 14, 1):
        x = Inches(i * 0.95)
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            x, Inches(0), Inches(0.015), Inches(7.5)
        )
        line.fill.solid()
        if i % 2 == 0:
            line.fill.fore_color.rgb = RGBColor(0, 50, 100)
        else:
            line.fill.fore_color.rgb = RGBColor(0, 30, 60)
        line.line.fill.background()

def add_glow_circles(slide, count=15):
    """添加发光圆点装饰"""
    import random
    for _ in range(count):
        x = Inches(random.uniform(0.5, 12.5))
        y = Inches(random.uniform(0.5, 6.5))
        size = Inches(random.uniform(0.05, 0.2))
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, size, size)
        circle.fill.solid()
        circle.fill.fore_color.rgb = CYAN
        circle.fill.transparency = 0.7
        circle.line.fill.background()

def add_title(slide, text, top=Inches(0.5), font_size=44):
    """添加科技感标题"""
    title_bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), top - Inches(0.2), Inches(13.333), Inches(1.1)
    )
    title_bg.fill.solid()
    title_bg.fill.fore_color.rgb = RGBColor(0, 40, 80)
    title_bg.fill.transparency = 0.5
    title_bg.line.fill.background()

    decor = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.3), top, Inches(0.1), Inches(0.7)
    )
    decor.fill.solid()
    decor.fill.fore_color.rgb = CYAN
    decor.line.fill.background()

    title_box = slide.shapes.add_textbox(Inches(0.6), top, Inches(12), Inches(0.8))
    title_frame = title_box.text_frame
    title_para = title_frame.paragraphs[0]
    title_para.text = text
    title_para.font.size = Pt(font_size)
    title_para.font.bold = True
    title_para.font.color.rgb = CYAN

    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.3), top + Inches(0.75), Inches(12.7), Inches(0.03)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = CYAN
    line.line.fill.background()

def add_card(slide, x, y, w, h, color=RGBColor(0, 40, 80), border_color=CYAN, alpha=0.5):
    """添加卡片背景"""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = color
    card.fill.transparency = alpha if alpha else 0
    card.line.color.rgb = border_color
    card.line.width = Pt(1.5)
    return card

def add_text(slide, x, y, w, h, text, size=14, bold=False, color=WHITE, align=PP_ALIGN.LEFT):
    """添加文本框"""
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    para = frame.paragraphs[0]
    para.text = text
    para.font.size = Pt(size)
    para.font.bold = bold
    para.font.color.rgb = color
    para.alignment = align
    return box

# ========== 第1页：封面 ==========
slide1 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide1)
add_grid_lines(slide1)
add_glow_circles(slide1, 20)

# 左侧装饰面板
left_panel = slide1.shapes.add_shape(
    MSO_SHAPE.RECTANGLE,
    Inches(0), Inches(0), Inches(4), Inches(7.5)
)
left_panel.fill.solid()
left_panel.fill.fore_color.rgb = RGBColor(0, 30, 60)
left_panel.fill.transparency = 0.3
left_panel.line.fill.background()

# 装饰电路图案
for i in range(6):
    y = Inches(1 + i * 1.0)
    line = slide1.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.3), y, Inches(2), Inches(0.02)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = CYAN
    line.line.fill.background()

# 主标题
title_box = slide1.shapes.add_textbox(Inches(4), Inches(1.8), Inches(8.5), Inches(1.2))
title_frame = title_box.text_frame
title_para = title_frame.paragraphs[0]
title_para.text = "太原市网络空间安全协会"
title_para.font.size = Pt(44)
title_para.font.bold = True
title_para.font.color.rgb = CYAN
title_para.alignment = PP_ALIGN.CENTER

# 副标题
subtitle_box = slide1.shapes.add_textbox(Inches(4), Inches(3.0), Inches(8.5), Inches(1))
subtitle_frame = subtitle_box.text_frame
subtitle_para = subtitle_frame.paragraphs[0]
subtitle_para.text = "2025年度财务报告"
subtitle_para.font.size = Pt(36)
subtitle_para.font.bold = True
subtitle_para.font.color.rgb = WHITE
subtitle_para.alignment = PP_ALIGN.CENTER

# 年份
year_box = slide1.shapes.add_textbox(Inches(4), Inches(4.2), Inches(8.5), Inches(0.8))
year_frame = year_box.text_frame
year_para = year_frame.paragraphs[0]
year_para.text = "收支汇总与财务分析"
year_para.font.size = Pt(24)
year_para.font.color.rgb = LIGHT_CYAN
year_para.alignment = PP_ALIGN.CENTER

# 底部信息
footer_box = slide1.shapes.add_textbox(Inches(4), Inches(6.0), Inches(8.5), Inches(0.6))
footer_frame = footer_box.text_frame
footer_para = footer_frame.paragraphs[0]
footer_para.text = "2026年3月30日"
footer_para.font.size = Pt(18)
footer_para.font.color.rgb = GRAY
footer_para.alignment = PP_ALIGN.CENTER

print("1. 封面完成")

# ========== 第2页：总体收支概览 ==========
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide2)
add_grid_lines(slide2)
add_glow_circles(slide2, 10)
add_title(slide2, "总体收支概览")

# 收入卡片
income_card = add_card(slide2, Inches(0.3), Inches(1.5), Inches(4.0), Inches(2.8))
add_text(slide2, Inches(0.5), Inches(1.7), Inches(3.6), Inches(0.5),
         "总收入", size=18, bold=True, color=COLOR_ACCENT)
add_text(slide2, Inches(0.5), Inches(2.3), Inches(3.6), Inches(0.8),
         "135,000", size=42, bold=True, color=LIGHT_GREEN, align=PP_ALIGN.CENTER)
add_text(slide2, Inches(0.5), Inches(3.1), Inches(3.6), Inches(0.3),
         "元", size=16, bold=True, color=GRAY, align=PP_ALIGN.CENTER)

# 收入明细
add_text(slide2, Inches(0.5), Inches(3.5), Inches(3.6), Inches(0.7),
         "• 投资收入: 30,000元\n• 会费收入: 78,000元\n• 赞助费: 27,000元",
         size=11, color=GRAY)

# 支出卡片
expense_card = add_card(slide2, Inches(4.65), Inches(1.5), Inches(4.0), Inches(2.8))
add_text(slide2, Inches(4.85), Inches(1.7), Inches(3.6), Inches(0.5),
         "总支出", size=18, bold=True, color=RED)
add_text(slide2, Inches(4.85), Inches(2.3), Inches(3.6), Inches(0.8),
         "157,536.49", size=42, bold=True, color=RED, align=PP_ALIGN.CENTER)
add_text(slide2, Inches(4.85), Inches(3.1), Inches(3.6), Inches(0.3),
         "元", size=16, bold=True, color=GRAY, align=PP_ALIGN.CENTER)

# 支出明细
add_text(slide2, Inches(4.85), Inches(3.5), Inches(3.6), Inches(0.7),
         "• 运营费用: 113,517.75元\n• 会务宣发费: 40,254元\n• 财务费用: 3,764.04元",
         size=11, color=GRAY)

# 净盈亏卡片
net_card = add_card(slide2, Inches(9.0), Inches(1.5), Inches(4.0), Inches(2.8), color=RGBColor(60, 10, 10))
add_text(slide2, Inches(9.2), Inches(1.7), Inches(3.6), Inches(0.5),
         "净盈亏", size=18, bold=True, color=RED)
add_text(slide2, Inches(9.2), Inches(2.3), Inches(3.6), Inches(0.8),
         "-22,536.49", size=42, bold=True, color=RED, align=PP_ALIGN.CENTER)
add_text(slide2, Inches(9.2), Inches(3.1), Inches(3.6), Inches(0.3),
         "元（亏损）", size=16, bold=True, color=RED, align=PP_ALIGN.CENTER)

# 资金余额卡片
balance_card = add_card(slide2, Inches(0.3), Inches(4.6), Inches(12.7), Inches(2.5), color=RGBColor(0, 50, 80), alpha=0.6)
add_text(slide2, Inches(0.5), Inches(4.8), Inches(12), Inches(0.5),
         "资金余额", size=20, bold=True, color=CYAN)

# 银行账户
bank_box = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.5), Inches(5.5), Inches(1.3))
bank_box.fill.solid()
bank_box.fill.fore_color.rgb = RGBColor(0, 30, 60)
bank_box.fill.transparency = 0.5
bank_box.line.color.rgb = CYAN
bank_box.line.width = Pt(1)

add_text(slide2, Inches(1.0), Inches(5.6), Inches(5.1), Inches(0.4),
         "银行账户", size=14, bold=True, color=LIGHT_CYAN)
add_text(slide2, Inches(1.0), Inches(6.0), Inches(2.5), Inches(0.4),
         "193.13 元", size=20, bold=True, color=LIGHT_GREEN)
add_text(slide2, Inches(4.0), Inches(6.0), Inches(2.0), Inches(0.4),
         "正常", size=14, bold=True, color=LIGHT_GREEN)

# 现金账户
cash_box = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.5), Inches(5.5), Inches(6.2), Inches(1.3))
cash_box.fill.solid()
cash_box.fill.fore_color.rgb = RGBColor(40, 0, 0)
cash_box.fill.transparency = 0.5
cash_box.line.color.rgb = RED
cash_box.line.width = Pt(1)

add_text(slide2, Inches(6.7), Inches(5.6), Inches(5.8), Inches(0.4),
         "现金账户", size=14, bold=True, color=RGBColor(255, 150, 150))
add_text(slide2, Inches(6.7), Inches(6.0), Inches(3), Inches(0.4),
         "-22,729.62 元", size=20, bold=True, color=RED)
add_text(slide2, Inches(10.5), Inches(6.0), Inches(2), Inches(0.4),
         "透支！", size=14, bold=True, color=RED)

print("2. 总体收支概览完成")

# ========== 第3页：收入结构分析（饼图） ==========
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide3)
add_grid_lines(slide3)
add_glow_circles(slide3, 10)
add_title(slide3, "收入结构分析")

# 创建饼图
fig, ax = plt.subplots(figsize=(5.5, 5))
fig.patch.set_facecolor('#050f28')
ax.set_facecolor('#050f28')

labels = ['会费收入\n78,000元\n(57.8%)', '投资收入\n30,000元\n(22.2%)', '赞助费\n27,000元\n(20.0%)']
sizes = [78000, 30000, 27000]
colors = ['#00c8ff', '#00ff80', '#ff9900']
explode = (0.05, 0, 0)

wedges, texts = ax.pie(sizes, colors=colors, explode=explode,
                        startangle=90, wedgeprops={'edgecolor': '#050f28', 'linewidth': 2})
ax.legend(wedges, labels, loc='lower center', bbox_to_anchor=(0.5, -0.15),
          ncol=3, fontsize=10, labelcolor='white', frameon=False)

ax.set_title('2025年度收入构成', color='white', fontsize=16, pad=20)

add_matplotlib_image(slide3, fig, Inches(0.5), Inches(1.4), Inches(6.5), Inches(5.8))

# 右侧详细说明
detail_card = add_card(slide3, Inches(7.2), Inches(1.5), Inches(5.8), Inches(5.5))

add_text(slide3, Inches(7.5), Inches(1.7), Inches(5.2), Inches(0.5),
         "收入明细", size=18, bold=True, color=CYAN)

items = [
    ("会费收入", "78,000元", "占比57.8%", LIGHT_CYAN, "最高"),
    ("投资收入", "30,000元", "占比22.2%", LIGHT_GREEN, ""),
    ("赞助费", "27,000元", "占比20.0%", ORANGE, ""),
    ("其他收入", "0元", "占比0%", GRAY, ""),
]

for i, (name, amount, pct, color, note) in enumerate(items):
    y = Inches(2.3 + i * 1.1)
    # 左侧色块
    dot = slide3.shapes.add_shape(MSO_SHAPE.OVAL, Inches(7.6), y + Inches(0.1), Inches(0.3), Inches(0.3))
    dot.fill.solid()
    dot.fill.fore_color.rgb = color
    dot.line.fill.background()

    add_text(slide3, Inches(8.0), y, Inches(2), Inches(0.4),
             name, size=14, bold=True, color=WHITE)
    add_text(slide3, Inches(10.0), y, Inches(2.5), Inches(0.4),
             f"{amount} {pct}", size=12, color=GRAY)
    if note:
        add_text(slide3, Inches(11.5), y, Inches(1.2), Inches(0.4),
                 note, size=12, bold=True, color=RED)

# 关键提示
add_text(slide3, Inches(7.5), Inches(6.3), Inches(5.2), Inches(0.5),
         "! 会费收入占比过高，依赖单一收入来源", size=11, color=RED)

print("3. 收入结构分析完成")

# ========== 第4页：支出结构分析（柱状图） ==========
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide4)
add_grid_lines(slide4)
add_glow_circles(slide4, 10)
add_title(slide4, "支出结构分析")

# 创建柱状图
fig, ax = plt.subplots(figsize=(5.5, 5))
fig.patch.set_facecolor('#050f28')
ax.set_facecolor('#050f28')

categories = ['运营费用', '会务宣发费', '财务费用']
values = [113517.75, 40254, 3764.04]
total = sum(values)
percentages = [v/total*100 for v in values]
percentages = [78.8, 20.2, 1.0]  # 重新计算
percentages = [v/total*100 for v in values]

colors_bar = ['#ff4444', '#ff9900', '#00c8ff']
bars = ax.bar(categories, values, color=colors_bar, edgecolor='white', linewidth=1)

# 添加数值标签
for bar, val, pct in zip(bars, values, percentages):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 2000,
            f'{val:,.0f}\n({pct:.1f}%)',
            ha='center', va='bottom', color='white', fontsize=11)

ax.set_ylabel('金额（元）', color='white', fontsize=12)
ax.tick_params(axis='y', colors='white')
ax.tick_params(axis='x', colors='white', labelsize=12)
ax.spines['bottom'].set_color('white')
ax.spines['left'].set_color('white')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
ax.set_title('2025年度支出构成', color='white', fontsize=16, pad=20)
ax.set_ylim(0, 140000)

add_matplotlib_image(slide4, fig, Inches(0.3), Inches(1.4), Inches(6.5), Inches(5.8))

# 右侧详细说明
detail_card = add_card(slide4, Inches(7.0), Inches(1.5), Inches(6.0), Inches(5.5))

add_text(slide4, Inches(7.3), Inches(1.7), Inches(5.4), Inches(0.5),
         "支出明细", size=18, bold=True, color=CYAN)

expense_items = [
    ("运营费用", "113,517.75元", "72.1%", RED,
     "• 房租、押金\n• 办公设备\n• 日常用品等"),
    ("会务宣发费", "40,254元", "25.5%", ORANGE,
     "• 会议场地\n• 专家费\n• 招待费、宣传物料"),
    ("财务费用", "3,764.04元", "2.4%", LIGHT_CYAN,
     "• 手续费\n• 验资报告\n• 印章费"),
]

for i, (name, amount, pct, color, detail) in enumerate(expense_items):
    y = Inches(2.2 + i * 1.7)

    # 顶部装饰条
    bar_top = slide4.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.3), y, Inches(5.4), Inches(0.08))
    bar_top.fill.solid()
    bar_top.fill.fore_color.rgb = color
    bar_top.line.fill.background()

    add_text(slide4, Inches(7.3), y + Inches(0.15), Inches(2.5), Inches(0.4),
             name, size=14, bold=True, color=color)
    add_text(slide4, Inches(9.8), y + Inches(0.15), Inches(1.5), Inches(0.4),
             amount, size=13, bold=True, color=WHITE)
    add_text(slide4, Inches(11.3), y + Inches(0.15), Inches(1.2), Inches(0.4),
             pct, size=12, color=GRAY)

    add_text(slide4, Inches(7.5), y + Inches(0.55), Inches(5), Inches(1.0),
             detail, size=11, color=GRAY)

print("4. 支出结构分析完成")

# ========== 第5页：现金流状况 ==========
slide5 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide5)
add_grid_lines(slide5)
add_glow_circles(slide5, 10)
add_title(slide5, "现金流状况")

# 银行流水卡片
bank_flow_card = add_card(slide5, Inches(0.3), Inches(1.5), Inches(6.2), Inches(5.5))
add_text(slide5, Inches(0.6), Inches(1.7), Inches(5.6), Inches(0.5),
         "银行账户流水", size=16, bold=True, color=CYAN)

bank_info = """收入特点：
• 会费收入集中（78,000元）

支出特点：
• 备用金提取为主（83,000元）
• 小额采购支出

期末余额：仅193.13元

风险提示：
流动性极低，需关注"""

add_text(slide5, Inches(0.6), Inches(2.3), Inches(5.6), Inches(4.2),
         bank_info, size=13, color=WHITE)

# 现金流水卡片
cash_flow_card = add_card(slide5, Inches(6.8), Inches(1.5), Inches(6.2), Inches(5.5), color=RGBColor(50, 10, 10), border_color=RED)
add_text(slide5, Inches(7.1), Inches(1.7), Inches(5.6), Inches(0.5),
         "现金账户流水", size=16, bold=True, color=RED)

cash_info = """大额支出：
• 房租: 45,000元 + 20,000元 + 25,000元
• 办公设备采购

收入来源：
• 赞助费收入（27,000元）

风险提示：
赞助费未能覆盖会议支出
现金账户已透支（-22,729.62元）"""

add_text(slide5, Inches(7.1), Inches(2.3), Inches(5.6), Inches(4.2),
         cash_info, size=13, color=WHITE)

# 底部警示
warning_box = slide5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.3), Inches(6.7), Inches(12.7), Inches(0.5))
warning_box.fill.solid()
warning_box.fill.fore_color.rgb = RGBColor(80, 20, 20)
warning_box.line.color.rgb = RED
warning_box.line.width = Pt(2)

add_text(slide5, Inches(0.6), Inches(6.78), Inches(12), Inches(0.4),
         "⚠ 资金链紧张：银行余额不足200元，现金账户透支超2万元", size=14, bold=True, color=RED, align=PP_ALIGN.CENTER)

print("5. 现金流状况完成")

# ========== 第6页：关键问题与风险提示 ==========
slide6 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide6)
add_grid_lines(slide6)
add_glow_circles(slide6, 12)
add_title(slide6, "关键问题与风险提示", font_size=40)

problems = [
    ("持续亏损", "年度亏损约2.25万元\n现金账户已透支", RED, "!"),
    ("收入单一", "会费占比过高（57.8%）\n缺乏多元化收入来源", ORANGE, "!"),
    ("运营成本高", "房租、设备采购等固定\n支出占比过大", RGBColor(200, 200, 0), "!"),
    ("账务需核查", "汇总表提示A-B差额需核查\n（当前显示为0，需定期复核）", LIGHT_CYAN, "i"),
]

for i, (title, desc, color, icon) in enumerate(problems):
    row = i // 2
    col = i % 2
    x = Inches(0.4 + col * 6.5)
    y = Inches(1.5 + row * 2.9)

    # 卡片背景
    card = slide6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Inches(6.2), Inches(2.6))

    if color == LIGHT_CYAN:
        card_bg = RGBColor(0, 50, 80)
    elif color == RED:
        card_bg = RGBColor(50, 10, 10)
    elif color == ORANGE:
        card_bg = RGBColor(40, 25, 5)
    elif str(color) == str(RGBColor(200, 200, 0)):
        card_bg = RGBColor(50, 50, 10)
    else:
        card_bg = RGBColor(0, 40, 80)

    card.fill.solid()
    card.fill.fore_color.rgb = card_bg
    card.fill.transparency = 0.4
    card.line.color.rgb = color
    card.line.width = Pt(2)

    # 左侧装饰条
    left_bar = slide6.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, Inches(0.1), Inches(2.6))
    left_bar.fill.solid()
    left_bar.fill.fore_color.rgb = color
    left_bar.line.fill.background()

    # 图标
    icon_box = slide6.shapes.add_textbox(x + Inches(0.3), y + Inches(0.2), Inches(0.6), Inches(0.6))
    icon_para = icon_box.text_frame.paragraphs[0]
    icon_para.text = icon
    icon_para.font.size = Pt(28)
    icon_para.font.bold = True
    icon_para.font.color.rgb = color

    # 标题
    add_text(slide6, x + Inches(1.0), y + Inches(0.2), Inches(4.8), Inches(0.5),
             title, size=18, bold=True, color=color)

    # 描述
    add_text(slide6, x + Inches(0.4), y + Inches(0.9), Inches(5.5), Inches(1.5),
             desc, size=13, color=WHITE)

print("6. 关键问题与风险提示完成")

# ========== 第7页：改进建议 ==========
slide7 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide7)
add_grid_lines(slide7)
add_glow_circles(slide7, 10)
add_title(slide7, "改进建议")

suggestions = [
    ("增收措施", LIGHT_GREEN, [
        "拓展企业赞助渠道",
        "开展培训收费服务",
        "收取活动报名费",
        "提高会费收缴率",
        "探索分级会费制度",
    ]),
    ("节流措施", ORANGE, [
        "优化采购流程",
        "控制非必要运营开支",
        "会议活动实行预算前置审批",
        "合理控制房租成本",
    ]),
    ("资金管理", CYAN, [
        "建立月度资金计划",
        "避免现金账户透支",
        "保留3-6个月应急备用金",
        "定期核查账务一致性",
    ]),
]

for i, (title, color, items) in enumerate(suggestions):
    x = Inches(0.3 + i * 4.4)
    y = Inches(1.5)

    # 卡片
    card = slide7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Inches(4.2), Inches(5.5))
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0, 40, 80)
    card.fill.transparency = 0.4
    card.line.color.rgb = color
    card.line.width = Pt(2)

    # 顶部色条
    top_bar = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, Inches(4.2), Inches(0.15))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = color
    top_bar.line.fill.background()

    # 标题
    add_text(slide7, x + Inches(0.2), y + Inches(0.25), Inches(3.8), Inches(0.5),
             title, size=18, bold=True, color=color)

    # 列表项
    for j, item in enumerate(items):
        item_y = y + Inches(0.9 + j * 1.05)
        # 小圆点
        dot = slide7.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(0.3), item_y + Inches(0.12), Inches(0.15), Inches(0.15))
        dot.fill.solid()
        dot.fill.fore_color.rgb = color
        dot.line.fill.background()

        add_text(slide7, x + Inches(0.55), item_y, Inches(3.5), Inches(0.9),
                 item, size=13, color=WHITE)

print("7. 改进建议完成")

# ========== 第8页：尾页 ==========
slide8 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide8)
add_grid_lines(slide8)
add_glow_circles(slide8, 20)

# 中心装饰
center_circle = slide8.shapes.add_shape(
    MSO_SHAPE.OVAL,
    Inches(4.666), Inches(1.5), Inches(4), Inches(4)
)
center_circle.fill.solid()
center_circle.fill.fore_color.rgb = RGBColor(0, 40, 80)
center_circle.fill.transparency = 0.5
center_circle.line.color.rgb = CYAN
center_circle.line.width = Pt(3)

# 结论标题
conclusion_box = slide8.shapes.add_textbox(Inches(0.5), Inches(2.0), Inches(12.333), Inches(0.8))
conclusion_frame = conclusion_box.text_frame
conclusion_para = conclusion_frame.paragraphs[0]
conclusion_para.text = "结论"
conclusion_para.font.size = Pt(32)
conclusion_para.font.bold = True
conclusion_para.font.color.rgb = CYAN
conclusion_para.alignment = PP_ALIGN.CENTER

# 结论内容
conclusion_content = slide8.shapes.add_textbox(Inches(0.5), Inches(2.8), Inches(12.333), Inches(1.2))
conclusion_frame2 = conclusion_content.text_frame
conclusion_para2 = conclusion_frame2.paragraphs[0]
conclusion_para2.text = "协会目前处于亏损状态，需尽快优化收支结构，加强预算管控。"
conclusion_para2.font.size = Pt(18)
conclusion_para2.font.color.rgb = WHITE
conclusion_para2.alignment = PP_ALIGN.CENTER

# 下一步标题
next_box = slide8.shapes.add_textbox(Inches(0.5), Inches(4.3), Inches(12.333), Inches(0.8))
next_frame = next_box.text_frame
next_para = next_frame.paragraphs[0]
next_para.text = "下一步"
next_para.font.size = Pt(32)
next_para.font.bold = True
next_para.font.color.rgb = CYAN
next_para.alignment = PP_ALIGN.CENTER

# 下一步内容
next_content = slide8.shapes.add_textbox(Inches(0.5), Inches(5.1), Inches(12.333), Inches(1.2))
next_frame2 = next_content.text_frame
next_para2 = next_frame2.paragraphs[0]
next_para2.text = "建议每季度复盘财务数据，并向理事会汇报。"
next_para2.font.size = Pt(18)
next_para2.font.color.rgb = WHITE
next_para2.alignment = PP_ALIGN.CENTER

# 底部
footer_box = slide8.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(12.333), Inches(0.6))
footer_frame = footer_box.text_frame
footer_para = footer_frame.paragraphs[0]
footer_para.text = "太原市网络空间安全协会 · 2026年3月"
footer_para.font.size = Pt(16)
footer_para.font.color.rgb = GRAY
footer_para.alignment = PP_ALIGN.CENTER

print("8. 尾页完成")

# 保存文件
output_path = r"d:\python files\太原市网络空间安全协会2025年度财务报告.pptx"
prs.save(output_path)
print(f"\nPPT已保存至: {output_path}")
print(f"文件大小: {os.path.getsize(output_path) / 1024:.1f} KB")