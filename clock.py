#---第1步---导出模块---
import turtle
from datetime import *
import time

#---第2步---定义函数跳跃---抬起画笔，向前运动一段距离放下--
def Skip(step):
    turtle.penup()  #提笔=pu=penup
    turtle.forward(step) #画线fd=forward
    turtle.pendown()  #落笔=pd=pendown

#---第3步---画圈函数---
def drawCircle(content,content_len,init_data,init_data_type,circle_radius,circle_radius_step,color,font_size):
    #回到原点=中心点=0,0
    turtle.home()
    turtle.pensize(3) #笔头大小设置
    turtle.pencolor(color)
    #圆点到时间的向左长度线
    Skip(circle_radius+circle_radius_step+10*3)
    #显示数据
    turtle.write(init_data_type, align="center", font=("Courier", font_size,'bold'))
    #往左条---中心点的位置
    Skip(-circle_radius-circle_radius_step-10*3)
    
    initdata_index=content.index(init_data)
    for i in range(initdata_index,content_len):
        Skip(circle_radius)
        #测长度，列表的长度，可以是时分秒的列表
        flen=len(content[i])
        if i == initdata_index:
            #圆心点与中心点的水平向右的距离，即圆点的水平画线长度，显示‘时’
        	turtle.forward(75)
            ##圆心点与中心点的水平向右的距离，后退-90
        	turtle.forward(-75)
        for name in range(flen):
            #画一圈时分秒的标签
            turtle.write(content[i][name], align="center", font=("Courier", font_size))
            #秒跳
            Skip(15)
        #分跳
        Skip(-15*flen)
        #时跳
        Skip(-circle_radius)
        #转角度
        turtle.left(360/content_len)
    for i in range(initdata_index):

        Skip(circle_radius)
        flen=len(content[i])
        for name in range(flen):
            #显示时分秒一圈一圈标签
            turtle.write(content[i][name], align="center", font=("Courier", font_size))
            Skip(15)
        Skip(-15*flen)
        Skip(-circle_radius)
        #向左转，回到水平向右的角度
        turtle.left(360/content_len)

#---第4步---相关自定义函数---
#---定义星期--- 
def Week(t):
    week = ["星期一", "星期二", "星期三","星期四", "星期五", "星期六", "星期日"]
    return week[t.weekday()]
 
#---定义日期---
def Date(t):
    y = t.year
    m = t.month
    d = t.day
    return "%s-%d-%d" % (y, m, d)

#---画线显示---
def drawline(draw):
    turtle.pendown() if draw else turtle.penup()
    turtle.fd(40)
    turtle.right(90)

#---显示右侧时分秒的晶体数字标签---
def drawdigit(digit):
    drawline(True) if digit in [2, 3, 4, 5, 6, 8, 9] else drawline(False)
    drawline(True) if digit in [0, 1, 3, 4, 5, 6, 7, 8, 9] else drawline(False)
    drawline(True) if digit in [0, 2, 3, 5, 6, 8, 9] else drawline(False)
    drawline(True) if digit in [0, 2, 6, 8] else drawline(False)
    turtle.left(90)
    drawline(True) if digit in [0, 4, 5, 6, 8, 9] else drawline(False)
    drawline(True) if digit in [0, 2, 3, 5, 6, 7, 8, 9] else drawline(False)
    drawline(True) if digit in [0, 1, 2, 3, 4, 7, 8, 9] else drawline(False)
    turtle.left(180)
    turtle.penup()
    turtle.fd(20)

#---画右侧显示时分秒的汉字标签---
def drawdate(date):
    for i in date:
        #本来显示月日时分，从0,0=home原点向右显示，但是重复了，所以不显示月日时分
        if i == '-':
            turtle.write('')
            turtle.pencolor('green')
            #画线为绿色
            turtle.fd(40)
            #显示白色的秒数和秒
            turtle.pencolor('white')
        elif i == '*':
            turtle.write('秒', font=('Arial', 18, 'normal'))
            turtle.fd(50)
        else:
            drawdigit(eval(i))

