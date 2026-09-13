#!/usr/bin/env python
# -*- coding: utf-8 -*-
import matplotlib.pyplot as plt 
import matplotlib as mpl
# 设置中文字体
mpl.rcParams['font.sans-serif'] = ['SimHei']
mpl.rcParams['axes.unicode_minus'] = False
myfont = mpl.font_manager.FontProperties(fname='C:/Windows/Fonts/simhei.ttf')

plt.plot([-2,2,3,4,5], 'r', label='第一条曲线')
plt.plot([3,4,5,8,9], 'b', label='第二条曲线')
plt.legend()
# plt.legend(('第一条曲线', '第二条曲线'))
plt.grid(True)
plt.axis([0, 5, -3, 9])
plt.xlabel('X轴坐标', fontproperties=myfont)
plt.ylabel('Y轴坐标', fontproperties=myfont)
plt.title('matplotlib演示图', fontproperties=myfont)
plt.savefig('plot123.png')
plt.show()