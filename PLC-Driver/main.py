"""
PLC 数据采集与编程工具 ─ 主图形界面
基于 PyQt6 + pyqtgraph 构建
"""
import sys
import asyncio
import qasync
import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QGridLayout, QFormLayout,
    QStatusBar, QMessageBox, QSplitter, QTextEdit, QToolBar,
    QHeaderView, QCheckBox, QDoubleSpinBox, QFileDialog, QMenu,
    QTreeWidget, QTreeWidgetItem, QInputDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QFont, QColor, QIcon

import pyqtgraph as pg
import numpy as np

from driver_base import (
    PLCDriver, ConnectionConfig, ConnectionState, DriverType,
    TagInfo, DataPoint,
)
from modbus_driver import ModbusDriver
from s7_driver import S7Driver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── 样式表 ─────────────────────────────────────
DARK_STYLE = """
QMainWindow { background-color: #1e1e2e; }
QWidget { background-color: #1e1e2e; color: #cdd6f4; font-size: 13px; }
QTabWidget::pane { border: 1px solid #313244; background: #1e1e2e; }
QTabBar::tab {
    background: #181825; color: #6c7086; padding: 8px 18px;
    border: 1px solid #313244; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #1e1e2e; color: #cdd6f4; font-weight: bold; }
QGroupBox {
    border: 1px solid #313244; border-radius: 8px; margin-top: 14px;
    padding-top: 18px; font-weight: bold; color: #89b4fa;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; }
QPushButton {
    background: #313244; border: 1px solid #45475a; border-radius: 6px;
    padding: 6px 16px; min-height: 28px;
}
QPushButton:hover { background: #45475a; }
QPushButton:pressed { background: #585b70; }
QPushButton#btnConnect { background: #a6e3a1; color: #1e1e2e; font-weight: bold; }
QPushButton#btnDisconnect { background: #f38ba8; color: #1e1e2e; font-weight: bold; }
QPushButton#btnStartPoll { background: #89b4fa; color: #1e1e2e; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #313244; border: 1px solid #45475a; border-radius: 4px;
    padding: 4px 8px; min-height: 26px;
}
QLineEdit:focus, QSpinBox:focus { border-color: #89b4fa; }
QTableWidget {
    background: #181825; gridline-color: #313244; border: 1px solid #313244;
    alternate-background-color: #1e1e2e;
}
QTableWidget::item { padding: 4px; }
QHeaderView::section {
    background: #313244; padding: 6px; border: 1px solid #45475a;
    font-weight: bold;
}
QStatusBar { background: #11111b; color: #6c7086; }
QTreeWidget { background: #181825; border: 1px solid #313244; }
QTreeWidget::item { padding: 3px; }
QTextEdit { background: #181825; border: 1px solid #313244; font-family: monospace; }
QComboBox QAbstractItemView { background: #313244; selection-background-color: #45475a; }
QMenu { background: #313244; border: 1px solid #45475a; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background: #45475a; }
"""


# ── 通讯线程 ────────────────────────────────────
class CommWorker(QThread):
    """异步通讯工作线程"""
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)
    data_received = pyqtSignal(list)  # list[DataPoint]
    status_changed = pyqtSignal(str)

    def __init__(self, driver: PLCDriver, config: ConnectionConfig, poll_interval: int = 500):
        super().__init__()
        self._driver = driver
        self._config = config
        self._poll_interval = poll_interval  # ms
        self._running = False

    async def _connect(self):
        ok = await self._driver.connect(self._config)
        if ok:
            self.connected.emit()
        else:
            self.error_occurred.emit(self._driver.error_message)

    async def _poll_loop(self):
        while self._running:
            try:
                dps = await self._driver.read_all_tags()
                if dps:
                    self.data_received.emit(dps)
            except Exception as e:
                self.error_occurred.emit(f"轮询错误: {e}")
            await asyncio.sleep(self._poll_interval / 1000.0)

    async def _disconnect(self):
        await self._driver.disconnect()
        self.disconnected.emit()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._running = True
        loop.run_until_complete(self._connect())
        if self._driver.state == ConnectionState.CONNECTED:
            loop.run_until_complete(self._poll_loop())
        loop.close()

    def stop(self):
        self._running = False
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._disconnect())
        loop.close()


