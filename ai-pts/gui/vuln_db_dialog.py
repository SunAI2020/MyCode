# -*- coding: utf-8 -*-
"""漏洞库管理组件：嵌入中间详情页的「漏洞库」标签。

自包含实现：直接读 vendor/cve_database.db（与扫描器共用同一库）。
惰性加载：首次切到该标签时才打开数据库并加载列表，避免启动即打开大库。
在线更新进度通过 update_started/progress_message/update_finished 信号外发，
由主窗口复用标签上方的进度条。
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QSpinBox,
    QPlainTextEdit, QGroupBox, QTextEdit,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor

# 与 core/scanner.py 一致：把 vendor 目录加入 sys.path 后按顶层模块导入
VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_SEV_COLORS = {"CRITICAL": "#d32f2f", "HIGH": "#f57c00", "MEDIUM": "#f9a825", "LOW": "#2e7d32"}


class NvdFetchThread(QThread):
    """后台从 NVD 抓取最近 N 天新增/更新的 CVE，去重入库。"""
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(int)   # 新增条数
    error = pyqtSignal(str)

    def __init__(self, days: int, parent=None):
        super().__init__(parent)
        self.days = days
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            import requests
        except ImportError:
            self.error.emit("缺少 requests 依赖，无法联网更新漏洞库")
            return

        try:
            from database import CVEDatabase
            db = CVEDatabase()
            existing = set()
            try:
                rows = db.conn.execute("SELECT cve_id FROM cve_database").fetchall()
                existing = {r["cve_id"] for r in rows}
            except Exception:
                existing = set()
        except Exception as e:  # noqa: BLE001
            self.error.emit(f"打开漏洞库失败: {e}")
            return

        start_date = (datetime.now() - timedelta(days=self.days)).strftime("%Y-%m-%dT00:00:00.000")
        end_date = datetime.now().strftime("%Y-%m-%dT23:59:59.000")

        params = {
            "lastModStartDate": start_date,
            "lastModEndDate": end_date,
            "resultsPerPage": 100,
            "startIndex": 0,
        }
        new_cves = []
        retry = 0
        while not self._stop and params["startIndex"] < 2000:
            try:
                resp = requests.get(NVD_API, params=params, timeout=(10, 60))
            except requests.exceptions.RequestException as e:
                retry += 1
                if retry > 4:
                    self.error.emit(f"网络连接失败: {e}")
                    return
                self.progress.emit(f"网络异常，{retry * 2} 秒后重试…")
                time.sleep(retry * 2)
                continue
            if resp.status_code == 429:
                self.progress.emit("触发 NVD 限流，等待 6 秒…")
                time.sleep(6)
                continue
            if resp.status_code != 200:
                self.error.emit(f"NVD API 返回 HTTP {resp.status_code}")
                return
            retry = 0
            try:
                data = resp.json()
            except ValueError:
                self.error.emit("NVD 返回数据解析失败")
                return
            items = data.get("vulnerabilities", [])
            if not items:
                break
            for item in items:
                if self._stop:
                    break
                c = item.get("cve", {})
                cve_id = c.get("id", "")
                if not cve_id or cve_id in existing:
                    continue
                desc = ""
                for d in c.get("descriptions", []):
                    if d.get("lang") == "en":
                        desc = d.get("value", "")[:500]
                        break
                cvss_score = None
                severity = "UNKNOWN"
                for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                    m = c.get("metrics", {}).get(key)
                    if m:
                        cvss_score = m[0].get("cvssData", {}).get("baseScore")
                        severity = (m[0].get("cvssData", {}).get("baseSeverity", "UNKNOWN")).upper()
                        break
                products = []
                for cfg in c.get("configurations", []):
                    for node in cfg.get("nodes", []):
                        for match in node.get("cpeMatch", []):
                            parts = (match.get("criteria", "") or "").split(":")
                            if len(parts) >= 5:
                                products.append(f"{parts[3]}:{parts[4]}")
                cwe = ""
                for w in c.get("weaknesses", []):
                    for wd in w.get("description", []):
                        if wd.get("lang") == "en":
                            cwe = wd.get("value", "")
                            break
                    if cwe:
                        break
                refs = [r.get("url", "") for r in c.get("references", [])][:10]
                patch = ""
                for r in c.get("references", []):
                    tags = [t.lower() for t in r.get("tags", [])]
                    if any(t in tags for t in ("patch", "vendor advisory")):
                        patch = r.get("url", "")
                        break
                if not patch and refs:
                    patch = refs[0]
                new_cves.append({
                    "cve_id": cve_id, "name": cve_id, "description": desc,
                    "cvss_score": cvss_score, "severity": severity,
                    "published_date": (c.get("published", "") or "")[:10],
                    "modified_date": (c.get("lastModified", "") or "")[:10],
                    "affected_products": list(dict.fromkeys(products))[:10],
                    "references": refs, "cwe": cwe, "patch_link": patch,
                })
                existing.add(cve_id)
            if len(items) < params["resultsPerPage"]:
                break
            params["startIndex"] += params["resultsPerPage"]
            time.sleep(0.6)

        imported = 0
        if new_cves:
            try:
                imported = db.add_cve_batch(new_cves)
            except Exception as e:  # noqa: BLE001
                self.error.emit(f"入库失败: {e}")
                return
        self.progress.emit(f"抓取完成：命中 {len(new_cves)} 条新 CVE，入库 {imported} 条")
        self.finished_ok.emit(imported)


class VulnDBManagerWidget(QWidget):
    """漏洞库管理组件（CVE 浏览/搜索/分页/详情 + 在线更新）。

    在线更新进度通过三个信号外发，由主窗口复用标签上方的进度条：
      update_started   -> 进度条切换为不确定（转圈）模式
      progress_message -> 更新进度文案
      update_finished  -> 进度条复位
    """
    update_started = pyqtSignal()
    progress_message = pyqtSignal(str)
    update_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        self._loaded = False
        self._page = 1
        self._page_size = 50
        self._keyword = ""
        self._filter_severity = "全部"
        self._thread = None
        self._init_ui()

    def showEvent(self, event):
        """首次切到本标签时惰性打开数据库并加载列表。"""
        if not self._loaded:
            self._loaded = True
            self._open_db()
            self._load_page()
        super().showEvent(event)

    # ---- UI ----
    def _init_ui(self):
        lay = QVBoxLayout(self)

        search = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索 CVE / 描述 / 受影响产品 (如 apache, CVE-2024-...)")
        search.addWidget(self.search_edit)
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._on_search)
        search.addWidget(self.search_btn)
        search.addWidget(QLabel("严重度:"))
        self.sev_combo = QComboBox()
        self.sev_combo.addItems(["全部", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        search.addWidget(self.sev_combo)
        search.addStretch(1)
        lay.addLayout(search)

        upd = QHBoxLayout()
        upd.addWidget(QLabel("更新最近:"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 90)
        self.days_spin.setValue(7)
        self.days_spin.setSuffix(" 天")
        upd.addWidget(self.days_spin)
        self.update_btn = QPushButton("从 NVD 更新漏洞库")
        self.update_btn.clicked.connect(self._on_update)
        upd.addWidget(self.update_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        upd.addWidget(self.stop_btn)
        self.total_label = QLabel("")
        upd.addWidget(self.total_label)
        upd.addStretch(1)
        lay.addLayout(upd)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["序号", "CVE编号", "严重度", "CVSS", "描述", "发布日期", "CWE", "受影响产品"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemClicked.connect(self._on_row_clicked)
        lay.addWidget(self.table, 1)

        page = QHBoxLayout()
        page.addStretch(1)
        self.first_btn = QPushButton("首页"); self.first_btn.clicked.connect(lambda: self._goto(1))
        self.prev_btn = QPushButton("上一页"); self.prev_btn.clicked.connect(lambda: self._goto(self._page - 1))
        self.next_btn = QPushButton("下一页"); self.next_btn.clicked.connect(lambda: self._goto(self._page + 1))
        self.last_btn = QPushButton("末页")
        self.page_label = QLabel("第 1 页")
        for b in (self.first_btn, self.prev_btn, self.next_btn, self.last_btn):
            page.addWidget(b)
        page.addWidget(self.page_label)
        page.addStretch(1)
        lay.addLayout(page)

        detail_group = QGroupBox("CVE 详情")
        dl = QVBoxLayout(detail_group)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMinimumHeight(120)
        dl.addWidget(self.detail_text)
        lay.addWidget(detail_group)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(110)
        self.log_text.setPlaceholderText("漏洞库更新进度将在此显示…")
        lay.addWidget(self.log_text)

    def _open_db(self):
        try:
            from database import CVEDatabase
            self._db = CVEDatabase()
        except Exception as e:  # noqa: BLE001
            self._log(f"打开漏洞库失败: {e}")

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{ts}] {msg}")

    # ---- 数据 ----
    def _load_page(self):
        if not self._db:
            return
        sev = self._filter_severity if self._filter_severity != "全部" else None
        if sev:
            all_rows = self._db.search_cve(keyword=self._keyword or None, min_cvss=0, limit=9990000)
            all_rows = [r for r in all_rows if str(r.get("severity", "")).upper() == sev]
            total = len(all_rows)
            rows = all_rows[(self._page - 1) * self._page_size:self._page * self._page_size]
        else:
            rows = self._db.search_cve(
                keyword=self._keyword or None, min_cvss=0,
                limit=self._page_size, offset=(self._page - 1) * self._page_size)
            total = self._db.count_cve(keyword=self._keyword or None, min_cvss=0)

        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str((self._page - 1) * self._page_size + i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(r.get("cve_id", "")))
            sev_item = QTableWidgetItem(r.get("severity", ""))
            sev_item.setForeground(QColor(_SEV_COLORS.get(r.get("severity", ""), "#333")))
            self.table.setItem(i, 2, sev_item)
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get("cvss_score") or "")))
            self.table.setItem(i, 4, QTableWidgetItem((r.get("description") or "")[:100]))
            self.table.setItem(i, 5, QTableWidgetItem((r.get("published_date") or "")[:10]))
            self.table.setItem(i, 6, QTableWidgetItem((r.get("cwe") or "")[:20]))
            self.table.setItem(i, 7, QTableWidgetItem((r.get("affected_products") or "")[:80]))

        pages = max(1, (total + self._page_size - 1) // self._page_size)
        self.page_label.setText(f"第 {self._page} / {pages} 页")
        self.total_label.setText(f"共 {total} 条 CVE")
        self.first_btn.setEnabled(self._page > 1)
        self.prev_btn.setEnabled(self._page > 1)
        self.next_btn.setEnabled(self._page < pages)
        self.last_btn.setEnabled(self._page < pages)

    def _goto(self, page: int):
        self._page = max(1, page)
        self._load_page()

    def _on_search(self):
        self._keyword = self.search_edit.text().strip()
        self._filter_severity = self.sev_combo.currentText()
        self._page = 1
        self._load_page()

    def _on_row_clicked(self, item):
        if not self._db:
            return
        cve_id = self.table.item(item.row(), 1).text()
        rows = self._db.search_cve(keyword=cve_id, min_cvss=0, limit=1)
        if not rows:
            return
        r = rows[0]
        lines = [
            f"CVE 编号: {r.get('cve_id', '')}",
            f"严重度: {r.get('severity', '')}   CVSS: {r.get('cvss_score', '')}",
            f"发布日期: {(r.get('published_date') or '')[:10]}   修改日期: {(r.get('modified_date') or '')[:10]}",
            f"CWE: {r.get('cwe') or 'N/A'}",
            f"受影响产品: {r.get('affected_products') or 'N/A'}",
            f"补丁/参考链接: {r.get('patch_link') or 'N/A'}",
            "",
            "描述:",
            r.get("description", "") or "N/A",
        ]
        self.detail_text.setPlainText("\n".join(lines))

    # ---- 在线更新 ----
    def _on_update(self):
        if not self._db:
            self._open_db()
            if not self._db:
                self._log("漏洞库未打开，无法更新")
                return
        self._thread = NvdFetchThread(self.days_spin.value())
        self._thread.progress.connect(self._on_progress)
        self._thread.finished_ok.connect(self._on_update_done)
        self._thread.error.connect(self._on_update_error)
        self.update_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.update_started.emit()
        self._log(f"开始从 NVD 更新最近 {self.days_spin.value()} 天的漏洞…")
        self._thread.start()

    def _on_progress(self, msg: str):
        self._log(msg)
        self.progress_message.emit(msg)

    def _on_stop(self):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
        self._log("已请求停止更新")

    def _on_update_done(self, imported: int):
        self.update_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._log(f"更新完成，新增 {imported} 条 CVE")
        self.update_finished.emit()
        self._load_page()

    def _on_update_error(self, msg: str):
        self.update_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._log(f"[错误] {msg}")
        self.update_finished.emit()
