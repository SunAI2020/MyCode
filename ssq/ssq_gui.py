"""
双色球预测系统 - PyQt5 图形界面

功能:
1. 本期开奖信息展示（期号、日期、时间、开奖号码、奖池、销售额）
2. 各奖级明细 + 一等奖中奖地区分布
3. 10组预测号码展示（含系统评分）
4. 1-33红球累积中选概率趋势曲线图表
5. 往期开奖数据查询
6. 启动自动获取最新数据
"""
import sys
import math
import random
import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QSplitter, QGroupBox, QScrollArea,
    QStatusBar, QMessageBox, QProgressBar, QSizePolicy, QSpacerItem,
    QAbstractItemView, QComboBox, QDateEdit,
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QDate, QSize, QRect,
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QGradient, QRadialGradient,
    QPixmap, QIcon, QPalette, QLinearGradient,
)

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
matplotlib.rcParams['axes.unicode_minus'] = False

# 导入项目模块
from ssq_database import (
    get_all_results, get_latest_issue, get_statistics,
    get_connection, create_database, import_from_json,
)
from ssq_prediction import (
    FusionPredictor, StatisticalAnalyzer, BacktestEngine,
    RED_BALL_RANGE, BLUE_BALL_RANGE, TOP_N_PREDICTIONS,
    LotteryDraw,
)
# V2 预测引擎 (TOP 5 算法)
try:
    from ssq_prediction_v2 import (
        BacktestEngineV2, FeatureEngineer, StackingEnsemble,
        FrequencyMissingStrategy, MCMCStrategy,
        LSTMStrategy, XGBoostStrategy, RandomForestStrategy,
    )
    HAS_V2_ENGINE = True
except ImportError:
    HAS_V2_ENGINE = False
from ssq_data_fetcher import (
    fetch_latest_draw, fetch_draw_by_issue, fetch_recent_draws,
    load_cached_latest, save_cache, format_money,
    PRIZE_NAMES, PRIZE_CONDITIONS,
)

# ============================================================
# 样式常量
# ============================================================
RED_BALL_COLOR = QColor("#DC143C")       # 深红
BLUE_BALL_COLOR = QColor("#4169E1")      # 皇家蓝
BG_COLOR = "#F5F5F5"                     # 浅灰背景
PRIMARY_COLOR = "#C41A1A"                # 主题红色
ACCENT_COLOR = "#1E90FF"                 # 强调蓝色
CARD_BG = "#FFFFFF"                      # 卡片白色
TEXT_DARK = "#333333"                    # 深色文字
TEXT_LIGHT = "#666666"                   # 浅色文字
BORDER_COLOR = "#E0E0E0"                 # 边框色

STYLESHEET = f"""
QMainWindow {{
    background-color: {BG_COLOR};
}}
QGroupBox {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-size: 13px;
    font-weight: bold;
    color: {TEXT_DARK};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: {PRIMARY_COLOR};
}}
QTableWidget {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    gridline-color: #F0F0F0;
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QTableWidget::item:selected {{
    background-color: #FFE0E0;
    color: {TEXT_DARK};
}}
QHeaderView::section {{
    background-color: #FAFAFA;
    border: none;
    border-bottom: 2px solid {BORDER_COLOR};
    padding: 6px 8px;
    font-weight: bold;
    color: {TEXT_DARK};
}}
QPushButton {{
    background-color: {PRIMARY_COLOR};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: #E51A1A;
}}
QPushButton:pressed {{
    background-color: #A01515;
}}
QPushButton:disabled {{
    background-color: #CCCCCC;
}}
QPushButton#refreshBtn {{
    background-color: {PRIMARY_COLOR};
    padding: 8px 24px;
    font-size: 13px;
}}
QPushButton#queryBtn {{
    background-color: {ACCENT_COLOR};
    padding: 6px 16px;
}}
QPushButton#queryBtn:hover {{
    background-color: #1E70D0;
}}
QLineEdit {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
    background-color: white;
}}
QLineEdit:focus {{
    border-color: {PRIMARY_COLOR};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    background-color: {CARD_BG};
}}
QTabBar::tab {{
    background-color: #E8E8E8;
    border: 1px solid {BORDER_COLOR};
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 12px;
    color: {TEXT_LIGHT};
}}
QTabBar::tab:selected {{
    background-color: {CARD_BG};
    color: {PRIMARY_COLOR};
    font-weight: bold;
    border-bottom: 2px solid {PRIMARY_COLOR};
}}
QTabBar::tab:hover {{
    background-color: #F0F0F0;
}}
QStatusBar {{
    background-color: #FAFAFA;
    border-top: 1px solid {BORDER_COLOR};
    font-size: 11px;
    color: {TEXT_LIGHT};
}}
QLabel#titleLabel {{
    font-size: 18px;
    font-weight: bold;
    color: {PRIMARY_COLOR};
}}
QLabel#issueLabel {{
    font-size: 14px;
    font-weight: bold;
    color: {TEXT_DARK};
}}
QLabel#infoLabel {{
    font-size: 12px;
    color: {TEXT_LIGHT};
}}
QLabel#moneyLabel {{
    font-size: 12px;
    color: {TEXT_DARK};
    font-weight: bold;
}}
"""


