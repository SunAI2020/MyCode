"""
双色球 TOP 5 预测员竞技场 - V3 GUI
====================================
五位预测员各自用不同算法独立预测，开奖后PK排名，按累计奖金排行
"""
import sys, random
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QScrollArea, QStatusBar, QSizePolicy,
    QComboBox, QHBoxLayout,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen, QRadialGradient

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
matplotlib.rcParams['axes.unicode_minus'] = False

from ssq_database import (
    get_all_results, get_latest_issue,
    get_connection, create_database, import_from_json,
    save_predictor_predictions, update_predictor_after_draw,
    get_predictor_rankings, save_draw_result,
)
from ssq_data_fetcher import fetch_latest_draw, load_cached_latest, save_cache, format_money
from ssq_prediction_v2 import (
    predict_per_strategy, PREDICTORS, RED_RANGE, BLUE_RANGE,
)

# ============================================================================
# 颜色常量
# ============================================================================
BG = "#F0F2F5"
CARD_BG = "#FFFFFF"
TEXT_DARK = "#1A1A2E"
TEXT_MID = "#555"
BORDER = "#E0E0E0"
GOLD = "#F59E0B"

# ============================================================================
# 球体控件
# ============================================================================

class BallWidget(QWidget):
    """单个双色球号码球"""
    def __init__(self, number: int, ball_type: str = "red", size: int = 40, parent=None):
        super().__init__(parent)
        self.number = number
        self.ball_type = ball_type
        self.bsize = size
        self.setFixedSize(size + 6, size + 6)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.bsize / 2
        cx, cy = self.bsize / 2 + 2, self.bsize / 2 + 2

        if self.ball_type == "red":
            mc, dc, lc = QColor("#E03030"), QColor("#8B0000"), QColor("#FF6060")
        else:
            mc, dc, lc = QColor("#3060E0"), QColor("#002080"), QColor("#6080FF")

        g = QRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 1.2)
        g.setColorAt(0.0, lc); g.setColorAt(0.4, mc); g.setColorAt(1.0, dc)
        p.setBrush(QBrush(g))
        p.setPen(QPen(dc.darker(120), 1))
        p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        p.setBrush(QBrush(QColor(255, 255, 255, 60)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(int(cx - r * 0.4), int(cy - r * 0.55), int(r * 0.6), int(r * 0.45))

        p.setPen(QPen(Qt.white))
        font_size = max(8, int(r * 0.55))
        p.setFont(QFont("Arial", font_size, QFont.Bold))
        p.drawText(int(cx - r), int(cy - r), int(r * 2), int(r * 2),
                   Qt.AlignCenter, f"{self.number:02d}")


# ============================================================================
# 后台线程
# ============================================================================

class DataFetchThread(QThread):
    data_ready = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def run(self):
        self.progress.emit("正在获取最新开奖数据...")
        try:
            data = fetch_latest_draw()
            if data:
                save_cache(data); self.data_ready.emit(data); return
            cached = load_cached_latest()
            if cached:
                self.data_ready.emit(cached); return
            self.error.emit("无法获取开奖数据")
        except Exception as e:
            self.error.emit(str(e))


class PredictionThreadV3(QThread):
    data_ready = pyqtSignal(dict)
    progress = pyqtSignal(str)

    def run(self):
        self.progress.emit("TOP 5 预测员正在分析...")
        try:
            all_r = get_all_results()
            if not all_r or len(all_r) < 10:
                self.data_ready.emit(_random_per_strategy()); return
            self.progress.emit("各预测员独立生成号码(全精度)...")
            result = predict_per_strategy(all_r, fast_mode=False)
            self.data_ready.emit(result)
        except Exception:
            logger.exception("预测生成失败，回退到随机号码")
            self.data_ready.emit(_random_per_strategy())


def _random_per_strategy():
    from ssq_prediction_v2 import Prediction
    r = {}
    for sn, info in PREDICTORS.items():
        preds = [Prediction(reds=sorted(random.sample(RED_RANGE, 6)),
                           blue=random.choice(BLUE_RANGE),
                           score=random.uniform(60, 95), strategy=sn)
                 for _ in range(5)]
        r[sn] = {'info': info, 'predictions': preds}
    return r


# ============================================================================
# 预测员卡片
# ============================================================================

class PredictorCard(QFrame):
    def __init__(self, s_name: str, info: dict, parent=None):
        super().__init__(parent)
        self.s_name = s_name
        self.info = info
        self._build()

    def _build(self):
        self.setStyleSheet(f"PredictorCard {{ background: {CARD_BG}; border: 2px solid {BORDER}; border-radius: 12px; }}")
        self.setMinimumWidth(190)
        self.setMaximumWidth(230)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        emoji = QLabel(self.info['emoji'])
        emoji.setFont(QFont("Segoe UI Emoji", 36))
        emoji.setAlignment(Qt.AlignCenter)
        lay.addWidget(emoji)

        name = QLabel(self.info['name'])
        name.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        name.setStyleSheet(f"color: {self.info['color']};")
        name.setAlignment(Qt.AlignCenter)
        lay.addWidget(name)

        algo = QLabel(self.info['algorithm'])
        algo.setFont(QFont("Microsoft YaHei", 7))
        algo.setStyleSheet(f"color: {TEXT_MID};")
        algo.setAlignment(Qt.AlignCenter)
        lay.addWidget(algo)

        tag = QLabel(self.info['tagline'])
        tag.setFont(QFont("Microsoft YaHei", 7))
        tag.setStyleSheet(f"color: {TEXT_MID}; font-style: italic;")
        tag.setAlignment(Qt.AlignCenter)
        lay.addWidget(tag)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        lay.addWidget(sep)

        self.ball_labels = []
        for i in range(5):
            row_w = QWidget()
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(2, 1, 2, 1)
            rl.setSpacing(1)
            idx = QLabel(f"#{i+1}")
            idx.setFont(QFont("Arial", 7)); idx.setStyleSheet(f"color: {TEXT_MID};")
            idx.setFixedWidth(16); rl.addWidget(idx)
            balls = []
            for j in range(7):
                bw = QLabel("--")
                bw.setFont(QFont("Arial", 8, QFont.Bold))
                bw.setAlignment(Qt.AlignCenter)
                bw.setFixedSize(22, 18)
                bw.setStyleSheet("color: #DC143C;" if j < 6 else "color: #4169E1;")
                balls.append(bw); rl.addWidget(bw)
            rl.addStretch(); lay.addWidget(row_w)
            self.ball_labels.append((idx, balls))
        lay.addStretch()

    def update_predictions(self, preds):
        for i, p in enumerate(preds[:5]):
            _, balls = self.ball_labels[i]
            for j, r in enumerate(p.reds):
                balls[j].setText(f"{r:02d}")
            balls[6].setText(f"{p.blue:02d}")


# ============================================================================
# PK排行榜
# ============================================================================

class PkLeaderboard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.setStyleSheet(f"PkLeaderboard {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 12px; }}")
        self.setMinimumHeight(180)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14); lay.setSpacing(6)

        t = QLabel("🏆 预测员累计奖金排行榜")
        t.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        t.setStyleSheet(f"color: {TEXT_DARK};"); lay.addWidget(t)

        self.rows = []
        medals = {0: '🥇', 1: '🥈', 2: '🥉'}
        for i in range(5):
            rw = QWidget(); rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 2, 0, 2); rl.setSpacing(10)
            medal = QLabel(medals.get(i, f"  {i+1}."))
            medal.setFont(QFont("Segoe UI Emoji", 14)); medal.setFixedWidth(30)
            rl.addWidget(medal)
            nl = QLabel("---"); nl.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
            nl.setFixedWidth(75); rl.addWidget(nl)
            pl = QLabel("¥ ---"); pl.setFont(QFont("Arial", 12, QFont.Bold))
            pl.setStyleSheet(f"color: {GOLD};"); pl.setMinimumWidth(130); rl.addWidget(pl)
            dl = QLabel(""); dl.setFont(QFont("Microsoft YaHei", 9))
            dl.setStyleSheet(f"color: {TEXT_MID};"); rl.addWidget(dl)
            rl.addStretch(); lay.addWidget(rw)
            self.rows.append((medal, nl, pl, dl))
        lay.addStretch()

    def update_rankings(self, rankings):
        if not rankings:
            # 无战绩时显示占位提示
            for i, (medal, nl, pl, dl) in enumerate(self.rows):
                if i == 0:
                    nl.setText("暂无战绩")
                    pl.setText("预测生成后将在此显示")
                    dl.setText("等待下期开奖后更新排名")
                    for w in [medal, nl, pl, dl]: w.setVisible(True)
                else:
                    for w in [medal, nl, pl, dl]: w.setVisible(False)
            return
        for i, (medal, nl, pl, dl) in enumerate(self.rows):
            if i < len(rankings):
                r = rankings[i]
                nl.setText(r['predictor_name'])
                tp = r['total_prize']
                pl.setText(f"¥{tp/10000:.1f}万" if tp >= 10000 else f"¥{tp:.0f}")
                dl.setText(f"{r['total_predictions']}注预测 | 中{r['win_count']}注")
                for w in [medal, nl, pl, dl]: w.setVisible(True)
            else:
                for w in [medal, nl, pl, dl]: w.setVisible(False)


