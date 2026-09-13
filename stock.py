#!/usr/bin/env python
# -*- coding: utf-8 -*-

import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import pandas as pd

class StockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("实时股票信息")
        self.root.geometry("800x600")
        
        # 创建UI组件
        self.create_widgets()
        
        # 初始化数据
        self.stock_data = pd.DataFrame()
        self.animation = None
        
    def create_widgets(self):
        # 顶部输入区域
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="股票代码:", font=('Arial', 12)).pack(side=tk.LEFT, padx=5)
        
        self.stock_entry = ttk.Entry(top_frame, font=('Arial', 12), width=10)
        self.stock_entry.pack(side=tk.LEFT, padx=5)
        self.stock_entry.insert(0, "AAPL")  # 默认苹果股票
        
        ttk.Button(top_frame, text="获取数据", command=self.start_stock_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="停止", command=self.stop_stock_data).pack(side=tk.LEFT, padx=5)
        
        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        ttk.Label(top_frame, textvariable=self.status_var, font=('Arial', 10)).pack(side=tk.RIGHT, padx=5)
        
        # 图表区域
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = ttk.Frame(self.root, padding="10")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 股票信息区域
        self.info_frame = ttk.Frame(self.root, padding="10")
        self.info_frame.pack(fill=tk.X)
        
        self.info_labels = {
            "当前价格": ttk.Label(self.info_frame, text="当前价格: --", font=('Arial', 12)),
            "开盘价": ttk.Label(self.info_frame, text="开盘价: --", font=('Arial', 12)),
            "最高价": ttk.Label(self.info_frame, text="最高价: --", font=('Arial', 12)),
            "最低价": ttk.Label(self.info_frame, text="最低价: --", font=('Arial', 12)),
            "成交量": ttk.Label(self.info_frame, text="成交量: --", font=('Arial', 12)),
            "涨跌幅": ttk.Label(self.info_frame, text="涨跌幅: --", font=('Arial', 12))
        }
        
        for i, (key, label) in enumerate(self.info_labels.items()):
            label.grid(row=0, column=i, padx=10, pady=5)
    
    def start_stock_data(self):
        self.stock_symbol = self.stock_entry.get().upper()
        self.status_var.set(f"正在获取 {self.stock_symbol} 数据...")
        
        # 清除之前的数据
        self.stock_data = pd.DataFrame()
        
        # 初始化图表
        self.ax.clear()
        self.ax.set_title(f"{self.stock_symbol} 实时股价")
        self.ax.set_xlabel("时间")
        self.ax.set_ylabel("价格")
        self.ax.grid(True)
        
        # 开始动画
        if self.animation:
            self.animation.event_source.stop()
        
        self.animation = FuncAnimation(self.fig, self.update_stock_data, interval=5000)  # 每5秒更新一次
        plt.show(block=False)
        
    def stop_stock_data(self):
        if self.animation:
            self.animation.event_source.stop()
            self.status_var.set("已停止")
    
    def update_stock_data(self, i):
        try:
            # 获取实时数据
            ticker = yf.Ticker(self.stock_symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if not data.empty:
                # 更新数据
                self.stock_data = data.tail(30)  # 只保留最近30分钟的数据
                
                # 绘制图表
                self.ax.clear()
                self.ax.plot(self.stock_data.index, self.stock_data['Close'], 'b-', linewidth=2)
                self.ax.set_title(f"{self.stock_symbol} 实时股价")
                self.ax.set_xlabel("时间")
                self.ax.set_ylabel("价格")
                self.ax.grid(True)
                
                # 更新股票信息
                latest_data = data.iloc[-1]
                current_price = latest_data['Close']
                open_price = latest_data['Open']
                high_price = latest_data['High']
                low_price = latest_data['Low']
                volume = latest_data['Volume']
                change_percent = ((current_price - open_price) / open_price) * 100
                
                self.info_labels["当前价格"].config(text=f"当前价格: {current_price:.2f}")
                self.info_labels["开盘价"].config(text=f"开盘价: {open_price:.2f}")
                self.info_labels["最高价"].config(text=f"最高价: {high_price:.2f}")
                self.info_labels["最低价"].config(text=f"最低价: {low_price:.2f}")
                self.info_labels["成交量"].config(text=f"成交量: {volume:,}")
                
                # 根据涨跌幅设置颜色
                if change_percent >= 0:
                    color = "green"
                else:
                    color = "red"
                self.info_labels["涨跌幅"].config(text=f"涨跌幅: {change_percent:.2f}%", foreground=color)
                
                self.status_var.set(f"更新于: {datetime.now().strftime('%H:%M:%S')}")
            else:
                self.status_var.set("暂无数据")
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")

if __name__ == "__main__":
    # 安装必要的库（首次运行时取消注释）
    # import subprocess
    # subprocess.run(["pip", "install", "yfinance", "matplotlib", "pandas"])
    
    root = tk.Tk()
    app = StockApp(root)
    root.mainloop()
