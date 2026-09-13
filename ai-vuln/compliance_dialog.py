# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 合规问卷填报对话框

独立文件，避免继续把 main_window.py 撑大。
AI 建议填报通过信号 ai_suggest_requested 交给主窗口的线程执行，
对话框本身不发起任何耗时调用（否则会卡住 UI 线程）。
"""
import logging
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QProgressBar, QAbstractItemView,
)

from compliance_questionnaire import (
    QuestionnaireEngine, ANSWERABLE_STATUSES, normalize_status,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_UNFILLED_OPTION = '— 未填报 —'

# 判定 → 下拉框底色，让整表的填报状况一眼可见
_STATUS_STYLE = {
    '符合': 'background:#e8f5e9;',
    '部分符合': 'background:#fff8e1;',
    '不符合': 'background:#ffebee;',
    '不适用': 'background:#f5f5f5;',
}

COL_ID, COL_DOMAIN, COL_QUESTION, COL_STATUS, COL_NOTE, COL_EVIDENCE, COL_AI = range(7)


class ComplianceQuestionnaireDialog(QDialog):
    """合规问卷填报对话框"""

    ai_suggest_requested = pyqtSignal(list)      # List[ComplianceControl]

    def __init__(self, standard: str, db, level: str = 'ALL',
                 business_system: str = '', parent=None):
        super().__init__(parent)
        self.standard = standard
        self.level = level
        self.business_system = business_system
        self.engine = QuestionnaireEngine(standard, db, level)
        self._rows: List[Dict] = []

        self.setWindowTitle(f'{self.engine.engine.standard_name} — 合规问卷填报')
        self.resize(1400, 800)
        self._build_ui()
        self.reload()

    # ------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel('业务系统:'))
        self.system_input = QLineEdit(self.business_system)
        self.system_input.setPlaceholderText('留空则填报到默认作用域（组织级条款始终全局复用）')
        self.system_input.setMaximumWidth(320)
        top.addWidget(self.system_input)
        reload_btn = QPushButton('切换/刷新')
        reload_btn.clicked.connect(self._on_switch_system)
        top.addWidget(reload_btn)
        top.addStretch()
        self.progress_label = QLabel('')
        self.progress_label.setStyleSheet('font-weight:bold;color:#1a237e;')
        top.addWidget(self.progress_label)
        layout.addLayout(top)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ['条款', '安全层面', '问题 / 证明材料提示', '判定', '说明依据', '证据材料', 'AI建议'])
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_QUESTION, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_NOTE, QHeaderView.Stretch)
        for col in (COL_ID, COL_DOMAIN, COL_STATUS, COL_EVIDENCE, COL_AI):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        self.hint = QLabel('提示：组织级条款（如制度、机构、人员）填一次即可，'
                           '所有业务系统共用；系统级条款按业务系统分别填报。')
        self.hint.setStyleSheet('color:#616161;font-size:13px;')
        layout.addWidget(self.hint)

        btns = QHBoxLayout()
        self.ai_btn = QPushButton('AI 建议填报（仅供参考）')
        self.ai_btn.clicked.connect(self._on_ai_suggest)
        btns.addWidget(self.ai_btn)

        apply_ai_btn = QPushButton('采纳全部 AI 建议')
        apply_ai_btn.clicked.connect(self._apply_all_suggestions)
        btns.addWidget(apply_ai_btn)

        btns.addStretch()
        save_btn = QPushButton('保存填报')
        save_btn.setObjectName('saveBtn')
        save_btn.clicked.connect(self._on_save)
        btns.addWidget(save_btn)

        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    # ------------------------------------------------------------
    def reload(self):
        """从数据库重新载入条款与已填答案"""
        if hasattr(self, 'system_input'):
            self.business_system = self.system_input.text().strip()
        self._rows = self.engine.to_rows(self.business_system)
        self.table.setRowCount(len(self._rows))

        for i, row in enumerate(self._rows):
            self.table.setItem(i, COL_ID, QTableWidgetItem(row['control_id']))
            scope_tag = '组织级' if row['scope'] == 'org' else '系统级'
            self.table.setItem(i, COL_DOMAIN,
                               QTableWidgetItem(f"{row['domain']}\n[{scope_tag}] {row['category']}"))

            question = row['question'] or row['requirement']
            if row['evidence_hint']:
                question += f"\n需备材料：{row['evidence_hint']}"
            q_item = QTableWidgetItem(question)
            q_item.setToolTip(row['requirement'])
            q_item.setFlags(q_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, COL_QUESTION, q_item)

            combo = QComboBox()
            combo.addItem(_UNFILLED_OPTION)
            combo.addItems(list(ANSWERABLE_STATUSES))
            current = row['status'] if row['answered'] else _UNFILLED_OPTION
            combo.setCurrentText(current)
            combo.currentTextChanged.connect(
                lambda text, c=combo: c.setStyleSheet(_STATUS_STYLE.get(text, '')))
            combo.setStyleSheet(_STATUS_STYLE.get(current, ''))
            self.table.setCellWidget(i, COL_STATUS, combo)

            self.table.setItem(i, COL_NOTE, QTableWidgetItem(row['note']))
            self.table.setItem(i, COL_EVIDENCE, QTableWidgetItem(row['evidence_ref']))
            ai_item = QTableWidgetItem('')
            ai_item.setFlags(ai_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, COL_AI, ai_item)

        self.table.resizeRowsToContents()
        self._refresh_progress()

    def _refresh_progress(self):
        p = self.engine.progress(self.business_system)
        pct = int(round((p['rate'] or 0) * 100))
        self.progress_bar.setValue(pct)
        scope = self.business_system or '默认作用域'
        self.progress_label.setText(
            f"作用域：{scope}　填报进度：{p['filled']}/{p['total']}（{pct}%）　待填 {p['pending']} 条")

    def _on_switch_system(self):
        self.business_system = self.system_input.text().strip()
        self.reload()

    # ------------------------------------------------------------
    def collect(self) -> Dict[str, Dict]:
        """收集界面上已选定判定的行（未填报的行不提交，避免覆盖已有答案）"""
        answers = {}
        for i, row in enumerate(self._rows):
            combo = self.table.cellWidget(i, COL_STATUS)
            if combo is None:
                continue
            status = normalize_status(combo.currentText())
            if status is None:
                continue
            note_item = self.table.item(i, COL_NOTE)
            ev_item = self.table.item(i, COL_EVIDENCE)
            answers[row['control_id']] = {
                'status': status,
                'note': note_item.text() if note_item else '',
                'evidence_ref': ev_item.text() if ev_item else '',
            }
        return answers

    def _on_save(self):
        answers = self.collect()
        if not answers:
            QMessageBox.information(self, '提示', '没有需要保存的填报内容。')
            return
        stats = self.engine.save_answers(answers, self.business_system)
        self.reload()
        if stats['rejected']:
            QMessageBox.warning(
                self, '部分未保存',
                f"已保存 {stats['saved']} 条，{stats['rejected']} 条因条款不存在或状态非法被拒绝。\n"
                f"详情见运行日志。")
        else:
            QMessageBox.information(self, '保存成功', f"已保存 {stats['saved']} 条填报记录。")

    # ------------------------------------------------------------
    def _on_ai_suggest(self):
        pending = self.engine.pending_controls(self.business_system)
        if not pending:
            QMessageBox.information(self, '提示', '当前作用域下没有待填报条款。')
            return
        self.ai_btn.setEnabled(False)
        self.ai_btn.setText('AI 分析中...')
        self.ai_suggest_requested.emit(pending)

    def apply_suggestions(self, suggestions: Optional[Dict[str, Dict]]):
        """接收主窗口线程返回的 AI 建议并回填到『AI建议』列。

        只填提示列，不直接改判定 —— AI 不替填报人签字。
        """
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText('AI 建议填报（仅供参考）')
        if not suggestions:
            QMessageBox.warning(self, 'AI 建议', 'AI 未返回任何建议（调用失败或不可用）。')
            return

        applied = 0
        for i, row in enumerate(self._rows):
            s = suggestions.get(row['control_id'])
            if not s:
                continue
            status = s.get('status')
            if status:
                conf = s.get('confidence', 0) or 0
                text = f"{status}（把握 {conf:.0%}）"
                applied += 1
            else:
                text = s.get('reason') or 'AI 未给出建议'
            item = self.table.item(i, COL_AI)
            if item is not None:
                item.setText(text)
                item.setToolTip((s.get('note') or '') + '\n' + (s.get('reason') or ''))
        QMessageBox.information(
            self, 'AI 建议', f'AI 对 {applied} 条条款给出了可采纳的建议，'
                             f'其余需人工确认。建议仅供参考，请核实后再保存。')

    def _apply_all_suggestions(self):
        """把 AI 建议列里带明确状态的建议填进判定下拉框（仍需人工点保存）"""
        applied = 0
        for i in range(self.table.rowCount()):
            item = self.table.item(i, COL_AI)
            combo = self.table.cellWidget(i, COL_STATUS)
            if item is None or combo is None:
                continue
            status = normalize_status((item.text() or '').split('（')[0].strip())
            if status is None:
                continue
            combo.setCurrentText(status)
            applied += 1
        if applied:
            QMessageBox.information(self, '已采纳',
                                    f'已把 {applied} 条 AI 建议填入判定列，请核对后点击「保存填报」。')
        else:
            QMessageBox.information(self, '提示', '没有可采纳的 AI 建议。')