# ── 连接面板 ────────────────────────────────────
class ConnectionPanel(QWidget):
    """PLC 连接配置面板"""

    connect_requested = pyqtSignal(ConnectionConfig)
    disconnect_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 驱动类型选择 ──
        group = QGroupBox("驱动配置")
        form = QFormLayout()

        self.cmb_driver = QComboBox()
        for dt in DriverType:
            self.cmb_driver.addItem(dt.value, dt)
        self.cmb_driver.currentIndexChanged.connect(self._on_driver_changed)

        self.txt_host = QLineEdit("127.0.0.1")
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(502)

        self.spn_unit_id = QSpinBox()
        self.spn_unit_id.setRange(0, 255)
        self.spn_unit_id.setValue(1)

        self.spn_timeout = QDoubleSpinBox()
        self.spn_timeout.setRange(0.1, 30.0)
        self.spn_timeout.setValue(2.0)
        self.spn_timeout.setSuffix(" s")

        self.spn_poll_interval = QSpinBox()
        self.spn_poll_interval.setRange(100, 10000)
        self.spn_poll_interval.setValue(500)
        self.spn_poll_interval.setSuffix(" ms")

        # 串口参数 (RTU 模式)
        self.txt_serial = QLineEdit("/dev/ttyUSB0")
        self.spn_baud = QComboBox()
        self.spn_baud.addItems(["9600", "19200", "38400", "57600", "115200"])

        form.addRow("驱动类型:", self.cmb_driver)
        form.addRow("IP 地址:", self.txt_host)
        form.addRow("端口:", self.spn_port)
        form.addRow("从站 ID:", self.spn_unit_id)
        form.addRow("超时:", self.spn_timeout)
        form.addRow("轮询间隔:", self.spn_poll_interval)
        form.addRow("串口:", self.txt_serial)
        form.addRow("波特率:", self.spn_baud)

        group.setLayout(form)
        layout.addWidget(group)

        # ── 按钮 ──
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("🔌 连接")
        self.btn_connect.setObjectName("btnConnect")
        self.btn_connect.clicked.connect(self._on_connect)

        self.btn_disconnect = QPushButton("⏏ 断开")
        self.btn_disconnect.setObjectName("btnDisconnect")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._on_disconnect)

        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)
        layout.addLayout(btn_layout)

        # 状态
        self.lbl_status = QLabel("⚪ 未连接")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #6c7086; padding: 8px;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        self._on_driver_changed()

    def _on_driver_changed(self):
        dt = self.cmb_driver.currentData()
        is_tcp = dt in (DriverType.MODBUS_TCP, DriverType.SIEMENS_S7)
        is_modbus = dt in (DriverType.MODBUS_TCP, DriverType.MODBUS_RTU)
        is_rtu = dt == DriverType.MODBUS_RTU

        self.txt_host.setEnabled(is_tcp)
        self.spn_port.setEnabled(is_tcp)
        self.spn_unit_id.setEnabled(is_modbus)
        self.txt_serial.setEnabled(is_rtu)
        self.spn_baud.setEnabled(is_rtu)

        if dt == DriverType.SIEMENS_S7:
            self.spn_port.setValue(102)

    def _on_connect(self):
        dt = self.cmb_driver.currentData()
        config = ConnectionConfig(
            driver_type=dt,
            host=self.txt_host.text(),
            port=self.spn_port.value(),
            unit_id=self.spn_unit_id.value(),
            serial_port=self.txt_serial.text(),
            baudrate=int(self.spn_baud.currentText()),
            timeout=self.spn_timeout.value(),
        )
        self._config = config
        self._poll_interval = self.spn_poll_interval.value()
        self.connect_requested.emit(config)

    def _on_disconnect(self):
        self.disconnect_requested.emit()

    def get_config(self) -> ConnectionConfig:
        dt = self.cmb_driver.currentData()
        return ConnectionConfig(
            driver_type=dt,
            host=self.txt_host.text(),
            port=self.spn_port.value(),
            unit_id=self.spn_unit_id.value(),
            serial_port=self.txt_serial.text(),
            baudrate=int(self.spn_baud.currentText()),
            timeout=self.spn_timeout.value(),
        )

    def get_poll_interval(self) -> int:
        return self.spn_poll_interval.value()

    def set_connected(self, connected: bool, status: str = ""):
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        if connected:
            self.lbl_status.setText("🟢 " + (status or "已连接"))
            self.lbl_status.setStyleSheet("color: #a6e3a1; padding: 8px;")
        else:
            self.lbl_status.setText("🔴 " + (status or "已断开"))
            self.lbl_status.setStyleSheet("color: #f38ba8; padding: 8px;")

    def set_error(self, msg: str):
        self.lbl_status.setText(f"⚠ {msg}")
        self.lbl_status.setStyleSheet("color: #fab387; padding: 8px;")


