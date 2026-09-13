#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的漏洞库管理程序
功能: 浏览漏洞库、按时间范围+严重度全网搜索CVE、去重入库
可独立运行，不影响原有程序
"""
import sys
import os
import time
import json
import requests
import threading
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QDateEdit, QComboBox, QProgressBar, QPlainTextEdit,
    QMessageBox, QFrame, QCheckBox, QGroupBox, QSplitter
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QColor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import Database

# NVD API
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_API_KEY = os.environ.get('NVD_API_KEY', '')


def _load_api_key():
    """从 assets_system.db 加载 NVD API Key"""
    global NVD_API_KEY
    if NVD_API_KEY:
        return
    try:
        assets_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets_system.db')
        if os.path.exists(assets_db):
            conn = __import__('sqlite3').connect(assets_db)
            row = conn.execute("SELECT value FROM system_settings WHERE key='nvd_api_key'").fetchone()
            conn.close()
            if row and row[0]:
                NVD_API_KEY = row[0]
    except Exception:
        pass


_load_api_key()


class FetchCVEThread(QThread):
    """后台CVE抓取线程"""
    progress = pyqtSignal(str)
    found_cve = pyqtSignal(dict)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, start_date, end_date, severities):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.severities = [s.upper() for s in severities]
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        count = 0
        headers = {}
        if NVD_API_KEY:
            headers['apiKey'] = NVD_API_KEY

        # 按月份分批查询，避免NVD API超时
        current_start = self.start_date
        while current_start < self.end_date and not self._stop:
            month_end = min(
                current_start + timedelta(days=90),
                self.end_date
            )

            self.progress.emit(f'正在搜索 {current_start.strftime("%Y-%m-%d")} ~ {month_end.strftime("%Y-%m-%d")} ...')

            params = {
                'pubStartDate': current_start.strftime('%Y-%m-%dT00:00:00.000'),
                'pubEndDate': month_end.strftime('%Y-%m-%dT23:59:59.000'),
                'resultsPerPage': 100,
                'startIndex': 0
            }

            retry_count = 0
            max_retries = 5
            base_delay = 2  # 重试基础等待秒数

            try:
                while not self._stop:
                    try:
                        resp = requests.get(NVD_API, params=params, headers=headers,
                                           timeout=(10, 60))  # (connect, read)
                    except (requests.exceptions.ConnectionError,
                            requests.exceptions.ReadTimeout,
                            requests.exceptions.ConnectTimeout,
                            requests.exceptions.ChunkedEncodingError) as e:
                        retry_count += 1
                        if retry_count > max_retries:
                            self.error.emit(f'网络连接失败(已重试{max_retries}次): {e}')
                            break
                        delay = base_delay * (2 ** (retry_count - 1))  # 指数退避
                        self.progress.emit(f'[网络] {e} ({retry_count}/{max_retries})，{delay}秒后重试...')
                        time.sleep(delay)
                        continue

                    if resp.status_code == 429:
                        retry_count += 1
                        if retry_count >= max_retries:
                            self.error.emit('API请求次数过多，请稍后再试')
                            break
                        self.progress.emit(f'触发API限流({retry_count}/{max_retries})，等待6秒重试...')
                        time.sleep(6)
                        continue
                    retry_count = 0
                    if resp.status_code != 200:
                        self.error.emit(f'NVD API返回 HTTP {resp.status_code}')
                        break

                    data = resp.json()
                    items = data.get('vulnerabilities', [])
                    if not items:
                        break

                    for item in items:
                        if self._stop:
                            break
                        try:
                            c = item.get('cve', {})
                            cve_id = c.get('id', '')
                            if not cve_id:
                                continue

                            desc = ''
                            for d in c.get('descriptions', []):
                                if d.get('lang') == 'en':
                                    desc = d.get('value', '')[:500]

                            cvss_score = None
                            severity = 'UNKNOWN'
                            metrics = c.get('metrics', {})
                            for key in ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']:
                                if key in metrics and metrics[key]:
                                    cvss_data = metrics[key][0].get('cvssData', {})
                                    cvss_score = cvss_data.get('baseScore')
                                    severity = (cvss_data.get('baseSeverity', 'UNKNOWN')).upper()
                                    break

                            # 严重度过滤
                            if self.severities and 'ALL' not in self.severities:
                                if severity not in self.severities:
                                    continue

                            published = (c.get('published', '') or '')[:10]

                            products = []
                            for cfg in c.get('configurations', []):
                                for node in cfg.get('nodes', []):
                                    for match in node.get('cpeMatch', []):
                                        crit = match.get('criteria', '')
                                        if crit:
                                            parts = crit.split(':')
                                            if len(parts) >= 5:
                                                products.append(f'{parts[3]}:{parts[4]}')

                            # 提取 CWE ID
                            cwe = ''
                            for w in c.get('weaknesses', []):
                                for desc in w.get('description', []):
                                    if desc.get('lang') == 'en':
                                        cwe = desc.get('value', '')
                                        break
                                if cwe:
                                    break

                            # 提取补丁/参考链接
                            patch_link = ''
                            refs_list = []
                            for ref in c.get('references', []):
                                url = ref.get('url', '')
                                tags = [t.lower() for t in ref.get('tags', [])]
                                refs_list.append(url)
                                if not patch_link and any(t in tags for t in ('patch', 'vendor advisory', 'mitigation')):
                                    patch_link = url
                            # 如果没有补丁标签，取第一个参考链接
                            if not patch_link and refs_list:
                                patch_link = refs_list[0]

                            cve_data = {
                                'cve_id': cve_id, 'name': cve_id,
                                'description': desc,
                                'cvss_score': cvss_score,
                                'severity': severity,
                                'published_date': published,
                                'modified_date': (c.get('lastModified', '') or '')[:10],
                                'affected_products': list(set(products))[:10],
                                'references': refs_list[:10],
                                'ai_analysis': None,
                                'cwe': cwe,
                                'patch_link': patch_link
                            }
                            self.found_cve.emit(cve_data)
                            count += 1
                        except:
                            pass

                    if len(items) < params['resultsPerPage']:
                        break
                    params['startIndex'] += params['resultsPerPage']
                    if params['startIndex'] >= 2000:
                        break
                    time.sleep(0.6)

            except Exception as e:
                self.error.emit(f'网络请求失败: {str(e)}')
                break

            current_start = month_end + timedelta(days=1)
            if not self._stop:
                time.sleep(1)

        self.progress.emit(f'搜索完成，共获取 {count} 条符合条件的CVE')
        self.finished.emit(count)


class VulnDBManager(QMainWindow):
    """漏洞库管理主窗口"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.work_id = None
        self.pending_cves = []
        self.new_count = 0
        self.dup_count = 0
        self._log_buffer = []
        self.init_ui()
        self._refresh_table()

    def init_ui(self):
        self.setWindowTitle('漏洞库管理程序 - CVE漏洞搜索与入库')
        self.setGeometry(100, 100, 1400, 900)
        self.setStyleSheet("""
            QMainWindow { background: #f3f3f3; }
            QGroupBox { font-weight: bold; font-size: 16px; border: 1px solid #d0d0d0; border-radius: 4px; margin-top: 10px; padding-top: 20px; background: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QPushButton { background: #e1e1e1; color: #333; border: 1px solid #c0c0c0; padding: 8px 18px; border-radius: 4px; font-size: 16px; }
            QPushButton:hover { background: #e5f0ff; border-color: #0078d4; color: #0078d4; }
            QPushButton#searchBtn { background: #0078d4; color: white; font-weight: bold; font-size: 18px; padding: 10px 30px; }
            QPushButton#searchBtn:hover { background: #005a9e; }
            QPushButton#stopBtn { color: #d13438; border-color: #d13438; }
            QPushButton#stopBtn:hover { background: #fde7e9; }
            QTableWidget { font-size: 14px; border: 1px solid #d0d0d0; gridline-color: #e0e0e0; background: white; }
            QHeaderView::section { background: #f0f0f0; color: #333; padding: 6px; border-bottom: 2px solid #d0d0d0; font-weight: bold; }
            QLabel { font-size: 15px; }
            QComboBox { font-size: 15px; padding: 4px; border: 1px solid #c0c0c0; border-radius: 4px; background: white; }
            QDateEdit { font-size: 15px; padding: 4px; border: 1px solid #c0c0c0; border-radius: 4px; background: white; }
            QPlainTextEdit { font-size: 15px; border: 1px solid #c0c0c0; border-radius: 4px; background: white; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ====== 1. 搜索条件 ======
        search_group = QGroupBox('全网搜索条件')
        search_layout = QHBoxLayout()

        search_layout.addWidget(QLabel('起始日期:'))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        self.start_date.setDisplayFormat('yyyy-MM-dd')
        search_layout.addWidget(self.start_date)

        search_layout.addWidget(QLabel('结束日期:'))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat('yyyy-MM-dd')
        search_layout.addWidget(self.end_date)

        search_layout.addWidget(QLabel('漏洞类别:'))
        self.sev_combo = QComboBox()
        self.sev_combo.addItems(['全部', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'])
        self.sev_combo.setCurrentText('全部')
        search_layout.addWidget(self.sev_combo)

        self.search_btn = QPushButton('开始全网搜索')
        self.search_btn.setObjectName('searchBtn')
        self.search_btn.clicked.connect(self._start_search)
        search_layout.addWidget(self.search_btn)

        self.stop_btn = QPushButton('停止')
        self.stop_btn.setObjectName('stopBtn')
        self.stop_btn.clicked.connect(self._stop_search)
        self.stop_btn.setEnabled(False)
        search_layout.addWidget(self.stop_btn)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # ====== 2. 进度 & 日志 ======
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        log_layout = QHBoxLayout()
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setPlaceholderText('搜索日志...')
        log_layout.addWidget(self.log_text)

        self.import_btn = QPushButton('导入选中CVE到漏洞库')
        self.import_btn.setObjectName('searchBtn')
        self.import_btn.clicked.connect(self._import_cves)
        self.import_btn.setEnabled(False)
        log_layout.addWidget(self.import_btn)
        layout.addLayout(log_layout)

        # ====== 3. 数据表格 ======
        splitter = QSplitter(Qt.Vertical)

        self.cve_table = QTableWidget()
        self.cve_table.setColumnCount(10)
        self.cve_table.setHorizontalHeaderLabels(['序号', 'CVE编号', '严重度', 'CVSS', '发布日期', '描述', 'CWE', '补丁链接', '受影响产品', '操作'])
        self.cve_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cve_table.setSelectionBehavior(QTableWidget.SelectRows)
        splitter.addWidget(self.cve_table)

        # 操作按钮
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 5, 0, 5)

        self.refresh_btn = QPushButton('刷新列表')
        self.refresh_btn.clicked.connect(self._refresh_table)
        btn_layout.addWidget(self.refresh_btn)

        self.select_all_cb = QCheckBox('全选')
        self.select_all_cb.toggled.connect(self._toggle_select_all)
        btn_layout.addWidget(self.select_all_cb)

        self.del_btn = QPushButton('删除选中CVE')
        self.del_btn.setObjectName('stopBtn')
        self.del_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(self.del_btn)

        self.export_btn = QPushButton('导出为HTML')
        self.export_btn.clicked.connect(self._export_html)
        btn_layout.addWidget(self.export_btn)

        self.stats_label = QLabel('')
        btn_layout.addWidget(self.stats_label)
        btn_layout.addStretch()
        layout.addWidget(btn_widget)

        # 分页控件
        page_widget = QWidget()
        page_layout = QHBoxLayout(page_widget)
        page_layout.setContentsMargins(0, 3, 0, 3)

        self.page_first_btn = QPushButton('首页')
        self.page_first_btn.clicked.connect(self._first_page)
        page_layout.addWidget(self.page_first_btn)

        self.page_prev_btn = QPushButton('上一页')
        self.page_prev_btn.clicked.connect(self._prev_page)
        page_layout.addWidget(self.page_prev_btn)

        self.page_label = QLabel('第 1 页')
        page_layout.addWidget(self.page_label)

        self.page_next_btn = QPushButton('下一页')
        self.page_next_btn.clicked.connect(self._next_page)
        page_layout.addWidget(self.page_next_btn)

        self.page_last_btn = QPushButton('末页')
        self.page_last_btn.clicked.connect(self._last_page)
        page_layout.addWidget(self.page_last_btn)

        self.page_info_label = QLabel('每页显示 500 条漏洞信息')
        page_layout.addWidget(self.page_info_label)

        page_layout.addStretch()
        layout.addWidget(page_widget)
        layout.addWidget(splitter)

        # 分页状态
        self.current_page = 1
        self.page_size = 500

        self._log('漏洞库管理程序已启动')
        self._log(f'当前漏洞库总量: {self.db.cve.get_statistics().get("total_cves", 0)} 条')

    def _log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self._log_buffer.append(f'[{ts}] {msg}')
        # 限制日志缓存上限
        if len(self._log_buffer) > 500:
            self._log_buffer = self._log_buffer[-500:]
        self.log_text.setPlainText('\n'.join(reversed(self._log_buffer)))

    def _refresh_table(self):
        """刷新表格（重置到第1页）"""
        self.current_page = 1
        self._load_page()

    def _load_page(self):
        """加载当前页的CVE数据"""
        offset = (self.current_page - 1) * self.page_size
        cves = self.db.cve.search_cve(limit=self.page_size, offset=offset)
        total = self.db.cve.count_cve()

        self.cve_table.setRowCount(0)
        self.cve_table.setRowCount(len(cves))
        for row, cve in enumerate(cves):
            self.cve_table.setItem(row, 0, QTableWidgetItem(str(offset + row + 1)))
            self.cve_table.setItem(row, 1, QTableWidgetItem(cve.get('cve_id', '')))
            sev = cve.get('severity', 'INFO')
            item = QTableWidgetItem(sev)
            if sev == 'CRITICAL':
                item.setForeground(Qt.red)
            elif sev == 'HIGH':
                item.setForeground(QColor(255, 140, 0))
            self.cve_table.setItem(row, 2, item)
            self.cve_table.setItem(row, 3, QTableWidgetItem(str(cve.get('cvss_score', ''))))
            self.cve_table.setItem(row, 4, QTableWidgetItem(cve.get('published_date', '')[:10] if cve.get('published_date') else ''))
            desc = (cve.get('description', '') or '')[:80]
            self.cve_table.setItem(row, 5, QTableWidgetItem(desc))
            self.cve_table.setItem(row, 6, QTableWidgetItem((cve.get('cwe', '') or '')[:20]))
            patch = (cve.get('patch_link', '') or '')[:50]
            self.cve_table.setItem(row, 7, QTableWidgetItem(patch))
            products = cve.get('affected_products', '')
            if isinstance(products, list):
                products = ', '.join(products)
            self.cve_table.setItem(row, 8, QTableWidgetItem((products or '')[:80]))

            cb = QCheckBox()
            self.cve_table.setCellWidget(row, 9, cb)

        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.page_label.setText(f'第 {self.current_page} / {total_pages} 页')
        self.page_info_label.setText(f'每页显示 {self.page_size} 条漏洞信息（共 {total} 条）')
        self.stats_label.setText(f'共 {total} 条CVE')
        self._update_page_buttons(total_pages)
        self._log(f'列表已刷新，第 {self.current_page}/{total_pages} 页，显示 {len(cves)} 条')

    def _update_page_buttons(self, total_pages):
        """更新分页按钮状态"""
        self.page_first_btn.setEnabled(self.current_page > 1)
        self.page_prev_btn.setEnabled(self.current_page > 1)
        self.page_next_btn.setEnabled(self.current_page < total_pages)
        self.page_last_btn.setEnabled(self.current_page < total_pages)

    def _first_page(self):
        if self.current_page > 1:
            self.current_page = 1
            self._load_page()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._load_page()

    def _next_page(self):
        self.current_page += 1
        self._load_page()

    def _last_page(self):
        total = self.db.cve.count_cve()
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page = total_pages
            self._load_page()

    def _toggle_select_all(self, checked):
        for row in range(self.cve_table.rowCount()):
            cb = self.cve_table.cellWidget(row, 9)
            if isinstance(cb, QCheckBox):
                cb.setChecked(checked)

    def _start_search(self):
        sd = self.start_date.date().toPyDate()
        ed = self.end_date.date().toPyDate()
        if sd > ed:
            QMessageBox.warning(self, '警告', '起始日期不能大于结束日期')
            return

        sev = self.sev_combo.currentText()
        severities = ['ALL'] if sev == '全部' else [sev]

        self._log(f'开始搜索: {sd} ~ {ed}, 类别: {sev}')
        self._search_stopped = False
        try:
            self.work_id = self.db.start_work('漏洞库更新')
        except Exception:
            self.work_id = None
        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.pending_cves = []
        self.new_count = 0
        self.dup_count = 0

        # 先从数据库加载已有cve_id用于去重
        existing = set()
        try:
            rows = self.db.cve.conn.execute('SELECT cve_id FROM cve_database').fetchall()
            existing = set(r['cve_id'] for r in rows)
        except:
            pass

        self.thread = FetchCVEThread(sd, ed, severities)
        self.thread.progress.connect(self._on_progress)
        self.thread.found_cve.connect(lambda c: self._on_cve_found(c, existing))
        self.thread.finished.connect(self._on_search_finished)
        self.thread.error.connect(self._on_error)
        self.thread.start()

    def _on_progress(self, msg):
        self._log(msg)

    def _on_cve_found(self, cve, existing):
        if cve['cve_id'] in existing:
            self.dup_count += 1
            return
        existing.add(cve['cve_id'])
        self.pending_cves.append(cve)
        self.new_count += 1

        # 不实时更新表格，搜索结束后统一刷新
        if self.new_count % 50 == 0:
            self.stats_label.setText(f'新发现: {self.new_count} | 已去重: {self.dup_count}')

    def _on_search_finished(self, count):
        self.search_btn.setEnabled(True)
        if not getattr(self, '_search_stopped', False):
            try:
                self.db.finish_work(self.work_id, '已完成')
            except Exception:
                pass
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(len(self.pending_cves) > 0)

        self.stats_label.setText(
            f'搜索完成 | 新发现: {self.new_count} | 已去重: {self.dup_count} | '
            f'待导入: {len(self.pending_cves)} | 共 {self.cve_table.rowCount()} 条'
        )

        self._log(f'搜索完成: 新发现 {self.new_count} 条, 去重 {self.dup_count} 条, 待导入 {len(self.pending_cves)} 条')

        # 自动导入新发现的CVE
        if self.pending_cves:
            self._auto_import_cves()

    def _on_error(self, msg):
        self._log(f'[错误] {msg}')
        self._search_stopped = True
        try:
            self.db.finish_work(self.work_id, '被终止')
        except Exception:
            pass

    def _stop_search(self):
        self._search_stopped = True
        if hasattr(self, 'thread') and self.thread:
            self.thread.stop()
        try:
            self.db.finish_work(self.work_id, '被终止')
        except Exception:
            pass
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._log('搜索已停止')

    def _import_cves(self):
        if not self.pending_cves:
            QMessageBox.information(self, '提示', '没有待导入的CVE')
            return

        reply = QMessageBox.question(self, '确认导入',
            f'将导入 {len(self.pending_cves)} 条新CVE到漏洞库，确认？',
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        imported = self.db.add_cve_batch(self.pending_cves)
        self._log(f'已导入 {imported} 条CVE到漏洞库')
        self.pending_cves = []
        self.import_btn.setEnabled(False)
        self._refresh_table()
        QMessageBox.information(self, '成功', f'成功导入 {imported} 条CVE')

    def _auto_import_cves(self):
        """自动导入新发现的CVE（无需确认）"""
        if not self.pending_cves:
            return

        imported = self.db.add_cve_batch(self.pending_cves)
        self._log(f'已自动导入 {imported} 条CVE到漏洞库')
        self.pending_cves = []
        self.import_btn.setEnabled(False)
        self._refresh_table()

    def _delete_selected(self):
        selected = []
        for row in range(self.cve_table.rowCount()):
            cb = self.cve_table.cellWidget(row, 9)
            if isinstance(cb, QCheckBox) and cb.isChecked():
                cve_id = self.cve_table.item(row, 1).text()
                selected.append(cve_id)

        if not selected:
            QMessageBox.information(self, '提示', '请先勾选要删除的CVE')
            return

        reply = QMessageBox.question(self, '确认删除',
            f'将删除 {len(selected)} 条CVE，此操作不可撤销，确认？',
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        c = self.db.cve.conn.cursor()
        for cve_id in selected:
            c.execute('DELETE FROM cve_database WHERE cve_id=?', (cve_id,))
        self.db.cve.conn.commit()
        self._log(f'已删除 {len(selected)} 条CVE')
        self._refresh_table()

    def _export_html(self):
        from PyQt5.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self, '导出CVE漏洞库', f'vuln_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
            'HTML (*.html)')
        if not filepath:
            return

        import html

        cves = self.db.cve.search_cve(limit=9990000)
        rows_html = ''
        for idx, c in enumerate(cves, 1):
            sev = c.get('severity', 'INFO')
            color = {'CRITICAL': '#d32f2f', 'HIGH': '#f57c00', 'MEDIUM': '#fbc02d'}.get(sev, '#333')
            safe_id = html.escape(c.get('cve_id',''))
            safe_cvss = html.escape(str(c.get('cvss_score','')))
            safe_pub = html.escape(str(c.get('published_date','')))
            safe_desc = html.escape((c.get('description','') or '')[:120])
            safe_cwe = html.escape(str((c.get('cwe','') or '')[:30]))
            safe_patch = html.escape(str((c.get('patch_link','') or '')[:80]))
            safe_products = html.escape(str((c.get('affected_products','') or '')[:80]))
            patch_cell = f'<a href="{safe_patch}" target="_blank">{safe_patch}</a>' if safe_patch else ''
            rows_html += f'''<tr>
                <td>{idx}</td>
                <td><a href="https://nvd.nist.gov/vuln/detail/{safe_id}" target="_blank">{safe_id}</a></td>
                <td style="color:{color};font-weight:bold;">{html.escape(sev)}</td>
                <td>{safe_cvss}</td>
                <td>{safe_pub}</td>
                <td>{safe_desc}</td>
                <td>{safe_cwe}</td>
                <td>{patch_cell}</td>
                <td>{safe_products}</td>
            </tr>'''

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>CVE漏洞库</title>
<style>
    body {{ font-family: "Microsoft YaHei",Arial; margin:20px; background:#f3f3f3; }}
    .container {{ max-width:1300px; margin:0 auto; background:white; padding:30px; border-radius:8px; }}
    h1 {{ color:#0078d4; text-align:center; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th {{ background:#f0f0f0; padding:10px; border-bottom:2px solid #d0d0d0; }}
    td {{ padding:8px; border-bottom:1px solid #e0e0e0; }}
    tr:hover {{ background:#f8f8f8; }}
    a {{ color:#0078d4; }}
    .footer {{ text-align:center; color:#999; margin-top:20px; }}
</style>
</head>
<body>
<div class="container">
<h1>CVE漏洞库</h1>
<p style="text-align:center;color:#666;">共 {len(cves)} 条记录 | 导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<table>
<tr><th>序号</th><th>CVE编号</th><th>严重度</th><th>CVSS</th><th>发布日期</th><th>描述</th><th>CWE</th><th>补丁链接</th><th>受影响产品</th></tr>
{rows_html}
</table>
<div class="footer">山西有信网安科技有限公司 &copy; 2026</div>
</div>
</body></html>'''
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        self._log(f'已导出 {len(cves)} 条CVE到 {filepath}')
        QMessageBox.information(self, '成功', f'已导出 {len(cves)} 条CVE')


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    from PyQt5.QtGui import QFont
    app.setFont(QFont('Microsoft YaHei', 10))
    window = VulnDBManager()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
