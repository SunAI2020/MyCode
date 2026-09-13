# 代码审查报告 — 高努力度全面审查

**审查日期**: 2026-08-07  
**审查范围**: 工作区未提交变更 (35 文件, +1650/-1234 行)  
**审查方法**: 7角度并行发现 → 单票验证 (召回优先)  
**审查工具**: Claude Code `/code-review` (high effort)

---

## 审查摘要

| 严重度 | 数量 |
|--------|------|
| 🔴 HIGH (正确性/鲁棒性) | 4 |
| 🟡 MEDIUM (性能/可维护性) | 4 |
| 🟢 LOW (清理) | 1 |
| **总计** | **9** |

---

## 🔴 HIGH — 正确性与鲁棒性

### 1. `intel_report_thread` 线程泄露 — 旧线程替换时未清理

**文件**: `D:\projects\ai-vuln\main_window.py` — `_on_intel_collection_finished` / `_start_ai_report_generation`

**问题**: `self.intel_report_thread` 在创建新线程前不检查旧线程是否仍在运行、不调用 `quit()/wait()/terminate()`。如果用户在情报采集完成后（自动触发报告生成，预计5-15分钟）立即手动重新开始采集，旧线程被孤立：
- 旧线程的 `finished`/`error` 信号仍连接到 `_on_ai_report_finished`/`_on_ai_report_error`
- 旧线程完成后会触发重复的 `QMessageBox` 弹窗、重复的 `db.save_report()` 调用、覆盖 `self.ai_intel_report`、提前重新启用按钮

**修复建议**: 在创建新 `intel_report_thread` 前检查并终止旧线程；或使用线程池模式确保同一时间只有一个报告生成线程。

---

### 2. AI扫描/审计等待对话框永远不自动关闭

**文件**: `D:\projects\ai-vuln\main_window.py` — `_on_ai_scan_finished` / `_on_audit_finished`

**问题**: AI扫描的 `wait_dlg`（"AI核验比较费时..."）和AI审计的 `wait_dlg` 在操作完成后从不自动关闭。`_on_ai_scan_finished`、`_on_ai_scan_error`、`_stop_ai_verify`、`_on_audit_finished`、`_on_audit_error`、`_stop_audit` 中均没有对对话框调用 `.close()`/`.accept()`/`.reject()`。审计对话框设置了 `WA_DeleteOnClose` 但仍需用户手动点击关闭。

**修复建议**: 在 `_on_*_finished` 和 `_on_*_error` 回调中添加 `wait_dlg.accept()` 或 `wait_dlg.close()`。

---

### 3. `database.py` 模块导入时全局修改环境变量

**文件**: `D:\projects\ai-vuln\database.py:22-25`

```python
os.environ['TEMP'] = _APP_TEMP_DIR
os.environ['TMP'] = _APP_TEMP_DIR
os.environ['TMPDIR'] = _APP_TEMP_DIR
```

**问题**: 在模块导入时设置 `os.environ['TEMP']`/`['TMP']`/`['TMPDIR']` 是进程级全局副作用。任何使用 `tempfile.gettempdir()` 的库（matplotlib、PIL 等）和所有子进程都会将临时文件写入应用目录而非系统临时目录。注释中说"重定向到D盘"，但 `BASE_DIR` 基于脚本路径，若脚本在 C 盘则重定向到 C 盘，违背设计意图。

**修复建议**: `SQLITE_TMPDIR` 已足够满足 SQLite 需求。Python 层面的临时目录控制应使用 `tempfile.tempdir = _APP_TEMP_DIR`（范围限定在 tempfile 模块），或仅在调用点使用 `tempfile.mkdtemp(dir=_APP_TEMP_DIR)`。

---

### 4. `_update_chart_card` 静默吞没所有异常

**文件**: `D:\projects\ai-vuln\main_window.py:771-781`

```python
try:
    if chart_type == 'pie':
        self._draw_pie(fig, data, colors)
    elif chart_type == 'trend':
        self._draw_trend(fig, data)
    canvas.draw_idle()
except Exception:
    pass  # ← 所有渲染失败静默忽略
```

**问题**: `num_label.setText(str(value))` 在 try 块之前已更新数字标签。如果图表渲染失败（如 matplotlib `ValueError`），用户看到新数字配旧图表——静默数据不一致，且无任何日志记录，难以调试。

**修复建议**: 至少用 `logger.exception(...)` 记录异常；或将 `num_label.setText` 移入 try 块末尾，确保数字只在渲染成功后才更新。

---

## 🟡 MEDIUM — 性能与可维护性

### 5. N+1 查询 — `get_vuln_by_task()` 和 `get_audit_by_task()` 各 121 次查询

**文件**: `D:\projects\ai-vuln\database.py:166-186` 和 `:797-818`

