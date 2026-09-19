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
    QListWidgetItem, QApplication, QStyle, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot, QProcess, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette, QTextCursor, QPixmap

logger = logging.getLogger(__name__)


# ================== 扫描线程 ==================
class ScanThread(QThread):
    """后台扫描线程"""
    progress = pyqtSignal(str, int)  # message, percentage
    result_ready = pyqtSignal(dict)  # scan result
    error = pyqtSignal(str)  # error message
    log_message = pyqtSignal(str)  # log message

    def __init__(self, target: str, ports: str = None,
                 version_detect: bool = True, os_detect: bool = False,
                 web_scan: bool = False, weak_pass: bool = False, parent=None):
        super().__init__(parent)
        self.target = target
        self.ports = ports
        self.version_detect = version_detect
        self.os_detect = os_detect
        self.web_scan = web_scan
        self.weak_pass = weak_pass
        self._running = True

    def run(self):
        """执行扫描"""
        try:
            self.progress.emit("初始化扫描器...", 5)
            self.log_message.emit(f"[*] 扫描目标: {self.target}")
            self.log_message.emit(f"[*] 端口范围: {self.ports or '默认'}")
            self.log_message.emit(
                f"[*] 扫描选项: 版本检测={self.version_detect}, OS检测={self.os_detect}, "
                f"Web扫描={self.web_scan}, 弱口令爆破={self.weak_pass}")

            # 导入扫描模块
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from core.scanner import create_engine

            engine = create_engine()

            self.progress.emit("正在扫描...", 30)

            # 执行扫描
            result = engine.scan_sync(
                target=self.target,
                ports=self.ports,
                version_detect=self.version_detect,
                os_detect=self.os_detect,
                web_scan=self.web_scan,
                weak_pass=self.weak_pass,
            )

            self.progress.emit("处理结果...", 80)

            # 转换为字典（保留完整字段 + web_findings + scan_config，供报告使用）
            result_dict = {
                "hosts": [
                    {
                        "ip": h.ip,
                        "status": h.status,
                        "hostname": h.hostname,
                        "mac": h.mac,
                        "vendor": h.vendor,
                        "os": h.os,
                        "os_accuracy": h.os_accuracy,
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
                        "version": s.version,
                        "banner": s.banner,
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
                        "cwe_id": v.cwe_id,
                        "host": v.host,
                        "port": v.port,
                        "service": v.service,
                        "protocol": v.protocol,
                        "finding_type": v.finding_type,
                        "affected_versions": v.affected_versions,
                        "references_url": v.references_url,
                        "patch_link": v.patch_link,
                        "match_confidence": v.match_confidence,
                        "matched_by": v.matched_by,
                        "evidence": v.evidence,
                        "remediation": v.remediation,
                    }
                    for v in result.vulnerabilities
                ],
                "statistics": result.statistics,
                "web_findings": result.web_findings,
                "scan_config": result.scan_config,
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
                 whitelist: List[str], credentials: dict = None,
                 credential_callback=None, plan_only: bool = False,
                 plan_dict: dict = None, parent=None):
        super().__init__(parent)
        self.services = services
        self.vulns = vulns
        self.api_key = api_key
        self.whitelist = whitelist
        self.credentials = credentials or {}
        self.credential_callback = credential_callback
        self.plan_only = plan_only
        self.plan_dict = plan_dict

    def run(self):
        try:
            from core.orchestrator import create_orchestrator
            from core.workflow import WorkflowBuilder
            import asyncio

            plan_dict = self.plan_dict
            if not plan_dict:
                # 未提供已规划方案时，调用 AI 现场规划
                self.progress.emit("AI 规划攻击路径...")
                from core.ai_analyzer import create_analyzer, ScannedService, Vulnerability
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
                            "tool": s.tool,
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

            # 仅规划模式：不执行，只把归一化后的攻击方案回传展示
            if self.plan_only:
                from core.workflow import resolve_step_targets
                steps = WorkflowBuilder.from_ai_plan(plan_dict)
                steps = resolve_step_targets(steps, self.whitelist)
                self.result_ready.emit({
                    "plan": plan_dict,
                    "steps": steps,
                })
                return

            self.progress.emit(f"执行 {len(plan_dict['steps'])} 步攻击链...")
            # 已在执行前整体确认，故 require_confirmation=False；白名单 fail-closed 仍生效
            orch = create_orchestrator(
                api_key=self.api_key,
                require_confirmation=False,
                whitelist=self.whitelist,
                credential_callback=self.credential_callback,
            )
            from core.workflow import resolve_step_targets
            steps = WorkflowBuilder.from_ai_plan(plan_dict)
            # 与 CLI 路径保持一致：把 AI 的描述性 target 归一化为真实主机 IP
            steps = resolve_step_targets(steps, self.whitelist)
            wf = orch.build_workflow(plan_dict)
            wf.create_workflow(plan_dict["plan_id"], steps)
            wf_result = asyncio.run(wf.execute({"credentials": self.credentials}))

            self.result_ready.emit({
                "plan": plan_dict,
                "steps": steps,  # 归一化后的步骤（resolve_step_targets + route_ai_steps 后）
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


# ================== 状态动画区 ==================
class StatusAnimation(QFrame):
    """中间动画区：emoji + 文字 + QTimer 帧切换展示系统工作状态。

    「位移/活动」用 QTimer 在两帧 emoji 间循环切换来模拟，无外部图片素材依赖。
    """

    SCENES = {
        "idle": ("🛡️", "就绪，等待开始扫描"),
        "scan": ("🔍", "正在扫描主机端口，寻找漏洞…"),
        "version": ("📋", "核实操作系统与数据库版本…"),
        "plan": ("🧠", "AI 规划攻击链路…"),
        "execute": ("💻", "执行攻击 / 横向移动中…"),
        "report": ("📄", "生成渗透测试报告…"),
        "done": ("✅", "完成"),
    }
    # 场景 → 帧序列（循环切换，模拟位移动态）
    FRAMES = {
        "scan": ["🔍", "🔎"],
        "version": ["📋", "📑"],
        "plan": ["🧠", "💭"],
        "execute": ["💻", "🖥️"],
        "report": ["📄", "📝"],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(150)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)

        self._emoji = QLabel("🛡️")
        self._emoji.setAlignment(Qt.AlignCenter)
        self._emoji.setStyleSheet("font-size: 56px;")
        lay.addWidget(self._emoji)

        self._text = QLabel("就绪，等待开始扫描")
        self._text.setAlignment(Qt.AlignCenter)
        self._text.setStyleSheet("font-size: 14px; color: #666;")
        lay.addWidget(self._text)

        # 帧切换（模拟位移/活动）
        self._frames: list = []
        self._frame_idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

    def set_scene(self, key: str, text: str = None):
        """切换动画场景；未知 key 回退 idle。"""
        emoji, default_text = self.SCENES.get(key, self.SCENES["idle"])
        self._frames = self.FRAMES.get(key, [emoji])
        self._frame_idx = 0
        self._emoji.setText(emoji)
        self._text.setText(text or default_text)
        if len(self._frames) > 1:
            self._timer.start(600)
        else:
            self._timer.stop()

    def _next_frame(self):
        if not self._frames:
            return
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        self._emoji.setText(self._frames[self._frame_idx])


# ================== 主窗口 ==================
class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.scan_thread: Optional[ScanThread] = None
        self.ai_thread: Optional[AIAnalysisThread] = None
        self.exploit_thread: Optional[ExploitChainThread] = None
        self.scan_results: dict = {}
        self.ai_analysis: dict = {}
        self.attack_results: dict = {}
        self.api_key: str = ""

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("AI渗透测试系统 V1.0")
        self.setGeometry(100, 100, 1500, 950)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部栏 + 扫描配置栏
        root.addWidget(self.create_top_bar())
        root.addWidget(self.create_scan_config())

        # 三栏主体
        body = QHBoxLayout()
        body.setContentsMargins(4, 4, 4, 4)
        body.setSpacing(4)
        body.addWidget(self.create_nav_panel())       # 左导航
        body.addWidget(self.create_center_panel(), 1)  # 中间动画 + 信息
        body.addWidget(self.create_tool_panel())       # 右侧工具栏
        root.addLayout(body, 1)

        # 菜单栏 / 工具栏 / 状态栏
        self.create_menu_bar()
        self.create_toolbar()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        self.animation.set_scene("idle")
        self.set_stage("目标扫描")

    # ---- 顶部栏 ----
    def create_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet("QFrame { background: #1a2b3c; }")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 6, 14, 6)

        # 标题居中（左右各一个等距 stretch）
        lay.addStretch(1)
        title = QLabel("AI渗透测试系统 V1.0")
        title.setStyleSheet("color: white; font-size: 22px; font-weight: bold;")
        lay.addWidget(title)
        lay.addStretch(1)

        # LOGO + 版权信息 + API 状态 + 退出（居右）
        self.logo_label = QLabel()
        logo_path = Path(__file__).parent / "logo.jpg"
        if logo_path.exists():
            self.logo_label.setPixmap(QPixmap(str(logo_path)).scaledToHeight(44, Qt.SmoothTransformation))
        else:
            self.logo_label.setText("🔐")
            self.logo_label.setStyleSheet("font-size: 31px;")
        lay.addWidget(self.logo_label)

        copy = QLabel("© 山西有信网安科技有限公司")
        copy.setStyleSheet("color: #cfe0ef; font-size: 15px;")
        lay.addWidget(copy)

        self.api_status_label = QLabel("API: 未配置")
        self.api_status_label.setStyleSheet("color: #cfe0ef; font-size: 15px;")
        lay.addWidget(self.api_status_label)

        self.exit_btn = QPushButton("✕")
        self.exit_btn.setFixedSize(36, 36)
        self.exit_btn.setToolTip("退出")
        self.exit_btn.clicked.connect(self.close)
        lay.addWidget(self.exit_btn)
        return bar

    # ---- 扫描配置栏 ----
    def create_scan_config(self) -> QWidget:
        bar = QFrame()
        check_svg = str(Path(__file__).parent / "check_green.svg").replace("\\", "/")
        bar.setStyleSheet(f"""
            QFrame {{ background: #ffffff; border-bottom: 1px solid #e0e0e0; }}
            QLabel, QCheckBox {{ color: #000000; font-size: 16px; }}
            QLineEdit, QComboBox {{ font-size: 16px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border: 2px solid #888888; border-radius: 3px; background: #ffffff; }}
            QCheckBox::indicator:checked {{ background: #ffffff; border-color: #2ecc71; image: url({check_svg}); }}
            QComboBox QAbstractItemView {{ background: #000000; color: #ffffff; selection-background-color: #1abc9c; }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 8, 14, 8)

        lay.addWidget(QLabel("扫描目标:"))
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("IP / CIDR / 域名 / IP段")
        self.target_input.setMinimumWidth(220)
        lay.addWidget(self.target_input, 1)

        lay.addWidget(QLabel("端口范围:"))
        self.port_mode_combo = QComboBox()
        self.port_mode_combo.addItem("full（1-65535）", "full")
        self.port_mode_combo.addItem("quick（常用端口）", "quick")
        self.port_mode_combo.addItem("custom（自定义）", "custom")
        self.port_mode_combo.currentIndexChanged.connect(self._on_port_mode_changed)
        lay.addWidget(self.port_mode_combo)

        self.port_input = QLineEdit("1-65535")
        self.port_input.setFixedWidth(200)
        self.port_input.setEnabled(False)
        lay.addWidget(self.port_input)

        self.version_check = QCheckBox("版本检测"); self.version_check.setChecked(True)
        self.os_check = QCheckBox("OS检测")
        self.web_scan_check = QCheckBox("Web扫描")
        self.weak_pass_check = QCheckBox("弱口令爆破")
        for cb in (self.version_check, self.os_check, self.web_scan_check, self.weak_pass_check):
            lay.addWidget(cb)
        return bar

    def _on_port_mode_changed(self):
        mode = self.port_mode_combo.currentData()
        if mode == "full":
            self.port_input.setText("1-65535")
            self.port_input.setEnabled(False)
        elif mode == "quick":
            self.port_input.setText("1-1000,3306,3389,5432,6379,8080,8443")
            self.port_input.setEnabled(False)
        else:
            self.port_input.setEnabled(True)

    # ---- 左侧导航 ----
    def create_nav_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(190)
        panel.setStyleSheet("QFrame { background: #ffffff; }")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget { background: #ffffff; border: none; color: #000000; font-size: 19px; }
            QListWidget::item { padding: 18px 10px; border-bottom: 1px solid #555555; }
            QListWidget::item:selected { background: #1abc9c; color: white; }
        """)
        self.nav_items = ["目标扫描", "扫描结果", "AI分析", "攻击链规划", "执行攻击", "生成报告", "AI修复建议"]
        for name in self.nav_items:
            self.nav_list.addItem(name)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        lay.addWidget(self.nav_list, 1)

        # 隐藏的动作按钮/历史列表：保留给既有处理器 setEnabled/addItem 引用
        self.scan_btn = QPushButton(self); self.scan_btn.hide()
        self.ai_btn = QPushButton(self); self.ai_btn.hide()
        self.exploit_btn = QPushButton(self); self.exploit_btn.hide()
        self.history_list = QListWidget(self); self.history_list.hide()
        return panel

    # ---- 中间动画 + 信息面板 ----
    def create_center_panel(self) -> QWidget:
        panel = QFrame()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # 动画行：开始按钮（左）+ 动画（中）+ 停止按钮（右）
        anim_row = QHBoxLayout()
        self.start_btn = QPushButton("开始")
        self.start_btn.setStyleSheet("QPushButton { background: #1abc9c; color: white; font-size: 22px; font-weight: bold; padding: 18px 28px; border-radius: 10px; }")
        self.start_btn.clicked.connect(self._on_start_clicked)
        anim_row.addWidget(self.start_btn)
        self.animation = StatusAnimation()
        anim_row.addWidget(self.animation, 1)
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background: #e74c3c; color: white; font-size: 16px; padding: 14px 18px; border-radius: 10px; }")
        self.stop_btn.clicked.connect(self.stop_scan)
        anim_row.addWidget(self.stop_btn)
        lay.addLayout(anim_row)

        # 进度条（动画下方、标签页上方）
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度:"))
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel("")
        progress_layout.addWidget(self.progress_label)
        lay.addLayout(progress_layout)

        # 信息面板（标签页）
        self.tabs = QTabWidget()

        results_tab = QWidget()
        results_layout = QVBoxLayout(results_tab)
        self.service_table = QTableWidget()
        self.service_table.setColumnCount(6)
        self.service_table.setHorizontalHeaderLabels(["IP", "端口", "协议", "服务", "产品", "版本"])
        self.service_count_label = QLabel("发现的服务：0")
        results_layout.addWidget(self.service_count_label)
        results_layout.addWidget(self.service_table, 2)
        self.vuln_table = QTableWidget()
        self.vuln_table.setColumnCount(5)
        self.vuln_table.setHorizontalHeaderLabels(["CVE", "严重性", "CVSS", "产品", "描述"])
        self.vuln_count_label = QLabel("发现的漏洞：0")
        results_layout.addWidget(self.vuln_count_label)
        results_layout.addWidget(self.vuln_table, 2)
        self.tabs.addTab(results_tab, "扫描结果")

        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.addWidget(QLabel("AI分析 - 漏洞优先级:"))
        self.ai_vuln_tree = QTreeWidget()
        self.ai_vuln_tree.setHeaderLabels(["漏洞", "优先级", "可利用性"])
        ai_layout.addWidget(self.ai_vuln_tree)
        self.tabs.addTab(ai_tab, "AI分析")

        path_tab = QWidget()
        path_layout = QVBoxLayout(path_tab)
        self.ai_path_tree = QTreeWidget()
        self.ai_path_tree.setHeaderLabels(["步骤", "类型", "目标"])
        path_layout.addWidget(self.ai_path_tree)
        self.tabs.addTab(path_tab, "攻击路径")

        rec_tab = QWidget()
        rec_layout = QVBoxLayout(rec_tab)
        self.ai_recommendations = QTextEdit()
        self.ai_recommendations.setReadOnly(True)
        rec_layout.addWidget(self.ai_recommendations)
        self.tabs.addTab(rec_tab, "AI修复建议")

        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        self.tabs.addTab(log_tab, "日志/详情")

        lay.addWidget(self.tabs, 1)
        return panel

    # ---- 右侧工具栏 ----
    def create_tool_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(180)
        panel.setStyleSheet("QFrame { background: #ecf0f1; border-left: 1px solid #d5dbdb; }")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tool_list = QListWidget()
        self.tool_list.setStyleSheet("""
            QListWidget { background: #ecf0f1; border: none; color: #2c3e50; font-size: 18px; }
            QListWidget::item { padding: 18px 8px; border-bottom: 1px solid #555555; }
            QListWidget::item:selected { background: #3498db; color: white; }
        """)
        for name in ["漏洞库管理", "渗透测试工具库", "渗透结果人工复核", "渗透测试工具使用方法", "报告中心", "Help"]:
            self.tool_list.addItem(name)
        self.tool_list.currentRowChanged.connect(self._on_tool_changed)
        lay.addWidget(self.tool_list)
        return panel

    # ---- 工作流导航 / 工具切换 ----
    def set_stage(self, stage: str):
        """高亮左侧导航当前阶段（程序化切换，不触发动作）。"""
        for i, name in enumerate(self.nav_items):
            if name == stage:
                self.nav_list.blockSignals(True)
                self.nav_list.setCurrentRow(i)
                self.nav_list.blockSignals(False)
                return

    def _on_nav_changed(self, row: int):
        if row < 0:
            return
        name = self.nav_items[row]
        # 仅选中/切页；具体动作由「开始」按钮触发
        if name == "扫描结果":
            self.tabs.setCurrentIndex(0)
        elif name == "AI修复建议":
            self.tabs.setCurrentIndex(3)

    def _is_busy(self) -> bool:
        """是否有扫描/AI分析/攻击链任一任务在运行。"""
        return any(
            th and th.isRunning()
            for th in (self.scan_thread, self.ai_thread, self.exploit_thread)
        )

    def _set_running(self, running: bool):
        """统一管理「开始」「停止」按钮可用态。"""
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _on_start_clicked(self):
        """点击「开始」按钮：执行当前选中导航项对应的动作。"""
        row = self.nav_list.currentRow()
        if row < 0:
            return
        name = self.nav_items[row]
        # 重入保护：任一任务运行中时禁止并发触发
        if self._is_busy():
            QMessageBox.warning(self, "提示", "有任务正在运行，请等待完成或点击「停止」后再操作。")
            return
        actions = {
            "目标扫描": self.start_scan,
            "AI分析": self.start_ai_analysis,
            "攻击链规划": self.start_attack_plan,
            "执行攻击": self.start_exploit_chain,
            "生成报告": self.export_report,
        }
        if name in actions:
            actions[name]()

    def _on_tool_changed(self, row: int):
        if row < 0:
            return
        name = self.tool_list.item(row).text()
        handlers = {
            "漏洞库管理": self.update_vuln_db,
            "渗透测试工具库": self._show_tool_library,
            "渗透结果人工复核": self._show_manual_review,
            "渗透测试工具使用方法": self._show_tool_usage,
            "报告中心": self._show_report_center,
            "Help": self.show_help,
        }
        handlers.get(name, lambda: None)()

    def _show_tool_library(self):
        try:
            from core.capabilities import CAPABILITIES
            lines = ["【渗透测试工具库】\n"]
            for etype, cap in CAPABILITIES.items():
                lines.append(f"■ {etype}：{cap.get('desc', '')}（工具：{cap.get('tool', 'manual')}）")
            self._show_info("\n".join(lines))
        except Exception as e:
            self._show_info(f"工具库加载失败: {e}")

    def _show_manual_review(self):
        self._show_info(
            "【渗透结果人工复核】\n\n"
            "对扫描/攻击发现的每一处结果，建议人工按以下方式核验：\n"
            "1. 打开报告中的漏洞详情，对照 CVE 编号在 NVD 官网核实受影响产品/版本是否匹配。\n"
            "2. 对攻击成功条目，按报告的「人工核验方法」打开对应 shell/页面，截图保存证据。\n"
            "3. 确认弱口令/开放服务等发现真实可复现，排除环境误报。\n"
            "4. 复核通过后在报告中心导出最终报告。"
        )

    def _show_tool_usage(self):
        self._show_info(
            "【渗透测试工具使用方法】\n\n"
            "Nmap：端口/服务/版本识别（-sV -T4）\n"
            "Web扫描器：SQLi/XSS/SSRF/XXE/路径遍历等 45+ 项主动检测\n"
            "弱口令爆破器：SSH/FTP/MySQL/PostgreSQL/Redis/MongoDB/HTTP/RDP/Telnet\n"
            "Metasploit：getshell（msfconsole）\n"
            "Impacket：wmiexec/psexec/secretsdump\n"
            "NetExec：横向移动；BloodHound：域攻击路径；Mimikatz：凭据提取"
        )

    def _report_dir(self) -> Path:
        """报告统一输出目录（项目根 reports/）。"""
        return Path(__file__).parent.parent / "reports"

    def _show_report_center(self):
        report_dir = self._report_dir()
        files = []
        if report_dir.exists():
            files = sorted(
                [str(p) for p in report_dir.glob("*.html")] +
                [str(p) for p in report_dir.glob("*.json")]
            )
        if not files:
            self._show_info("【报告中心】\n\n暂无报告。扫描后点「生成报告」导出。")
            return
        self._show_info("【报告中心】\n\n" + "\n".join(files))

    def _show_info(self, text: str):
        """在日志/详情标签页展示文本。"""
        self.log_text.setPlainText(text)
        self.tabs.setCurrentIndex(4)

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

        style = self.style()
        toolbar.addAction(style.standardIcon(QStyle.SP_MediaPlay), "开始", self.start_scan)
        toolbar.addAction(style.standardIcon(QStyle.SP_MediaStop), "停止", self.stop_scan)
        toolbar.addSeparator()
        toolbar.addAction(style.standardIcon(QStyle.SP_DialogOpenButton), "导入", self.open_targets)
        toolbar.addAction(style.standardIcon(QStyle.SP_DialogSaveButton), "导出", self.export_report)
        toolbar.addSeparator()

    # ================== 扫描相关 ==================
    def start_scan(self):
        """开始扫描"""
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, "警告", "请输入扫描目标")
            return

        ports = self.port_input.text().strip() or None

        # 更新UI
        self._set_running(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("初始化...")

        # 清空结果（含上一轮攻击链方案与AI分析，避免串到新目标）
        self.service_table.setRowCount(0)
        self.vuln_table.setRowCount(0)
        self.scan_results = {}
        self.ai_analysis = {}
        self.attack_results = {}

        # 启动扫描线程
        self.scan_thread = ScanThread(
            target, ports,
            version_detect=self.version_check.isChecked(),
            os_detect=self.os_check.isChecked(),
            web_scan=self.web_scan_check.isChecked(),
            weak_pass=self.weak_pass_check.isChecked(),
        )
        self.scan_thread.progress.connect(self.update_progress)
        self.scan_thread.result_ready.connect(self.on_scan_complete)
        self.scan_thread.error.connect(self.on_scan_error)
        self.scan_thread.log_message.connect(self.append_log)
        self.scan_thread.start()

        self.animation.set_scene("scan")
        self.set_stage("扫描结果")
        self.tabs.setCurrentIndex(4)
        self.status_bar.showMessage(f"正在扫描 {target}...")

    def stop_scan(self):
        """停止当前任务（扫描/AI分析/攻击链任一）。

        扫描线程支持优雅 stop()；AI/攻击链线程无协作式取消，退化为
        requestInterruption + terminate()（已执行前整体确认 + 白名单 fail-closed 兜底）。
        """
        for th in (self.scan_thread, self.ai_thread, self.exploit_thread):
            if th and th.isRunning():
                if hasattr(th, "stop"):
                    th.stop()
                else:
                    th.requestInterruption()
                    th.terminate()
                th.wait()
        self.scan_thread = None
        self.ai_thread = None
        self.exploit_thread = None

        self._set_running(False)
        self.status_bar.showMessage("已停止")

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

        # 计数标签
        self.service_count_label.setText(f"发现的服务：{len(services)}")
        self.vuln_count_label.setText(f"发现的漏洞：{len(vulns)}")
        self.append_log(f"[+] 扫描完成：发现 {len(services)} 个服务、{len(vulns)} 个漏洞")
        for s in services:
            self.append_log(
                f"    端口 {s.get('port')} {s.get('service_name') or ''} "
                f"{s.get('product') or ''} {s.get('version') or ''}".strip())

        self._set_running(False)
        self.ai_btn.setEnabled(bool(services))
        self.exploit_btn.setEnabled(bool(services))

        self.animation.set_scene("done", f"扫描完成：{len(services)} 服务 / {len(vulns)} 漏洞")
        self.tabs.setCurrentIndex(0)
        self.set_stage("扫描结果")
        self.status_bar.showMessage(
            f"扫描完成: {len(services)} 个服务, {len(vulns)} 个漏洞"
        )

    def on_scan_error(self, error: str):
        """扫描错误"""
        QMessageBox.critical(self, "错误", f"扫描失败: {error}")
        self._set_running(False)
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

        self._set_running(True)
        self.status_bar.showMessage("AI分析中...")
        self.append_log("[*] 开始 AI 分析：对扫描结果进行漏洞优先级排序与攻击路径分析...")
        self.animation.set_scene("version")
        self.set_stage("AI分析")
        self.tabs.setCurrentIndex(1)

        # 启动AI分析线程
        self.ai_thread = AIAnalysisThread(services, vulns, self._effective_api_key())
        self.ai_thread.progress.connect(lambda m: self.status_bar.showMessage(m))
        self.ai_thread.result_ready.connect(self.on_ai_complete)
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def on_ai_complete(self, result: dict):
        """AI分析完成"""
        self.ai_analysis = result
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

        self._set_running(False)
        self.animation.set_scene("done", "AI 分析完成")
        self.append_log("[+] AI 分析完成")
        self.set_stage("AI分析")
        self.tabs.setCurrentIndex(1)
        self.status_bar.showMessage("AI分析完成")

    def on_ai_error(self, error: str):
        """AI分析错误"""
        QMessageBox.critical(self, "错误", f"AI分析失败: {error}")
        self._set_running(False)

    def start_attack_plan(self):
        """攻击链规划：仅调用 AI 规划攻击路径，不执行任何攻击。"""
        if not self.api_key and not self._has_env_api_key():
            self.set_api_key()
            if not self.api_key:
                return

        services = self.scan_results.get("services", [])
        vulns = self.scan_results.get("vulnerabilities", [])

        if not services:
            QMessageBox.warning(self, "警告", "没有可规划的目标数据")
            return

        hosts = sorted({s.get("host_ip", "") for s in services if s.get("host_ip")})
        if not hosts:
            QMessageBox.warning(self, "警告", "无法从扫描结果提取目标主机")
            return

        self._set_running(True)
        self.status_bar.showMessage("AI 规划攻击路径中...")
        self.append_log("[*] 开始 AI 攻击链规划：分析漏洞与服务，规划攻击策略与工具...")
        self.animation.set_scene("plan")
        self.set_stage("攻击链规划")
        self.tabs.setCurrentIndex(2)  # 攻击路径标签页

        self.exploit_thread = ExploitChainThread(services, vulns, self._effective_api_key(), hosts,
                                                 plan_only=True)
        self.exploit_thread.progress.connect(lambda m: self.status_bar.showMessage(m))
        self.exploit_thread.result_ready.connect(self.on_plan_complete)
        self.exploit_thread.error.connect(self.on_exploit_error)
        self.exploit_thread.start()

    def on_plan_complete(self, result: dict):
        """攻击链规划完成：展示 AI 规划的攻击方案（未执行）。"""
        self.attack_results = result
        plan = result.get("plan", {})
        steps = result.get("steps", [])
        self.append_log(f"[+] 攻击链规划完成：共 {len(steps)} 步")

        # 在「攻击路径」树中展示详细方案：每步 = 父项，策略/脚本/验证 = 子项
        self.ai_path_tree.clear()
        for i, s in enumerate(plan.get("steps", []), 1):
            parent = QTreeWidgetItem([
                f"第{i}步 {s.get('exploit_type')}",
                s.get("tool") or "-",
                s.get("target", ""),
            ])
            parent.setToolTip(0, s.get("description", ""))
            for label, key in (("策略", "description"), ("脚本", "payload"), ("验证", "validation_cmd")):
                val = s.get(key)
                if val:
                    parent.addChild(QTreeWidgetItem([label, "", str(val)]))
            self.ai_path_tree.addTopLevelItem(parent)
            self.append_log(
                f"    第{i}步 [{s.get('exploit_type')}] 工具={s.get('tool') or '-'} "
                f"目标={s.get('target')} - {s.get('description', '')}")

        self._set_running(False)
        self.animation.set_scene("done", "攻击链规划完成")
        self.set_stage("攻击链规划")
        self.tabs.setCurrentIndex(2)
        self.status_bar.showMessage("攻击链规划完成")

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
        # 用户名与密码分开收集，密码用掩码回显，避免在界面上明文泄露
        username, ok = QInputDialog.getText(
            self, "目标用户名",
            "输入目标用户名（留空使用默认 administrator）:",
            QLineEdit.Normal,
        )
        if not ok:
            self.append_log("[!] 用户取消了凭据输入")
            return
        password, ok = QInputDialog.getText(
            self, "目标密码",
            "输入目标密码（留空则不带密码）:",
            QLineEdit.Password,
        )
        if not ok:
            self.append_log("[!] 用户取消了凭据输入")
            return
        creds = {}
        if username.strip():
            creds["username"] = username.strip()
        if password:
            creds["password"] = password

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

        self._set_running(True)
        self.status_bar.showMessage("执行攻击链中...")
        self.animation.set_scene("execute")
        self.set_stage("执行攻击")
        self.tabs.setCurrentIndex(4)

        self.exploit_thread = ExploitChainThread(services, vulns, self._effective_api_key(), hosts, creds,
                                                credential_callback=self._credential_callback,
                                                plan_dict=self.attack_results.get("plan"))
        self.exploit_thread.progress.connect(lambda m: self.status_bar.showMessage(m))
        self.exploit_thread.result_ready.connect(self.on_exploit_complete)
        self.exploit_thread.error.connect(self.on_exploit_error)
        self.exploit_thread.start()

    def on_exploit_complete(self, result: dict):
        """攻击链执行完成"""
        self.attack_results = result
        self.append_log(f"[+] 攻击链执行完成: {result.get('status')}")
        self.append_log(f"    成功 {result.get('success_steps')} 步 / 失败 {result.get('failed_steps')} 步")
        for sr in result.get("step_results", []):
            detail = f" - {sr['error']}" if sr.get("error") else ""
            self.append_log(f"    [{sr['status']}] {sr['step_id']}{detail}")
        self._set_running(False)
        self.animation.set_scene("done", "攻击链执行完成")
        self.set_stage("执行攻击")
        self.status_bar.showMessage("攻击链执行完成")

    def on_exploit_error(self, error: str):
        """攻击链执行错误"""
        QMessageBox.critical(self, "错误", f"攻击链执行失败: {error}")
        self.append_log(f"[-] 攻击链执行失败: {error}")
        self._set_running(False)

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
        self.ai_analysis = {}
        self.attack_results = {}

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
        """导出报告（HTML，含完整章节；亦可导出 JSON）"""
        if not self.scan_results:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return

        report_dir = self._report_dir()
        report_dir.mkdir(parents=True, exist_ok=True)
        default_name = f"渗透测试报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", str(report_dir / default_name), "HTML报告 (*.html);;JSON文件 (*.json)"
        )
        if not file_path:
            return

        self.animation.set_scene("report")
        self.set_stage("生成报告")

        try:
            from core.report_builder import build_report_context, build_report_html

            # 组装攻击步骤：优先用归一化后的 steps（resolve_step_targets + route_ai_steps
            # 后的真实 target/tool），与 step_results 按 step_id 合并；无归一化数据时回退 AI 计划。
            attack_steps = []
            plan = self.attack_results.get("plan", {})
            norm_steps = self.attack_results.get("steps") or plan.get("steps", [])
            sr_map = {sr.get("step_id"): sr for sr in self.attack_results.get("step_results", [])}
            for s in norm_steps:
                sr = sr_map.get(s.get("step_id"), {})
                attack_steps.append({
                    "step_id": s.get("step_id"),
                    "order": s.get("order"),
                    "exploit_type": s.get("exploit_type"),
                    "tool": s.get("tool"),
                    "target": s.get("target"),
                    "description": s.get("description"),
                    "payload": s.get("payload") or "",
                    "validation_cmd": s.get("validation_cmd") or "",
                    "status": sr.get("status", ""),
                    "error": sr.get("error", ""),
                    "evidence": sr.get("evidence", []),
                })

            context = build_report_context(
                scan_result=self.scan_results,
                ai_analysis=self.ai_analysis,
                attack_steps=attack_steps,
            )

            if file_path.lower().endswith(".json"):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(context, f, indent=2, ensure_ascii=False, default=str)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(build_report_html(context))
            QMessageBox.information(self, "完成", f"报告已导出到 {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def update_vuln_db(self):
        """更新漏洞库"""
        QMessageBox.information(self, "更新", "正在从NVD更新漏洞库...")
        # TODO: 实现

    @staticmethod
    def _has_env_api_key() -> bool:
        """是否已有可用密钥：进程环境变量 或 本机 CC Switch 配置"""
        if os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"):
            return True
        try:
            from core.ai_analyzer import load_cc_switch_env
            env = load_cc_switch_env()
            return bool(env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY"))
        except Exception:
            return False

    def _effective_api_key(self):
        """返回实际应使用的 api_key：优先本机 CC Switch 通道，否则回退 GUI 手动保存的 key。

        用户指定「大模型用本机 CC SWITCH 的通道」，而 gui/settings.json 里可能残留
        旧的手动 key，若直接传 create_analyzer 会以最高优先级覆盖 CC Switch。这里在
        CC Switch 可用时返回 None，让 create_analyzer 走 CC Switch 回退链。
        """
        if self._has_env_api_key():
            return None
        return self.api_key or None

    def _credential_callback(self, host: str, username: str):
        """后台线程调用：经 BlockingQueuedConnection 回到主线程弹密码框。

        执行器在缺密码时通过此回调向用户索取密码，返回密码字符串或 None。
        """
        from PyQt5.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject
        try:
            return QMetaObject.invokeMethod(
                self, "_prompt_credential",
                Qt.BlockingQueuedConnection,
                Q_RETURN_ARG(str),
                Q_ARG(str, host),
                Q_ARG(str, username),
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"密码弹框失败: {e}")
            return None

    @pyqtSlot(str, str, result=str)
    def _prompt_credential(self, host: str, username: str) -> str:
        """在主线程弹出居中的密码输入框（窗口中央）。"""
        pw, ok = QInputDialog.getText(
            self,
            "输入凭据",
            f"目标 {host}（用户 {username}）需要密码：\n留空则取消该步攻击。",
            QLineEdit.Password,
        )
        return pw if ok else ""

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
    window.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()