# ============================================================================
# Matplotlib 图表
# ============================================================================

class TrendChartCanvas(FigureCanvas):
    """红球1-33概率偏离曲线 - 偏离理论均值(6/33)"""
    RED_EXPECT = 6.0 / 33.0  # 理论概率

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(9, 4), dpi=100, facecolor='#FAFAFA')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.period = 10  # 默认近10期

    def update_chart(self, history=None, window=None):
        self.ax.clear()
        if window is not None:
            self.period = window
        if not history:
            history = get_all_results()
        if not history:
            self.ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                        transform=self.ax.transAxes, fontsize=14, color='#999')
            self.draw(); return

        total_all = len(history)
        win = self.period if self.period > 0 and self.period < total_all else total_all
        start_idx = total_all - win

        # 计算窗口内各号码的实际概率，然后偏离均值
        colors = plt.cm.Spectral([i / 33 for i in range(33)])
        x_range = list(range(start_idx + 1, total_all + 1))

        # 滑动窗口计算偏离
        for n in range(1, 34):
            deviations = []
            for i in range(start_idx, total_all):
                window_slice = history[max(0, i - win + 1):i + 1]
                cnt = sum(1 for d in window_slice
                         for j in range(1, 7) if d.get(f'red_{j}', 0) == n)
                actual_prob = cnt / len(window_slice) if window_slice else 0
                deviation = actual_prob - self.RED_EXPECT
                deviations.append(deviation)

            self.ax.plot(x_range, deviations, color=colors[n - 1],
                        alpha=0.7 if n <= 16 else 0.4, linewidth=1.2,
                        label=f'{n}' if (n % 5 == 1 or n == 33) else '')

        # 零线
        self.ax.axhline(y=0, color='#999', linestyle='--', linewidth=0.8, alpha=0.5)
        # 在每条线终点标注号码
        for n in range(1, 34):
            if x_range:
                y_end = deviations[-1] if deviations else 0
                self.ax.annotate(f'{n}', xy=(x_range[-1], y_end),
                                fontsize=5, fontweight='bold', color=colors[n-1],
                                ha='left', va='center',
                                xytext=(3, 0), textcoords='offset points',
                                alpha=0.9)
        self.ax.set_title(f'红球 1-33 概率偏离曲线 ({"近"+str(win)+"期" if win < total_all else "全部"}, 基线=6/33≈{self.RED_EXPECT:.3f})',
                         fontsize=12, fontweight='bold')
        self.ax.set_ylabel('偏离 (实际概率 - 理论概率)')
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.fig.tight_layout(); self.draw()