# ── 数据监控表 ────────────────────────────────
class DataMonitorTable(QWidget):
    """实时数据监控表格"""

    tag_added = pyqtSignal(TagInfo)
    tag_removed = pyqtSignal(str)
    write_requested = pyqtSignal(int, int)  # address, value

    def __init__(self):
        super().__init__()
        self._tags: dict[str, DataPoint] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_add = QPushButton("➕ 添加标签")
        self.btn_add.clicked.connect(self._add_tag_dialog)
        self.btn_del = QPushButton("🗑 删除选中")
        self.btn_del.clicked.connect(self._remove_tag)
        self.btn_export = QPushButton("📊 导出 CSV")
        self.btn_export.clicked.connect(self._export_csv)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_del)
        toolbar.addWidget(self.btn_export)
        toolbar.addStretch()
        self.lbl_count = QLabel("标签: 0")
        toolbar.addWidget(self.lbl_count)
        layout.addLayout(toolbar)

        # 表格
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "名称", "地址", "类型", "原始值", "换算值", "单位", "质量", "时间"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_cell_double_click)
        layout.addWidget(self.table)

    def _add_tag_dialog(self):
        """添加标签对话框"""
        dlg = QMessageBox(self)
        dlg.setWindowTitle("添加数据标签")
        dlg.setText("请在右侧标签管理面板中添加数据标签。\n"
                     "快捷添加 — 点击工具栏 「导入标签配置」 可从 JSON 文件批量导入。")
        dlg.exec()

    def _remove_tag(self):
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            name = self.table.item(row, 0).text()
            self.tag_removed.emit(name)
            self.table.removeRow(row)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "plc_data.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            headers = [self.table.horizontalHeaderItem(i).text()
                       for i in range(self.table.columnCount())]
            f.write(','.join(headers) + '\n')
            for row in range(self.table.rowCount()):
                vals = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    vals.append(item.text() if item else '')
                f.write(','.join(vals) + '\n')

    def update_data(self, dps: list[DataPoint]):
        """更新表格数据"""
        for dp in dps:
            self._tags[dp.tag.name] = dp
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self._tags))
        for i, (name, dp) in enumerate(self._tags.items()):
            items = [
                QTableWidgetItem(name),
                QTableWidgetItem(str(dp.tag.address)),
                QTableWidgetItem(dp.tag.data_type),
                QTableWidgetItem(str(dp.raw_value) if dp.raw_value is not None else "N/A"),
                QTableWidgetItem(f"{dp.value:.3f}" if isinstance(dp.value, float) else str(dp.value or '')),
                QTableWidgetItem(dp.tag.unit),
                QTableWidgetItem("✓" if dp.quality else "✗"),
                QTableWidgetItem(dp.timestamp.strftime("%H:%M:%S.%f")[:-3]),
            ]
            if not dp.quality:
                items[6].setForeground(QColor(243, 139, 168))
            for j, item in enumerate(items):
                self.table.setItem(i, j, item)
        self.lbl_count.setText(f"标签: {len(self._tags)}")

    def _on_cell_double_click(self, row: int, col: int):
        """双击写入值"""
        if col not in (3, 4):
            return
        name = self.table.item(row, 0).text()
        dp = self._tags.get(name)
        if not dp or dp.tag.read_only:
            return

        current = self.table.item(row, 4).text()
        new_val, ok = QInputDialog.getInt(
            self, "写入寄存器", f"新值 ({dp.tag.name} @ {dp.tag.address}):",
            value=int(dp.raw_value or 0) if dp.raw_value is not None else 0
        )
        if ok:
            self.write_requested.emit(dp.tag.address, new_val)


