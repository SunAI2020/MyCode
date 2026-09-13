# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 主窗口 GUI"""
import sys
import os
import re
import logging
import subprocess
import sqlite3
import threading
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QTextEdit, QPlainTextEdit, QComboBox, QProgressBar, QGroupBox, QFormLayout,
    QCheckBox, QSpinBox, QMessageBox, QFileDialog, QSplitter,
    QStatusBar, QHeaderView, QToolBar, QRadioButton, QGridLayout,
    QFrame, QSizePolicy, QDialog, QMenu, QAction, QDateEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QDate
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPalette, QBrush

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import SEV_COLORS
from vuln_enrich import evidence_dict, remediation_dict
from audit_enrich import evidence_dict as _audit_evidence_dict, remediation_dict as _audit_remediation_dict


def _build_vuln_tooltip(vuln):
    """从结构化 evidence/remediation 拼接结果表悬浮提示"""
    ev = evidence_dict(vuln)
    rm = remediation_dict(vuln)
    lines = []
    if ev.get('summary'):
        lines.append(f"证据: {ev['summary']}")
    lines.append(f"端口: {ev.get('port', '')} | 协议: {ev.get('protocol', '')}")
    lines.append(f"服务: {ev.get('service', '')} | 版本: {ev.get('version', '')}")
    if ev.get('cve_id'):
        lines.append(f"CVE: {ev['cve_id']} | CVSS: {ev.get('cvss_score', '')} | 严重程度: {ev.get('severity', '')}")
    if ev.get('kev'):
        lines.append("⚠ CISA KEV 在野利用")
    if vuln.get('known_ransomware'):
        lines.append("⛔ 已知勒索软件利用 — 最高优先级立即处置")
    if vuln.get('epss_high'):
        lines.append(f"⚠ EPSS 高危利用概率: {vuln.get('epss_score', '')}")
    if rm:
        src = {'ai': 'AI', 'rule': '规则库', 'generic': '通用'}.get(rm.get('source'), rm.get('source', ''))
        lines.append(f"修复方案 ({src}):")
        for s in (rm.get('steps') or [])[:5]:
            lines.append(f"  • {s}")
        if rm.get('urgency'):
            lines.append(f"修复紧急度: {rm['urgency']}")
    return '\n'.join(lines)


def _honeypot_badge_item(vuln):
    """命中蜜罐/欺骗资产时返回紫色徽标项，否则返回空项。

    判定依据：finding_type=='honeypot'（实时扫描）或 description 以
    [蜜罐告警] 开头（历史重载兜底，因 finding_type 不落库）。
    """
    is_honeypot = (vuln.get('finding_type') == 'honeypot'
                   or vuln.get('honeypot_type')
                   or (vuln.get('description') or '').startswith('[蜜罐告警]'))
    if not is_honeypot:
        return QTableWidgetItem('')
    item = QTableWidgetItem('🍯 蜜罐')
    item.setBackground(QColor(106, 27, 154))
    item.setForeground(QColor(255, 255, 255))
    item.setTextAlignment(Qt.AlignCenter)
    return item


def _build_audit_tooltip(issue):
    """从结构化 evidence/remediation 拼接代码审计结果悬浮提示"""
    ev = _audit_evidence_dict(issue)
    rm = _audit_remediation_dict(issue)
    lines = []
    if ev.get('summary'):
        lines.append(f"证据: {ev['summary']}")
    if ev.get('code'):
        lines.append(f"代码: {ev['code'][:120]}")
    if ev.get('problem'):
        lines.append(f"问题: {ev['problem'][:200]}")
    if rm:
        src = {'ai': 'AI', 'rule': '规则', 'generic': '通用'}.get(rm.get('source'), rm.get('source', ''))
        lines.append(f"解决方案 ({src}):")
        for s in (rm.get('steps') or [])[:8]:
            lines.append(f"  • {s}")
        if rm.get('urgency'):
            lines.append(f"修复紧急度: {rm['urgency']}")
    return '\n'.join(lines)

# matplotlib 图表嵌入
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
# 中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    # PyInstaller 打包后：资源（assets/reports）定位到 EXE 同目录，与 database.py 保持一致
    PROJECT_DIR = os.path.dirname(sys.executable)
else:
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# 资产合规字段选项（空串在前 —— 未定级就该显示为空，不能默认塞一个等级）
COMPLIANCE_LEVEL_OPTIONS = ['', 'L1', 'L2', 'L3', 'L4']
DATA_CLASSIFICATION_OPTIONS = ['', '公开数据', '内部数据', '重要数据', '核心数据',
                               '个人信息', '敏感个人信息']

# ============ 工作线程 ============
class ScanThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, scanner, target, ports, scan_type, weak_pass=False,
                 zero_day_focus=False):
        super().__init__()
        self.scanner = scanner
        self.target = target
        self.ports = ports
        self.scan_type = scan_type
        self.weak_pass = weak_pass
        self.zero_day_focus = zero_day_focus

    def run(self):
        try:
            self.progress.emit(f"开始扫描: {self.target}")
            # 设置进度回调
            if hasattr(self.scanner, 'network_scanner'):
                self.scanner.network_scanner.set_progress_callback(
                    lambda msg: self.progress.emit(msg))
            result = self.scanner.scan_target(self.target, self.ports, self.scan_type,
                                              weak_pass=self.weak_pass,
                                              zero_day_focus=self.zero_day_focus)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AIScanEnhanceThread(QThread):
    """AI扫描增强线程 — 对扫描结果进行AI核验和分析"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)   # 核验后的漏洞列表 + AI分析
    error = pyqtSignal(str)

    def __init__(self, scan_result, api_key):
        super().__init__()
        self.scan_result = scan_result
        self.api_key = api_key
        self._stop_event = threading.Event()

    def stop(self):
        """协作式停止：置位事件，使 AIClient 终止子进程。"""
        self._stop_event.set()
        self.requestInterruption()

    def run(self):
        try:
            from ai_scan_enhancer import AIScanEnhancer

            enhancer = AIScanEnhancer(api_key=self.api_key, stop_event=self._stop_event)
            vulnerabilities = self.scan_result.get('vulnerabilities', [])

            if not vulnerabilities:
                self.finished.emit({
                    'verified_vulns': [],
                    'excluded_vulns': [],
                    'pre_filtered': [],
                    'ai_analysis': {},
                    'stats': {}
                })
                return

            # 构建扫描上下文
            total = len(vulnerabilities)
            services = set(v.get('service', '') for v in vulnerabilities)
            target = self.scan_result.get('target', 'Unknown')
            scan_context = (
                f"目标: {target}, "
                f"开放服务: {', '.join(sorted(services)[:10])}, "
                f"漏洞总数: {total}"
            )

            # 阶段1: 批量AI核验 + 版本预过滤
            self.progress.emit(f"AI核验阶段: 正在分析 {total} 个漏洞 (批量模式)...")
            verify_result = enhancer.verify_vulnerabilities(
                vulnerabilities,
                scan_context=scan_context,
                progress_callback=lambda msg: self.progress.emit(msg)
            )

            # 阶段2: AI生成风险分析
            if verify_result['confirmed'] and not self._stop_event.is_set():
                self.progress.emit("AI正在生成风险分析报告...")
                enhanced_scan = {
                    **self.scan_result,
                    'vulnerabilities': verify_result['confirmed'],
                    'ai_excluded': verify_result['excluded'],
                    'ai_stats': verify_result['stats'],
                }
                ai_analysis = enhancer.generate_ai_analysis(enhanced_scan)
            else:
                ai_analysis = {}

            self.finished.emit({
                'verified_vulns': verify_result['confirmed'],
                'excluded_vulns': verify_result['excluded'],
                'pre_filtered': verify_result.get('pre_filtered', []),
                'ai_analysis': ai_analysis,
                'stats': verify_result['stats'],
            })

        except Exception as e:
            import traceback
            self.error.emit(f"AI增强分析失败: {str(e)}\n{traceback.format_exc()}")


class WebScanThread(QThread):
    """Web 安全扫描线程 — 编排指纹/路径/目录/ZAP/主动检测"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, target_url, db, do_directory, do_zap, do_active, ai_enabled):
        super().__init__()
        self.target_url = target_url
        self.db = db
        self.do_directory = do_directory
        self.do_zap = do_zap
        self.do_active = do_active
        self.ai_enabled = ai_enabled
        self._stop_event = threading.Event()

    def stop(self):
        """协作式停止：置位事件，使 AI 核验阶段的子进程被终止。"""
        self._stop_event.set()
        self.requestInterruption()

    def run(self):
        try:
            from web_scanner import WebSecurityScanner
            scanner = WebSecurityScanner(db=self.db, ai_enabled=self.ai_enabled)
            result = scanner.scan(
                self.target_url,
                do_directory=self.do_directory,
                do_zap=self.do_zap,
                do_active=self.do_active,
                progress_callback=lambda msg: self.progress.emit(msg),
                stop_event=self._stop_event,
            )
            self.finished.emit(result)
        except Exception as e:
            import traceback
            self.error.emit(f"Web 扫描失败: {str(e)}\n{traceback.format_exc()}")


# 质量审计维度中文名映射（与 ai_code_reviewer.QUALITY_DIMENSIONS 保持一致）
DIMENSION_LABELS = {
    'security': '安全', 'architecture': '架构设计', 'logic': '逻辑问题',
    'function': '函数规范', 'completeness': '功能完整性', 'loop': '循环与复杂度',
    'invocation': '调用关系', 'interface': '接口规范', 'parameter': '参数传递',
    'naming': '命名标识', 'io': '输入输出', 'ui': '交互界面',
    'api': 'API设计', 'database': '数据库', 'supply_chain': '供应链',
}


class AIAuditThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, analyzer, target, analysis_type, api_key=None, enable_quality_review=False, enable_sca=True):
        super().__init__()
        self.analyzer = analyzer
        self.target = target
        self.analysis_type = analysis_type
        self.api_key = api_key
        self.enable_quality_review = enable_quality_review
        self.enable_sca = enable_sca
        self._stop_security_event = threading.Event()
        self._stop_quality_event = threading.Event()

    def stop_security(self):
        """请求停止 AI 安全核验阶段"""
        self._stop_security_event.set()

    def stop_quality(self):
        """请求停止代码质量/设计审计阶段"""
        self._stop_quality_event.set()

    def run(self):
        try:
            # 代码质量/设计检测（独立模块，与安全审计分离）
            if self.analysis_type == 'quality':
                self._run_quality_review()
                return

            # 根据审计类型配置分析器
            if self.analysis_type == 'claude_security':
                self.progress.emit("正在初始化 Claude AI 验证引擎...")
                from ai_verifier import AIVerifier
                verifier = AIVerifier(api_key=self.api_key, stop_event=self._stop_security_event)
                self.analyzer.ai_verifier = verifier
                self.analyzer.audit_type = 'claude_security'
            else:
                self.analyzer.ai_verifier = None
                self.analyzer.audit_type = 'code'

            self.progress.emit("正在进行AI代码安全分析...")
            result = self.analyzer.scan_directory(
                self.target,
                progress_callback=lambda msg: self.progress.emit(msg),
                enable_quality_review=self.enable_quality_review,
                enable_sca=self.enable_sca,
                stop_security=self._stop_security_event.is_set,
                stop_quality=self._stop_quality_event.is_set
            )
            analysis = self.analyzer.generate_report(result)
            self.finished.emit(analysis)
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")

    def _run_quality_review(self):
        """代码质量/设计检测独立执行体（架构/逻辑/接口/命名等设计缺陷）"""
        import os
        from datetime import datetime
        from ai_code_reviewer import AICodeReviewer
        from audit_dedup import AuditDeduplicator
        from audit_enrich import enrich_audit_findings

        self.progress.emit("正在启动代码质量/设计检测...")
        reviewer = AICodeReviewer(api_key=self.api_key, stop_event=self._stop_quality_event)
        quality_issues = reviewer.review_project(
            self.target,
            progress_callback=lambda msg: self.progress.emit(msg),
            should_stop=self._stop_quality_event.is_set)

        dedup = AuditDeduplicator().deduplicate(quality_issues)
        issues = enrich_audit_findings(dedup['unique'])

        severity_counts = {}
        dimension_counts = {}
        for issue in issues:
            sev = issue.get('severity', 'UNKNOWN')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            dim = issue.get('dimension', 'quality')
            dimension_counts[dim] = dimension_counts.get(dim, 0) + 1

        scan_result = {
            'target': self.target,
            'scan_time': datetime.now().isoformat(),
            'audit_type': 'quality',
            'issues': issues,
            'total_files_scanned': self._count_code_files(self.target),
            'total_vulnerabilities': len(issues),
            'severity_summary': severity_counts,
            'dimension_summary': dimension_counts,
            'quality_issues_count': len(issues),
            'security_issues_count': 0,
            'duplicate_count': len(dedup['duplicates']),
        }
        self.finished.emit(self.analyzer.generate_report(scan_result))

    @staticmethod
    def _count_code_files(path):
        """统计目标路径下可审计代码文件数量"""
        import os
        extensions = ['.py', '.js', '.ts', '.java', '.go', '.php', '.rb', '.c', '.cpp', '.html']
        skip = {'node_modules', '__pycache__', 'venv', '.git', 'dist', 'build'}
        if os.path.isfile(path):
            return 1
        count = 0
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip]
            for f in files:
                if os.path.splitext(f)[1].lower() in extensions:
                    count += 1
        return count


class ThreatIntelThread(QThread):
    """威胁情报收集线程（旧版，保留兼容）"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, collector, days=7):
        super().__init__()
        self.collector = collector
        self.days = days

    def run(self):
        try:
            self.progress.emit("正在从NVD获取最新CVE数据...")
            cves = self.collector.fetch_recent_cve(days=self.days)
            self.progress.emit(f"获取到{len(cves)}条CVE，正在同步到数据库...")
            count = self.collector.sync_to_database(cves)
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class IntelCollectThread(QThread):
    """全球威胁情报收集线程（新版-多源）"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, collector, start_date=None, end_date=None):
        super().__init__()
        self.collector = collector
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        try:
            def callback(msg):
                self.progress.emit(msg)
            self.collector.set_progress_callback(callback)
            results = self.collector.collect_all_intel(
                start_date=self.start_date, end_date=self.end_date
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ThreatIntelReportThread(QThread):
    """AI威胁情报综合报告生成线程 — 生成17章节深度分析报告"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, results, db, output_dir, start_date='', end_date=''):
        super().__init__()
        self.results = results
        self.db = db
        self.output_dir = output_dir
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        try:
            from threat_intel_reporter import ThreatIntelReporter
            from ai_client import AIClient

            ai = AIClient()
            reporter = ThreatIntelReporter(self.db, ai, self.output_dir)
            reporter.progress_callback = lambda msg: self.progress.emit(msg)
            report = reporter.generate_full_report(
                self.results,
                start_date=self.start_date,
                end_date=self.end_date,
            )
            self.finished.emit(report)
        except Exception as e:
            import traceback
            self.error.emit(f"AI报告生成失败: {str(e)}\n{traceback.format_exc()}")


class CveRepairThread(QThread):
    """CVE数据库修复线程 — 用cve_db_repair模块执行后台维护"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, operations, start_month=None, end_month=None, dry_run=False):
        super().__init__()
        self.operations = operations
        self.start_month = start_month
        self.end_month = end_month
        self.dry_run = dry_run
        self._stop = False

    def stop(self):
        self._stop = True

    def _emit(self, msg):
        if not self._stop:
            self.progress.emit(msg)

    def run(self):
        import sys, os, time
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from cve_db_repair import (
                get_conn, clean_fake_cves, backfill_cwe_patch,
                fetch_month, load_api_key_from_db, REQUEST_DELAY
            )
            load_api_key_from_db()
            results = {'cleaned': 0, 'backfilled': 0, 'added': 0, 'checked': 0}
            conn = get_conn()
            total_before = conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
            self._emit(f'数据库当前: {total_before} 条CVE')

            if 'clean_fakes' in self.operations:
                if self._stop:
                    conn.close()
                    return
                self._emit('=== 阶段 1: 清除假CVE ===')
                c = conn.cursor()
                # 已知假CVE
                from cve_db_repair import KNOWN_FAKES
                for cid in KNOWN_FAKES:
                    if self._stop:
                        break
                    if conn.execute('SELECT 1 FROM cve_database WHERE cve_id=?', (cid,)).fetchone():
                        self._emit(f'  [FAKE] 移除: {cid}')
                        if not self.dry_run:
                            conn.execute('DELETE FROM cve_database WHERE cve_id=?', (cid,))
                        results['cleaned'] += 1
                conn.commit()
                self._emit(f'清除 {results["cleaned"]} 条假CVE')

            if 'backfill' in self.operations:
                if self._stop:
                    conn.close()
                    return
                self._emit('=== 阶段 2: 回填CWE/补丁链接 ===')
                need = conn.execute(
                    "SELECT cve_id FROM cve_database WHERE cwe IS NULL OR cwe='' OR patch_link IS NULL OR patch_link=''"
                ).fetchall()
                self._emit(f'需回填: {len(need)} 条')
                from cve_db_repair import nvd_get, parse_cve, REQUEST_DELAY as _rd
                for i, row in enumerate(need):
                    if self._stop:
                        break
                    cid = row['cve_id']
                    if i % 10 == 0:
                        self._emit(f'  回填进度: {i+1}/{len(need)}')
                    try:
                        data = nvd_get({'cveId': cid})
                        if data and data.get('vulnerabilities'):
                            f = parse_cve(data['vulnerabilities'][0])
                            if not self.dry_run:
                                conn.execute(
                                    '''UPDATE cve_database SET cwe=?, patch_link=?, references_url=?,
                                       description=CASE WHEN description IS NULL OR description='' THEN ? ELSE description END,
                                       cvss_score=CASE WHEN cvss_score IS NULL THEN ? ELSE cvss_score END
                                       WHERE cve_id=?''',
                                    (f['cwe'], f['patch_link'], f['references_url'],
                                     f['description'], f['cvss_score'], cid))
                            results['backfilled'] += 1
                    except Exception:
                        pass
                    time.sleep(_rd)
                conn.commit()
                self._emit(f'回填完成: {results["backfilled"]} 条')

            if 'fetch' in self.operations:
                if self._stop:
                    return
                self._emit('=== 阶段 3: 逐月全网补全 ===')
                sm = self.start_month or '2000-01'
                em = self.end_month or datetime.now().strftime('%Y-%m')
                try:
                    cur = datetime.strptime(sm, '%Y-%m')
                    end = datetime.strptime(em, '%Y-%m')
                except ValueError:
                    self._emit(f'日期格式错误: {sm} ~ {em}')
                    conn.close()
                    return
                # end should be no later than now
                now = datetime.now()
                if end > now:
                    end = now
                total_m = (end.year - cur.year) * 12 + (end.month - cur.month) + 1
                self._emit(f'范围: {sm} ~ {em} ({total_m} 个月)')
                from cve_db_repair import fetch_month, REQUEST_DELAY
                idx = 0
                while cur <= end and not self._stop:
                    idx += 1
                    m_end = (datetime(cur.year, cur.month + 1, 1) - timedelta(days=1)
                             if cur.month < 12 else datetime(cur.year, 12, 31))
                    m_end = min(m_end, end)
                    self._emit(f'  [{idx}/{total_m}] {cur.strftime("%Y-%m")}...')
                    try:
                        fetch_month(cur, m_end, conn, results)
                    except Exception:
                        pass
                    conn.commit()
                    cur = m_end + timedelta(days=1)
                self._emit(f'逐月补全完成: 新增 {results["added"]} 条')

            total_after = conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
            conn.close()
            self._emit(f'全部完成: 清除{results["cleaned"]} 回填{results["backfilled"]} 新增{results["added"]}')
            self._emit(f'DB: {total_before} -> {total_after} (+{total_after-total_before})')
            self.finished.emit(results)
        except Exception as e:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            import traceback
            self._emit(f'错误: {e}\n{traceback.format_exc()}')
            self.error.emit(str(e))


class AssetDiscoveryThread(QThread):
    """资产发现线程 - 支持ICMP Ping / Nmap / TCP多种方式"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, scanner, target_range):
        super().__init__()
        self.scanner = scanner
        self.target_range = target_range
        self._running = True

    def run(self):
        try:
            def callback(msg):
                if self._running:
                    self.progress.emit(msg)

            self.scanner._cancel = False
            hosts = self.scanner.discover_assets(self.target_range, method='auto', callback=callback)
            self.finished.emit(hosts)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False
        self.scanner.cancel()


class ComplianceCheckThread(QThread):
    """合规检查线程：装配证据 → 引擎判定 → 可选AI研判 → 落库"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, db, standard, level='ALL', business_system='',
                 scan_id=None, target='', ai_enabled=False):
        super().__init__()
        self.db = db
        self.standard = standard
        self.level = level or 'ALL'
        self.business_system = business_system
        self.scan_id = scan_id
        self.target = target
        self.ai_enabled = ai_enabled
        self._running = True

    def run(self):
        try:
            from compliance_engine import ComplianceEngine, build_evidence
            from compliance_questionnaire import system_scope_key

            engine = ComplianceEngine(self.standard)
            self.progress.emit(f'已加载 {engine.standard_name}，共 {len(engine.controls)} 条条款')

            scan_rows = None
            target = self.target
            if self.scan_id is not None:
                task = self.db.scan.get_task(self.scan_id)
                if task:
                    scan_rows = self.db.scan.get_task_results(self.scan_id)
                    target = target or dict(task).get('target', '')
                    self.progress.emit(
                        f'复用扫描任务 #{self.scan_id} 的 {len(scan_rows)} 条结果作为技术证据')
                else:
                    # 不静默忽略：用户明确选了任务却取不到，必须说出来
                    self.progress.emit(f'⚠ 扫描任务 #{self.scan_id} 不存在，本次将无技术证据')
            else:
                self.progress.emit('未选择扫描任务，技术类条款将判为「证据不足」')

            scope_key = system_scope_key(self.business_system)
            # Web 侧证据另存在 web_scan_results 表，不随 scan_rows 一起来；
            # 不带上它，Web 安全条款只能永远报『证据不足』
            web_findings = []
            if target:
                try:
                    web_findings = self.db.get_web_scan_results(target=target) or []
                except Exception as e:
                    logger.error(f'读取 Web 扫描结果失败: {e}')
                    self.progress.emit(f'⚠ 读取 Web 扫描证据失败，Web 条款将缺证据：{e}')
            if web_findings:
                self.progress.emit(f'并入 {len(web_findings)} 条 Web 扫描发现作为证据')

            evidence = build_evidence(scan_rows, target=target, scope_key=scope_key,
                                      standard=self.standard, level=self.level,
                                      web_findings=web_findings)
            answers = self.db.get_questionnaire_answers(self.standard, scope_key, include_org=True)
            self.progress.emit(f'已载入 {len(answers)} 条问卷填报记录（作用域 {scope_key}）')

            if not self._running:
                return
            agg = engine.evaluate(evidence, answers=answers, level=self.level)
            self.progress.emit(
                f"判定完成：符合 {agg['counts'].get('符合', 0)} / "
                f"不符合 {agg['counts'].get('不符合', 0)} / "
                f"证据不足 {agg['counts'].get('证据不足', 0)} / "
                f"未填报 {agg['counts'].get('未填报', 0)}")

            ai_ran = False
            if self.ai_enabled and self._running:
                try:
                    from compliance_ai import ComplianceAI, merge_verdicts
                    ai = ComplianceAI()
                    if ai.available:
                        self.progress.emit('AI 研判中：复核填报 + 与技术证据交叉比对...')
                        # 两轮结论取较严重者：用 update() 会让交叉比对的『认可』
                        # 盖掉复核的『存疑』，把拿不准悄悄升级成没问题
                        verdicts = merge_verdicts(
                            ai.review_answers(agg['results'], self.progress.emit),
                            ai.cross_check(agg['results'], evidence, self.progress.emit))
                        engine.apply_ai_verdicts(agg['results'], verdicts)
                        remediation = ai.generate_remediation(agg['results'],
                                                              progress_callback=self.progress.emit)
                        for r in agg['results']:
                            if r['control_id'] in remediation:
                                r['recommendation'] = remediation[r['control_id']]
                        agg.update(engine.summarize(agg['results']))
                        ai_ran = True
                    else:
                        self.progress.emit('⚠ AI 不可用，本次跳过 AI 研判（条款标记为「未完成」）')
                except Exception as e:
                    # AI 失败不影响基础判定结果，但必须让用户知道没跑成
                    logger.error(f'合规 AI 研判失败: {e}')
                    self.progress.emit(f'⚠ AI 研判失败，已跳过：{e}')

            if not self._running:
                return
            history_id = self.db.save_compliance_result(agg, ai_enabled=ai_ran)
            agg['history_id'] = history_id
            agg['ai_ran'] = ai_ran
            self.finished.emit(agg)
        except Exception as e:
            logger.error(f'合规检查失败: {e}')
            self.error.emit(str(e))

    def stop(self):
        self._running = False