class BlueChartCanvas(FigureCanvas):
    """蓝球1-16概率偏离曲线 - 偏离理论均值(1/16)"""
    BLUE_EXPECT = 1.0 / 16.0

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(9, 3), dpi=100, facecolor='#FAFAFA')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.period = 10

    def update_chart(self, history=None, window=None):
        self.ax.clear()
        if window is not None:
            self.period = window
        if not history:
            history = get_all_results()
        if not history:
            self.ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                        transform=self.ax.transAxes, fontsize=14, color='#999')
            self.draw(); return

        total_all = len(history)
        win = self.period if self.period > 0 and self.period < total_all else total_all
        start_idx = total_all - win

        colors = plt.cm.coolwarm([i / 16 for i in range(16)])
        x_range = list(range(start_idx + 1, total_all + 1))

        for n in range(1, 17):
            deviations = []
            for i in range(start_idx, total_all):
                window_slice = history[max(0, i - win + 1):i + 1]
                cnt = sum(1 for d in window_slice if d.get('blue', 0) == n)
                actual_prob = cnt / len(window_slice) if window_slice else 0
                deviations.append(actual_prob - self.BLUE_EXPECT)

            self.ax.plot(x_range, deviations, color=colors[n - 1],
                        alpha=0.8, linewidth=1.5, label=f'{n}')

        self.ax.axhline(y=0, color='#999', linestyle='--', linewidth=0.8, alpha=0.5)
        # 在每条线终点标注号码
        for n in range(1, 17):
            if x_range:
                y_end = deviations[-1] if deviations else 0
                self.ax.annotate(f'{n}', xy=(x_range[-1], y_end),
                                fontsize=6, fontweight='bold', color=colors[n-1],
                                ha='left', va='center',
                                xytext=(3, 0), textcoords='offset points',
                                alpha=0.9)
        win_label = f'近{win}期' if win < total_all else f'全部{total_all}期'
        self.ax.set_title(f'蓝球 1-16 概率偏离曲线 ({win_label}, 基线=1/16≈{self.BLUE_EXPECT:.4f})',
                         fontsize=12, fontweight='bold')
        self.ax.set_ylabel('偏离 (实际概率 - 理论概率)')
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.fig.tight_layout(); self.draw()