# ── 实时曲线面板 ──────────────────────────────
class RealTimePlot(QWidget):
    """实时曲线图 (基于 pyqtgraph)"""

    def __init__(self):
        super().__init__()
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._data_buffers: dict[str, list] = {}
        self._time_buffer: list[float] = []
        self._max_points = 600  # 10分钟 @ 1s
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_pause = QPushButton("⏯ 暂停")
        self.btn_pause.setCheckable(True)
        toolbar.addWidget(self.btn_pause)
        self.btn_clear = QPushButton("🗑 清除")
        self.btn_clear.clicked.connect(self._clear)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 绘图区域
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#181825')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', '值')
        self.plot_widget.setLabel('bottom', '时间', units='s')
        self.plot_widget.addLegend(offset=(-10, 10))
        layout.addWidget(self.plot_widget)

    def add_curve(self, tag_name: str, color: str = None):
        """添加曲线"""
        if tag_name in self._curves:
            return
        if color is None:
            color = pg.intColor(len(self._curves), hues=12)
        curve = self.plot_widget.plot(
            [], [], pen=pg.mkPen(color=color, width=2),
            name=tag_name
        )
        self._curves[tag_name] = curve
        self._data_buffers[tag_name] = []

    def remove_curve(self, tag_name: str):
        if tag_name in self._curves:
            self.plot_widget.removeItem(self._curves[tag_name])
            del self._curves[tag_name]
            del self._data_buffers[tag_name]

    def update_data(self, dps: list[DataPoint]):
        """更新曲线数据"""
        if self.btn_pause.isChecked():
            return

        t = len(self._time_buffer) * 0.5  # 模拟时间轴
        self._time_buffer.append(t)

        for dp in dps:
            name = dp.tag.name
            if name not in self._curves:
                self.add_curve(name)

            val = dp.value if dp.value is not None else 0.0
            if isinstance(val, bool):
                val = 1.0 if val else 0.0

            self._data_buffers[name].append(float(val))

        # 裁剪
        if len(self._time_buffer) > self._max_points:
            self._time_buffer[:] = self._time_buffer[-self._max_points:]
            for buf in self._data_buffers.values():
                buf[:] = buf[-self._max_points:]

        # 更新曲线
        for name, curve in self._curves.items():
            buf = self._data_buffers.get(name, [])
            t_buf = self._time_buffer[-len(buf):] if buf else []
            curve.setData(t_buf, buf)

    def _clear(self):
        self._time_buffer.clear()
        self._data_buffers.clear()
        for curve in self._curves.values():
            curve.setData([], [])


# ── 标签管理面板 ──────────────────────────────
class TagManagerPanel(QWidget):
    """数据标签管理器"""

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("标签配置")
        form = QFormLayout()

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("例如: 反应温度")

        self.spn_addr = QSpinBox()
        self.spn_addr.setRange(0, 65535)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["int16", "uint16", "int32", "float32", "bool"])

        self.spn_scale = QDoubleSpinBox()
        self.spn_scale.setRange(0.0001, 1000000)
        self.spn_scale.setValue(1.0)

        self.spn_offset = QDoubleSpinBox()
        self.spn_offset.setRange(-1000000, 1000000)

        self.txt_unit = QLineEdit()
        self.txt_unit.setPlaceholderText("例如: ℃, bar, %")

        self.chk_readonly = QCheckBox("只读")

        form.addRow("名称:", self.txt_name)
        form.addRow("地址:", self.spn_addr)
        form.addRow("类型:", self.cmb_type)
        form.addRow("缩放:", self.spn_scale)
        form.addRow("偏移:", self.spn_offset)
        form.addRow("单位:", self.txt_unit)
        form.addRow("", self.chk_readonly)

        group.setLayout(form)
        layout.addWidget(group)

        # 按钮
        self.btn_add = QPushButton("✅ 添加到监控")
        self.btn_add.clicked.connect(self._add)
        layout.addWidget(self.btn_add)

        # 已添加列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["名称", "地址", "类型"])
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree)

        # 导入/导出
        btn_row = QHBoxLayout()
        self.btn_import = QPushButton("📥 导入")
        self.btn_import.clicked.connect(self._import)
        self.btn_export = QPushButton("📤 导出")
        self.btn_export.clicked.connect(self._export)
        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_export)
        layout.addLayout(btn_row)

    def _add(self):
        name = self.txt_name.text().strip()
        if not name:
            return

        tag = TagInfo(
            name=name,
            address=self.spn_addr.value(),
            data_type=self.cmb_type.currentText(),
            read_only=self.chk_readonly.isChecked(),
            scale=self.spn_scale.value(),
            offset=self.spn_offset.value(),
            unit=self.txt_unit.text(),
        )
        item = QTreeWidgetItem([name, str(tag.address), tag.data_type])
        item.setData(0, Qt.ItemDataRole.UserRole, tag)
        self.tree.addTopLevelItem(item)
        self.txt_name.clear()

    def get_tags(self) -> list[TagInfo]:
        tags = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            tag = item.data(0, Qt.ItemDataRole.UserRole)
            if tag:
                tags.append(tag)
        return tags

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入标签配置", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for td in data:
                tag = TagInfo(**td)
                item = QTreeWidgetItem([tag.name, str(tag.address), tag.data_type])
                item.setData(0, Qt.ItemDataRole.UserRole, tag)
                self.tree.addTopLevelItem(item)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出标签配置", "tags.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            import json
            tags = self.get_tags()
            data = [{
                'name': t.name, 'address': t.address,
                'data_type': t.data_type, 'read_only': t.read_only,
                'scale': t.scale, 'offset': t.offset, 'unit': t.unit
            } for t in tags]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))