# ============================================================
# 自定义球号绘制组件
# ============================================================
class BallWidget(QWidget):
    """单个双色球号码球控件（圆形渐变绘制）"""

    def __init__(self, number: int = 0, ball_type: str = "red",
                 size: int = 36, parent=None):
        super().__init__(parent)
        self.number = number
        self.ball_type = ball_type  # "red" or "blue"
        self.ball_size = size
        self.setFixedSize(size + 4, size + 4)

    def paintEvent(self, event):
        if self.number <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.ball_size // 2
        cx = self.width() // 2
        cy = self.height() // 2

        # 渐变色
        if self.ball_type == "red":
            main_color = QColor("#E03030")
            dark_color = QColor("#8B0000")
            light_color = QColor("#FF6060")
        else:
            main_color = QColor("#3060E0")
            dark_color = QColor("#002080")
            light_color = QColor("#6080FF")

        # 径向渐变模拟3D效果
        gradient = QRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 1.2)
        gradient.setColorAt(0.0, light_color)
        gradient.setColorAt(0.4, main_color)
        gradient.setColorAt(1.0, dark_color)

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(dark_color.darker(120), 1))
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # 白色高光
        painter.setBrush(QBrush(QColor(255, 255, 255, 60)))
        painter.setPen(Qt.NoPen)
        hx = int(cx - r * 0.40)
        hy = int(cy - r * 0.55)
        hw = int(r * 0.6)
        hh = int(r * 0.45)
        painter.drawEllipse(hx, hy, hw, hh)

        # 号码数字
        painter.setPen(QPen(Qt.white, 1))
        font = QFont("Arial", int(max(8, r * 0.55)), QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRect(cx - r, cy - r, r * 2, r * 2),
                         Qt.AlignCenter, f"{self.number:02d}")

        painter.end()


