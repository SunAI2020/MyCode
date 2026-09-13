# -*- coding: utf-8 -*-
"""
现场抽奖程序 - 美化版
根据签到表序号抽取一等奖1个、二等奖2个、三等奖3个
"""
import sys
import random
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QSpinBox, QGroupBox, QMessageBox, QTextEdit,
                             QFileDialog, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDialog, QListWidget, QListWidgetItem,
                             QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QLinearGradient, QPainter


class GradientLabel(QLabel):
    """渐变背景标签"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)

    def set_gradient(self, color1, color2):
        self._color1 = color1
        self._color2 = color2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, self._color1)
        gradient.setColorAt(1, self._color2)
        painter.fillRect(self.rect(), gradient)
        super().paintEvent(event)


class LuckyDrawWindow(QMainWindow):
    """抽奖主窗口"""

    def __init__(self):
        super().__init__()

        self.participants = []
        self.winners = {'一等奖': [], '二等奖': [], '三等奖': []}
        self.animation_timer = None
        self.animation_count = 0

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle('现场抽奖系统 - 太原市网络空间安全协会')
        self.setGeometry(200, 100, 900, 700)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(15)

        # 标题区域
        title_container = QWidget()
        title_container.setFixedHeight(80)
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel('现 场 抽 奖 系 统')
        title_label.setFont(QFont('Microsoft YaHei', 32, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet('color: #FFD700; text-shadow: 2px 2px 4px #000;')
        title_layout.addWidget(title_label)

        subtitle = QLabel('太原市网络空间安全协会')
        subtitle.setFont(QFont('Microsoft YaHei', 14))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('color: #87CEEB;')
        title_layout.addWidget(subtitle)

        main_layout.addWidget(title_container)

        # 参与人数
        self.count_label = QLabel('参与人数: 0')
        self.count_label.setFont(QFont('Microsoft YaHei', 12))
        self.count_label.setAlignment(Qt.AlignCenter)
        self.count_label.setStyleSheet('color: #FFF; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 5px;')
        main_layout.addWidget(self.count_label)

        # 奖品区域 - 三个大奖并排
        prize_container = QWidget()
        prize_layout = QHBoxLayout(prize_container)
        prize_layout.setSpacing(20)

        # 一等奖卡片
        self.prize1_card = self.create_prize_card('一等奖', '1', '#FFD700', '#FFA500')
        prize_layout.addWidget(self.prize1_card)

        # 二等奖卡片
        self.prize2_card = self.create_prize_card('二等奖', '2', '#C0C0C0', '#A9A9A9')
        prize_layout.addWidget(self.prize2_card)

        # 三等奖卡片
        self.prize3_card = self.create_prize_card('三等奖', '3', '#CD7F32', '#8B4513')
        prize_layout.addWidget(self.prize3_card)

        main_layout.addWidget(prize_container)

        # 按钮区域
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(15)

        self.import_btn = self.create_btn('📂 导入签到表', '#4CAF50')
        self.import_btn.clicked.connect(self.import_participants)
        btn_layout.addWidget(self.import_btn)

        self.manual_btn = self.create_btn('✏️ 手动设置', '#2196F3')
        self.manual_btn.clicked.connect(self.manual_input)
        btn_layout.addWidget(self.manual_btn)

        self.reset_btn = self.create_btn('🔄 重置抽奖', '#FF9800')
        self.reset_btn.clicked.connect(self.reset_draw)
        btn_layout.addWidget(self.reset_btn)

        self.export_btn = self.create_btn('💾 导出结果', '#9C27B0')
        self.export_btn.clicked.connect(self.export_winners)
        btn_layout.addWidget(self.export_btn)

        main_layout.addWidget(btn_container)

        # 参与人员列表
        list_label = QLabel('📋 参与人员名单')
        list_label.setFont(QFont('Microsoft YaHei', 12, QFont.Bold))
        list_label.setStyleSheet('color: #87CEEB;')
        main_layout.addWidget(list_label)

        self.participant_list = QTextEdit()
        self.participant_list.setReadOnly(True)
        self.participant_list.setMaximumHeight(120)
        self.participant_list.setPlaceholderText('点击"导入签到表"或"手动设置"添加参与人员...')
        main_layout.addWidget(self.participant_list)

    def create_prize_card(self, title, count, color1, color2):
        """创建奖品卡片"""
        card = QWidget()
        card.setFixedHeight(180)

        # 卡片样式
        card.setStyleSheet(f'''
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color1}, stop:1 {color2});
                border-radius: 15px;
                border: 2px solid rgba(255,255,255,0.3);
            }}
        ''')

        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 标题
        title_label = QLabel(f'🏆 {title}')
        title_label.setFont(QFont('Microsoft YaHei', 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet('color: white; text-shadow: 1px 1px 2px #000;')
        layout.addWidget(title_label)

        # 数量
        count_label = QLabel(f'{count}名')
        count_label.setFont(QFont('Microsoft YaHei', 14))
        count_label.setAlignment(Qt.AlignCenter)
        count_label.setStyleSheet('color: white;')
        layout.addWidget(count_label)

        # 结果显示
        result_label = QLabel('等待抽取...')
        result_label.setFont(QFont('Microsoft YaHei', 16, QFont.Bold))
        result_label.setAlignment(Qt.AlignCenter)
        result_label.setStyleSheet('''
            color: white;
            background: rgba(0,0,0,0.3);
            padding: 10px;
            border-radius: 8px;
        ''')
        layout.addWidget(result_label)

        # 抽奖按钮
        btn = QPushButton('🎲 开始抽奖')
        btn.setFont(QFont('Microsoft YaHei', 12, QFont.Bold))
        btn.setStyleSheet('''
            QPushButton {
                background: white;
                color: #333;
                border: none;
                padding: 10px 20px;
                border-radius: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #f0f0f0;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background: #e0e0e0;
            }
            QPushButton:disabled {
                background: #ccc;
                color: #666;
            }
        ''')
        btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(btn)

        # 绑定事件
        if title == '一等奖':
            btn.clicked.connect(lambda: self.start_draw('一等奖', 1))
            self.prize1_result = result_label
            self.prize1_btn = btn
        elif title == '二等奖':
            btn.clicked.connect(lambda: self.start_draw('二等奖', 2))
            self.prize2_result = result_label
            self.prize2_btn = btn
        else:
            btn.clicked.connect(lambda: self.start_draw('三等奖', 3))
            self.prize3_result = result_label
            self.prize3_btn = btn

        return card

    def create_btn(self, text, color):
        """创建美化按钮"""
        btn = QPushButton(text)
        btn.setFont(QFont('Microsoft YaHei', 11))
        btn.setMinimumHeight(45)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f'''
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {color}DD;
                transform: translateY(-2px);
            }}
            QPushButton:pressed {{
                background: {color}BB;
                transform: translateY(0);
            }}
        ''')
        return btn

    def apply_styles(self):
        """应用整体样式"""
        self.setStyleSheet('''
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
            }
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 2px solid rgba(255,255,255,0.2);
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTextEdit {
                background: rgba(255,255,255,0.1);
                color: white;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 8px;
                padding: 10px;
                font-family: Microsoft YaHei;
            }
            QTextEdit::placeholder {
                color: rgba(255,255,255,0.5);
            }
            QInputDialog QLineEdit, QFileDialog QListWidget {
                background: white;
            }
            QMessageBox {
                background: #1a1a2e;
            }
            QMessageBox QLabel {
                color: white;
                font-size: 14px;
            }
        ''')

    def import_participants(self):
        """导入签到表"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择签到表', '', '文本文件 (*.txt);;JSON文件 (*.json);;所有文件 (*)'
        )

        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            try:
                data = json.loads(content)
                if isinstance(data, list):
                    self.participants = [str(x) for x in data]
                elif isinstance(data, dict) and 'numbers' in data:
                    self.participants = [str(x) for x in data['numbers']]
            except:
                lines = content.split('\n')
                self.participants = [line.strip() for line in lines if line.strip()]

            self.update_participant_display()
            QMessageBox.information(self, '✅ 成功', f'成功导入 {len(self.participants)} 个参与序号')

        except Exception as e:
            QMessageBox.critical(self, '❌ 错误', f'导入失败: {str(e)}')

    def manual_input(self):
        """手动输入"""
        dialog = QDialog(self)
        dialog.setWindowTitle('设置参与序号')
        dialog.setModal(True)
        dialog.setMinimumSize(400, 350)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel('请输入参与序号（每行一个，或用逗号分隔）:'))
        layout.setSpacing(10)

        text_edit = QTextEdit()
        text_edit.setPlaceholderText('例如:\n1\n2\n3\n...\n100\n\n或者: 1,2,3,4,5')
        layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('✓ 确定')
        ok_btn.setStyleSheet('''
            QPushButton { background: #4CAF50; color: white; padding: 8px 20px; border-radius: 5px; border: none; }
            QPushButton:hover { background: #45a049; }
        ''')
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton('✗ 取消')
        cancel_btn.setStyleSheet('''
            QPushButton { background: #f44336; color: white; padding: 8px 20px; border-radius: 5px; border: none; }
            QPushButton:hover { background: #da190b; }
        ''')
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        if dialog.exec_() == QDialog.Accepted:
            content = text_edit.toPlainText().strip()
            if ',' in content:
                self.participants = [x.strip() for x in content.split(',') if x.strip()]
            else:
                self.participants = [line.strip() for line in content.split('\n') if line.strip()]

            self.update_participant_display()
            QMessageBox.information(self, '✅ 成功', f'已设置 {len(self.participants)} 个参与序号')

    def update_participant_display(self):
        """更新显示"""
        self.count_label.setText(f'👥 参与人数: {len(self.participants)}')

        if self.participants:
            display = ', '.join(self.participants[:30])
            if len(self.participants) > 30:
                display += f' ... 等共{len(self.participants)}人'
            self.participant_list.setText(display)
        else:
            self.participant_list.setText('')

    def start_draw(self, prize_name: str, count: int):
        """开始抽奖"""
        if not self.participants:
            QMessageBox.warning(self, '⚠️ 警告', '请先导入签到表或手动设置参与序号')
            return

        already_won = []
        for winners in self.winners.values():
            already_won.extend(winners)

        available = [p for p in self.participants if p not in already_won]

        if len(available) < count:
            QMessageBox.warning(self, '⚠️ 警告', f'剩余可用序号不足 {count} 个')
            return

        # 禁用按钮
        self.prize1_btn.setEnabled(False)
        self.prize2_btn.setEnabled(False)
        self.prize3_btn.setEnabled(False)

        self.animation_count = 0
        self.current_available = available
        self.current_prize = prize_name

        # 创建抽奖动画窗口
        self.animation_label = QLabel()
        self.animation_label.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.animation_label.setAttribute(Qt.WA_TranslucentBackground)
        self.animation_label.setFixedSize(500, 300)
        self.animation_label.move(
            self.geometry().x() + (self.width() - 500) // 2,
            self.geometry().y() + (self.height() - 300) // 2
        )

        # 动画标签内容
        self.animation_label.setStyleSheet('''
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #0f3460);
                border: 3px solid #FFD700;
                border-radius: 20px;
                color: #FFD700;
            }
        ''')

        self.animation_label_layout = QVBoxLayout(self.animation_label)
        self.animation_label_layout.setContentsMargins(20, 20, 20, 20)

        self.animation_title = QLabel(f'{prize_name} 抽奖中...')
        self.animation_title.setFont(QFont('Microsoft YaHei', 24, QFont.Bold))
        self.animation_title.setAlignment(Qt.AlignCenter)
        self.animation_label_layout.addWidget(self.animation_title)

        self.animation_number = QLabel('🎲')
        self.animation_number.setFont(QFont('Microsoft YaHei', 48))
        self.animation_number.setAlignment(Qt.AlignCenter)
        self.animation_label_layout.addWidget(self.animation_number)

        self.animation_label.show()

        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_draw)
        self.animation_timer.start(100)

    def animate_draw(self):
        """抽奖动画"""
        self.animation_count += 1

        # 随机显示序号
        show_list = random.sample(self.current_available, min(3, len(self.current_available)))
        self.animation_number.setText('  '.join(show_list))
        self.animation_number.setFont(QFont('Microsoft YaHei', 32 + random.randint(-5, 5)))

        if self.animation_count >= 25:  # 25次后停止
            self.animation_timer.stop()

            winners = random.sample(self.current_available, 1 if self.current_prize == '一等奖' else 2 if self.current_prize == '二等奖' else 3)
            self.winners[self.current_prize] = winners

            self.animation_label.close()
            self.update_winner_display(self.current_prize, winners)

            # 启用按钮
            self.prize1_btn.setEnabled(True)
            self.prize2_btn.setEnabled(True)
            self.prize3_btn.setEnabled(True)

            # 显示结果
            winner_text = '\n'.join([f'✨ 序号: {w}' for w in winners])
            QMessageBox.information(
                self, f'🎉 {self.current_prize}中奖名单',
                f'{self.current_prize}中奖序号:\n\n{winner_text}\n\n恭喜以上{len(winners)}位幸运儿!'
            )

    def update_winner_display(self, prize_name, winners):
        """更新中奖显示"""
        winner_text = '\n'.join(winners)

        if prize_name == '一等奖':
            self.prize1_result.setText(winner_text)
            self.prize1_result.setStyleSheet('''
                color: white;
                background: rgba(0,0,0,0.5);
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
            ''')
        elif prize_name == '二等奖':
            self.prize2_result.setText(winner_text)
            self.prize2_result.setStyleSheet('''
                color: white;
                background: rgba(0,0,0,0.5);
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
            ''')
        elif prize_name == '三等奖':
            self.prize3_result.setText(winner_text)
            self.prize3_result.setStyleSheet('''
                color: white;
                background: rgba(0,0,0,0.5);
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
            ''')

    def reset_draw(self):
        """重置"""
        reply = QMessageBox.question(
            self, '确认',
            '确定要重置所有抽奖结果吗？',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.winners = {'一等奖': [], '二等奖': [], '三等奖': []}
            self.prize1_result.setText('等待抽取...')
            self.prize2_result.setText('等待抽取...')
            self.prize3_result.setText('等待抽取...')
            self.prize1_result.setStyleSheet('''
                color: white;
                background: rgba(0,0,0,0.3);
                padding: 10px;
                border-radius: 8px;
            ''')
            self.prize2_result.setStyleSheet('''
                color: white;
                background: rgba(0,0,0,0.3);
                padding: 10px;
                border-radius: 8px;
            ''')
            self.prize3_result.setStyleSheet('''
                color: white;
                background: rgba(0,0,0,0.3);
                padding: 10px;
                border-radius: 8px;
            ''')

    def export_winners(self):
        """导出结果"""
        if not any(self.winners.values()):
            QMessageBox.warning(self, '⚠️ 警告', '还没有抽取任何奖项')
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存结果', '抽奖结果.txt', '文本文件 (*.txt)'
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('='*50 + '\n')
                f.write('         现 场 抽 奖 结 果\n')
                f.write('    太原市网络空间安全协会\n')
                f.write('='*50 + '\n\n')

                for prize, winners in self.winners.items():
                    f.write(f'【{prize}】\n')
                    if winners:
                        for i, w in enumerate(winners, 1):
                            f.write(f'   {i}. 序号 {w}\n')
                    else:
                        f.write('   (待抽取)\n')
                    f.write('\n')

                f.write('='*50 + '\n')
                f.write(f'总参与人数: {len(self.participants)}\n')
                f.write(f'已抽取人数: {sum(len(w) for w in self.winners.values())}\n')

            QMessageBox.information(self, '✅ 成功', '结果已导出')

        except Exception as e:
            QMessageBox.critical(self, '❌ 错误', f'导出失败: {str(e)}')


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    font = QFont('Microsoft YaHei', 10)
    app.setFont(font)

    window = LuckyDrawWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()