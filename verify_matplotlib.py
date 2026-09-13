import matplotlib
print("matplotlib库安装成功！")
print("版本:", matplotlib.__version__)

# 测试简单的绘图功能
import matplotlib.pyplot as plt
import numpy as np

# 创建数据
x = np.linspace(0, 2*np.pi, 100)
y = np.sin(x)

# 绘制图表
plt.plot(x, y)
plt.title('正弦函数')
plt.xlabel('x')
plt.ylabel('sin(x)')

# 保存图表
plt.savefig('test_plot.png')
print("已生成测试图表: test_plot.png")