class ComplianceAISuggestThread(QThread):
    """问卷 AI 建议填报线程（结果仅作参考，不直接落库）"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, controls, db=None, scan_id=None, standard='', level='ALL'):
        super().__init__()
        self.controls = list(controls or [])
        self.db = db
        self.scan_id = scan_id
        self.standard = standard
        self.level = level

    def run(self):
        try:
            from compliance_ai import ComplianceAI
            from compliance_engine import build_evidence

            ai = ComplianceAI()
            if not ai.available:
                self.error.emit('AI 不可用：未检测到 Claude Code CLI，也未配置 API Key')
                return

            scan_rows = None
            if self.db is not None and self.scan_id is not None:
                scan_rows = self.db.scan.get_task_results(self.scan_id)
            evidence = build_evidence(scan_rows, standard=self.standard, level=self.level)

            self.finished.emit(ai.suggest_answers(self.controls, evidence, self.progress.emit))
        except Exception as e:
            logger.error(f'AI 建议填报失败: {e}')
            self.error.emit(str(e))


# ============ 主窗口 ============
def _get_logo_path():
    """获取LOGO文件路径（优先级: jpg > png）"""
    for ext in ['.jpg', '.png']:
        path = os.path.join(PROJECT_DIR, 'assets', f'logo{ext}')
        if os.path.exists(path):
            return path
    return ''


# 交付文档清单（帮助菜单 → 交付文档）：(文件名, 显示名)
DELIVERABLE_DOCS = [
    ('漏洞扫描系统需求规格说明书v1.1.html', '需求规格说明书 (HTML)'),
    ('漏洞扫描系统需求规格说明书v1.1.md', '需求规格说明书 (Markdown)'),
    ('软件架构设计说明书.html', '软件架构设计说明书 (HTML)'),
    ('软件架构设计说明书.docx', '软件架构设计说明书 (Word)'),
    ('漏洞扫描系统架构设计.md', '软件架构设计 (Markdown)'),
    ('研发需求差距分析与开发计划_20260818.html', '研发差距分析与开发计划 (HTML)'),
    ('研发需求差距分析与开发计划_20260818.md', '研发差距分析与开发计划 (Markdown)'),
    ('软件功能清单.html', '软件功能清单'),
]


def _docs_dir():
    """交付文档目录：优先 EXE/项目同目录的 文档/（可增删），回退 PyInstaller 内置资源"""
    candidates = [os.path.join(PROJECT_DIR, '文档')]
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(os.path.join(meipass, '文档'))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


def _make_white_transparent(pixmap, tolerance=40):
    """将QPixmap中的白色转为透明（保留其他颜色）"""
    from PyQt5.QtGui import QImage
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.red() > 255 - tolerance and color.green() > 255 - tolerance and color.blue() > 255 - tolerance:
                image.setPixelColor(x, y, QColor(255, 255, 255, 0))
    return QPixmap.fromImage(image)


class MainWindow(QMainWindow):
    # 定时扫描触发信号（调度器后台线程发出，主线程槽执行扫描）
    _scheduled_scan_triggered = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        # 线程安全消息缓冲（避免跨线程 QTextCursor 错误）
        self._msg_buffer = []
        self._msg_lock = __import__('threading').Lock()
        self._init_components()
        self._init_ui()
        self._update_status_bar()
        self._update_dashboard()

        # 启动消息刷新定时器（每100ms刷新一次）
        self._msg_timer = QTimer()
        self._msg_timer.timeout.connect(self._flush_messages)
        self._msg_timer.start(100)

        logger.info("AI漏洞扫描系统主窗口初始化完成")

    def _flush_messages(self):
        """刷新缓冲消息到日志控件"""
        if not self._msg_buffer:
            return
        with self._msg_lock:
            msgs = self._msg_buffer[:]
            self._msg_buffer.clear()
        cleared = set()
        for target, text in msgs:
            try:
                widget = getattr(self, target)
                if text == '__CLEAR__':
                    if target not in cleared:
                        widget.clear()
                        cleared.add(target)
                else:
                    widget.appendPlainText(text)
            except:
                pass

    def _safe_log(self, target: str, text: str):
        """线程安全的日志写入"""
        with self._msg_lock:
            self._msg_buffer.append((target, text))

    def _safe_clear(self, target: str):
        """线程安全的清空日志"""
        with self._msg_lock:
            self._msg_buffer.append((target, '__CLEAR__'))

    def closeEvent(self, event):
        """关闭窗口时停止后台调度线程"""
        try:
            if hasattr(self, 'scheduler'):
                self.scheduler.stop()
        except Exception:
            pass
        super().closeEvent(event)

    def _init_components(self):
        """初始化核心组件"""
        from database import Database
        from scanner_engine import NetworkScanner, VulnScanner
        from ai_analyzer import AIAnalyzer
        from threat_intel import ThreatIntelCollector, VulnMatcher
        from ai_security import AISecurityAnalyzer
        from ecc_security import ECCSecurityChecker

        self.db = Database()
        self.vuln_matcher = VulnMatcher(self.db)
        self.scanner = VulnScanner(self.db, self.vuln_matcher)
        self.scanner.network_scanner.set_progress_callback(self._on_scan_progress_msg)
        self.ai_analyzer = AIAnalyzer()
        self.ai_security = AISecurityAnalyzer(self.db)
        self.ecc_checker = ECCSecurityChecker(timeout=5)
        self.threat_intel = ThreatIntelCollector(self.db)
        self.threat_intel.set_progress_callback(self._on_intel_progress_msg)

        # 定时扫描调度器（后台线程 + 优先队列）
        from scheduler import ScanScheduler
        self.scheduler = ScanScheduler()
        self.scheduler.start()
        self._scheduled_scan_triggered.connect(self._on_scheduled_scan)

        self.current_scan_thread = None
        self.current_ai_scan_thread = None
        self.current_web_scan_thread = None
        self.web_scan_work_id = None
        self.current_audit_thread = None
        self.current_quality_audit_thread = None
        self.current_intel_thread = None
        self._scheduled_work_ids = {}
        self.last_scan_result = None
        self.last_web_scan_result = None
        self.last_audit_result = None
        self.last_quality_audit_result = None
        self.last_ai_analysis = None
        self.last_ecc_result = None
        self.audit_history = self.db.get_audit_history(50)
        self._discover_running = False
        self.discover_thread = None

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle('下一代智能漏洞扫描系统 Pro v1.0 - 山西有信网安科技有限公司')
        self.setGeometry(100, 50, 1500, 850)

        # 设置应用样式 - Windows 10/11 扁平风格
        self.setStyleSheet("""
            QMainWindow { background-color: #f3f3f3; }
            QGroupBox { font-weight: bold; font-size: 18px; border: 1px solid #d0d0d0; border-radius: 4px; margin-top: 12px; padding-top: 22px; background: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px; color: #333; }
            QPushButton { background-color: #e1e1e1; color: #333; border: 1px solid #c0c0c0; padding: 8px 20px; border-radius: 4px; font-size: 18px; font-weight: bold; }
            QPushButton:hover { background-color: #e5f0ff; border-color: #0078d4; color: #0078d4; }
            QPushButton:pressed { background-color: #cce5ff; }
            QPushButton:disabled { background-color: #f0f0f0; color: #a0a0a0; border-color: #e0e0e0; }
            QPushButton#stopBtn { background-color: #e1e1e1; color: #d13438; border: 1px solid #d13438; }
            QPushButton#stopBtn:hover { background-color: #fde7e9; border-color: #a4262c; color: #a4262c; }
            QPushButton#saveBtn { background-color: #e1e1e1; color: #107c10; border: 1px solid #107c10; }
            QPushButton#saveBtn:hover { background-color: #dff6dd; border-color: #0b5e0b; color: #0b5e0b; }
            QPushButton#aiBtn { background-color: #e1e1e1; color: #222; border: 1px solid #c0c0c0; }
            QPushButton#aiBtn:hover { background-color: #e5f0ff; border-color: #0078d4; color: #0078d4; }
            QPushButton#aiBtn:disabled { background-color: #f0f0f0; color: #a0a0a0; border-color: #e0e0e0; }
            QPushButton#eccBtn { background-color: #e1e1e1; color: #222; border: 1px solid #c0c0c0; }
            QPushButton#eccBtn:hover { background-color: #e5f0ff; border-color: #0078d4; color: #0078d4; }
            QPushButton#eccBtn:disabled { background-color: #f0f0f0; color: #a0a0a0; border-color: #e0e0e0; }
            QTableWidget { font-size: 16px; border: 1px solid #d0d0d0; border-radius: 4px; gridline-color: #e8e8e8; background: #ffffff; }
            QTableWidget::item { padding: 5px; }
            QHeaderView::section { background-color: #f0f0f0; color: #333; padding: 8px; border: none; border-bottom: 2px solid #d0d0d0; font-weight: bold; font-size: 16px; }
            QLineEdit, QTextEdit, QComboBox, QSpinBox { font-size: 16px; border: 1px solid #c0c0c0; border-radius: 4px; padding: 6px; background: #ffffff; }
            QLineEdit:focus { border-color: #0078d4; }
            QComboBox:focus { border-color: #0078d4; }
            QProgressBar { font-size: 16px; border: 1px solid #d0d0d0; border-radius: 4px; text-align: center; background: #ffffff; }
            QProgressBar::chunk { background-color: #0078d4; border-radius: 3px; }
            QTabWidget::pane { border: 1px solid #d0d0d0; border-radius: 0; background: #ffffff; }
            QTabBar::tab { font-size: 18px; font-weight: bold; background: #f3f3f3; color: #333; padding: 14px 30px; margin-right: 1px; border: 1px solid #d0d0d0; border-bottom: none; }
            QTabBar::tab:selected { background: #ffffff; color: #0078d4; border-bottom: 2px solid #0078d4; border-right: 4px solid #0078d4; font-weight: bold; }
            QTabBar::tab:hover { background: #e5f0ff; }
            QLabel { font-size: 16px; color: #333; }
            QPlainTextEdit { font-size: 16px; border: 1px solid #c0c0c0; border-radius: 4px; background: #ffffff; color: #333; }
            QTextEdit { background: #ffffff; }
            QSplitter::handle { background: #d0d0d0; }
            QStatusBar { background: #f0f0f0; border-top: 1px solid #d0d0d0; }
        """)

        self._create_menu_bar()
        self._create_toolbar()

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.setCentralWidget(self.tabs)

        # 刷新按钮放在标签行最右侧
        refresh_btn = QPushButton('🔄 刷新')
        refresh_btn.setMinimumHeight(36)
        refresh_btn.setStyleSheet('''
            QPushButton {
                padding: 8px 20px;
                font-size: 16px;
                font-weight: bold;
                background: #ffffff;
                color: #333;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #e5f0ff;
                border-color: #0078d4;
                color: #0078d4;
            }
        ''')
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_all)
        self.tabs.setCornerWidget(refresh_btn, Qt.TopRightCorner)

        self._create_dashboard_tab()
        self._create_asset_tab()
        self._create_scan_tab()
        self._create_web_scan_tab()
        self._create_vulndb_tab()
        self._create_db_maintain_tab()
        self._create_audit_tab()
        self._create_quality_tab()
        self._create_intel_tab()
        self._create_reports_tab()
        self._create_settings_tab()
        # 合规检查整合为单页（二级子页签：等保/关基/数据安全/176号），
        # 必须追加在最后 —— _on_tab_changed 按硬编码索引分发（0~10），前插会全部错位
        self._create_compliance_tab()

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_dashboard)
        self.update_timer.start(60000)

        # 每日自动更新CVE漏洞库 (24小时)
        self.cve_auto_update_timer = QTimer()
        self.cve_auto_update_timer.timeout.connect(self._auto_update_cve)
        self.cve_auto_update_timer.start(86400000)

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu('文件(&F)')
        save_action = file_menu.addAction('保存报告(&S)')
        save_action.triggered.connect(self._save_report)
        open_action = file_menu.addAction('打开报告(&O)')
        open_action.triggered.connect(self._open_report)
        file_menu.addSeparator()
        export_action = file_menu.addAction('导出报告(&E)')
        export_action.triggered.connect(self._export_report)
        file_menu.addSeparator()
        exit_action = file_menu.addAction('退出(&X)')
        exit_action.triggered.connect(self.close)

        scan_menu = menubar.addMenu('扫描(&S)')
        scan_menu.addAction('快速扫描').triggered.connect(lambda: self._start_scan('quick'))
        scan_menu.addAction('完整扫描').triggered.connect(lambda: self._start_scan('full'))

        tool_menu = menubar.addMenu('工具(&T)')
        tool_menu.addAction('更新CVE数据库').triggered.connect(self._update_cve_db)
        tool_menu.addAction('清空数据库').triggered.connect(self._clear_database)

        help_menu = menubar.addMenu('帮助(&H)')
        help_menu.addAction('关于(&A)').triggered.connect(self._show_about)
        help_menu.addSeparator()
        docs_menu = help_menu.addMenu('交付文档(&D)')
        for fname, label in DELIVERABLE_DOCS:
            docs_menu.addAction(label).triggered.connect(
                lambda checked, f=fname: self._open_deliverable_doc(f))

    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(72, 72))
        toolbar.setMinimumHeight(90)
        toolbar.setStyleSheet('QToolBar { spacing: 8px; padding: 4px 8px; }')
        self.addToolBar(toolbar)

        # 大标题 — 窗口居中
        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(left_spacer)

        big_title = QLabel('下一代智能漏洞扫描系统 <span style="color:#d13438;">Pro v1.0</span>')
        big_title.setTextFormat(Qt.RichText)
        big_title.setStyleSheet('font-weight: bold; font-size: 36px; color: #1a73e8;')
        big_title.setAlignment(Qt.AlignCenter)
        toolbar.addWidget(big_title)

        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(right_spacer)

        toolbar.addSeparator()

        # Logo + 版权信息 — 居右
        logo_path = _get_logo_path()
        if logo_path:
            logo_label = QLabel()
            pixmap = QPixmap(logo_path).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = _make_white_transparent(pixmap)
            logo_label.setPixmap(pixmap)
            logo_label.setStyleSheet('background: transparent;')
            toolbar.addWidget(logo_label)

        title_label = QLabel('  <span style=\"font-size:33px; vertical-align:top;\">&copy;</span>2026 山西有信网安科技有限公司  ')
        title_label.setTextFormat(Qt.RichText)
        title_label.setStyleSheet('font-weight: bold; font-size: 22px; color: #1a73e8;')
        toolbar.addWidget(title_label)

    def _create_header_widget(self, title: str, subtitle: str = '') -> QWidget:
        """创建标准页头"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 10)
        title_label = QLabel(f'<h2 style="color:#1a73e8;margin:0;">{title}</h2>')
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(f'<span style="color:#666;font-size:18px;">{subtitle}</span>')
            layout.addWidget(subtitle_label)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet('background-color: #e0e0e0; max-height: 1px;')
        layout.addWidget(line)
        return w

    # ============ 仪表盘 ============
    PIE_COLORS = ['#d32f2f', '#f57c00', '#fbc02d', '#388e3c', '#1976d2', '#881798', '#038387', '#0078d4']
    CHART_SIZE = (3.0, 2.4)
    CHART_DPI = 80

    def _make_chart_card(self, label, color):
        """创建带图表的卡片"""
        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{'
            f'background: white;'
            f'border: 1px solid #e0e0e0;'
            f'border-top: 4px solid {color};'
            f'border-radius: 4px;'
            f'padding: 8px;'
            f'}}'
        )
        card.setMinimumHeight(320)
        cl = QVBoxLayout(card)
        cl.setSpacing(2)
        cl.setContentsMargins(6, 4, 6, 4)

        # 标题 + 数字 同行
        header_row = QHBoxLayout()
        title_lbl = QLabel(label)
        title_lbl.setStyleSheet(f'color: {color}; font-size: 24px; font-weight: bold; border: none;')
        header_row.addWidget(title_lbl)
        header_row.addStretch()
        num_lbl = QLabel('0')
        num_lbl.setStyleSheet(f'color: {color}; font-size: 24px; font-weight: bold; border: none;')
        header_row.addWidget(num_lbl)
        cl.addLayout(header_row)

        fig = Figure(self.CHART_SIZE, dpi=self.CHART_DPI)
        fig.subplots_adjust(left=0.12, right=0.92, top=0.90, bottom=0.15)
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet('border: none; background: transparent;')
        cl.addWidget(canvas, 1)

        return card, fig, canvas, num_lbl

    def _draw_pie(self, fig, data, colors=None):
        """在 figure 上绘制饼状图（最大块突出）"""
        fig.clear()
        fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        ax = fig.add_subplot(111)
        labels = [k for k, v in data.items() if v > 0]
        values = [v for v in data.values() if v > 0]
        if not labels:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return
        cols = (colors or self.PIE_COLORS)[:len(labels)]
        # 最大的一块突出 0.08
        max_idx = values.index(max(values))
        explode = [0.08 if i == max_idx else 0 for i in range(len(values))]
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, colors=cols, autopct='%1.1f%%',
            explode=explode, textprops={'fontsize': 11}, pctdistance=0.6
        )
        for at in autotexts:
            at.set_fontsize(10)
        for t in texts:
            t.set_fontsize(11)
        ax.set_aspect('equal')

    def _draw_stacked_bar(self, fig, data):
        """在 figure 上绘制四段堆叠柱状图（横轴=工作类型，纵轴=四状态）"""
        fig.clear()
        fig.subplots_adjust(left=0.08, right=0.96, top=0.82, bottom=0.28)
        ax = fig.add_subplot(111)
        work_types = list(data.keys())
        statuses = ['已完成', '进行中', '计划中', '被终止']
        status_colors = {'已完成': '#388e3c', '进行中': '#f57c00', '计划中': '#1976d2', '被终止': '#d32f2f'}
        if not work_types:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return
        x = range(len(work_types))
        bottom = [0] * len(work_types)
        for status in statuses:
            vals = [data[wt].get(status, 0) for wt in work_types]
            ax.bar(x, vals, bottom=bottom, width=0.6, color=status_colors[status], label=status)
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax.set_xticks(list(x))
        ax.set_xticklabels(work_types, fontsize=8, rotation=30, ha='right')
        ax.legend(fontsize=8, loc='upper right')
        ax.tick_params(labelsize=9)
        ax.set_ylim(bottom=0)

    def _update_chart_card(self, key, fig, canvas, num_label, data, chart_type='pie', value=0, colors=None):
        """刷新卡片图表和数字"""
        num_label.setText(str(value))
        try:
            if chart_type == 'pie':
                self._draw_pie(fig, data, colors)
            elif chart_type == 'trend':
                self._draw_trend(fig, data)
            elif chart_type == 'stack':
                self._draw_stacked_bar(fig, data)
            elif chart_type == 'compliance':
                self._draw_compliance_trend(fig, data)
            canvas.draw_idle()
        except Exception:
            logger.exception(f'图表卡片 {key} 渲染失败')

    def _draw_trend(self, fig, data):
        """在 figure 上绘制柱状图+折线图（趋势），横轴=最近检查时间"""
        fig.clear()
        fig.subplots_adjust(left=0.10, right=0.95, top=0.90, bottom=0.22)
        ax = fig.add_subplot(111)
        if not data:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return
        labels = [d.get('date') or d.get('label', '') for d in data]
        sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        colors = [SEV_COLORS[s] for s in sevs]
        n = len(labels)
        x = range(n)
        width = 0.2
        for i, (sev, c) in enumerate(zip(sevs, colors)):
            vals = [d[sev] for d in data]
            ax.bar([xi + i * width for xi in x], vals, width, color=c, label=sev, alpha=0.8)
        # 折线: 总数
        totals = [sum(d[s] for s in sevs) for d in data]
        ax.plot(x, totals, 'k-', linewidth=1.2, marker='o', markersize=4, label='总数')
        # x轴: 最近十次检查时间，全部标注
        tick_idx = list(range(n))
        tick_pos = [xi + 1.5 * width for xi in tick_idx]
        tick_labels = [labels[i] for i in tick_idx]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_labels, fontsize=8, rotation=45, ha='right')
        ax.legend(fontsize=9, loc='upper left', ncol=5)
        ax.tick_params(labelsize=9)

    def _draw_compliance_trend(self, fig, data):
        """合规趋势图：柱状(符合/部分符合/不符合) + 折线(合规得分)，横轴=最近十次检查时间"""
        fig.clear()
        fig.subplots_adjust(left=0.12, right=0.86, top=0.85, bottom=0.28)
        ax = fig.add_subplot(111)
        if not data:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return
        labels = [d['date'] for d in data]
        statuses = ['符合', '部分符合', '不符合']
        status_colors = {'符合': '#388e3c', '部分符合': '#fbc02d', '不符合': '#d32f2f'}
        n = len(labels)
        x = range(n)
        width = 0.25
        for i, st in enumerate(statuses):
            vals = [d[st] for d in data]
            ax.bar([xi + i * width for xi in x], vals, width, color=status_colors[st], label=st, alpha=0.85)
        # 折线: 合规得分（右轴 0-100）
        scores = [d['score'] for d in data]
        ax2 = ax.twinx()
        ax2.plot(x, scores, 'k-', linewidth=1.4, marker='o', markersize=4, label='合规得分')
        ax2.set_ylim(0, 100)
        ax2.set_ylabel('得分', fontsize=8)
        ax2.tick_params(labelsize=8)
        # x轴: 最近十次检查时间，全部标注
        tick_pos = [xi + width for xi in x]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(labels, fontsize=8, rotation=45, ha='right')
        # 合并双轴图例
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, fontsize=8, loc='upper left')
        ax.tick_params(labelsize=8)

    def _create_dashboard_tab(self):
        """创建仪表盘 - 带图表卡片"""
        widget = QWidget()
        widget.setStyleSheet('background: #ffffff;')
        layout = QVBoxLayout(widget)

        layout.addWidget(self._create_header_widget('系统仪表盘'))

        # 统计卡片 + 图表 - 4列3行
        cards_layout = QGridLayout()
        cards_layout.setSpacing(8)
        self.stat_cards = {}
        self.dash_charts = {}

        card_config = [
            # 第一行
            ('total_assets', '资产总数', '#0078d4', 'pie'),
            ('total_cves', 'CVE漏洞库', '#ff8c00', 'pie'),
            ('critical_count', '漏洞等级', '#d13438', 'pie'),
            ('intel_today', '威胁情报', '#038387', 'pie'),
            # 第二行
            ('recent_tasks', '今日工作', '#0078d4', 'stack'),
            ('total_tasks', '扫描任务', '#107c10', 'pie'),
            ('total_vulns', '漏洞发现', '#d13438', 'trend'),
            ('audit_issues', '代码审计发现', '#881798', 'trend'),
            # 第三行：四标准合规检查趋势
            ('dengbao', '等保合规', '#1976d2', 'compliance'),
            ('cii', '关基合规', '#388e3c', 'compliance'),
            ('data_security', '数据安全合规', '#f57c00', 'compliance'),
            ('mps176', '176号合规', '#7b1fa2', 'compliance'),
        ]

        for i, (key, label, color, ctype) in enumerate(card_config):
            card, fig, canvas, num_label = self._make_chart_card(label, color)
            cards_layout.addWidget(card, i // 4, i % 4)
            self.stat_cards[key] = num_label
            self.dash_charts[key] = (fig, canvas, ctype)

        layout.addLayout(cards_layout)

        layout.addStretch()
        self.tabs.addTab(widget, '仪表盘')

    def _on_tab_changed(self, index):
        """切换标签页时自动刷新对应模块数据"""
        if index == 0:  # 仪表盘
            self._update_dashboard()
            self._update_status_bar()
        elif index == 1:  # 资产管理
            self._search_assets()
        elif index == 2:  # 漏洞扫描
            if not getattr(self, '_scan_loaded', False):
                self._scan_loaded = True
                self._load_last_scan_result()
        elif index == 3:  # Web扫描
            if not getattr(self, '_web_scan_loaded', False):
                self._web_scan_loaded = True
                self._load_last_web_scan_result()
        elif index == 4:  # 漏洞库
            if not getattr(self, '_vulndb_loaded', False):
                self._vulndb_loaded = True
                self._search_cve()
        elif index == 6:  # AI代码审计
            if not getattr(self, '_audit_loaded', False):
                self._audit_loaded = True
                self._load_last_audit_result()
        elif index == 9:  # 报告中心
            self._refresh_reports()

    def _refresh_all(self):
        """刷新仪表盘和报告数据"""
        self._update_dashboard()
        self._update_status_bar()
        if hasattr(self, 'report_table'):
            self._refresh_reports()
        self.status_bar.showMessage('数据已刷新 | 山西有信网安科技有限公司', 3000)

    def _update_dashboard(self):
        """更新仪表盘数据（卡片数字+图表）"""
        try:
            stats = self.db.get_statistics()

            # ---- 第一行 ----
            # 资产总数 (饼状图: 资产类型分布)
            asset_types = self.db.get_asset_type_counts()
            fig, canvas, ctype = self.dash_charts['total_assets']
            self._update_chart_card('total_assets', fig, canvas, self.stat_cards['total_assets'],
                                    asset_types, 'pie', stats['total_assets'])

            # CVE漏洞库 (饼状图: 严重度分布)
            cve_by_sev = stats.get('cve_by_severity', {})
            fig, canvas, ctype = self.dash_charts['total_cves']
            self._update_chart_card('total_cves', fig, canvas, self.stat_cards['total_cves'],
                                    cve_by_sev, 'pie', stats['total_cves'])

            # 漏洞等级 (饼状图: 严重/高危/中危/低危)
            sev_counts = self.db.get_scan_severity_counts()
            sev_labels = {'CRITICAL': '严重', 'HIGH': '高危', 'MEDIUM': '中危', 'LOW': '低危'}
            vuln_sev_data = {sev_labels.get(k, k): v for k, v in sev_counts.items() if v > 0}
            fig, canvas, ctype = self.dash_charts['critical_count']
            self._update_chart_card('critical_count', fig, canvas, self.stat_cards['critical_count'],
                                    vuln_sev_data, 'pie', stats['total_vulns'],
                                    colors=['#d32f2f', '#f57c00', '#fbc02d', '#388e3c'])

            # 威胁情报 (饼状图: 情报类型分布)
            intel_stats = self.db.get_intel_statistics()
            intel_labels = {'kev_count': 'KEV', 'epss_count': 'EPSS', 'actor_count': '威胁行为者',
                           'ioc_count': 'IOC', 'attack_pattern_count': '攻击模式'}
            intel_data = {intel_labels.get(k, k): v for k, v in intel_stats.items() if v > 0}
            intel_total = sum(intel_stats.values())
            fig, canvas, ctype = self.dash_charts['intel_today']
            self._update_chart_card('intel_today', fig, canvas, self.stat_cards['intel_today'],
                                    intel_data, 'pie', intel_total)

            # ---- 第二行 ----
            # 今日工作 (堆叠柱状图: 工作类型 × 状态)
            work_matrix = self.db.get_today_work_status_matrix()
            today_count = sum(sum(s.values()) for s in work_matrix.values())
            fig, canvas, ctype = self.dash_charts['recent_tasks']
            self._update_chart_card('recent_tasks', fig, canvas, self.stat_cards['recent_tasks'],
                                    work_matrix, 'stack', today_count)

            # 扫描任务 (饼状图: 任务类型分布)
            task_types = self.db.get_task_type_counts()
            task_type_total = sum(task_types.values())
            fig, canvas, ctype = self.dash_charts['total_tasks']
            self._update_chart_card('total_tasks', fig, canvas, self.stat_cards['total_tasks'],
                                    task_types, 'pie', task_type_total,
                                    colors=['#d32f2f', '#0078d4', '#881798', '#ff8c00', '#038387'])

            # 漏洞发现 (柱状+折线: 最近十次扫描)
            vuln_trend = self.db.get_vuln_by_task(10)
            fig, canvas, ctype = self.dash_charts['total_vulns']
            self._update_chart_card('total_vulns', fig, canvas, self.stat_cards['total_vulns'],
                                    vuln_trend, 'trend', stats['total_vulns'])

            # 代码审计发现 (柱状+折线: 最近十次审计)
            audit_trend = self.db.get_audit_by_task(10)
            total_issues = sum(a.get('total_vulnerabilities', 0) for a in self.audit_history)
            fig, canvas, ctype = self.dash_charts['audit_issues']
            self._update_chart_card('audit_issues', fig, canvas, self.stat_cards['audit_issues'],
                                    audit_trend if audit_trend else vuln_trend, 'trend', total_issues)

            # ---- 第三行: 四标准合规检查趋势 ----
            for std in ('dengbao', 'cii', 'data_security', 'mps176'):
                self._update_compliance_chart(std)

        except Exception as e:
            logger.error(f"更新仪表盘失败: {e}")

    def _update_compliance_chart(self, standard):
        """更新单个合规标准的趋势图（最近十次检查）"""
        try:
            history = self.db.get_compliance_history(standard, 10)
            trend = []
            for h in reversed(history):
                trend.append({
                    'date': (h.get('generated_at') or '')[:10],
                    '符合': h.get('pass_count', 0) or 0,
                    '部分符合': h.get('partial_count', 0) or 0,
                    '不符合': h.get('fail_count', 0) or 0,
                    'score': h.get('score') or 0,
                })
            latest_score = trend[-1]['score'] if trend else 0
            fig, canvas, ctype = self.dash_charts[standard]
            self._update_chart_card(standard, fig, canvas, self.stat_cards[standard],
                                    trend, 'compliance', latest_score)
        except Exception as e:
            logger.error(f"合规图表 {standard} 更新失败: {e}")

    # ============ 资产管理 ============
    def _create_asset_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('资产管理', '管理网络资产信息'))

        # 工具栏
        toolbar = QHBoxLayout()
        self.asset_search = QLineEdit()
        self.asset_search.setPlaceholderText('搜索资产 (名称/IP)...')
        self.asset_search.setMaximumWidth(300)
        toolbar.addWidget(self.asset_search)
        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self._search_assets)
        toolbar.addWidget(search_btn)

        self.asset_type_filter = QComboBox()
        self.asset_type_filter.addItems(['全部类型', 'SERVER', 'DATABASE', 'WEB_APP', 'NETWORK_DEVICE', 'IOT_DEVICE'])
        toolbar.addWidget(QLabel('类型:'))
        toolbar.addWidget(self.asset_type_filter)

        add_btn = QPushButton('+ 添加资产')
        add_btn.clicked.connect(self._add_asset_dialog)
        toolbar.addWidget(add_btn)
        import_btn = QPushButton('📥 批量导入')
        import_btn.clicked.connect(self._import_assets_dialog)
        toolbar.addWidget(import_btn)
        self.discover_btn = QPushButton('自动发现资产')
        self.discover_btn.setObjectName('saveBtn')
        self.discover_btn.clicked.connect(self._auto_discover_assets)
        toolbar.addWidget(self.discover_btn)

        self.discover_stop_btn = QPushButton('停止扫描资产')
        self.discover_stop_btn.setObjectName('stopBtn')
        self.discover_stop_btn.clicked.connect(self._stop_discover_assets)
        self.discover_stop_btn.setEnabled(False)
        toolbar.addWidget(self.discover_stop_btn)

        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self._search_assets)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(16)
        self.asset_table.setHorizontalHeaderLabels(['☐', 'ID', '名称', 'IP地址', 'MAC地址', '类型', '状态', '重要性', '负责人', '操作系统', '位置', '部门', '标签', '等保定级', '业务系统', '数据分类'])
        self.asset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.asset_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.asset_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.asset_table.itemClicked.connect(self._on_asset_clicked)
        self.asset_table.setMaximumHeight(600)
        # 点击复选框列标题 → 全选/取消全选
        self._asset_select_all = True  # 全选状态追踪
        self.asset_table.horizontalHeader().sectionClicked.connect(self._on_asset_header_clicked)
        # 右键菜单
        self.asset_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.asset_table.customContextMenuRequested.connect(self._on_asset_context_menu)
        # 双击编辑文本列，类型/重要性列用下拉菜单
        self.asset_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        from PyQt5.QtWidgets import QStyledItemDelegate
        class ComboDelegate(QStyledItemDelegate):
            def __init__(self, items, parent=None):
                super().__init__(parent)
                self.items = items
            def createEditor(self, parent, option, index):
                combo = QComboBox(parent)
                combo.addItems(self.items)
                return combo
            def setEditorData(self, editor, index):
                val = index.data(Qt.DisplayRole) or ''
                idx = editor.findText(val)
                if idx >= 0:
                    editor.setCurrentIndex(idx)
            def setModelData(self, editor, model, index):
                model.setData(index, editor.currentText())
        self.asset_table.setItemDelegateForColumn(5, ComboDelegate(
            ['SERVER', 'PC', 'NETWORK_DEVICE', 'DATABASE', 'WEB_APP', 'IOT_DEVICE', 'OTHER'], self))
        self.asset_table.setItemDelegateForColumn(7, ComboDelegate(
            ['HIGH', 'MEDIUM', 'LOW'], self))
        self.asset_table.setItemDelegateForColumn(9, ComboDelegate(
            ['Windows', 'Linux', 'macOS', 'Android', 'HarmonyOS', 'iOS', 'FreeBSD', 'Unix', '其他'], self))
        layout.addWidget(self.asset_table)

        # 底部按钮行：全选 + 保存更改 + 删除选择
        btn_row = QHBoxLayout()
        self.asset_select_all_btn = QPushButton('☑ 全选')
        self.asset_select_all_btn.clicked.connect(self._toggle_asset_select_all)
        self.asset_select_all_btn.setStyleSheet('font-size: 16px; padding: 8px 16px;')
        btn_row.addWidget(self.asset_select_all_btn)
        save_btn = QPushButton('💾 保存更改')
        save_btn.setObjectName('saveBtn')
        save_btn.clicked.connect(self._save_asset_changes)
        save_btn.setStyleSheet('font-size: 16px; padding: 8px 20px;')
        btn_row.addWidget(save_btn)
        del_sel_btn = QPushButton('🗑 删除选择')
        del_sel_btn.setObjectName('stopBtn')
        del_sel_btn.clicked.connect(self._delete_selected_assets)
        del_sel_btn.setStyleSheet('font-size: 16px; padding: 8px 20px;')
        btn_row.addWidget(del_sel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 资产详情
        layout.addWidget(QLabel('<b style="color:#1a73e8; font-size:18px;">资产详情</b>'))
        self.asset_detail_text = QTextEdit()
        self.asset_detail_text.setReadOnly(True)
        self.asset_detail_text.setMaximumHeight(400)
        self.asset_detail_text.setStyleSheet('font-size: 18px; font-family: monospace;')
        self.asset_detail_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.asset_detail_text)

        self.tabs.addTab(widget, '资产管理')

    def _search_assets(self):
        filters = {}
        keyword = self.asset_search.text().strip()
        if keyword:
            filters['keyword'] = keyword
        asset_type = self.asset_type_filter.currentText()
        if asset_type != '全部类型':
            filters['type'] = asset_type

        assets = self.db.get_assets(filters)
        self.asset_table.setRowCount(0)
        for asset in assets:
            row = self.asset_table.rowCount()
            self.asset_table.insertRow(row)
            # Column 0: checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Unchecked)
            self.asset_table.setItem(row, 0, chk_item)
            # Columns 1-15: data（末三列为合规字段，供等保/关基/数据安全检查取作用域与条款集）
            for col, key in enumerate(['id', 'name', 'ip', 'mac', 'type', 'status', 'importance',
                                       'owner', 'os', 'location', 'department', 'tags',
                                       'dengbao_level', 'business_system', 'data_classification'], 1):
                val = asset.get(key, '')
                if key == 'importance' and not val:
                    val = 'MEDIUM'
                item = QTableWidgetItem(str(val if val else ''))
                self.asset_table.setItem(row, col, item)

    def _import_assets_dialog(self):
        """批量导入资产（CSV / Excel），复用 asset_importer 模块"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, '选择资产文件 (CSV/Excel)', PROJECT_DIR,
            '数据文件 (*.csv *.txt *.xlsx);;CSV 文件 (*.csv);;Excel 文件 (*.xlsx);;所有文件 (*)')
        if not filepath:
            return
        try:
            from asset_importer import parse_csv, parse_excel, import_assets
            ext = os.path.splitext(filepath)[1].lower()
            if ext in ('.xlsx', '.xlsm'):
                with open(filepath, 'rb') as f:
                    assets, errors = parse_excel(f.read())
            else:
                with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    assets, errors = parse_csv(f.read())
        except Exception as e:
            QMessageBox.critical(self, '错误', f'解析失败: {e}')
            return
        if not assets:
            QMessageBox.warning(self, '提示', '未解析到有效资产（需含 name 和 ip 列）')
            return
        stats = import_assets(self.db, assets)
        if stats.get('inserted', 0) > 0:
            self.db.log_work('资产管理')
        self._search_assets()
        err_text = '；'.join(f"第{e['line']}行: {e['error']}" for e in errors[:5]) if errors else '无'
        QMessageBox.information(
            self, '导入完成',
            f"新增 {stats['inserted']} 条，重复 {stats['duplicate']} 条，失败 {stats['failed']} 条\n"
            f"解析错误: {err_text}")

    def _on_asset_clicked(self, item):
        row = item.row()
        asset_id = self.asset_table.item(row, 1).text()
        asset = self.db.get_asset(int(asset_id))
        if asset:
            detail = f"""资产详情
名称: {asset.get('name', '')}
IP: {asset.get('ip', '')}
MAC: {asset.get('mac', 'N/A')}
类型: {asset.get('type', '')} | 状态: {asset.get('status', '')}
重要性: {asset.get('importance', '')}
操作系统: {asset.get('os', 'N/A')}
位置: {asset.get('location', 'N/A')}
负责人: {asset.get('owner', 'N/A')}
部门: {asset.get('department', 'N/A')}
标签: {asset.get('tags', 'N/A')}"""
            self.asset_detail_text.setText(detail)

    def _on_asset_header_clicked(self, col):
        """点击表头: 列0 → 全选/取消全选"""
        if col != 0:
            return
        self._asset_select_all = not self._asset_select_all
        state = Qt.Checked if self._asset_select_all else Qt.Unchecked
        for row in range(self.asset_table.rowCount()):
            chk = self.asset_table.item(row, 0)
            if chk:
                chk.setCheckState(state)
        # 更新按钮文字
        self._update_select_all_btn()

    def _toggle_asset_select_all(self):
        """全选按钮: 切换全选/取消全选"""
        self._asset_select_all = not self._asset_select_all
        state = Qt.Checked if self._asset_select_all else Qt.Unchecked
        for row in range(self.asset_table.rowCount()):
            chk = self.asset_table.item(row, 0)
            if chk:
                chk.setCheckState(state)
        self._update_select_all_btn()

    def _update_select_all_btn(self):
        """更新全选按钮文字"""
        btn = getattr(self, 'asset_select_all_btn', None)
        if btn:
            btn.setText('☐ 取消全选' if self._asset_select_all else '☑ 全选')

    def _save_asset_changes(self):
        """保存资产列表中的编辑更改"""
        col_keys = ['id', 'name', 'ip', 'mac', 'type', 'status', 'importance', 'owner', 'os', 'location', 'department', 'tags']
        count = 0
        errors = []
        for row in range(self.asset_table.rowCount()):
            asset_id = int(self.asset_table.item(row, 1).text())  # ID now at column 1
            data = {}
            for col, key in enumerate(col_keys[1:], 2):  # data starts at column 2
                item = self.asset_table.item(row, col)
                if item:
                    data[key] = item.text().strip()
            try:
                self.db.update_asset(asset_id, data)
                count += 1
            except Exception as e:
                name = data.get('name', asset_id)
                errors.append(f'{name}: {e}')
        msg = f'已保存 {count} 条资产更改'
        if errors:
            msg += f' | {len(errors)} 条失败'
            logger.warning(f'保存资产失败: {errors}')
        self.status_bar.showMessage(f'{msg} | 山西有信网安科技有限公司', 3000)

    def _on_asset_context_menu(self, pos):
        """资产列表右键菜单"""
        menu = QMenu(self)
        edit_action = menu.addAction('✏️ 修改')
        add_action = menu.addAction('➕ 新增')
        menu.addSeparator()
        save_action = menu.addAction('💾 保存更改')
        menu.addSeparator()
        del_action = menu.addAction('🗑 删除')

        action = menu.exec_(self.asset_table.viewport().mapToGlobal(pos))
        if action == edit_action:
            self._edit_asset_dialog()
        elif action == add_action:
            self._add_asset_dialog()
        elif action == save_action:
            self._save_asset_changes()
        elif action == del_action:
            self._delete_selected_assets()

    def _edit_asset_dialog(self):
        """右键修改: 弹出对话框编辑选中资产"""
        current_row = self.asset_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, '提示', '请先选中要修改的资产')
            return
        asset_id = int(self.asset_table.item(current_row, 1).text())
        asset = self.db.get_asset(asset_id)
        if not asset:
            QMessageBox.warning(self, '错误', f'资产 {asset_id} 不存在')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f'修改资产 - {asset.get("name", "")}')
        dlg.setMinimumWidth(450)
        layout = QFormLayout(dlg)

        name_edit = QLineEdit(asset.get('name', ''))
        layout.addRow('名称:', name_edit)
        ip_edit = QLineEdit(asset.get('ip', ''))
        layout.addRow('IP地址:', ip_edit)
        mac_edit = QLineEdit(asset.get('mac', ''))
        layout.addRow('MAC地址:', mac_edit)

        type_combo = QComboBox()
        type_combo.addItems(['SERVER', 'PC', 'NETWORK_DEVICE', 'DATABASE', 'WEB_APP', 'IOT_DEVICE', 'OTHER'])
        idx = type_combo.findText(asset.get('type', 'SERVER'))
        if idx >= 0: type_combo.setCurrentIndex(idx)
        layout.addRow('类型:', type_combo)

        os_edit = QLineEdit(asset.get('os', ''))
        layout.addRow('操作系统:', os_edit)

        importance_combo = QComboBox()
        importance_combo.addItems(['HIGH', 'MEDIUM', 'LOW'])
        idx = importance_combo.findText(asset.get('importance', 'MEDIUM'))
        if idx >= 0: importance_combo.setCurrentIndex(idx)
        layout.addRow('重要性:', importance_combo)

        owner_edit = QLineEdit(asset.get('owner', ''))
        layout.addRow('负责人:', owner_edit)
        location_edit = QLineEdit(asset.get('location', ''))
        layout.addRow('位置:', location_edit)
        dept_edit = QLineEdit(asset.get('department', ''))
        layout.addRow('部门:', dept_edit)
        tags_edit = QLineEdit(asset.get('tags', ''))
        layout.addRow('标签:', tags_edit)

        # 合规字段：等保定级决定条款集，业务系统是问卷答案的作用域键
        dengbao_combo = QComboBox()
        dengbao_combo.addItems(COMPLIANCE_LEVEL_OPTIONS)
        dengbao_combo.setCurrentText(asset.get('dengbao_level', '') or '')
        layout.addRow('等保定级:', dengbao_combo)

        system_edit = QLineEdit(asset.get('business_system', '') or '')
        system_edit.setPlaceholderText('该资产所属业务系统，如：OA系统')
        layout.addRow('业务系统:', system_edit)

        data_class_combo = QComboBox()
        data_class_combo.addItems(DATA_CLASSIFICATION_OPTIONS)
        data_class_combo.setCurrentText(asset.get('data_classification', '') or '')
        layout.addRow('数据分类:', data_class_combo)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('保存')
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

        if dlg.exec_() != QDialog.Accepted:
            return
        data = {
            'name': name_edit.text().strip(),
            'ip': ip_edit.text().strip(),
            'mac': mac_edit.text().strip(),
            'type': type_combo.currentText(),
            'os': os_edit.text().strip(),
            'importance': importance_combo.currentText(),
            'owner': owner_edit.text().strip(),
            'location': location_edit.text().strip(),
            'department': dept_edit.text().strip(),
            'tags': tags_edit.text().strip(),
            'dengbao_level': dengbao_combo.currentText(),
            'business_system': system_edit.text().strip(),
            'data_classification': data_class_combo.currentText(),
        }
        if not data['name'] or not data['ip']:
            QMessageBox.warning(self, '错误', '名称和IP地址不能为空')
            return
        try:
            self.db.update_asset(asset_id, data)
            self._search_assets()
            self.status_bar.showMessage(f'资产 {data["name"]} 已更新 | 山西有信网安科技有限公司', 3000)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'更新失败: {e}')

    def _delete_selected_assets(self):
        """删除选中的资产（支持多选复选框删除）"""
        selected = []
        for row in range(self.asset_table.rowCount()):
            chk_item = self.asset_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                asset_id = self.asset_table.item(row, 1).text()
                name = self.asset_table.item(row, 2).text()
                selected.append((int(asset_id), name))
        if not selected:
            # Fallback: 如果有当前选中行但没勾选复选框，用当前行
            current = self.asset_table.currentRow()
            if current >= 0:
                asset_id = int(self.asset_table.item(current, 1).text())
                name = self.asset_table.item(current, 2).text()
                selected = [(asset_id, name)]
        if not selected:
            QMessageBox.warning(self, '提示', '请先勾选或选中要删除的资产')
            return

        names = ', '.join(n for _, n in selected[:5])
        if len(selected) > 5:
            names += f' ... 等{len(selected)}条'
        reply = QMessageBox.question(self, '确认删除',
            f'确定要删除以下资产吗？\n\n{names}\n\n此操作不可撤销！',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        deleted = 0
        for asset_id, name in selected:
            try:
                self.db.delete_asset(asset_id)
                deleted += 1
            except Exception as e:
                logger.error(f'删除资产 {name} 失败: {e}')
        self._search_assets()
        self.status_bar.showMessage(f'已删除 {deleted} 条资产 | 山西有信网安科技有限公司', 3000)

    def _add_asset_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('添加资产')
        dlg.setMinimumWidth(400)
        layout = QFormLayout(dlg)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText('输入资产名称...')
        layout.addRow('名称:', name_edit)

        ip_edit = QLineEdit()
        ip_edit.setPlaceholderText('输入IP地址...')
        layout.addRow('IP地址:', ip_edit)

        type_combo = QComboBox()
        type_combo.addItems(['SERVER', 'PC', 'NETWORK_DEVICE', 'DATABASE', 'WEB_APP', 'IOT_DEVICE', 'OTHER'])
        layout.addRow('类型:', type_combo)

        importance_combo = QComboBox()
        importance_combo.addItems(['HIGH', 'MEDIUM', 'LOW'])
        importance_combo.setCurrentIndex(1)  # 默认 MEDIUM
        layout.addRow('重要性:', importance_combo)

        # 合规字段：等保定级决定条款集，业务系统是问卷答案的作用域键
        dengbao_combo = QComboBox()
        dengbao_combo.addItems(COMPLIANCE_LEVEL_OPTIONS)
        layout.addRow('等保定级:', dengbao_combo)

        system_edit = QLineEdit()
        system_edit.setPlaceholderText('该资产所属业务系统，如：OA系统')
        layout.addRow('业务系统:', system_edit)

        data_class_combo = QComboBox()
        data_class_combo.addItems(DATA_CLASSIFICATION_OPTIONS)
        layout.addRow('数据分类:', data_class_combo)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('确定')
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

        if dlg.exec_() != QDialog.Accepted:
            return
        name = name_edit.text().strip()
        ip = ip_edit.text().strip()
        if not name or not ip:
            QMessageBox.warning(self, '警告', '名称和IP地址不能为空')
            return
        result = self.db.add_asset({
            'name': name, 'ip': ip,
            'type': type_combo.currentText(),
            'importance': importance_combo.currentText(),
            'dengbao_level': dengbao_combo.currentText(),
            'business_system': system_edit.text().strip(),
            'data_classification': data_class_combo.currentText(),
        })
        if result > 0:
            self.db.log_work('资产管理')
        self._search_assets()

    def _stop_discover_assets(self):
        """停止资产发现扫描"""
        self._discover_running = False
        if hasattr(self, 'discover_thread') and self.discover_thread:
            self.discover_thread.stop()
            self.discover_thread.requestInterruption()
            if not self.discover_thread.wait(3000):
                self.discover_thread.terminate()
                self.discover_thread.wait(1000)
            self.discover_thread = None
        self.discover_stop_btn.setEnabled(False)
        self.discover_btn.setText('自动发现资产')
        self.discover_btn.setEnabled(True)
        self.asset_detail_text.clear()
        self.status_bar.showMessage('资产发现已停止 | 山西有信网安科技有限公司')

    def _on_discover_progress(self, msg):
        """资产发现进度"""
        if '发现主机' in msg:
            current = self.asset_detail_text.toPlainText()
            self.asset_detail_text.setText(f'{current}\n{msg}')
        else:
            self.asset_detail_text.setText(msg)

    def _on_discover_finished(self, discovered):
        """资产发现完成"""
        self._discover_running = False
        self.discover_btn.setText('自动发现资产')
        self.discover_btn.setEnabled(True)
        self.discover_stop_btn.setEnabled(False)
        self.discover_thread = None

        if discovered:
            # 去重：获取已有资产的IP集合
            existing = self.db.get_assets()
            existing_ips = set(a.get('ip', '') for a in existing)
            new_hosts = [h for h in discovered if h not in existing_ips]
            skipped = len(discovered) - len(new_hosts)

            count = 0
            for host in new_hosts:
                result = self.db.add_asset({'name': host, 'ip': host, 'type': 'SERVER', 'status': 'ACTIVE'})
                if result > 0:
                    count += 1
            if count > 0:
                self.db.log_work('资产管理')
            self._search_assets()

            # 在资产详情框显示汇总结果
            summary = f'共发现 {len(discovered)} 个IP，已存在 {skipped} 个IP，新增加 {count} 个IP'
            self.asset_detail_text.setText(summary)

            msg = f'扫描完成！\n发现 {len(discovered)} 台主机'
            if skipped > 0:
                msg += f'\n跳过 {skipped} 个已存在资产'
            if count > 0:
                msg += f'\n新增 {count} 个资产'
            elif skipped == len(discovered):
                msg += '\n所有主机已存在，未新增资产'
            QMessageBox.information(self, '发现完成', msg)
        else:
            self.asset_detail_text.setText('未发现存活主机')
            QMessageBox.information(self, '发现完成', '未发现存活主机')
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')

    def _on_discover_error(self, error):
        """资产发现出错"""
        self._discover_running = False
        self.asset_detail_text.clear()
        self.discover_btn.setText('自动发现资产')
        self.discover_btn.setEnabled(True)
        self.discover_stop_btn.setEnabled(False)
        self.discover_thread = None
        QMessageBox.critical(self, '错误', f'资产发现失败: {error}')
        self.status_bar.showMessage('就绪 | 山西有信网安科技有限公司')

    def _auto_discover_assets(self):
        """自动发现网络资产"""
        from PyQt5.QtWidgets import QInputDialog

        ip_range, ok = QInputDialog.getText(self, '自动发现资产',
            '请输入IP地址范围:\n(如 192.168.1.1-254 或 192.168.1.0/24)')
        if not ok or not ip_range.strip():
            return

        ip_range = ip_range.strip()
        self.status_bar.showMessage(f'正在扫描 {ip_range} ...')

        reply = QMessageBox.question(self, '确认扫描',
            f'将对 {ip_range} 进行主机发现扫描，\n发现的主机将自动添加到资产清单。\n\n是否继续？',
            QMessageBox.Yes | QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        try:
            self.discover_btn.setText('正在扫描在线资产......')
            self.discover_btn.setEnabled(False)
            self.discover_stop_btn.setEnabled(True)

            targets = self.scanner.network_scanner.parse_target(ip_range)
            if not targets:
                QMessageBox.warning(self, '警告', '无法解析IP地址范围')
                return

            self.status_bar.showMessage(f'正在发现资产: {ip_range} ({len(targets)} 个目标) ...')
            self.asset_detail_text.clear()

            self._discover_running = True
            self.discover_thread = AssetDiscoveryThread(self.scanner.network_scanner, ip_range)
            self.discover_thread.progress.connect(self._on_discover_progress)
            self.discover_thread.finished.connect(self._on_discover_finished)
            self.discover_thread.error.connect(self._on_discover_error)
            self.discover_thread.start()

        except Exception as e:
            QMessageBox.critical(self, '错误', f'资产发现失败: {str(e)}')
            self.discover_btn.setText('自动发现资产')
            self.discover_btn.setEnabled(True)
            self.discover_stop_btn.setEnabled(False)

    # ============ 漏洞扫描 ============
    def _create_scan_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('漏洞扫描', '执行网络漏洞扫描任务'))

        config_group = QGroupBox('扫描配置')
        config_layout = QFormLayout()

        target_layout = QHBoxLayout()
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText('输入IP/域名/CIDR网段 (如 192.168.1.1 或 192.168.1.0/24)')
        target_layout.addWidget(self.target_input)
        select_asset_btn = QPushButton('从资产选择')
        select_asset_btn.clicked.connect(self._select_target_from_assets)
        target_layout.addWidget(select_asset_btn)
        config_layout.addRow('扫描目标:', target_layout)

        port_layout = QHBoxLayout()
        self.port_input = QLineEdit('21-23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017,2181,9200')
        port_layout.addWidget(self.port_input)
        config_layout.addRow('端口范围:', port_layout)

        type_layout = QHBoxLayout()
        self.scan_type_combo = QComboBox()
        self.scan_type_combo.addItems(['quick', 'full', 'custom'])
        self.scan_type_combo.currentTextChanged.connect(self._on_scan_type_changed)
        type_layout.addWidget(self.scan_type_combo)
        type_layout.addWidget(QLabel('quick=常用端口 | full=0-65535 | custom=自定义端口'))
        config_layout.addRow('扫描类型:', type_layout)

        timeout_layout = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setValue(10)
        self.timeout_spin.setSuffix(' 秒')
        timeout_layout.addWidget(self.timeout_spin)
        config_layout.addRow('超时时间:', timeout_layout)

        # AI核验选项
        ai_layout = QHBoxLayout()
        self.scan_ai_checkbox = QCheckBox('启用AI核验 (Claude) — 智能消除误报漏洞')
        self.scan_ai_checkbox.setToolTip('扫描完成后使用AI批量核验漏洞，自动识别并过滤误报\n（版本不匹配/产品不相关/服务类型错误）')
        self.scan_ai_checkbox.setChecked(True)  # 默认启用，本机Claude Code加持
        self.scan_ai_checkbox.setStyleSheet('font-size: 16px; font-weight: bold; color: #1a237e;')
        ai_layout.addWidget(self.scan_ai_checkbox)
        self.scan_ai_status_label = QLabel('✅ AI能力由本机Claude Code加持，默认启用')
        self.scan_ai_status_label.setStyleSheet('font-size: 14px; color: #107c10;')
        ai_layout.addWidget(self.scan_ai_status_label)
        config_layout.addRow('AI增强:', ai_layout)

        # 渗透测试选项（弱口令爆破）
        pen_layout = QHBoxLayout()
        self.pen_test_checkbox = QCheckBox('渗透测试 (弱口令爆破) — 对开放服务尝试常见弱口令')
        self.pen_test_checkbox.setToolTip(
            '扫描完成后对 SSH/FTP/MySQL/Redis/MongoDB/HTTP Basic 等开放服务做弱口令爆破\n'
            '采用保守策略（连续失败即停，避免触发目标账户锁定）\n'
            '默认关闭，请确保已获得目标网络的授权后再启用')
        self.pen_test_checkbox.setChecked(False)
        pen_layout.addWidget(self.pen_test_checkbox)
        pen_layout.addStretch()
        config_layout.addRow('渗透测试:', pen_layout)

        # 0day漏洞专项扫描（最高优先级，重点提示）
        zero_day_layout = QHBoxLayout()
        self.zero_day_checkbox = QCheckBox('0day漏洞专项扫描 — 重点检测CISA KEV在野利用漏洞（最高优先级）')
        self.zero_day_checkbox.setToolTip(
            '对CISA已知被利用漏洞(KEV)目录做全量产品级交叉比对，重点提示正在被攻击者活跃利用的0day漏洞\n'
            '命中结果以深红底白字高亮显示，并提升至CRITICAL级别，请立即处置')
        self.zero_day_checkbox.setChecked(True)  # 0day是网络安全防护最重要的防护点，默认开启
        self.zero_day_checkbox.setStyleSheet('font-size: 16px; font-weight: bold; color: #b71c1c;')
        zero_day_layout.addWidget(self.zero_day_checkbox)
        zero_day_layout.addStretch()
        config_layout.addRow('0day专项:', zero_day_layout)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton('开始扫描')
        self.scan_btn.clicked.connect(lambda: self._start_scan(self.scan_type_combo.currentText()))
        btn_layout.addWidget(self.scan_btn)

        self.stop_btn = QPushButton('停止扫描')
        self.stop_btn.setObjectName('stopBtn')
        self.stop_btn.clicked.connect(self._stop_scan)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.ai_stop_btn = QPushButton('停止AI核验')
        self.ai_stop_btn.setObjectName('stopBtn')
        self.ai_stop_btn.clicked.connect(self._stop_ai_verify)
        self.ai_stop_btn.setEnabled(False)
        self.ai_stop_btn.setToolTip('停止正在进行的AI漏洞核验')
        btn_layout.addWidget(self.ai_stop_btn)

        self.save_report_btn = QPushButton('保存报告')
        self.save_report_btn.setObjectName('saveBtn')
        self.save_report_btn.clicked.connect(self._save_report)
        self.save_report_btn.setEnabled(False)
        btn_layout.addWidget(self.save_report_btn)

        self.open_report_btn = QPushButton('打开报告')
        self.open_report_btn.clicked.connect(self._open_report)
        self.open_report_btn.setEnabled(False)
        btn_layout.addWidget(self.open_report_btn)

        self.ai_report_btn = QPushButton('AI安全报告')
        self.ai_report_btn.setObjectName('aiBtn')
        self.ai_report_btn.clicked.connect(self._save_ai_report)
        self.ai_report_btn.setEnabled(False)
        self.ai_report_btn.setToolTip('Claude Code Security AI分析报告')
        btn_layout.addWidget(self.ai_report_btn)

        self.ecc_report_btn = QPushButton('ECC安全报告')
        self.ecc_report_btn.setObjectName('eccBtn')
        self.ecc_report_btn.clicked.connect(self._save_ecc_report)
        self.ecc_report_btn.setEnabled(False)
        self.ecc_report_btn.setToolTip('Claude Code ECC 加密安全检测报告')
        btn_layout.addWidget(self.ecc_report_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 定时扫描调度面板
        sched_group = QGroupBox('⏰ 定时扫描（后台调度）')
        sched_layout = QHBoxLayout()
        sched_layout.addWidget(QLabel('优先级:'))
        self.sched_priority_combo = QComboBox()
        self.sched_priority_combo.addItems(['critical', 'high', 'medium', 'low'])
        self.sched_priority_combo.setCurrentText('medium')
        sched_layout.addWidget(self.sched_priority_combo)
        sched_layout.addWidget(QLabel('延迟(分钟):'))
        self.sched_delay_spin = QSpinBox()
        self.sched_delay_spin.setRange(1, 1440)
        self.sched_delay_spin.setValue(5)
        sched_layout.addWidget(self.sched_delay_spin)
        add_sched_btn = QPushButton('添加定时任务')
        add_sched_btn.clicked.connect(self._add_scheduled_scan)
        sched_layout.addWidget(add_sched_btn)
        run_now_btn = QPushButton('立即执行')
        run_now_btn.clicked.connect(self._run_scheduled_now)
        sched_layout.addWidget(run_now_btn)
        cancel_btn = QPushButton('取消选中')
        cancel_btn.clicked.connect(self._cancel_scheduled)
        sched_layout.addWidget(cancel_btn)
        sched_layout.addStretch()
        sched_group.setLayout(sched_layout)
        layout.addWidget(sched_group)

        self.sched_table = QTableWidget()
        self.sched_table.setColumnCount(4)
        self.sched_table.setHorizontalHeaderLabels(['任务ID', '目标', '优先级', '计划时间'])
        self.sched_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sched_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sched_table.setMaximumHeight(150)
        layout.addWidget(self.sched_table)

        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        layout.addWidget(self.scan_progress)

        splitter = QSplitter(Qt.Vertical)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(10)
        self.result_table.setHorizontalHeaderLabels(['主机', '端口', '协议', '服务', '版本', 'CVE', '严重程度', 'CVSS', '描述', '蜜罐'])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        splitter.addWidget(self.result_table)

        self.scan_log = QPlainTextEdit()
        self.scan_log.setReadOnly(True)
        self.scan_log.setMaximumHeight(200)
        splitter.addWidget(self.scan_log)

        layout.addWidget(splitter)
        self.tabs.addTab(widget, '漏洞扫描')

    def _create_web_scan_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('Web扫描', '独立 Web 应用安全扫描（指纹/路径/目录/ZAP/主动检测 + AI误报核验）'))

        config_group = QGroupBox('Web 扫描配置')
        config_layout = QFormLayout()

        target_layout = QHBoxLayout()
        self.web_target_input = QLineEdit()
        self.web_target_input.setPlaceholderText('输入目标 URL (如 https://example.com 或 http://192.168.1.10)')
        target_layout.addWidget(self.web_target_input)
        config_layout.addRow('目标 URL:', target_layout)

        opt_layout = QHBoxLayout()
        self.web_dir_checkbox = QCheckBox('目录枚举')
        self.web_dir_checkbox.setChecked(True)
        self.web_zap_checkbox = QCheckBox('ZAP 被动扫描')
        self.web_zap_checkbox.setChecked(True)
        self.web_active_checkbox = QCheckBox('主动漏洞检测')
        self.web_active_checkbox.setChecked(True)
        self.web_ai_checkbox = QCheckBox('AI误报核验')
        self.web_ai_checkbox.setChecked(False)
        self.web_ai_checkbox.setToolTip('扫描完成后用 AI 核验 web_vuln 中高危发现，自动过滤误报')
        opt_layout.addWidget(self.web_dir_checkbox)
        opt_layout.addWidget(self.web_zap_checkbox)
        opt_layout.addWidget(self.web_active_checkbox)
        opt_layout.addWidget(self.web_ai_checkbox)
        opt_layout.addStretch()
        config_layout.addRow('检测项:', opt_layout)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        btn_layout = QHBoxLayout()
        self.web_scan_btn = QPushButton('开始Web扫描')
        self.web_scan_btn.clicked.connect(self._start_web_scan)
        btn_layout.addWidget(self.web_scan_btn)

        self.web_stop_btn = QPushButton('停止Web扫描')
        self.web_stop_btn.setObjectName('stopBtn')
        self.web_stop_btn.clicked.connect(self._stop_web_scan)
        self.web_stop_btn.setEnabled(False)
        btn_layout.addWidget(self.web_stop_btn)

        self.web_save_report_btn = QPushButton('保存报告')
        self.web_save_report_btn.setObjectName('saveBtn')
        self.web_save_report_btn.clicked.connect(self._save_web_scan_report)
        self.web_save_report_btn.setEnabled(False)
        btn_layout.addWidget(self.web_save_report_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.web_scan_progress = QProgressBar()
        self.web_scan_progress.setVisible(False)
        layout.addWidget(self.web_scan_progress)

        splitter = QSplitter(Qt.Vertical)

        self.web_result_table = QTableWidget()
        self.web_result_table.setColumnCount(6)
        self.web_result_table.setHorizontalHeaderLabels(['类别', '标题', '严重度', 'URL', 'AI判定', '证据'])
        self.web_result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        splitter.addWidget(self.web_result_table)

        self.web_scan_log = QPlainTextEdit()
        self.web_scan_log.setReadOnly(True)
        self.web_scan_log.setMaximumHeight(200)
        splitter.addWidget(self.web_scan_log)

        layout.addWidget(splitter)
        self.tabs.addTab(widget, 'Web扫描')

    def _start_web_scan(self):
        target = self.web_target_input.text().strip()
        if not target:
            QMessageBox.warning(self, '提示', '请输入目标 URL')
            return
        if not re.match(r'^https?://', target, re.IGNORECASE):
            QMessageBox.warning(self, '提示', 'URL 需以 http:// 或 https:// 开头')
            return
        if self.current_web_scan_thread and self.current_web_scan_thread.isRunning():
            return
        self._safe_clear('web_scan_log')
        self.web_result_table.setRowCount(0)
        self.web_scan_progress.setVisible(True)
        self.web_scan_progress.setRange(0, 0)
        self.web_scan_btn.setEnabled(False)
        self.web_stop_btn.setEnabled(True)
        self._safe_log('web_scan_log', f'开始 Web 扫描: {target}')
        thread = WebScanThread(
            target, self.db,
            self.web_dir_checkbox.isChecked(),
            self.web_zap_checkbox.isChecked(),
            self.web_active_checkbox.isChecked(),
            self.web_ai_checkbox.isChecked(),
        )
        self.current_web_scan_thread = thread
        try:
            self.web_scan_work_id = self.db.start_work('Web扫描')
        except Exception:
            self.web_scan_work_id = None
        thread.progress.connect(self._on_web_scan_progress)
        # 用捕获 thread 的 lambda 区分陈旧线程，防止已停止的旧线程覆盖新扫描状态
        thread.finished.connect(lambda result, t=thread: self._on_web_scan_finished(result, t))
        thread.error.connect(lambda msg, t=thread: self._on_web_scan_error(msg, t))
        thread.start()

    def _stop_web_scan(self):
        thread = self.current_web_scan_thread
        if thread and thread.isRunning():
            self._safe_log('web_scan_log', '正在停止 Web 扫描...')
            if hasattr(thread, 'stop'):
                thread.stop()
            else:
                thread.requestInterruption()
            try:
                self.db.finish_work(self.web_scan_work_id, '被终止')
            except Exception:
                pass
            # 立即隐藏进度条，不阻塞 GUI；旧线程随后自然结束，其结果由 lambda 守卫忽略
            self.web_scan_progress.setVisible(False)
            self.current_web_scan_thread = None
            self.web_stop_btn.setEnabled(False)
            self.web_scan_btn.setEnabled(True)
            self._safe_log('web_scan_log', 'Web 扫描停止请求已发出，正在收尾...')

    def _on_web_scan_progress(self, msg):
        self._safe_log('web_scan_log', msg)

    def _on_web_scan_finished(self, result, thread=None):
        if thread is not None and thread is not self.current_web_scan_thread:
            return  # 陈旧线程，忽略
        self.current_web_scan_thread = None
        self.web_scan_btn.setEnabled(True)
        self.web_stop_btn.setEnabled(False)
        self.web_scan_progress.setVisible(False)
        findings = result.get('findings', [])
        ai_stats = result.get('ai_stats', {})
        self._safe_log('web_scan_log', f'Web 扫描完成: 共 {len(findings)} 项发现')
        # 记录 Web 扫描工作完成（供仪表盘"今日工作"次数统计）
        try:
            self.db.finish_work(self.web_scan_work_id, '已完成')
        except Exception as e:
            logger.warning(f'记录 Web 扫描工作失败: {e}')
        if ai_stats:
            self._safe_log('web_scan_log',
                           f"AI核验: 确认 {ai_stats.get('confirmed', 0)}, 排除 {ai_stats.get('excluded', 0)}, "
                           f"误报率 {ai_stats.get('exclusion_rate', 0):.1%}")
        self._populate_web_result_table(findings)
        self.last_web_scan_result = result
        self.web_save_report_btn.setEnabled(True)
        # 自动保存扫描报告到报告中心
        self._auto_save_web_scan_report(result)

    def _on_web_scan_error(self, msg, thread=None):
        if thread is not None and thread is not self.current_web_scan_thread:
            return  # 陈旧线程，忽略
        self.current_web_scan_thread = None
        self.web_scan_btn.setEnabled(True)
        self.web_stop_btn.setEnabled(False)
        self.web_scan_progress.setVisible(False)
        try:
            self.db.finish_work(self.web_scan_work_id, '被终止')
        except Exception:
            pass
        self._safe_log('web_scan_log', msg)
        QMessageBox.critical(self, 'Web 扫描错误', msg)

    def _auto_save_web_scan_report(self, result):
        """Web 扫描完成后自动保存报告并登记到报告中心。"""
        try:
            from report_generator import generate_web_scan_report
            html_path = generate_web_scan_report(result, self._report_dir())
            title = f'Web扫描报告 - {result.get("target", "未知")}'
            summary = self._web_scan_report_summary(result)
            self.db.save_report(title, 'web_scan', 'html', summary, html_path)
            self._safe_log('web_scan_log', f'扫描报告已自动保存: {html_path}')
            return html_path
        except Exception as e:
            logger.warning(f'Web 扫描报告自动保存失败: {e}')
            self._safe_log('web_scan_log', f'扫描报告自动保存失败: {e}')
            return None

    def _save_web_scan_report(self):
        """手动保存 Web 扫描报告到指定路径。"""
        if not self.last_web_scan_result:
            QMessageBox.warning(self, '警告', '没有可保存的 Web 扫描结果，请先执行扫描')
            return
        default_path = os.path.join(self._report_dir(), f'web_scan_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')
        filepath, _ = QFileDialog.getSaveFileName(self, '保存Web扫描报告', default_path, 'HTML报告 (*.html)')
        if not filepath:
            return
        try:
            from report_generator import render_web_scan_html
            html_content = render_web_scan_html(self.last_web_scan_result)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            title = f'Web扫描报告 - {self.last_web_scan_result.get("target", "未知")}'
            summary = self._web_scan_report_summary(self.last_web_scan_result)
            self.db.save_report(title, 'web_scan', 'html', summary, filepath)
            QMessageBox.information(self, '成功', f'报告已保存至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    @staticmethod
    def _web_scan_report_summary(result):
        """生成 Web 扫描报告摘要（用于报告中心展示）。"""
        findings = result.get('findings', []) or []
        sev = {}
        for f in findings:
            s = str(f.get('severity', 'INFO')).upper()
            sev[s] = sev.get(s, 0) + 1
        parts = [f'{k}:{v}' for k, v in sorted(sev.items())]
        ai = result.get('ai_stats') or {}
        if ai:
            parts.append(f"AI排除{ai.get('excluded', 0)}项")
        return f'发现{len(findings)}项 ({", ".join(parts)})'

    def _populate_web_result_table(self, findings):
        self.web_result_table.setRowCount(len(findings))
        for row, f in enumerate(findings):
            sev = f.get('severity', 'INFO')
            if f.get('excluded_reason'):
                ai_judge = '误报(已排除)'
            elif f.get('ai_verified'):
                ai_judge = f"确认 {float(f.get('ai_confidence') or 0):.0%}"
            else:
                ai_judge = ''
            items = [
                f.get('category', ''), f.get('title', ''),
                sev, f.get('url', ''),
                ai_judge, f.get('evidence', '') or f.get('detail', ''),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                if sev in ('CRITICAL', 'HIGH'):
                    item.setForeground(QColor(SEV_COLORS.get(sev, '#d32f2f')))
                self.web_result_table.setItem(row, col, item)

    def _load_last_web_scan_result(self):
        try:
            rows = self.db.get_web_scan_results(limit=100)
            if not rows:
                return
            latest_target = rows[0].get('target')
            findings = [r for r in rows if r.get('target') == latest_target]
            self.web_target_input.setText(latest_target or '')
            self._populate_web_result_table(findings)
            self._safe_log('web_scan_log', f'已加载最近 Web 扫描结果: {latest_target} ({len(findings)} 项)')
        except Exception as e:
            logger.warning(f'加载 Web 扫描历史失败: {e}')

    def _select_target_from_assets(self):
        """从资产列表中选择扫描目标"""
        assets = self.db.get_assets()
        if not assets:
            QMessageBox.warning(self, '提示', '资产列表为空，请先在资产管理中添加资产')
            return

        dialog = QDialog(self)
        dialog.setWindowTitle('选择扫描目标')
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel('<b>从资产列表中选择扫描目标（可多选）：</b>'))

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['资产名称', 'IP地址', '类型'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        for asset in assets:
            row = table.rowCount()
            table.insertRow(row)
            item = QTableWidgetItem(asset.get('name', ''))
            item.setData(Qt.UserRole, asset)
            item.setCheckState(Qt.Unchecked)
            table.setItem(row, 0, item)
            table.setItem(row, 1, QTableWidgetItem(asset.get('ip', '')))
            table.setItem(row, 2, QTableWidgetItem(asset.get('type', '')))

        layout.addWidget(table)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('确定')
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec_() == QDialog.Accepted:
            selected = []
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.checkState() == Qt.Checked:
                    asset = item.data(Qt.UserRole)
                    selected.append(asset.get('ip', ''))
            if selected:
                self.target_input.setText(', '.join(selected))

    def _on_scan_progress_msg(self, msg):
        self._safe_log('scan_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _on_scan_type_changed(self, scan_type):
        """扫描类型切换 - 自定义模式强调端口输入"""
        if scan_type == 'custom':
            self.port_input.setStyleSheet('border: 2px solid #e53935; font-size: 16px;')
            self.port_input.setPlaceholderText('输入自定义端口范围 (如 80,443,8080 或 1-65535)')
        else:
            self.port_input.setStyleSheet('')
            if scan_type == 'quick':
                self.port_input.setText('21-23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017,2181,9200')
            elif scan_type == 'full':
                self.port_input.setText('0-65535')

    def _start_scan(self, scan_type='quick'):
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, '警告', '请输入扫描目标')
            return
        ports = self.port_input.text().strip() or None
        self._do_scan(target, ports, scan_type)

    def _do_scan(self, target, ports, scan_type):
        """实际执行扫描（手动扫描与定时调度共用，主线程调用）。返回是否已启动。"""
        if not target:
            return False
        if self.current_scan_thread and self.current_scan_thread.isRunning():
            self._safe_log('scan_log', '已有扫描任务进行中，跳过本次任务')
            return False

        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.save_report_btn.setEnabled(False)
        self.open_report_btn.setEnabled(False)
        self.scan_progress.setVisible(True)
        self.scan_progress.setValue(0)
        self._safe_clear('scan_log')
        self.result_table.setRowCount(0)

        timeout = self.timeout_spin.value()
        self.scanner.network_scanner.timeout = timeout

        task_id = self.db.create_task(target, scan_type, {'ports': ports})

        weak_pass = self.pen_test_checkbox.isChecked() if hasattr(self, 'pen_test_checkbox') else False
        zero_day_focus = self.zero_day_checkbox.isChecked() if hasattr(self, 'zero_day_checkbox') else False
        self.current_scan_thread = ScanThread(self.scanner, target, ports, scan_type,
                                              weak_pass, zero_day_focus)
        self.current_scan_thread.progress.connect(self._on_scan_progress)
        self.current_scan_thread.finished.connect(lambda r: self._on_scan_finished(r, task_id))
        self.current_scan_thread.error.connect(self._on_scan_error)
        self.current_scan_thread.start()
        self._safe_log('scan_log', f'开始扫描任务: {target}')
        return True

    def _scheduled_task_func(self, task):
        """调度器后台线程回调 → 发信号到主线程执行扫描"""
        self._scheduled_scan_triggered.emit(task)

    def _on_scheduled_scan(self, task):
        """主线程槽：执行定时扫描；与进行中扫描冲突则延后 60 秒重试"""
        # 定时任务已触发，移除"计划中"标记（实际执行状态由扫描任务自身跟踪）
        try:
            sid = self._scheduled_work_ids.pop(task.task_id, None)
            if sid:
                self.db.delete_work(sid)
        except Exception:
            pass
        started = self._do_scan(task.target, task.ports or '', task.scan_type)
        if not started:
            from scheduler import ScheduledTask
            retry = ScheduledTask(
                task_id=task.task_id,
                target=task.target,
                priority=task.priority,
                scan_type=task.scan_type,
                ports=task.ports,
                run_at=datetime.now() + timedelta(seconds=60),
                func=self._scheduled_task_func,
            )
            self.scheduler.add_task(retry)
            self._refresh_scheduled_queue()
            self._safe_log('scan_log', f'定时任务 {task.task_id} 与进行中扫描冲突，60 秒后重试')

    def _add_scheduled_scan(self):
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, '警告', '请输入扫描目标')
            return
        import uuid
        from scheduler import ScheduledTask
        delay_min = self.sched_delay_spin.value()
        task = ScheduledTask(
            task_id=uuid.uuid4().hex[:8],
            target=target,
            priority=self.sched_priority_combo.currentText(),
            scan_type=self.scan_type_combo.currentText(),
            ports=self.port_input.text().strip() or None,
            run_at=datetime.now() + timedelta(minutes=delay_min),
            func=self._scheduled_task_func,
        )
        self.scheduler.add_task(task)
        try:
            self._scheduled_work_ids[task.task_id] = self.db.log_work('漏洞扫描', '计划中')
        except Exception:
            pass
        self._refresh_scheduled_queue()
        self._safe_log('scan_log', f'已添加定时任务: {target} ({delay_min}分钟后, 优先级 {task.priority})')

    def _run_scheduled_now(self):
        task_id = self._selected_sched_task_id()
        if not task_id:
            QMessageBox.warning(self, '提示', '请先在定时任务列表中选择一行')
            return
        self.scheduler.run_once_now(task_id)

    def _cancel_scheduled(self):
        task_id = self._selected_sched_task_id()
        if not task_id:
            QMessageBox.warning(self, '提示', '请先在定时任务列表中选择一行')
            return
        if self.scheduler.cancel(task_id):
            self._refresh_scheduled_queue()
            try:
                sid = self._scheduled_work_ids.pop(task_id, None)
                if sid:
                    self.db.finish_work(sid, '被终止')
            except Exception:
                pass

    def _selected_sched_task_id(self):
        row = self.sched_table.currentRow()
        if row < 0:
            return None
        item = self.sched_table.item(row, 0)
        return item.text() if item else None

    def _refresh_scheduled_queue(self):
        self.sched_table.setRowCount(0)
        for t in self.scheduler.get_queue():
            row = self.sched_table.rowCount()
            self.sched_table.insertRow(row)
            self.sched_table.setItem(row, 0, QTableWidgetItem(t['task_id']))
            self.sched_table.setItem(row, 1, QTableWidgetItem(t['target']))
            self.sched_table.setItem(row, 2, QTableWidgetItem(t['priority']))
            self.sched_table.setItem(row, 3, QTableWidgetItem(t['run_at'] or ''))

    def _stop_scan(self):
        if self.current_scan_thread:
            self.scanner.network_scanner.cancel()
            self.current_scan_thread.requestInterruption()
            self.current_scan_thread.wait(5000)
            if self.current_scan_thread.isRunning():
                self.current_scan_thread.terminate()
                self.current_scan_thread.wait(1000)
            self.current_scan_thread = None
        # 同时停止AI核验线程
        self._stop_ai_verify()
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_report_btn.setEnabled(False)
        self.scan_progress.setVisible(False)
        self._safe_log('scan_log','扫描已停止')

    def _stop_ai_verify(self):
        """停止正在进行的AI核验（协作式取消，避免 terminate 闪退）"""
        # 关闭等待对话框
        if getattr(self, '_ai_wait_dlg', None):
            try:
                self._ai_wait_dlg.accept()
            except RuntimeError:
                pass
            self._ai_wait_dlg = None
        if self.current_ai_scan_thread and self.current_ai_scan_thread.isRunning():
            self._safe_log('scan_log', '正在停止AI核验...')
            # 置位停止事件 → AIClient 终止 claude 子进程 → 线程随即退出
            if hasattr(self.current_ai_scan_thread, 'stop'):
                self.current_ai_scan_thread.stop()
            else:
                self.current_ai_scan_thread.requestInterruption()
            self.current_ai_scan_thread.wait(8000)
            if self.current_ai_scan_thread.isRunning():
                # 极端兜底：不再 terminate，避免原生线程强杀导致闪退
                logger.warning('AI核验线程未在限时内退出，已脱离引用')
            self.current_ai_scan_thread = None
            self.ai_stop_btn.setEnabled(False)
            self.scan_ai_checkbox.setEnabled(True)
            self._safe_log('scan_log', 'AI核验已停止')

    def _load_last_scan_result(self):
        """加载最近一次扫描结果到界面（含AI增强核验报告）"""
        try:
            tasks = self.db.get_all_tasks(limit=1)
            if not tasks or len(tasks) == 0:
                return
            task = tasks[0]
            results = self.db.get_task_results(task['id'])
            if not results or len(results) == 0:
                return

            self._safe_log('scan_log',
                f'已加载历史扫描记录 | 目标: {task.get("target", "N/A")} | '
                f'时间: {task.get("created_at", "")} | '
                f'发现: {len(results)} 个项目')

            self.result_table.setRowCount(0)
            for vuln in results:
                row = self.result_table.rowCount()
                self.result_table.insertRow(row)
                self.result_table.setItem(row, 0, QTableWidgetItem(str(vuln.get('host', ''))))
                self.result_table.setItem(row, 1, QTableWidgetItem(str(vuln.get('port', ''))))
                self.result_table.setItem(row, 2, QTableWidgetItem(str(vuln.get('protocol', 'tcp'))))
                self.result_table.setItem(row, 3, QTableWidgetItem(str(vuln.get('service', ''))))
                self.result_table.setItem(row, 4, QTableWidgetItem(str(vuln.get('version', ''))))
                self.result_table.setItem(row, 5, QTableWidgetItem(str(vuln.get('cve_id', 'N/A'))))
                self.result_table.setItem(row, 6, QTableWidgetItem(str(vuln.get('severity', 'INFO'))))

                severity = str(vuln.get('severity', 'INFO'))
                if severity in ['CRITICAL', 'HIGH']:
                    for c in range(9):
                        item = self.result_table.item(row, c)
                        if item:
                            item.setBackground(QColor(255, 210, 210))
                elif severity == 'MEDIUM':
                    for c in range(9):
                        item = self.result_table.item(row, c)
                        if item:
                            item.setBackground(QColor(255, 255, 210))

                cvss = vuln.get('cvss_score', '')
                self.result_table.setItem(row, 7, QTableWidgetItem(str(cvss) if cvss else ''))
                self.result_table.setItem(row, 8, QTableWidgetItem(
                    str(vuln.get('description', ''))[:80] if vuln.get('description') else ''))
                self.result_table.setItem(row, 9, _honeypot_badge_item(vuln))

                tip = _build_vuln_tooltip(vuln)
                if tip:
                    for c in range(self.result_table.columnCount()):
                        item = self.result_table.item(row, c)
                        if item:
                            item.setToolTip(tip)

            # 重建 last_scan_result 以便保存报告等功能可用
            self.last_scan_result = {
                'target': task.get('target', ''),
                'start_time': task.get('created_at', ''),
                'end_time': task.get('updated_at', ''),
                'duration': 0,
                'scan_result': {'hosts': []},
                'vulnerabilities': [
                    {k: v for k, v in dict(r).items()}
                    for r in results
                ],
                'summary': {
                    'total': len(results),
                    'by_severity': {},
                    'high_critical': sum(1 for r in results
                        if r.get('severity') in ('CRITICAL', 'HIGH')),
                }
            }
            for r in results:
                sev = str(r.get('severity', 'INFO'))
                self.last_scan_result['summary']['by_severity'][sev] = \
                    self.last_scan_result['summary']['by_severity'].get(sev, 0) + 1

            self.save_report_btn.setEnabled(True)
            self.open_report_btn.setEnabled(True)

            # 回放上次扫描的完整任务日志 + AI增强核验报告
            self._load_scan_log_file()
            self._display_cached_ai_report(task['id'])

        except Exception as e:
            pass  # 静默失败，不影响正常使用

    def _display_cached_ai_report(self, task_id):
        """从数据库加载并显示该任务的AI增强报告到scan_log（读取MD文件）"""
        try:
            reports = self.db.assets.conn.execute(
                "SELECT * FROM reports WHERE task_id=? AND type='scan' "
                "ORDER BY id DESC LIMIT 1", (task_id,)
            ).fetchall()
            if not reports:
                self._safe_log('scan_log', '  (未找到该任务的AI增强报告文件)')
                return
            report = dict(reports[0])
            filepath = report.get('file_path', '')

            # 优先读取MD文件
            md_path = filepath
            if filepath.endswith('.html'):
                md_path = filepath.replace('.html', '.md')
            if not os.path.exists(md_path):
                md_path = filepath

            if not md_path or not os.path.exists(md_path):
                self._safe_log('scan_log', self._format_scan_summary())
                return

            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            # 去Markdown标记，提取纯文本
            text = re.sub(r'#{1,6}\s+', '', md_content)
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            text = re.sub(r'`(.+?)`', r'\1', text)
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            text = re.sub(r'\|', ' ', text)
            text = re.sub(r'[-*+]{3,}', '', text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            summary = text[:3000] + ('...' if len(text) > 3000 else '')

            self._safe_log('scan_log', '')
            self._safe_log('scan_log', '─' * 50)
            self._safe_log('scan_log', '  上次扫描的AI增强核验报告')
            self._safe_log('scan_log', '─' * 50)
            for line in summary.split('\n')[:40]:
                line = line.strip()
                if line:
                    self._safe_log('scan_log', f'  {line}')
            self._safe_log('scan_log', '─' * 50)
            self._safe_log('scan_log', f'  完整报告: {md_path}')
        except Exception as e:
            logger.warning(f'加载AI报告失败: {e}')
            try:
                self._safe_log('scan_log', self._format_scan_summary())
            except:
                pass

    def _format_scan_summary(self):
        """从last_scan_result生成文本摘要"""
        if not self.last_scan_result:
            return '  (无可用扫描数据)'
        s = self.last_scan_result.get('summary', {})
        lines = [
            '',
            '─' * 50,
            '  历史扫描结果摘要',
            '─' * 50,
            f'  目标: {self.last_scan_result.get("target", "N/A")}',
            f'  时间: {self.last_scan_result.get("start_time", "N/A")}',
            f'  发现漏洞总数: {s.get("total", 0)}',
            f'  高危/严重: {s.get("high_critical", 0)}',
        ]
        by_sev = s.get('by_severity', {})
        if by_sev:
            for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
                if sev in by_sev:
                    lines.append(f'    {sev}: {by_sev[sev]}')
        lines.append('─' * 50)
        return '\n'.join(lines)

    def _on_scan_progress(self, msg):
        self._safe_log('scan_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')
        if '已扫描' in msg and '/' in msg:
            try:
                import re
                match = re.search(r'(\d+)/(\d+)', msg)
                if match:
                    current, total = int(match.group(1)), int(match.group(2))
                    if total > 0:
                        self.scan_progress.setValue(int(current / total * 90))
            except:
                pass

    def _on_scan_finished(self, result, task_id):
        self.scan_progress.setValue(100)
        self._safe_log('scan_log','扫描完成!')

        # VulnScanner已内置漏洞匹配，直接使用结果
        vulnerabilities = result.get('vulnerabilities', [])
        summary = result.get('summary', {})

        self.last_scan_result = result

        self.result_table.setRowCount(0)
        for vuln in vulnerabilities:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            self.result_table.setItem(row, 0, QTableWidgetItem(vuln.get('host', '')))
            self.result_table.setItem(row, 1, QTableWidgetItem(str(vuln.get('port', ''))))
            self.result_table.setItem(row, 2, QTableWidgetItem(vuln.get('protocol', 'tcp')))
            self.result_table.setItem(row, 3, QTableWidgetItem(vuln.get('service', '')))
            self.result_table.setItem(row, 4, QTableWidgetItem(vuln.get('version', '')))
            self.result_table.setItem(row, 5, QTableWidgetItem(vuln.get('cve_id', 'N/A')))
            self.result_table.setItem(row, 6, QTableWidgetItem(vuln.get('severity', 'INFO')))

            severity = vuln.get('severity', 'INFO')
            if vuln.get('is_0day'):
                # 0day/高危利用：深红底 + 白字，最高优先级重点提示
                sev_item = self.result_table.item(row, 6)
                if sev_item:
                    if vuln.get('known_ransomware'):
                        sev_item.setText('⛔ 勒索软件')
                    elif vuln.get('epss_high') and not vuln.get('kev'):
                        sev_item.setText('⚠ EPSS高危')
                    else:
                        sev_item.setText('⚠ 0DAY')
                for c in range(9):
                    item = self.result_table.item(row, c)
                    if item:
                        item.setBackground(QColor(183, 28, 28))
                        item.setForeground(QColor(255, 255, 255))
            elif severity in ['CRITICAL', 'HIGH']:
                for c in range(9):
                    item = self.result_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 210, 210))
            elif severity == 'MEDIUM':
                for c in range(9):
                    item = self.result_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 255, 210))

            cvss = vuln.get('cvss_score', '')
            self.result_table.setItem(row, 7, QTableWidgetItem(str(cvss) if cvss else ''))
            self.result_table.setItem(row, 8, QTableWidgetItem((vuln.get('description', '') or '')[:80]))
            self.result_table.setItem(row, 9, _honeypot_badge_item(vuln))

            tip = _build_vuln_tooltip(vuln)
            if tip:
                for c in range(self.result_table.columnCount()):
                    item = self.result_table.item(row, c)
                    if item:
                        item.setToolTip(tip)

        for vuln in vulnerabilities:
            self.db.add_scan_result(task_id, vuln)

        vuln_count = len(vulnerabilities)
        self.db.update_task_status(task_id, 'completed', vuln_count)

        high_crit = summary.get('high_critical', 0)
        total = summary.get('total', vuln_count)
        self._safe_log('scan_log',f'发现 {total} 个安全项目 (高危/严重: {high_crit})')

        dedup_stats = result.get('dedup_stats')
        if dedup_stats:
            self._safe_log('scan_log',
                f"相似度去重: 原始 {dedup_stats.get('before', 0)} → 唯一 {dedup_stats.get('unique', 0)} (合并 {dedup_stats.get('duplicates', 0)})")

        weak_count = result.get('weak_password_count', 0)
        if weak_count:
            self._safe_log('scan_log', f'渗透测试: 发现 {weak_count} 个弱口令')

        zero_day_count = result.get('zero_day_count', 0)
        if zero_day_count:
            self._safe_log('scan_log', f'⚠ 0day/活跃利用漏洞: {zero_day_count} 个 (最高优先级，请立即处置)')

        # AI安全分析 (Claude Code Security)
        try:
            self._safe_log('scan_log','正在执行AI安全分析 (Claude Code Security)...')
            self.last_ai_analysis = self.ai_security.analyze_scan_results(result)
            ai_risk = self.last_ai_analysis.get('risk_level', 'N/A')
            ai_score = self.last_ai_analysis.get('overall_risk_score', 0)
            self._safe_log('scan_log',f'AI分析完成: 风险等级 {ai_risk}, 综合评分 {ai_score}/100')
        except Exception as e:
            self._safe_log('scan_log',f'AI分析异常: {e}')

        # ECC安全检查 (Claude Code ECC)
        try:
            self._safe_log('scan_log','正在执行ECC加密安全检测 (Claude Code ECC)...')
            open_ports = []
            for host_info in result.get('scan_result', {}).get('hosts', []):
                for p in host_info.get('ports', []):
                    if p.get('state') == 'open':
                        open_ports.append(p)
            if open_ports:
                target = result.get('target', '')
                self.last_ecc_result = self.ecc_checker.run_full_check(target, open_ports)
                ecc_total = self.last_ecc_result.get('total_findings', 0)
                self._safe_log('scan_log',f'ECC检测完成: 发现 {ecc_total} 个加密安全问题')
        except Exception as e:
            self._safe_log('scan_log',f'ECC检测异常: {e}')

        # 自动保存扫描报告（HTML + MD）
        try:
            from report_generator import _generate_html_report, _generate_text_report
            report_dir = self._report_dir()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            target_name = re.sub(r'[^A-Za-z0-9._-]', '_', result.get('target', 'unknown'))
            # HTML
            html_content = _generate_html_report(result)
            html_path = os.path.join(report_dir, f'漏洞扫描报告_{target_name}_{ts}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.db.save_report(
                f'扫描报告 - {result.get("target", "")}',
                'scan', 'html', html_content[:500], html_path, task_id)
            self._safe_log('scan_log', f'扫描报告已自动保存至: {html_path}')
            # MD
            md_content = _generate_text_report(result)
            md_path = os.path.join(report_dir, f'漏洞扫描报告_{target_name}_{ts}.md')
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            self._safe_log('scan_log', f'MD报告已自动保存至: {md_path}')
        except Exception as e:
            self._safe_log('scan_log', f'扫描报告自动保存失败: {e}')

        # AI增强核验 — 默认使用本机Claude Code，无需API Key
        if self.scan_ai_checkbox.isChecked():
            api_key = self.db.get_setting('claude_api_key', '') or None
            self._safe_log('scan_log', '--- 启动AI核验 (本机Claude Code) ---')
            self._safe_log('scan_log', f'正在对 {len(vulnerabilities)} 个漏洞进行AI核验...')

            # 弹出提示窗口（含停止AI核验按钮）
            wait_dlg = QMessageBox(self)
            wait_dlg.setWindowTitle('AI核验')
            wait_dlg.setIcon(QMessageBox.Information)
            wait_dlg.setText('AI核验比较费时，请您耐心等待！')
            wait_dlg.setStandardButtons(QMessageBox.Close)
            stop_verify_btn = wait_dlg.addButton('停止AI核验', QMessageBox.DestructiveRole)
            stop_verify_btn.clicked.connect(self._stop_ai_verify)
            wait_dlg.setModal(False)
            wait_dlg.show()
            # 关闭后清理引用
            wait_dlg.finished.connect(lambda: setattr(self, '_ai_wait_dlg', None))
            self._ai_wait_dlg = wait_dlg

            self.scan_ai_checkbox.setEnabled(False)
            self.ai_stop_btn.setEnabled(True)
            self.current_ai_scan_thread = AIScanEnhanceThread(result, api_key)
            self.current_ai_scan_thread.progress.connect(self._on_ai_scan_progress)
            self.current_ai_scan_thread.finished.connect(self._on_ai_scan_finished)
            self.current_ai_scan_thread.error.connect(self._on_ai_scan_error)
            self.current_ai_scan_thread.start()
            return  # AI核验完成后才启用按钮和弹窗

        self._finalize_scan(ai_score, ai_risk, total, high_crit)

    def _finalize_scan(self, ai_score, ai_risk, total, high_crit):
        """完成扫描的通用处理"""
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.ai_stop_btn.setEnabled(False)
        self.save_report_btn.setEnabled(True)
        self.open_report_btn.setEnabled(True)
        self.ai_report_btn.setEnabled(self.last_ai_analysis is not None)
        self.ecc_report_btn.setEnabled(self.last_ecc_result is not None)
        self.scan_progress.setVisible(False)
        self.scan_ai_checkbox.setEnabled(True)

        # 保存扫描日志到文件（用于下次进入时回放）
        self._save_scan_log_file()

        QMessageBox.information(self, '扫描完成',
            f'扫描完成，发现 {total} 个安全项目\n'
            f'高危/严重: {high_crit} 个\n'
            f'AI风险评分: {ai_score}/100 ({ai_risk})')

    def _save_scan_log_file(self):
        """保存当前scan_log内容到文件"""
        try:
            log_text = self.scan_log.toPlainText()
            if not log_text.strip():
                return
            report_dir = self._report_dir()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            target = self.last_scan_result.get('target', 'unknown') if self.last_scan_result else 'unknown'
            target_name = re.sub(r'[^A-Za-z0-9._-]', '_', str(target))
            log_path = os.path.join(report_dir, f'scan_log_{target_name}_{ts}.txt')
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(log_text)
        except Exception as e:
            logger.warning(f'保存扫描日志失败: {e}')

    def _load_scan_log_file(self):
        """加载最近一次扫描日志文件并回放到scan_log"""
        try:
            report_dir = self._report_dir()
            log_files = sorted(
                [f for f in os.listdir(report_dir) if f.startswith('scan_log_') and f.endswith('.txt')],
                reverse=True
            )
            if not log_files:
                return
            log_path = os.path.join(report_dir, log_files[0])
            with open(log_path, 'r', encoding='utf-8') as f:
                log_text = f.read()
            if log_text.strip():
                self._safe_log('scan_log', '')
                self._safe_log('scan_log', '─' * 50)
                self._safe_log('scan_log', '  上次扫描任务详情')
                self._safe_log('scan_log', '─' * 50)
                for line in log_text.split('\n'):
                    self._safe_log('scan_log', line)
                self._safe_log('scan_log', '─' * 50)
        except Exception as e:
            logger.warning(f'加载扫描日志失败: {e}')

    def _on_ai_scan_progress(self, msg):
        self._safe_log('scan_log', msg)

    def _on_ai_scan_finished(self, result):
        """AI核验完成（增强版：支持预过滤+批量AI核验）"""
        # 关闭等待对话框
        if getattr(self, '_ai_wait_dlg', None):
            try:
                self._ai_wait_dlg.accept()
            except RuntimeError:
                pass
            self._ai_wait_dlg = None
        verified = result.get('verified_vulns', [])
        excluded = result.get('excluded_vulns', [])
        pre_filtered = result.get('pre_filtered', [])
        ai_analysis = result.get('ai_analysis', {})
        stats = result.get('stats', {})

        self._safe_log('scan_log', '══════ AI核验完成 ══════')
        self._safe_log('scan_log', f'✓ 确认漏洞: {len(verified)}个')
        self._safe_log('scan_log', f'✗ AI排除误报: {len(excluded) - len(pre_filtered)}个')
        if pre_filtered:
            self._safe_log('scan_log', f'⚡ 版本预过滤: {len(pre_filtered)}个（快速排除）')
        self._safe_log('scan_log', f'误报排除率: {stats.get("exclusion_rate", 0):.1%}')

        if excluded:
            self._safe_log('scan_log', '--- 已排除的误报详情 ---')
            for v in excluded[:15]:
                pre_tag = '[预过滤]' if v.get('pre_filtered') else '[AI判定]'
                self._safe_log('scan_log',
                    f'  ✗ {pre_tag} {v.get("cve_id", "N/A")} | {v.get("service")}:{v.get("port")} '
                    f'| {v.get("excluded_reason", "")[:80]}')

            if len(excluded) > 15:
                self._safe_log('scan_log', f'  ... 还有 {len(excluded) - 15} 个已排除')

        if ai_analysis:
            self._safe_log('scan_log', '--- AI风险分析 ---')
            self._safe_log('scan_log', f'风险评分: {ai_analysis.get("risk_score", "?")}/100')
            self._safe_log('scan_log', f'风险等级: {ai_analysis.get("risk_level", "?")}')
            if ai_analysis.get('executive_summary'):
                self._safe_log('scan_log', f'摘要: {ai_analysis["executive_summary"][:120]}')
            if ai_analysis.get('key_findings'):
                for f in ai_analysis['key_findings'][:5]:
                    self._safe_log('scan_log', f'  • {f}')
            self.last_ai_analysis = ai_analysis

        # 更新结果表格：标记AI核验状态
        if excluded:
            # 建立排除映射：CVE ID → 排除原因
            excluded_map = {}
            for v in excluded:
                cve_id = v.get('cve_id', '')
                if cve_id:
                    excluded_map[cve_id] = {
                        'reason': v.get('excluded_reason', 'AI判定为误报'),
                        'pre_filtered': v.get('pre_filtered', False),
                        'confidence': v.get('ai_confidence', 0),
                    }

            for row in range(self.result_table.rowCount()):
                cve_item = self.result_table.item(row, 5)  # CVE列 (index 5)
                if cve_item:
                    cve_text = cve_item.text()
                    if cve_text in excluded_map:
                        info = excluded_map[cve_text]
                        pre_tag = '⚡预过滤' if info['pre_filtered'] else '🤖AI判定'
                        tooltip = f'{pre_tag}: {info["reason"]} (置信度: {info["confidence"]:.0%})'
                        for col in range(self.result_table.columnCount()):
                            item = self.result_table.item(row, col)
                            if item:
                                # 预过滤用浅灰，AI排除用中灰
                                if info['pre_filtered']:
                                    item.setBackground(QColor(230, 230, 230))
                                else:
                                    item.setBackground(QColor(200, 200, 200))
                                item.setToolTip(tooltip)

        # 对AI确认的漏洞，添加绿色标记
        for v in verified:
            if v.get('ai_verified') and v.get('ai_confidence', 0) >= 0.7:
                for row in range(self.result_table.rowCount()):
                    cve_item = self.result_table.item(row, 5)
                    if cve_item and cve_item.text() == v.get('cve_id', ''):
                        sev_item = self.result_table.item(row, 6)
                        if sev_item:
                            ai_risk = v.get('ai_assessed_risk', '')
                            if ai_risk:
                                sev_item.setToolTip(f'AI评估风险: {ai_risk} | 置信度: {v.get("ai_confidence", 0):.0%}')
                                if ai_risk != v.get('severity', ''):
                                    # AI重新评估了风险等级
                                    sev_item.setText(f'{v.get("severity", "")} → {ai_risk}')
                                    sev_item.setForeground(QColor(0, 100, 0))

        # 用核验后的结果更新；重跑富化以刷新 remediation 为 AI 来源
        try:
            from vuln_enrich import enrich_vulnerabilities
            verified = enrich_vulnerabilities(verified)
        except ImportError:
            pass
        self.last_scan_result['vulnerabilities'] = verified
        self.last_scan_result['ai_enhanced'] = True
        self.last_scan_result['ai_stats'] = stats
        self.last_scan_result['ai_excluded'] = excluded
        self.last_scan_result['ai_pre_filtered'] = pre_filtered

        # 同步更新 severity 分布和总数
        new_by_sev = {}
        for v in verified:
            # 优先使用AI评估的风险等级
            sev = v.get('ai_assessed_risk') or v.get('severity', 'INFO')
            new_by_sev[sev] = new_by_sev.get(sev, 0) + 1
        self.last_scan_result['summary']['by_severity'] = new_by_sev
        self.last_scan_result['summary']['total'] = len(verified)
        self.last_scan_result['summary']['high_critical'] = (
            new_by_sev.get('CRITICAL', 0) + new_by_sev.get('HIGH', 0)
        )
        if ai_analysis:
            self.last_scan_result['ai_analysis'] = ai_analysis

        # 重新生成AI增强报告（HTML + MD）
        try:
            from report_generator import _generate_html_report, _generate_text_report
            report_dir = self._report_dir()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            target = self.last_scan_result.get('target', 'unknown')
            target_name = re.sub(r'[^A-Za-z0-9._-]', '_', str(target))

            # HTML 报告
            html_content = _generate_html_report(self.last_scan_result)
            html_path = os.path.join(report_dir,
                f'AI漏洞扫描核验报告_{target_name}_{ts}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            # MD 报告
            md_content = _generate_text_report(self.last_scan_result)
            md_path = os.path.join(report_dir,
                f'AI漏洞扫描核验报告_{target_name}_{ts}.md')
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            self._safe_log('scan_log', f'AI增强报告已保存: {html_path}')
            self._safe_log('scan_log', f'AI增强报告(MD)已保存: {md_path}')

            # 注册到报告中心数据库
            self.db.save_report(
                f'AI漏洞扫描核验报告 - {target}',
                'scan', 'html', html_content[:500], html_path,
                getattr(self, 'current_task_id', None)
            )
        except Exception as e:
            self._safe_log('scan_log', f'报告生成失败: {e}')

        # 完成
        ai_score = ai_analysis.get('risk_score', 50)
        ai_risk = ai_analysis.get('risk_level', 'MEDIUM')
        self._finalize_scan(ai_score, ai_risk, len(verified), sum(
            1 for v in verified if (v.get('ai_assessed_risk') or v.get('severity')) in ('CRITICAL', 'HIGH')))

    def _on_ai_scan_error(self, error):
        # 关闭等待对话框
        if getattr(self, '_ai_wait_dlg', None):
            try:
                self._ai_wait_dlg.accept()
            except RuntimeError:
                pass
            self._ai_wait_dlg = None
        self._safe_log('scan_log', f'AI核验错误: {error}')
        self.scan_ai_checkbox.setEnabled(True)
        self.ai_stop_btn.setEnabled(False)
        # 错误时正常结束
        self._finalize_scan(50, 'UNKNOWN',
            self.last_scan_result.get('summary', {}).get('total', 0),
            self.last_scan_result.get('summary', {}).get('high_critical', 0))

    def _on_scan_error(self, error):
        self._safe_log('scan_log',f'错误: {error}')
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_progress.setVisible(False)
        QMessageBox.critical(self, '扫描错误', error)

    # ============ 漏洞库 ============
    def _create_vulndb_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('CVE漏洞库', '浏览和搜索CVE漏洞数据'))

        search_layout = QHBoxLayout()
        self.cve_search = QLineEdit()
        self.cve_search.setPlaceholderText('搜索CVE (如: apache, mysql, CVE-2024-...)')
        self.cve_search.setMaximumWidth(400)
        search_layout.addWidget(self.cve_search)

        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self._search_cve)
        search_layout.addWidget(search_btn)

        self.cve_severity_filter = QComboBox()
        self.cve_severity_filter.addItems(['全部', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'])
        search_layout.addWidget(QLabel('严重度:'))
        search_layout.addWidget(self.cve_severity_filter)

        search_layout.addStretch()

        update_layout = QHBoxLayout()
        update_layout.addWidget(QLabel('更新天数:'))
        self.cve_days_spin = QSpinBox()
        self.cve_days_spin.setRange(1, 90)
        self.cve_days_spin.setValue(7)
        self.cve_days_spin.setSuffix(' 天')
        update_layout.addWidget(self.cve_days_spin)

        self.cve_update_btn = QPushButton('更新漏洞库')
        self.cve_update_btn.setObjectName('saveBtn')
        self.cve_update_btn.clicked.connect(self._update_cve_db)
        update_layout.addWidget(self.cve_update_btn)

        self.cve_stop_btn = QPushButton('停止搜索')
        self.cve_stop_btn.setObjectName('stopBtn')
        self.cve_stop_btn.clicked.connect(self._stop_cve_update)
        self.cve_stop_btn.setEnabled(False)
        update_layout.addWidget(self.cve_stop_btn)

        update_layout.addStretch()
        layout.addLayout(search_layout)
        layout.addLayout(update_layout)

        # 更新进度条（不确定进度模式=转圈动画）
        self.cve_progress_bar = QProgressBar()
        self.cve_progress_bar.setRange(0, 0)  # 不确定模式
        self.cve_progress_bar.setMaximumHeight(6)
        self.cve_progress_bar.setVisible(False)
        layout.addWidget(self.cve_progress_bar)

        self.cve_table = QTableWidget()
        self.cve_table.setColumnCount(9)
        self.cve_table.setHorizontalHeaderLabels(['序号', 'CVE编号', '严重程度', 'CVSS', '描述', '发布日期', 'CWE', '补丁链接', '受影响产品'])
        self.cve_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cve_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cve_table.itemClicked.connect(self._on_cve_clicked)
        layout.addWidget(self.cve_table)

        # 分页控件
        page_layout = QHBoxLayout()
        page_layout.addStretch()

        self.cve_first_btn = QPushButton('首页')
        self.cve_first_btn.clicked.connect(self._cve_first_page)
        page_layout.addWidget(self.cve_first_btn)

        self.cve_prev_btn = QPushButton('上一页')
        self.cve_prev_btn.clicked.connect(self._cve_prev_page)
        page_layout.addWidget(self.cve_prev_btn)

        self.cve_page_label = QLabel('第 1 页')
        self.cve_page_label.setStyleSheet('font-size: 16px; padding: 0 10px;')
        page_layout.addWidget(self.cve_page_label)

        self.cve_next_btn = QPushButton('下一页')
        self.cve_next_btn.clicked.connect(self._cve_next_page)
        page_layout.addWidget(self.cve_next_btn)

        self.cve_last_btn = QPushButton('末页')
        self.cve_last_btn.clicked.connect(self._cve_last_page)
        page_layout.addWidget(self.cve_last_btn)

        self.cve_info_label = QLabel('每页显示 500 条漏洞信息')
        self.cve_info_label.setStyleSheet('font-size: 15px; color: #666; padding: 0 15px;')
        page_layout.addWidget(self.cve_info_label)

        page_layout.addStretch()
        layout.addLayout(page_layout)

        # 分页状态
        self.cve_page = 1
        self.cve_page_size = 500
        self.cve_keyword = ''
        self.cve_filter_severity = '全部'

        detail_group = QGroupBox('CVE详情')
        detail_layout = QVBoxLayout()
        self.cve_detail_text = QTextEdit()
        self.cve_detail_text.setReadOnly(True)
        self.cve_detail_text.setMinimumHeight(200)
        self.cve_detail_text.setStyleSheet('font-size: 18px; line-height: 1.5;')
        detail_layout.addWidget(self.cve_detail_text)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        # CVE更新进度日志
        self.cve_update_log = QPlainTextEdit()
        self.cve_update_log.setReadOnly(True)
        self.cve_update_log.setMaximumHeight(150)
        self.cve_update_log.setStyleSheet('font-size: 18px;')
        self.cve_update_log.setPlaceholderText('漏洞库更新进度将在此显示...')
        layout.addWidget(self.cve_update_log)

        self.tabs.addTab(widget, '漏洞库')

    def _search_cve(self):
        """搜索CVE（重置到第1页）"""
        self.cve_keyword = self.cve_search.text().strip()
        self.cve_filter_severity = self.cve_severity_filter.currentText()
        self.cve_page = 1
        self._load_cve_page()

    def _load_cve_page(self):
        """加载当前页的CVE数据"""
        min_cvss = 7.0 if self.cve_filter_severity != '全部' else 0
        offset = (self.cve_page - 1) * self.cve_page_size

        cves = self.db.search_cve(
            keyword=self.cve_keyword, min_cvss=min_cvss,
            limit=self.cve_page_size, offset=offset
        )
        total = self.db.count_cve(keyword=self.cve_keyword, min_cvss=min_cvss)

        self.cve_table.setRowCount(0)
        for cve in cves:
            row = self.cve_table.rowCount()
            self.cve_table.insertRow(row)
            self.cve_table.setItem(row, 0, QTableWidgetItem(str(offset + row + 1)))
            self.cve_table.setItem(row, 1, QTableWidgetItem(cve.get('cve_id', '')))
            sev = cve.get('severity', 'INFO')
            item = QTableWidgetItem(sev)
            if sev == 'CRITICAL':
                item.setBackground(QColor(255, 80, 80))
                item.setForeground(QColor(255, 255, 255))
            elif sev == 'HIGH':
                item.setBackground(QColor(255, 150, 50))
                item.setForeground(QColor(255, 255, 255))
            self.cve_table.setItem(row, 2, item)
            self.cve_table.setItem(row, 3, QTableWidgetItem(str(cve.get('cvss_score', ''))))
            self.cve_table.setItem(row, 4, QTableWidgetItem((cve.get('description', '') or '')[:100]))
            self.cve_table.setItem(row, 5, QTableWidgetItem(cve.get('published_date', '') or ''))
            self.cve_table.setItem(row, 6, QTableWidgetItem((cve.get('cwe', '') or '')[:20]))
            self.cve_table.setItem(row, 7, QTableWidgetItem((cve.get('patch_link', '') or '')[:50]))
            self.cve_table.setItem(row, 8, QTableWidgetItem((cve.get('affected_products', '') or '')[:80]))

        total_pages = max(1, (total + self.cve_page_size - 1) // self.cve_page_size)
        self.cve_page_label.setText(f'第 {self.cve_page} / {total_pages} 页')
        self.cve_info_label.setText(f'每页显示 {self.cve_page_size} 条漏洞信息（共 {total} 条）')
        self._update_page_buttons(total_pages)

    def _update_page_buttons(self, total_pages):
        """更新分页按钮状态"""
        self.cve_first_btn.setEnabled(self.cve_page > 1)
        self.cve_prev_btn.setEnabled(self.cve_page > 1)
        self.cve_next_btn.setEnabled(self.cve_page < total_pages)
        self.cve_last_btn.setEnabled(self.cve_page < total_pages)

    def _cve_first_page(self):
        if self.cve_page > 1:
            self.cve_page = 1
            self._load_cve_page()

    def _cve_prev_page(self):
        if self.cve_page > 1:
            self.cve_page -= 1
            self._load_cve_page()

    def _cve_next_page(self):
        self.cve_page += 1
        self._load_cve_page()

    def _cve_last_page(self):
        min_cvss = 7.0 if self.cve_filter_severity != '全部' else 0
        total = self.db.count_cve(keyword=self.cve_keyword, min_cvss=min_cvss)
        total_pages = max(1, (total + self.cve_page_size - 1) // self.cve_page_size)
        if self.cve_page < total_pages:
            self.cve_page = total_pages
            self._load_cve_page()

    def _on_cve_clicked(self, item):
        row = item.row()
        cve_id = self.cve_table.item(row, 1).text()
        cves = self.db.search_cve(keyword=cve_id, limit=1)
        if cves:
            cve = cves[0]
            products = cve.get('affected_products', '') or ''
            if isinstance(products, list):
                products = ', '.join(products)
            cwe = cve.get('cwe', '') or ''
            patch = cve.get('patch_link', '') or ''
            detail = f"""
CVE编号: {cve.get('cve_id', '')}
名称: {cve.get('name', '')}
严重程度: {cve.get('severity', 'INFO')} | CVSS分数: {cve.get('cvss_score', 'N/A')}
发布时间: {cve.get('published_date', 'N/A')}
更新时间: {cve.get('modified_date', 'N/A')}
CWE: {cwe}
补丁链接: {patch}
受影响产品: {products}

漏洞描述:
{cve.get('description', '暂无描述') or '暂无描述'}

AI分析:
{cve.get('ai_analysis', '暂无AI分析') or '暂无AI分析'}
"""
            self.cve_detail_text.setText(detail)

    # ============ 数据库维护 ============
    def _create_db_maintain_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('CVE数据库维护', '清除假数据、回填CWE/补丁链接、逐月补全遗漏漏洞'))

        # 状态概览
        status_layout = QHBoxLayout()
        self.db_status_label = QLabel('加载中...')
        self.db_status_label.setStyleSheet('font-size:18px; padding:8px; background:#e3f2fd; border-radius:6px;')
        status_layout.addWidget(self.db_status_label)
        refresh_status_btn = QPushButton('刷新状态')
        refresh_status_btn.clicked.connect(self._refresh_db_status)
        status_layout.addWidget(refresh_status_btn)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # 操作模式选择
        mode_group = QGroupBox('操作模式')
        mode_layout = QVBoxLayout()

        self.repair_mode = QComboBox()
        self.repair_mode.addItems([
            '预览 (不实际修改数据库)',
            '全部修复 (清除假CVE → 回填 → 逐月补全)',
            '仅清除假CVE',
            '仅回填CWE/补丁链接',
            '仅逐月补全遗漏',
        ])
        self.repair_mode.currentIndexChanged.connect(self._on_repair_mode_changed)
        self.repair_mode.setStyleSheet('font-size:20px; padding:6px;')
        mode_layout.addWidget(self.repair_mode)

        # 时间范围（仅补全模式需要）
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel('起始月份:'))
        self.repair_start = QComboBox()
        self.repair_start.setEditable(True)
        self.repair_start.setMinimumWidth(120)
        self.repair_start.addItems([f'{y}-{m:02d}' for y in range(2000, 2027) for m in range(1, 13)])
        self.repair_start.setCurrentText('2000-01')
        time_layout.addWidget(self.repair_start)

        time_layout.addWidget(QLabel('结束月份:'))
        self.repair_end = QComboBox()
        self.repair_end.setEditable(True)
        self.repair_end.setMinimumWidth(120)
        self.repair_end.addItems([f'{y}-{m:02d}' for y in range(2000, 2027) for m in range(1, 13)])
        self.repair_end.setCurrentText(datetime.now().strftime('%Y-%m'))
        time_layout.addWidget(self.repair_end)

        self.repair_dry_cb = QCheckBox('预览模式 (不实际写入)')
        self.repair_dry_cb.setChecked(False)
        time_layout.addWidget(self.repair_dry_cb)

        time_layout.addStretch()
        self.time_range_widget = QWidget()
        self.time_range_widget.setLayout(time_layout)
        self.time_range_widget.setVisible(False)
        mode_layout.addWidget(self.time_range_widget)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.repair_start_btn = QPushButton('开始执行')
        self.repair_start_btn.setObjectName('searchBtn')
        self.repair_start_btn.clicked.connect(self._start_db_repair)
        btn_layout.addWidget(self.repair_start_btn)

        self.repair_stop_btn = QPushButton('停止')
        self.repair_stop_btn.setObjectName('stopBtn')
        self.repair_stop_btn.clicked.connect(self._stop_db_repair)
        self.repair_stop_btn.setEnabled(False)
        btn_layout.addWidget(self.repair_stop_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 进度条
        self.repair_progress = QProgressBar()
        self.repair_progress.setVisible(False)
        layout.addWidget(self.repair_progress)

        # 日志
        self.repair_log = QPlainTextEdit()
        self.repair_log.setReadOnly(True)
        self.repair_log.setStyleSheet('font-size:16px;')
        self.repair_log.setPlaceholderText('操作日志将在此显示...')
        layout.addWidget(self.repair_log)

        self.tabs.addTab(widget, '数据库维护')

    def _on_repair_mode_changed(self, idx):
        """模式切换时显示/隐藏时间范围"""
        show_time = idx in (0, 1, 4)  # 预览/全部/仅补全 需要时间范围
        self.time_range_widget.setVisible(show_time)

    def _refresh_db_status(self):
        try:
            c = self.db.cve.conn.cursor()
            total = c.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
            fake = c.execute(
                "SELECT COUNT(*) FROM cve_database WHERE cve_id IN (?,?,?,?,?,?,?)",
                ('CVE-2026-0001','CVE-2026-0002','CVE-2026-1234','CVE-2026-5678','CVE-2026-9012','CVE-2026-3456','CVE-2026-7890')
            ).fetchone()[0]
            no_cwe = c.execute(
                "SELECT COUNT(*) FROM cve_database WHERE cwe IS NULL OR cwe=''"
            ).fetchone()[0]
            no_patch = c.execute(
                "SELECT COUNT(*) FROM cve_database WHERE patch_link IS NULL OR patch_link=''"
            ).fetchone()[0]
            self.db_status_label.setText(
                f'CVE总量: {total} | 疑似假CVE: {fake} | 缺CWE: {no_cwe} | 缺补丁链接: {no_patch}'
            )
        except Exception as e:
            self.db_status_label.setText(f'读取失败: {e}')

    def _start_db_repair(self):
        mode = self.repair_mode.currentIndex()
        ops = []
        if mode == 0:  # 预览
            ops = ['clean_fakes', 'backfill', 'fetch']
            dry = True
        elif mode == 1:  # 全部修复
            ops = ['clean_fakes', 'backfill', 'fetch']
            dry = self.repair_dry_cb.isChecked()
        elif mode == 2:  # 仅清除
            ops = ['clean_fakes']
            dry = self.repair_dry_cb.isChecked()
        elif mode == 3:  # 仅回填
            ops = ['backfill']
            dry = self.repair_dry_cb.isChecked()
        elif mode == 4:  # 仅补全
            ops = ['fetch']
            dry = self.repair_dry_cb.isChecked()

        sm = self.repair_start.currentText().strip()
        em = self.repair_end.currentText().strip()

        self.repair_log.clear()
        self.repair_log.appendPlainText(f'模式: {self.repair_mode.currentText()}')
        self.repair_log.appendPlainText(f'范围: {sm} ~ {em}' if 'fetch' in ops else f'操作: {ops}')
        self.repair_log.appendPlainText(f'预览: {"是" if dry else "否"}\n')

        self.repair_start_btn.setEnabled(False)
        self.repair_stop_btn.setEnabled(True)
        self.repair_progress.setVisible(True)
        self.repair_progress.setRange(0, 0)

        self.repair_thread = CveRepairThread(ops, start_month=sm, end_month=em, dry_run=dry)
        self._repair_stopped = False
        try:
            self._repair_work_id = self.db.start_work('漏洞库更新')
        except Exception:
            self._repair_work_id = None
        self.repair_thread.progress.connect(self._on_repair_progress)
        self.repair_thread.finished.connect(self._on_repair_finished)
        self.repair_thread.error.connect(self._on_repair_error)
        self.repair_thread.start()

    def _stop_db_repair(self):
        self._repair_stopped = True
        try:
            self.db.finish_work(self._repair_work_id, '被终止')
        except Exception:
            pass
        if hasattr(self, 'repair_thread') and self.repair_thread:
            self.repair_thread.stop()
            self.repair_thread.wait(3000)
        self.repair_start_btn.setEnabled(True)
        self.repair_stop_btn.setEnabled(False)
        self.repair_progress.setVisible(False)
        self.repair_log.appendPlainText('[已停止]')

    def _on_repair_progress(self, msg):
        self.repair_log.appendPlainText(msg)
        sb = self.repair_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_repair_finished(self, results):
        if not getattr(self, '_repair_stopped', False):
            try:
                self.db.finish_work(self._repair_work_id, '已完成')
            except Exception:
                pass
        self.repair_start_btn.setEnabled(True)
        self.repair_stop_btn.setEnabled(False)
        self.repair_progress.setVisible(False)
        self.repair_log.appendPlainText(f'\n完成: 清除{results.get("cleaned",0)}条, 回填{results.get("backfilled",0)}条, 新增{results.get("added",0)}条')
        self._refresh_db_status()

    def _on_repair_error(self, err):
        try:
            self.db.finish_work(self._repair_work_id, '被终止')
        except Exception:
            pass
        self.repair_log.appendPlainText(f'\n错误: {err}')
        self.repair_start_btn.setEnabled(True)
        self.repair_stop_btn.setEnabled(False)
        self.repair_progress.setVisible(False)

    # ============ AI代码审计 ============
    def _create_audit_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('AI代码审计', '使用AI分析源代码安全漏洞'))

        # ============ AI代码安全审计 ============
        security_card = QGroupBox('🛡️ AI代码安全审计（漏洞 / 注入 / 危险函数等安全缺陷）')
        security_layout = QVBoxLayout(security_card)

        # Claude Code Security 选项
        claude_layout = QHBoxLayout()
        self.claude_checkbox = QCheckBox('使用 Claude Code Security 进行深度AI审计（本机Claude Code加持）')
        self.claude_checkbox.setStyleSheet('font-size: 16px; font-weight: bold; color: #1a237e;')
        self.claude_checkbox.setChecked(True)  # 默认启用AI审计
        self.claude_checkbox.toggled.connect(self._on_claude_toggled)
        claude_layout.addWidget(self.claude_checkbox)
        claude_layout.addStretch()
        security_layout.addLayout(claude_layout)

        # API Key 状态指示 (直接使用系统设置中保存的密钥，无需重复输入)
        api_layout = QHBoxLayout()
        api_label = QLabel('API Key:')
        api_label.setStyleSheet('font-size: 16px;')
        api_layout.addWidget(api_label)
        self.claude_api_key = QLineEdit()
        self.claude_api_key.setPlaceholderText('可选：输入自定义API Key（留空则使用本机Claude Code）')
        self.claude_api_key.setEchoMode(QLineEdit.Password)
        self.claude_api_key.setMaximumWidth(500)
        self.claude_api_key.setEnabled(False)
        self.claude_api_key.setStyleSheet('font-size: 16px; padding: 6px;')
        api_layout.addWidget(self.claude_api_key)
        self.claude_key_status = QLabel('')
        self.claude_key_status.setStyleSheet('font-size: 14px;')
        api_layout.addWidget(self.claude_key_status)
        api_layout.addStretch()
        security_layout.addLayout(api_layout)

        # 代码路径选择 — 两个浏览按钮在左侧
        path_layout = QHBoxLayout()
        file_btn = QPushButton('选择代码文件')
        file_btn.clicked.connect(self._select_code_file)
        path_layout.addWidget(file_btn)
        dir_btn = QPushButton('选择代码存放文件夹')
        dir_btn.clicked.connect(self._select_code_dir)
        path_layout.addWidget(dir_btn)
        self.code_path_input = QLineEdit()
        self.code_path_input.setPlaceholderText('选择要审计的代码目录或文件...')
        path_layout.addWidget(self.code_path_input)
        security_layout.addLayout(path_layout)

        btn_layout = QHBoxLayout()
        self.audit_btn = QPushButton('开始安全审计')
        self.audit_btn.clicked.connect(self._start_audit)
        btn_layout.addWidget(self.audit_btn)

        self.audit_stop_btn = QPushButton('停止安全审计')
        self.audit_stop_btn.setObjectName('stopBtn')
        self.audit_stop_btn.clicked.connect(self._stop_audit)
        self.audit_stop_btn.setEnabled(False)
        btn_layout.addWidget(self.audit_stop_btn)

        self.audit_save_btn = QPushButton('保存审计报告')
        self.audit_save_btn.setObjectName('saveBtn')
        self.audit_save_btn.clicked.connect(self._save_audit_report)
        self.audit_save_btn.setEnabled(False)
        btn_layout.addWidget(self.audit_save_btn)

        self.audit_open_btn = QPushButton('打开审计报告')
        self.audit_open_btn.clicked.connect(self._open_audit_report)
        self.audit_open_btn.setEnabled(False)
        btn_layout.addWidget(self.audit_open_btn)
        btn_layout.addStretch()
        security_layout.addLayout(btn_layout)

        self.audit_progress = QProgressBar()
        self.audit_progress.setVisible(False)
        security_layout.addWidget(self.audit_progress)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(8)
        self.audit_table.setHorizontalHeaderLabels(['文件', '行号', '维度', '类别', '严重程度', '代码片段', '问题描述', '解决方案'])
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        security_layout.addWidget(self.audit_table)

        self.audit_log = QPlainTextEdit()
        self.audit_log.setReadOnly(True)
        self.audit_log.setMaximumHeight(120)
        security_layout.addWidget(self.audit_log)

        layout.addWidget(security_card)

        self.tabs.addTab(widget, 'AI代码审计')

    def _create_quality_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('AI代码质量检测', '使用AI分析代码架构/逻辑/接口/命名等设计缺陷'))

        # ============ AI代码质量检测 ============
        quality_card = QGroupBox('🔍 AI代码质量检测（架构 / 逻辑 / 接口 / 命名等设计缺陷）')
        quality_layout = QVBoxLayout(quality_card)

        qual_path_layout = QHBoxLayout()
        qual_file_btn = QPushButton('选择代码文件')
        qual_file_btn.clicked.connect(self._select_quality_code_file)
        qual_path_layout.addWidget(qual_file_btn)
        qual_dir_btn = QPushButton('选择代码存放文件夹')
        qual_dir_btn.clicked.connect(self._select_quality_code_dir)
        qual_path_layout.addWidget(qual_dir_btn)
        self.quality_code_path_input = QLineEdit()
        self.quality_code_path_input.setPlaceholderText('选择要检测的代码目录或文件...')
        qual_path_layout.addWidget(self.quality_code_path_input)
        quality_layout.addLayout(qual_path_layout)

        qual_btn_layout = QHBoxLayout()
        self.quality_audit_btn = QPushButton('开始质量检测')
        self.quality_audit_btn.clicked.connect(self._start_quality_audit)
        qual_btn_layout.addWidget(self.quality_audit_btn)
        self.quality_audit_stop_btn = QPushButton('停止质量检测')
        self.quality_audit_stop_btn.setObjectName('stopBtn')
        self.quality_audit_stop_btn.clicked.connect(self._stop_quality_audit)
        self.quality_audit_stop_btn.setEnabled(False)
        qual_btn_layout.addWidget(self.quality_audit_stop_btn)

        self.quality_audit_save_btn = QPushButton('保存报告')
        self.quality_audit_save_btn.setObjectName('saveBtn')
        self.quality_audit_save_btn.clicked.connect(self._save_quality_audit_report)
        self.quality_audit_save_btn.setEnabled(False)
        qual_btn_layout.addWidget(self.quality_audit_save_btn)

        self.quality_audit_open_btn = QPushButton('打开报告')
        self.quality_audit_open_btn.clicked.connect(self._open_quality_audit_report)
        self.quality_audit_open_btn.setEnabled(False)
        qual_btn_layout.addWidget(self.quality_audit_open_btn)
        qual_btn_layout.addStretch()
        quality_layout.addLayout(qual_btn_layout)

        self.quality_audit_progress = QProgressBar()
        self.quality_audit_progress.setVisible(False)
        quality_layout.addWidget(self.quality_audit_progress)

        self.quality_audit_table = QTableWidget()
        self.quality_audit_table.setColumnCount(8)
        self.quality_audit_table.setHorizontalHeaderLabels(['文件', '行号', '维度', '类别', '严重程度', '代码片段', '问题描述', '解决方案'])
        self.quality_audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        quality_layout.addWidget(self.quality_audit_table)

        self.quality_audit_log = QPlainTextEdit()
        self.quality_audit_log.setReadOnly(True)
        self.quality_audit_log.setMaximumHeight(120)
        quality_layout.addWidget(self.quality_audit_log)

        layout.addWidget(quality_card)

        self.tabs.addTab(widget, 'AI代码质量检测')

    def _on_claude_toggled(self, checked):
        """Claude Code Security 复选框切换"""
        if checked:
            saved_key = self.db.get_setting('claude_api_key', '')
            self.claude_api_key.setText(saved_key)
            self.claude_api_key.setStyleSheet(
                'font-size: 16px; padding: 6px; border: 2px solid #107c10; background: #dff6dd;')
            self.claude_key_status.setText('✅ AI审计将使用本机Claude Code执行')
            self.claude_key_status.setStyleSheet('font-size: 14px; color: #107c10; font-weight: bold;')
        else:
            self.claude_api_key.setText('')
            self.claude_api_key.setStyleSheet('font-size: 16px; padding: 6px;')
            self.claude_key_status.setText('')
            self.claude_key_status.setStyleSheet('font-size: 14px;')

    def _browse_code_path(self):
        """支持选择文件或目录"""
        menu = QMenu(self)
        dir_action = QAction('选择文件夹', self)
        dir_action.triggered.connect(lambda: self._select_code_dir())
        menu.addAction(dir_action)
        file_action = QAction('选择文件', self)
        file_action.triggered.connect(lambda: self._select_code_file())
        menu.addAction(file_action)
        # 在浏览按钮下方展开菜单
        browse_btn = self.sender()
        if browse_btn:
            menu.popup(browse_btn.mapToGlobal(browse_btn.rect().bottomLeft()))
        else:
            menu.popup(self.mapToGlobal(QPoint(0, 0)))

    def _select_code_dir(self):
        path = QFileDialog.getExistingDirectory(self, '选择代码目录')
        if path:
            self.code_path_input.setText(path)

    def _select_code_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, '选择代码文件',
            filter='代码文件 (*.py *.js *.ts *.java *.go *.php *.rb *.c *.cpp *.html *.txt);;所有文件 (*)')
        if filepath:
            self.code_path_input.setText(filepath)

    def _start_audit(self):
        path = self.code_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, '警告', '请输入代码路径')
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, '警告', '路径不存在')
            return

        use_claude = self.claude_checkbox.isChecked()
        if use_claude:
            api_key = self.claude_api_key.text().strip()
            # 如果界面未填写，自动从系统设置中获取已保存的API密钥
            if not api_key:
                api_key = self.db.get_setting('claude_api_key', '')
                if api_key:
                    self.claude_api_key.setText(api_key)
                    self._safe_log('audit_log', '已从系统设置自动加载API密钥')
            # API Key 可选：未配置时使用本机Claude Code CLI
            if not api_key:
                self._safe_log('audit_log', '未配置API Key，将使用本机Claude Code执行AI审计')
            else:
                self._safe_log('audit_log', f'API Key 已配置 (长度: {len(api_key)})')

        self.audit_btn.setEnabled(False)
        self.audit_stop_btn.setEnabled(True)
        self.audit_save_btn.setEnabled(False)
        self.audit_open_btn.setEnabled(False)
        self.audit_progress.setVisible(True)
        self.audit_progress.setValue(0)
        self._safe_clear('audit_log')
        self.audit_table.setRowCount(0)
        self._ai_audit_popup_shown = False  # 重置弹窗标记

        # 根据是否启用Claude选择审计类型
        audit_type = 'claude_security' if use_claude else 'code'
        api_key = (self.claude_api_key.text().strip() or None) if use_claude else None

        self.current_audit_thread = AIAuditThread(self.ai_analyzer, path, audit_type, api_key)
        self._audit_stopped = False
        try:
            self._audit_work_id = self.db.start_work('AI代码审计')
        except Exception:
            self._audit_work_id = None
        self.current_audit_thread.progress.connect(self._on_audit_progress)
        self.current_audit_thread.finished.connect(self._on_audit_finished)
        self.current_audit_thread.error.connect(self._on_audit_error)
        self.current_audit_thread.start()
        self._safe_log('audit_log',f'开始安全审计: {path}')

    def _stop_audit(self):
        self._audit_stopped = True
        try:
            self.db.finish_work(self._audit_work_id, '被终止')
        except Exception:
            pass
        if self.current_audit_thread:
            self.current_audit_thread.stop_security()
            self.current_audit_thread.stop_quality()
            self.current_audit_thread.requestInterruption()
            if not self.current_audit_thread.wait(5000):
                self.current_audit_thread.terminate()
                self.current_audit_thread.wait(1000)
            self.current_audit_thread = None
        self.audit_btn.setEnabled(True)
        self.audit_stop_btn.setEnabled(False)
        self.audit_progress.setVisible(False)

    def _load_last_audit_result(self):
        """加载最近一次代码审计结果到界面"""
        try:
            history = self.db.get_audit_history(limit=1)
            if not history or len(history) == 0:
                return
            last = history[0]

            target = last.get('target', 'N/A')
            scan_time = last.get('scan_time', last.get('generated_at', ''))
            total_files = last.get('total_files_scanned', 0)
            total_vulns = last.get('total_vulnerabilities', 0)
            risk_level = last.get('risk_level', 'N/A')
            severity = last.get('severity_summary', {})
            issues = last.get('issues', [])

            self._safe_log('audit_log',
                f'已加载历史审计记录 | 目标: {target} | '
                f'时间: {scan_time} | '
                f'扫描文件: {total_files} | '
                f'发现问题: {total_vulns} | '
                f'风险等级: {risk_level}')
            if severity:
                sev_str = ', '.join(f'{k}: {v}' for k, v in severity.items())
                self._safe_log('audit_log', f'严重度分布: {sev_str}')

            if not issues:
                return

            # 填充审计表格
            self.audit_table.setRowCount(0)
            for issue in issues:
                row = self.audit_table.rowCount()
                self.audit_table.insertRow(row)
                dim = issue.get('dimension') or 'security'
                problem = issue.get('problem') or issue.get('code') or ''
                self.audit_table.setItem(row, 0, QTableWidgetItem(str(issue.get('file', ''))))
                self.audit_table.setItem(row, 1, QTableWidgetItem(str(issue.get('line', ''))))
                self.audit_table.setItem(row, 2, QTableWidgetItem(DIMENSION_LABELS.get(dim, '安全')))
                self.audit_table.setItem(row, 3, QTableWidgetItem(str(issue.get('category', ''))))
                self.audit_table.setItem(row, 4, QTableWidgetItem(str(issue.get('severity', 'INFO'))))
                self.audit_table.setItem(row, 5, QTableWidgetItem(str(issue.get('code', ''))[:80]))
                self.audit_table.setItem(row, 6, QTableWidgetItem(str(problem)[:120]))
                sol_item = QTableWidgetItem(str(issue.get('recommendation', ''))[:200])
                sol_item.setToolTip(_build_audit_tooltip(issue))
                self.audit_table.setItem(row, 7, sol_item)

                sev = str(issue.get('severity', '')).upper()
                if sev in ['CRITICAL', 'HIGH']:
                    for c in range(8):
                        item = self.audit_table.item(row, c)
                        if item:
                            item.setBackground(QColor(255, 210, 210))
                elif sev == 'MEDIUM':
                    for c in range(8):
                        item = self.audit_table.item(row, c)
                        if item:
                            item.setBackground(QColor(255, 255, 210))

            self.audit_save_btn.setEnabled(True)
            self.audit_open_btn.setEnabled(True)
        except Exception:
            pass

    def _on_audit_progress(self, msg):
        self._safe_log('audit_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')
        # AI核验/质量审计阶段开始时弹出提示窗（非代码扫描阶段）
        if ('AI验证' in msg or 'AI核验' in msg or '质量审计' in msg or '代码质量' in msg) \
                and not getattr(self, '_ai_audit_popup_shown', False):
            self._ai_audit_popup_shown = True
            wait_dlg = QMessageBox(self)
            wait_dlg.setWindowTitle('AI审计')
            wait_dlg.setIcon(QMessageBox.Information)
            wait_dlg.setText('AI代码审计比较费时，请您耐心等待！')
            wait_dlg.setStandardButtons(QMessageBox.Close)
            stop_audit_btn = wait_dlg.addButton('停止AI审计', QMessageBox.DestructiveRole)
            stop_audit_btn.clicked.connect(self._stop_audit)
            wait_dlg.setModal(False)
            wait_dlg.show()
            wait_dlg.finished.connect(lambda: setattr(self, '_ai_audit_wait_dlg', None))
            self._ai_audit_wait_dlg = wait_dlg

    def _on_audit_finished(self, result):
        if not getattr(self, '_audit_stopped', False):
            try:
                self.db.finish_work(self._audit_work_id, '已完成')
            except Exception:
                pass
        # 关闭等待对话框
        if getattr(self, '_ai_audit_wait_dlg', None):
            try:
                self._ai_audit_wait_dlg.accept()
            except RuntimeError:
                pass
            self._ai_audit_wait_dlg = None
        self.audit_progress.setValue(100)
        self._safe_log('audit_log','审计完成!')
        self.last_audit_result = result
        self.audit_history.insert(0, result)
        if len(self.audit_history) > 50:
            self.audit_history = self.audit_history[:50]
        self.db.save_audit_result(result)

        self.audit_table.setRowCount(0)
        for issue in result.get('issues', []):
            row = self.audit_table.rowCount()
            self.audit_table.insertRow(row)
            dim = issue.get('dimension') or 'security'
            problem = issue.get('problem') or issue.get('code') or ''
            self.audit_table.setItem(row, 0, QTableWidgetItem(issue.get('file', '')))
            self.audit_table.setItem(row, 1, QTableWidgetItem(str(issue.get('line', ''))))
            self.audit_table.setItem(row, 2, QTableWidgetItem(DIMENSION_LABELS.get(dim, '安全')))
            self.audit_table.setItem(row, 3, QTableWidgetItem(issue.get('category', '')))
            self.audit_table.setItem(row, 4, QTableWidgetItem(issue.get('severity', '')))
            self.audit_table.setItem(row, 5, QTableWidgetItem(issue.get('code', '')[:80]))
            self.audit_table.setItem(row, 6, QTableWidgetItem(problem[:120]))
            sol_item = QTableWidgetItem(issue.get('recommendation', '')[:200])
            sol_item.setToolTip(_build_audit_tooltip(issue))
            self.audit_table.setItem(row, 7, sol_item)

            sev = issue.get('severity', '')
            if sev in ['CRITICAL', 'HIGH']:
                for c in range(8):
                    item = self.audit_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 210, 210))

        total = result.get('total_vulnerabilities', 0)
        self._safe_log('audit_log',f'扫描文件: {result.get("total_files_scanned", 0)}')
        self._safe_log('audit_log',f'发现问题: {total}')
        risk = result.get('risk_level', '未知')
        self._safe_log('audit_log',f'风险等级: {risk}')

        # AI验证统计
        if result.get('ai_enhanced'):
            regex_candidates = result.get('regex_candidates', 0)
            ai_excluded = result.get('ai_excluded_count', 0)
            ai_stats = result.get('ai_verification_stats', {})
            self._safe_log('audit_log', f'--- AI验证统计 ---')
            self._safe_log('audit_log', f'Regex初筛候选: {regex_candidates}')
            self._safe_log('audit_log', f'AI确认漏洞: {total}')
            self._safe_log('audit_log', f'AI排除误报: {ai_excluded}')
            if ai_stats:
                self._safe_log('audit_log', f'误报排除率: {ai_stats.get("fp_rate", 0):.1%}')

        # 代码质量/设计审计统计
        quality_count = result.get('quality_issues_count', 0)
        if quality_count:
            dim_summary = result.get('dimension_summary', {})
            dim_str = ', '.join(
                f'{DIMENSION_LABELS.get(k, k)}:{v}' for k, v in dim_summary.items() if k != 'security'
            )
            self._safe_log('audit_log', '--- 代码质量/设计审计统计 ---')
            self._safe_log('audit_log', f'设计问题数: {quality_count}')
            if dim_str:
                self._safe_log('audit_log', f'维度分布: {dim_str}')

        self._safe_log('audit_log',f'建议: {result.get("recommendation", "")}')
        self._safe_log('audit_log','审计结果已自动存入代码审计数据库')

        # 自动保存审计报告到文件（HTML + MD）
        try:
            from report_generator import _generate_audit_html
            report_dir = self._report_dir()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            target_name = re.sub(r'[^A-Za-z0-9._-]', '_', str(result.get('target', 'unknown')))
            # HTML
            html_content = _generate_audit_html(result)
            html_path = os.path.join(report_dir, f'AI代码安全审计报告_{target_name}_{ts}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            # MD
            md_path = os.path.join(report_dir, f'AI代码安全审计报告_{target_name}_{ts}.md')
            md_content = self._generate_audit_md(result)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            self.last_audit_report_path = html_path
            self.db.save_report(
                f'AI代码审计报告 - {result.get("target", "")}',
                'audit', 'html', f'发现{result.get("total_vulnerabilities", 0)}个问题', html_path)
            self._safe_log('audit_log', f'审计报告已自动保存至: {html_path}')
            self._safe_log('audit_log', f'审计报告(MD)已自动保存至: {md_path}')
        except Exception as e:
            self._safe_log('audit_log', f'审计报告自动保存失败: {e}')

        self.audit_btn.setEnabled(True)
        self.audit_stop_btn.setEnabled(False)
        self.audit_save_btn.setEnabled(True)
        self.audit_open_btn.setEnabled(True)
        self.audit_progress.setVisible(False)

        QMessageBox.information(self, '审计完成', f'审计完成，发现 {total} 个安全问题\n风险等级: {risk}')

    def _on_audit_error(self, error):
        try:
            self.db.finish_work(self._audit_work_id, '被终止')
        except Exception:
            pass
        self._safe_log('audit_log',f'错误: {error}')
        self.audit_btn.setEnabled(True)
        self.audit_stop_btn.setEnabled(False)
        self.audit_progress.setVisible(False)
        QMessageBox.critical(self, '审计错误', error)

    # ============ 卡片2：AI代码质量检测 处理器 ============
    def _select_quality_code_dir(self):
        path = QFileDialog.getExistingDirectory(self, '选择代码目录')
        if path:
            self.quality_code_path_input.setText(path)

    def _select_quality_code_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, '选择代码文件',
            filter='代码文件 (*.py *.js *.ts *.java *.go *.php *.rb *.c *.cpp *.html *.txt);;所有文件 (*)')
        if filepath:
            self.quality_code_path_input.setText(filepath)

    def _start_quality_audit(self):
        path = self.quality_code_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, '警告', '请输入代码路径')
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, '警告', '路径不存在')
            return

        self.quality_audit_btn.setEnabled(False)
        self.quality_audit_stop_btn.setEnabled(True)
        self.quality_audit_save_btn.setEnabled(False)
        self.quality_audit_open_btn.setEnabled(False)
        self.quality_audit_progress.setVisible(True)
        self.quality_audit_progress.setValue(0)
        self._safe_clear('quality_audit_log')
        self.quality_audit_table.setRowCount(0)
        api_key = self.db.get_setting('claude_api_key', '') or None

        self.current_quality_audit_thread = AIAuditThread(self.ai_analyzer, path, 'quality', api_key)
        self._quality_stopped = False
        try:
            self._quality_work_id = self.db.start_work('AI代码质量检测')
        except Exception:
            self._quality_work_id = None
        self.current_quality_audit_thread.progress.connect(self._on_quality_audit_progress)
        self.current_quality_audit_thread.finished.connect(self._on_quality_audit_finished)
        self.current_quality_audit_thread.error.connect(self._on_quality_audit_error)
        self.current_quality_audit_thread.start()
        self._safe_log('quality_audit_log', f'开始代码质量检测: {path}')

    def _stop_quality_audit(self):
        self._quality_stopped = True
        try:
            self.db.finish_work(self._quality_work_id, '被终止')
        except Exception:
            pass
        if self.current_quality_audit_thread:
            self.current_quality_audit_thread.stop_quality()
            self.current_quality_audit_thread.requestInterruption()
            if not self.current_quality_audit_thread.wait(5000):
                self.current_quality_audit_thread.terminate()
                self.current_quality_audit_thread.wait(1000)
            self.current_quality_audit_thread = None
        self.quality_audit_btn.setEnabled(True)
        self.quality_audit_stop_btn.setEnabled(False)
        self.quality_audit_progress.setVisible(False)
        self._safe_log('quality_audit_log', '质量检测已停止')

    def _on_quality_audit_progress(self, msg):
        self._safe_log('quality_audit_log', f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _on_quality_audit_finished(self, result):
        if not getattr(self, '_quality_stopped', False):
            try:
                self.db.finish_work(self._quality_work_id, '已完成')
            except Exception:
                pass
        self.quality_audit_progress.setValue(100)
        self._safe_log('quality_audit_log', '代码质量检测完成!')
        self.last_quality_audit_result = result

        self.quality_audit_table.setRowCount(0)
        for issue in result.get('issues', []):
            row = self.quality_audit_table.rowCount()
            self.quality_audit_table.insertRow(row)
            dim = issue.get('dimension') or 'quality'
            problem = issue.get('problem') or issue.get('code') or ''
            self.quality_audit_table.setItem(row, 0, QTableWidgetItem(str(issue.get('file', ''))))
            self.quality_audit_table.setItem(row, 1, QTableWidgetItem(str(issue.get('line', ''))))
            self.quality_audit_table.setItem(row, 2, QTableWidgetItem(DIMENSION_LABELS.get(dim, dim)))
            self.quality_audit_table.setItem(row, 3, QTableWidgetItem(str(issue.get('category', ''))))
            self.quality_audit_table.setItem(row, 4, QTableWidgetItem(str(issue.get('severity', 'INFO'))))
            self.quality_audit_table.setItem(row, 5, QTableWidgetItem(str(issue.get('code', ''))[:80]))
            self.quality_audit_table.setItem(row, 6, QTableWidgetItem(str(problem)[:120]))
            sol_item = QTableWidgetItem(str(issue.get('recommendation', ''))[:200])
            sol_item.setToolTip(_build_audit_tooltip(issue))
            self.quality_audit_table.setItem(row, 7, sol_item)

            sev = str(issue.get('severity', '')).upper()
            if sev in ['CRITICAL', 'HIGH']:
                for c in range(8):
                    item = self.quality_audit_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 210, 210))
            elif sev == 'MEDIUM':
                for c in range(8):
                    item = self.quality_audit_table.item(row, c)
                    if item:
                        item.setBackground(QColor(255, 255, 210))

        total = result.get('total_vulnerabilities', 0)
        files = result.get('total_files_scanned', 0)
        dim_summary = result.get('dimension_summary', {})
        dim_str = ', '.join(f'{DIMENSION_LABELS.get(k, k)}:{v}' for k, v in dim_summary.items())
        self._safe_log('quality_audit_log', f'扫描文件: {files}, 发现问题: {total}')
        if dim_str:
            self._safe_log('quality_audit_log', f'维度分布: {dim_str}')

        # 自动保存代码质量检测报告到文件（HTML + MD）
        try:
            from report_generator import _generate_audit_html
            report_dir = self._report_dir()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            target_name = re.sub(r'[^A-Za-z0-9._-]', '_', str(result.get('target', 'unknown')))
            # HTML
            html_content = _generate_audit_html(result, title='AI代码质量检测报告')
            html_path = os.path.join(report_dir, f'AI代码质量检测报告_{target_name}_{ts}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            # MD
            md_path = os.path.join(report_dir, f'AI代码质量检测报告_{target_name}_{ts}.md')
            md_content = self._generate_quality_audit_md(result)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            self.last_quality_audit_report_path = html_path
            self.db.save_report(
                f'AI代码质量检测报告 - {result.get("target", "")}',
                'quality_audit', 'html', f'发现{result.get("total_vulnerabilities", 0)}个问题', html_path)
            self._safe_log('quality_audit_log', f'检测报告已自动保存至: {html_path}')
            self._safe_log('quality_audit_log', f'检测报告(MD)已自动保存至: {md_path}')
        except Exception as e:
            self._safe_log('quality_audit_log', f'检测报告自动保存失败: {e}')

        self.quality_audit_btn.setEnabled(True)
        self.quality_audit_stop_btn.setEnabled(False)
        self.quality_audit_save_btn.setEnabled(True)
        self.quality_audit_open_btn.setEnabled(True)
        self.quality_audit_progress.setVisible(False)

    def _on_quality_audit_error(self, error):
        try:
            self.db.finish_work(self._quality_work_id, '被终止')
        except Exception:
            pass
        self._safe_log('quality_audit_log', f'错误: {error}')
        self.quality_audit_btn.setEnabled(True)
        self.quality_audit_stop_btn.setEnabled(False)
        self.quality_audit_progress.setVisible(False)
        QMessageBox.critical(self, '质量检测错误', error)

    def _save_audit_report(self):
        if not self.last_audit_result:
            QMessageBox.warning(self, '警告', '没有可保存的审计结果')
            return
        default_path = os.path.join(self._report_dir(), f'audit_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        filepath, _ = QFileDialog.getSaveFileName(self, '保存审计报告', default_path, self._report_filter())
        if not filepath:
            return
        try:
            from report_generator import generate_audit_report
            from report_converter import save_report_formatted
            # 先生成HTML，再转换格式
            tmp_html = os.path.join(self._report_dir(), f'_tmp_audit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')
            generate_audit_report(self.last_audit_result, os.path.dirname(tmp_html) or 'reports')
            # 读取生成的HTML
            report_html_path = tmp_html
            if not os.path.exists(report_html_path):
                # 查找最近生成的审计报告
                import glob
                candidates = glob.glob(os.path.join(self._report_dir(), 'audit_report_*.html'))
                if candidates:
                    report_html_path = max(candidates, key=os.path.getmtime)
            if os.path.exists(report_html_path):
                with open(report_html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                ok, actual_path = save_report_formatted(html_content, filepath)
                if not ok:
                    raise RuntimeError('格式转换失败')
                # 清理临时文件
                if report_html_path != actual_path:
                    try: os.remove(report_html_path)
                    except: pass
                self.last_audit_report_path = actual_path
                QMessageBox.information(self, '成功', f'审计报告已保存至:\n{actual_path}')
            else:
                self.last_audit_report_path = filepath
                QMessageBox.information(self, '成功', f'审计报告已保存至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _generate_audit_md(self, result):
        """从审计结果生成Markdown报告"""
        target = result.get('target', 'unknown')
        total_files = result.get('total_files_scanned', 0)
        total_vulns = result.get('total_vulnerabilities', 0)
        risk = result.get('risk_level', '未知')
        issues = result.get('issues', [])
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        md = f'# AI代码安全审计报告\n\n'
        md += f'**审计目标**: {target}\n\n'
        md += f'**审计时间**: {ts}\n\n'
        md += f'**扫描文件数**: {total_files}\n\n'
        md += f'**发现问题数**: {total_vulns}\n\n'
        md += f'**风险等级**: {risk}\n\n'
        md += f'---\n\n## 问题详情\n\n'
        if issues:
            md += '| 文件 | 行号 | 维度 | 类别 | 严重程度 | 代码片段 | 问题描述 | 解决方案 |\n'
            md += '|------|------|------|------|---------|---------|----------|----------|\n'
            for issue in issues:
                file = issue.get('file', '').replace('|', '/')
                line = issue.get('line', '')
                dim = DIMENSION_LABELS.get(issue.get('dimension') or 'security', '安全')
                category = issue.get('category', '')
                severity = issue.get('severity', '')
                code = (issue.get('code', '') or '')[:60].replace('|', '/').replace('\n', ' ')
                problem = (issue.get('problem') or issue.get('code') or '')[:120].replace('|', '/').replace('\n', ' ')
                recommendation = (issue.get('recommendation', '') or '')[:200].replace('|', '/').replace('\n', ' ')
                md += f'| {file} | {line} | {dim} | {category} | {severity} | {code} | {problem} | {recommendation} |\n'
        else:
            md += '*(未发现安全问题)*\n'
        md += f'\n---\n\n'
        if result.get('ai_enhanced'):
            md += f'**AI增强审计**: 是\n\n'
        md += f'*本报告由AI代码安全审计模块自动生成 | 山西有信网安科技有限公司*\n'
        return md

    def _generate_quality_audit_md(self, result):
        """从代码质量检测结果生成Markdown报告"""
        target = result.get('target', 'unknown')
        total_files = result.get('total_files_scanned', 0)
        total_issues = result.get('total_vulnerabilities', 0)
        issues = result.get('issues', [])
        dim_summary = result.get('dimension_summary', {})
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        md = f'# AI代码质量检测报告\n\n'
        md += f'**检测目标**: {target}\n\n'
        md += f'**检测时间**: {ts}\n\n'
        md += f'**扫描文件数**: {total_files}\n\n'
        md += f'**发现问题数**: {total_issues}\n\n'
        if dim_summary:
            dim_str = ', '.join(f'{DIMENSION_LABELS.get(k, k)}:{v}' for k, v in dim_summary.items())
            md += f'**维度分布**: {dim_str}\n\n'
        md += f'---\n\n## 问题详情\n\n'
        if issues:
            md += '| 文件 | 行号 | 维度 | 类别 | 严重程度 | 代码片段 | 问题描述 | 解决方案 |\n'
            md += '|------|------|------|------|---------|---------|----------|----------|\n'
            for issue in issues:
                file = issue.get('file', '').replace('|', '/')
                line = issue.get('line', '')
                dim = DIMENSION_LABELS.get(issue.get('dimension') or 'quality', '质量')
                category = issue.get('category', '')
                severity = issue.get('severity', '')
                code = (issue.get('code', '') or '')[:60].replace('|', '/').replace('\n', ' ')
                problem = (issue.get('problem') or issue.get('code') or '')[:120].replace('|', '/').replace('\n', ' ')
                recommendation = (issue.get('recommendation', '') or '')[:200].replace('|', '/').replace('\n', ' ')
                md += f'| {file} | {line} | {dim} | {category} | {severity} | {code} | {problem} | {recommendation} |\n'
        else:
            md += '*(未发现代码质量问题)*\n'
        md += f'\n---\n\n'
        md += f'*本报告由AI代码质量检测模块自动生成 | 山西有信网安科技有限公司*\n'
        return md

    def _open_audit_report(self):
        """打开审计报告 - 优先打开最近保存的报告文件"""
        filepath = getattr(self, 'last_audit_report_path', None)
        if not filepath or not os.path.exists(filepath):
            filepath, _ = QFileDialog.getOpenFileName(self, '打开审计报告', self._report_dir(),
                self._report_filter() + ';;所有文件 (*)')
        if filepath and os.path.exists(filepath):
            try:
                os.startfile(filepath)
            except Exception as e:
                QMessageBox.critical(self, '错误', f'打开失败: {str(e)}')
        elif filepath:
            QMessageBox.warning(self, '警告', '报告文件不存在，请选择其他文件')

    def _save_quality_audit_report(self):
        """保存代码质量检测报告到用户指定路径"""
        if not getattr(self, 'last_quality_audit_result', None):
            QMessageBox.warning(self, '警告', '没有可保存的检测结果')
            return
        default_path = os.path.join(self._report_dir(), f'quality_audit_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        filepath, _ = QFileDialog.getSaveFileName(self, '保存质量检测报告', default_path, self._report_filter())
        if not filepath:
            return
        try:
            from report_generator import _generate_audit_html
            if filepath.lower().endswith('.md'):
                content = self._generate_quality_audit_md(self.last_quality_audit_result)
            else:
                content = _generate_audit_html(self.last_quality_audit_result, title='AI代码质量检测报告')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.last_quality_audit_report_path = filepath
            QMessageBox.information(self, '成功', f'质量检测报告已保存至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _open_quality_audit_report(self):
        """打开代码质量检测报告 - 优先打开最近保存的报告文件"""
        filepath = getattr(self, 'last_quality_audit_report_path', None)
        if not filepath or not os.path.exists(filepath):
            filepath, _ = QFileDialog.getOpenFileName(self, '打开质量检测报告', self._report_dir(),
                self._report_filter() + ';;所有文件 (*)')
        if filepath and os.path.exists(filepath):
            try:
                os.startfile(filepath)
            except Exception as e:
                QMessageBox.critical(self, '错误', f'打开失败: {str(e)}')
        elif filepath:
            QMessageBox.warning(self, '警告', '报告文件不存在，请选择其他文件')

    # ============ 威胁情报 ============
    def _create_intel_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('威胁情报', '从全球6大数据源收集威胁情报'))

        btn_layout = QHBoxLayout()
        self.intel_update_btn = QPushButton('获取全球威胁情报')
        self.intel_update_btn.setObjectName('saveBtn')
        self.intel_update_btn.clicked.connect(self._start_intel_collection)
        btn_layout.addWidget(self.intel_update_btn)

        self.intel_stop_btn = QPushButton('停止搜索')
        self.intel_stop_btn.setObjectName('stopBtn')
        self.intel_stop_btn.clicked.connect(self._stop_intel)
        self.intel_stop_btn.setEnabled(False)
        btn_layout.addWidget(self.intel_stop_btn)

        self.intel_preset = QComboBox()
        self.intel_preset.addItems(['7天', '10天', '15天', '1个月', '3个月', '半年', '全年', '自定义'])
        self.intel_preset.setCurrentIndex(0)
        self.intel_preset.currentTextChanged.connect(self._on_intel_preset_changed)
        btn_layout.addWidget(self.intel_preset)

        self.intel_date_start = QDateEdit()
        self.intel_date_start.setCalendarPopup(True)
        self.intel_date_start.setDate(QDate.currentDate().addDays(-7))
        self.intel_date_start.setMaximumDate(QDate.currentDate())
        self.intel_date_start.setDisplayFormat('yyyy-MM-dd')
        self.intel_date_start.hide()
        btn_layout.addWidget(self.intel_date_start)

        self.intel_date_sep = QLabel(' 至 ')
        self.intel_date_sep.hide()
        btn_layout.addWidget(self.intel_date_sep)

        self.intel_date_end = QDateEdit()
        self.intel_date_end.setCalendarPopup(True)
        self.intel_date_end.setDate(QDate.currentDate())
        self.intel_date_end.setMaximumDate(QDate.currentDate())
        self.intel_date_end.setDisplayFormat('yyyy-MM-dd')
        self.intel_date_end.hide()
        btn_layout.addWidget(self.intel_date_end)

        self.intel_ai_report_btn = QPushButton('🤖 AI综合报告')
        self.intel_ai_report_btn.setToolTip('使用AI生成包含17个章节的深度威胁情报分析报告（MD+HTML）')
        self.intel_ai_report_btn.clicked.connect(self._start_ai_report_generation)
        self.intel_ai_report_btn.setEnabled(False)
        btn_layout.addWidget(self.intel_ai_report_btn)

        self.intel_save_btn = QPushButton('保存报告')
        self.intel_save_btn.setObjectName('saveBtn')
        self.intel_save_btn.clicked.connect(self._save_intel_report)
        self.intel_save_btn.setEnabled(False)
        btn_layout.addWidget(self.intel_save_btn)

        self.intel_open_btn = QPushButton('打开报告')
        self.intel_open_btn.clicked.connect(self._open_report)
        self.intel_open_btn.setEnabled(False)
        btn_layout.addWidget(self.intel_open_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.intel_progress = QProgressBar()
        self.intel_progress.setVisible(False)
        layout.addWidget(self.intel_progress)

        self.intel_log = QPlainTextEdit()
        self.intel_log.setReadOnly(True)
        self.intel_log.setStyleSheet('font-size: 18px; font-family: monospace; background: #ffffff; color: #333; border: 1px solid #d0d0d0;')
        self.intel_log.setMinimumHeight(400)
        layout.addWidget(self.intel_log)

        self.tabs.addTab(widget, '威胁情报')

    def _on_intel_progress_msg(self, msg):
        self._safe_log('intel_log',f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _on_intel_preset_changed(self, text):
        """预设切换：自定义时显示日期选择器，否则隐藏"""
        if text == '自定义':
            self.intel_date_start.show()
            self.intel_date_sep.show()
            self.intel_date_end.show()
            today = QDate.currentDate()
            self.intel_date_start.setDate(today.addDays(-7))
            self.intel_date_end.setDate(today)
        else:
            self.intel_date_start.hide()
            self.intel_date_sep.hide()
            self.intel_date_end.hide()

    PRESET_DAYS = {
        '7天': 7, '10天': 10, '15天': 15,
        '1个月': 30, '3个月': 90,
        '半年': 182, '全年': 365,
    }

    def _start_intel_collection(self):
        """启动全球威胁情报收集"""
        self.intel_update_btn.setText('正在全网搜索威胁情报......')
        self.intel_update_btn.setEnabled(False)
        self.intel_stop_btn.setEnabled(True)
        self.intel_save_btn.setEnabled(False)
        self.intel_open_btn.setEnabled(False)
        self.intel_progress.setVisible(True)
        self.intel_progress.setValue(0)
        self.intel_progress.setRange(0, 0)
        self._safe_clear('intel_log')

        preset = self.intel_preset.currentText()
        if preset == '自定义':
            start_date = self.intel_date_start.date().toString('yyyy-MM-dd')
            end_date = self.intel_date_end.date().toString('yyyy-MM-dd')
            if self.intel_date_start.date() > self.intel_date_end.date():
                QMessageBox.warning(self, '日期错误', '开始日期不能晚于结束日期')
                self.intel_update_btn.setText('获取全球威胁情报')
                self.intel_update_btn.setEnabled(True)
                self.intel_stop_btn.setEnabled(False)
                self.intel_progress.setVisible(False)
                return
        else:
            d = self.PRESET_DAYS.get(preset, 7)
            today = QDate.currentDate()
            start_date = today.addDays(-d).toString('yyyy-MM-dd')
            end_date = today.toString('yyyy-MM-dd')

        # 保存日期范围供AI报告使用
        self.intel_date_range = (start_date, end_date)
        self.threat_intel._stop_requested = False

        self.intel_collect_thread = IntelCollectThread(
            self.threat_intel, start_date=start_date, end_date=end_date
        )
        self._intel_stopped = False
        try:
            self._intel_work_id = self.db.start_work('威胁情报')
        except Exception:
            self._intel_work_id = None
        self.intel_collect_thread.progress.connect(self._on_intel_progress)
        self.intel_collect_thread.finished.connect(self._on_intel_collection_finished)
        self.intel_collect_thread.error.connect(self._on_intel_error)
        self.intel_collect_thread.start()

    def _on_intel_progress(self, msg):
        self._safe_log('intel_log', msg)

    def _on_intel_collection_finished(self, results):
        self.intel_progress.setRange(0, 100)
        self.intel_progress.setValue(100)

        # 记录威胁情报采集工作完成（供仪表盘"今日工作"次数统计）
        if not getattr(self, '_intel_stopped', False):
            try:
                self.db.finish_work(self._intel_work_id, '已完成')
            except Exception:
                pass

        from threat_intel import generate_threat_intel_report
        self.intel_report_html = generate_threat_intel_report(results, self.db)
        self.intel_report_data = results

        # 自动保存报告文件到磁盘
        report_dir = self._report_dir()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(report_dir, f'threat_intel_report_{ts}.html')
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.intel_report_html)
            self.db.save_report(
                f'全球威胁分析报告 - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'threat_intel', 'html', self.intel_report_html[:500], filepath, None
            )
            self._safe_log('intel_log', f'报告已自动保存至: {filepath}')
        except Exception as e:
            self._safe_log('intel_log', f'报告自动保存失败: {e}')

        # 数据驱动的屏幕摘要（替换旧模板"战略层/运营层/战术层/技术层"）
        self._safe_log('intel_log', '')
        try:
            from intel_pipeline import generate_data_driven_summary
            summary_lines = generate_data_driven_summary(results)
            for line in summary_lines:
                self._safe_log('intel_log', line)
        except Exception:
            # 降级：简单数据输出
            self._safe_log('intel_log', '=' * 50)
            self._safe_log('intel_log', f'  采集完成: {results.get("collection_time", "")}')
            self._safe_log('intel_log', f'  KEV: {results.get("total_kev", 0)} | '
                           f'CVE新增: {results.get("total_cve", 0)} | '
                           f'IOC: {results.get("total_ioc", 0)}')
            self._safe_log('intel_log', '=' * 50)

        self.intel_update_btn.setText('获取全球威胁情报')
        self.intel_update_btn.setEnabled(True)
        self.intel_stop_btn.setEnabled(False)
        self.intel_save_btn.setEnabled(True)
        self.intel_open_btn.setEnabled(True)
        self.intel_ai_report_btn.setEnabled(True)
        self.intel_progress.setVisible(False)
        self._update_dashboard()

        # 自动启动AI综合报告生成
        self._cleanup_intel_report_thread()
        start_date, end_date = getattr(self, 'intel_date_range', ('', ''))
        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '正在启动AI综合威胁情报报告生成（17个章节，预计5-15分钟）...')
        self.intel_ai_report_btn.setEnabled(False)
        self.intel_report_thread = ThreatIntelReportThread(
            results, self.db, self._report_dir(), start_date, end_date
        )
        self.intel_report_thread.progress.connect(
            lambda msg: self._safe_log('intel_log', f'  [AI报告] {msg}')
        )
        self.intel_report_thread.finished.connect(self._on_ai_report_finished)
        self.intel_report_thread.error.connect(self._on_ai_report_error)
        self.intel_report_thread.start()

        QMessageBox.information(self, '收集完毕',
            f'全球威胁情报采集完成！\n\n'
            f'活跃利用漏洞(KEV): {results.get("total_kev", 0)} 条\n'
            f'新增CVE: {results.get("total_cve", 0)} 条 (高危: {results.get("high_critical_cve", 0)})\n'
            f'威胁指标(IOC): {results.get("total_ioc", 0)} 个\n'
            f'威胁行为者: {results.get("total_threat_actors", 0)} 个\n'
            f'数据源: {len(results.get("sources", {}))} 个\n\n'
            f'AI综合报告正在后台生成中（单次全量分析）...')

    def _save_intel_report(self):
        if not hasattr(self, 'intel_report_html'):
            QMessageBox.warning(self, '警告', '没有可保存的威胁情报报告')
            return
        default_path = os.path.join(self._report_dir(), f'threat_intel_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        filepath, _ = QFileDialog.getSaveFileName(
            self, '保存全球威胁分析报告', default_path, self._report_filter())
        if not filepath:
            return
        try:
            from report_converter import save_report_formatted
            ok, actual_path = save_report_formatted(self.intel_report_html, filepath)
            if not ok:
                raise RuntimeError('格式转换失败')
            QMessageBox.information(self, '成功', f'报告已保存至:\n{actual_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _cleanup_intel_report_thread(self):
        """安全终止正在运行的AI报告生成线程"""
        t = getattr(self, 'intel_report_thread', None)
        if t and t.isRunning():
            self._safe_log('intel_log', '正在停止上一个AI报告生成线程...')
            t.requestInterruption()
            t.quit()
            if not t.wait(5000):
                t.terminate()
                t.wait(1000)
            # 断开旧信号连接，防止重复触发
            try:
                t.finished.disconnect(self._on_ai_report_finished)
                t.error.disconnect(self._on_ai_report_error)
            except TypeError:
                pass  # 可能已断开
        self.intel_report_thread = None

    def _start_ai_report_generation(self):
        """手动触发AI综合报告生成"""
        if not hasattr(self, 'intel_report_data'):
            QMessageBox.warning(self, '警告', '请先获取威胁情报数据')
            return

        self._cleanup_intel_report_thread()
        self.intel_ai_report_btn.setEnabled(False)
        self._safe_log('intel_log', '正在启动AI综合威胁情报报告生成（17个章节）...')

        start_date, end_date = getattr(self, 'intel_date_range', ('', ''))
        self.intel_report_thread = ThreatIntelReportThread(
            self.intel_report_data, self.db, self._report_dir(),
            start_date, end_date
        )
        self.intel_report_thread.progress.connect(
            lambda msg: self._safe_log('intel_log', f'  [AI报告] {msg}')
        )
        self.intel_report_thread.finished.connect(self._on_ai_report_finished)
        self.intel_report_thread.error.connect(self._on_ai_report_error)
        self.intel_report_thread.start()

    def _on_ai_report_finished(self, report):
        """AI综合报告生成完成"""
        md_path = report.get('md_path', '')
        html_path = report.get('html_path', '')

        self._safe_log('intel_log', '')
        self._safe_log('intel_log', '=' * 60)
        self._safe_log('intel_log', '  AI综合威胁情报报告生成完成!')
        self._safe_log('intel_log', f'  MarkDown: {md_path}')
        self._safe_log('intel_log', f'  HTML: {html_path}')
        self._safe_log('intel_log', '=' * 60)

        self.ai_intel_report = report
        self.intel_ai_report_btn.setEnabled(True)

        try:
            self.db.save_report(
                f'AI综合威胁情报分析报告 - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'ai_threat_intel', 'html',
                report.get('html_content', '')[:500], html_path, None
            )
        except Exception as e:
            logger.error(f"保存AI报告到数据库失败: {e}")

        QMessageBox.information(self, 'AI报告生成完成',
            f'AI综合威胁情报分析报告已生成！\n\n'
            f'包含17个章节的深度分析\n'
            f'MarkDown: {os.path.basename(md_path)}\n'
            f'HTML: {os.path.basename(html_path)}')

    def _on_ai_report_error(self, error_msg):
        """AI报告生成失败"""
        self._safe_log('intel_log', f'[AI报告] 错误: {error_msg}')
        self.intel_ai_report_btn.setEnabled(True)
        QMessageBox.warning(self, 'AI报告生成失败',
            f'AI综合报告生成过程中出现错误:\n{error_msg[:500]}\n\n'
            f'基础框架报告仍然可用。')

    def _stop_intel(self):
        self._intel_stopped = True
        try:
            self.db.finish_work(self._intel_work_id, '被终止')
        except Exception:
            pass
        self.threat_intel.stop()
        if hasattr(self, 'intel_collect_thread') and self.intel_collect_thread:
            self.intel_collect_thread.requestInterruption()
            if not self.intel_collect_thread.wait(5000):
                self.intel_collect_thread.terminate()
                self.intel_collect_thread.wait(1000)
            self.intel_collect_thread = None
        self.intel_update_btn.setText('获取全球威胁情报')
        self.intel_update_btn.setEnabled(True)
        self.intel_stop_btn.setEnabled(False)
        self.intel_save_btn.setEnabled(False)
        self.intel_open_btn.setEnabled(False)
        self.intel_progress.setVisible(False)

    def _on_intel_error(self, error):
        try:
            self.db.finish_work(self._intel_work_id, '被终止')
        except Exception:
            pass
        self._safe_log('intel_log', f'错误: {error}')
        self.intel_update_btn.setText('获取全球威胁情报')
        self.intel_update_btn.setEnabled(True)
        self.intel_stop_btn.setEnabled(False)
        self.intel_progress.setVisible(False)
        QMessageBox.critical(self, '错误', error)

    def _update_cve_db(self):
        """手动更新漏洞库"""
        self.cve_update_btn.setText('正在搜索漏洞信息......')
        self.cve_update_btn.setEnabled(False)
        self.cve_stop_btn.setEnabled(True)
        self._safe_clear('cve_update_log')
        self.cve_progress_bar.setVisible(True)

        days = self.cve_days_spin.value()
        self.threat_intel._stop_requested = False

        self.current_cve_thread = ThreatIntelThread(self.threat_intel, days=days)
        self._cve_stopped = False
        try:
            self._cve_work_id = self.db.start_work('漏洞库更新')
        except Exception:
            self._cve_work_id = None
        self.current_cve_thread.progress.connect(self._on_cve_update_progress)
        self.current_cve_thread.finished.connect(self._on_cve_update_finished)
        self.current_cve_thread.error.connect(self._on_cve_update_error)
        self.current_cve_thread.start()

    def _on_cve_update_progress(self, msg):
        self._safe_log('cve_update_log', f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    def _on_cve_update_finished(self, count):
        if not getattr(self, '_cve_stopped', False):
            try:
                self.db.finish_work(self._cve_work_id, '已完成')
            except Exception:
                pass
        self._safe_log('cve_update_log', f'更新完成! 新增{count}条CVE')
        self.cve_update_btn.setText('更新漏洞库')
        self.cve_update_btn.setEnabled(True)
        self.cve_stop_btn.setEnabled(False)
        self.cve_progress_bar.setVisible(False)
        self._load_cve_page()
        self._update_dashboard()

    def _on_cve_update_error(self, error):
        try:
            self.db.finish_work(self._cve_work_id, '被终止')
        except Exception:
            pass
        self._safe_log('cve_update_log', f'错误: {error}')
        self.cve_update_btn.setText('更新漏洞库')
        self.cve_update_btn.setEnabled(True)
        self.cve_stop_btn.setEnabled(False)
        self.cve_progress_bar.setVisible(False)

    def _stop_cve_update(self):
        """停止CVE更新搜索"""
        self._cve_stopped = True
        try:
            self.db.finish_work(self._cve_work_id, '被终止')
        except Exception:
            pass
        self.threat_intel.stop()
        if hasattr(self, 'current_cve_thread') and self.current_cve_thread:
            self.current_cve_thread.requestInterruption()
            if not self.current_cve_thread.wait(5000):
                self.current_cve_thread.terminate()
                self.current_cve_thread.wait(1000)
            self.current_cve_thread = None
        self.cve_update_btn.setText('更新漏洞库')
        self.cve_update_btn.setEnabled(True)
        self.cve_stop_btn.setEnabled(False)
        self.cve_progress_bar.setVisible(False)

    def _auto_update_cve(self):
        """每日自动更新CVE漏洞库"""
        try:
            logger.info("开始每日自动更新CVE漏洞库...")
            cves = self.threat_intel.fetch_recent_cve(days=1, limit=100)
            if cves:
                count = self.threat_intel.sync_to_database(cves)
                logger.info(f"自动更新完成: 新增{count}条CVE")
                self.status_bar.showMessage(f'CVE漏洞库已自动更新 +{count}条 | 山西有信网安科技有限公司', 10000)
                self._update_dashboard()
        except Exception as e:
            logger.error(f"自动更新CVE失败: {e}")

    # ============ 报告中心 ============
    def _create_reports_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('报告中心', '管理扫描报告和导出数据'))

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton('刷新列表')
        refresh_btn.clicked.connect(self._refresh_reports)
        btn_layout.addWidget(refresh_btn)

        export_scan_btn = QPushButton('导出最新扫描报告')
        export_scan_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(export_scan_btn)

        export_vulndb_btn = QPushButton('导出漏洞库报告')
        export_vulndb_btn.clicked.connect(self._export_vulndb)
        btn_layout.addWidget(export_vulndb_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.report_table = QTableWidget()
        self.report_table.setColumnCount(7)
        self.report_table.setHorizontalHeaderLabels(['标题', '类型', '格式', '创建时间', '存放位置', '打开', '删除'])
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.report_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.report_table.setColumnWidth(5, 100)
        self.report_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.report_table.setColumnWidth(6, 100)
        layout.addWidget(self.report_table)

        self.tabs.addTab(widget, '报告中心')

    def _refresh_reports(self):
        reports = self.db.get_reports()
        self.report_table.setRowCount(0)
        for r in reports:
            row = self.report_table.rowCount()
            self.report_table.insertRow(row)
            self.report_table.setItem(row, 0, QTableWidgetItem(r.get('title', '')))
            self.report_table.setItem(row, 1, QTableWidgetItem(r.get('type', '')))
            self.report_table.setItem(row, 2, QTableWidgetItem(r.get('format', '')))
            self.report_table.setItem(row, 3, QTableWidgetItem(r.get('created_at', '')[:19] if r.get('created_at') else ''))

            # 存放位置 - 单行显示，超出部分省略
            filepath = r.get('file_path', '') or ''
            path_item = QTableWidgetItem(filepath)
            path_item.setToolTip(filepath)
            path_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.report_table.setItem(row, 4, path_item)

            # 打开报告按钮
            open_btn = QPushButton('打开')
            open_btn.setStyleSheet('font-size: 16px; padding: 2px 10px; background: #e1e1e1; color: #333; border: 1px solid #c0c0c0; border-radius: 4px;')
            report_id = r.get('id')
            open_btn.clicked.connect(lambda checked, fp=filepath, rid=report_id: self._open_report_file(fp, rid))
            self.report_table.setCellWidget(row, 5, open_btn)

            # 删除报告按钮
            del_btn = QPushButton('删除')
            del_btn.setStyleSheet('font-size: 16px; padding: 2px 10px; background: #e1e1e1; color: #d13438; border: 1px solid #d13438; border-radius: 4px;')
            del_btn.clicked.connect(lambda checked, rid=report_id: self._delete_report(rid))
            self.report_table.setCellWidget(row, 6, del_btn)

    def _open_report_file(self, filepath, report_id=None):
        """打开指定报告文件"""
        if filepath and os.path.exists(filepath):
            try:
                os.startfile(filepath)
            except Exception as e:
                QMessageBox.critical(self, '错误', f'打开失败: {str(e)}')
        elif report_id:
            QMessageBox.information(self, '提示', '报告文件已不存在，请重新生成')
        else:
            QMessageBox.warning(self, '警告', '报告文件不存在')

    def _delete_report(self, report_id):
        """删除指定报告"""
        reply = QMessageBox.question(self, '确认删除',
            f'确定要删除报告 #{report_id} 吗？\n此操作不可撤销。',
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_report(report_id)
            self._refresh_reports()

    # ============ 系统设置 ============
    # ============================================================
    # 合规检查（等保 / 关基 / 数据安全）
    # ============================================================
    # 三页共用一套控件与处理函数，用 key 区分；控件存在 self._compliance[key] 里，
    # 日志控件另外 setattr 成实例属性，因为 _safe_log 是按属性名 getattr 取控件的。
    COMPLIANCE_TABS = [
        ('dengbao', '等保合规', '等保合规检查',
         '依据 GB/T 22239-2019 开展等级保护合规自查', True),
        ('cii', '关基合规', '关键信息基础设施合规检查',
         '依据 GB/T 39204-2022 开展关键信息基础设施安全保护要求核查', False),
        ('data_security', '数据安全合规', '数据安全合规检查',
         '依据《数据安全法》《个人信息保护法》与 DSMM 开展数据安全合规核查', False),
        ('mps176', '176号合规', '公安机关网络空间安全监督检查迎检自评',
         '依据《公安机关网络空间安全监督检查办法》(公安部令第176号)开展迎检自评', False),
    ]

    # 四标准合规报告名称（检查完成后自动保存时使用）
    COMPLIANCE_REPORT_NAMES = {
        'dengbao': '等保合规检查报告',
        'cii': '关基合规检查报告',
        'data_security': '数据安全合规检查报告',
        'mps176': '176号监督检查迎检自评报告',
    }

    def _create_compliance_tab(self):
        """合规检查整合为单页，四标准作为二级子页签，避免一级页签过多。"""
        self._compliance_subtabs = QTabWidget()
        for cfg in self.COMPLIANCE_TABS:
            self._build_compliance_tab(*cfg)
        self.tabs.addTab(self._compliance_subtabs, '合规检查')

    def _build_compliance_tab(self, key, tab_title, header, subtitle, with_level):
        if not hasattr(self, '_compliance'):
            self._compliance = {}

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget(header, subtitle))

        card = QGroupBox(f'📋 {header}')
        card_layout = QVBoxLayout(card)

        # ---- 参数行 ----
        param = QHBoxLayout()
        level_combo = None
        if with_level:
            param.addWidget(QLabel('保护等级:'))
            level_combo = QComboBox()
            level_combo.addItems(['L3', 'L2', 'ALL'])
            level_combo.setMaximumWidth(110)
            param.addWidget(level_combo)

        param.addWidget(QLabel('业务系统:'))
        system_input = QLineEdit()
        system_input.setPlaceholderText('留空=默认作用域；组织级条款全局共用')
        system_input.setMaximumWidth(240)
        param.addWidget(system_input)

        param.addWidget(QLabel('技术证据(扫描任务):'))
        scan_combo = QComboBox()
        scan_combo.setMinimumWidth(320)
        param.addWidget(scan_combo)
        refresh_btn = QPushButton('刷新任务')
        refresh_btn.clicked.connect(lambda: self._refresh_compliance_scans(key))
        param.addWidget(refresh_btn)
        param.addStretch()
        card_layout.addLayout(param)

        # ---- AI 开关 ----
        ai_check = QCheckBox('启用 AI 研判（复核填报合理性 + 与扫描事实交叉比对 + 生成整改建议）')
        ai_check.setStyleSheet('font-size: 15px; font-weight: bold; color: #1a237e;')
        ai_check.setChecked(True)
        card_layout.addWidget(ai_check)

        # ---- 按钮行 ----
        btns = QHBoxLayout()
        fill_btn = QPushButton('填报合规问卷')
        fill_btn.clicked.connect(lambda: self._open_compliance_questionnaire(key))
        btns.addWidget(fill_btn)

        start_btn = QPushButton('开始合规检查')
        start_btn.clicked.connect(lambda: self._start_compliance_check(key))
        btns.addWidget(start_btn)

        stop_btn = QPushButton('停止检查')
        stop_btn.setObjectName('stopBtn')
        stop_btn.setEnabled(False)
        stop_btn.clicked.connect(lambda: self._stop_compliance_check(key))
        btns.addWidget(stop_btn)

        save_btn = QPushButton('保存合规报告')
        save_btn.setObjectName('saveBtn')
        save_btn.setEnabled(False)
        save_btn.clicked.connect(lambda: self._save_compliance_report(key))
        btns.addWidget(save_btn)
        btns.addStretch()
        card_layout.addLayout(btns)

        progress = QProgressBar()
        progress.setVisible(False)
        card_layout.addWidget(progress)

        summary = QLabel('尚未执行检查')
        summary.setStyleSheet('font-size: 15px; font-weight: bold; color: #283593; padding: 6px;')
        summary.setWordWrap(True)
        card_layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            ['条款', '安全层面', '条款标题', '判定', '判定来源', 'AI研判', '权重', '判定依据 / 整改建议'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        card_layout.addWidget(table)

        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setMaximumHeight(120)
        card_layout.addWidget(log)
        setattr(self, f'compliance_log_{key}', log)

        layout.addWidget(card)
        self._compliance_subtabs.addTab(widget, tab_title)

        self._compliance[key] = {
            'standard': key, 'title': header, 'work_type': tab_title,
            'level_combo': level_combo, 'system_input': system_input,
            'scan_combo': scan_combo, 'ai_check': ai_check,
            'start_btn': start_btn, 'stop_btn': stop_btn, 'save_btn': save_btn,
            'progress': progress, 'summary': summary, 'table': table,
            'log_target': f'compliance_log_{key}',
            'thread': None, 'suggest_thread': None, 'result': None, 'work_id': None,
        }
        self._refresh_compliance_scans(key)

    # ---- 辅助 ----
    def _compliance_level(self, key):
        combo = self._compliance[key]['level_combo']
        return combo.currentText() if combo is not None else 'ALL'

    def _refresh_compliance_scans(self, key):
        """把最近的扫描任务填进下拉框，供选作技术证据"""
        combo = self._compliance[key]['scan_combo']
        combo.clear()
        combo.addItem('（不使用扫描证据 — 技术类条款将判为证据不足）', None)
        try:
            for task in self.db.scan.get_all_tasks(limit=50):
                t = dict(task)
                combo.addItem(
                    f"#{t['id']} {t.get('target', '')} [{t.get('status', '')}] {(t.get('start_time') or '')[:16]}",
                    t['id'])
        except Exception as e:
            logger.error(f'加载扫描任务失败: {e}')
            self._safe_log(self._compliance[key]['log_target'], f'⚠ 加载扫描任务失败: {e}')

    def _open_compliance_questionnaire(self, key):
        from compliance_dialog import ComplianceQuestionnaireDialog
        cfg = self._compliance[key]
        try:
            dlg = ComplianceQuestionnaireDialog(
                cfg['standard'], self.db, self._compliance_level(key),
                cfg['system_input'].text().strip(), self)
        except FileNotFoundError as e:
            QMessageBox.critical(self, '错误', f'合规条款目录缺失：{e}')
            return
        dlg.ai_suggest_requested.connect(
            lambda controls, k=key, d=dlg: self._start_compliance_ai_suggest(k, d, controls))
        dlg.exec_()
        self._safe_log(cfg['log_target'], '问卷填报窗口已关闭')

    def _start_compliance_ai_suggest(self, key, dialog, controls):
        cfg = self._compliance[key]
        scan_id = cfg['scan_combo'].currentData()
        th = ComplianceAISuggestThread(controls, self.db, scan_id,
                                       cfg['standard'], self._compliance_level(key))
        cfg['suggest_thread'] = th
        # 捕获 th：线程被换掉后旧线程的信号不得再回写界面
        th.progress.connect(lambda msg, t=cfg['log_target']: self._safe_log(t, msg))
        th.finished.connect(
            lambda res, d=dialog, k=key, t=th:
            d.apply_suggestions(res) if self._compliance[k]['suggest_thread'] is t else None)
        th.error.connect(
            lambda err, d=dialog, k=key, t=th:
            (d.apply_suggestions(None), QMessageBox.warning(self, 'AI 建议失败', err))
            if self._compliance[k]['suggest_thread'] is t else None)
        th.start()

    # ---- 执行检查 ----
    def _start_compliance_check(self, key):
        cfg = self._compliance[key]
        if cfg['thread'] is not None and cfg['thread'].isRunning():
            QMessageBox.information(self, '提示', '本页的合规检查正在进行中。')
            return

        cfg['start_btn'].setEnabled(False)
        cfg['stop_btn'].setEnabled(True)
        cfg['save_btn'].setEnabled(False)
        cfg['progress'].setRange(0, 0)
        cfg['progress'].setVisible(True)
        cfg['summary'].setText('检查进行中...')
        cfg['table'].setRowCount(0)
        self._safe_clear(cfg['log_target'])

        try:
            cfg['work_id'] = self.db.start_work(cfg['work_type'])
        except Exception as e:
            cfg['work_id'] = None
            logger.error(f'记录合规工作开始失败: {e}')

        th = ComplianceCheckThread(
            self.db, cfg['standard'], self._compliance_level(key),
            cfg['system_input'].text().strip(), cfg['scan_combo'].currentData(),
            '', cfg['ai_check'].isChecked())
        cfg['thread'] = th
        th.progress.connect(lambda msg, t=cfg['log_target']: self._safe_log(t, msg))
        th.finished.connect(
            lambda agg, k=key, t=th:
            self._on_compliance_finished(k, agg) if self._compliance[k]['thread'] is t else None)
        th.error.connect(
            lambda err, k=key, t=th:
            self._on_compliance_error(k, err) if self._compliance[k]['thread'] is t else None)
        th.start()

    def _stop_compliance_check(self, key):
        cfg = self._compliance[key]
        th = cfg['thread']
        if th is not None and th.isRunning():
            th.stop()
            self._safe_log(cfg['log_target'], '正在停止合规检查...')
        self._finish_compliance_work(key, '被终止')
        self._reset_compliance_buttons(key)
        cfg['summary'].setText('检查已被用户终止')

    def _reset_compliance_buttons(self, key):
        cfg = self._compliance[key]
        cfg['start_btn'].setEnabled(True)
        cfg['stop_btn'].setEnabled(False)
        cfg['progress'].setVisible(False)
        cfg['progress'].setRange(0, 100)

    def _finish_compliance_work(self, key, status):
        cfg = self._compliance[key]
        if cfg.get('work_id'):
            try:
                self.db.finish_work(cfg['work_id'], status)
            except Exception as e:
                logger.error(f'更新合规工作状态失败: {e}')
            cfg['work_id'] = None

    def _on_compliance_error(self, key, err):
        self._finish_compliance_work(key, '被终止')
        self._reset_compliance_buttons(key)
        self._compliance[key]['summary'].setText(f'检查失败：{err}')
        QMessageBox.critical(self, '合规检查失败', err)

    def _on_compliance_finished(self, key, agg):
        cfg = self._compliance[key]
        cfg['result'] = agg
        self._finish_compliance_work(key, '已完成')
        self._reset_compliance_buttons(key)
        cfg['save_btn'].setEnabled(True)
        # 检查完成后自动保存报告，登记到报告中心并刷新列表
        self._auto_save_compliance_report(key, agg)

        counts = agg.get('counts', {})
        rate = agg.get('compliance_rate')
        rate_text = '—' if rate is None else f'{rate * 100:.1f}%'
        ai_note = '' if agg.get('ai_ran') else '（本次未执行 AI 研判）'
        cfg['summary'].setText(
            f"合规率 {rate_text}　得分 {agg.get('score') if agg.get('score') is not None else '—'}　|　"
            f"条款 {counts.get('total', 0)} ："
            f"符合 {counts.get('符合', 0)} / 部分符合 {counts.get('部分符合', 0)} / "
            f"不符合 {counts.get('不符合', 0)} / 证据不足 {counts.get('证据不足', 0)} / "
            f"未填报 {counts.get('未填报', 0)}　|　"
            f"自动判定占比 {(agg.get('auto_ratio') or 0) * 100:.1f}% {ai_note}")

        self._populate_compliance_table(key, agg.get('results', []))
        self._safe_log(cfg['log_target'], f"检查完成，结果已保存（历史ID {agg.get('history_id')}）")
        self._update_dashboard()

    def _populate_compliance_table(self, key, results):
        """填充条款明细表。AI 判『矛盾』整行标红、『存疑』标橙，让问题一眼可见。"""
        from compliance_report import STATUS_COLORS, SOURCE_LABELS

        table = self._compliance[key]['table']
        order = {'不符合': 0, '证据不足': 1, '部分符合': 2, '未填报': 3, '符合': 4, '不适用': 5}
        rows = sorted(results, key=lambda x: (order.get(x.get('status'), 9),
                                              -float(x.get('_weight', 1.0) or 1.0)))
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            status = r.get('status', '')
            ai_status = r.get('ai_status', '') or ''
            detail = r.get('detail', '') or ''
            if r.get('recommendation'):
                detail = f"{detail}\n整改：{r['recommendation']}"

            values = [
                r.get('control_id', ''),
                f"{r.get('domain', '')} / {r.get('category', '')}",
                r.get('title', ''),
                status,
                SOURCE_LABELS.get(r.get('verdict_source', ''), r.get('verdict_source', '') or '—'),
                ai_status if ai_status and ai_status != '未运行' else '—',
                str(r.get('_weight', 1.0)),
                detail,
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col == 3:
                    item.setForeground(QColor(STATUS_COLORS.get(status, '#212121')))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if col == 7:
                    item.setToolTip(str(val))
                table.setItem(i, col, item)

            # AI 研判异常时整行着色
            if ai_status == '矛盾':
                bg = QColor('#ffcdd2')
            elif ai_status == '存疑':
                bg = QColor('#ffe0b2')
            elif status == '不符合':
                bg = QColor('#fff1f0')
            else:
                bg = None
            if bg is not None:
                for col in range(table.columnCount()):
                    cell = table.item(i, col)
                    if cell is not None:
                        cell.setBackground(bg)

            ai_cell = table.item(i, 5)
            if ai_cell is not None and r.get('ai_reasoning'):
                ai_cell.setToolTip(r['ai_reasoning'])
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)

    def _save_compliance_report(self, key):
        cfg = self._compliance[key]
        if not cfg.get('result'):
            QMessageBox.information(self, '提示', '请先执行一次合规检查。')
            return
        from compliance_report import generate_compliance_report
        try:
            path = generate_compliance_report(cfg['result'], self._report_dir())
        except Exception as e:
            logger.error(f'生成合规报告失败: {e}')
            QMessageBox.critical(self, '生成失败', str(e))
            return
        self._safe_log(cfg['log_target'], f'合规报告已保存: {path}')
        QMessageBox.information(self, '保存成功', f'合规报告已保存至：\n{path}')

    def _auto_save_compliance_report(self, key, agg):
        """合规检查完成后自动保存报告并登记到报告中心。"""
        cfg = self._compliance[key]
        name = self.COMPLIANCE_REPORT_NAMES.get(key, f'{key}合规检查报告')
        try:
            from compliance_report import generate_compliance_report
            path = generate_compliance_report(
                agg, self._report_dir(), title=name, filename_prefix=name)
            summary = self._compliance_report_summary(agg)
            self.db.save_report(name, 'compliance', 'html', summary, path)
            self._safe_log(cfg['log_target'], f'合规报告已自动保存: {path}')
            if hasattr(self, 'report_table'):
                self._refresh_reports()
            return path
        except Exception as e:
            logger.warning(f'合规报告自动保存失败: {e}')
            self._safe_log(cfg['log_target'], f'⚠ 合规报告自动保存失败: {e}')
            return None

    @staticmethod
    def _compliance_report_summary(agg):
        """生成合规报告摘要（用于报告中心展示）。"""
        counts = agg.get('counts', {})
        rate = agg.get('compliance_rate')
        rate_text = '—' if rate is None else f'{rate * 100:.1f}%'
        return (f"合规率 {rate_text}，条款 {counts.get('total', 0)}："
                f"符合 {counts.get('符合', 0)} / 不符合 {counts.get('不符合', 0)} / "
                f"证据不足 {counts.get('证据不足', 0)}")

    def _create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._create_header_widget('系统设置', '配置系统参数'))

        # 扫描设置
        scan_group = QGroupBox('扫描设置')
        scan_layout = QFormLayout()
        self.setting_timeout = QSpinBox()
        self.setting_timeout.setRange(1, 30)
        self.setting_timeout.setValue(int(self.db.get_setting('scan_timeout', '5')))
        self.setting_timeout.setSuffix(' 秒')
        scan_layout.addRow('默认超时:', self.setting_timeout)
        self.setting_concurrent = QSpinBox()
        self.setting_concurrent.setRange(1, 50)
        self.setting_concurrent.setValue(int(self.db.get_setting('scan_concurrent', '10')))
        scan_layout.addRow('并发扫描:', self.setting_concurrent)
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        # CVE设置
        cve_group = QGroupBox('漏洞库设置')
        cve_layout = QFormLayout()
        self.setting_auto_update = QCheckBox('自动更新CVE数据')
        self.setting_auto_update.setChecked(self.db.get_setting('auto_update_cve', 'true') == 'true')
        cve_layout.addRow(self.setting_auto_update)
        self.setting_retention = QSpinBox()
        self.setting_retention.setRange(30, 365)
        self.setting_retention.setValue(int(self.db.get_setting('report_retention_days', '90')))
        self.setting_retention.setSuffix(' 天')
        cve_layout.addRow('报告保留天数:', self.setting_retention)
        cve_group.setLayout(cve_layout)
        layout.addWidget(cve_group)

        # API配置
        api_group = QGroupBox('API配置')
        api_layout = QFormLayout()

        # 提示文字
        api_hint = QLabel('<span style="color:#107c10;font-size:22px;">AI能力默认通过本机Claude Code加持，无需配置API Key。如需使用远程API，可在此配置（可选）</span>')
        api_hint.setStyleSheet('padding: 5px 0;')
        api_layout.addRow(api_hint)

        self.setting_claude_key = QLineEdit()
        self.setting_claude_key.setPlaceholderText('可选：输入API Key作为回退方案（留空使用本机Claude Code）...')
        self.setting_claude_key.setEchoMode(QLineEdit.Password)
        self.setting_claude_key.setText(self.db.get_setting('claude_api_key', ''))
        api_layout.addRow('Claude Code API Key:', self.setting_claude_key)

        self.setting_nvd_key = QLineEdit()
        self.setting_nvd_key.setPlaceholderText('输入NVD API Key...')
        self.setting_nvd_key.setText(self.db.get_setting('nvd_api_key', ''))
        api_layout.addRow('NVD API Key:', self.setting_nvd_key)

        # 显示/隐藏切换
        show_keys_cb = QCheckBox('显示API Key')
        show_keys_cb.toggled.connect(lambda checked: (
            self.setting_claude_key.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password),
            self.setting_nvd_key.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        ))
        api_layout.addRow(show_keys_cb)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # 文档设置
        doc_group = QGroupBox('文档设置')
        doc_layout = QFormLayout()

        path_row = QHBoxLayout()
        self.setting_report_path = QLineEdit()
        self.setting_report_path.setText(self.db.get_setting('report_path', os.path.join(PROJECT_DIR, 'reports')))
        self.setting_report_path.setPlaceholderText('报告文件存储目录...')
        path_row.addWidget(self.setting_report_path)
        browse_path_btn = QPushButton('浏览...')
        browse_path_btn.clicked.connect(lambda: (
            lambda p: self.setting_report_path.setText(p) if p else None
        )(QFileDialog.getExistingDirectory(self, '选择报告存储目录')))
        path_row.addWidget(browse_path_btn)
        doc_layout.addRow('报告文件存储位置:', path_row)

        format_row = QHBoxLayout()
        self.setting_fmt_html = QCheckBox('HTML')
        self.setting_fmt_html.setChecked(self.db.get_setting('report_fmt_html', 'true') == 'true')
        format_row.addWidget(self.setting_fmt_html)
        self.setting_fmt_pdf = QCheckBox('PDF')
        self.setting_fmt_pdf.setChecked(self.db.get_setting('report_fmt_pdf', 'false') == 'true')
        format_row.addWidget(self.setting_fmt_pdf)
        self.setting_fmt_word = QCheckBox('Word')
        self.setting_fmt_word.setChecked(self.db.get_setting('report_fmt_word', 'false') == 'true')
        format_row.addWidget(self.setting_fmt_word)
        self.setting_fmt_md = QCheckBox('MarkDown')
        self.setting_fmt_md.setChecked(self.db.get_setting('report_fmt_md', 'false') == 'true')
        format_row.addWidget(self.setting_fmt_md)
        format_row.addStretch()
        doc_layout.addRow('报告文件格式:', format_row)

        doc_group.setLayout(doc_layout)
        layout.addWidget(doc_group)

        save_btn = QPushButton('保存设置')
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        # 版权信息
        info_frame = QFrame()
        info_frame.setStyleSheet('background: #f8f9fa; border-radius: 8px; padding: 15px;')
        info_layout = QVBoxLayout(info_frame)
        info_layout.setAlignment(Qt.AlignCenter)

        # LOGO + 公司名同行居中
        logo_row = QHBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)
        logo_label = QLabel()
        logo_path = _get_logo_path()
        if logo_path:
            pixmap = QPixmap(logo_path).scaled(160, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = _make_white_transparent(pixmap)
            logo_label.setPixmap(pixmap)
            logo_label.setStyleSheet('background: transparent;')
        logo_row.addWidget(logo_label)
        company_label = QLabel("<b style='font-size:22px;color:#1a73e8;'>© 2026 山西有信网安科技有限公司</b>")
        company_label.setAlignment(Qt.AlignCenter)
        logo_row.addWidget(company_label)
        info_layout.addLayout(logo_row)

        # 其他信息居中
        info_layout.addWidget(QLabel('<span style="color:#666;font-size:20px;"><b>下一代智能漏洞扫描系统 Pro v1.0</b></span>'))
        info_layout.itemAt(info_layout.count() - 1).widget().setAlignment(Qt.AlignCenter)
        info_layout.addWidget(QLabel('<span style="color:#999;font-size:20px;"><b>&copy; 2026 AI Vuln Scanner. All rights reserved.</b></span>'))
        info_layout.itemAt(info_layout.count() - 1).widget().setAlignment(Qt.AlignCenter)
        info_layout.addWidget(QLabel('<span style="color:#999;font-size:20px;"><b>技术支持: 山西有信网安科技有限公司</b></span>'))
        info_layout.itemAt(info_layout.count() - 1).widget().setAlignment(Qt.AlignCenter)
        layout.addWidget(info_frame)
        layout.addStretch()

        self.tabs.addTab(widget, '系统设置')

    def _save_settings(self):
        self.db.set_setting('scan_timeout', str(self.setting_timeout.value()))
        self.db.set_setting('scan_concurrent', str(self.setting_concurrent.value()))
        self.db.set_setting('auto_update_cve', 'true' if self.setting_auto_update.isChecked() else 'false')
        self.db.set_setting('report_retention_days', str(self.setting_retention.value()))
        self.db.set_setting('claude_api_key', self.setting_claude_key.text().strip())
        self.db.set_setting('nvd_api_key', self.setting_nvd_key.text().strip())
        self.db.set_setting('report_path', self.setting_report_path.text().strip())
        self.db.set_setting('report_fmt_html', 'true' if self.setting_fmt_html.isChecked() else 'false')
        self.db.set_setting('report_fmt_pdf', 'true' if self.setting_fmt_pdf.isChecked() else 'false')
        self.db.set_setting('report_fmt_word', 'true' if self.setting_fmt_word.isChecked() else 'false')
        self.db.set_setting('report_fmt_md', 'true' if self.setting_fmt_md.isChecked() else 'false')

        # 同步到 threat_intel 模块的 NVD API Key
        import threat_intel
        threat_intel.NVD_API_KEY = self.setting_nvd_key.text().strip()
        if threat_intel.NVD_API_KEY:
            # 重建 collector headers
            if hasattr(self, 'threat_intel') and self.threat_intel:
                self.threat_intel.headers = {'apiKey': threat_intel.NVD_API_KEY}

        self.status_bar.showMessage('设置已保存 | 山西有信网安科技有限公司', 3000)
        QMessageBox.information(self, '成功', '设置已保存')

    # ============ 报告操作 ============
    def _generate_scan_html(self, scan_result):
        """生成扫描HTML报告"""
        from report_generator import _generate_html_report
        return _generate_html_report(scan_result)

    def _generate_scan_text(self, scan_result):
        from report_generator import _generate_text_report
        return _generate_text_report(scan_result)

    def _report_dir(self):
        """获取配置的报告存储目录"""
        d = self.db.get_setting('report_path', '') or os.path.join(PROJECT_DIR, 'reports')
        os.makedirs(d, exist_ok=True)
        return d

    def _report_filter(self):
        """根据设置生成文件格式过滤器"""
        fmts = []
        if self.db.get_setting('report_fmt_html', 'true') == 'true':
            fmts.append('HTML报告 (*.html)')
        if self.db.get_setting('report_fmt_pdf', 'false') == 'true':
            fmts.append('PDF报告 (*.pdf)')
        if self.db.get_setting('report_fmt_word', 'false') == 'true':
            fmts.append('Word文档 (*.docx)')
        if self.db.get_setting('report_fmt_md', 'false') == 'true':
            fmts.append('MarkDown (*.md)')
        if not fmts:
            fmts.append('HTML报告 (*.html)')
        return ';;'.join(fmts)

    def _save_report(self):
        if not self.last_scan_result:
            QMessageBox.warning(self, '警告', '没有可保存的扫描结果，请先执行扫描')
            return
        default_path = os.path.join(self._report_dir(), f'scan_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        filepath, _ = QFileDialog.getSaveFileName(
            self, '保存报告', default_path, self._report_filter())
        if not filepath:
            return
        try:
            from report_converter import save_report_formatted
            html_content = self._generate_scan_html(self.last_scan_result)
            ok, actual_path = save_report_formatted(html_content, filepath)
            if not ok:
                raise RuntimeError('格式转换失败')
            title = f'扫描报告 - {self.last_scan_result.get("target", "未知")}'
            fmt = os.path.splitext(actual_path)[1].lstrip('.')
            self.db.save_report(title, 'scan', fmt, html_content[:500], actual_path)
            QMessageBox.information(self, '成功', f'报告已保存至:\n{actual_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _open_report(self):
        filepath, _ = QFileDialog.getOpenFileName(self, '打开报告', self._report_dir(),
            self._report_filter() + ';;所有文件 (*)')
        if filepath:
            try:
                os.startfile(filepath)
            except Exception as e:
                QMessageBox.critical(self, '错误', f'打开失败: {str(e)}')

    def _save_ai_report(self):
        """保存AI安全分析报告 (Claude Code Security)"""
        if not self.last_scan_result or not self.last_ai_analysis:
            QMessageBox.warning(self, '警告', '没有AI分析结果，请先执行扫描')
            return
        default_path = os.path.join(self._report_dir(), f'ai_security_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        filepath, _ = QFileDialog.getSaveFileName(
            self, '保存AI安全分析报告', default_path, self._report_filter())
        if not filepath:
            return
        try:
            from report_converter import save_report_formatted
            html_content = self.ai_security.generate_ai_report_html(
                self.last_scan_result, self.last_ai_analysis)
            ok, actual_path = save_report_formatted(html_content, filepath)
            if not ok:
                raise RuntimeError('格式转换失败')
            target = self.last_scan_result.get('target', 'unknown')
            title = f'AI安全分析 - {target}'
            summary = self.last_ai_analysis.get('executive_summary', '')[:500]
            fmt = os.path.splitext(actual_path)[1].lstrip('.')
            self.db.save_report(title, 'ai_security', fmt, summary, actual_path)
            QMessageBox.information(self, '成功', f'AI安全分析报告已保存至:\n{actual_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _save_ecc_report(self):
        """保存ECC加密安全检测报告 (Claude Code ECC)"""
        if not self.last_ecc_result:
            QMessageBox.warning(self, '警告', '没有ECC检测结果，请先执行扫描')
            return
        default_path = os.path.join(self._report_dir(), f'ecc_security_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        filepath, _ = QFileDialog.getSaveFileName(
            self, '保存ECC安全检测报告', default_path, self._report_filter())
        if not filepath:
            return
        try:
            from report_converter import save_report_formatted
            html_content = self.ecc_checker.generate_ecc_report(self.last_ecc_result)
            ok, actual_path = save_report_formatted(html_content, filepath)
            if not ok:
                raise RuntimeError('格式转换失败')
            target = self.last_ecc_result.get('host', 'unknown')
            title = f'ECC安全检测 - {target}'
            summary = f'发现{self.last_ecc_result.get("total_findings", 0)}个加密安全问题'
            fmt = os.path.splitext(actual_path)[1].lstrip('.')
            self.db.save_report(title, 'ecc_security', fmt, summary, actual_path)
            QMessageBox.information(self, '成功', f'ECC安全检测报告已保存至:\n{actual_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _export_report(self):
        if not self.last_scan_result:
            tasks = self.db.get_all_tasks(1)
            if not tasks:
                QMessageBox.warning(self, '警告', '没有扫描记录')
                return
            task = tasks[0]
            results = self.db.get_task_results(task['id'])
            if not results:
                QMessageBox.warning(self, '警告', '没有扫描结果')
                return
            scan_data = {
                'target': task['target'],
                'start_time': task.get('start_time', ''),
                'end_time': task.get('end_time', ''),
                'duration': 0,
                'vulnerabilities': results,
                'scan_result': {'hosts': []},
                'summary': {'total': len(results), 'by_severity': {}, 'high_critical': 0}
            }
        else:
            scan_data = self.last_scan_result

        from report_generator import generate_scan_report
        output_dir = 'reports'
        output_files = generate_scan_report(scan_data, output_dir, ['html'])
        result_text = '\n'.join([f'{k}: {v}' for k, v in output_files.items()])
        QMessageBox.information(self, '成功', f'报告已导出:\n{result_text}')

    def _export_vulndb(self):
        from report_generator import export_vuln_database
        default_path = os.path.join(self._report_dir(), f'vuln_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        filepath, _ = QFileDialog.getSaveFileName(self, '导出漏洞库', default_path, self._report_filter())
        if not filepath:
            return
        try:
            export_vuln_database(self.db, filepath)
            QMessageBox.information(self, '成功', f'漏洞库已导出至:\n{filepath}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出失败: {str(e)}')

    # ============ 工具操作 ============
    def _clear_database(self):
        reply = QMessageBox.question(self, '确认', '确定要清空所有数据吗？此操作不可恢复！', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db.clear_database()
                self._update_dashboard()
                QMessageBox.information(self, '完成', '所有数据库已清空')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'清空失败: {str(e)}')

    def _open_deliverable_doc(self, filename):
        """打开交付文档（帮助菜单 → 交付文档）"""
        path = os.path.join(_docs_dir(), filename)
        if not os.path.isfile(path):
            QMessageBox.warning(self, '未找到文档', f'文档文件不存在:\n{path}')
            return
        try:
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'打开失败: {str(e)}')

    def _show_about(self):
        QMessageBox.about(self, '关于 AI漏洞扫描系统',
                          '<h2>下一代智能漏洞扫描系统 Pro v1.0</h2>'
                          '<p><b>山西有信网安科技有限公司</b></p>'
                          '<p>下一代智能漏洞扫描系统</p>'
                          '<hr>'
                          '<p><b>功能模块:</b></p>'
                          '<ul>'
                          '<li>仪表盘 - 系统运行概览</li>'
                          '<li>资产管理 - 网络资产发现与管理</li>'
                          '<li>漏洞扫描 - 多类型资产漏洞检测</li>'
                          '<li>漏洞库 - CVE漏洞数据库管理</li>'
                          '<li>AI代码审计 - 源码安全分析</li>'
                          '<li>威胁情报 - NVD实时情报</li>'
                          '<li>报告中心 - 多格式报告生成</li>'
                          '</ul>'
                          '<hr>'
                          '<p>&copy; 2026 山西有信网安科技有限公司</p>'
                          '<p>All rights reserved.</p>')

    def _update_status_bar(self):
        stats = self.db.get_statistics()
        self.status_bar.showMessage(
            f'就绪 | CVE: {stats["total_cves"]}条 | 资产: {stats["total_assets"]}个 | '
            f'任务: {stats["total_tasks"]}个 | 山西有信网安科技有限公司'
        )


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