#---农历判断函数---
def Nongli(t):
    y=t.year
    t=(y-4)%60%10
    d=(y-4)%60%12
    T=["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    D=["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    #判断是农历的什么年？
    #pan="{}年是：农历{}{}年".format(y,T[t],D[d])
    pan="今年是：农历{}{}年".format(T[t],D[d])
    return pan

#---第5步---定义时钟走动---
def  runclock():
    turtle.reset()
    t = datetime.today()  #获取此刻时间
    second = t.second #+ t.microsecond * 0.000001
    minute = t.minute #+ second / 60.0
    hour = t.hour# + minute / 60.0

    #简体汉字列表---有空格字符串''
    Simplified_Chinese=['零','一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
                        '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九',
                        '二十','二十一', '二十二', '二十三', '二十四', '二十五', '二十六', '二十七', '二十八', '二十九',
                        '三十','三十一', '三十二', '三十三', '三十四', '三十五', '三十六', '三十七', '三十八', '三十九', 
                        '四十','四十一', '四十二', '四十三', '四十四', '四十五', '四十六', '四十七', '四十八', '四十九', 
                        '五十', '五十一', '五十二', '五十三', '五十四', '五十五', '五十六', '五十七', '五十八', '五十九' 
                        ]

    #简体汉字时间列表
    Simplified_hours=['一', '二', '三', '四', '五', '六', '七', '八', '九', '十','十一', '十二', '十三', 
                    '十四', '十五', '十六', '十七', '十八', '十九','二十' ,'二十一', '二十二', '二十三', '二十四']

    #字体大小6，颜色不同设定
    #坐标比如：150,250,350是半径（正代表当前时间的时分秒水平向右；负值代表水平线向左）；
    #40是水平线的长度，时分秒显示位置，len是一秒条多少
    #每跳动1秒都要从新绘画一次
    drawCircle(Simplified_Chinese,len(Simplified_Chinese),Simplified_Chinese[second],'秒',350,40,'green',8)
    drawCircle(Simplified_Chinese,len(Simplified_Chinese),Simplified_Chinese[minute],'分',250,40,'red',8)
    drawCircle(Simplified_hours,len(Simplified_hours),Simplified_hours[hour-1],'时',150,40,'yellow',8)
    
    #这里不建议设置为t，因为有一个时间t，所以为tg=turtle龟代替
    tg= turtle.Turtle()
    tg.hideturtle()  # 隐藏画笔的turtle形状,ht=hideturtle
    tg.color('white') #画笔的颜色，书写字体的颜色
    tg.right(-90)
    tg.penup()

    #显示右侧动态秒的晶体可变数字
    drawdate(time.strftime('-----------%S*', time.gmtime()))
    tg.forward(450)
    tg.back(400)
    #显示星期
    tg.write(Week(t), align="center",font=("Courier", 10, "bold"))

    #显示年月日
    tg.back(90)
    tg.write(Date(t), align="center",font=("Courier", 10, "bold"))
    #建议输出农历庚子年
    tg.back(400)
    tg.write(Nongli(t), align="center",font=("Courier", 10, "bold"))

    tg.right(90)
    #计时函数,动态更新实时时间，用来控制刷新时间。单位-毫秒
    turtle.ontimer(runclock, 1000)

#---第6步---定义主函数---
def main():
    # 打开/关闭龟动画，并为更新图纸设置延迟。
    turtle.tracer(False)# 关闭绘画追踪，可以用于加速绘画复杂图形
    #注意不建议使用t或者tg，容易搞错
    ts = turtle.getscreen()
    #背景颜色为黑色，我喜欢
    ts.bgcolor("black")
    #调用函数：走钟
    runclock()
    ts.mainloop()

#---第7步---调用函数程序---
if __name__ == "__main__":
    main()
