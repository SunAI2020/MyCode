"""
AI-PTS GUI - 主窗口
PyQt5实现的桌面客户端界面
"""
import sys
import os
import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QTextEdit, QLabel, QProgressBar,
    QMenuBar, QMenu, QAction, QStatusBar, QToolBar, QDockWidget,
    QGroupBox, QCheckBox, QComboBox, QSpinBox, QFileDialog,
    QMessageBox, QDialog, QInputDialog, QSplitter, QListWidget,
    QApplication, QStyle, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot, QProcess
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette, QTextCursor

logger = logging.getLogger(__name__)


# ================== 扫描线程 ==================
class ScanThread(QThread):
    """后台扫描线程"""
    progress = pyqtSignal(str, int)  # message, percentage
    result_ready = pyqtSignal(dict)  # scan result
    error = pyqtSignal(str)  # error message
    log_message = pyqtSignal(str)  # log message

    def __init__(self, target: str, ports: str = None, parent=None):
        super().__init__(parent)
        self.target = target
        self.ports = ports
        self._running = True

    def run(self):
        """执行扫描"""
        try:
            self.progress.emit("初始化扫描器...", 5)
            self.log_message.emit(f"[*] 开始扫描目标: {self.target}")

            # 导入扫描模块
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from core.scanner import create_engine

            engine = create_engine()

            self.progress.emit("正在扫描...", 30)

            # 执行扫描
            result = engine.scan_sync(
                target=self.target,
                ports=self.ports,
                version_detect=True
            )

            self.progress.emit("处理结果...", 80)

            # 转换为字典
            result_dict = {
                "hosts": [
                    {
                        "ip": h.ip,
                        "status": h.status,
                        "hostname": h.hostname
                    }
                    for h in result.hosts
                ],
                "services": [
                    {
                        "host_ip": s.host_ip,
                        "port": s.port,
                        "protocol": s.protocol,
                        "service_name": s.service_name,
                        "product": s.product,
                        "version": s.version
                    }
                    for s in result.services
                ],
                "vulnerabilities": [
                    {
                        "cve_id": v.cve_id,
                        "description": v.description,
                        "severity": v.severity,
                        "cvss_score": v.cvss_score,
                        "product": v.product,
                        "version": v.version,
                    }
                    for v in result.vulnerabilities
                ],
                "statistics": result.statistics
            }

            self.progress.emit("完成", 100)
            self.result_ready.emit(result_dict)

        except Exception as e:
            self.error.emit(str(e))
            logger.error(f"扫描失败: {e}")

    def stop(self):
        """停止扫描"""
        self._running = False


# ================== AI分析线程 ==================
class AIAnalysisThread(QThread):
    """AI分析线程"""
    progress = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, services: List, vulns: List, api_key: str, parent=None):
        super().__init__(parent)
        self.services = services
        self.vulns = vulns
        self.api_key = api_key

    def run(self):
        try:
            self.progress.emit("正在调用AI分析...")

            from core.ai_analyzer import create_analyzer, ScannedService, Vulnerability

            ai = create_analyzer(api_key=self.api_key)

            # 转换服务
            services = [
                ScannedService(
                    host_ip=s["host_ip"],
                    port=s["port"],
                    service_name=s.get("service_name", ""),
                    product=s.get("product", ""),
                    version=s.get("version", ""),
                    banner=s.get("product", "") + " " + s.get("version", "")
                )
                for s in self.services
            ]

            # 转换漏洞
            vulns = [
                Vulnerability(
                    cve_id=v["cve_id"],
                    description=v.get("description", ""),
                    severity=v.get("severity", "medium"),
                    cvss_score=v.get("cvss_score", 0),
                    product=v.get("product", ""),
                    version=v.get("version", "")
                )
                for v in self.vulns
            ]

            # 分析
            report = ai.analyze_scan_results(services, vulns)

            self.result_ready.emit({
                "vulnerabilities": report.vulnerabilities,
                "attack_paths": report.attack_paths,
                "recommendations": report.recommendations,
                "risk_summary": report.risk_summary
            })

        except Exception as e:
            self.error.emit(str(e))


