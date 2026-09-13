# -*- coding: utf-8 -*-
"""
AI Vuln Scanner Pro - PyQt5 GUI主界面
"""
import sys
import os
import logging
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTabWidget, QTableWidget, QTableWidgetItem, QPushButton,
                             QLineEdit, QLabel, QTextEdit, QComboBox, QProgressBar,
                             QGroupBox, QFormLayout, QCheckBox, QSpinBox, QMessageBox,
                             QFileDialog, QSplitter, QStatusBar, QMenuBar, QMenu,
                             QAction, QHeaderView, QToolBar, QDialog, QProgressDialog,
                             QRadioButton)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScanThread(QThread):
    """扫描线程"""
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


class AIAnalysisThread(QThread):
    """AI分析线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, analyzer, target, analysis_type):
        super().__init__()
        self.analyzer = analyzer
        self.target = target
        self.analysis_type = analysis_type

    def run(self):
        try:
            self.progress.emit("正在进行AI分析...")
            if self.analysis_type == 'code':
                result = self.analyzer.scan_directory(self.target)
                analysis = self.analyzer.generate_report(result)
                summary = f"扫描文件: {analysis['total_files_scanned']}, 发现漏洞: {analysis['total_vulnerabilities']}"
            else:
                result = self.analyzer.analyze_vulnerability({'cve_id': 'manual', 'description': self.target})
                summary = result
            self.finished.emit(summary)
        except Exception as e:
            self.error.emit(str(e))


class ThreatIntelUpdateThread(QThread):
    """威胁情报更新线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, collector):
        super().__init__()
        self.collector = collector

    def run(self):
        try:
            self.progress.emit("正在从NVD获取最新CVE...")
            cves = self.collector.fetch_recent_cve(days=7)

            self.progress.emit(f"获取到 {len(cves)} 条CVE，正在同步到数据库...")
            count = self.collector.sync_to_database(cves)

            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        # 初始化模块
        from database import VulnDatabase
        from ai_analyzer import AIAnalyzer
        from threat_intel import ThreatIntelCollector, VulnMatcher
        from scanner_engine import VulnScanner

        self.db = VulnDatabase()
        self.ai_analyzer = AIAnalyzer()
        self.threat_intel = ThreatIntelCollector(self.db)
        self.vuln_matcher = VulnMatcher(self.db)
        self.scanner = VulnScanner(self.db, self.threat_intel)

        # 扫描状态
        self.current_scan_thread = None

        # 初始化UI
        self.init_ui()

        # 定时更新状态栏
        self.update_status_bar()

        logger.info("主窗口初始化完成")

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('AI Vuln Scanner Pro - 下一代智能漏洞扫描系统')
        self.setGeometry(100, 100, 1400, 800)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建工具栏
        self.create_toolbar()

        # 中央部件 - TabWidget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 创建各个标签页
        self.create_scan_tab()
        self.create_vuln_db_tab()
        self.create_ai_audit_tab()
        self.create_threat_intel_tab()
        self.create_tasks_tab()
        self.create_settings_tab()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 统计定时器
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(30000)  # 每30秒更新

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件')

        export_action = QAction('导出报告', self)
        export_action.triggered.connect(self.export_report)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction('退出', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 扫描菜单
        scan_menu = menubar.addMenu('扫描')

        quick_scan_action = QAction('快速扫描', self)
        quick_scan_action.triggered.connect(lambda: self.start_scan('quick'))
        scan_menu.addAction(quick_scan_action)

        full_scan_action = QAction('完整扫描', self)
        full_scan_action.triggered.connect(lambda: self.start_scan('full'))
        scan_menu.addAction(full_scan_action)

        # 工具菜单
        tool_menu = menubar.addMenu('工具')

        update_cve_action = QAction('更新CVE数据库', self)
        update_cve_action.triggered.connect(self.update_threat_intel)
        tool_menu.addAction(update_cve_action)

        clear_db_action = QAction('清空数据库', self)
        clear_db_action.triggered.connect(self.clear_database)
        tool_menu.addAction(clear_db_action)

        # 帮助菜单
        help_menu = menubar.addMenu('帮助')

        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 快速扫描按钮
        quick_scan_btn = QPushButton('快速扫描')
        quick_scan_btn.clicked.connect(lambda: self.start_scan('quick'))
        toolbar.addWidget(quick_scan_btn)

        # 完整扫描按钮
        full_scan_btn = QPushButton('完整扫描')
        full_scan_btn.clicked.connect(lambda: self.start_scan('full'))
        toolbar.addWidget(full_scan_btn)

        toolbar.addSeparator()

        # 更新CVE按钮
        update_btn = QPushButton('更新漏洞库')
        update_btn.clicked.connect(self.update_threat_intel)
        toolbar.addWidget(update_btn)

        toolbar.addSeparator()

        # 状态显示
        self.toolbar_status = QLabel('就绪')
        toolbar.addWidget(self.toolbar_status)

    def create_scan_tab(self):
        """创建扫描标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 扫描配置区域
        config_group = QGroupBox('扫描配置')
        config_layout = QFormLayout()

        # 目标输入
        target_layout = QHBoxLayout()
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText('输入IP地址、域名或CIDR (如: 192.168.1.1, 10.0.0.0/24)')
        target_layout.addWidget(self.target_input)

        # 示例按钮
        example_btn = QPushButton('示例')
        example_btn.clicked.connect(lambda: self.target_input.setText('192.168.1.1'))
        target_layout.addWidget(example_btn)

        config_layout.addRow('扫描目标:', target_layout)

        # 端口设置
        port_layout = QHBoxLayout()
        self.port_input = QLineEdit('21,22,23,25,53,80,110,143,443,445,993,995,1433,3306,3389,5432,8080,8443')
        port_layout.addWidget(self.port_input)
        port_layout.addWidget(QLabel('(留空使用默认常用端口)'))
        config_layout.addRow('端口范围:', port_layout)

        # 扫描类型
        scan_type_layout = QHBoxLayout()
        self.scan_type_combo = QComboBox()
        self.scan_type_combo.addItems(['quick', 'full', 'custom'])
        scan_type_layout.addWidget(self.scan_type_combo)
        scan_type_layout.addWidget(QLabel('快速扫描仅检测常用端口，完整扫描会进行深度探测'))
        config_layout.addRow('扫描类型:', scan_type_layout)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 扫描按钮
        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton('开始扫描')
        self.scan_btn.clicked.connect(lambda: self.start_scan(self.scan_type_combo.currentText()))
        btn_layout.addWidget(self.scan_btn)

        self.stop_btn = QPushButton('停止扫描')
        self.stop_btn.clicked.connect(self.stop_scan)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 进度条
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        layout.addWidget(self.scan_progress)

        # 结果区域 - 使用分割器
        splitter = QSplitter(Qt.Vertical)

        # 扫描结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(9)
        self.result_table.setHorizontalHeaderLabels([
            '主机', '端口', '协议', '服务', '版本', 'CVE ID', '严重程度', 'CVSS', '描述'
        ])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        splitter.addWidget(self.result_table)

        # 扫描日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        splitter.addWidget(self.log_text)

        layout.addWidget(splitter)

        self.tabs.addTab(widget, '漏洞扫描')

    def create_vuln_db_tab(self):
        """创建漏洞库标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索区域
        search_group = QGroupBox('CVE搜索')
        search_layout = QHBoxLayout()

        self.cve_search_input = QLineEdit()
        self.cve_search_input.setPlaceholderText('搜索CVE ID、产品名或关键词')
        search_layout.addWidget(self.cve_search_input)

        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self.search_cve)
        search_layout.addWidget(search_btn)

        search_layout.addStretch()

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # CVE结果表格
        self.cve_table = QTableWidget()
        self.cve_table.setColumnCount(7)
        self.cve_table.setHorizontalHeaderLabels([
            'CVE ID', '名称', '严重程度', 'CVSS', '发布年份', '受影响产品', '描述'
        ])
        self.cve_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 设置表格选择模式为整行选中
        self.cve_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cve_table.setSelectionMode(QTableWidget.SingleSelection)
        # 绑定点击事件
        self.cve_table.itemClicked.connect(self.on_cve_table_clicked)
        layout.addWidget(self.cve_table)

        # CVE详情
        detail_group = QGroupBox('CVE详情')
        detail_layout = QVBoxLayout()
        self.cve_detail_text = QTextEdit()
        self.cve_detail_text.setReadOnly(True)
        detail_layout.addWidget(self.cve_detail_text)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        self.tabs.addTab(widget, '漏洞库')

    def create_ai_audit_tab(self):
        """创建AI审计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 选择审计类型
        type_group = QGroupBox('审计类型')
        type_layout = QHBoxLayout()

        self.audit_type_combo = QComboBox()
        self.audit_type_combo.addItems(['代码目录扫描', '单个文件扫描', 'CVE深度分析'])
        type_layout.addWidget(QLabel('审计模式:'))
        type_layout.addWidget(self.audit_type_combo)

        type_layout.addStretch()
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # 输入区域
        input_group = QGroupBox('扫描目标')
        input_layout = QFormLayout()

        self.code_path_input = QLineEdit()
        self.code_path_input.setPlaceholderText('输入代码目录或文件路径')
        input_layout.addRow('路径:', self.code_path_input)

        browse_btn = QPushButton('浏览...')
        browse_btn.clicked.connect(self.browse_code_path)
        input_layout.addRow('', browse_btn)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 审计按钮
        audit_btn = QPushButton('开始AI安全审计')
        audit_btn.clicked.connect(self.start_ai_audit)
        layout.addWidget(audit_btn)

        # 进度条
        self.audit_progress = QProgressBar()
        layout.addWidget(self.audit_progress)

        # 结果区域
        self.audit_result_table = QTableWidget()
        self.audit_result_table.setColumnCount(5)
        self.audit_result_table.setHorizontalHeaderLabels([
            '文件', '语言', '代码行数', '漏洞数量', '漏洞类型'
        ])
        self.audit_result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.audit_result_table)

        # 详细结果
        detail_group = QGroupBox('详细漏洞信息')
        detail_layout = QVBoxLayout()
        self.audit_detail_text = QTextEdit()
        self.audit_detail_text.setReadOnly(True)
        detail_layout.addWidget(self.audit_detail_text)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        self.tabs.addTab(widget, 'AI代码审计')

    def create_threat_intel_tab(self):
        """创建威胁情报标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 更新控制
        update_group = QGroupBox('漏洞库更新')
        update_layout = QHBoxLayout()

        update_btn = QPushButton('立即更新CVE库')
        update_btn.clicked.connect(self.update_threat_intel)
        update_layout.addWidget(update_btn)

        self.update_status_label = QLabel('上次更新: 未知')
        update_layout.addWidget(self.update_status_label)

        update_layout.addStretch()

        # 自动更新复选框
        self.auto_update_check = QCheckBox('自动更新 (每天)')
        self.auto_update_check.setChecked(True)
        update_layout.addWidget(self.auto_update_check)

        update_group.setLayout(update_layout)
        layout.addWidget(update_group)

        # 统计信息
        stats_group = QGroupBox('漏洞库统计')
        stats_layout = QHBoxLayout()

        self.total_cve_label = QLabel('CVE总数: 0')
        stats_layout.addWidget(self.total_cve_label)

        self.critical_cve_label = QLabel('严重: 0')
        stats_layout.addWidget(self.critical_cve_label)

        self.high_cve_label = QLabel('高危: 0')
        stats_layout.addWidget(self.high_cve_label)

        self.medium_cve_label = QLabel('中危: 0')
        stats_layout.addWidget(self.medium_cve_label)

        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 日志
        self.threat_intel_log = QTextEdit()
        self.threat_intel_log.setReadOnly(True)
        layout.addWidget(self.threat_intel_log)

        self.tabs.addTab(widget, '威胁情报')

    def create_tasks_tab(self):
        """创建任务历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 任务列表
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(6)
        self.task_table.setHorizontalHeaderLabels([
            '任务ID', '目标', '类型', '状态', '发现漏洞', '开始时间'
        ])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.task_table)

        # 刷新按钮
        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self.load_tasks)
        layout.addWidget(refresh_btn)

        self.tabs.addTab(widget, '扫描任务')

    def create_settings_tab(self):
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # API配置
        api_group = QGroupBox('API配置')
        api_layout = QFormLayout()

        self.anthropic_key_input = QLineEdit()
        self.anthropic_key_input.setPlaceholderText('输入 Anthropic API Key (可选)')
        self.anthropic_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow('Claude API Key:', self.anthropic_key_input)

        self.nvd_key_input = QLineEdit()
        self.nvd_key_input.setPlaceholderText('输入 NVD API Key (可选)')
        api_layout.addRow('NVD API Key:', self.nvd_key_input)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # 扫描配置
        scan_group = QGroupBox('扫描配置')
        scan_layout = QFormLayout()

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        self.timeout_spin.setValue(5)
        self.timeout_spin.setSuffix(' 秒')
        scan_layout.addRow('连接超时:', self.timeout_spin)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 20)
        self.concurrent_spin.setValue(5)
        scan_layout.addRow('并发扫描数:', self.concurrent_spin)

        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        # 保存按钮
        save_btn = QPushButton('保存设置')
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

        self.tabs.addTab(widget, '设置')

    def start_scan(self, scan_type=None):
        """开始扫描"""
        if scan_type is None:
            scan_type = self.scan_type_combo.currentText()

        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, '警告', '请输入扫描目标')
            return

        # 更新UI状态
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.scan_progress.setVisible(True)
        self.scan_progress.setValue(0)
        self.log_text.clear()

        # 创建数据库任务记录
        task_id = self.db.create_task(target, scan_type, {
            'ports': self.port_input.text(),
            'scan_type': scan_type
        })
        self.db.update_task_status(task_id, 'running')

        # 启动扫描线程
        self.current_scan_thread = ScanThread(
            self.scanner, target, self.port_input.text() or None, scan_type
        )
        self.current_scan_thread.progress.connect(self.on_scan_progress)
        self.current_scan_thread.finished.connect(lambda r: self.on_scan_finished(r, task_id))
        self.current_scan_thread.error.connect(self.on_scan_error)
        self.current_scan_thread.start()

        self.log_message(f"开始扫描任务: {target}")

    def stop_scan(self):
        """停止扫描"""
        if self.current_scan_thread:
            self.current_scan_thread.terminate()
            self.current_scan_thread = None

        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_progress.setVisible(False)
        self.log_message("扫描已停止")

    def on_scan_progress(self, message):
        """扫描进度更新"""
        self.log_message(message)

        # 解析进度消息
        # 格式: "已扫描端口5/20" 或 "已扫描IP3/10"
        if '已扫描' in message and '/' in message:
            try:
                import re
                # 匹配 "已扫描端口X/Y" 或 "已扫描IPX/Y"
                # 提取最后一个 "/" 前的数字作为当前值，"/" 后的数字作为总数
                nums = re.findall(r'(\d+)/(\d+)', message)
                if nums:
                    # 取最后一组数字（最具体的进度信息）
                    current, total = map(int, nums[-1])
                    if total > 0:
                        percent = int(current * 100 / total)
                        self.scan_progress.setValue(percent)
                        self.scan_progress.setFormat(message)
                    return
                # 如果上面的正则没匹配到，尝试简单解析
                nums = re.findall(r'\d+', message)
                if len(nums) >= 2:
                    current, total = int(nums[-2]), int(nums[-1])
                    if total > 0:
                        percent = int(current * 100 / total)
                        self.scan_progress.setValue(percent)
                        self.scan_progress.setFormat(message)
            except:
                self.scan_progress.setFormat(message)
        elif '%' in message:
            try:
                value = int(message.replace('%', ''))
                self.scan_progress.setValue(value)
                self.scan_progress.setFormat(f"{value}%")
            except:
                pass

    def on_scan_finished(self, result, task_id):
        """扫描完成"""
        self.scan_progress.setValue(100)

        # 更新任务状态
        vuln_count = len(result.get('vulnerabilities', []))
        self.db.update_task_status(task_id, 'completed', vuln_count)

        # 更新结果表格
        self.result_table.setRowCount(0)
        for vuln in result.get('vulnerabilities', []):
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)

            self.result_table.setItem(row, 0, QTableWidgetItem(vuln.get('host', '')))
            self.result_table.setItem(row, 1, QTableWidgetItem(str(vuln.get('port', ''))))
            self.result_table.setItem(row, 2, QTableWidgetItem(vuln.get('protocol', 'tcp')))
            self.result_table.setItem(row, 3, QTableWidgetItem(vuln.get('service', '')))
            self.result_table.setItem(row, 4, QTableWidgetItem(vuln.get('version', '')))
            self.result_table.setItem(row, 5, QTableWidgetItem(vuln.get('cve_id', 'N/A')))
            self.result_table.setItem(row, 6, QTableWidgetItem(vuln.get('severity', 'INFO')))

            cvss = vuln.get('cvss_score', '')
            self.result_table.setItem(row, 7, QTableWidgetItem(str(cvss) if cvss else ''))

            desc = vuln.get('description', '')[:80]
            self.result_table.setItem(row, 8, QTableWidgetItem(desc))

            # 根据严重程度着色
            severity = vuln.get('severity', 'INFO')
            if severity in ['CRITICAL', 'HIGH']:
                for col in range(9):
                    self.result_table.item(row, col).setBackground(QColor(255, 200, 200))
            elif severity == 'MEDIUM':
                for col in range(9):
                    self.result_table.item(row, col).setBackground(QColor(255, 255, 200))

        # 保存扫描结果到数据库
        for vuln in result.get('vulnerabilities', []):
            self.db.add_scan_result(task_id, vuln)

        # 输出摘要
        summary = result.get('summary', {})
        self.log_message(f"\n扫描完成!")
        self.log_message(f"总发现: {summary.get('total', 0)} 个项目")
        self.log_message(f"高危/严重: {summary.get('high_critical', 0)} 个")
        self.log_message(f"耗时: {result.get('duration', 0):.2f} 秒")

        # 更新UI状态
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_progress.setVisible(False)

        QMessageBox.information(self, '扫描完成', f"扫描完成，发现 {vuln_count} 个项目")

    def on_scan_error(self, error):
        """扫描错误"""
        self.log_message(f"错误: {error}")
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_progress.setVisible(False)

        QMessageBox.critical(self, '扫描错误', error)

    def search_cve(self):
        """搜索CVE"""
        keyword = self.cve_search_input.text().strip()

        # 支持自定义limit，默认10000
        results = self.db.search_cve(keyword=keyword, limit=10000)

        self.cve_table.setRowCount(0)
        for cve in results:
            row = self.cve_table.rowCount()
            self.cve_table.insertRow(row)

            self.cve_table.setItem(row, 0, QTableWidgetItem(cve.get('cve_id', '')))
            self.cve_table.setItem(row, 1, QTableWidgetItem(cve.get('name', '')))
            self.cve_table.setItem(row, 2, QTableWidgetItem(cve.get('severity', '')))
            self.cve_table.setItem(row, 3, QTableWidgetItem(str(cve.get('cvss_score', ''))))
            self.cve_table.setItem(row, 4, QTableWidgetItem(str(cve.get('published_date', ''))[:4]))
            self.cve_table.setItem(row, 5, QTableWidgetItem(', '.join(cve.get('affected_products', [])[:3])))
            self.cve_table.setItem(row, 6, QTableWidgetItem(cve.get('description', '')[:100]))

            # 着色
            severity = cve.get('severity', '')
            if severity in ['CRITICAL']:
                for col in range(7):
                    self.cve_table.item(row, col).setBackground(QColor(255, 180, 180))
            elif severity == 'HIGH':
                for col in range(7):
                    self.cve_table.item(row, col).setBackground(QColor(255, 220, 180))

    def on_cve_table_clicked(self, item):
        """CVE表格点击事件 - 显示详情"""
        row = item.row()

        # 获取CVE ID
        cve_id = self.cve_table.item(row, 0).text() if self.cve_table.item(row, 0) else ''

        if not cve_id:
            return

        # 从数据库获取完整CVE信息
        results = self.db.search_cve(keyword=cve_id, limit=1)

        if results:
            cve = results[0]

            # 获取受影响产品
            products = cve.get('affected_products', [])
            if isinstance(products, list):
                products_str = ', '.join(products)
            else:
                products_str = str(products)

            # 获取引用链接
            refs = cve.get('references', [])
            if isinstance(refs, list):
                refs_str = '\n'.join([f'- {r}' for r in refs[:5]])
            else:
                refs_str = str(refs)

            detail = f"""===== CVE详细信息 =====

