# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 主窗口 GUI"""
import sys
import os
import logging
import subprocess
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QTextEdit, QPlainTextEdit, QComboBox, QProgressBar, QGroupBox, QFormLayout,
    QCheckBox, QSpinBox, QMessageBox, QFileDialog, QSplitter,
    QStatusBar, QHeaderView, QToolBar, QRadioButton, QGridLayout,
    QFrame, QSizePolicy, QDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPalette, QBrush

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ 工作线程 ============
class ScanThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, scanner, target, ports, scan_type):
        super().__init__()
        self.scanner = scanner
        self.target = target
        self.ports = ports
        self.scan_type = scan_type

    def run(self):
        try:
            self.progress.emit(f"开始扫描: {self.target}")
            result = self.scanner.scan_target(self.target, self.ports, self.scan_type)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AIAuditThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, analyzer, target, analysis_type):
        super().__init__()
        self.analyzer = analyzer
        self.target = target
        self.analysis_type = analysis_type

    def run(self):
        try:
            self.progress.emit("正在进行AI代码安全分析...")
            result = self.analyzer.scan_directory(self.target)
            analysis = self.analyzer.generate_report(result)
            self.finished.emit(analysis)
        except Exception as e:
            self.error.emit(str(e))


class ThreatIntelThread(QThread):
    """威胁情报收集线程（旧版，保留兼容）"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, collector, days=7):
        super().__init__()
        self.collector = collector
        self.days = days

    def run(self):
        try:
            self.progress.emit("正在从NVD获取最新CVE数据...")
            cves = self.collector.fetch_recent_cve(days=self.days)
            self.progress.emit(f"获取到{len(cves)}条CVE，正在同步到数据库...")
            count = self.collector.sync_to_database(cves)
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class IntelCollectThread(QThread):
    """全球威胁情报收集线程（新版-多源）"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, collector, days=7, mode='recent'):
        super().__init__()
        self.collector = collector
        self.days = days
        self.mode = mode

    def run(self):
        try:
            def callback(msg):
                self.progress.emit(msg)
            self.collector.set_progress_callback(callback)
            results = self.collector.collect_all_intel(days=self.days, mode=self.mode)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class AssetDiscoveryThread(QThread):
    """资产发现线程 - 支持ICMP Ping / Nmap / TCP多种方式"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, scanner, target_range):
        super().__init__()
        self.scanner = scanner
        self.target_range = target_range
        self._running = True

    def run(self):
        try:
            def callback(msg):
                if self._running:
                    self.progress.emit(msg)

            self.scanner._cancel = False
            hosts = self.scanner.discover_assets(self.target_range, method='auto', callback=callback)
            self.finished.emit(hosts)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False
        self.scanner.cancel()


# ============ 主窗口 ============
def _get_logo_path():
    """获取LOGO文件路径（优先级: jpg > png）"""
    for ext in ['.jpg', '.png']:
        path = os.path.join(PROJECT_DIR, 'assets', f'logo{ext}')
        if os.path.exists(path):
            return path
    return ''


def _make_white_transparent(pixmap, tolerance=40):
    """将QPixmap中的白色转为透明（保留其他颜色）"""
    from PyQt5.QtGui import QImage
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.red() > 255 - tolerance and color.green() > 255 - tolerance and color.blue() > 255 - tolerance:
                image.setPixelColor(x, y, QColor(255, 255, 255, 0))
    return QPixmap.fromImage(image)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 线程安全消息缓冲（避免跨线程 QTextCursor 错误）
        self._msg_buffer = []
        self._msg_lock = __import__('threading').Lock()
        self._init_components()
        self._init_ui()
        self._update_status_bar()
        self._update_dashboard()

        # 启动消息刷新定时器（每100ms刷新一次）
        self._msg_timer = QTimer()
        self._msg_timer.timeout.connect(self._flush_messages)
        self._msg_timer.start(100)

        logger.info("AI漏洞扫描系统主窗口初始化完成")

    def _flush_messages(self):
        """刷新缓冲消息到日志控件"""
        if not self._msg_buffer:
            return
        with self._msg_lock:
            msgs = self._msg_buffer[:]
            self._msg_buffer.clear()
        cleared = set()
        for target, text in msgs:
            try:
                widget = getattr(self, target)
                if text == '__CLEAR__':
                    if target not in cleared:
                        widget.clear()
                        cleared.add(target)
                else:
                    widget.appendPlainText(text)
            except:
                pass

    def _safe_log(self, target: str, text: str):
        """线程安全的日志写入"""
        with self._msg_lock:
            self._msg_buffer.append((target, text))

    def _safe_clear(self, target: str):
        """线程安全的清空日志"""
        with self._msg_lock:
            self._msg_buffer.append((target, '__CLEAR__'))

    def _init_components(self):
        """初始化核心组件"""
        from database import Database
        from scanner_engine import NetworkScanner
        from ai_analyzer import AIAnalyzer
        from threat_intel import ThreatIntelCollector, VulnMatcher

        self.db = Database()
        self.scanner = NetworkScanner(self.db)
        self.ai_analyzer = AIAnalyzer()
        self.threat_intel = ThreatIntelCollector(self.db)
        self.vuln_matcher = VulnMatcher(self.db)

        self.scanner.set_progress_callback(self._on_scan_progress_msg)
        self.threat_intel.set_progress_callback(self._on_intel_progress_msg)

        self.current_scan_thread = None
        self.current_audit_thread = None
        self.current_intel_thread = None
        self.last_scan_result = None
        self.last_audit_result = None
        self.audit_history = self.db.get_audit_history(50)
        self._discover_running = False
        self.discover_thread = None

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle('下一代智能漏洞扫描系统 Pro v1.0 - 山西有信网安科技有限公司')
        self.setGeometry(100, 50, 1500, 850)

        # 设置应用样式
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QGroupBox { font-weight: bold; font-size: 18px; border: 1px solid #d0d5dd; border-radius: 6px; margin-top: 10px; padding-top: 20px; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px; color: #1a73e8; }
            QPushButton { background-color: #1a73e8; color: white; border: none; padding: 10px 24px; border-radius: 4px; font-weight: bold; font-size: 18px; }
            QPushButton:hover { background-color: #1557b0; }
            QPushButton:disabled { background-color: #c0c0c0; }
            QPushButton#stopBtn { background-color: #e53935; }
            QPushButton#stopBtn:hover { background-color: #c62828; }
            QPushButton#saveBtn { background-color: #43a047; }
            QPushButton#saveBtn:hover { background-color: #2e7d32; }
            QTableWidget { font-size: 16px; border: 1px solid #d0d5dd; border-radius: 4px; gridline-color: #e8e8e8; }
            QTableWidget::item { padding: 5px; }
            QHeaderView::section { background-color: #1a73e8; color: white; padding: 8px; border: none; font-weight: bold; font-size: 16px; }
            QLineEdit, QTextEdit, QComboBox, QSpinBox { font-size: 16px; border: 1px solid #d0d5dd; border-radius: 4px; padding: 6px; }
            QLineEdit:focus { border-color: #1a73e8; }
            QProgressBar { font-size: 16px; border: 1px solid #d0d5dd; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background-color: #1a73e8; border-radius: 3px; }
            QTabWidget::pane { border: 1px solid #d0d5dd; border-radius: 4px; background: white; }
            QTabBar::tab { font-size: 18px; background: #e8eaf6; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: white; border-bottom: 3px solid #1a73e8; }
            QLabel { font-size: 16px; }
        """)

        self._create_menu_bar()
        self._create_toolbar()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._create_dashboard_tab()
        self._create_asset_tab()
        self._create_scan_tab()
        self._create_vulndb_tab()
        self._create_audit_tab()
        self._create_intel_tab()
        self._create_reports_tab()
        self._create_settings_tab()

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_dashboard)
        self.update_timer.start(60000)

        # 每日自动更新CVE漏洞库 (24小时)
        self.cve_auto_update_timer = QTimer()
        self.cve_auto_update_timer.timeout.connect(self._auto_update_cve)
        self.cve_auto_update_timer.start(86400000)

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu('文件(&F)')
        save_action = file_menu.addAction('保存报告(&S)')
        save_action.triggered.connect(self._save_report)
        open_action = file_menu.addAction('打开报告(&O)')
        open_action.triggered.connect(self._open_report)
        file_menu.addSeparator()
        export_action = file_menu.addAction('导出报告(&E)')
        export_action.triggered.connect(self._export_report)
        file_menu.addSeparator()
        exit_action = file_menu.addAction('退出(&X)')
        exit_action.triggered.connect(self.close)

        scan_menu = menubar.addMenu('扫描(&S)')
        scan_menu.addAction('快速扫描').triggered.connect(lambda: self._start_scan('quick'))
        scan_menu.addAction('完整扫描').triggered.connect(lambda: self._start_scan('full'))

        tool_menu = menubar.addMenu('工具(&T)')
        tool_menu.addAction('更新CVE数据库').triggered.connect(self._update_cve_db)
        tool_menu.addAction('清空数据库').triggered.connect(self._clear_database)

        help_menu = menubar.addMenu('帮助(&H)')
        help_menu.addAction('关于(&A)').triggered.connect(self._show_about)

    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(72, 72))
        toolbar.setMinimumHeight(90)
        toolbar.setStyleSheet('QToolBar { spacing: 8px; padding: 4px 8px; }')
        self.addToolBar(toolbar)

        logo_path = _get_logo_path()
        if logo_path:
            logo_label = QLabel()
            pixmap = QPixmap(logo_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = _make_white_transparent(pixmap)
            logo_label.setPixmap(pixmap)
            logo_label.setStyleSheet('background: transparent;')
            toolbar.addWidget(logo_label)

        title_label = QLabel('  <span style=\"font-size:33px; vertical-align:top;\">&copy;</span>2026 山西有信网安科技有限公司  ')
        title_label.setTextFormat(Qt.RichText)
        title_label.setStyleSheet('font-weight: bold; font-size: 22px; color: #1a73e8;')
        toolbar.addWidget(title_label)
        toolbar.addSeparator()

        btn_style = 'padding: 12px 24px; font-size: 18px;'
        quick_btn = QPushButton('快速扫描')
        quick_btn.setStyleSheet(btn_style)
        quick_btn.clicked.connect(lambda: self._start_scan('quick'))
        toolbar.addWidget(quick_btn)

        full_btn = QPushButton('完整扫描')
        full_btn.setStyleSheet(btn_style)
        full_btn.clicked.connect(lambda: self._start_scan('full'))
        toolbar.addWidget(full_btn)
        toolbar.addSeparator()

        refresh_btn = QPushButton('刷新')
        refresh_btn.setStyleSheet(btn_style)
        refresh_btn.clicked.connect(self._refresh_all)
        toolbar.addWidget(refresh_btn)

    def _create_header_widget(self, title: str, subtitle: str = '') -> QWidget:
        """创建标准页头"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 10)
        title_label = QLabel(f'<h2 style="color:#1a73e8;margin:0;">{title}</h2>')
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(f'<span style="color:#666;font-size:18px;">{subtitle}</span>')
            layout.addWidget(subtitle_label)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet('background-color: #e0e0e0; max-height: 1px;')
        layout.addWidget(line)
        return w

    # ============ 仪表盘 ============
    def _create_dashboard_tab(self):
        """创建仪表盘"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(self._create_header_widget('系统仪表盘', 'AI漏洞扫描系统运行概览'))

        # 统计卡片
        cards_layout = QGridLayout()
        self.stat_cards = {}
        card_data = [
            ('recent_tasks', '今日扫描工作', '0', '#1976d2'),
            ('total_vulns', '漏洞发现', '0', '#f5576c'),
            ('audit_issues', 'AI审计发现', '0', '#8e24aa'),
            ('intel_today', '今日威胁情报', '0', '#00897b'),
            ('total_tasks', '扫描任务', '0', '#43a047'),
            ('critical_count', '高危/严重漏洞', '0', '#d32f2f'),
            ('total_assets', '资产总数', '0', '#667eea'),
            ('total_cves', 'CVE漏洞库', '0', '#ff6f00'),
        ]

        for i, (key, label, value, color) in enumerate(card_data):
            card = QFrame()
            card.setStyleSheet(f'background: {color}; border-radius: 10px; padding: 15px;')
            card.setMinimumSize(200, 80)
            cl = QVBoxLayout(card)
            num_label = QLabel(value)
            num_label.setStyleSheet('color: white; font-size: 32px; font-weight: bold;')
            text_label = QLabel(label)
            text_label.setStyleSheet('color: rgba(255,255,255,0.9); font-size: 18px;')
            cl.addWidget(num_label)
            cl.addWidget(text_label)
            cards_layout.addWidget(card, i // 4, i % 4)
            self.stat_cards[key] = num_label

        layout.addLayout(cards_layout)

        # 最近扫描任务和AI审计任务（可调节分割）
        task_splitter = QSplitter(Qt.Vertical)
        task_splitter.setChildrenCollapsible(False)

        scan_task_widget = QWidget()
        scan_task_layout = QVBoxLayout(scan_task_widget)
        scan_task_layout.setContentsMargins(0, 0, 0, 0)
        scan_task_layout.addWidget(QLabel('<b style="color:#333;">最近扫描任务</b>'))
        self.dash_task_table = QTableWidget()
        self.dash_task_table.setColumnCount(5)
        self.dash_task_table.setHorizontalHeaderLabels(['ID', '目标', '类型', '状态', '时间'])
        self.dash_task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        scan_task_layout.addWidget(self.dash_task_table)
        task_splitter.addWidget(scan_task_widget)

        audit_task_widget = QWidget()
        audit_task_layout = QVBoxLayout(audit_task_widget)
        audit_task_layout.setContentsMargins(0, 0, 0, 0)
        audit_task_layout.addWidget(QLabel('<b style="color:#333;">最近AI代码审计任务</b>'))
        self.dash_audit_table = QTableWidget()
        self.dash_audit_table.setColumnCount(5)
        self.dash_audit_table.setHorizontalHeaderLabels(['审计目标', '扫描文件数', '发现问题数', '风险等级', '审计时间'])
        self.dash_audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        audit_task_layout.addWidget(self.dash_audit_table)
        task_splitter.addWidget(audit_task_widget)

        asset_task_widget = QWidget()
        asset_task_layout = QVBoxLayout(asset_task_widget)
        asset_task_layout.setContentsMargins(0, 0, 0, 0)
        asset_task_layout.addWidget(QLabel('<b style="color:#333;">最近资产列表</b>'))
        self.dash_asset_table = QTableWidget()
        self.dash_asset_table.setColumnCount(5)
        self.dash_asset_table.setHorizontalHeaderLabels(['名称', 'IP地址', 'MAC地址', '类型', '状态'])
        self.dash_asset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        asset_task_layout.addWidget(self.dash_asset_table)
        task_splitter.addWidget(asset_task_widget)

        task_splitter.setSizes([400, 400, 400])
        layout.addWidget(task_splitter)

        layout.addStretch()
        self.tabs.addTab(widget, '仪表盘')

    def _on_tab_changed(self, index):
        """切换标签页时自动刷新对应模块数据"""
        if index == 0:  # 仪表盘
            self._update_dashboard()
            self._update_status_bar()
        elif index == 1:  # 资产管理
            self._search_assets()

    def _refresh_all(self):
        """刷新仪表盘和报告数据"""
        self._update_dashboard()
        self._update_status_bar()
        if hasattr(self, 'report_table'):
            self._refresh_reports()
        self.status_bar.showMessage('数据已刷新 | 山西有信网安科技有限公司', 3000)

    def _update_dashboard(self):
        """更新仪表盘数据"""
        try:
            stats = self.db.get_statistics()
            self.stat_cards['total_assets'].setText(str(stats['total_assets']))
            self.stat_cards['total_vulns'].setText(str(stats['total_vulns']))
            self.stat_cards['total_tasks'].setText(str(stats['total_tasks']))
            self.stat_cards['total_cves'].setText(str(stats['total_cves']))
            self.stat_cards['critical_count'].setText(str(stats['critical_count']))

            today_str = datetime.now().strftime('%Y-%m-%d')
            today_count = self.db.scan.conn.execute(
                "SELECT COUNT(*) FROM scan_tasks WHERE start_time LIKE ?",
                (today_str + '%',)
            ).fetchone()[0]
            self.stat_cards['recent_tasks'].setText(str(today_count))

            tasks = self.db.get_all_tasks(100)

            self.dash_task_table.setRowCount(0)
            for task in tasks:
                row = self.dash_task_table.rowCount()
                self.dash_task_table.insertRow(row)
                self.dash_task_table.setItem(row, 0, QTableWidgetItem(str(task.get('id', ''))))
                self.dash_task_table.setItem(row, 1, QTableWidgetItem(task.get('target', '')))
                scan_type = task.get('scan_type', '')
                type_text = '快速扫描' if scan_type == 'quick' else '完整扫描' if scan_type == 'full' else '自定义扫描' if scan_type == 'custom' else scan_type
                self.dash_task_table.setItem(row, 2, QTableWidgetItem(type_text))
                status = task.get('status', '')
                status_text = '运行中' if status == 'running' else '已完成' if status == 'completed' else '失败' if status == 'failed' else status
                self.dash_task_table.setItem(row, 3, QTableWidgetItem(status_text))
                self.dash_task_table.setItem(row, 4, QTableWidgetItem(task.get('start_time', '')[:19] if task.get('start_time') else ''))

            # AI审计统计
            total_issues = sum(a.get('total_vulnerabilities', 0) for a in self.audit_history)
            self.stat_cards['audit_issues'].setText(str(total_issues))

            self.dash_audit_table.setRowCount(0)
            for audit in self.audit_history[:100]:
                row = self.dash_audit_table.rowCount()
                self.dash_audit_table.insertRow(row)
                target = audit.get('target', '') or '未知路径'
                if len(target) > 50:
                    target = '...' + target[-47:]
                self.dash_audit_table.setItem(row, 0, QTableWidgetItem(target))
                self.dash_audit_table.setItem(row, 1, QTableWidgetItem(str(audit.get('total_files_scanned', 0))))
                self.dash_audit_table.setItem(row, 2, QTableWidgetItem(str(audit.get('total_vulnerabilities', 0))))
                self.dash_audit_table.setItem(row, 3, QTableWidgetItem(audit.get('risk_level', '未知')))
                self.dash_audit_table.setItem(row, 4, QTableWidgetItem(audit.get('generated_at', '')))

            # 今日情报更新统计
            cve_updated_today = self.db.cve.get_today_updated_count()
            self.stat_cards['intel_today'].setText(str(cve_updated_today))

            # 最近资产列表
            assets = self.db.get_assets(limit=20)
            self.dash_asset_table.setRowCount(0)
            for asset in assets:
                row = self.dash_asset_table.rowCount()
                self.dash_asset_table.insertRow(row)
                self.dash_asset_table.setItem(row, 0, QTableWidgetItem(asset.get('name', '')))
                self.dash_asset_table.setItem(row, 1, QTableWidgetItem(asset.get('ip', '')))
                self.dash_asset_table.setItem(row, 2, QTableWidgetItem(asset.get('mac', 'N/A')))
                self.dash_asset_table.setItem(row, 3, QTableWidgetItem(asset.get('type', '')))
                self.dash_asset_table.setItem(row, 4, QTableWidgetItem(asset.get('status', '')))
        except Exception as e:
            logger.error(f"更新仪表盘失败: {e}")

    # ============ 资产管理 ============
    def _create_asset_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('资产管理', '管理网络资产信息'))

        # 工具栏
        toolbar = QHBoxLayout()
        self.asset_search = QLineEdit()
        self.asset_search.setPlaceholderText('搜索资产 (名称/IP)...')
        self.asset_search.setMaximumWidth(300)
        toolbar.addWidget(self.asset_search)
        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self._search_assets)
        toolbar.addWidget(search_btn)

        self.asset_type_filter = QComboBox()
        self.asset_type_filter.addItems(['全部类型', 'SERVER', 'DATABASE', 'WEB_APP', 'NETWORK_DEVICE', 'IOT_DEVICE'])
        toolbar.addWidget(QLabel('类型:'))
        toolbar.addWidget(self.asset_type_filter)

        add_btn = QPushButton('+ 添加资产')
        add_btn.clicked.connect(self._add_asset_dialog)
        toolbar.addWidget(add_btn)
        self.discover_btn = QPushButton('自动发现资产')
        self.discover_btn.setObjectName('saveBtn')
        self.discover_btn.clicked.connect(self._auto_discover_assets)
        toolbar.addWidget(self.discover_btn)

        self.discover_stop_btn = QPushButton('停止扫描资产')
        self.discover_stop_btn.setObjectName('stopBtn')
        self.discover_stop_btn.clicked.connect(self._stop_discover_assets)
        self.discover_stop_btn.setEnabled(False)
        toolbar.addWidget(self.discover_stop_btn)

        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self._search_assets)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(8)
        self.asset_table.setHorizontalHeaderLabels(['ID', '名称', 'IP地址', 'MAC地址', '类型', '状态', '重要性', '负责人'])
        self.asset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.asset_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.asset_table.itemClicked.connect(self._on_asset_clicked)
        self.asset_table.setMaximumHeight(600)
        layout.addWidget(self.asset_table)

        # 资产详情
        layout.addWidget(QLabel('<b style="color:#1a73e8; font-size:18px;">资产详情</b>'))
        self.asset_detail_text = QTextEdit()
        self.asset_detail_text.setReadOnly(True)
        self.asset_detail_text.setMaximumHeight(400)
        self.asset_detail_text.setStyleSheet('font-size: 18px; font-family: monospace;')
        self.asset_detail_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.asset_detail_text)

        self.tabs.addTab(widget, '资产管理')

    def _search_assets(self):
        filters = {}
        keyword = self.asset_search.text().strip()
        if keyword:
            filters['keyword'] = keyword
        asset_type = self.asset_type_filter.currentText()
        if asset_type != '全部类型':
            filters['type'] = asset_type

        assets = self.db.get_assets(filters)
        self.asset_table.setRowCount(0)
        for asset in assets:
            row = self.asset_table.rowCount()
            self.asset_table.insertRow(row)
            self.asset_table.setItem(row, 0, QTableWidgetItem(str(asset.get('id', ''))))
            self.asset_table.setItem(row, 1, QTableWidgetItem(asset.get('name', '')))
            self.asset_table.setItem(row, 2, QTableWidgetItem(asset.get('ip', '')))
            self.asset_table.setItem(row, 3, QTableWidgetItem(asset.get('mac', '')))
            self.asset_table.setItem(row, 4, QTableWidgetItem(asset.get('type', '')))
            self.asset_table.setItem(row, 5, QTableWidgetItem(asset.get('status', '')))
            importance = asset.get('importance', 'MEDIUM')
            self.asset_table.setItem(row, 6, QTableWidgetItem(importance))
            self.asset_table.setItem(row, 7, QTableWidgetItem(asset.get('owner', '')))

    def _on_asset_clicked(self, item):
        row = item.row()
        asset_id = self.asset_table.item(row, 0).text()
        asset = self.db.get_asset(int(asset_id))
        if asset:
            detail = f"""资产详情
名称: {asset.get('name', '')}
IP: {asset.get('ip', '')}
MAC: {asset.get('mac', 'N/A')}
类型: {asset.get('type', '')} | 状态: {asset.get('status', '')}
重要性: {asset.get('importance', '')}
操作系统: {asset.get('os', 'N/A')}
位置: {asset.get('location', 'N/A')}
负责人: {asset.get('owner', 'N/A')}
部门: {asset.get('department', 'N/A')}
标签: {asset.get('tags', 'N/A')}"""
            self.asset_detail_text.setText(detail)

    def _add_asset_dialog(self):
        name, ok = self._input_dialog('添加资产', '名称:')
        if not ok or not name:
            return
        ip, ok = self._input_dialog('添加资产', 'IP地址:')
        if not ok or not ip:
            return
        self.db.add_asset({'name': name, 'ip': ip, 'type': 'SERVER'})
        self._search_assets()

    def _input_dialog(self, title, label):
        from PyQt5.QtWidgets import QInputDialog
        return QInputDialog.getText(self, title, label)

    def _stop_discover_assets(self):
        """停止资产发现扫描"""
        self._discover_running = False
        if hasattr(self, 'discover_thread') and self.discover_thread:
            self.discover_thread.stop()
            self.discover_thread.terminate()
            self.discover_thread = None
        self.discover_stop_btn.setEnabled(False)
        self.discover_btn.setText('自动发现资产')
        self.discover_btn.setEnabled(True)
        self.asset_detail_text.clear()
        self.status_bar.showMessage('资产发现已停止 | 山西有信网安科技有限公司')

    def _on_discover_progress(self, msg):
        """资产发现进度"""
        if '发现主机' in msg:
            current = self.asset_detail_text.toPlainText()
            self.asset_detail_text.setText(f'{current}\n{msg}')
        else:
            self.asset_detail_text.setText(msg)

    def _on_discover_finished(self, discovered):
        """资产发现完成"""
        self._discover_running = False
        self.discover_btn.setText('自动发现资产')
        self.discover_btn.setEnabled(True)
        self.discover_stop_btn.setEnabled(False)
        self.discover_thread = None

        if discovered:
            # 去重：获取已有资产的IP集合
            existing = self.db.get_assets()
            existing_ips = set(a.get('ip', '') for a in existing)
            new_hosts = [h for h in discovered if h not in existing_ips]
            skipped = len(discovered) - len(new_hosts)

            count = 0
            for host in new_hosts:
                result = self.db.add_asset({'name': host, 'ip': host, 'type': 'SERVER', 'status': 'ACTIVE'})
                if result > 0:
                    count += 1
            self._search_assets()

            # 在资产详情框显示汇总结果
            summary = f'共发现 {len(discovered)} 个IP，已存在 {skipped} 个IP，新增加 {count} 个IP'
            self.asset_detail_text.setText(summary)

            msg = f'扫描完成！\n发现 {len(discovered)} 台主机'
            if skipped > 0:
                msg += f'\n跳过 {skipped} 个已存在资产'
            if count > 0:
                msg += f'\n新增 {count} 个资产'
            elif skipped == len(discovered):
                msg += '\n所有主机已存在，未新增资产'
            QMessageBox.information(self, '发现完成', msg)
        else:
            self.asset_detail_text.setText('未发现存活主机')
            QMessageBox.information(self, '发现完成', '未发现存活主机')
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')

    def _on_discover_error(self, error):
        """资产发现出错"""
        self._discover_running = False
        self.asset_detail_text.clear()
        self.discover_btn.setText('自动发现资产')
        self.discover_btn.setEnabled(True)
        self.discover_stop_btn.setEnabled(False)
        self.discover_thread = None
        QMessageBox.critical(self, '错误', f'资产发现失败: {error}')
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')

    def _auto_discover_assets(self):
        """自动发现网络资产"""
        from PyQt5.QtWidgets import QInputDialog

        ip_range, ok = QInputDialog.getText(self, '自动发现资产',
            '请输入IP地址范围:\n(如 192.168.1.1-254 或 192.168.1.0/24)')
        if not ok or not ip_range.strip():
            return

        ip_range = ip_range.strip()
        self.status_bar.showMessage(f'正在扫描 {ip_range} ...')

        reply = QMessageBox.question(self, '确认扫描',
            f'将对 {ip_range} 进行主机发现扫描，\n发现的主机将自动添加到资产清单。\n\n是否继续？',
            QMessageBox.Yes | QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        try:
            self.discover_btn.setText('正在扫描在线资产......')
            self.discover_btn.setEnabled(False)
            self.discover_stop_btn.setEnabled(True)

            targets = self.scanner.parse_target(ip_range)
            if not targets:
                QMessageBox.warning(self, '警告', '无法解析IP地址范围')
                return

            self.status_bar.showMessage(f'正在发现资产: {ip_range} ({len(targets)} 个目标) ...')
            self.asset_detail_text.clear()

            self._discover_running = True
            self.discover_thread = AssetDiscoveryThread(self.scanner, ip_range)
            self.discover_thread.progress.connect(self._on_discover_progress)
            self.discover_thread.finished.connect(self._on_discover_finished)
            self.discover_thread.error.connect(self._on_discover_error)
            self.discover_thread.start()

        except Exception as e:
            QMessageBox.critical(self, '错误', f'资产发现失败: {str(e)}')
            self.discover_btn.setText('自动发现资产')
            self.discover_btn.setEnabled(True)
            self.discover_stop_btn.setEnabled(False)

    # ============ 漏洞扫描 ============
    def _create_scan_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('漏洞扫描', '执行网络漏洞扫描任务'))

        config_group = QGroupBox('扫描配置')
        config_layout = QFormLayout()

        target_layout = QHBoxLayout()
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText('输入IP/域名/CIDR网段 (如 192.168.1.1 或 192.168.1.0/24)')
        target_layout.addWidget(self.target_input)
        select_asset_btn = QPushButton('从资产选择')
        select_asset_btn.clicked.connect(self._select_target_from_assets)
        target_layout.addWidget(select_asset_btn)
        config_layout.addRow('扫描目标:', target_layout)

        port_layout = QHBoxLayout()
        self.port_input = QLineEdit('21-23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017,2181,9200')
        port_layout.addWidget(self.port_input)
        config_layout.addRow('端口范围:', port_layout)

        type_layout = QHBoxLayout()
        self.scan_type_combo = QComboBox()
        self.scan_type_combo.addItems(['quick', 'full', 'custom'])
        self.scan_type_combo.currentTextChanged.connect(self._on_scan_type_changed)
        type_layout.addWidget(self.scan_type_combo)
        type_layout.addWidget(QLabel('quick=常用端口 | full=0-65535 | custom=自定义端口'))
        config_layout.addRow('扫描类型:', type_layout)

        timeout_layout = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setValue(10)
        self.timeout_spin.setSuffix(' 秒')
        timeout_layout.addWidget(self.timeout_spin)
        config_layout.addRow('超时时间:', timeout_layout)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton('开始扫描')
        self.scan_btn.clicked.connect(lambda: self._start_scan(self.scan_type_combo.currentText()))
        btn_layout.addWidget(self.scan_btn)

        self.stop_btn = QPushButton('停止扫描')
        self.stop_btn.setObjectName('stopBtn')
        self.stop_btn.clicked.connect(self._stop_scan)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.save_report_btn = QPushButton('保存报告')
        self.save_report_btn.setObjectName('saveBtn')
        self.save_report_btn.clicked.connect(self._save_report)
        self.save_report_btn.setEnabled(False)
        btn_layout.addWidget(self.save_report_btn)

        self.open_report_btn = QPushButton('打开报告')
        self.open_report_btn.clicked.connect(self._open_report)
        self.open_report_btn.setEnabled(False)
        btn_layout.addWidget(self.open_report_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        layout.addWidget(self.scan_progress)

        splitter = QSplitter(Qt.Vertical)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(9)
        self.result_table.setHorizontalHeaderLabels(['主机', '端口', '协议', '服务', '版本', 'CVE', '严重程度', 'CVSS', '描述'])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        splitter.addWidget(self.result_table)

        self.scan_log = QPlainTextEdit()
        self.scan_log.setReadOnly(True)
        self.scan_log.setMaximumHeight(200)
        splitter.addWidget(self.scan_log)

        layout.addWidget(splitter)
        self.tabs.addTab(widget, '漏洞扫描')

    def _select_target_from_assets(self):
        """从资产列表中选择扫描目标"""
        assets = self.db.get_assets()
        if not assets:
            QMessageBox.warning(self, '提示', '资产列表为空，请先在资产管理中添加资产')
            return

        dialog = QDialog(self)
        dialog.setWindowTitle('选择扫描目标')
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel('<b>从资产列表中选择扫描目标（可多选）：</b>'))

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['资产名称', 'IP地址', '类型'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        for asset in assets:
            row = table.rowCount()
            table.insertRow(row)
            item = QTableWidgetItem(asset.get('name', ''))
            item.setData(Qt.UserRole, asset)
            item.setCheckState(Qt.Unchecked)
            table.setItem(row, 0, item)
            table.setItem(row, 1, QTableWidgetItem(asset.get('ip', '')))
            table.setItem(row, 2, QTableWidgetItem(asset.get('type', '')))

        layout.addWidget(table)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('确定')
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec_() == QDialog.Accepted:
            selected = []
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.checkState() == Qt.Checked:
                    asset = item.data(Qt.UserRole)
                    selected.append(asset.get('ip', ''))
            if selected:
                self.target_input.setText(', '.join(selected))

    def _on_scan_progress_msg(self, msg):
        self._safe_log('scan_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _on_scan_type_changed(self, scan_type):
        """扫描类型切换 - 自定义模式强调端口输入"""
        if scan_type == 'custom':
            self.port_input.setStyleSheet('border: 2px solid #e53935; font-size: 16px;')
            self.port_input.setPlaceholderText('输入自定义端口范围 (如 80,443,8080 或 1-65535)')
        else:
            self.port_input.setStyleSheet('')
            if scan_type == 'quick':
                self.port_input.setText('21-23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017,2181,9200')
            elif scan_type == 'full':
                self.port_input.setText('0-65535')

    def _start_scan(self, scan_type='quick'):
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, '警告', '请输入扫描目标')
            return

        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.save_report_btn.setEnabled(False)
        self.open_report_btn.setEnabled(False)
        self.scan_progress.setVisible(True)
        self.scan_progress.setValue(0)
        self._safe_clear('scan_log')
        self.result_table.setRowCount(0)

        ports = self.port_input.text().strip() or None
        timeout = self.timeout_spin.value()
        self.scanner.timeout = timeout

        task_id = self.db.create_task(target, scan_type, {'ports': ports})

        self.current_scan_thread = ScanThread(self.scanner, target, ports, scan_type)
        self.current_scan_thread.progress.connect(self._on_scan_progress)
        self.current_scan_thread.finished.connect(lambda r: self._on_scan_finished(r, task_id))
        self.current_scan_thread.error.connect(self._on_scan_error)
        self.current_scan_thread.start()
        self._safe_log('scan_log',f'开始扫描任务: {target}')

    def _stop_scan(self):
        if self.current_scan_thread:
            self.current_scan_thread.terminate()
            self.current_scan_thread = None
        self.scanner.cancel()
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_report_btn.setEnabled(False)
        self.scan_progress.setVisible(False)
        self._safe_log('scan_log','扫描已停止')

    def _on_scan_progress(self, msg):
        self._safe_log('scan_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')
        if '已扫描' in msg and '/' in msg:
            try:
                import re
                match = re.search(r'(\d+)/(\d+)', msg)
                if match:
                    current, total = int(match.group(1)), int(match.group(2))
                    if total > 0:
                        self.scan_progress.setValue(int(current / total * 90))
            except:
                pass

    def _on_scan_finished(self, result, task_id):
        self.scan_progress.setValue(100)
        self._safe_log('scan_log','扫描完成!')

        # 漏洞匹配
        vulnerabilities = []
        for host_info in result.get('hosts', []):
            if host_info.get('status') != 'up':
                continue
            host = host_info.get('ip') or host_info.get('host', '')
            ports_data = host_info.get('ports', [])
            vulns = self.vuln_matcher.match_vulnerabilities(host, ports_data)
            vulnerabilities.extend(vulns)

        result['vulnerabilities'] = vulnerabilities
        summary = {}
        for v in vulnerabilities:
            sev = v.get('severity', 'INFO')
            summary[sev] = summary.get(sev, 0) + 1
        result['summary'] = {
            'total': len(vulnerabilities),
            'by_severity': summary,
            'high_critical': summary.get('CRITICAL', 0) + summary.get('HIGH', 0)
        }

        self.last_scan_result = result

        self.result_table.setRowCount(0)
        for vuln in vulnerabilities:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            self.result_table.setItem(row, 0, QTableWidgetItem(vuln.get('host', '')))
            self.result_table.setItem(row, 1, QTableWidgetItem(str(vuln.get('port', ''))))
            self.result_table.setItem(row, 2, QTableWidgetItem(vuln.get('protocol', 'tcp')))
            self.result_table.setItem(row, 3, QTableWidgetItem(vuln.get('service', '')))
            self.result_table.setItem(row, 4, QTableWidgetItem(vuln.get('version', '')))
            self.result_table.setItem(row, 5, QTableWidgetItem(vuln.get('cve_id', 'N/A')))
            self.result_table.setItem(row, 6, QTableWidgetItem(vuln.get('severity', 'INFO')))

            severity = vuln.get('severity', 'INFO')
            if severity in ['CRITICAL', 'HIGH']:
                for c in range(9):
                    item = self.result_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 210, 210))
            elif severity == 'MEDIUM':
                for c in range(9):
                    item = self.result_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 255, 210))

            cvss = vuln.get('cvss_score', '')
            self.result_table.setItem(row, 7, QTableWidgetItem(str(cvss) if cvss else ''))
            self.result_table.setItem(row, 8, QTableWidgetItem((vuln.get('description', '') or '')[:80]))

        for vuln in vulnerabilities:
            self.db.add_scan_result(task_id, vuln)

        vuln_count = len(vulnerabilities)
        self.db.update_task_status(task_id, 'completed', vuln_count)

        self._safe_log('scan_log',f'发现 {vuln_count} 个漏洞')
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_report_btn.setEnabled(True)
        self.open_report_btn.setEnabled(True)
        self.scan_progress.setVisible(False)

        QMessageBox.information(self, '扫描完成', f'扫描完成，发现 {vuln_count} 个安全项目')

    def _on_scan_error(self, error):
        self._safe_log('scan_log',f'错误: {error}')
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_progress.setVisible(False)
        QMessageBox.critical(self, '扫描错误', error)

    # ============ 漏洞库 ============
    def _create_vulndb_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('CVE漏洞库', '浏览和搜索CVE漏洞数据'))

        search_layout = QHBoxLayout()
        self.cve_search = QLineEdit()
        self.cve_search.setPlaceholderText('搜索CVE (如: apache, mysql, CVE-2024-...)')
        self.cve_search.setMaximumWidth(400)
        search_layout.addWidget(self.cve_search)

        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self._search_cve)
        search_layout.addWidget(search_btn)

        self.cve_severity_filter = QComboBox()
        self.cve_severity_filter.addItems(['全部', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'])
        search_layout.addWidget(QLabel('严重度:'))
        search_layout.addWidget(self.cve_severity_filter)

        search_layout.addStretch()

        update_layout = QHBoxLayout()
        update_layout.addWidget(QLabel('更新天数:'))
        self.cve_days_spin = QSpinBox()
        self.cve_days_spin.setRange(1, 90)
        self.cve_days_spin.setValue(7)
        self.cve_days_spin.setSuffix(' 天')
        update_layout.addWidget(self.cve_days_spin)

        self.cve_update_btn = QPushButton('更新漏洞库')
        self.cve_update_btn.setObjectName('saveBtn')
        self.cve_update_btn.clicked.connect(self._update_cve_db)
        update_layout.addWidget(self.cve_update_btn)

        self.cve_stop_btn = QPushButton('停止搜索')
        self.cve_stop_btn.setObjectName('stopBtn')
        self.cve_stop_btn.clicked.connect(self._stop_cve_update)
        self.cve_stop_btn.setEnabled(False)
        update_layout.addWidget(self.cve_stop_btn)

        update_layout.addStretch()
        layout.addLayout(search_layout)
        layout.addLayout(update_layout)

        self.cve_table = QTableWidget()
        self.cve_table.setColumnCount(6)
        self.cve_table.setHorizontalHeaderLabels(['CVE编号', '严重程度', 'CVSS', '描述', '发布日期', '受影响产品'])
        self.cve_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cve_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cve_table.itemClicked.connect(self._on_cve_clicked)
        layout.addWidget(self.cve_table)

        detail_group = QGroupBox('CVE详情')
        detail_layout = QVBoxLayout()
        self.cve_detail_text = QTextEdit()
        self.cve_detail_text.setReadOnly(True)
        self.cve_detail_text.setMinimumHeight(200)
        self.cve_detail_text.setStyleSheet('font-size: 18px; line-height: 1.5;')
        detail_layout.addWidget(self.cve_detail_text)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        # CVE更新进度日志
        self.cve_update_log = QPlainTextEdit()
        self.cve_update_log.setReadOnly(True)
        self.cve_update_log.setMaximumHeight(150)
        self.cve_update_log.setStyleSheet('font-size: 18px;')
        self.cve_update_log.setPlaceholderText('漏洞库更新进度将在此显示...')
        layout.addWidget(self.cve_update_log)

        self.tabs.addTab(widget, '漏洞库')

    def _search_cve(self):
        keyword = self.cve_search.text().strip()
        severity = self.cve_severity_filter.currentText()
        min_cvss = 7.0 if severity != '全部' else 0

        cves = self.db.search_cve(keyword=keyword, min_cvss=min_cvss, limit=9990000)
        if severity != '全部':
            cves = [c for c in cves if c.get('severity') == severity]

        self.cve_table.setRowCount(0)
        for cve in cves:
            row = self.cve_table.rowCount()
            self.cve_table.insertRow(row)
            self.cve_table.setItem(row, 0, QTableWidgetItem(cve.get('cve_id', '')))
            sev = cve.get('severity', 'INFO')
            item = QTableWidgetItem(sev)
            if sev == 'CRITICAL':
                item.setBackground(QColor(255, 80, 80))
                item.setForeground(QColor(255, 255, 255))
            elif sev == 'HIGH':
                item.setBackground(QColor(255, 150, 50))
                item.setForeground(QColor(255, 255, 255))
            self.cve_table.setItem(row, 1, item)
            self.cve_table.setItem(row, 2, QTableWidgetItem(str(cve.get('cvss_score', ''))))
            self.cve_table.setItem(row, 3, QTableWidgetItem((cve.get('description', '') or '')[:120]))
            self.cve_table.setItem(row, 4, QTableWidgetItem(cve.get('published_date', '') or ''))
            self.cve_table.setItem(row, 5, QTableWidgetItem((cve.get('affected_products', '') or '')[:80]))

    def _on_cve_clicked(self, item):
        row = item.row()
        cve_id = self.cve_table.item(row, 0).text()
        cves = self.db.search_cve(keyword=cve_id, limit=1)
        if cves:
            cve = cves[0]
            products = cve.get('affected_products', '') or ''
            if isinstance(products, list):
                products = ', '.join(products)
            detail = f"""
CVE编号: {cve.get('cve_id', '')}
名称: {cve.get('name', '')}
严重程度: {cve.get('severity', 'INFO')} | CVSS分数: {cve.get('cvss_score', 'N/A')}
发布时间: {cve.get('published_date', 'N/A')}
更新时间: {cve.get('modified_date', 'N/A')}
受影响产品: {products}

漏洞描述:
{cve.get('description', '暂无描述') or '暂无描述'}

AI分析:
{cve.get('ai_analysis', '暂无AI分析') or '暂无AI分析'}
"""
            self.cve_detail_text.setText(detail)

    # ============ AI代码审计 ============
    def _create_audit_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('AI代码安全审计', '使用AI分析源代码安全漏洞'))

        path_layout = QHBoxLayout()
        self.code_path_input = QLineEdit()
        self.code_path_input.setPlaceholderText('选择要审计的代码目录...')
        path_layout.addWidget(self.code_path_input)
        browse_btn = QPushButton('浏览...')
        browse_btn.clicked.connect(self._browse_code_path)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        btn_layout = QHBoxLayout()
        self.audit_btn = QPushButton('开始审计')
        self.audit_btn.clicked.connect(self._start_audit)
        btn_layout.addWidget(self.audit_btn)

        self.audit_stop_btn = QPushButton('停止')
        self.audit_stop_btn.setObjectName('stopBtn')
        self.audit_stop_btn.clicked.connect(self._stop_audit)
        self.audit_stop_btn.setEnabled(False)
        btn_layout.addWidget(self.audit_stop_btn)

        self.audit_save_btn = QPushButton('保存审计报告')
        self.audit_save_btn.setObjectName('saveBtn')
        self.audit_save_btn.clicked.connect(self._save_audit_report)
        self.audit_save_btn.setEnabled(False)
        btn_layout.addWidget(self.audit_save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.audit_progress = QProgressBar()
        self.audit_progress.setVisible(False)
        layout.addWidget(self.audit_progress)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(6)
        self.audit_table.setHorizontalHeaderLabels(['文件', '行号', '类别', '严重程度', '代码片段', '修复建议'])
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.audit_table)

        self.audit_log = QPlainTextEdit()
        self.audit_log.setReadOnly(True)
        self.audit_log.setMaximumHeight(150)
        layout.addWidget(self.audit_log)

        self.tabs.addTab(widget, 'AI代码审计')

    def _browse_code_path(self):
        path = QFileDialog.getExistingDirectory(self, '选择代码目录')
        if path:
            self.code_path_input.setText(path)

    def _start_audit(self):
        path = self.code_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, '警告', '请输入代码路径')
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, '警告', '路径不存在')
            return

        self.audit_btn.setEnabled(False)
        self.audit_stop_btn.setEnabled(True)
        self.audit_save_btn.setEnabled(False)
        self.audit_progress.setVisible(True)
        self.audit_progress.setValue(0)
        self._safe_clear('audit_log')
        self.audit_table.setRowCount(0)

        self.current_audit_thread = AIAuditThread(self.ai_analyzer, path, 'code')
        self.current_audit_thread.progress.connect(self._on_audit_progress)
        self.current_audit_thread.finished.connect(self._on_audit_finished)
        self.current_audit_thread.error.connect(self._on_audit_error)
        self.current_audit_thread.start()
        self._safe_log('audit_log',f'开始审计: {path}')

    def _stop_audit(self):
        if self.current_audit_thread:
            self.current_audit_thread.terminate()
            self.current_audit_thread = None
        self.audit_btn.setEnabled(True)
        self.audit_stop_btn.setEnabled(False)
        self.audit_progress.setVisible(False)

    def _on_audit_progress(self, msg):
        self._safe_log('audit_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _on_audit_finished(self, result):
        self.audit_progress.setValue(100)
        self._safe_log('audit_log','审计完成!')
        self.last_audit_result = result
        self.audit_history.insert(0, result)
        if len(self.audit_history) > 50:
            self.audit_history = self.audit_history[:50]
        self.db.save_audit_result(result)

        self.audit_table.setRowCount(0)
        for issue in result.get('issues', []):
            row = self.audit_table.rowCount()
            self.audit_table.insertRow(row)
            self.audit_table.setItem(row, 0, QTableWidgetItem(issue.get('file', '')))
            self.audit_table.setItem(row, 1, QTableWidgetItem(str(issue.get('line', ''))))
            self.audit_table.setItem(row, 2, QTableWidgetItem(issue.get('category', '')))
            self.audit_table.setItem(row, 3, QTableWidgetItem(issue.get('severity', '')))
            self.audit_table.setItem(row, 4, QTableWidgetItem(issue.get('code', '')[:80]))
            self.audit_table.setItem(row, 5, QTableWidgetItem(issue.get('recommendation', '')))

            sev = issue.get('severity', '')
            if sev in ['CRITICAL', 'HIGH']:
                for c in range(6):
                    item = self.audit_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 210, 210))

        total = result.get('total_vulnerabilities', 0)
        self._safe_log('audit_log',f'扫描文件: {result.get("total_files_scanned", 0)}')
        self._safe_log('audit_log',f'发现问题: {total}')
        risk = result.get('risk_level', '未知')
        self._safe_log('audit_log',f'风险等级: {risk}')
        self._safe_log('audit_log',f'建议: {result.get("recommendation", "")}')

        self.audit_btn.setEnabled(True)
        self.audit_stop_btn.setEnabled(False)
        self.audit_save_btn.setEnabled(True)
        self.audit_progress.setVisible(False)

        QMessageBox.information(self, '审计完成', f'审计完成，发现 {total} 个安全问题\n风险等级: {risk}')

    def _on_audit_error(self, error):
        self._safe_log('audit_log',f'错误: {error}')
        self.audit_btn.setEnabled(True)
        self.audit_stop_btn.setEnabled(False)
        self.audit_progress.setVisible(False)
        QMessageBox.critical(self, '审计错误', error)

    def _save_audit_report(self):
        if not self.last_audit_result:
            QMessageBox.warning(self, '警告', '没有可保存的审计结果')
            return
        filepath, _ = QFileDialog.getSaveFileName(self, '保存审计报告', f'audit_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html', 'HTML报告 (*.html)')
        if not filepath:
            return
        try:
            from report_generator import generate_audit_report
            report_path = generate_audit_report(self.last_audit_result, os.path.dirname(filepath) or 'reports')
            if report_path != filepath:
                import shutil
                shutil.copy(report_path, filepath)
            QMessageBox.information(self, '成功', f'审计报告已保存至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    # ============ 威胁情报 ============
    def _create_intel_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('威胁情报', '从全球6大数据源收集威胁情报'))

        btn_layout = QHBoxLayout()
        self.intel_update_btn = QPushButton('获取全球威胁情报')
        self.intel_update_btn.setObjectName('saveBtn')
        self.intel_update_btn.clicked.connect(self._start_intel_collection)
        btn_layout.addWidget(self.intel_update_btn)

        self.intel_stop_btn = QPushButton('停止搜索')
        self.intel_stop_btn.setObjectName('stopBtn')
        self.intel_stop_btn.clicked.connect(self._stop_intel)
        self.intel_stop_btn.setEnabled(False)
        btn_layout.addWidget(self.intel_stop_btn)

        days_label = QLabel('搜索天数:')
        btn_layout.addWidget(days_label)
        self.intel_days = QSpinBox()
        self.intel_days.setRange(1, 90)
        self.intel_days.setValue(7)
        self.intel_days.setSuffix(' 天')
        btn_layout.addWidget(self.intel_days)

        mode_label = QLabel('模式:')
        btn_layout.addWidget(mode_label)
        self.intel_mode = QComboBox()
        self.intel_mode.addItem('最近CVE', 'recent')
        self.intel_mode.addItem('历史CVE(2020起)', 'historical')
        self.intel_mode.setToolTip('recent=最近CVEs, historical=2020年以来所有CVE')
        btn_layout.addWidget(self.intel_mode)

        self.intel_save_btn = QPushButton('保存报告')
        self.intel_save_btn.setObjectName('saveBtn')
        self.intel_save_btn.clicked.connect(self._save_intel_report)
        self.intel_save_btn.setEnabled(False)
        btn_layout.addWidget(self.intel_save_btn)

        self.intel_open_btn = QPushButton('打开报告')
        self.intel_open_btn.clicked.connect(self._open_report)
        self.intel_open_btn.setEnabled(False)
        btn_layout.addWidget(self.intel_open_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.intel_progress = QProgressBar()
        self.intel_progress.setVisible(False)
        layout.addWidget(self.intel_progress)

        self.intel_log = QPlainTextEdit()
        self.intel_log.setReadOnly(True)
        self.intel_log.setStyleSheet('font-size: 18px; font-family: monospace; background: #0a0e27; color: #4caf50;')
        self.intel_log.setMinimumHeight(400)
        layout.addWidget(self.intel_log)

        self.tabs.addTab(widget, '威胁情报')

    def _on_intel_progress_msg(self, msg):
        self._safe_log('intel_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _start_intel_collection(self):
        """启动全球威胁情报收集"""
        self.intel_update_btn.setText('正在全网搜索威胁情报......')
        self.intel_update_btn.setEnabled(False)
        self.intel_stop_btn.setEnabled(True)
        self.intel_save_btn.setEnabled(False)
        self.intel_open_btn.setEnabled(False)
        self.intel_progress.setVisible(True)
        self.intel_progress.setValue(0)
        self.intel_progress.setRange(0, 0)
        self._safe_clear('intel_log')

        days = self.intel_days.value()
        mode = self.intel_mode.currentData()
        self.threat_intel._stop_requested = False

        self.intel_collect_thread = IntelCollectThread(self.threat_intel, days, mode)
        self.intel_collect_thread.progress.connect(self._on_intel_progress)
        self.intel_collect_thread.finished.connect(self._on_intel_collection_finished)
        self.intel_collect_thread.error.connect(self._on_intel_error)
        self.intel_collect_thread.start()

    def _on_intel_progress(self, msg):
        self._safe_log('intel_log', msg)

    def _on_intel_collection_finished(self, results):
        self.intel_progress.setRange(0, 100)
        self.intel_progress.setValue(100)

        from threat_intel import generate_threat_intel_report
        self.intel_report_html = generate_threat_intel_report(results, self.db)
        self.intel_report_data = results

        self.db.save_report(
            f'全球威胁分析报告 - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'threat_intel', 'html', self.intel_report_html[:500], '', None
        )

        # 在文本框显示报告内容
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '=' * 60)
        self._safe_log('intel_log', '          全球威胁分析报告')
        self._safe_log('intel_log', '    基于STIX 2.1 / MITRE ATT&CK框架')
        self._safe_log('intel_log', '=' * 60)
        self._safe_log('intel_log', f'生成时间: {results.get("collection_time", "")}')
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '┌─ 战略层 (Strategic) ──────────────────────')
        self._safe_log('intel_log', f'│ 威胁态势: {results.get("total_kev", 0)}个漏洞被活跃利用')
        self._safe_log('intel_log', f'│ 新增CVE: {results.get("total_cve", 0)}个, 高危: {results.get("high_critical_cve", 0)}个')
        self._safe_log('intel_log', f'│ 威胁行为者: {results.get("total_threat_actors", 0)}个APT组织/勒索团伙')
        self._safe_log('intel_log', '│ 建议: 优先修复KEV列表中的勒索软件相关漏洞')
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '├─ 运营层 (Operational) ────────────────────')
        self._safe_log('intel_log', f'│ IoC威胁指标: {results.get("total_ioc", 0)}个')
        self._safe_log('intel_log', f'│ EPSS利用预测: {results.get("total_epss", 0)}条评分')
        self._safe_log('intel_log', '│ 防御建议: 封禁恶意IoC, 加强流量监控')
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '├─ 战术层 (Tactical) ──────────────────────')
        self._safe_log('intel_log', f'│ MITRE ATT&CK: {results.get("total_attack_patterns", 0)}个攻击模式(T1190/T1203等)')
        self._safe_log('intel_log', '│ 攻击链: 初始访问→执行→持久化→C2→数据渗出')
        self._safe_log('intel_log', f'│ 入侵指标: IP/域名/URL/文件哈希')
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '├─ 技术层 (Technical) ─────────────────────')
        self._safe_log('intel_log', '│ 可机读IoC: 可导入SIEM/SOAR/Firewall')
        self._safe_log('intel_log', '│ 恶意软件: Emotet/Cobalt Strike等家族')
        self._safe_log('intel_log', '│ C2通信: HTTP/HTTPS/DNS隧道')
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '┌─ 6大数据源采集结果 ──────────────────────')
        for name, status in results.get('sources', {}).items():
            self._safe_log('intel_log', f'│ {name}: {status}')
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', 'HTML格式完整报告已生成(四层架构)，')
        self._safe_log('intel_log', '可点击"保存报告"或"打开报告"查看完整报告')
        self._safe_log('intel_log', '=' * 60)

        self.intel_update_btn.setText('获取全球威胁情报')
        self.intel_update_btn.setEnabled(True)
        self.intel_stop_btn.setEnabled(False)
        self.intel_save_btn.setEnabled(True)
        self.intel_open_btn.setEnabled(True)
        self.intel_progress.setVisible(False)
        self._update_dashboard()

        QMessageBox.information(self, '收集完毕',
            f'全球威胁情报收集完成！\n\n'
            f'战略层: KEV {results.get("total_kev", 0)}条 | 威胁行为者 {results.get("total_threat_actors", 0)}个\n'
            f'运营层: IoC {results.get("total_ioc", 0)}个 | EPSS {results.get("total_epss", 0)}条\n'
            f'战术层: ATT&CK模式 {results.get("total_attack_patterns", 0)}个\n'
            f'技术层: CVE {results.get("total_cve", 0)}条(新增)')

    def _save_intel_report(self):
        if not hasattr(self, 'intel_report_html'):
            QMessageBox.warning(self, '警告', '没有可保存的威胁情报报告')
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, '保存全球威胁分析报告',
            f'threat_intel_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
            'HTML报告 (*.html)')
        if not filepath:
            return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.intel_report_html)
            QMessageBox.information(self, '成功', f'报告已保存至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _stop_intel(self):
        self.threat_intel.stop()
        if hasattr(self, 'intel_collect_thread') and self.intel_collect_thread:
            self.intel_collect_thread.terminate()
            self.intel_collect_thread = None
        self.intel_update_btn.setText('获取全球威胁情报')
        self.intel_update_btn.setEnabled(True)
        self.intel_stop_btn.setEnabled(False)
        self.intel_save_btn.setEnabled(False)
        self.intel_open_btn.setEnabled(False)
        self.intel_progress.setVisible(False)

    def _on_intel_error(self, error):
        self._safe_log('intel_log', f'错误: {error}')
        self.intel_update_btn.setText('获取全球威胁情报')
        self.intel_update_btn.setEnabled(True)
        self.intel_stop_btn.setEnabled(False)
        self.intel_progress.setVisible(False)
        QMessageBox.critical(self, '错误', error)

    def _update_cve_db(self):
        """手动更新漏洞库"""
        self.cve_update_btn.setText('正在搜索漏洞信息......')
        self.cve_update_btn.setEnabled(False)
        self.cve_stop_btn.setEnabled(True)
        self._safe_clear('cve_update_log')

        days = self.cve_days_spin.value()
        self.threat_intel._stop_requested = False

        self.current_cve_thread = ThreatIntelThread(self.threat_intel, days=days)
        self.current_cve_thread.progress.connect(self._on_cve_update_progress)
        self.current_cve_thread.finished.connect(self._on_cve_update_finished)
        self.current_cve_thread.error.connect(self._on_cve_update_error)
        self.current_cve_thread.start()

    def _on_cve_update_progress(self, msg):
        self._safe_log('cve_update_log', f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _on_cve_update_finished(self, count):
        self._safe_log('cve_update_log', f'更新完成! 新增{count}条CVE')
        self.cve_update_btn.setText('更新漏洞库')
        self.cve_update_btn.setEnabled(True)
        self.cve_stop_btn.setEnabled(False)
        self._update_dashboard()

    def _on_cve_update_error(self, error):
        self._safe_log('cve_update_log', f'错误: {error}')
        self.cve_update_btn.setText('更新漏洞库')
        self.cve_update_btn.setEnabled(True)
        self.cve_stop_btn.setEnabled(False)

    def _stop_cve_update(self):
        """停止CVE更新搜索"""
        self.threat_intel.stop()
        if hasattr(self, 'current_cve_thread') and self.current_cve_thread:
            self.current_cve_thread.terminate()
            self.current_cve_thread = None
        self.cve_update_btn.setText('更新漏洞库')
        self.cve_update_btn.setEnabled(True)
        self.cve_stop_btn.setEnabled(False)

    def _auto_update_cve(self):
        """每日自动更新CVE漏洞库"""
        try:
            logger.info("开始每日自动更新CVE漏洞库...")
            cves = self.threat_intel.fetch_recent_cve(days=1, limit=100)
            if cves:
                count = self.threat_intel.sync_to_database(cves)
                logger.info(f"自动更新完成: 新增{count}条CVE")
                self.status_bar.showMessage(f'CVE漏洞库已自动更新 +{count}条 | 山西有信网安科技有限公司', 10000)
                self._update_dashboard()
        except Exception as e:
            logger.error(f"自动更新CVE失败: {e}")

    # ============ 报告中心 ============
    def _create_reports_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('报告中心', '管理扫描报告和导出数据'))

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton('刷新列表')
        refresh_btn.clicked.connect(self._refresh_reports)
        btn_layout.addWidget(refresh_btn)

        export_scan_btn = QPushButton('导出最新扫描报告')
        export_scan_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(export_scan_btn)

        export_vulndb_btn = QPushButton('导出漏洞库报告')
        export_vulndb_btn.clicked.connect(self._export_vulndb)
        btn_layout.addWidget(export_vulndb_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.report_table = QTableWidget()
        self.report_table.setColumnCount(5)
        self.report_table.setHorizontalHeaderLabels(['ID', '标题', '类型', '格式', '创建时间'])
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.report_table)

        self.tabs.addTab(widget, '报告中心')

    def _refresh_reports(self):
        reports = self.db.get_reports()
        self.report_table.setRowCount(0)
        for r in reports:
            row = self.report_table.rowCount()
            self.report_table.insertRow(row)
            self.report_table.setItem(row, 0, QTableWidgetItem(str(r.get('id', ''))))
            self.report_table.setItem(row, 1, QTableWidgetItem(r.get('title', '')))
            self.report_table.setItem(row, 2, QTableWidgetItem(r.get('type', '')))
            self.report_table.setItem(row, 3, QTableWidgetItem(r.get('format', '')))
            self.report_table.setItem(row, 4, QTableWidgetItem(r.get('created_at', '')[:19] if r.get('created_at') else ''))

    # ============ 系统设置 ============
    def _create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('系统设置', '配置系统参数'))

        # 扫描设置
        scan_group = QGroupBox('扫描设置')
        scan_layout = QFormLayout()
        self.setting_timeout = QSpinBox()
        self.setting_timeout.setRange(1, 30)
        self.setting_timeout.setValue(int(self.db.get_setting('scan_timeout', '5')))
        self.setting_timeout.setSuffix(' 秒')
        scan_layout.addRow('默认超时:', self.setting_timeout)
        self.setting_concurrent = QSpinBox()
        self.setting_concurrent.setRange(1, 50)
        self.setting_concurrent.setValue(int(self.db.get_setting('scan_concurrent', '10')))
        scan_layout.addRow('并发扫描:', self.setting_concurrent)
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        # CVE设置
        cve_group = QGroupBox('漏洞库设置')
        cve_layout = QFormLayout()
        self.setting_auto_update = QCheckBox('自动更新CVE数据')
        self.setting_auto_update.setChecked(self.db.get_setting('auto_update_cve', 'true') == 'true')
        cve_layout.addRow(self.setting_auto_update)
        self.setting_retention = QSpinBox()
        self.setting_retention.setRange(30, 365)
        self.setting_retention.setValue(int(self.db.get_setting('report_retention_days', '90')))
        self.setting_retention.setSuffix(' 天')
        cve_layout.addRow('报告保留天数:', self.setting_retention)
        cve_group.setLayout(cve_layout)
        layout.addWidget(cve_group)

        save_btn = QPushButton('保存设置')
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        # 版权信息
        info_frame = QFrame()
        info_frame.setStyleSheet('background: #f8f9fa; border-radius: 8px; padding: 15px;')
        info_layout = QVBoxLayout(info_frame)
        logo_label = QLabel()
        logo_path = _get_logo_path()
        if logo_path:
            pixmap = QPixmap(logo_path).scaled(200, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = _make_white_transparent(pixmap)
            logo_label.setPixmap(pixmap)
            logo_label.setStyleSheet('background: transparent;')
        info_layout.addWidget(logo_label)
        info_layout.addWidget(QLabel("<b style='font-size:22px;color:#1a73e8;'><span style='font-size:33px; vertical-align:top;'>©</span>2026 山西有信网安科技有限公司</b>"))
        info_layout.addWidget(QLabel('<span style="color:#666;">下一代智能漏洞扫描系统 Pro v1.0</span>'))
        info_layout.addWidget(QLabel('<span style="color:#999;">&copy; 2026 AI Vuln Scanner. All rights reserved.</span>'))
        info_layout.addWidget(QLabel('<span style="color:#999;">技术支持: 山西有信网安科技有限公司</span>'))
        layout.addWidget(info_frame)
        layout.addStretch()

        self.tabs.addTab(widget, '系统设置')

    def _save_settings(self):
        self.db.set_setting('scan_timeout', str(self.setting_timeout.value()))
        self.db.set_setting('scan_concurrent', str(self.setting_concurrent.value()))
        self.db.set_setting('auto_update_cve', 'true' if self.setting_auto_update.isChecked() else 'false')
        self.db.set_setting('report_retention_days', str(self.setting_retention.value()))
        QMessageBox.information(self, '成功', '设置已保存')

    # ============ 报告操作 ============
    def _generate_scan_html(self, scan_result):
        """生成扫描HTML报告"""
        from report_generator import _generate_html_report
        return _generate_html_report(scan_result)

    def _generate_scan_text(self, scan_result):
        from report_generator import _generate_text_report
        return _generate_text_report(scan_result)

    def _save_report(self):
        if not self.last_scan_result:
            QMessageBox.warning(self, '警告', '没有可保存的扫描结果，请先执行扫描')
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, '保存报告', f'scan_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'HTML报告 (*.html);;文本报告 (*.txt)')
        if not filepath:
            return
        try:
            content = self._generate_scan_html(self.last_scan_result) if filepath.endswith('.html') else self._generate_scan_text(self.last_scan_result)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            title = f'扫描报告 - {self.last_scan_result.get("target", "未知")}'
            self.db.save_report(title, 'scan', 'html' if filepath.endswith('.html') else 'txt', content[:500], filepath)
            QMessageBox.information(self, '成功', f'报告已保存至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _open_report(self):
        filepath, _ = QFileDialog.getOpenFileName(self, '打开报告', '', '报告文件 (*.html *.txt);;所有文件 (*)')
        if filepath:
            try:
                os.startfile(filepath)
            except Exception as e:
                QMessageBox.critical(self, '错误', f'打开失败: {str(e)}')

    def _export_report(self):
        if not self.last_scan_result:
            tasks = self.db.get_all_tasks(1)
            if not tasks:
                QMessageBox.warning(self, '警告', '没有扫描记录')
                return
            task = tasks[0]
            results = self.db.get_task_results(task['id'])
            if not results:
                QMessageBox.warning(self, '警告', '没有扫描结果')
                return
            scan_data = {
                'target': task['target'],
                'start_time': task.get('start_time', ''),
                'end_time': task.get('end_time', ''),
                'duration': 0,
                'vulnerabilities': results,
                'scan_result': {'hosts': []},
                'summary': {'total': len(results), 'by_severity': {}, 'high_critical': 0}
            }
        else:
            scan_data = self.last_scan_result

        from report_generator import generate_scan_report
        output_dir = 'reports'
        output_files = generate_scan_report(scan_data, output_dir, ['html'])
        result_text = '\n'.join([f'{k}: {v}' for k, v in output_files.items()])
        QMessageBox.information(self, '成功', f'报告已导出:\n{result_text}')

    def _export_vulndb(self):
        from report_generator import export_vuln_database
        filepath, _ = QFileDialog.getSaveFileName(self, '导出漏洞库', f'vuln_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html', 'HTML (*.html)')
        if not filepath:
            return
        try:
            export_vuln_database(self.db, filepath)
            QMessageBox.information(self, '成功', f'漏洞库已导出至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出失败: {str(e)}')

    # ============ 工具操作 ============
    def _clear_database(self):
        reply = QMessageBox.question(self, '确认', '确定要清空所有数据吗？此操作不可恢复！', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db.clear_database()
                self._update_dashboard()
                QMessageBox.information(self, '完成', '所有数据库已清空')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'清空失败: {str(e)}')

    def _show_about(self):
        QMessageBox.about(self, '关于 AI漏洞扫描系统',
                          '<h2>下一代智能漏洞扫描系统 Pro v1.0</h2>'
                          '<p><b>山西有信网安科技有限公司</b></p>'
                          '<p>下一代智能漏洞扫描系统</p>'
                          '<hr>'
                          '<p><b>功能模块:</b></p>'
                          '<ul>'
                          '<li>仪表盘 - 系统运行概览</li>'
                          '<li>资产管理 - 网络资产发现与管理</li>'
                          '<li>漏洞扫描 - 多类型资产漏洞检测</li>'
                          '<li>漏洞库 - CVE漏洞数据库管理</li>'
                          '<li>AI代码审计 - 源码安全分析</li>'
                          '<li>威胁情报 - NVD实时情报</li>'
                          '<li>报告中心 - 多格式报告生成</li>'
                          '</ul>'
                          '<hr>'
                          '<p>&copy; 2026 山西有信网安科技有限公司</p>'
                          '<p>All rights reserved.</p>')

    def _update_status_bar(self):
        stats = self.db.get_statistics()
        self.status_bar.showMessage(
            f'就绪 | CVE: {stats["total_cves"]}条 | 资产: {stats["total_assets"]}个 | '
            f'任务: {stats["total_tasks"]}个 | 山西有信网安科技有限公司'
        )


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
