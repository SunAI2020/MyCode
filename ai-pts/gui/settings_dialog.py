# -*- coding: utf-8 -*-
"""设置对话框（报告目录/API密钥/首选项/定时扫描）与登录对话框。"""
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QSpinBox, QLabel, QGroupBox, QFileDialog,
    QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
)
from PyQt5.QtCore import Qt

# 与 core/scanner.py 一致：vendor 加入 sys.path 后按顶层模块导入
VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


class SettingsDialog(QDialog):
    """设置对话框：报告目录 / API 密钥 / 首选项 / 定时扫描。"""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(540, 560)
        self.settings = dict(settings or {})
        self._init_ui()
        self._load()

    def _init_ui(self):
        lay = QVBoxLayout(self)

        report_group = QGroupBox("报告存储目录")
        rl = QHBoxLayout(report_group)
        self.report_dir_edit = QLineEdit()
        rl.addWidget(self.report_dir_edit)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse_report_dir)
        rl.addWidget(browse)
        lay.addWidget(report_group)

        api_group = QGroupBox("API 密钥")
        al = QFormLayout(api_group)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        al.addRow("API Key:", self.api_key_edit)
        self.nvd_api_key_edit = QLineEdit()
        self.nvd_api_key_edit.setEchoMode(QLineEdit.Password)
        self.nvd_api_key_edit.setPlaceholderText("用于漏洞库在线更新（NVD）")
        al.addRow("NVD API Key:", self.nvd_api_key_edit)
        lay.addWidget(api_group)

        pref_group = QGroupBox("首选项")
        pl = QFormLayout(pref_group)
        self.scan_mode_combo = QComboBox()
        self.scan_mode_combo.addItem("Full（1-65535）", "full")
        self.scan_mode_combo.addItem("Quick（常用端口）", "quick")
        self.scan_mode_combo.addItem("Custom（自定义）", "custom")
        pl.addRow("扫描模式:", self.scan_mode_combo)

        scan_opts = QHBoxLayout()
        self.version_detect_check = QCheckBox("版本检测")
        self.os_detect_check = QCheckBox("OS检测")
        self.web_scan_check = QCheckBox("Web扫描")
        self.weak_pass_check = QCheckBox("弱口令爆破")
        for cb in (self.version_detect_check, self.os_detect_check,
                   self.web_scan_check, self.weak_pass_check):
            scan_opts.addWidget(cb)
        scan_opts.addStretch(1)
        scan_opts_widget = QWidget()
        scan_opts_widget.setLayout(scan_opts)
        pl.addRow("扫描选项:", scan_opts_widget)

        self.ai_analysis_check = QCheckBox("扫描完成后自动启用 AI 分析")
        pl.addRow("", self.ai_analysis_check)
        self.intensity_combo = QComboBox()
        self.intensity_combo.addItems(["低", "中", "高"])
        pl.addRow("攻击强度:", self.intensity_combo)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("默认 administrator")
        pl.addRow("用户名:", self.username_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        pl.addRow("密码:", self.password_edit)
        lay.addWidget(pref_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _browse_report_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "选择报告存储目录", self.report_dir_edit.text() or ".")
        if d:
            self.report_dir_edit.setText(d)

    def _load(self):
        prefs = self.settings.get("preferences", {}) or {}
        self.report_dir_edit.setText(self.settings.get("report_dir", ""))
        self.api_key_edit.setText(self.settings.get("api_key", ""))
        self.nvd_api_key_edit.setText(self.settings.get("nvd_api_key", ""))
        mode = prefs.get("scan_mode", "full")
        idx = self.scan_mode_combo.findData(mode)
        if idx >= 0:
            self.scan_mode_combo.setCurrentIndex(idx)
        self.version_detect_check.setChecked(bool(prefs.get("version_detect", True)))
        self.os_detect_check.setChecked(bool(prefs.get("os_detect", False)))
        self.web_scan_check.setChecked(bool(prefs.get("web_scan", False)))
        self.weak_pass_check.setChecked(bool(prefs.get("weak_pass", False)))
        self.ai_analysis_check.setChecked(bool(prefs.get("ai_analysis_enabled", False)))
        intensity = prefs.get("attack_intensity", "中")
        if intensity in ("低", "中", "高"):
            self.intensity_combo.setCurrentText(intensity)
        self.username_edit.setText(prefs.get("username", ""))
        self.password_edit.setText(prefs.get("password", ""))
    def _on_accept(self):
        self.settings["report_dir"] = self.report_dir_edit.text().strip()
        self.settings["api_key"] = self.api_key_edit.text().strip()
        self.settings["nvd_api_key"] = self.nvd_api_key_edit.text().strip()
        self.settings["preferences"] = {
            "scan_mode": self.scan_mode_combo.currentData(),
            "ai_analysis_enabled": self.ai_analysis_check.isChecked(),
            "attack_intensity": self.intensity_combo.currentText(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "version_detect": self.version_detect_check.isChecked(),
            "os_detect": self.os_detect_check.isChecked(),
            "web_scan": self.web_scan_check.isChecked(),
            "weak_pass": self.weak_pass_check.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return self.settings


class ScheduledTaskDialog(QDialog):
    """定时任务管理：增删多任务（名称/目标/周期/启用），持久化到 SQLite。"""

    def __init__(self, store, on_changed=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.on_changed = on_changed
        self.setWindowTitle("定时任务管理")
        self.resize(660, 440)
        self._init_ui()
        self._reload()

    def _init_ui(self):
        lay = QVBoxLayout(self)

        form = QHBoxLayout()
        form.addWidget(QLabel("名称:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：每日巡检")
        form.addWidget(self.name_edit)
        form.addWidget(QLabel("目标:"))
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("IP / CIDR / 域名")
        form.addWidget(self.target_edit, 1)
        form.addWidget(QLabel("间隔(分):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 10080)
        self.interval_spin.setValue(60)
        form.addWidget(self.interval_spin)
        self.enabled_check = QCheckBox("启用")
        self.enabled_check.setChecked(True)
        form.addWidget(self.enabled_check)
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add)
        form.addWidget(add_btn)
        lay.addLayout(form)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "名称", "目标", "间隔(分)", "启用"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnWidth(2, 200)
        lay.addWidget(self.table, 1)

        btns = QHBoxLayout()
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        toggle_btn = QPushButton("启用/停用")
        toggle_btn.clicked.connect(self._toggle)
        btns.addWidget(toggle_btn)
        btns.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        lay.addLayout(btns)

    def _reload(self):
        self.table.setRowCount(0)
        for t in self.store.list():
            row = self.table.rowCount()
            self.table.insertRow(row)
            id_item = QTableWidgetItem(str(t["id"]))
            id_item.setData(Qt.UserRole, t["id"])
            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, QTableWidgetItem(t["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(t["target"]))
            self.table.setItem(row, 3, QTableWidgetItem(str(t["interval_minutes"])))
            self.table.setItem(row, 4, QTableWidgetItem("是" if t["enabled"] else "否"))

    def _add(self):
        name = self.name_edit.text().strip()
        target = self.target_edit.text().strip()
        if not name or not target:
            QMessageBox.warning(self, "提示", "请填写任务名称与目标")
            return
        self.store.add(name, target, self.interval_spin.value(),
                       self.enabled_check.isChecked())
        self.name_edit.clear()
        self.target_edit.clear()
        self._reload()
        self._notify()

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _delete(self):
        tid = self._selected_id()
        if tid is None:
            QMessageBox.information(self, "提示", "请先选中一个任务")
            return
        self.store.delete(tid)
        self._reload()
        self._notify()

    def _toggle(self):
        tid = self._selected_id()
        if tid is None:
            QMessageBox.information(self, "提示", "请先选中一个任务")
            return
        task = next((t for t in self.store.list() if t["id"] == tid), None)
        if not task:
            return
        self.store.update(tid, task["name"], task["target"],
                          task["interval_minutes"], not task["enabled"])
        self._reload()
        self._notify()

    def _notify(self):
        if self.on_changed:
            self.on_changed()


class LoginDialog(QDialog):
    """登录对话框：接入 vendor 的 users 表 + auth_rbac 密码校验。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录")
        self.resize(340, 160)
        self.user = None
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.username_edit = QLineEdit("admin")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("用户名:", self.username_edit)
        form.addRow("密码:", self.password_edit)
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _on_ok(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        try:
            from database import AssetsSystemDB
            from auth_rbac import verify_password
            db = AssetsSystemDB()
            u = db.get_user_by_username(username)
            if not u or not u.get("active"):
                QMessageBox.warning(self, "登录失败", "用户不存在或已禁用")
                db.close()
                return
            if not verify_password(password, u.get("password_hash", "")):
                QMessageBox.warning(self, "登录失败", "密码错误")
                db.close()
                return
            db.record_login(u["id"])
            db.close()
            self.user = {"username": username, "role": u.get("role", "viewer"),
                         "full_name": u.get("full_name", "")}
            self.accept()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "登录失败", f"无法连接用户库: {e}")

    def get_user(self):
        return self.user


class ApiKeyDialog(QDialog):
    """API 密钥对话框：Anthropic API Key + NVD API Key。"""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 API 密钥")
        self.resize(400, 150)
        self.settings = dict(settings or {})
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.api_key_edit = QLineEdit(self.settings.get("api_key", ""))
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self.api_key_edit)
        self.nvd_api_key_edit = QLineEdit(self.settings.get("nvd_api_key", ""))
        self.nvd_api_key_edit.setEchoMode(QLineEdit.Password)
        self.nvd_api_key_edit.setPlaceholderText("用于漏洞库在线更新（NVD）")
        form.addRow("NVD API Key:", self.nvd_api_key_edit)
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def get_api_key(self) -> str:
        return self.api_key_edit.text().strip()

    def get_nvd_api_key(self) -> str:
        return self.nvd_api_key_edit.text().strip()