【基本信息】
CVE ID: {cve.get('cve_id', 'N/A')}
名称: {cve.get('name', 'N/A')}
严重程度: {cve.get('severity', 'UNKNOWN')}
CVSS评分: {cve.get('cvss_score', 'N/A')}

【时间信息】
发布时间: {cve.get('published_date', 'N/A')}
更新时间: {cve.get('modified_date', 'N/A')}

【漏洞详情】
受影响产品: {products_str}

漏洞描述:
{cve.get('description', '暂无描述')}

【参考链接】
{refs_str}

【AI分析】
{cve.get('ai_analysis', '暂无AI分析')}
"""
            self.cve_detail_text.setText(detail)

    def browse_code_path(self):
        """浏览代码路径"""
        path = QFileDialog.getExistingDirectory(self, '选择代码目录')
        if path:
            self.code_path_input.setText(path)

    def start_ai_audit(self):
        """开始AI审计"""
        path = self.code_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, '警告', '请输入代码路径')
            return

        self.audit_progress.setVisible(True)
        self.audit_progress.setValue(0)

        # 启动AI审计线程
        self.audit_thread = AIAnalysisThread(
            self.ai_analyzer, path, self.audit_type_combo.currentText()
        )
        self.audit_thread.progress.connect(lambda m: self.log_message(m))
        self.audit_thread.finished.connect(self.on_audit_finished)
        self.audit_thread.error.connect(lambda e: self.on_audit_error(e))
        self.audit_thread.start()

    def on_audit_finished(self, result):
        """审计完成"""
        self.audit_progress.setValue(100)
        self.audit_progress.setVisible(False)

        # 显示结果
        self.audit_detail_text.setText(result)
        self.log_message("AI审计完成")

    def on_audit_error(self, error):
        """审计错误"""
        self.audit_progress.setVisible(False)
        QMessageBox.critical(self, '审计错误', error)

    def update_threat_intel(self):
        """更新威胁情报"""
        self.threat_intel_log.clear()
        self.threat_intel_log.append("开始更新CVE数据库...")

        self.update_thread = ThreatIntelUpdateThread(self.threat_intel)
        self.update_thread.progress.connect(lambda m: self.threat_intel_log.append(m))
        self.update_thread.finished.connect(self.on_threat_intel_updated)
        self.update_thread.error.connect(lambda e: self.threat_intel_log.append(f"错误: {e}"))
        self.update_thread.start()

    def on_threat_intel_updated(self, count):
        """威胁情报更新完成"""
        self.threat_intel_log.append(f"\n更新完成! 新增 {count} 条CVE")
        self.update_status_label.setText(f'上次更新: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    def load_tasks(self):
        """加载任务列表"""
        tasks = self.db.get_all_tasks()

        self.task_table.setRowCount(0)
        for task in tasks[:50]:  # 显示最近50个
            row = self.task_table.rowCount()
            self.task_table.insertRow(row)

            self.task_table.setItem(row, 0, QTableWidgetItem(str(task.get('id'))))
            self.task_table.setItem(row, 1, QTableWidgetItem(task.get('target', '')))
            self.task_table.setItem(row, 2, QTableWidgetItem(task.get('scan_type', '')))

            status = task.get('status', '')
            self.task_table.setItem(row, 3, QTableWidgetItem(status))

            if status == 'completed':
                self.task_table.setItem(row, 4, QTableWidgetItem(str(task.get('vulnerabilities_found', 0))))

            self.task_table.setItem(row, 5, QTableWidgetItem(task.get('start_time', '')[:19] if task.get('start_time') else ''))

    def update_stats(self):
        """更新统计信息"""
        try:
            stats = self.db.get_statistics()

            self.total_cve_label.setText(f"CVE总数: {stats.get('total_cves', 0)}")

            severity = stats.get('cve_by_severity', {})
            self.critical_cve_label.setText(f"严重: {severity.get('CRITICAL', 0)}")
            self.high_cve_label.setText(f"高危: {severity.get('HIGH', 0)}")
            self.medium_cve_label.setText(f"中危: {severity.get('MEDIUM', 0)}")

        except Exception as e:
            logger.error(f"更新统计失败: {e}")

    def update_status_bar(self):
        """更新状态栏"""
        self.status_bar.showMessage(f"就绪 | CVE库: {self.db.get_statistics().get('total_cves', 0)}")

    def log_message(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def export_report(self):
        """导出报告"""
        from report_generator import generate_scan_report, export_vuln_database

        # 选择导出类型
        dialog = QDialog(self)
        dialog.setWindowTitle('导出报告')
        dialog.setMinimumSize(400, 250)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel('选择导出内容:'))

        # 导出选项
        self.export_type = 'scan'  # 默认
        scan_radio = QRadioButton('扫描报告 (当前扫描结果)')
        scan_radio.setChecked(True)
        scan_radio.toggled.connect(lambda: setattr(self, 'export_type', 'scan'))
        layout.addWidget(scan_radio)

        db_radio = QRadioButton('漏洞库报告 (全部CVE数据)')
        db_radio.toggled.connect(lambda: setattr(self, 'export_type', 'database'))
        layout.addWidget(db_radio)

        layout.addWidget(QLabel('选择输出格式:'))

        # 格式选项
        format_layout = QHBoxLayout()
        html_check = QCheckBox('HTML')
        html_check.setChecked(True)
        format_layout.addWidget(html_check)

        pdf_check = QCheckBox('PDF (可选安装 weasyprint/xhtml2pdf/pdfkit)')
        format_layout.addWidget(pdf_check)
        layout.addLayout(format_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('导出')
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        if dialog.exec_() != QDialog.Accepted:
            return

        formats = []
        if html_check.isChecked():
            formats.append('html')
        if pdf_check.isChecked():
            formats.append('pdf')

        try:
            if self.export_type == 'database':
                # 导出漏洞库
                output_path = f'vuln_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
                html_path = export_vuln_database(self.db, output_path)
                QMessageBox.information(self, '成功', f'漏洞库报告已导出:\n{html_path}')
            else:
                # 导出扫描结果 - 获取当前任务结果
                tasks = self.db.get_all_tasks()
                if not tasks:
                    QMessageBox.warning(self, '警告', '没有扫描记录')
                    return

                # 获取最新的扫描结果
                latest_task = tasks[0]
                task_id = latest_task['id']
                results = self.db.get_task_results(task_id)

                if not results:
                    QMessageBox.warning(self, '警告', '没有扫描结果')
                    return

                # 构建扫描数据
                scan_data = {
                    'target': latest_task['target'],
                    'start_time': latest_task.get('start_time', ''),
                    'end_time': latest_task.get('end_time', ''),
                    'duration': 10.0,  # 简化
                    'vulnerabilities': results,
                    'summary': {
                        'total': len(results),
                        'by_severity': {}
                    }
                }

                # 统计严重程度
                for r in results:
                    sev = r.get('severity', 'INFO')
                    if sev not in scan_data['summary']['by_severity']:
                        scan_data['summary']['by_severity'][sev] = 0
                    scan_data['summary']['by_severity'][sev] += 1

                # 生成报告
                output_dir = 'reports'
                os.makedirs(output_dir, exist_ok=True)
                output_files = generate_scan_report(scan_data, output_dir, formats)

                # 显示结果
                result_text = '\n'.join([f'{k}: {v}' for k, v in output_files.items()])
                QMessageBox.information(self, '成功', f'报告已导出:\n{result_text}')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出失败: {str(e)}')

    def clear_database(self):
        """清空数据库"""
        reply = QMessageBox.question(
            self, '确认',
            '确定要清空所有数据吗？此操作不可恢复！',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.db.clear_database()
            QMessageBox.information(self, '完成', '数据库已清空')

    def show_about(self):
        """显示关于"""
        QMessageBox.about(
            self, '关于',
            'AI Vuln Scanner Pro\n\n'
            '下一代智能漏洞扫描系统\n'
            '版本: 1.0.0\n\n'
            '功能:\n'
            '- 网络漏洞扫描\n'
            '- AI代码安全审计\n'
            '- 自动化漏洞情报收集\n'
            '- CVE数据库管理\n\n'
            'Powered by Claude Code Security'
        )

    def save_settings(self):
        """保存设置"""
        # 保存API Key到环境变量
        if self.anthropic_key_input.text():
            os.environ['ANTHROPIC_API_KEY'] = self.anthropic_key_input.text()

        if self.nvd_key_input.text():
            os.environ['NVD_API_KEY'] = self.nvd_key_input.text()

        # 保存到数据库
        self.db.save_setting('timeout', str(self.timeout_spin.value()))
        self.db.save_setting('concurrent', str(self.concurrent_spin.value()))

        QMessageBox.information(self, '完成', '设置已保存')


def main():
    """主函数"""
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # ���置���体
    font = QFont('Microsoft YaHei', 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()