**问题**: 两个函数按同样模式：1次查询获取任务列表，然后对每个任务的 4 个严重等级分别执行 `COUNT(*)` 查询。limit=30 时各 1 + 30×4 = 121 次查询。每次仪表盘刷新产生约 240 次 SQLite 往返。

**修复建议**: 使用单次 JOIN + GROUP BY 查询替代：

```sql
SELECT task_id, severity, COUNT(*) as cnt
FROM scan_results
WHERE task_id IN (SELECT id FROM scan_tasks WHERE status='completed' ORDER BY id DESC LIMIT ?)
GROUP BY task_id, severity
```

---

### 6. `_strip_markdown_fences` 重复定义于 2 个文件

**文件**: `D:\projects\ai-vuln\ai_scan_enhancer.py:418-425` 和 `D:\projects\ai-vuln\ai_verifier.py:187-195`

**问题**: 两个文件中有完全相同的 `_strip_markdown_fences` 静态方法（逐字符相同）。Markdown 代码块包裹是 `AIClient` 输出的特性，应在客户端层面统一处理。修改正则时需同步两处，必然会有一处遗漏。

**修复建议**: 将 `_strip_markdown_fences` 移入 `AIClient.query()` 或 `ai_client.py` 的模块级工具函数，两个调用方改为导入。

---

### 7. 严重度颜色映射 `SEV_COLORS` 重复定义

**文件**: `D:\projects\ai-vuln\main_window.py:706` 和 `D:\projects\ai-vuln\report_generator.py:79`

**问题**: `{'CRITICAL': '#d32f2f', 'HIGH': '#f57c00', 'MEDIUM': '#fbc02d', 'LOW': '#388e3c', 'INFO': '#1976d2'}` 在两个文件中独立定义。颜色方案变更时需同步两处，否则仪表盘图表与导出HTML报告颜色不一致。

**修复建议**: 提取到共享模块（如 `constants.py`），统一引用。

---

### 8. `__import__('datetime').timedelta` 动态导入反模式

**文件**: `D:\projects\ai-vuln\database.py:155` 和 `:785`

```python
d = (datetime.now() - __import__('datetime').timedelta(days=i)).strftime('%Y-%m-%d')
```

**问题**: 文件顶部已 `from datetime import datetime`，但在循环内使用 `__import__()` 动态导入 `timedelta`。虽然 Python 的导入机制会缓存，但这是不必要的属性遍历开销和代码异味。

**修复建议**: 将导入改为 `from datetime import datetime, timedelta`，直接使用 `timedelta`。

---

## 🟢 LOW — 清理

### 9. 死代码 — `get_vuln_trend()` 和 `get_audit_trend()` 已定义但无调用者

**文件**: `D:\projects\ai-vuln\database.py:150-164` / `:780-795` 以及门面类委托方法

**问题**: 这两个函数（按日期统计30天漏洞/审计趋势）被定义并通过 `Database` 门面类暴露，但整个代码库中零调用点。仪表盘实际使用的是按任务统计的 `get_vuln_by_task()`/`get_audit_by_task()`。同时这两个函数也包含相同的 `__import__('datetime')` 反模式和 N+1 LIKE 查询问题。

**修复建议**: 删除死代码，或明确标注为未来使用的预留 API。

---

## 已验证但排除的候选

| 候选 | 判定 | 理由 |
|------|------|------|
| ThreadPoolExecutor 中断传播 | REFUTED | `QThread.requestInterruption()` 正确地通过父线程生命周期传播；`ThreadPoolExecutor` 本身设计就是运行已提交的 futures 到完成。`_stop_ai_verify` 的 wait(5000)+terminate() 机制可正常工作。这不是 bug，是架构设计取舍。 |

---

## 审查覆盖的变更文件

| 文件 | 变更类型 | 审查维度 |
|------|----------|----------|
| `ai_scan_enhancer.py` | API→AIClient 切换 + 并行批处理 | A, B, C, D, E, G |
| `ai_verifier.py` | API→AIClient 切换 | A, B, C, D |
| `database.py` | 临时目录重定向 + 新查询方法 | A, E, F, G |
| `main_window.py` | Dashboard 图表 + 资产管理增强 | A, B, C, E, F, G |
| `scanner_engine.py` | 回退 CVE 匹配并行化 | A, E |
| `threat_intel.py` | 完全重构 → IntelPipeline 委托 | B, C, G |
| `report_generator.py` | sev_color 移至模块级 | B, D |
| `vuln_db_manager.py` | 网络错误指数退避重试 | A |
| `ai_analyzer.py` | 进度回调信息增强 | C |

---

> 🤖 Generated with [Claude Code](https://claude.com/claude-code) — 2026-08-07  
> 审查级别: High Effort (3 correctness + 3 cleanup + 1 altitude × up to 6 candidates each)  
> 总审查 token: ~600K
