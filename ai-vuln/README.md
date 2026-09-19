# 下一代智能漏洞扫描系统 Pro

> **Next-Generation Intelligent Vulnerability Scanning System**
>
> 山西有信网安科技有限公司 · 版本 2.1.0

一款「AI 优先」的综合安全检测平台，以 Claude AI 双引擎贯穿 **扫描 → 验证 → 分析 → 报告** 全流程，实现行业最低误报率（~12%）。

## 核心特性

- **AI 双引擎**：Claude 内嵌于扫描→核验→分析→报告全流程，而非外挂
- **多引擎检测**：Nmap/Socket 双引擎网络扫描 + 45+ 项主动 Web DAST + AI 静态代码审计 + 供应链 SCA + 多类型设备指纹
- **威胁情报**：CISA KEV / EPSS 威胁情报 + 多因子风险评分
- **合规检查**：等保 2.0 / 关基 / 数据安全 / 公安部 176 号 四类标准
- **数据主权**：全本地部署，所有数据不出内网
- **优雅降级**：Nmap→Socket、Claude CLI→API、PDF→HTML

## 技术栈

Python 3 + PyQt5 + FastAPI + SQLite + Claude AI

## 功能模块（8 大页签）

| 页签 | 说明 |
|------|------|
| 仪表盘 | 系统运行概览 |
| 网络扫描 | 端口/主机发现、服务指纹、CVE 匹配、设备专项、弱口令、蜜罐识别、认证扫描 |
| Web 扫描 | 45+ 项主动 DAST（注入/XSS/SSRF/文件包含/反序列化等） |
| AI 代码审计 | 10 类 / 40+ 正则静态缺陷检测 |
| AI 代码质量检测 | 13 维度代码质量与设计审查 |
| 威胁情报 | 13 源（6 本地 API + 7 Web OSINT）+ AI 分析 |
| 合规检查 | 等保/关基/数据安全/176 号合规自评 |
| 漏洞库管理 / 报告中心 | CVE 检索统计、报告导出 |

## 菜单栏

| 菜单 | 条目 |
|------|------|
| 文件(F) | 保存报告 / 打开报告 / 导出报告 / 退出 |
| 扫描(S) | 快速扫描 / 完整扫描 |
| 工具(T) | 更新 CVE 数据库 / 清空数据库 |
| 帮助(H) | 关于 / **交付文档(D)** |

### 交付文档入口

菜单栏「**帮助(H) → 交付文档(D)**」内置随系统分发的交付文档，点击即以系统默认程序打开。
文档存放于 exe 同目录 `文档/`（可增删），程序内另内置一份回退副本。

| 交付文档 | 格式 |
|----------|------|
| 漏洞扫描系统需求规格说明书 V1.1 | HTML / Markdown |
| 软件架构设计说明书 V1.0 | HTML / Word（docx） |
| 软件架构设计 | Markdown |
| 研发需求差距分析与开发计划 V2.0 | HTML / Markdown |
| 软件功能清单 | HTML |

## 目录结构

```
main.py                    # GUI 入口
main_window.py             # 8 页签主窗口（编排层）
scanner_engine.py          # 网络扫描双引擎
web_vuln_scanner.py        # Web 主动扫描
ai_analyzer.py             # 代码静态分析
ai_verifier.py             # AI 误报消除
ai_scan_enhancer.py        # 扫描三阶段核验
ai_code_reviewer.py        # 代码质量检测
device_fingerprint.py      # 多类型设备指纹
supply_chain.py            # 供应链安全（SCA）
honeypot_detector.py       # 蜜罐识别
ecc_security.py            # 密码学/TLS 安全
compliance_engine.py       # 合规检查引擎
compliance_controls/       # 合规条款目录（JSON，可扩充）
threat_intel.py            # 威胁情报门面
intel_pipeline.py          # 三阶段情报流水线
intel_sources.py           # 13 数据源
database.py                # 6 库统一门面
report_generator.py        # 报告生成
report_converter.py        # HTML→PDF/Word/MD
api/                       # FastAPI REST 层
api_server.py              # REST API 入口
文档/                      # 交付文档（随系统分发）
tests/                     # Pytest 测试套件
```

## 快速开始

### 环境要求

- Python 3.10+（推荐 3.13）
- Windows / Linux / macOS
- （可选）Nmap（`python-nmap` 依赖，缺失时自动回退 Socket 引擎）
- （可选）Claude Code CLI（本机 AI 能力，缺失时回退 Anthropic API Key）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动 GUI

```bash
python main.py
```

### 启动 REST API

```bash
python api_server.py
# Swagger 文档: http://127.0.0.1:8000/api/docs
```

### 更新 CVE 库

```bash
python cve_db_repair.py --fetch --start 2024-01
python vuln_db_manager.py      # 独立 CVE 库管理 GUI
```

### 运行测试

```bash
python -m pytest tests/ -v
```

## 数据库架构（6 库，SQLite WAL）

| 数据库文件 | 用途 |
|-----------|------|
| `scan_results.db` | 扫描历史与结果 |
| `cve_database.db` | CVE 知识库 |
| `threat_intel.db` | 威胁情报 |
| `audit_results.db` | 代码审计历史 |
| `assets_system.db` | 资产与系统配置 |
| `compliance_results.db` | 合规检查结果 |

可选 PostgreSQL 后端：`db/schema_postgres.py` + `db/migrate.py`。

## 打包部署

```bash
python -m PyInstaller pack_v1.spec --clean --noconfirm
# 输出: dist/AI漏洞扫描系统/ (exe + _internal)
```

发布时需将以下内容放到 exe 同目录（数据库文件**不**打入 exe）：

- `compliance_controls/`（合规填报表单）
- `assets/`（logo）
- `reports/`（报告输出目录）
- `文档/`（交付文档，供「帮助 → 交付文档」打开）
- 6 个 `*.db` 数据库文件

## 设计原则

1. **AI-first**：Claude 内嵌而非外挂
2. **保守安全**：AI 失败保留发现（绝不静默丢弃真实漏洞）
3. **数据主权**：全本地部署
4. **优雅降级**：逐级回退，无单点依赖
5. **无静默失败**：每个数据源显式上报状态
6. **批量效率**：AI 调用 4/批、3 并发
7. **线程安全**：跨线程 UI 更新走消息缓冲

## 参考文档

| 文档 | 编号 / 版本 |
|------|-----------|
| 漏洞扫描系统需求规格说明书 | VSS-SRS-2026-001 V1.1 |
| 软件架构设计说明书 | V1.0 |
| 研发需求差距分析与开发计划 | VSS-GAP-2026-002 V2.0 |
| 软件功能清单 | — |
