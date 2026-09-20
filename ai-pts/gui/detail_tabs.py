# -*- coding: utf-8 -*-
"""中间详情页新增标签：业务逻辑 / 人工复核 / 报告列表（可嵌入 QWidget）。

与 gui/tool_dialogs.py 中对应的 QDialog 并存：本模块提供常驻标签页版本，
右侧工具栏的弹窗入口保持不变。
"""
import json
import sys
import shutil
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QTextEdit, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QFormLayout, QLineEdit, QCheckBox, QScrollArea, QFrame,
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices


# ================== 纯函数辅助（便于单测） ==================

def derive_verify_action(step: dict, step_result: dict):
    """由成功步骤推导「人工复核」动作：("url", url) / ("command", cmd) / None。"""
    step_result = step_result or {}
    target = str(step.get("target") or "").strip()
    if target.lower().startswith(("http://", "https://")):
        return ("url", target)

    # 从工具解析结果里找可点击 URL（nuclei matched_at 等）
    parsed = (step_result.get("result") or {}).get("parsed") or {}
    if isinstance(parsed, dict):
        for m in parsed.get("matches") or []:
            u = m.get("matched_at") or m.get("url")
            if u:
                return ("url", str(u))

    # 验证命令 → 终端
    cmd = str(step.get("validation_cmd") or "").strip()
    if not cmd:
        ev = step_result.get("evidence") or []
        if isinstance(ev, str):
            ev = [ev]
        for e in ev:
            e = str(e).strip()
            if e.startswith("$ "):
                cmd = e[2:].strip()
                break
    if cmd:
        return ("command", cmd)
    return None


def _open_link(url: str):
    """在系统默认浏览器打开链接。"""
    webbrowser.open(url)


def _open_terminal(command: str):
    """打开新终端窗口并预载命令（Windows: cmd /k；macOS/Linux 作兜底）。"""
    if sys.platform.startswith("win"):
        # start "标题" cmd /k <命令>：新开一个窗口并保持会话
        subprocess.Popen(["cmd", "/c", "start", "人工复核", "cmd", "/k", command])
    elif sys.platform == "darwin":
        subprocess.Popen(["osascript", "-e",
                          'tell application "Terminal" to do script {}'.format(json.dumps(command))])
    else:
        subprocess.Popen(["x-terminal-emulator", "-e", "bash -lc {}".format(json.dumps(command))])


# ================== 业务逻辑标签页 ==================