class BallsDisplayWidget(QWidget):
    """红球(6个) + 蓝球(1个) 横向排列"""

    def __init__(self, reds: List[int] = None, blue: int = 0,
                 ball_size: int = 40, parent=None):
        super().__init__(parent)
        self.ball_size = ball_size
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        reds = reds or []
        for r in reds:
            ball = BallWidget(r, "red", ball_size)
            layout.addWidget(ball)

        # 加号分隔
        plus = QLabel("+")
        plus.setFont(QFont("Arial", ball_size // 2, QFont.Bold))
        plus.setStyleSheet("color: #999;")
        layout.addWidget(plus)

        # 蓝球
        if blue > 0:
            ball = BallWidget(blue, "blue", ball_size)
            layout.addWidget(ball)

        layout.addStretch()


class MiniBallWidget(QWidget):
    """小号球控件（用于表格内显示）"""

    def __init__(self, number: int = 0, ball_type: str = "red", parent=None):
        super().__init__(parent)
        self.number = number
        self.ball_type = ball_type
        self.setFixedSize(26, 26)

    def paintEvent(self, event):
        if self.number <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = 11
        cx, cy = 13, 13

        if self.ball_type == "red":
            gradient = QRadialGradient(cx - 3, cy - 3, 13)
            gradient.setColorAt(0.0, QColor("#FF5050"))
            gradient.setColorAt(0.5, QColor("#DC143C"))
            gradient.setColorAt(1.0, QColor("#8B0000"))
        else:
            gradient = QRadialGradient(cx - 3, cy - 3, 13)
            gradient.setColorAt(0.0, QColor("#6080FF"))
            gradient.setColorAt(0.5, QColor("#4169E1"))
            gradient.setColorAt(1.0, QColor("#002080"))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        painter.setPen(QPen(Qt.white, 1))
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRect(0, 0, 26, 26), Qt.AlignCenter, f"{self.number:02d}")
        painter.end()


# ============================================================
# 数据获取线程
# ============================================================
class DataFetchThread(QThread):
    """后台线程获取最新开奖数据"""
    data_ready = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        self.progress.emit("正在获取最新开奖数据...")
        try:
            # 先尝试在线获取
            latest = fetch_latest_draw()
            if latest:
                save_cache(latest)
                self.data_ready.emit(latest)
                return

            # 在线失败，尝试缓存
            self.progress.emit("网络获取失败，尝试加载缓存...")
            cached = load_cached_latest()
            if cached:
                self.data_ready.emit(cached)
                self.progress.emit("已加载缓存数据")
                return

            self.error.emit("无法获取开奖数据，请检查网络连接")
        except Exception as e:
            self.error.emit(f"数据获取异常: {str(e)}")


class PredictionThread(QThread):
    """后台线程生成预测 - 支持 V1/V2 引擎"""
    data_ready = pyqtSignal(list)
    progress = pyqtSignal(str)

    def __init__(self, parent=None, use_v2: bool = True):
        super().__init__(parent)
        self.use_v2 = use_v2 and HAS_V2_ENGINE

    def run(self):
        self.progress.emit("正在生成预测号码...")
        try:
            all_results = get_all_results()
            if not all_results:
                self.progress.emit("无历史数据，使用随机预测...")
                self.data_ready.emit(self._random_predictions())
                return

            if self.use_v2:
                self._run_v2(all_results)
            else:
                self._run_v1(all_results)
        except Exception as e:
            self.progress.emit(f"预测异常: {e}")
            self.data_ready.emit(self._random_predictions())

    def _run_v2(self, all_results):
        """使用 TOP 5 算法 V2 引擎"""
        self.progress.emit("正在运行 TOP 5 算法回测...")
        engine = BacktestEngineV2(all_results)
        result = engine.run(sample_every=10)

        preds = []
        for i, p in enumerate(result['final_predictions'], 1):
            preds.append({
                "index": i,
                "reds": p.reds,
                "blue": p.blue,
                "score": round(min(p.score, 99.9), 1),
            })
        self.data_ready.emit(preds)

    def _run_v1(self, all_results):
        """使用原 V1 引擎 (回退)"""
        self.progress.emit("使用 V1 融合预测引擎...")
        predictor = FusionPredictor(all_results, fast_mode=False)
        preds = predictor.predict(TOP_N_PREDICTIONS)
        result = []
        for i, p in enumerate(preds, 1):
            result.append({
                "index": i,
                "reds": p.reds,
                "blue": p.blue,
                "score": round(p.score * 100, 1),
            })
        self.data_ready.emit(result)

    @staticmethod
    def _random_predictions() -> List[Dict]:
        preds = []
        for i in range(10):
            reds = sorted(random.sample(list(RED_BALL_RANGE), 6))
            blue = random.choice(list(BLUE_BALL_RANGE))
            preds.append({
                "index": i + 1,
                "reds": reds,
                "blue": blue,
                "score": round(random.uniform(60, 95), 1),
            })
        return preds


class IssueQueryThread(QThread):
    """后台线程查询指定期号（在线接口会阻塞，放到线程避免卡 UI）"""
    query_done = pyqtSignal(str, object)   # (issue, dict在线数据 或 None)

    def __init__(self, issue: str, parent=None):
        super().__init__(parent)
        self.issue = issue

    def run(self):
        data = None
        try:
            data = fetch_draw_by_issue(self.issue)
        except Exception:
            logger.exception("期号查询失败: %s", self.issue)
            data = None
        self.query_done.emit(self.issue, data)


# ============================================================
# Matplotlib 图表 Canvas
# ============================================================
class TrendChartCanvas(FigureCanvas):
    """1-33红球累积中选概率趋势曲线"""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(9, 4.5), dpi=100)
        self.fig.patch.set_facecolor('#FAFAFA')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update_chart(self, history: List[Dict] = None):
        """根据历史数据更新概率趋势曲线"""
        self.ax.clear()

        if not history:
            history = get_all_results()

        if not history:
            self.ax.text(0.5, 0.5, "暂无数据", ha='center', va='center',
                         transform=self.ax.transAxes, fontsize=14, color='#999')
            self.draw()
            return

        # 累积统计每个数字的出现次数
        cum_counts = {n: [] for n in RED_BALL_RANGE}
        cum_total = {n: [] for n in RED_BALL_RANGE}
        counts = {n: 0 for n in RED_BALL_RANGE}
        total_draws = 0

        for row in history:
            total_draws += 1
            reds = [row.get(f'red_{i}', 0) for i in range(1, 7)]
            for r in reds:
                if r in counts:
                    counts[r] += 1
            for n in RED_BALL_RANGE:
                cum_counts[n].append(counts[n])
                cum_total[n].append(total_draws)

        # 计算累积概率曲线
        x = list(range(1, len(history) + 1))
        colors = plt.cm.Spectral([i / 32 for i in range(33)])

        for n in RED_BALL_RANGE:
            if len(cum_counts[n]) == len(x):
                probs = [c / max(t, 1) for c, t in
                         zip(cum_counts[n], cum_total[n])]
                label = f"{n:02d}" if n % 5 == 1 or n == 33 else ""
                alpha = 0.7 if n <= 16 else 0.4
                self.ax.plot(x, probs, color=colors[n - 1], alpha=alpha,
                             linewidth=1.2, label=label)

        self.ax.set_xlabel("期数序号", fontsize=10, color='#666')
        self.ax.set_ylabel("累积出现概率", fontsize=10, color='#666')
        self.ax.set_title("红球 1-33 累积中选概率趋势曲线", fontsize=12,
                          fontweight='bold', color='#333', pad=10)
        self.ax.legend(loc='upper left', ncol=7, fontsize=7,
                       framealpha=0.5, title="号码")
        self.ax.set_ylim(0, max(0.30, self.ax.get_ylim()[1]))
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.tick_params(labelsize=9)

        self.fig.tight_layout()
        self.draw()


