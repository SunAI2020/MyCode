#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
import time
import random
from datetime import datetime

class StockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("实时股票信息")
        self.root.geometry("800x600")
        
        # 创建UI组件
        self.create_widgets()
        
        # 模拟股票数据
        self.stock_prices = {}
        self.is_running = False
    
    def create_widgets(self):
        # 顶部输入区域
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="股票代码:", font=('Arial', 12)).pack(side=tk.LEFT, padx=5)
        
        self.stock_entry = ttk.Entry(top_frame, font=('Arial', 12), width=10)
        self.stock_entry.pack(side=tk.LEFT, padx=5)
        self.stock_entry.insert(0, "AAPL")  # 默认苹果股票
        
        ttk.Button(top_frame, text="开始", command=self.start_stock_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="停止", command=self.stop_stock_data).pack(side=tk.LEFT, padx=5)
        
        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        ttk.Label(top_frame, textvariable=self.status_var, font=('Arial', 10)).pack(side=tk.RIGHT, padx=5)
        
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
        
        # 图表区域（使用文本模拟）
        self.chart_frame = ttk.Frame(self.root, padding="10", relief=tk.SUNKEN)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chart_text = tk.Text(self.chart_frame, font=('Courier New', 10))
        self.chart_text.pack(fill=tk.BOTH, expand=True)
        self.chart_text.insert(tk.END, "实时股价走势图\n")
        self.chart_text.insert(tk.END, "-" * 70 + "\n")
    
    def start_stock_data(self):
        self.stock_symbol = self.stock_entry.get().upper()
        self.status_var.set(f"正在获取 {self.stock_symbol} 数据...")
        
        # 初始化股票数据
        if self.stock_symbol not in self.stock_prices:
            # 生成随机初始价格
            initial_price = random.uniform(100, 500)
            self.stock_prices[self.stock_symbol] = {
                'open': initial_price,
                'current': initial_price,
                'high': initial_price,
                'low': initial_price,
                'volume': random.randint(1000000, 10000000),
                'price_history': [initial_price]
            }
        
        self.is_running = True
        self.update_stock_data()
    
    def stop_stock_data(self):
        self.is_running = False
        self.status_var.set("已停止")
    
    def update_stock_data(self):
        if not self.is_running:
            return
        
        try:
            # 模拟股票价格波动
            stock_data = self.stock_prices[self.stock_symbol]
            
            # 生成随机价格变动
            price_change = random.uniform(-2, 2)
            new_price = max(0, stock_data['current'] + price_change)
            
            # 更新数据
            stock_data['current'] = new_price
            stock_data['high'] = max(stock_data['high'], new_price)
            stock_data['low'] = min(stock_data['low'], new_price)
            stock_data['volume'] += random.randint(10000, 100000)
            stock_data['price_history'].append(new_price)
            
            # 只保留最近30个数据点
            if len(stock_data['price_history']) > 30:
                stock_data['price_history'] = stock_data['price_history'][-30:]
            
            # 计算涨跌幅
            change_percent = ((new_price - stock_data['open']) / stock_data['open']) * 100
            
            # 更新股票信息
            self.info_labels["当前价格"].config(text=f"当前价格: {new_price:.2f}")
            self.info_labels["开盘价"].config(text=f"开盘价: {stock_data['open']:.2f}")
            self.info_labels["最高价"].config(text=f"最高价: {stock_data['high']:.2f}")
            self.info_labels["最低价"].config(text=f"最低价: {stock_data['low']:.2f}")
            self.info_labels["成交量"].config(text=f"成交量: {stock_data['volume']:,}")
            
            # 根据涨跌幅设置颜色
            if change_percent >= 0:
                color = "green"
            else:
                color = "red"
            self.info_labels["涨跌幅"].config(text=f"涨跌幅: {change_percent:.2f}%", foreground=color)
            
            # 更新图表
            self.update_chart(stock_data['price_history'])
            
            self.status_var.set(f"更新于: {datetime.now().strftime('%H:%M:%S')}")
            
            # 每1秒更新一次
            self.root.after(1000, self.update_stock_data)
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")
    
    def update_chart(self, price_history):
        self.chart_text.delete(1.0, tk.END)
        self.chart_text.insert(tk.END, f"{self.stock_symbol} 实时股价走势图\n")
        self.chart_text.insert(tk.END, "-" * 70 + "\n")
        
        # 计算价格范围
        min_price = min(price_history)
        max_price = max(price_history)
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = 1  # 避免除以零
        
        # 绘制价格走势
        for i, price in enumerate(price_history):
            # 计算相对高度
            relative_height = (price - min_price) / price_range
            # 转换为文本高度（20行）
            bar_height = int(relative_height * 20)
            # 绘制价格条
            bar = '█' * bar_height
            # 格式化时间标签
            time_label = f"{i:2d}"
            # 格式化价格
            price_label = f"{price:.2f}"
            # 插入到文本框
            self.chart_text.insert(tk.END, f"{time_label}: {bar:20} {price_label}\n")
        
        self.chart_text.insert(tk.END, "-" * 70 + "\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = StockApp(root)
    root.mainloop()
