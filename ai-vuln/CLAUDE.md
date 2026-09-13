# AI-VULN Development Guide

## Project Identity

**Name:** 下一代智能漏洞扫描系统 Pro (Next-Generation Intelligent Vulnerability Scanning System)
**Organization:** 山西有信网安科技有限公司
**Version:** 2.1.0
**Stack:** Python 3 + PyQt5 + FastAPI + SQLite + Claude AI

## Reference Documents

| 文档 | 编号 / 版本 | 用途 |
|------|-----------|------|
| 漏洞扫描系统需求规格说明书 | VSS-SRS-2026-001 V1.1 | 功能需求依据（FR-01 ~ FR-17） |
| 软件架构设计说明书 | V1.0 | 架构设计依据 |
| 研发需求差距分析与开发计划 | VSS-GAP-2026-002 V2.0 | 差距分析与分阶段开发计划 |

## Architecture at a Glance

```
main.py → main_window.py (8-tab GUI, 4044 lines)
  ├── scanner_engine.py    # NetworkScanner + VulnScanner (Nmap/Socket dual-engine)
  ├── device_fingerprint.py # Multi-type device detection: net-dev/sec-dev/IoT/OT/国产化 (FR-11)
  ├── ai_analyzer.py        # Code security static analysis (10 categories, 40+ regex)
  ├── ai_verifier.py        # AI false-positive elimination (Claude-powered)
  ├── ai_scan_enhancer.py   # 3-phase scan verification (pre-filter → AI verify → analyze)
  ├── ai_client.py          # Claude Code CLI subprocess wrapper
  ├── ai_security.py        # Post-scan risk scoring & analysis
  ├── ecc_security.py       # Cryptographic/TLS security checker (8 ECC rules)
  ├── threat_intel.py       # VulnMatcher + ThreatIntelCollector (facade)
  ├── intel_pipeline.py     # 3-phase: local API (parallel) → OSINT (serial) → AI analysis
  ├── intel_sources.py      # 13 data source classes (6 local + 7 web OSINT)
  ├── threat_intel_reporter.py # 17-section AI-enhanced threat intel report
  ├── database.py           # 5 SQLite DBs + unified Database facade (1187 lines)
  ├── report_generator.py   # HTML/TXT scan & audit reports
  ├── report_converter.py   # HTML→PDF/Word/MD converters
  ├── vuln_db_manager.py    # Standalone CVE DB manager GUI
  ├── cve_db_repair.py      # CVE DB maintenance CLI
  ├── api/                  # FastAPI REST layer
  │   ├── server.py         # App factory
  │   ├── routers/          # 7 route modules (assets, scans, cve, intel, audit, reports, dashboard)
  │   ├── models/           # Pydantic schemas
  │   ├── auth.py           # API key auth
  │   └── dependencies.py   # DI helpers
  ├── db/                   # PostgreSQL migration (optional)
  ├── tests/                # Pytest test suite
  ├── constants.py          # SEV_COLORS shared constant
  └── config.py             # Env-driven config (SQLite/PG dual backend)
```

## Five-Database Architecture

| DB File | Class | Key Tables | Purpose |
|---------|-------|-----------|---------|
| `scan_results.db` | `ScanResultsDB` | `scan_tasks`, `scan_results` | Scan history & results |
| `cve_database.db` | `CVEDatabase` | `cve_database`, `vendor_advisories`, `cvss_distribution` | CVE knowledge base |
| `threat_intel.db` | `ThreatIntelDB` | `cisa_kev`, `epss_scores`, `threat_actors`, `iocs`, `attack_patterns`, `threat_feeds`, `weak_passwords` | Threat intelligence |
| `audit_results.db` | `AuditResultsDB` | `audit_history`, `audit_issues` | Code audit history |
| `assets_system.db` | `AssetsSystemDB` | `assets`, `scan_policies`, `reports`, `system_settings`, `audit_logs` | Assets & system config |

**DB connection pattern:**
```python
def _connect(db_name):
    path = os.path.join(BASE_DIR, db_name)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA temp_store=2")       # temp in memory
    conn.execute("PRAGMA wal_autocheckpoint=1000")  # merge at ~1MB
    return conn
```
- WAL mode for concurrent read/write
- `check_same_thread=False` required because DB accessed from multiple threads
- Temp files redirected to `./temp/` to avoid C-drive disk-full
- Timestamps use SQLite `datetime('now','localtime')`
- **Unified facade**: `Database` class delegates to all 5 sub-DBs via convenience methods