class BlueChartCanvas(FigureCanvas):
    """1-16蓝球累积中选概率趋势曲线"""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(9, 3.5), dpi=100)
        self.fig.patch.set_facecolor('#FAFAFA')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update_chart(self, history: List[Dict] = None):
        self.ax.clear()

        if not history:
            history = get_all_results()

        if not history:
            self.ax.text(0.5, 0.5, "暂无数据", ha='center', va='center',
                         transform=self.ax.transAxes, fontsize=14, color='#999')
            self.draw()
            return

        cum_counts = {n: [] for n in BLUE_BALL_RANGE}
        cum_total = {n: [] for n in BLUE_BALL_RANGE}
        counts = {n: 0 for n in BLUE_BALL_RANGE}
        total_draws = 0

        for row in history:
            total_draws += 1
            blue = row.get('blue', 0)
            if blue in counts:
                counts[blue] += 1
            for n in BLUE_BALL_RANGE:
                cum_counts[n].append(counts[n])
                cum_total[n].append(total_draws)

        x = list(range(1, len(history) + 1))
        colors = plt.cm.coolwarm([i / 15 for i in range(16)])

        for n in BLUE_BALL_RANGE:
            if len(cum_counts[n]) == len(x):
                probs = [c / max(t, 1) for c, t in
                         zip(cum_counts[n], cum_total[n])]
                self.ax.plot(x, probs, color=colors[n - 1], alpha=0.8,
                             linewidth=1.5, label=f"{n:02d}")

        self.ax.set_xlabel("期数序号", fontsize=10, color='#666')
        self.ax.set_ylabel("累积出现概率", fontsize=10, color='#666')
        self.ax.set_title("蓝球 1-16 累积中选概率趋势曲线", fontsize=12,
                          fontweight='bold', color='#333', pad=8)
        self.ax.legend(loc='upper left', ncol=8, fontsize=8,
                       framealpha=0.5)
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.tick_params(labelsize=9)

        self.fig.tight_layout()
        self.draw()


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    """双色球预测系统主窗口"""

    def __init__(self):
        super().__init__()
        self.latest_draw: Optional[Dict] = None
        self.predictions: List[Dict] = []
        self.history_data: List[Dict] = []

        self.setWindowTitle("双色球预测系统 - Double Color Ball Prediction")
        self.setMinimumSize(1100, 800)
        self.resize(1280, 900)

        # 居中显示
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - 1280) // 2,
                  (screen.height() - 900) // 2)

        self.setStyleSheet(STYLESHEET)
        self._setup_ui()
        self._setup_statusbar()

        # 启动后自动加载数据
        QTimer.singleShot(300, self._auto_load_data)

    # ----------------------------------------------------------
    # UI 构建
    # ----------------------------------------------------------
    def _setup_ui(self):
        """构建完整UI布局"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # --- 顶部标题栏 ---
        header = QHBoxLayout()
        title = QLabel("🎯 双色球预测系统")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()

        self.btn_refresh = QPushButton("🔄 刷新数据")
        self.btn_refresh.setObjectName("refreshBtn")
        self.btn_refresh.clicked.connect(self._on_refresh)
        header.addWidget(self.btn_refresh)

        main_layout.addLayout(header)

        # --- 本期开奖信息面板 ---
        main_layout.addWidget(self._create_issue_panel())

        # --- 主内容区（Tab页） ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_overview_tab(), "📋 本期概览")
        self.tabs.addTab(self._create_prediction_tab(), "🎯 预测号码")
        self.tabs.addTab(self._create_chart_tab(), "📈 趋势图表")
        self.tabs.addTab(self._create_query_tab(), "🔍 往期查询")
        main_layout.addWidget(self.tabs, stretch=1)

    def _create_issue_panel(self) -> QFrame:
        """创建本期开奖信息面板"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame#issuePanel {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
            }}
            QLabel#issueNum {{
                font-size: 18px;
                font-weight: bold;
                color: {PRIMARY_COLOR};
            }}
            QLabel#drawDate {{
                font-size: 13px;
                color: {TEXT_DARK};
                font-weight: bold;
            }}
            QLabel#poolLabel {{
                font-size: 13px;
                color: #E67E22;
                font-weight: bold;
            }}
            QLabel#salesLabel {{
                font-size: 12px;
                color: {TEXT_LIGHT};
            }}
        """)
        frame.setObjectName("issuePanel")
        frame.setMinimumHeight(85)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)

        # 左侧：期号 + 日期
        left = QVBoxLayout()
        self.lbl_issue = QLabel("加载中...")
        self.lbl_issue.setObjectName("issueNum")
        left.addWidget(self.lbl_issue)

        self.lbl_date = QLabel("")
        self.lbl_date.setObjectName("drawDate")
        left.addWidget(self.lbl_date)
        layout.addLayout(left)

        # 分隔线
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet(f"color: {BORDER_COLOR};")
        layout.addWidget(sep1)

        # 中间：开奖号码
        mid = QVBoxLayout()
        mid.addWidget(QLabel("开奖号码"))
        self.balls_display = BallsDisplayWidget([], 0, 34)
        mid.addWidget(self.balls_display)
        layout.addLayout(mid)

        # 分隔线
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet(f"color: {BORDER_COLOR};")
        layout.addWidget(sep2)

        # 右侧：奖池 + 销售额
        right = QVBoxLayout()
        self.lbl_pool = QLabel("奖池: --")
        self.lbl_pool.setObjectName("poolLabel")
        right.addWidget(self.lbl_pool)

        self.lbl_sales = QLabel("本期销售: --")
        self.lbl_sales.setObjectName("salesLabel")
        right.addWidget(self.lbl_sales)

        self.lbl_first_prize = QLabel("一等奖分布: --")
        self.lbl_first_prize.setObjectName("salesLabel")
        self.lbl_first_prize.setWordWrap(True)
        right.addWidget(self.lbl_first_prize)

        layout.addLayout(right)
        layout.addStretch()

        return frame

    def _create_overview_tab(self) -> QWidget:
        """创建本期概览标签页（奖级明细 + 一等奖分布）"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 左侧：奖级明细表格
        left_group = QGroupBox("各奖级明细")
        left_layout = QVBoxLayout(left_group)

        self.prize_table = QTableWidget()
        self.prize_table.setColumnCount(5)
        self.prize_table.setHorizontalHeaderLabels(
            ["奖项", "中奖条件", "中奖注数", "单注奖金", "奖金合计"]
        )
        self.prize_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.prize_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.prize_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.prize_table.setAlternatingRowColors(True)
        self.prize_table.verticalHeader().setVisible(False)
        # 初始化占位行
        self.prize_table.setRowCount(1)
        placeholder = QTableWidgetItem("等待数据加载...")
        placeholder.setTextAlignment(Qt.AlignCenter)
        placeholder.setForeground(QColor("#999"))
        self.prize_table.setSpan(0, 0, 1, 5)
        self.prize_table.setItem(0, 0, placeholder)
        left_layout.addWidget(self.prize_table)

        # 右侧：一等奖分布表格
        right_group = QGroupBox("一等奖中奖地区分布")
        right_layout = QVBoxLayout(right_group)

        self.province_table = QTableWidget()
        self.province_table.setColumnCount(4)
        self.province_table.setHorizontalHeaderLabels(
            ["地区", "中奖注数", "单注奖金", "销售地址"])
        self.province_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.province_table.setColumnWidth(0, 80)
        self.province_table.setColumnWidth(1, 80)
        self.province_table.setColumnWidth(2, 120)
        self.province_table.setColumnWidth(3, 180)
        self.province_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.province_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.province_table.setAlternatingRowColors(True)
        self.province_table.verticalHeader().setVisible(False)
        # 初始化占位行
        self.province_table.setRowCount(1)
        placeholder2 = QTableWidgetItem("等待数据加载...")
        placeholder2.setTextAlignment(Qt.AlignCenter)
        placeholder2.setForeground(QColor("#999"))
        self.province_table.setSpan(0, 0, 1, 4)
        self.province_table.setItem(0, 0, placeholder2)
        right_layout.addWidget(self.province_table)

        # 分别设置左右占比
        layout.addWidget(left_group, stretch=3)
        layout.addWidget(right_group, stretch=2)

        return widget

    def _create_prediction_tab(self) -> QWidget:
        """创建预测号码标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明文字
        info = QLabel(
            "基于6种策略融合算法生成的10组预测号码"
            "（仅供学术研究参考，不构成投注建议）"
        )
        info.setObjectName("infoLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

        # 预测表格
        self.pred_table = QTableWidget()
        self.pred_table.setColumnCount(9)
        self.pred_table.setHorizontalHeaderLabels(
            ["序号", "红1", "红2", "红3", "红4", "红5", "红6", "蓝球", "系统评分"]
        )
        self.pred_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.pred_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pred_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pred_table.verticalHeader().setVisible(False)
        self.pred_table.setAlternatingRowColors(True)
        self.pred_table.verticalHeader().setDefaultSectionSize(34)
        layout.addWidget(self.pred_table)

        # 免责声明
        disclaimer = QLabel(
            "⚠️ 免责声明：彩票为随机事件，本系统仅用于学术研究和统计分析参考，"
            "不构成任何投注建议。请理性购彩，量力而行。"
        )
        disclaimer.setStyleSheet(
            "color: #E67E22; font-size: 11px; padding: 8px;")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        return widget

    def _create_chart_tab(self) -> QWidget:
        """创建趋势图表标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "基于历史数据统计的各号码累积出现概率变化曲线，反映号码的长期趋势特征")
        info.setObjectName("infoLabel")
        layout.addWidget(info)

        # 红球图表
        self.red_chart = TrendChartCanvas()
        layout.addWidget(self.red_chart, stretch=3)

        # 蓝球图表
        self.blue_chart = BlueChartCanvas()
        layout.addWidget(self.blue_chart, stretch=2)

        return widget

    def _create_query_tab(self) -> QWidget:
        """创建往期查询标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 查询输入区域
        query_bar = QHBoxLayout()
        query_bar.addWidget(QLabel("输入期号:"))

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("如: 2026078")
        self.query_input.setFixedWidth(150)
        self.query_input.returnPressed.connect(self._on_query)
        query_bar.addWidget(self.query_input)

        self.btn_query = QPushButton("🔍 查询")
        self.btn_query.setObjectName("queryBtn")
        self.btn_query.clicked.connect(self._on_query)
        query_bar.addWidget(self.btn_query)

        query_bar.addSpacing(20)
        query_bar.addWidget(QLabel("或选择年份:"))

        self.year_combo = QComboBox()
        current_year = datetime.now().year
        for y in range(2020, current_year + 1):
            self.year_combo.addItem(str(y), y)
        self.year_combo.setCurrentText(str(current_year))
        query_bar.addWidget(self.year_combo)

        self.btn_year_query = QPushButton("查看该年数据")
        self.btn_year_query.clicked.connect(self._on_year_query)
        query_bar.addWidget(self.btn_year_query)

        query_bar.addStretch()
        layout.addLayout(query_bar)

        # 查询结果表格
        self.query_table = QTableWidget()
        self.query_table.setColumnCount(9)
        self.query_table.setHorizontalHeaderLabels(
            ["期号", "日期", "红1", "红2", "红3", "红4", "红5", "红6", "蓝球"]
        )
        self.query_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.query_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.query_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.query_table.verticalHeader().setVisible(False)
        self.query_table.setAlternatingRowColors(True)
        self.query_table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(self.query_table, stretch=1)

        # 结果统计
        self.lbl_query_stats = QLabel("")
        self.lbl_query_stats.setObjectName("infoLabel")
        layout.addWidget(self.lbl_query_stats)

        return widget

    def _setup_statusbar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status = QLabel("就绪")
        self.status_bar.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    # ----------------------------------------------------------
    # 数据加载
    # ----------------------------------------------------------
    def _safe_stop_thread(self, thread):
        """安全停止后台线程"""
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(3000)

    def _start_fetch_thread(self):
        """启动数据获取线程（确保同一时间只有一个）"""
        if hasattr(self, 'fetch_thread'):
            self._safe_stop_thread(self.fetch_thread)
        self.fetch_thread = DataFetchThread()
        self.fetch_thread.progress.connect(self.set_status)
        self.fetch_thread.data_ready.connect(self._on_data_loaded)
        self.fetch_thread.error.connect(self._on_data_error)
        self.fetch_thread.start()

    def _start_prediction(self):
        """启动预测线程（确保同一时间只有一个）"""
        if hasattr(self, 'pred_thread'):
            self._safe_stop_thread(self.pred_thread)
        self.pred_thread = PredictionThread()
        self.pred_thread.progress.connect(self.set_status)
        self.pred_thread.data_ready.connect(self._on_predictions_ready)
        self.pred_thread.start()

    def _auto_load_data(self):
        """启动时自动加载数据"""
        self.set_status("正在初始化...")
        self.btn_refresh.setEnabled(False)

        # 确保数据库已初始化
        try:
            create_database()
            stats = get_statistics()
            if stats['total_records'] < 10:
                import_from_json()
        except Exception as e:
            print(f"[WARN] 数据库初始化: {e}")

        # 加载历史数据用于图表
        try:
            self.history_data = get_all_results()
        except Exception:
            self.history_data = []

        # 后台获取最新开奖数据
        self._start_fetch_thread()

    def _on_data_loaded(self, data: Dict):
        """数据加载完成"""
        self.latest_draw = data
        self._update_issue_panel(data)
        self._update_overview_tab(data)
        self.btn_refresh.setEnabled(True)
        self.set_status(f"数据加载完成 - {data['issue']}期")

        # 更新图表
        self.red_chart.update_chart(self.history_data)
        self.blue_chart.update_chart(self.history_data)

        # 后台生成预测
        if not self.predictions:
            self._start_prediction()

    def _on_data_error(self, msg: str):
        """数据加载失败"""
        self.btn_refresh.setEnabled(True)
        self.set_status(f"⚠️ {msg}")
        QMessageBox.warning(self, "数据加载失败",
                            f"{msg}\n\n将尝试使用本地数据库数据。")

        # 使用本地数据库
        try:
            latest = get_latest_issue()
            if latest:
                reds = [latest[f'red_{i}'] for i in range(1, 7)]
                local_data = {
                    "issue": latest['issue_number'],
                    "date": latest['draw_date'],
                    "weekday": "",
                    "time": "21:15",
                    "reds": reds,
                    "blue": latest['blue'],
                    "sales": 0,
                    "pool": 0,
                    "prize_grades": [],
                    "province_winners": [],
                    "province_raw": "",
                }
                self._on_data_loaded(local_data)
                return
        except Exception:
            logger.exception("本地数据加载失败")

        self.lbl_issue.setText("暂无数据")
        self.lbl_date.setText("请检查网络连接后点击刷新")

        # 仍然更新图表
        if self.history_data:
            self.red_chart.update_chart(self.history_data)
            self.blue_chart.update_chart(self.history_data)

        # 仍然尝试预测
        self._start_prediction()

    def _on_predictions_ready(self, preds: List[Dict]):
        """预测结果就绪"""
        self.predictions = preds
        self._update_prediction_tab(preds)
        self.set_status(f"预测完成 - 共{len(preds)}组号码")

    # ----------------------------------------------------------
    # UI 更新
    # ----------------------------------------------------------
    def _update_issue_panel(self, data: Dict):
        """更新本期开奖信息面板"""
        issue = data.get("issue", "未知")
        self.lbl_issue.setText(f"第{issue}期")

        date = data.get("date", "")
        weekday = data.get("weekday", "")
        time_str = data.get("time", "21:15")
        weekday_map = {"一": "周一", "二": "周二", "三": "周三",
                       "四": "周四", "五": "周五", "六": "周六", "日": "周日"}
        wd = weekday_map.get(weekday, weekday)
        self.lbl_date.setText(f"📅 {date} {wd} ⏰ {time_str}")

        # 更新号码球
        reds = data.get("reds", [])
        blue = data.get("blue", 0)
        self._update_balls(reds, blue)

        # 奖池与销售额
        pool = data.get("pool", 0)
        sales = data.get("sales", 0)
        self.lbl_pool.setText(f"💰 奖池金额: {format_money(pool)}")
        self.lbl_sales.setText(f"🛒 本期全国销售金额: {format_money(sales)}")

        # 一等奖分布摘要
        province_raw = data.get("province_raw", "")
        if province_raw:
            self.lbl_first_prize.setText(f"🏆 一等奖分布: {province_raw}")
        else:
            provinces = data.get("province_winners", [])
            if provinces:
                text = "🏆 一等奖分布: " + "、".join(
                    f"{p['province']}{p['count']}注" for p in provinces[:8]
                )
                self.lbl_first_prize.setText(text)
            else:
                self.lbl_first_prize.setText("一等奖分布: 暂无数据")

    def _update_balls(self, reds: List[int], blue: int):
        """更新号码球显示"""
        layout = self.balls_display.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for r in reds:
            ball = BallWidget(r, "red", 34)
            layout.addWidget(ball)

        plus = QLabel("+")
        plus.setFont(QFont("Arial", 16, QFont.Bold))
        plus.setStyleSheet("color: #999;")
        layout.addWidget(plus)

        if blue > 0:
            ball = BallWidget(blue, "blue", 34)
            layout.addWidget(ball)

        layout.addStretch()

    def _update_overview_tab(self, data: Dict):
        """更新奖级明细与一等奖分布表格"""
        # 奖级明细
        grades = data.get("prize_grades", [])
        # 如果没有在线奖级数据，生成本地默认奖级结构
        if not grades:
            grades = [
                {"level": lv, "name": PRIZE_NAMES[lv], "condition": PRIZE_CONDITIONS[lv],
                 "winners": 0, "prize_per": 0}
                for lv in range(1, 7)
            ]
        # 清除之前的 span 和占位内容
        self.prize_table.clearSpans()
        self.prize_table.setRowCount(len(grades))
        for i, g in enumerate(grades):
            self.prize_table.setItem(i, 0, QTableWidgetItem(g['name']))
            self.prize_table.setItem(i, 1, QTableWidgetItem(g['condition']))

            winners = int(g.get('winners', 0))
            winners_item = QTableWidgetItem(
                f"{winners:,}注" if winners > 0 else "0注")
            winners_item.setTextAlignment(Qt.AlignCenter)
            self.prize_table.setItem(i, 2, winners_item)

            prize = int(g.get('prize_per', 0))
            prize_item = QTableWidgetItem(format_money(prize))
            prize_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.prize_table.setItem(i, 3, prize_item)

            total = prize * winners
            total_item = QTableWidgetItem(format_money(total))
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.prize_table.setItem(i, 4, total_item)

            # 一等奖行高亮
            if g['level'] == 1:
                for col in range(5):
                    item = self.prize_table.item(i, col)
                    if item:
                        item.setBackground(QColor("#FFF3CD"))

        # 一等奖地区分布
        provinces = data.get("province_winners", [])
        # 获取一等奖单注奖金
        first_prize_amount = 0
        for g in data.get("prize_grades", []):
            if g.get("level") == 1:
                first_prize_amount = g.get("prize_per", 0)
                break

        # 清除之前的 span 和占位内容
        self.province_table.clearSpans()
        self.province_table.setRowCount(max(len(provinces), 1))
        if not provinces:
            no_data = QTableWidgetItem("暂无数据")
            no_data.setTextAlignment(Qt.AlignCenter)
            no_data.setForeground(QColor("#999"))
            self.province_table.setSpan(0, 0, 1, 4)
            self.province_table.setItem(0, 0, no_data)
            return

        for i, p in enumerate(provinces):
            prov_item = QTableWidgetItem(p['province'])
            prov_item.setTextAlignment(Qt.AlignCenter)
            self.province_table.setItem(i, 0, prov_item)

            cnt_item = QTableWidgetItem(f"{p['count']}注")
            cnt_item.setTextAlignment(Qt.AlignCenter)
            cnt_item.setForeground(QColor(PRIMARY_COLOR))
            font = QFont()
            font.setBold(True)
            cnt_item.setFont(font)
            self.province_table.setItem(i, 1, cnt_item)

            # 单注奖金
            amt_item = QTableWidgetItem(format_money(first_prize_amount))
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt_item.setForeground(QColor("#E67E22"))
            self.province_table.setItem(i, 2, amt_item)

            # 销售地址（需从详情页抓取，此处显示提示）
            addr_item = QTableWidgetItem("详情页查询")
            addr_item.setTextAlignment(Qt.AlignCenter)
            addr_item.setForeground(QColor("#999"))
            self.province_table.setItem(i, 3, addr_item)

    def _update_prediction_tab(self, preds: List[Dict]):
        """更新预测号码表"""
        self.pred_table.setRowCount(len(preds))
        for i, p in enumerate(preds):
            # 序号
            idx_item = QTableWidgetItem(str(p['index']))
            idx_item.setTextAlignment(Qt.AlignCenter)
            self.pred_table.setItem(i, 0, idx_item)

            # 红球
            reds = p.get('reds', [])
            for j, r in enumerate(reds):
                container = QWidget()
                hbox = QHBoxLayout(container)
                hbox.setContentsMargins(2, 2, 2, 2)
                hbox.setAlignment(Qt.AlignCenter)
                ball = MiniBallWidget(r, "red")
                hbox.addWidget(ball)
                self.pred_table.setCellWidget(i, j + 1, container)

            # 蓝球
            blue_container = QWidget()
            hbox = QHBoxLayout(blue_container)
            hbox.setContentsMargins(2, 2, 2, 2)
            hbox.setAlignment(Qt.AlignCenter)
            blue_ball = MiniBallWidget(p.get('blue', 0), "blue")
            hbox.addWidget(blue_ball)
            self.pred_table.setCellWidget(i, 7, blue_container)

            # 评分
            score = p.get('score', 0)
            score_item = QTableWidgetItem(str(round(float(score), 1)))
            score_item.setTextAlignment(Qt.AlignCenter)
            if score >= 85:
                score_item.setForeground(QColor("#27AE60"))
            elif score >= 70:
                score_item.setForeground(QColor("#E67E22"))
            else:
                score_item.setForeground(QColor("#999"))
            font = QFont()
            font.setBold(True)
            score_item.setFont(font)
            self.pred_table.setItem(i, 8, score_item)

    # ----------------------------------------------------------
    # 事件处理
    # ----------------------------------------------------------
    def _on_refresh(self):
        """刷新按钮点击"""
        self.btn_refresh.setEnabled(False)
        self.set_status("正在刷新数据...")

        # 重新加载数据库
        try:
            self.history_data = get_all_results()
        except Exception:
            logger.exception("历史数据加载失败")

        self._start_fetch_thread()

    def _on_query(self):
        """往期查询"""
        issue = self.query_input.text().strip()
        if not issue:
            QMessageBox.information(self, "提示",
                                    "请输入要查询的期号，如: 2026078")
            return

        self._query_issue(issue)

    def _on_year_query(self):
        """按年份查询"""
        year = self.year_combo.currentData()
        results = get_all_results(years=[year])

        self._populate_query_table(results)
        self.lbl_query_stats.setText(
            f"📊 {year}年共 {len(results)} 期开奖记录")

    def _query_issue(self, issue: str):
        """查询指定期号（在线查询放入后台线程，避免阻塞 UI）"""
        self.set_status(f"正在查询 {issue} 期...")
        self.query_input.setEnabled(False)
        self.btn_query.setEnabled(False)

        if hasattr(self, 'query_thread'):
            self._safe_stop_thread(self.query_thread)
        self.query_thread = IssueQueryThread(issue)
        self.query_thread.query_done.connect(self._on_issue_query_done)
        self.query_thread.start()

    def _on_issue_query_done(self, issue: str, online_data):
        """后台查询完成回调"""
        self.query_input.setEnabled(True)
        self.btn_query.setEnabled(True)

        # 在线查到，直接展示
        if online_data:
            self._update_issue_panel(online_data)
            self._update_overview_tab(online_data)
            self.tabs.setCurrentIndex(0)
            self.set_status(f"✅ 已查询 {issue} 期（在线数据）")
            return

        # 在线没有，查本地数据库
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM lottery_results WHERE issue_number = ?", (issue,))
        row = cursor.fetchone()
        conn.close()

        if row:
            row_dict = dict(row)
            reds = [row_dict[f'red_{i}'] for i in range(1, 7)]
            data = {
                "issue": row_dict['issue_number'],
                "date": row_dict['draw_date'],
                "weekday": "",
                "time": "21:15",
                "reds": reds,
                "blue": row_dict['blue'],
                "sales": 0,
                "pool": 0,
                "prize_grades": [],
                "province_winners": [],
                "province_raw": "",
            }
            self._update_issue_panel(data)
            self._update_overview_tab(data)
            self.tabs.setCurrentIndex(0)
            self.set_status(f"✅ 已查询 {issue} 期（本地数据）")
        else:
            QMessageBox.information(self, "查询结果",
                                    f"未找到期号 {issue} 的数据\n\n"
                                    f"请确认期号是否正确（格式: YYYYNNN）")
            self.set_status(f"❌ 未找到 {issue} 期")

    def _populate_query_table(self, results: List[Dict]):
        """填充查询结果表格"""
        self.query_table.setRowCount(len(results))
        for i, row in enumerate(results):
            self.query_table.setItem(
                i, 0, QTableWidgetItem(row.get('issue_number', '')))
            self.query_table.setItem(
                i, 1, QTableWidgetItem(row.get('draw_date', '')))

            for j in range(1, 7):
                val = row.get(f'red_{j}', 0)
                item = QTableWidgetItem(f"{val:02d}")
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(QColor("#DC143C"))
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                self.query_table.setItem(i, j + 1, item)

            blue_val = row.get('blue', 0)
            blue_item = QTableWidgetItem(f"{blue_val:02d}")
            blue_item.setTextAlignment(Qt.AlignCenter)
            blue_item.setForeground(QColor("#4169E1"))
            font = QFont()
            font.setBold(True)
            blue_item.setFont(font)
            self.query_table.setItem(i, 8, blue_item)

    # ----------------------------------------------------------
    # 辅助
    # ----------------------------------------------------------
    def set_status(self, msg: str):
        self.lbl_status.setText(msg)


# ============================================================
# 程序入口
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("双色球预测系统")

    # 设置应用字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
