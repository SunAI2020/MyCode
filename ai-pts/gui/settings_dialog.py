# -*- coding: utf-8 -*-
"""设置对话框（报告目录/API密钥/首选项/定时扫描）与登录对话框。"""
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QSpinBox, QLabel, QGroupBox, QFileDialog,
    QDialogButtonBox, QMessageBox,
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
        lay.addWidget(api_group)

        pref_group = QGroupBox("首选项")
        pl = QFormLayout(pref_group)
        self.scan_mode_combo = QComboBox()
        self.scan_mode_combo.addItem("Full（1-65535）", "full")
        self.scan_mode_combo.addItem("Quick（常用端口）", "quick")
        self.scan_mode_combo.addItem("Custom（自定义）", "custom")
        pl.addRow("扫描模式:", self.scan_mode_combo)
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

        sched_group = QGroupBox("定时扫描")
        sl = QHBoxLayout(sched_group)
        self.schedule_check = QCheckBox("启用定时扫描")
        sl.addWidget(self.schedule_check)
        sl.addWidget(QLabel("间隔(分钟):"))
        self.schedule_spin = QSpinBox()
        self.schedule_spin.setRange(1, 1440)
        self.schedule_spin.setValue(60)
        sl.addWidget(self.schedule_spin)
        sl.addStretch(1)
        lay.addWidget(sched_group)

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
        mode = prefs.get("scan_mode", "full")
        idx = self.scan_mode_combo.findData(mode)
        if idx >= 0:
            self.scan_mode_combo.setCurrentIndex(idx)
        self.ai_analysis_check.setChecked(bool(prefs.get("ai_analysis_enabled", False)))
        intensity = prefs.get("attack_intensity", "中")
        if intensity in ("低", "中", "高"):
            self.intensity_combo.setCurrentText(intensity)
        self.username_edit.setText(prefs.get("username", ""))
        self.password_edit.setText(prefs.get("password", ""))
        sched = self.settings.get("scheduled_scan", {}) or {}
        self.schedule_check.setChecked(bool(sched.get("enabled", False)))
        try:
            interval = int(sched.get("interval_minutes", 60))
        except (TypeError, ValueError):
            interval = 60
        self.schedule_spin.setValue(interval)

    def _on_accept(self):
        self.settings["report_dir"] = self.report_dir_edit.text().strip()
        self.settings["api_key"] = self.api_key_edit.text().strip()
        self.settings["preferences"] = {
            "scan_mode": self.scan_mode_combo.currentData(),
            "ai_analysis_enabled": self.ai_analysis_check.isChecked(),
            "attack_intensity": self.intensity_combo.currentText(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
        }
        self.settings["scheduled_scan"] = {
            "enabled": self.schedule_check.isChecked(),
            "interval_minutes": self.schedule_spin.value(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return self.settings


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