## Coding Conventions

### File Header
```python
# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - <module description>"""
```

### Imports order (strict)
1. stdlib: `sys`, `os`, `re`, `logging`, `threading`, `datetime`
2. typing: `List`, `Dict`, `Optional`, `Any`, `Callable`, `Tuple`
3. third-party: `PyQt5.*`, `requests`, `nmap`, `weasyprint`, `docx`
4. local: `from constants import SEV_COLORS`, `from ai_client import AIClient`

### Logging pattern (every module)
```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

### Naming conventions
- Classes: `PascalCase` — `VulnScanner`, `AIScanEnhancer`, `NetworkScanner`
- Functions/methods: `snake_case` — `_check_host_alive()`, `_parse_port_string()`
- Threads: `*Thread(QThread)` — `ScanThread`, `AIEnhanceThread`
- Constants: `UPPER_SNAKE_CASE` — `DEFAULT_PORT_LIST`, `COMMON_PORTS`
- Private module attrs: `_` prefix — `_APP_TEMP_DIR`, `_connect()`

### Class documentation (Chinese)
```python
class ClassName:
    """中文类描述"""

    def method(self):
        """中文方法描述"""
        pass
```

## Core Patterns (CRITICAL — follow these exactly)

### 1. Thread-Safe GUI Logging
```python
# NEVER call widget methods from worker threads.
# ALWAYS use the message buffer pattern (main_window.py):
self._msg_buffer = []
self._msg_lock = threading.Lock()

def _safe_log(self, target: str, text: str):
    """target = 'scan_log' | 'audit_log' | 'intel_log'"""
    with self._msg_lock:
        self._msg_buffer.append((target, text))

# Buffer flushed to QPlainTextEdit by QTimer every 100ms
```

### 2. AI Client Pattern
```python
from ai_client import AIClient, is_ai_available, strip_markdown_fences

client = AIClient()  # Uses local Claude Code CLI (no API key needed)
# Fallback: AIClient(api_key="sk-ant-...")

result = client.query(
    "user prompt",
    system_prompt="You are a security expert...",
    max_turns=1,     # >1 enables tool use (web search)
    timeout=300      # seconds, default 300
)
clean = strip_markdown_fences(result)  # Always strip ```json fences
```

### 3. Worker Thread Pattern
```python
class MyWorkerThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, ...):
        super().__init__()
        # store params as instance attrs

    def run(self):
        try:
            self.progress.emit("Starting...")
            result = do_heavy_work()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

# Wiring in MainWindow:
self.thread = MyWorkerThread(...)
self.thread.progress.connect(lambda msg: self._safe_log('log_widget', msg))
self.thread.finished.connect(self._on_finished)
self.thread.error.connect(lambda e: QMessageBox.critical(self, '错误', e))
self.thread.start()
```

### 4. Scan → AI Verify → Analyze Pipeline
```python
# Phase 1: Network scan
result = vuln_scanner.scan_target(target, ports, scan_type)

# Phase 2: AI verification (user-toggleable checkbox)
if ai_enabled:
    enhancer = AIScanEnhancer()
    verify_result = enhancer.verify_vulnerabilities(
        result['vulnerabilities'],
        scan_context=f"Target: {target}",
        progress_callback=callback
    )

