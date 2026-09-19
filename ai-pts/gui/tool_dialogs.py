# -*- coding: utf-8 -*-
"""工具类对话框：渗透测试工具库 / 渗透结果人工复核 / 报告中心。"""
import sys
import shutil
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 sys.path 上，使 core 包可导入（与 core/scanner.py 一致）
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QTextEdit, QListWidget, QListWidgetItem,
    QFileDialog, QWidget, QMessageBox,
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices

from core.tool_library import TOOLS, render_usage


class ToolLibraryDialog(QDialog):
    """渗透测试工具库：工具目录 + 中文使用方法。"""

    def __init__(self, tab: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("渗透测试工具库")
        self.resize(1020, 720)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()

        catalog = QWidget()
        cl = QVBoxLayout(catalog)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["工具", "分类", "简介", "官网"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemClicked.connect(self._on_click)
        cl.addWidget(self.table)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(190)
        cl.addWidget(self.detail)
        self.tabs.addTab(catalog, "工具目录")

        usage = QWidget()
        ul = QVBoxLayout(usage)
        self.usage_text = QTextEdit()
        self.usage_text.setReadOnly(True)
        self.usage_text.setPlainText(render_usage())
        ul.addWidget(self.usage_text)
        self.tabs.addTab(usage, "使用方法")

        lay.addWidget(self.tabs)
        self._fill_table()
        self.tabs.setCurrentIndex(tab)

    def _fill_table(self):
        self.table.setRowCount(len(TOOLS))
        for i, t in enumerate(TOOLS):
            self.table.setItem(i, 0, QTableWidgetItem(t["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(t["cat"]))
            self.table.setItem(i, 2, QTableWidgetItem(t["desc"]))
            self.table.setItem(i, 3, QTableWidgetItem(t["url"]))

    def _on_click(self, item):
        t = TOOLS[item.row()]
        self.detail.setPlainText(
            f"【{t['name']}】\n{t['desc']}\n\n官网: {t['url']}\n\n"
            f"安装:\n{t['install']}\n\n使用方法:\n{t['usage']}")


class ManualReviewDialog(QDialog):
    """渗透结果人工复核：攻击结果 + 人工核验方法。"""

    def __init__(self, attack_results: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("渗透结果人工复核")
        self.resize(920, 680)
        self.attack_results = attack_results or {}
        self._init_ui()
        self._fill()

    def _init_ui(self):
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()

        result_tab = QWidget()
        rl = QVBoxLayout(result_tab)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        rl.addWidget(self.result_text)
        self.tabs.addTab(result_tab, "攻击结果")

        method_tab = QWidget()
        ml = QVBoxLayout(method_tab)
        self.method_text = QTextEdit()
        self.method_text.setReadOnly(True)
        ml.addWidget(self.method_text)
        self.tabs.addTab(method_tab, "人工复核方法")

        lay.addWidget(self.tabs)

    def _fill(self):
        lines = ["【渗透测试攻击过程中产生的结果】\n"]
        plan = self.attack_results.get("plan", {})
        steps = self.attack_results.get("steps") or plan.get("steps", [])
        sr_map = {sr.get("step_id"): sr for sr in self.attack_results.get("step_results", [])}
        if not steps:
            lines.append("暂无攻击结果。请先执行「攻击链规划」与「执行攻击」。")
        for i, s in enumerate(steps, 1):
            sr = sr_map.get(s.get("step_id"), {})
            status = sr.get("status", "未执行")
            lines.append(
                f"\n第{i}步 [{s.get('exploit_type')}] 工具={s.get('tool') or '-'} "
                f"目标={s.get('target') or '-'}")
            lines.append(f"  状态: {status}")
            if s.get("description"):
                lines.append(f"  策略: {s.get('description')}")
            if s.get("payload"):
                lines.append(f"  脚本: {s.get('payload')}")
            if sr.get("error"):
                lines.append(f"  错误: {sr['error']}")
            ev = sr.get("evidence") or []
            if isinstance(ev, str):
                ev = [ev]
            for e in ev:
                lines.append(f"  证据: {e}")
        self.result_text.setPlainText("\n".join(lines))

        from core.report_builder import _VERIFY_METHODS
        mlines = ["【人工复核方法】\n",
                  "对每一处攻击结果，按下列对应类型的核验方式人工确认，并截图保存证据：\n"]
        for etype, method in _VERIFY_METHODS.items():
            mlines.append(f"  ● {etype}: {method}")
        mlines += [
            "\n通用复核流程：",
            "  1. 打开对应 shell/页面，核对命令输出与报告是否一致。",
            "  2. 截图保存证据，标注目标、时间、执行者。",
            "  3. 排除环境误报（弱口令/开放服务需实际可复现）。",
            "  4. 复核通过后在报告中心导出最终报告。",
        ]
        self.method_text.setPlainText("\n".join(mlines))


class ReportCenterDialog(QDialog):
    """报告中心：列出已存档报告，支持打开/导出。"""

    def __init__(self, report_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("报告中心")
        self.resize(840, 560)
        self.report_dir = Path(report_dir)
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("已存档的报告:"))
        top.addStretch(1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._load)
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

        self._files = []
        self._load()

    def _load(self):
        self.list.clear()
        self._files = []
        if self.report_dir.exists():
            self._files = sorted(
                list(self.report_dir.glob("*.html")) + list(self.report_dir.glob("*.json")),
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