# ── Ladder Logic 编程编辑器 ─────────────────────
class LadderEditor(QWidget):
    """梯形图编程器 (简易版)"""

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        tb = QHBoxLayout()
        for name, tag in [
            ("常开", "| |"), ("常闭", "|/|"), ("线圈", "( )"),
            ("定时器", "[TON]"), ("计数器", "[CTU]"), ("比较", "[CMP]"),
            ("MOVE", "[MOV]"), ("加法", "[ADD]"),
        ]:
            btn = QPushButton(name)
            btn.setMaximumWidth(80)
            btn.clicked.connect(lambda _, t=tag: self._insert_element(t))
            tb.addWidget(btn)
        tb.addStretch()

        self.btn_compile = QPushButton("🔧 编译检查")
        self.btn_compile.setObjectName("btnStartPoll")
        tb.addWidget(self.btn_compile)

        self.btn_sim = QPushButton("▶ 模拟运行")
        tb.addWidget(self.btn_sim)

        layout.addLayout(tb)

        # 编程区域
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "; ── 梯形逻辑 (Instruction List / 结构化文本) ──\n"
            "; 支持简易 IL 语法:\n"
            ";   LD  I0.0    -- 装载常开触点\n"
            ";   LDN I0.1    -- 装载常闭触点\n"
            ";   A   I0.2    -- 串联常开\n"
            ";   AN  I0.3    -- 串联常闭\n"
            ";   O   I0.4    -- 并联常开\n"
            ";   =   Q0.0    -- 输出线圈\n"
            ";   TON T37, 100 -- 定时器\n"
            ";   MOV VW0, 100 -- 赋值\n"
            "\n"
            "; 示例 - 电机启停控制:\n"
            "NETWORK 1  // 启停控制\n"
            "LD  I0.0     ; 启动按钮\n"
            "O   Q0.0     ; 自锁\n"
            "AN  I0.1     ; 停止按钮\n"
            "=   Q0.0     ; 电机输出\n"
            "\n"
            "NETWORK 2  // 定时器\n"
            "LD  Q0.0\n"
            "TON T37, 50  ; 50*100ms = 5s\n"
            "\n"
            "NETWORK 3  // 比较输出\n"
            "LDW> VW10, 500  ; 当 VW10 > 500\n"
            "=   Q0.1         ; 报警灯\n"
        )
        self.editor.setStyleSheet("""
            QTextEdit {
                background: #11111b; color: #cdd6f4;
                font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
                font-size: 14px; line-height: 1.6;
                border: 2px solid #313244; border-radius: 6px;
            }
        """)
        layout.addWidget(self.editor)

        # 输出区
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(150)
        self.output.setStyleSheet("""
            QTextEdit {
                background: #11111b; color: #a6e3a1;
                font-family: monospace; font-size: 12px;
                border: 1px solid #313244; border-radius: 4px;
            }
        """)
        layout.addWidget(self.output)

        self.btn_compile.clicked.connect(self._compile)
        self.btn_sim.clicked.connect(self._simulate)

    def _insert_element(self, element: str):
        cursor = self.editor.textCursor()
        cursor.insertText(element + " ")
        self.editor.setFocus()

    def _compile(self):
        code = self.editor.toPlainText().strip()
        if not code:
            self.output.setText("⚠ 无代码可供编译")
            return

        errors = []
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line.startswith(';') or line.startswith('//') or not line:
                continue

            # 基本语法检查
            parts = line.split()
            if parts and parts[0] in ('LD', 'LDN', 'A', 'AN', 'O', 'ON', '=', 'TON', 'CTU', 'MOV', 'LDW>'):
                pass  # 已知指令
            elif parts and parts[0].startswith('NETWORK'):
                pass  # 网络分隔
            elif parts:
                errors.append(f"  ⚠ Line {i}: 未知指令 '{parts[0]}' — {line}")

        if errors:
            self.output.setText("❌ 编译错误:\n" + '\n'.join(errors))
        else:
            self.output.setText(f"✅ 编译通过 — {len(lines)} 行, 无语法错误")

    def _simulate(self):
        code = self.editor.toPlainText().strip()
        if not code:
            self.output.setText("⚠ 无代码可供模拟")
            return

        # 简易 IL 解释器
        output_lines = ["▶ 模拟运行结果:", ""]
        variables = {}
        i0_0 = True   # 模拟输入
        i0_1 = False
        q0_0 = False

        for line in code.split('\n'):
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('//'):
                if line.startswith(';'):
                    output_lines.append(f"  {line}")
                continue
            if line.startswith('NETWORK'):
                output_lines.append(f"\n--- {line} ---")
                continue

            parts = line.split()
            instr = parts[0].upper() if parts else ''

            if instr == 'LD':
                if parts[1] == 'I0.0': q0_0 = i0_0
                elif parts[1] == 'Q0.0': pass  # 保持
                output_lines.append(f"  LD  {parts[1]} → RLO={q0_0}")
            elif instr == 'O':
                if parts[1] == 'Q0.0':
                    q0_0 = True  # 自锁
                output_lines.append(f"  O   {parts[1]} → RLO={q0_0}")
            elif instr == 'AN':
                if parts[1] == 'I0.1':
                    q0_0 = q0_0 and (not i0_1)
                output_lines.append(f"  AN  {parts[1]} → RLO={q0_0}")
            elif instr == '=':
                variables[parts[1]] = q0_0
                output_lines.append(f"  =   {parts[1]} → {'ON' if q0_0 else 'OFF'}")

        output_lines.append(f"\n📊 最终状态: I0.0=ON, I0.1=OFF → Q0.0={'ON (电机运行)' if q0_0 else 'OFF'}")
        self.output.setText('\n'.join(output_lines))


