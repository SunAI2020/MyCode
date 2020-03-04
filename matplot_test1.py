import matplotlib.pyplot as plt
import numpy as np
#import sys

#plt.figure(figsize=(5,5))
plt.rcParams['font.sans-serif']=['SimHei'] #用来正常显示中文标签
plt.rcParams['axes.unicode_minus']=False #用来正常显示负号

x=np.linspace(-1,1,50)
y=2*x+1
plt.figure(figsize=(8, 5))
#fig.subplots_adjust(bottom=0.15, left=0.2)
plt.plot(x,y,color="blue",linewidth=1.0,linestyle="--")
plt.xlabel('时间 [s]')
plt.ylabel('路程[米]')
plt.xticks([-1,-0.5,0,0.5,1])
plt.yticks([-1,0,1,2,3],['minus one','zero','one','two','three'])
plt.text(0.8, 0.1, '增长趋势图', horizontalalignment='center',verticalalignment='center')
plt.show()

#plt.figure(figsize=(8,8))
x=np.linspace(-np.pi,np.pi,256)
y1,y2,y3=np.cos(x),np.sin(x),np.arctan(x)
fig, ax = plt.subplots(figsize=(9, 6))
fig.subplots_adjust(bottom=0.15, left=0.2)
ax.plot(x,y1,color="red",linewidth=2.0,linestyle=":")
ax.plot(x,y2,color="green",linewidth=3.0,linestyle="-.")
ax.plot(x,y3,color="blue",linewidth=2.0,linestyle="-")
ax.set_xlabel('角度[度]')
ax.set_ylabel('三家函数[V]')
plt.xticks([-3,-2,-1,0,1,2,3],['-180','-120','-60','0','60','120','180'])
plt.show()