# ================== 攻击链执行线程 ==================
class ExploitChainThread(QThread):
    """后台执行攻击链：AI 规划攻击路径 + 专项工具执行"""
    progress = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, services: List, vulns: List, api_key: str,
                 whitelist: List[str], credentials: dict = None, parent=None):
        super().__init__(parent)
        self.services = services
        self.vulns = vulns
        self.api_key = api_key
        self.whitelist = whitelist
        self.credentials = credentials or {}

    def run(self):
        try:
            self.progress.emit("AI 规划攻击路径...")
            from core.ai_analyzer import create_analyzer, ScannedService, Vulnerability
            from core.orchestrator import create_orchestrator
            from core.workflow import WorkflowBuilder
            import asyncio

            ai = create_analyzer(api_key=self.api_key)

            services = [
                ScannedService(
                    host_ip=s["host_ip"],
                    port=s["port"],
                    service_name=s.get("service_name", ""),
                    product=s.get("product", ""),
                    version=s.get("version", ""),
                    banner=s.get("banner", ""),
                )
                for s in self.services
            ]
            vulns = [
                Vulnerability(
                    cve_id=v["cve_id"],
                    description=v.get("description", ""),
                    severity=v.get("severity", "medium"),
                    cvss_score=v.get("cvss_score", 0),
                    product=v.get("product", ""),
                    version=v.get("version", ""),
                )
                for v in self.vulns
            ]

            plan = ai.plan_exploit_path(services, vulns, target_goal="get_shell")
            plan_dict = {
                "plan_id": plan.plan_id,
                "target": plan.target,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "order": s.order,
                        "exploit_type": s.exploit_type,
                        "target": s.target,
                        "description": s.description,
                        "payload": s.payload,
                        "validation_cmd": s.validation_cmd,
                        "risk_level": s.risk_level,
                    }
                    for s in plan.steps
                ],
            }

            if not plan_dict["steps"]:
                self.error.emit("AI 未规划出可执行步骤")
                return

            self.progress.emit(f"执行 {len(plan_dict['steps'])} 步攻击链...")
            # 已在执行前整体确认，故 require_confirmation=False；白名单 fail-closed 仍生效
            orch = create_orchestrator(
                api_key=self.api_key,
                require_confirmation=False,
                whitelist=self.whitelist,
            )
            steps = WorkflowBuilder.from_ai_plan(plan_dict)
            wf = orch.build_workflow(plan_dict)
            wf.create_workflow(plan_dict["plan_id"], steps)
            wf_result = asyncio.run(wf.execute({"credentials": self.credentials}))

            self.result_ready.emit({
                "plan": plan_dict,
                "status": wf_result.status.value,
                "success_steps": wf_result.success_steps,
                "failed_steps": wf_result.failed_steps,
                "total_time": wf_result.total_time,
                "step_results": [
                    {
                        "step_id": r.step_id,
                        "status": r.status.value,
                        "error": r.output.error,
                        "evidence": r.output.evidence,
                    }
                    for r in wf_result.step_results
                ],
            })

        except Exception as e:
            self.error.emit(str(e))


