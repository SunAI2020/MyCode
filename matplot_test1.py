import matplotlib.pyplot as plt
import numpy as np
import sys

#plt.figure(figsize=(5,5))
plt.rcParams['font.sans-serif']=['SimHei'] #用来正常显示中文标签
plt.rcParams['axes.unicode_minus']=False #用来正常显示负号

x=np.linspace(-1,1,50)
y=2*x+1
fig, ax = plt.subplots(figsize=(8, 5))
fig.subplots_adjust(bottom=0.15, left=0.2)
plt.plot(x,y,color="blue",linewidth=1.0,linestyle="--")
ax.set_xlabel('time [s]')
ax.set_ylabel('Damped oscillation [V]')
ax.text(0.8, 0.1, '增长趋势图', horizontalalignment='center',verticalalignment='center', transform=ax.transAxes)
plt.show()

#plt.figure(figsize=(8,8))
x=np.linspace(-np.pi,np.pi,256)
y1,y2=np.cos(x),np.sin(x)
fig, ax = plt.subplots(figsize=(5, 3))
fig.subplots_adjust(bottom=0.15, left=0.2)
ax.plot(x,y1,color="red",linewidth=2.0,linestyle=":")
ax.plot(x,y2,color="green",linewidth=3.0,linestyle="-.")
ax.set_xlabel('角度[度]')
ax.set_ylabel('三家函数[V]')
plt.show()