# Phase 3: AI risk analysis
analysis = enhancer.generate_ai_analysis(enhanced_scan)
```

### 5. AI Verification Rules
- **Code audit**: `AIVerifier` — context is ±5 lines around match, confidence threshold ≥ 0.6
- **Scan CVE verify**: `AIScanEnhancer` — 3 phases: version pre-filter → batch AI verify (4/batch, 3 concurrent) → AI risk analysis
- **Conservative on failure**: If AI call fails or can't parse response → keep the finding (never drop real vulns)
- **Version pre-filter**: Fast rule-based exclusion before AI call — saves cost, catches ~20-30% of false matches

## Module Change Impact Map

| If modifying... | Must also check... |
|----------------|-------------------|
| `database.py` | All `*Thread` in `main_window.py`, `vuln_db_manager.py`, `cve_db_repair.py` |
| `ai_client.py` | `ai_verifier.py`, `ai_scan_enhancer.py`, `intel_pipeline.py`, `threat_intel_reporter.py` |
| `scanner_engine.py` | `main_window.py` (ScanThread callers), `threat_intel.py` (VulnMatcher) |
| `device_fingerprint.py` | `scanner_engine.py` (`VulnScanner._identify_devices`) — 签名库改动影响设备识别与专项发现 |
| `constants.py` | `report_generator.py` (HTML SEV_COLORS), `main_window.py` (dashboard charts) |
| `config.py` | `api_server.py`, `db/`, `api/dependencies.py` |
| `report_generator.py` | `main_window.py` (save buttons), `report_converter.py` |
| `intel_sources.py` | `intel_pipeline.py` (factory functions), `threat_intel.py` (backward compat) |
| `main_window.py` | This is the orchestrator — almost everything connects here |

## Common Extension Recipes

### Adding a new vulnerability pattern
Edit `ai_analyzer.py`:
```python
# Add to DANGEROUS_PATTERNS dict
'新类别': [r'pattern1', r'pattern2'],
# Add to SEVERITY_MAP
'新类别': 'CRITICAL',
# Add to RECOMMENDATIONS
'新类别': '修复建议文本...',
```

### Adding a new intel source
Edit `intel_sources.py`:
```python
class NewSource(IntelSource):
    @property
    def source_name(self): return "Source Display Name"
    @property
    def source_type(self): return "local_api"  # or "web_osint"
    @property
    def confidence(self): return "P1"  # P0/P1/P2

    def fetch(self) -> Dict:
        # Fetch data, return {'data': [...], 'count': N}
        ...
    def sync_to_db(self, data) -> int:
        # Store to DB, return count
        ...
```
Then register in `intel_sources.py` factory functions: `create_local_sources()` or `create_osint_sources()`.

### Adding a new report format
Edit `report_converter.py` — see `save_report_formatted()` for the dispatch pattern.

### Adding an API endpoint
Create a new router in `api/routers/` following existing patterns:
```python
from fastapi import APIRouter, Depends
from api.dependencies import get_db, verify_api_key

router = APIRouter(prefix="/api/new", tags=["new"])

@router.get("/")
def list_items(db=Depends(get_db), _=Depends(verify_api_key)):
    ...
```
Register in `api/server.py` → `create_app()`.

## Testing

```bash
cd D:\projects\ai-vuln
python -m pytest tests/ -v
# tests/test_database.py    — DB CRUD operations
# tests/test_scanner_ai.py  — Scanner + AI integration tests
# tests/conftest.py         — Shared fixtures
```

## Quick Start Commands

```bash
python main.py              # Launch GUI
python api_server.py        # Start REST API (Swagger: http://127.0.0.1:8000/api/docs)
python cve_db_repair.py --fetch --start 2024-01  # Update CVE DB
python vuln_db_manager.py   # Standalone CVE DB manager GUI
```

## Design Principles

1. **AI-first**: Claude embedded in scan→verify→analyze→report pipeline, not bolted on
2. **Conservative security**: When AI fails → keep finding (never silently drop real vulns)
3. **Data sovereignty**: Fully local deployment, all data stays on-premise
4. **Graceful degradation**: Nmap→Socket fallback, Claude CLI→API fallback, PDF→HTML fallback
5. **No silent failures**: Every data source reports explicit status (success/partial/empty/error)
6. **Batch efficiency**: AI calls batched (4/batch) and parallelized (3 concurrent) for speed/cost balance
7. **Thread safety first**: All cross-thread UI updates go through the `_safe_log()` buffer

## International Benchmark Context

When making design decisions or writing docs, reference these competitive baselines:

| Product | Detection Coverage | False-Positive Rate | Key Differentiator |
|---------|-------------------|-------------------|-------------------|
| Nessus Pro | ~85% | ~30% | 200K+ NASL plugins |
| Qualys VMDR | ~85% | ~18% | TruRisk™ VPT scoring |
| Rapid7 InsightVM | ~80% | ~35% | Real Risk™ + Metasploit |
| **本系统 Pro** | **~65%** | **~12%** | **Claude AI双引擎，行业最低误报率** |

**Our structural advantages**: AI误报控制 (12% vs 25-45% industry), 代码审计 (unique), 数据主权, 成本优势
**Our structural gaps**: 检测覆盖率 (20% deficit), 云原生 (zero), 分布式架构 (single-node), CI/CD集成 (minimal)