class BusinessLogicTab(QWidget):
    """业务逻辑漏洞检测：内嵌完整表单，就地跑检测，结果表格展示。"""

    def __init__(self, api_key_provider=None, on_findings=None, parent=None):
        super().__init__(parent)
        self.api_key_provider = api_key_provider
        self.on_findings = on_findings
        self.thread = None
        self._last_findings = []
        self._init_ui()
        self._render([])

    def _init_ui(self):
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("如 http://target.example.com")
        form.addRow("目标 URL:", self.target_edit)

        self.endpoints_edit = QTextEdit()
        self.endpoints_edit.setPlaceholderText(
            "每行一个端点，可选方法前缀，如：\n/orders/100\n/api/users/1\nPOST /api/login")
        self.endpoints_edit.setFixedHeight(90)
        form.addRow("敏感端点:", self.endpoints_edit)

        self.owner_cookie_edit = QLineEdit()
        self.owner_cookie_edit.setPlaceholderText("owner 角色 Cookie（session=...）")
        form.addRow("Owner Cookie:", self.owner_cookie_edit)
        self.attacker_cookie_edit = QLineEdit()
        self.attacker_cookie_edit.setPlaceholderText("attacker 角色 Cookie（留空=未登录）")
        form.addRow("Attacker Cookie:", self.attacker_cookie_edit)
        lay.addLayout(form)

        self.trust_self_signed_check = QCheckBox("信任自签证书（仅授权自测环境勾选）")
        self.trust_self_signed_check.setChecked(False)
        lay.addWidget(self.trust_self_signed_check)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("开始检测")
        self.run_btn.clicked.connect(self._run)
        btn_row.addWidget(self.run_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.summary_label = QLabel("")
        lay.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["类型", "方法", "URL", "置信度", "场景", "原因"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.table, 1)

    def _parse_endpoints(self):
        endpoints = []
        for raw in self.endpoints_edit.toPlainText().splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                method, url = parts[0].upper(), parts[1]
            else:
                method, url = "GET", line
            endpoints.append({"method": method, "url": url})
        return endpoints

    def _run(self):
        from gui.tool_dialogs import BusinessLogicThread
        target = self.target_edit.text().strip()
        if not target.startswith(("http://", "https://")):
            QMessageBox.warning(self, "提示", "请输入以 http:// 或 https:// 开头的目标 URL")
            return
        endpoints = self._parse_endpoints()
        if not endpoints:
            QMessageBox.warning(self, "提示", "请输入至少一个待检测端点")
            return
        owner_cookie = self.owner_cookie_edit.text().strip()
        attacker_cookie = self.attacker_cookie_edit.text().strip()
        sessions = {
            "owner": {"headers": {"Cookie": owner_cookie}} if owner_cookie else {},
            "attacker": {"headers": {"Cookie": attacker_cookie}} if attacker_cookie else {},
        }
        api_key = self.api_key_provider() if callable(self.api_key_provider) else ""
        verify = not self.trust_self_signed_check.isChecked()

        self.run_btn.setEnabled(False)
        self.summary_label.setText("检测中，请稍候...")
        self.table.setRowCount(0)
        self.thread = BusinessLogicThread(target, endpoints, sessions, api_key, verify=verify)
        self.thread.result_ready.connect(self._on_done)
        self.thread.error.connect(self._on_error)
        self.thread.start()

    def _on_done(self, findings):
        self.run_btn.setEnabled(True)
        # 回传结果（含空结果），确保主窗口 business_logic_findings 与本次检测一致
        if callable(self.on_findings):
            try:
                self.on_findings(findings)
            except Exception:  # noqa: BLE001
                pass
        self._render(findings)

    def _on_error(self, err):
        self.run_btn.setEnabled(True)
        self.summary_label.setText(f"检测失败：{err}")
        self.table.setRowCount(0)

    def refresh(self, findings=None):
        """重渲染表格；无参时用最近一次结果。"""
        if findings is not None:
            self._last_findings = findings or []
        self._render(self._last_findings)

    def _render(self, findings):
        self._last_findings = findings or []
        type_cn = {
            "idor": "IDOR/越权",
            "access_control_bypass": "越权访问",
            "blocked": "已拦截(SSRF)",
            "error": "检测异常",
        }
        real = [f for f in self._last_findings
                if f.get("finding_type") in ("idor", "access_control_bypass")]
        self.summary_label.setText(
            f"发现 {len(real)} 处业务逻辑漏洞，共 {len(self._last_findings)} 条记录。")

        self.table.setRowCount(len(self._last_findings))
        for i, f in enumerate(self._last_findings):
            ft = f.get("finding_type", "")
            vals = [
                type_cn.get(ft, ft or "-"),
                f.get("method", ""),
                f.get("url", ""),
                f.get("confidence", ""),
                f.get("scenario", ""),
                f.get("reason", f.get("error", "")),
            ]
            for col, v in enumerate(vals):
                self.table.setItem(i, col, QTableWidgetItem(str(v or "")))


# ================== 人工复核标签页 ==================

class ManualReviewTab(QWidget):
    """渗透结果人工复核：列出攻击成功步骤 + 验证方法 + 人工复核按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_result = {}
        self._init_ui()
        self._render(self._last_result)

    def _init_ui(self):
        lay = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._box = QVBoxLayout(self._container)
        self._box.setSpacing(8)
        self.scroll.setWidget(self._container)
        lay.addWidget(self.scroll)

    def refresh(self, result: dict):
        """重渲染成功步骤卡片。"""
        self._last_result = result or {}
        self._render(self._last_result)

    def _render(self, result):
        from core.report_builder import _VERIFY_METHODS
        # 清空容器
        while self._box.count():
            item = self._box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        steps = result.get("steps") or (result.get("plan") or {}).get("steps", [])
        sr_map = {sr.get("step_id"): sr for sr in result.get("step_results", [])}
        success = []
        for s in steps:
            if not isinstance(s, dict):
                continue
            sr = sr_map.get(s.get("step_id"), {})
            if str(sr.get("status") or "").lower() in ("success", "completed", "成功"):
                success.append((s, sr))

        if not success:
            label = QLabel("暂无成功的攻击步骤。请先执行「攻击链规划」并「执行攻击」。")
            label.setStyleSheet("color: #888888; padding: 16px;")
            self._box.addWidget(label)
            self._box.addStretch(1)
            return

        for i, (s, sr) in enumerate(success, 1):
            self._box.addWidget(self._make_card(i, s, sr, _VERIFY_METHODS))
        self._box.addStretch(1)

    def _make_card(self, i, s, sr, verify_methods):
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #f7f9fa; border: 1px solid #d5dbdb; border-radius: 6px; }")
        v = QVBoxLayout(card)
        v.setSpacing(6)

        etype = s.get("exploit_type") or "-"
        tool = s.get("tool") or "-"
        target = s.get("target") or "-"
        title = QLabel(f"第{i}步 [{etype}] 工具={tool} 目标={target}")
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: bold; color: #1a2b3c;")
        v.addWidget(title)

        detail_lines = []
        if s.get("description"):
            detail_lines.append(f"策略：{s['description']}")
        if s.get("payload"):
            detail_lines.append(f"脚本：{s['payload']}")
        if s.get("validation_cmd"):
            detail_lines.append(f"验证命令：{s['validation_cmd']}")
        ev = sr.get("evidence") or []
        if isinstance(ev, str):
            ev = [ev]
        for e in ev:
            detail_lines.append(f"证据：{e}")
        if detail_lines:
            detail = QLabel("\n".join(detail_lines))
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
            detail.setStyleSheet("color: #2c3e50;")
            v.addWidget(detail)

        verify_row = QHBoxLayout()
        verify_text = verify_methods.get(etype, "核对攻击输出与目标状态，确认攻击是否成功")
        verify_label = QLabel(f"人工验证方法：{verify_text}")
        verify_label.setWordWrap(True)
        verify_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        verify_label.setStyleSheet("color: #7f8c8d;")
        verify_row.addWidget(verify_label, 1)

        action = derive_verify_action(s, sr)
        btn = QPushButton("人工复核")
        btn.setStyleSheet(
            "QPushButton { background: #1abc9c; color: white; padding: 6px 14px; border-radius: 4px; }"
            "QPushButton:disabled { background: #bdc3c7; }")
        if action is None:
            btn.setEnabled(False)
            btn.setToolTip("该步骤无可用链接或命令行")
        else:
            kind, payload = action
            if kind == "url":
                btn.setToolTip(f"在浏览器打开：{payload}")
                btn.clicked.connect(lambda _=False, u=payload: _open_link(u))
            else:
                btn.setToolTip(f"在终端执行：{payload}")
                btn.clicked.connect(lambda _=False, c=payload: _open_terminal(c))
        verify_row.addWidget(btn, 0, Qt.AlignVCenter)
        v.addLayout(verify_row)

        return card


# ================== 报告列表标签页 ==================

class ReportListTab(QWidget):
    """报告列表：列出已存档报告，支持打开/导出/刷新。"""

    def __init__(self, report_dir_provider=None, parent=None):
        super().__init__(parent)
        self._report_dir_provider = report_dir_provider or (lambda: None)
        self._files = []
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("已存档的报告:"))
        top.addStretch(1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        lay.addLayout(top)

        self.list = QListWidget()
        lay.addWidget(self.list, 1)

        btns = QHBoxLayout()
        self.open_btn = QPushButton("打开报告")
        self.open_btn.clicked.connect(self._open)
        btns.addWidget(self.open_btn)
        self.export_btn = QPushButton("导出报告")
        self.export_btn.clicked.connect(self._export)
        btns.addWidget(self.export_btn)
        btns.addStretch(1)
        lay.addLayout(btns)

    def _report_dir(self):
        try:
            d = self._report_dir_provider()
        except Exception:  # noqa: BLE001
            d = None
        return Path(d) if d else None

    def refresh(self, *args):  # 兼容 clicked(bool) 与无参调用
        self.list.clear()
        self._files = []
        rd = self._report_dir()
        if rd and rd.exists():
            self._files = sorted(
                list(rd.glob("*.html")) + list(rd.glob("*.json")),
                key=lambda p: p.stat().st_mtime, reverse=True)
        for p in self._files:
            mt = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            self.list.addItem(QListWidgetItem(f"{p.name}    ({mt})"))
        if not self._files:
            self.list.addItem(QListWidgetItem("暂无报告。扫描后点「生成报告」导出。"))

    def _selected(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self._files):
            return None
        return self._files[row]

    def _open(self):
        p = self._selected()
        if not p:
            QMessageBox.information(self, "提示", "请先选择一个报告")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _export(self):
        p = self._selected()
        if not p:
            QMessageBox.information(self, "提示", "请先选择一个报告")
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "导出报告", p.name, "所有文件 (*.*)")
        if not target:
            return
        try:
            shutil.copy2(str(p), target)
            QMessageBox.information(self, "完成", f"已导出到 {target}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))