# ── 主窗口 ─────────────────────────────────────
class MainWindow(QMainWindow):
    """PLC 数据采集与编程工具 ─ 主窗口"""

    def __init__(self):
        super().__init__()
        self._driver: Optional[PLCDriver] = None
        self._worker: Optional[CommWorker] = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_data)
        self._init_ui()
        self._init_menu()

    def _init_ui(self):
        self.setWindowTitle("🦞 PLC 数据采集与编程工具 v1.0")
        self.setMinimumSize(1280, 800)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 左侧面板
        left_panel = QWidget()
        left_panel.setMaximumWidth(380)
        left_layout = QVBoxLayout(left_panel)

        self.conn_panel = ConnectionPanel()
        self.conn_panel.connect_requested.connect(self._do_connect)
        self.conn_panel.disconnect_requested.connect(self._do_disconnect)
        left_layout.addWidget(self.conn_panel)

        self.tag_panel = TagManagerPanel()
        left_layout.addWidget(self.tag_panel)

        main_layout.addWidget(left_panel)

        # 右侧 Tab
        self.tabs = QTabWidget()

        self.monitor_table = DataMonitorTable()
        self.monitor_table.write_requested.connect(self._do_write)
        self.tabs.addTab(self.monitor_table, "📊 数据监控")

        self.realtime_plot = RealTimePlot()
        self.tabs.addTab(self.realtime_plot, "📈 实时曲线")

        self.ladder_editor = LadderEditor()
        self.tabs.addTab(self.ladder_editor, "💻 梯形图编程")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_conn = QLabel("⚪ 未连接")
        self.lbl_tags = QLabel("标签: 0")
        self.lbl_rate = QLabel("采集: 0 Hz")
        self.status_bar.addWidget(self.lbl_conn)
        self.status_bar.addWidget(self.lbl_tags)
        self.status_bar.addPermanentWidget(self.lbl_rate)

    def _init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")
        act_import = QAction("导入标签配置...", self)
        act_import.triggered.connect(self.tag_panel._import)
        act_export = QAction("导出标签配置...", self)
        act_export.triggered.connect(self.tag_panel._export)
        act_exit = QAction("退出", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_import)
        file_menu.addAction(act_export)
        file_menu.addSeparator()
        file_menu.addAction(act_exit)

        conn_menu = menubar.addMenu("连接")
        act_connect = QAction("连接", self)
        act_connect.triggered.connect(lambda: self.conn_panel._on_connect())
        act_disconnect = QAction("断开", self)
        act_disconnect.triggered.connect(self._do_disconnect)
        conn_menu.addAction(act_connect)
        conn_menu.addAction(act_disconnect)

        help_menu = menubar.addMenu("帮助")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ── 连接管理 ──────────────────────────────

    def _do_connect(self, config: ConnectionConfig):
        """建立连接"""
        # 创建对应驱动
        dt = config.driver_type
        if dt in (DriverType.MODBUS_TCP, DriverType.MODBUS_RTU):
            self._driver = ModbusDriver(dt)
        elif dt == DriverType.SIEMENS_S7:
            self._driver = S7Driver()
        else:
            self.statusBar().showMessage(f"不支持的驱动: {dt.value}")
            return

        # 将标签注册到驱动
        tags = self.tag_panel.get_tags()
        for t in tags:
            self._driver.add_tag(t)

        # 启动通讯线程
        self._worker = CommWorker(
            self._driver, config,
            poll_interval=self.conn_panel.get_poll_interval()
        )
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.data_received.connect(self._on_data)
        self._worker.start()

        self.conn_panel.set_connected(True, "连接中...")
        self.statusBar().showMessage(f"正在连接 {config.host}...")

    def _do_disconnect(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        self._driver = None
        self._worker = None
        self.conn_panel.set_connected(False)
        self.lbl_conn.setText("⚪ 未连接")
        self.statusBar().showMessage("已断开连接")

    def _do_write(self, address: int, value: int):
        """执行写入操作"""
        if not self._driver:
            QMessageBox.warning(self, "未连接", "请先连接到 PLC")
            return
        try:
            loop = asyncio.new_event_loop()
            ok = loop.run_until_complete(self._driver.write_register(address, value))
            loop.close()
            if ok:
                self.statusBar().showMessage(f"✅ 写入成功: 地址 {address} ← {value}")
            else:
                self.statusBar().showMessage(f"❌ 写入失败: 地址 {address}")
        except Exception as e:
            self.statusBar().showMessage(f"❌ 写入错误: {e}")

    def _poll_data(self):
        """同步轮询 (不使用线程时)"""
        if not self._driver or self._driver.state != ConnectionState.CONNECTED:
            return
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            dps = loop.run_until_complete(self._driver.read_all_tags())
            loop.close()
            if dps:
                self._on_data(dps)
        except Exception:
            pass

    # ── 信号处理 ──────────────────────────────

    def _on_connected(self):
        self.conn_panel.set_connected(True)
        self.lbl_conn.setText("🟢 已连接")
        self.statusBar().showMessage("✅ 连接成功 — 开始数据采集")

    def _on_disconnected(self):
        self.conn_panel.set_connected(False)
        self.lbl_conn.setText("⚪ 未连接")

    def _on_error(self, msg: str):
        self.conn_panel.set_error(msg)
        self.statusBar().showMessage(f"⚠ {msg}")

    def _on_data(self, dps: list[DataPoint]):
        if not isinstance(dps, list) or not dps:
            return
        self.monitor_table.update_data(dps)
        self.realtime_plot.update_data(dps)
        self.lbl_tags.setText(f"标签: {len(dps)}")

    def _show_about(self):
        QMessageBox.about(
            self, "关于",
            "<h2>🦞 PLC 数据采集与编程工具 v1.0</h2>"
            "<p>基于 PyQt6 + pyqtgraph 构建</p>"
            "<p><b>支持的驱动:</b></p>"
            "<ul>"
            "<li>Modbus TCP / Modbus RTU (pymodbus)</li>"
            "<li>Siemens S7-1200/1500/300/400 (snap7)</li>"
            "</ul>"
            "<p><b>功能:</b></p>"
            "<ul>"
            "<li>多协议 PLC 连接与数据采集</li>"
            "<li>实时数据监控表格</li>"
            "<li>多通道实时趋势曲线</li>"
            "<li>梯形图编程器 (IL 语法)</li>"
            "<li>标签配置导入/导出 (JSON)</li>"
            "<li>数据 CSV 导出</li>"
            "</ul>"
        )

    def closeEvent(self, event):
        self._do_disconnect()
        event.accept()


# ── main ────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