# ================== 主窗口 ==================
class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.scan_thread: Optional[ScanThread] = None
        self.ai_thread: Optional[AIAnalysisThread] = None
        self.exploit_thread: Optional[ExploitChainThread] = None
        self.scan_results: dict = {}
        self.api_key: str = ""

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("AI-PTS Penetration Testing System")
        self.setGeometry(100, 100, 1400, 900)

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)

        # 主布局
        main_layout = QHBoxLayout(central)

        # 左侧面板
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 1)

        # 右侧面板
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 2)

        # 菜单栏
        self.create_menu_bar()

        # 工具栏
        self.create_toolbar()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)

        # 目标输入
        target_group = QGroupBox("扫描目标")
        target_layout = QVBoxLayout(target_group)

        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("输入IP/CIDR/域名...")
        target_layout.addWidget(self.target_input)

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("端口范围 (如 1-1000,3306)")
        self.port_input.setText("1-1000,3306,3389,5432,6379,8080,8443")
        target_layout.addWidget(self.port_input)

        # 选项
        options_layout = QHBoxLayout()
        self.version_check = QCheckBox("版本检测")
        self.version_check.setChecked(True)
        options_layout.addWidget(self.version_check)

        self.os_check = QCheckBox("OS检测")
        options_layout.addWidget(self.os_check)
        options_layout.addStretch()

        target_layout.addLayout(options_layout)
        layout.addWidget(target_group)

        # 操作按钮
        button_layout = QHBoxLayout()
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setIcon(QStyle.SP_MediaPlay)
        self.scan_btn.clicked.connect(self.start_scan)
        button_layout.addWidget(self.scan_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scan)
        button_layout.addWidget(self.stop_btn)

        self.ai_btn = QPushButton("AI分析")
        self.ai_btn.setEnabled(False)
        self.ai_btn.clicked.connect(self.start_ai_analysis)
        button_layout.addWidget(self.ai_btn)

        self.exploit_btn = QPushButton("执行攻击链")
        self.exploit_btn.setEnabled(False)
        self.exploit_btn.clicked.connect(self.start_exploit_chain)
        button_layout.addWidget(self.exploit_btn)

        layout.addLayout(button_layout)

        # 历史记录
        history_group = QGroupBox("历史扫描")
        history_layout = QVBoxLayout(history_group)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.load_history)
        history_layout.addWidget(self.history_list)

        layout.addWidget(history_group, 1)

        return panel

    def create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)

        # 标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 结果标签页
        results_tab = QWidget()
        results_layout = QVBoxLayout(results_tab)

        # 服务表格
        self.service_table = QTableWidget()
        self.service_table.setColumnCount(6)
        self.service_table.setHorizontalHeaderLabels([
            "IP", "端口", "协议", "服务", "产品", "版本"
        ])
        results_layout.addWidget(QLabel("发现的服务:"))
        results_layout.addWidget(self.service_table, 2)

        # 漏洞表格
        self.vuln_table = QTableWidget()
        self.vuln_table.setColumnCount(5)
        self.vuln_table.setHorizontalHeaderLabels([
            "CVE", "严重性", "CVSS", "产品", "描述"
        ])
        results_layout.addWidget(QLabel("发现的漏洞:"))
        results_layout.addWidget(self.vuln_table, 2)

        self.tabs.addTab(results_tab, "扫描结果")

        # AI分析标签页
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)

        # 漏洞优先级
        ai_layout.addWidget(QLabel("AI分析 - 漏洞优先级:"))
        self.ai_vuln_tree = QTreeWidget()
        self.ai_vuln_tree.setHeaderLabels(["漏洞", "优先级", "可利用性"])
        ai_layout.addWidget(self.ai_vuln_tree, 2)

        # 攻击路径
        ai_layout.addWidget(QLabel("AI分析 - 攻击路径:"))
        self.ai_path_tree = QTreeWidget()
        self.ai_path_tree.setHeaderLabels(["步骤", "类型", "目标"])
        ai_layout.addWidget(self.ai_path_tree, 2)

        # 建议
        ai_layout.addWidget(QLabel("建议:"))
        self.ai_recommendations = QTextEdit()
        self.ai_recommendations.setReadOnly(True)
        ai_layout.addWidget(self.ai_recommendations)

        self.tabs.addTab(ai_tab, "AI分析")

        # 日志标签页
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        self.tabs.addTab(log_tab, "日志")

        # 进度条
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度:"))
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("")
        progress_layout.addWidget(self.progress_label)
        layout.addLayout(progress_layout)

        return panel

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        file_menu.addAction("新建扫描", self.new_scan)
        file_menu.addAction("打开目标列表...", self.open_targets)
        file_menu.addSeparator()
        file_menu.addAction("导出报告...", self.export_report)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close, "Ctrl+Q")

        # 扫描菜单
        scan_menu = menubar.addMenu("扫描(&S)")
        scan_menu.addAction("开始扫描", self.start_scan, "Ctrl+Enter")
        scan_menu.addAction("停止扫描", self.stop_scan, "Ctrl+C")
        scan_menu.addSeparator()
        scan_menu.addAction("AI分析", self.start_ai_analysis, "Ctrl+A")
        scan_menu.addAction("规划攻击路径", self.plan_exploit)

        # 工具菜单
        tool_menu = menubar.addMenu("工具(&T)")
        tool_menu.addAction("漏洞库更新...", self.update_vuln_db)
        tool_menu.addAction("设置API密钥...", self.set_api_key)
        tool_menu.addSeparator()
        tool_menu.addAction("首选项...", self.show_settings)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        help_menu.addAction("使用说明", self.show_help)
        help_menu.addAction("关于", self.show_about)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(QStyle.SP_MediaPlay, "开始", self.start_scan)
        toolbar.addAction(QStyle.SP_MediaStop, "停止", self.stop_scan)
        toolbar.addSeparator()
        toolbar.addAction(QStyle.SP_DialogOpenButton, "导入", self.open_targets)
        toolbar.addAction(QStyle.SP_DialogSaveButton, "导出", self.export_report)
        toolbar.addSeparator()

        # API状态
        self.api_status_label = QLabel("API: 未配置")
        toolbar.addWidget(self.api_status_label)

    # ================== 扫描相关 ==================
    def start_scan(self):
        """开始扫描"""
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, "警告", "请输入扫描目标")
            return

        ports = self.port_input.text().strip() or None

        # 更新UI
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("初始化...")

        # 清空结果
        self.service_table.setRowCount(0)
        self.vuln_table.setRowCount(0)
        self.scan_results = {}

        # 启动扫描线程
        self.scan_thread = ScanThread(target, ports)
        self.scan_thread.progress.connect(self.update_progress)
        self.scan_thread.result_ready.connect(self.on_scan_complete)
        self.scan_thread.error.connect(self.on_scan_error)
        self.scan_thread.log_message.connect(self.append_log)
        self.scan_thread.start()

        self.status_bar.showMessage(f"正在扫描 {target}...")

    def stop_scan(self):
        """停止扫描"""
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
            self.scan_thread = None

        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_bar.showMessage("扫描已停止")

    def on_scan_complete(self, result: dict):
        """扫描完成"""
        self.scan_results = result

        # 更新服务表格
        services = result.get("services", [])
        self.service_table.setRowCount(len(services))
        for i, s in enumerate(services):
            self.service_table.setItem(i, 0, QTableWidgetItem(s.get("host_ip", "")))
            self.service_table.setItem(i, 1, QTableWidgetItem(str(s.get("port", ""))))
            self.service_table.setItem(i, 2, QTableWidgetItem(s.get("protocol", "tcp")))
            self.service_table.setItem(i, 3, QTableWidgetItem(s.get("service_name", "")))
            self.service_table.setItem(i, 4, QTableWidgetItem(s.get("product", "")))
            self.service_table.setItem(i, 5, QTableWidgetItem(s.get("version", "")))

        # 漏洞（扫描引擎已匹配 CVE）
        vulns = result.get("vulnerabilities", [])
        self.vuln_table.setRowCount(len(vulns))
        for i, v in enumerate(vulns):
            self.vuln_table.setItem(i, 0, QTableWidgetItem(v.get("cve_id", "")))
            self.vuln_table.setItem(i, 1, QTableWidgetItem(v.get("severity", "")))
            self.vuln_table.setItem(i, 2, QTableWidgetItem(str(v.get("cvss_score", ""))))
            self.vuln_table.setItem(i, 3, QTableWidgetItem(v.get("product", "")))
            self.vuln_table.setItem(i, 4, QTableWidgetItem(v.get("description", "")))

        # 添加到历史
        target = self.target_input.text()
        self.history_list.addItem(f"{datetime.now().strftime('%H:%M:%S')} - {target}")

        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.ai_btn.setEnabled(bool(services))
        self.exploit_btn.setEnabled(bool(services))

        self.status_bar.showMessage(
            f"扫描完成: {len(services)} 个服务, {len(vulns)} 个漏洞"
        )

    def on_scan_error(self, error: str):
        """扫描错误"""
        QMessageBox.critical(self, "错误", f"扫描失败: {error}")
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_bar.showMessage("扫描失败")

    @pyqtSlot(str, int)
    def update_progress(self, message: str, value: int):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    # ================== AI分析相关 ==================
    def start_ai_analysis(self):
        """开始AI分析"""
        if not self.api_key and not self._has_env_api_key():
            self.set_api_key()
            if not self.api_key:
                return

        # 获取服务和漏洞
        services = self.scan_results.get("services", [])
        vulns = self.scan_results.get("vulnerabilities", [])

        if not services:
            QMessageBox.warning(self, "警告", "没有可分析的数据")
            return

        self.ai_btn.setEnabled(False)
        self.status_bar.showMessage("AI分析中...")

        # 启动AI分析线程
        self.ai_thread = AIAnalysisThread(services, vulns, self.api_key)
        self.ai_thread.progress.connect(lambda m: self.status_bar.showMessage(m))
        self.ai_thread.result_ready.connect(self.on_ai_complete)
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def on_ai_complete(self, result: dict):
        """AI分析完成"""
        # 更新漏洞树
        self.ai_vuln_tree.clear()
        vulns = result.get("vulnerabilities", [])
        for v in vulns[:20]:
            item = QTreeWidgetItem([
                v.get("cve_id", ""),
                v.get("severity", ""),
                v.get("exploitability", "")
            ])
            self.ai_vuln_tree.addTopLevelItem(item)

        # 更新攻击路径
        self.ai_path_tree.clear()
        paths = result.get("attack_paths", [])
        for path in paths:
            parent = QTreeWidgetItem([f"路径 {path.get('path_id', '')}", "", ""])
            parent.setData(0, Qt.UserRole, path)

            for step in path.get("steps", []):
                child = QTreeWidgetItem([
                    f"  {step}",
                    path.get("exploit_type", ""),
                    path.get("target", "")
                ])
                parent.addChild(child)

            self.ai_path_tree.addTopLevelItem(parent)

        # 更新建议
        recommendations = result.get("recommendations", [])
        self.ai_recommendations.setPlainText("\n".join(recommendations))

        self.ai_btn.setEnabled(True)
        self.status_bar.showMessage("AI分析完成")

    def on_ai_error(self, error: str):
        """AI分析错误"""
        QMessageBox.critical(self, "错误", f"AI分析失败: {error}")
        self.ai_btn.setEnabled(True)

    def start_exploit_chain(self):
        """执行攻击链（AI 规划 + 专项工具执行，执行前整体确认）"""
        if not self.api_key and not self._has_env_api_key():
            self.set_api_key()
            if not self.api_key:
                return

        services = self.scan_results.get("services", [])
        vulns = self.scan_results.get("vulnerabilities", [])

        if not services:
            QMessageBox.warning(self, "警告", "没有可执行的目标数据")
            return

        # 目标白名单
        hosts = sorted({s.get("host_ip", "") for s in services if s.get("host_ip")})
        if not hosts:
            QMessageBox.warning(self, "警告", "无法从扫描结果提取目标主机")
            return

        # 收集目标凭据（可选；留空则各工具退回默认 administrator）
        creds_raw, ok = QInputDialog.getText(
            self, "目标凭据",
            "输入目标凭据 user:pass（留空使用默认 administrator）:",
            QLineEdit.Normal,
        )
        creds = {}
        if ok and creds_raw.strip():
            if ":" in creds_raw:
                u, _, p = creds_raw.partition(":")
                creds = {"username": u, "password": p}
            else:
                creds = {"username": creds_raw}

        # 执行前整体确认（一次性放行）
        reply = QMessageBox.question(
            self,
            "执行攻击链确认",
            "即将对以下目标执行 AI 规划的攻击链（getshell/提权/横向移动）：\n\n"
            + "\n".join(f"  - {h}" for h in hosts)
            + "\n\n这些操作具有破坏性，仅限已授权的测试目标。\n确定继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            self.append_log("[!] 用户取消了攻击链执行")
            return

        self.exploit_btn.setEnabled(False)
        self.status_bar.showMessage("执行攻击链中...")

        self.exploit_thread = ExploitChainThread(services, vulns, self.api_key, hosts, creds)
        self.exploit_thread.progress.connect(lambda m: self.status_bar.showMessage(m))
        self.exploit_thread.result_ready.connect(self.on_exploit_complete)
        self.exploit_thread.error.connect(self.on_exploit_error)
        self.exploit_thread.start()

    def on_exploit_complete(self, result: dict):
        """攻击链执行完成"""
        self.append_log(f"[+] 攻击链执行完成: {result.get('status')}")
        self.append_log(f"    成功 {result.get('success_steps')} 步 / 失败 {result.get('failed_steps')} 步")
        for sr in result.get("step_results", []):
            detail = f" - {sr['error']}" if sr.get("error") else ""
            self.append_log(f"    [{sr['status']}] {sr['step_id']}{detail}")
        self.exploit_btn.setEnabled(True)
        self.status_bar.showMessage("攻击链执行完成")

    def on_exploit_error(self, error: str):
        """攻击链执行错误"""
        QMessageBox.critical(self, "错误", f"攻击链执行失败: {error}")
        self.append_log(f"[-] 攻击链执行失败: {error}")
        self.exploit_btn.setEnabled(True)

    def plan_exploit(self):
        """规划攻击路径（并可选执行）——复用攻击链流程"""
        self.start_exploit_chain()

    # ================== 菜单动作 ==================
    def new_scan(self):
        """新建扫描"""
        self.target_input.clear()
        self.service_table.setRowCount(0)
        self.vuln_table.setRowCount(0)
        self.scan_results = {}

    def open_targets(self):
        """打开目标列表"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开目标列表", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            with open(file_path, "r") as f:
                targets = [line.strip() for line in f if line.strip()]
            self.target_input.setText(",".join(targets))

    def export_report(self):
        """导出报告"""
        if not self.scan_results:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", "", "JSON文件 (*.json);;HTML文件 (*.html)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.scan_results, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "完成", f"报告已导出到 {file_path}")

    def update_vuln_db(self):
        """更新漏洞库"""
        QMessageBox.information(self, "更新", "正在从NVD更新漏洞库...")
        # TODO: 实现

    @staticmethod
    def _has_env_api_key() -> bool:
        """是否已通过本机 CC Switch 环境变量提供密钥"""
        return bool(os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))

    def set_api_key(self):
        """设置API密钥"""
        key, ok = QInputDialog.getText(
            self, "设置API密钥", "输入Anthropic API Key:",
            QLineEdit.Password
        )
        if ok and key:
            self.api_key = key
            self.api_status_label.setText("API: 已配置")
            self.settings["api_key"] = key
            self.save_settings()

    def show_settings(self):
        """显示设置"""
        # TODO: 实现
        pass

    def show_help(self):
        """显示帮助"""
        QMessageBox.information(
            self, "使用说明",
            "AI-PTS 使用说明:\n\n"
            "1. 输入扫描目标 (IP/CIDR/域名)\n"
            "2. 点击开始扫描\n"
            "3. 查看扫描结果\n"
            "4. 点击AI分析获取智能建议"
        )

    def show_about(self):
        """显示关于"""
        QMessageBox.about(
            self, "关于",
            "AI-PTS Penetration Testing System\n\n"
            "版本: 1.0.0\n"
            "基于AI的渗透测试工具\n\n"
            "集成了Nmap扫描和Claude AI分析"
        )

    # ================== 辅助方法 ==================
    def append_log(self, message: str):
        """追加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.moveCursor(QTextCursor.End)

    def load_history(self, item):
        """加载历史"""
        # TODO: 实现
        pass

    def load_settings(self):
        """加载设置"""
        config_path = Path(__file__).parent / "settings.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                self.settings = json.load(f)
            self.api_key = self.settings.get("api_key", "")
            if self.api_key:
                self.api_status_label.setText("API: 已配置")
        else:
            self.settings = {}

    def save_settings(self):
        """保存设置"""
        config_path = Path(__file__).parent / "settings.json"
        with open(config_path, "w") as f:
            json.dump(self.settings, f, indent=2)

    def closeEvent(self, event):
        """关闭事件"""
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置深色主题
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(35, 35, 35))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()