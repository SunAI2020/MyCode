import tkinter as tk
import random
import time
import winsound

class WhackAMole:
    def __init__(self, root):
        self.root = root
        self.root.title("打地鼠游戏")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        
        # 游戏参数
        self.score = 0
        self.time_left = 60
        self.mole_active = False
        self.mole_position = None
        self.game_running = False
        
        # 创建游戏画布
        self.canvas = tk.Canvas(root, width=800, height=600, bg="#8B4513")
        self.canvas.pack()
        
        # 绘制草地
        self.canvas.create_rectangle(0, 400, 800, 600, fill="#008000")
        
        # 绘制地洞位置（不规则分布）
        self.hole_positions = [
            (150, 450), (400, 420), (650, 450),
            (250, 520), (400, 550), (550, 520),
            (100, 580), (400, 580), (700, 580)
        ]
        
        # 绘制地洞
        self.holes = []
        for x, y in self.hole_positions:
            hole = self.canvas.create_oval(x-30, y-20, x+30, y+20, fill="#333333")
            self.holes.append(hole)
        
        # 绘制锤子
        self.hammer = self.canvas.create_polygon(400, 300, 420, 280, 440, 300, 420, 320, fill="#8B4513")
        self.canvas.bind("<Motion>", self.move_hammer)
        self.canvas.bind("<Button-1>", self.whack)
        
        # 游戏状态显示
        self.score_label = tk.Label(root, text="得分: 0", font=("Arial", 16), bg="#8B4513", fg="white")
        self.score_label.place(x=20, y=20)
        
        self.time_label = tk.Label(root, text="时间: 60秒", font=("Arial", 16), bg="#8B4513", fg="white")
        self.time_label.place(x=600, y=20)
        
        # 开始按钮
        self.start_button = tk.Button(root, text="开始游戏", font=("Arial", 14), command=self.start_game)
        self.start_button.place(x=350, y=50)
        
        # 地鼠图片（使用简单图形代替）
        self.mole = None
        self.mole_face = None
    
    def move_hammer(self, event):
        # 移动锤子跟随鼠标
        x, y = event.x, event.y
        self.canvas.coords(self.hammer, x-20, y-20, x, y-40, x+20, y-20, x, y)
    
    def start_game(self):
        if not self.game_running:
            self.game_running = True
            self.score = 0
            self.time_left = 60
            self.score_label.config(text="得分: 0")
            self.time_label.config(text="时间: 60秒")
            self.start_button.config(text="游戏中...")
            self.start_button.config(state=tk.DISABLED)
            self.game_loop()
    
    def game_loop(self):
        if not self.game_running:
            return
        
        if self.time_left > 0:
            # 随机出现地鼠
            if not self.mole_active:
                self.show_mole()
            
            # 更新时间
            self.time_left -= 1
            self.time_label.config(text=f"时间: {self.time_left}秒")
            
            # 继续游戏循环
            self.root.after(1000, self.game_loop)
        else:
            # 游戏结束
            self.game_running = False
            self.hide_mole()
            self.start_button.config(text="开始游戏")
            self.start_button.config(state=tk.NORMAL)
            self.canvas.create_text(400, 300, text=f"游戏结束！最终得分: {self.score}", font=("Arial", 24), fill="white")
    
    def show_mole(self):
        # 随机选择一个地洞
        self.mole_position = random.randint(0, 8)
        x, y = self.hole_positions[self.mole_position]
        
        # 绘制地鼠身体
        self.mole = self.canvas.create_oval(x-25, y-60, x+25, y-20, fill="#8B4513")
        
        # 绘制地鼠脸
        self.mole_face = self.canvas.create_oval(x-15, y-50, x+15, y-30, fill="#FFCC80")
        
        # 绘制地鼠眼睛
        self.canvas.create_oval(x-8, y-45, x-3, y-40, fill="black")
        self.canvas.create_oval(x+3, y-45, x+8, y-40, fill="black")
        
        # 绘制地鼠鼻子
        self.canvas.create_oval(x-2, y-38, x+2, y-34, fill="pink")
        
        # 绘制地鼠嘴巴（鬼脸）
        self.canvas.create_arc(x-8, y-40, x+8, y-25, start=0, extent=-180, fill="#FF6B6B")
        
        self.mole_active = True
        
        # 地鼠停留一段时间后消失
        self.root.after(random.randint(1000, 2000), self.hide_mole)
    
    def hide_mole(self):
        if self.mole_active:
            # 如果地鼠还在，隐藏它
            if self.mole:
                self.canvas.delete(self.mole)
            if self.mole_face:
                self.canvas.delete(self.mole_face)
            # 删除地鼠的其他部分（眼睛、鼻子、嘴巴）
            # 这里简化处理，实际应该保存所有元素的ID并删除
            self.mole_active = False
            self.mole_position = None
    
    def whack(self, event):
        if not self.game_running or not self.mole_active:
            return
        
        # 检查是否打中地鼠
        x, y = event.x, event.y
        mole_x, mole_y = self.hole_positions[self.mole_position]
        
        # 计算距离
        distance = ((x - mole_x) ** 2 + (y - (mole_y - 40)) ** 2) ** 0.5
        
        if distance < 30:  # 打中了
            # 播放惨叫音效
            try:
                winsound.Beep(800, 200)
            except:
                pass
            
            # 更新得分
            self.score += 10
            self.score_label.config(text=f"得分: {self.score}")
            
            # 显示头晕表情
            self.canvas.delete(self.mole_face)
            self.mole_face = self.canvas.create_oval(mole_x-15, mole_y-50, mole_x+15, mole_y-30, fill="#FFCC80")
            # 头晕星星
            self.canvas.create_polygon(mole_x-10, mole_y-60, mole_x-5, mole_y-50, mole_x, mole_y-60, mole_x-5, mole_y-70, fill="yellow")
            self.canvas.create_polygon(mole_x+10, mole_y-60, mole_x+5, mole_y-50, mole_x+10, mole_y-60, mole_x+5, mole_y-70, fill="yellow")
            
            # 延迟后隐藏地鼠
            self.root.after(500, self.hide_mole)
        else:  # 没打中
            # 播放窃喜音效
            try:
                winsound.Beep(1200, 150)
            except:
                pass
            
            # 显示幸灾乐祸表情
            self.canvas.delete(self.mole_face)
            self.mole_face = self.canvas.create_oval(mole_x-15, mole_y-50, mole_x+15, mole_y-30, fill="#FFCC80")
            # 绘制幸灾乐祸的眼睛
            self.canvas.create_oval(mole_x-8, mole_y-45, mole_x-3, mole_y-40, fill="black")
            self.canvas.create_oval(mole_x+3, mole_y-45, mole_x+8, mole_y-40, fill="black")
            # 绘制幸灾乐祸的嘴巴
            self.canvas.create_arc(mole_x-8, mole_y-35, mole_x+8, mole_y-20, start=0, extent=180, fill="#FF6B6B")
            
            # 延迟后隐藏地鼠
            self.root.after(500, self.hide_mole)

if __name__ == "__main__":
    root = tk.Tk()
    game = WhackAMole(root)
    root.mainloop()