# ============================================================================
# 主窗口
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("双色球 TOP 5 预测员竞技场")
        self.setMinimumSize(1200, 850)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG}; }}")
        self.latest_draw = None
        self.predictions_data = {}
        self.history_data = []
        self._build()
        QTimer.singleShot(300, self._auto_load)

    def _build(self):
        cw = QWidget(); self.setCentralWidget(cw)
        ml = QVBoxLayout(cw)
        ml.setContentsMargins(16, 10, 16, 10); ml.setSpacing(10)

        title = QLabel("🏆 双色球 TOP 5 预测员竞技场")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_DARK};"); title.setAlignment(Qt.AlignCenter)
        ml.addWidget(title)

        # 开奖面板
        self.issue_panel = self._mk_issue_panel()
        ml.addWidget(self.issue_panel)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; background: {CARD_BG}; }}
            QTabBar::tab {{ padding: 8px 18px; font-size: 12px; background: #F0F0F0; }}
            QTabBar::tab:selected {{ background: white; border-bottom: 3px solid #C41A1A; font-weight: bold; }}
        """)
        self.tabs.addTab(self._mk_arena_tab(), "🎯 预测员竞技场")
        self.tabs.addTab(self._mk_leaderboard_tab(), "🏆 PK排行榜")
        self.tabs.addTab(self._mk_chart_tab(), "📈 趋势图表")
        ml.addWidget(self.tabs, stretch=1)

        self.sb = QStatusBar()
        self.sb.setStyleSheet(f"QStatusBar {{ background: #FAFAFA; border-top: 1px solid {BORDER}; }}")
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet(f"color: {TEXT_MID}; font-size: 11px;")
        self.sb.addWidget(self.lbl_status)
        self.setStatusBar(self.sb)

    def _mk_issue_panel(self):
        p = QFrame()
        p.setStyleSheet(f"QFrame {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 12px; }}")
        p.setMaximumHeight(95)
        l = QHBoxLayout(p); l.setContentsMargins(20, 10, 20, 10); l.setSpacing(16)

        il = QVBoxLayout(); il.setSpacing(4)
        self.issue_label = QLabel("第 --- 期")
        self.issue_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        self.issue_label.setStyleSheet("color: #C41A1A; border: none;"); il.addWidget(self.issue_label)
        self.date_label = QLabel("----年--月--日")
        self.date_label.setStyleSheet(f"color: {TEXT_MID}; border: none; font-size: 11px;"); il.addWidget(self.date_label)
        l.addLayout(il)

        self.balls_container = QWidget()
        self.balls_container.setStyleSheet("border: none;")
        self.balls_layout = QHBoxLayout(self.balls_container)
        self.balls_layout.setContentsMargins(0, 0, 0, 0); self.balls_layout.setSpacing(6)
        l.addWidget(self.balls_container)
        l.addStretch()

        ml2 = QVBoxLayout(); ml2.setSpacing(4)
        self.pool_label = QLabel("💰 奖池: ---")
        self.pool_label.setStyleSheet("color: #E67E22; font-size: 13px; font-weight: bold; border: none;"); ml2.addWidget(self.pool_label)
        self.refresh_btn = QPushButton("🔄 刷新数据")
        self.refresh_btn.setStyleSheet("QPushButton { background: #C41A1A; color: white; border-radius: 6px; padding: 8px 14px; font-weight: bold; } QPushButton:hover { background: #E03030; }")
        self.refresh_btn.clicked.connect(self._on_refresh); ml2.addWidget(self.refresh_btn)
        l.addLayout(ml2)
        return p

    def _mk_arena_tab(self):
        sc = QScrollArea(); sc.setWidgetResizable(True)
        sc.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        c = QWidget(); lay = QVBoxLayout(c)
        lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(12)

        hint = QLabel("💡 五位预测员各自使用不同的算法独立预测，每人 5 注号码")
        hint.setStyleSheet(f"color: {TEXT_MID}; font-size: 11px;"); lay.addWidget(hint)

        cl = QHBoxLayout(); cl.setSpacing(10)
        self.cards = {}
        for sn, info in PREDICTORS.items():
            card = PredictorCard(sn, info); cl.addWidget(card)
            self.cards[sn] = card
        cl.addStretch(); lay.addLayout(cl)

        # 重新预测按钮
        btn_row = QWidget()
        brl = QHBoxLayout(btn_row); brl.setContentsMargins(0, 0, 0, 0)
        self.repredict_btn = QPushButton("🔄 重新预测 (全精度)")
        self.repredict_btn.setStyleSheet("""
            QPushButton { background: #1E90FF; color: white; border-radius: 6px;
                          padding: 10px 20px; font-size: 13px; font-weight: bold; }
            QPushButton:hover { background: #1E70D0; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.repredict_btn.clicked.connect(self._on_re_predict)
        brl.addWidget(self.repredict_btn)
        self.repredict_status = QLabel("")
        self.repredict_status.setStyleSheet(f"color: {TEXT_MID}; font-size: 11px;")
        brl.addWidget(self.repredict_status)
        brl.addStretch()
        lay.addWidget(btn_row)

        self.pk_frame = QFrame()
        self.pk_frame.setStyleSheet(f"QFrame {{ background: #FFFDF5; border: 2px solid {GOLD}; border-radius: 12px; }}")
        self.pk_frame.setVisible(False)
        pkl = QVBoxLayout(self.pk_frame); pkl.setContentsMargins(16, 10, 16, 10)
        self.pk_title = QLabel("📊 本期开奖PK结果")
        self.pk_title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.pk_title.setStyleSheet(f"color: {TEXT_DARK}; border: none;"); pkl.addWidget(self.pk_title)
        self.pk_detail = QLabel("")
        self.pk_detail.setStyleSheet(f"color: {TEXT_MID}; border: none; font-size: 11px;")
        self.pk_detail.setWordWrap(True); pkl.addWidget(self.pk_detail)
        lay.addWidget(self.pk_frame)
        lay.addStretch()
        sc.setWidget(c); return sc

    def _mk_leaderboard_tab(self):
        c = QWidget(); lay = QVBoxLayout(c)
        lay.setContentsMargins(20, 14, 20, 14); lay.setSpacing(12)

        self.leaderboard = PkLeaderboard(); lay.addWidget(self.leaderboard)

        hl = QLabel("📋 近期战绩明细")
        hl.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        hl.setStyleSheet(f"color: {TEXT_DARK};"); lay.addWidget(hl)

        self.hist_table = QTableWidget()
        self.hist_table.setColumnCount(8)
        self.hist_table.setHorizontalHeaderLabels(
            ["期号", "预测员", "预测红球", "蓝", "实际红球", "蓝", "命中", "奖金"])
        self.hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hist_table.setStyleSheet(f"""
            QTableWidget {{ background: white; border: 1px solid {BORDER}; border-radius: 6px; }}
            QHeaderView::section {{ background: #FAFAFA; padding: 6px; font-weight: bold; }}
        """)
        self.hist_table.setMaximumHeight(350); lay.addWidget(self.hist_table)
        lay.addStretch(); return c

    def _mk_chart_tab(self):
        c = QWidget(); lay = QVBoxLayout(c)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(10)

        # 区间选择控件
        ctrl = QWidget()
        ctrl_layout = QHBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(0, 0, 0, 0); ctrl_layout.setSpacing(10)

        ctrl_layout.addWidget(QLabel("📊 图表区间:"))
        self.chart_period = QComboBox()
        self.chart_period.addItems(["近10期", "近20期", "近50期", "近100期", "近1年(~150期)", "全部"])
        self.chart_period.setCurrentIndex(0)
        self.chart_period.currentIndexChanged.connect(self._on_period_changed)
        self.chart_period.setStyleSheet("""
            QComboBox { padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px; }
        """)
        ctrl_layout.addWidget(self.chart_period)
        ctrl_layout.addStretch()

        # 快捷切换按钮
        for label, w in [("10期", 10), ("20期", 20), ("50期", 50), ("100期", 100), ("全部", 0)]:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton { padding: 4px 10px; border: 1px solid #ccc; border-radius: 4px;
                              background: white; font-size: 11px; }
                QPushButton:hover { background: #F0F0F0; border-color: #C41A1A; }
            """)
            btn.clicked.connect(lambda checked, w=w: self._set_chart_window(w))
            ctrl_layout.addWidget(btn)

        lay.addWidget(ctrl)
        self.red_chart = TrendChartCanvas(); lay.addWidget(self.red_chart)
        self.blue_chart = BlueChartCanvas(); lay.addWidget(self.blue_chart)
        return c

    def _set_chart_window(self, window: int):
        """切换图表区间"""
        period_map = {10: 0, 20: 1, 50: 2, 100: 3, 150: 4, 0: 5}
        if window in period_map:
            self.chart_period.setCurrentIndex(period_map[window])
        self.red_chart.update_chart(self.history_data, window=window)
        self.blue_chart.update_chart(self.history_data, window=window)

    def _on_period_changed(self, idx: int):
        """下拉框切换图表区间"""
        windows = [10, 20, 50, 100, 150, 0]
        if idx < len(windows):
            window = windows[idx]
            self.red_chart.update_chart(self.history_data, window=window)
            self.blue_chart.update_chart(self.history_data, window=window)

    # === 数据加载 ===

    def _get_target_issue(self):
        """计算下一期目标期号"""
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT issue_number FROM lottery_results ORDER BY issue_number DESC LIMIT 1")
        row = c.fetchone(); conn.close()
        if row:
            issue_str = row[0]
            # 处理5位期号(如"26082")和7位期号(如"2026082")
            if len(issue_str) <= 5:
                nn = int(issue_str[-3:]) + 1
            else:
                nn = int(issue_str[4:]) + 1
            return f"{datetime.now().year}{nn:03d}"
        return f"{datetime.now().year}001"

    def _load_cached_predictions(self):
        """从数据库加载已保存的预测"""
        target = self._get_target_issue()
        conn = get_connection()
        conn.row_factory = __import__('sqlite3').Row
        c = conn.cursor()
        c.execute(
            "SELECT predictor_name, predicted_reds, predicted_blue "
            "FROM predictor_records WHERE target_issue=? AND actual_reds IS NULL "
            "ORDER BY id", (target,))
        rows = c.fetchall(); conn.close()

        if not rows:
            return None

        # 按预测员分组重建数据结构
        from ssq_prediction_v2 import Prediction
        result = {}
        for sn, info in PREDICTORS.items():
            result[sn] = {'info': info, 'predictions': []}

        for row in rows:
            name = row['predictor_name']
            reds = [int(x) for x in row['predicted_reds'].split(',')]
            blue = row['predicted_blue']
            # 找到对应的 strategy name
            for sn, info in PREDICTORS.items():
                if info['name'] == name:
                    if len(result[sn]['predictions']) < 5:
                        result[sn]['predictions'].append(
                            Prediction(reds=reds, blue=blue, score=0, strategy=sn))
                    break

        return result

    def _display_predictions(self, data: dict):
        """将预测数据显示到卡片上"""
        for sn, card in self.cards.items():
            if sn in data and data[sn]['predictions']:
                card.update_predictions(data[sn]['predictions'])

    def _auto_load(self):
        create_database()
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM lottery_results")
        cnt = c.fetchone()[0]; conn.close()
        if cnt < 100:
            n = import_from_json('ssq_history.json')
            self.set_status(f"导入 {n} 条历史数据")
        self.history_data = get_all_results()
        self.red_chart.update_chart(self.history_data)
        self.blue_chart.update_chart(self.history_data)
        rankings = get_predictor_rankings()
        self.leaderboard.update_rankings(rankings)
        self._update_hist_table()

        # 先尝试加载已保存的预测
        cached = self._load_cached_predictions()
        if cached and any(len(d['predictions']) > 0 for d in cached.values()):
            self._display_predictions(cached)
            target = self._get_target_issue()
            self.set_status(f"已加载保存的预测 (期号: {target})")
            self.repredict_status.setText(f"✓ 已加载 {target} 期预测")
        else:
            self.set_status("首次运行，正在生成预测...")

        self._start_fetch()

    def _start_fetch(self):
        self.ft = DataFetchThread()
        self.ft.progress.connect(self.set_status)
        self.ft.data_ready.connect(self._on_data)
        self.ft.error.connect(self._on_err)
        self.ft.start()

    def _on_data(self, data):
        self.latest_draw = data
        # 将获取到的开奖数据存入数据库，确保 _get_target_issue() 计算正确
        try:
            saved = save_draw_result(
                data['issue'], data['date'], data['reds'], data['blue'])
            if saved:
                self.history_data = get_all_results()
        except Exception:
            logger.exception("开奖数据入库失败")
        self._update_issue(data)
        # 检查是否已有缓存预测，避免重复生成
        cached = self._load_cached_predictions()
        if cached and any(len(d['predictions']) > 0 for d in cached.values()):
            self._display_predictions(cached)
            self.set_status("已加载保存的预测")
            self.repredict_status.setText("✓ 预测已就绪")
            self.repredict_btn.setEnabled(True)
        else:
            self._start_pred()

    def _on_err(self, msg):
        self.set_status(f"网络失败: {msg}，使用本地数据")
        latest = get_latest_issue()
        if latest:
            self._on_data({
                'issue': latest['issue_number'], 'date': latest['draw_date'],
                'weekday': '', 'time': '21:15',
                'reds': [latest[f'red_{i}'] for i in range(1, 7)],
                'blue': latest['blue'], 'sales': 0, 'pool': 0,
                'prize_grades': [], 'province_winners': [], 'province_raw': '',
            })

    def _start_pred(self):
        self.set_status("TOP 5 预测员正在生成号码...")
        self.pt = PredictionThreadV3()
        self.pt.progress.connect(self.set_status)
        self.pt.data_ready.connect(self._on_preds)
        self.pt.start()

    def _on_preds(self, data: dict):
        self.predictions_data = data
        self._display_predictions(data)
        ni = self._get_target_issue()
        try:
            saved = save_predictor_predictions(ni, data)
            self.set_status(f"预测完成 | 已保存 {saved} 条 (期号: {ni})")
            self.repredict_status.setText(f"✓ 预测已保存 ({ni}期)")
            self.repredict_btn.setEnabled(True)
        except Exception as e:
            self.set_status(f"保存失败: {e}")
            self.repredict_btn.setEnabled(True)

    def _on_re_predict(self):
        """重新预测按钮 - 清除旧数据并重新计算"""
        self.repredict_btn.setEnabled(False)
        self.repredict_status.setText("⏳ 正在重新预测...")
        ni = self._get_target_issue()
        # 清除该期旧预测
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM predictor_records WHERE target_issue=?", (ni,))
        conn.commit(); conn.close()
        # 重新运行
        self._start_pred()

    # === UI更新 ===

    def _update_issue(self, data):
        self.issue_label.setText(f"第 {data['issue']} 期")
        wd_map = {'一': '周一', '二': '周二', '三': '周三', '四': '周四', '五': '周五', '六': '周六', '日': '周日'}
        wd = wd_map.get(data.get('weekday', ''), '')
        self.date_label.setText(f"📅 {data['date']} {wd} ⏰ {data.get('time', '21:15')}")
        self._update_balls(data['reds'], data['blue'])
        pool = data.get('pool', 0)
        self.pool_label.setText(f"💰 奖池: {format_money(pool)}" if pool else "💰 奖池: ---")
        self._check_pk(data)

    def _update_balls(self, reds, blue):
        while self.balls_layout.count():
            it = self.balls_layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        for r in reds:
            self.balls_layout.addWidget(BallWidget(r, "red", 40))
        plus = QLabel("+"); plus.setFont(QFont("Arial", 14, QFont.Bold))
        plus.setStyleSheet("color: #999; border: none;"); self.balls_layout.addWidget(plus)
        self.balls_layout.addWidget(BallWidget(blue, "blue", 40))
        self.balls_layout.addStretch()

    def _check_pk(self, data):
        import sqlite3
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # 标准化期号格式（备用数据源可能返回5位如"26082"）
        from ssq_database import _normalize_issue
        issue = _normalize_issue(data['issue'])
        c.execute("SELECT COUNT(*) as cnt FROM predictor_records WHERE target_issue=? AND actual_reds IS NULL", (issue,))
        row = c.fetchone(); conn.close()
        if row and row['cnt'] > 0:
            pk = update_predictor_after_draw(issue, data['reds'], data['blue'])
            if pk: self._show_pk(pk)

    def _show_pk(self, pk):
        self.pk_frame.setVisible(True)
        reds_str = ' '.join(f'{r:02d}' for r in pk['actual_reds'])
        lines = [f"开奖号码: 🔴 {reds_str}  🔵 {pk['actual_blue']:02d}", ""]
        sorted_r = sorted(pk['results'], key=lambda x: x['prize_amount'], reverse=True)
        medals = {0: '🥇', 1: '🥈', 2: '🥉', 3: '4.', 4: '5.'}
        for rank, r in enumerate(sorted_r):
            m = medals.get(rank, f'{rank+1}.')
            if r['prize_level'] > 0:
                lines.append(f"{m} {r['predictor_name']}: 中{r['red_hit']}红+{r['blue_hit']}蓝 → {r['prize_name']} 💰 ¥{r['prize_amount']:,}")
            else:
                lines.append(f"{m} {r['predictor_name']}: 中{r['red_hit']}红+{r['blue_hit']}蓝 → 未中奖")
        self.pk_detail.setText('\n'.join(lines))
        rankings = get_predictor_rankings()
        self.leaderboard.update_rankings(rankings)
        self._update_hist_table()

    def _update_hist_table(self):
        import sqlite3
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT target_issue, predictor_name, predicted_reds, predicted_blue,
                   actual_reds, actual_blue, red_match_count, blue_match,
                   prize_name, prize_amount
            FROM predictor_records WHERE actual_reds IS NOT NULL
            ORDER BY id DESC LIMIT 50
        """)
        rows = c.fetchall(); conn.close()
        self.hist_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            vals = [
                row['target_issue'], row['predictor_name'],
                row['predicted_reds'], str(row['predicted_blue']),
                row['actual_reds'] or '', str(row['actual_blue']) if row['actual_blue'] else '',
                f"{row['red_match_count']}红+{row['blue_match']}蓝",
                f"{row['prize_name']} ¥{row['prize_amount']:,.0f}" if row['prize_amount'] > 0 else '未中奖',
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v); it.setTextAlignment(Qt.AlignCenter)
                self.hist_table.setItem(i, j, it)

    def _on_refresh(self):
        self.set_status("正在刷新...")
        self.history_data = get_all_results()
        self.red_chart.update_chart(self.history_data)
        self.blue_chart.update_chart(self.history_data)
        # 刷新PK排行榜和战绩明细
        rankings = get_predictor_rankings()
        self.leaderboard.update_rankings(rankings)
        self._update_hist_table()
        self._start_fetch()

    def set_status(self, msg: str):
        self.lbl_status.setText(msg)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    app.setStyleSheet("QMainWindow { background: #F0F2F5; } QScrollArea { border: none; background: transparent; }")
    w = MainWindow(); w.show()
    if len(sys.argv) == 4:
        pk = update_predictor_after_draw(sys.argv[1],
            [int(x) for x in sys.argv[2].split(',')], int(sys.argv[3]))
        if pk: w._show_pk(pk)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
