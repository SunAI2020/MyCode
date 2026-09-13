# -*- coding: utf-8 -*-
"""
创建科技感风格的PPT - 太原市网络空间安全协会第一届理事会工作总结
增强版：丰富背景 + 全中文
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
import os
import random

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

def set_tech_background(slide):
    """设置科技感渐变背景"""
    background = slide.background

    # 创建渐变背景
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = DARK_BLUE

def add_grid_lines(slide):
    """添加网格背景线"""
    # 垂直网格线
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

    # 水平网格线
    for i in range(0, 8, 1):
        y = Inches(i * 1.07)
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0), y, Inches(13.333), Inches(0.008)
        )
        line.fill.solid()
        line.fill.fore_color.rgb = RGBColor(0, 40, 80)
        line.line.fill.background()

def add_glow_circles(slide, count=15):
    """添加发光圆点装饰"""
    for _ in range(count):
        x = Inches(random.uniform(0.5, 12.5))
        y = Inches(random.uniform(0.5, 6.5))
        size = Inches(random.uniform(0.05, 0.2))
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, size, size)
        circle.fill.solid()
        circle.fill.fore_color.rgb = CYAN
        circle.fill.transparency = 0.7
        circle.line.fill.background()

def add_scan_line(slide):
    """添加扫描线效果"""
    for i in range(0, 7):
        y = Inches(i * 1.2 + 0.5)
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0), y, Inches(13.333), Inches(0.02)
        )
        line.fill.solid()
        line.fill.fore_color.rgb = CYAN
        line.fill.transparency = 0.8
        line.line.fill.background()

def add_title(slide, text, top=Inches(0.5), font_size=44):
    """添加科技感标题"""
    # 标题背景条
    title_bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), top - Inches(0.2), Inches(13.333), Inches(1.1)
    )
    title_bg.fill.solid()
    title_bg.fill.fore_color.rgb = RGBColor(0, 40, 80)
    title_bg.fill.transparency = 0.5
    title_bg.line.fill.background()

    # 左侧装饰条
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

    # 底部发光线
    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.3), top + Inches(0.75), Inches(12.7), Inches(0.03)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = CYAN
    line.line.fill.background()

# ========== 第1页：封面 ==========
slide1 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide1)
add_grid_lines(slide1)
add_glow_circles(slide1, 20)
add_scan_line(slide1)

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
for i in range(5):
    y = Inches(1 + i * 1.3)
    line = slide1.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.3), y, Inches(2), Inches(0.02)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = CYAN
    line.line.fill.background()

# 主标题
title_box = slide1.shapes.add_textbox(Inches(4.5), Inches(2.2), Inches(8), Inches(1.2))
title_frame = title_box.text_frame
title_para = title_frame.paragraphs[0]
title_para.text = "太原市网络空间安全协会"
title_para.font.size = Pt(48)
title_para.font.bold = True
title_para.font.color.rgb = CYAN
title_para.alignment = PP_ALIGN.CENTER

# 副标题
subtitle_box = slide1.shapes.add_textbox(Inches(4.5), Inches(3.6), Inches(8), Inches(1))
subtitle_frame = subtitle_box.text_frame
subtitle_para = subtitle_frame.paragraphs[0]
subtitle_para.text = "第一届理事会工作总结"
subtitle_para.font.size = Pt(36)
subtitle_para.font.bold = True
subtitle_para.font.color.rgb = WHITE
subtitle_para.alignment = PP_ALIGN.CENTER

# 年份装饰
year_box = slide1.shapes.add_textbox(Inches(4.5), Inches(4.8), Inches(8), Inches(0.8))
year_frame = year_box.text_frame
year_para = year_frame.paragraphs[0]
year_para.text = "2024 - 2025"
year_para.font.size = Pt(32)
year_para.font.color.rgb = LIGHT_CYAN
year_para.alignment = PP_ALIGN.CENTER

# 底部信息
footer_box = slide1.shapes.add_textbox(Inches(4.5), Inches(6.2), Inches(8), Inches(0.6))
footer_frame = footer_box.text_frame
footer_para = footer_frame.paragraphs[0]
footer_para.text = "2025年12月"
footer_para.font.size = Pt(18)
footer_para.font.color.rgb = GRAY
footer_para.alignment = PP_ALIGN.CENTER

print("1. 封面完成")

# ========== 第2页：目录 ==========
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide2)
add_grid_lines(slide2)
add_glow_circles(slide2, 12)

add_title(slide2, "目 录")

toc_items = [
    ("01", "协会工作情况", "2024-2025年度工作回顾"),
    ("02", "工作亮点", "核心成就与突出贡献"),
    ("03", "存在问题", "当前面临的挑战与不足"),
    ("04", "下一步工作计划", "未来发展蓝图"),
    ("05", "第二届理事会推荐名单", "新一届领导团队")
]

for i, (num, title, desc) in enumerate(toc_items):
    y_pos = Inches(1.6 + i * 1.1)

    # 背景卡片
    card = slide2.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1.5), y_pos, Inches(10.333), Inches(0.95)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0, 50, 100)
    card.fill.transparency = 0.4
    card.line.color.rgb = CYAN
    card.line.width = Pt(1.5)

    # 序号
    num_box = slide2.shapes.add_textbox(Inches(1.8), y_pos + Inches(0.25), Inches(1), Inches(0.5))
    num_frame = num_box.text_frame
    num_para = num_frame.paragraphs[0]
    num_para.text = num
    num_para.font.size = Pt(28)
    num_para.font.bold = True
    num_para.font.color.rgb = CYAN
    num_para.alignment = PP_ALIGN.CENTER

    # 标题
    title_box = slide2.shapes.add_textbox(Inches(3), y_pos + Inches(0.15), Inches(4), Inches(0.45))
    title_frame = title_box.text_frame
    title_para = title_frame.paragraphs[0]
    title_para.text = title
    title_para.font.size = Pt(22)
    title_para.font.bold = True
    title_para.font.color.rgb = WHITE

    # 描述
    desc_box = slide2.shapes.add_textbox(Inches(7), y_pos + Inches(0.15), Inches(4.5), Inches(0.45))
    desc_frame = desc_box.text_frame
    desc_para = desc_frame.paragraphs[0]
    desc_para.text = desc
    desc_para.font.size = Pt(14)
    desc_para.font.color.rgb = GRAY

print("2. 目录完成")

# ========== 第3页：2024年工作情况 ==========
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide3)
add_grid_lines(slide3)
add_glow_circles(slide3, 10)

add_title(slide3, "2024年工作情况")

events_2024 = [
    ("7月", "向太原市委网信办专题汇报", "明晰协会定位与发展路径"),
    ("9月", "参与网络安全宣传周启动仪式", "普及网络安全知识"),
    ("9月", "配合市公安局开展法制主题日", "强化市民网络安全法律意识"),
    ("10月", "召开第一届会员大会", "正式成立协会"),
    ("10月", "主办卫生健康网络安全培训班", "38家医疗机构140余人参与"),
    ("11月", "赴市科协拜访", "提交加入市科协申请"),
    ("12月", "参加企业社会责任蓝皮书发布会", "深化跨领域合作"),
    ("12月", "联合举办国企等保测评培训", "市属国企150余人参加"),
]

# 左侧时间线
for i, (month, title, desc) in enumerate(events_2024[:4]):
    y_pos = Inches(1.4 + i * 1.45)

    # 连接线
    if i < 3:
        connector = slide3.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.95), y_pos + Inches(1.1), Inches(0.02), Inches(0.35)
        )
        connector.fill.solid()
        connector.fill.fore_color.rgb = CYAN
        connector.line.fill.background()

    # 圆点
    dot = slide3.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(0.85), y_pos + Inches(0.3), Inches(0.2), Inches(0.2)
    )
    dot.fill.solid()
    dot.fill.fore_color.rgb = CYAN
    dot.line.color.rgb = WHITE
    dot.line.width = Pt(1)

    # 内容卡片
    card = slide3.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1.3), y_pos, Inches(5), Inches(1.1)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0, 40, 80)
    card.fill.transparency = 0.5
    card.line.color.rgb = CYAN
    card.line.width = Pt(1)

    month_box = slide3.shapes.add_textbox(Inches(1.5), y_pos + Inches(0.1), Inches(4.6), Inches(0.35))
    month_frame = month_box.text_frame
    month_para = month_frame.paragraphs[0]
    month_para.text = f"【{month}】{title}"
    month_para.font.size = Pt(14)
    month_para.font.bold = True
    month_para.font.color.rgb = CYAN

    desc_box = slide3.shapes.add_textbox(Inches(1.5), y_pos + Inches(0.5), Inches(4.6), Inches(0.5))
    desc_frame = desc_box.text_frame
    desc_para = desc_frame.paragraphs[0]
    desc_para.text = desc
    desc_para.font.size = Pt(11)
    desc_para.font.color.rgb = WHITE

# 右侧时间线
for i, (month, title, desc) in enumerate(events_2024[4:]):
    y_pos = Inches(1.4 + i * 1.45)

    # 连接线
    if i < 3:
        connector = slide3.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(6.95), y_pos + Inches(1.1), Inches(0.02), Inches(0.35)
        )
        connector.fill.solid()
        connector.fill.fore_color.rgb = CYAN
        connector.line.fill.background()

    # 圆点
    dot = slide3.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(6.85), y_pos + Inches(0.3), Inches(0.2), Inches(0.2)
    )
    dot.fill.solid()
    dot.fill.fore_color.rgb = CYAN
    dot.line.color.rgb = WHITE
    dot.line.width = Pt(1)

    # 内容卡片
    card = slide3.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(7.3), y_pos, Inches(5), Inches(1.1)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0, 40, 80)
    card.fill.transparency = 0.5
    card.line.color.rgb = CYAN
    card.line.width = Pt(1)

    month_box = slide3.shapes.add_textbox(Inches(7.5), y_pos + Inches(0.1), Inches(4.6), Inches(0.35))
    month_frame = month_box.text_frame
    month_para = month_frame.paragraphs[0]
    month_para.text = f"【{month}】{title}"
    month_para.font.size = Pt(14)
    month_para.font.bold = True
    month_para.font.color.rgb = CYAN

    desc_box = slide3.shapes.add_textbox(Inches(7.5), y_pos + Inches(0.5), Inches(4.6), Inches(0.5))
    desc_frame = desc_box.text_frame
    desc_para = desc_frame.paragraphs[0]
    desc_para.text = desc
    desc_para.font.size = Pt(11)
    desc_para.font.color.rgb = WHITE

print("3. 2024年工作情况完成")

# ========== 第4页：2025年工作情况 ==========
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide4)
add_grid_lines(slide4)
add_glow_circles(slide4, 10)

add_title(slide4, "2025年协会成立后工作")

events_2025 = [
    ("1月", "取得社会团体法人登记证书", "完成正式注册"),
    ("3月", "向市委网信办和市公安局汇报", "获得主管部门支持"),
    ("4月", "医疗机构安全巡检", "发现大量安全隐患"),
    ("5月", "承办首席网络安全官培训", "市委网信办/市公安局/国资委主办"),
    ("5月", "走访调研测评机构", "了解测评市场现状"),
    ("6月", "成立党支部", "吴占分任党支部书记"),
    ("6月", "签署等保测评自律公约", "省内六家机构"),
    ("7月", "邀请云时代公司考察", "技术交流合作"),
    ("9月", "国企入户安全辅导", "近20家市属国企"),
    ("10月", "开通协会公众号", "增加宣传渠道"),
]

# 创建三列布局
cols = [(0.4, 4.2), (4.5, 4.2), (8.6, 4.2)]
col_events = [events_2025[:3], events_2025[3:6], events_2025[6:]]

for col_idx, (x_start, width) in enumerate(cols):
    events = col_events[col_idx]
    for i, (month, title, desc) in enumerate(events):
        y_pos = Inches(1.4 + i * 1.9)

        # 左边框发光条
        border = slide4.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(x_start), y_pos, Inches(0.1), Inches(1.7)
        )
        border.fill.solid()
        border.fill.fore_color.rgb = CYAN
        border.line.fill.background()

        # 内容卡片
        card = slide4.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(x_start + 0.2), y_pos, width - 0.3, Inches(1.6)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0, 40, 80)
        card.fill.transparency = 0.5
        card.line.color.rgb = CYAN
        card.line.width = Pt(1)

        month_box = slide4.shapes.add_textbox(Inches(x_start + 0.4), y_pos + Inches(0.1), width - 0.8, Inches(0.4))
        month_frame = month_box.text_frame
        month_para = month_frame.paragraphs[0]
        month_para.text = f"【{month}】"
        month_para.font.size = Pt(16)
        month_para.font.bold = True
        month_para.font.color.rgb = CYAN

        title_box = slide4.shapes.add_textbox(Inches(x_start + 0.4), y_pos + Inches(0.5), width - 0.8, Inches(0.7))
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        title_para.text = title
        title_para.font.size = Pt(13)
        title_para.font.bold = True
        title_para.font.color.rgb = WHITE

        desc_box = slide4.shapes.add_textbox(Inches(x_start + 0.4), y_pos + Inches(1.1), width - 0.8, Inches(0.4))
        desc_frame = desc_box.text_frame
        desc_para = desc_frame.paragraphs[0]
        desc_para.text = desc
        desc_para.font.size = Pt(11)
        desc_para.font.color.rgb = GRAY

print("4. 2025年工作情况完成")

# ========== 第5页：工作亮点 ==========
slide5 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide5)
add_grid_lines(slide5)
add_glow_circles(slide5, 15)

add_title(slide5, "工作亮点")

highlights = [
    ("01", "高效筹建", "从筹备汇报到正式成立\n仅用时5个月\n彰显卓越组织协调能力"),
    ("02", "精准服务", "聚焦医疗、国企等关键领域\n累计覆盖近500名专业人员\n提升重点行业防护水平"),
    ("03", "政社协同", "与网信办、公安局等部门深度合作\n参与各项活动\n增强社会公信力"),
]

for i, (num, title, desc) in enumerate(highlights):
    x_pos = Inches(0.8 + i * 4.2)

    # 背景卡片 - 渐变效果
    card = slide5.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        x_pos, Inches(1.5), Inches(4), Inches(5.2)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0, 30, 70)
    card.fill.transparency = 0.3
    card.line.color.rgb = CYAN
    card.line.width = Pt(2)

    # 顶部装饰条
    top_bar = slide5.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        x_pos, Inches(1.5), Inches(4), Inches(0.15)
    )
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = CYAN
    top_bar.line.fill.background()

    # 序号
    num_box = slide5.shapes.add_textbox(x_pos + Inches(0.2), Inches(1.8), Inches(3.6), Inches(0.8))
    num_frame = num_box.text_frame
    num_para = num_frame.paragraphs[0]
    num_para.text = num
    num_para.font.size = Pt(52)
    num_para.font.bold = True
    num_para.font.color.rgb = CYAN

    # 标题
    title_box = slide5.shapes.add_textbox(x_pos + Inches(0.2), Inches(2.9), Inches(3.6), Inches(0.6))
    title_frame = title_box.text_frame
    title_para = title_frame.paragraphs[0]
    title_para.text = title
    title_para.font.size = Pt(28)
    title_para.font.bold = True
    title_para.font.color.rgb = WHITE
    title_para.alignment = PP_ALIGN.CENTER

    # 分割线
    divider = slide5.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        x_pos + Inches(0.5), Inches(3.6), Inches(3), Inches(0.02)
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = CYAN
    divider.line.fill.background()

    # 描述
    desc_box = slide5.shapes.add_textbox(x_pos + Inches(0.2), Inches(3.9), Inches(3.6), Inches(2.2))
    desc_frame = desc_box.text_frame
    desc_para = desc_frame.paragraphs[0]
    desc_para.text = desc
    desc_para.font.size = Pt(14)
    desc_para.font.color.rgb = GRAY
    desc_para.alignment = PP_ALIGN.CENTER

print("5. 工作亮点完成")

# ========== 第6页：存在问题 ==========
slide6 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide6)
add_grid_lines(slide6)
add_glow_circles(slide6, 12)

add_title(slide6, "存在问题", font_size=40)

problems = [
    ("架构不完整", "• 缺乏会员基础和社会知名度\n• 等保测评自律委员会未运作\n• 专家委员会未组建\n• 党支部活动缺失"),
    ("人手不足", "• 缺乏专职工作人员\n• 各项工作难以开展\n• 经常顾此失彼，难以周全"),
    ("经费困难", "• 秘书长、理事长工资赊欠\n• 无经费签约代理记账\n• 房租、注册资金由个人垫付"),
    ("活动不足", "• 学术交流、专题培训太少\n• 缺乏行业号召力和领导力"),
    ("公众号问题", "• 没有专人负责\n• 文章少，编排不专业\n• 宣传力度差"),
    ("软件开发", "• 等保测评打卡软件开发缓慢"),
]

for i, (title, desc) in enumerate(problems):
    row = i // 3
    col = i % 3
    x_pos = Inches(0.3 + col * 4.35)
    y_pos = Inches(1.4 + row * 3.1)

    # 背景卡片
    card = slide6.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        x_pos, y_pos, Inches(4.1), Inches(2.8)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(60, 15, 15)
    card.fill.transparency = 0.5
    card.line.color.rgb = RGBColor(255, 80, 80)
    card.line.width = Pt(2)

    # 左边装饰条
    side_bar = slide6.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        x_pos, y_pos, Inches(0.08), Inches(2.8)
    )
    side_bar.fill.solid()
    side_bar.fill.fore_color.rgb = RGBColor(255, 100, 100)
    side_bar.line.fill.background()

    # 标题
    title_box = slide6.shapes.add_textbox(x_pos + Inches(0.2), y_pos + Inches(0.15), Inches(3.8), Inches(0.45))
    title_frame = title_box.text_frame
    title_para = title_frame.paragraphs[0]
    title_para.text = f"⚠ {title}"
    title_para.font.size = Pt(16)
    title_para.font.bold = True
    title_para.font.color.rgb = RGBColor(255, 150, 150)

    # 描述
    desc_box = slide6.shapes.add_textbox(x_pos + Inches(0.2), y_pos + Inches(0.65), Inches(3.8), Inches(2))
    desc_frame = desc_box.text_frame
    desc_para = desc_frame.paragraphs[0]
    desc_para.text = desc
    desc_para.font.size = Pt(13)
    desc_para.font.color.rgb = WHITE

print("6. 存在问题完成")

# ========== 第7页：下一步工作计划 ==========
slide7 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide7)
add_grid_lines(slide7)
add_glow_circles(slide7, 12)

add_title(slide7, "下一步工作计划")

plans = [
    ("1", "召开理事长办公会", "总结工作，提议架构重组，推荐第二届理事会人选"),
    ("2", "召开第二届会员大会", "选举新一届理事会成员"),
    ("3", "召开第二届理事会", "选举理事长、副理事长，聘任秘书长"),
    ("4", "召开第二届理事长办公会", "部署下一步工作"),
]

for i, (num, title, desc) in enumerate(plans):
    y_pos = Inches(1.4 + i * 1.45)

    # 序号圆形
    circle = slide7.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(0.7), y_pos + Inches(0.15), Inches(0.8), Inches(0.8)
    )
    circle.fill.solid()
    circle.fill.fore_color.rgb = CYAN
    circle.line.color.rgb = WHITE
    circle.line.width = Pt(2)

    num_box = slide7.shapes.add_textbox(Inches(0.7), y_pos + Inches(0.35), Inches(0.8), Inches(0.5))
    num_frame = num_box.text_frame
    num_para = num_frame.paragraphs[0]
    num_para.text = num
    num_para.font.size = Pt(26)
    num_para.font.bold = True
    num_para.font.color.rgb = RGBColor(10, 20, 50)
    num_para.alignment = PP_ALIGN.CENTER

    # 内容卡片
    card = slide7.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1.8), y_pos, Inches(10.8), Inches(1.2)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0, 50, 100)
    card.fill.transparency = 0.4
    card.line.color.rgb = CYAN
    card.line.width = Pt(1.5)

    # 标题
    title_box = slide7.shapes.add_textbox(Inches(2.1), y_pos + Inches(0.15), Inches(10.2), Inches(0.5))
    title_frame = title_box.text_frame
    title_para = title_frame.paragraphs[0]
    title_para.text = title
    title_para.font.size = Pt(20)
    title_para.font.bold = True
    title_para.font.color.rgb = CYAN

    # 描述
    desc_box = slide7.shapes.add_textbox(Inches(2.1), y_pos + Inches(0.7), Inches(10.2), Inches(0.45))
    desc_frame = desc_box.text_frame
    desc_para = desc_frame.paragraphs[0]
    desc_para.text = desc
    desc_para.font.size = Pt(14)
    desc_para.font.color.rgb = WHITE

print("7. 下一步工作计划完成")

# ========== 第8页：第二届理事会推荐名单 ==========
slide8 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide8)
add_grid_lines(slide8)
add_glow_circles(slide8, 12)

add_title(slide8, "第二届理事会推荐名单", font_size=38)

# 左侧 - 领导层
leadership_title = slide8.shapes.add_textbox(Inches(0.4), Inches(1.3), Inches(6), Inches(0.5))
leadership_frame = leadership_title.text_frame
leadership_para = leadership_frame.paragraphs[0]
leadership_para.text = "协会领导层"
leadership_para.font.size = Pt(22)
leadership_para.font.bold = True
leadership_para.font.color.rgb = CYAN

# 领导层背景
lead_card = slide8.shapes.add_shape(
    MSO_SHAPE.ROUNDED_RECTANGLE,
    Inches(0.4), Inches(1.8), Inches(6.2), Inches(5.2)
)
lead_card.fill.solid()
lead_card.fill.fore_color.rgb = RGBColor(0, 40, 80)
lead_card.fill.transparency = 0.4
lead_card.line.color.rgb = CYAN
lead_card.line.width = Pt(1.5)

leaders = [
    ("理事长", "王福明"),
    ("荣誉理事长", "陈俊杰"),
    ("副理事长", "白尚旺、刘全明、靳黎忠、刘运涛、\n苑小军、刘东新、郑亚彤、任凌云"),
    ("法人", "任凌云"),
    ("秘书长", "邱静"),
    ("监事长", "吴占分"),
    ("党支部书记", "吴占分"),
]

y_start = Inches(2.0)
for i, (role, name) in enumerate(leaders):
    y_pos = y_start + i * 0.7
    role_box = slide8.shapes.add_textbox(Inches(0.6), y_pos, Inches(1.8), Inches(0.5))
    role_frame = role_box.text_frame
    role_para = role_frame.paragraphs[0]
    role_para.text = role + "："
    role_para.font.size = Pt(14)
    role_para.font.bold = True
    role_para.font.color.rgb = LIGHT_CYAN

    name_box = slide8.shapes.add_textbox(Inches(2.4), y_pos, Inches(4), Inches(0.5))
    name_frame = name_box.text_frame
    name_para = name_frame.paragraphs[0]
    name_para.text = name
    name_para.font.size = Pt(12)
    name_para.font.color.rgb = WHITE

# 右侧 - 理事单位
org_title = slide8.shapes.add_textbox(Inches(6.9), Inches(1.3), Inches(6), Inches(0.5))
org_frame = org_title.text_frame
org_para = org_frame.paragraphs[0]
org_para.text = "理事单位（30家）"
org_para.font.size = Pt(22)
org_para.font.bold = True
org_para.font.color.rgb = CYAN

# 理事单位背景
org_card = slide8.shapes.add_shape(
    MSO_SHAPE.ROUNDED_RECTANGLE,
    Inches(6.9), Inches(1.8), Inches(6), Inches(5.2)
)
org_card.fill.solid()
org_card.fill.fore_color.rgb = RGBColor(0, 40, 80)
org_card.fill.transparency = 0.4
org_card.line.color.rgb = CYAN
org_card.line.width = Pt(1.5)

companies = [
    "太原清众鑫科技有限公司",
    "山西晋信安科技有限公司",
    "山西好友科技发展有限公司",
    "山西赛盾网络安全测评技术有限公司",
    "山西省信息化和信息安全评测中心",
    "山西因弗美讯科技有限公司",
    "山西蓝荧科技有限公司",
    "山西三友和智慧信息技术股份有限公司",
    "山西有信网安科技有限公司",
    "山西众成达信息技术服务有限公司",
    "...(共30家)",
]

y_start = Inches(2.0)
for i, company in enumerate(companies):
    y_pos = y_start + i * 0.5
    if y_pos > Inches(6.5):
        break
    company_box = slide8.shapes.add_textbox(Inches(7.1), y_pos, Inches(5.6), Inches(0.45))
    company_frame = company_box.text_frame
    company_para = company_frame.paragraphs[0]
    company_para.text = f"• {company}"
    company_para.font.size = Pt(12)
    company_para.font.color.rgb = WHITE

print("8. 第二届理事会推荐名单完成")

# ========== 第9页：结束页 ==========
slide9 = prs.slides.add_slide(prs.slide_layouts[6])
set_tech_background(slide9)
add_grid_lines(slide9)
add_glow_circles(slide9, 25)

# 中心装饰圆
center_circle = slide9.shapes.add_shape(
    MSO_SHAPE.OVAL,
    Inches(4.666), Inches(2), Inches(4), Inches(4)
)
center_circle.fill.solid()
center_circle.fill.fore_color.rgb = RGBColor(0, 40, 80)
center_circle.fill.transparency = 0.5
center_circle.line.color.rgb = CYAN
center_circle.line.width = Pt(3)

# 感谢文字
thanks_box = slide9.shapes.add_textbox(Inches(0.5), Inches(3), Inches(12.333), Inches(1.2))
thanks_frame = thanks_box.text_frame
thanks_para = thanks_frame.paragraphs[0]
thanks_para.text = "感谢聆听"
thanks_para.font.size = Pt(56)
thanks_para.font.bold = True
thanks_para.font.color.rgb = CYAN
thanks_para.alignment = PP_ALIGN.CENTER

# 副标题
sub_box = slide9.shapes.add_textbox(Inches(0.5), Inches(4.5), Inches(12.333), Inches(0.8))
sub_frame = sub_box.text_frame
sub_para = sub_frame.paragraphs[0]
sub_para.text = "太原市网络空间安全协会"
sub_para.font.size = Pt(28)
sub_para.font.color.rgb = WHITE
sub_para.alignment = PP_ALIGN.CENTER

# 底部
footer_box = slide9.shapes.add_textbox(Inches(0.5), Inches(5.8), Inches(12.333), Inches(0.6))
footer_frame = footer_box.text_frame
footer_para = footer_frame.paragraphs[0]
footer_para.text = "携手共建网络安全生态"
footer_para.font.size = Pt(20)
footer_para.font.color.rgb = GRAY
footer_para.alignment = PP_ALIGN.CENTER

print("9. 结束页完成")

# 保存文件
output_path = r"d:\python files\太原市网络空间安全协会第一届理事会工作总结.pptx"
prs.save(output_path)
print(f"\nPPT已保存至: {output_path}")
print(f"文件大小: {os.path.getsize(output_path) / 1024:.1f} KB")
