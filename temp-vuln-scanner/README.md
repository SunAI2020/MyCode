# 🔒 漏洞扫描系统 (Vulnerability Scanner System)

一个功能完整的漏洞扫描系统，类似"绿盟漏洞扫描系统"，用于授权的安全测试和漏洞评估。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ⚠️ 法律免责声明

**本工具仅用于授权的安全测试和漏洞评估。**

使用前请确保：
1. ✅ 您拥有目标系统的所有权或已获得**书面授权**
2. ✅ 您的使用符合当地法律法规
3. ✅ 您了解并承担使用本工具的全部责任

**未经授权扫描他人系统是违法行为！**

---

## 📋 功能特性

### 核心功能

- **漏洞库管理**
  - 包含 2000 年以来的操作系统和应用软件安全漏洞
  - 支持 CVE 编号、CVSS 评分、严重程度分级
  - 包含修复建议和参考链接
  - 内置 50+ 示例 CVE 数据

- **多 IP 设备扫描**
  - 支持单个 IP、IP 范围、IP 列表文件、CIDR 格式
  - 端口扫描与服务识别
  - 版本检测（操作系统、应用软件）
  - 并发扫描支持

- **漏洞匹配引擎**
  - 智能匹配检测到的服务/版本
  - 严重程度分级（Critical/High/Medium/Low/Info）
  - 误报处理机制
  - 置信度评估

- **报告输出**
  - HTML/PDF/JSON 多种格式
  - 按严重程度分类统计
  - 修复建议汇总
  - 执行摘要与详细发现

### 技术特性

- 🚀 基于 asyncio 的异步扫描
- 📊 SQLite 漏洞数据库
- 🔍 基于 nmap 的端口和服务扫描
- 📝 Jinja2 模板报告生成
- 🎨 Rich 库美化命令行输出

---

## 📦 安装

### 系统要求

- Python 3.10+
- Nmap（系统级安装）
- pip

### 安装步骤

1. **克隆或下载项目**

```bash
cd vuln-scanner
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **验证 Nmap 安装**

```bash
nmap --version
```

如果未安装 Nmap，请根据系统安装：

```bash
# Ubuntu/Debian
sudo apt-get install nmap

# CentOS/RHEL
sudo yum install nmap

# macOS
brew install nmap

# Windows
# 从 https://nmap.org/download.html 下载安装
```

---

## 🚀 快速开始

### 基本扫描

```bash
# 扫描单个 IP
python main.py scan --target 192.168.1.1

# 扫描 IP 范围
python main.py scan --target 192.168.1.1-100

# 扫描 CIDR 网段
python main.py scan --target 192.168.1.0/24

# 扫描指定端口
python main.py scan --target 192.168.1.1 --ports 1-1000,8080,443
```

### 报告生成

```bash
# 生成 HTML 报告（默认）
python main.py scan --target 192.168.1.1 -f html

# 生成多种格式报告
python main.py scan --target 192.168.1.1 -f html -f json -f pdf

# 指定输出目录
python main.py scan --target 192.168.1.1 --output ./reports
```

### 漏洞库操作

```bash
# 查看漏洞库统计
python main.py stats

# 搜索漏洞
python main.py search --product Apache --severity CRITICAL

# 查看 CVE 详情
python main.py detail --cve-id CVE-2021-44228

# 导出漏洞库
python main.py export --output cve_export.json --limit 100
```

### 帮助信息

```bash
# 查看主帮助
python main.py --help

# 查看子命令帮助
python main.py scan --help
python main.py search --help
```

---

## 📖 使用示例

### 示例 1: 扫描本地网络

```bash
# 扫描本地网段，生成详细报告
python main.py scan \
  --target 192.168.1.0/24 \
  --ports 1-65535 \
  --format html \
  --format json \
  --output ./scan_results
```

### 示例 2: 针对特定服务扫描

```bash
# 只扫描 Web 服务相关端口
python main.py scan \
  --target 10.0.0.1 \
  --ports 80,443,8080,8443 \
  --format html
```

### 示例 3: 从文件读取目标列表

创建 `targets.txt`:
```
192.168.1.1
192.168.1.2
192.168.1.10-20
10.0.0.0/24
```

执行扫描:
```bash
python main.py scan --target targets.txt --output ./reports
```

### 示例 4: 搜索特定漏洞

```bash
# 搜索所有 Apache 相关的高危漏洞
python main.py search \
  --product Apache \
  --severity HIGH \
  --min-cvss 7.0 \
  --limit 50
```

---

## 📁 项目结构

```
vuln-scanner/
├── core/               # 核心引擎
│   ├── __init__.py
│   └── engine.py       # 扫描引擎主逻辑
├── scanner/            # 扫描模块
│   ├── __init__.py
│   ├── nmap_scanner.py # Nmap 扫描器
│   └── vuln_matcher.py # 漏洞匹配引擎
├── database/           # 漏洞库管理
│   ├── __init__.py
│   ├── models.py       # 数据模型
│   └── vuln_database.py # 数据库操作
├── report/             # 报告生成
│   ├── __init__.py
│   └── report_generator.py
├── utils/              # 工具函数
│   ├── __init__.py
│   └── helpers.py
├── config/             # 配置文件
│   ├── __init__.py
│   └── settings.py
├── templates/          # 报告模板
│   └── report.html
├── data/               # 数据文件
│   └── cve_samples.json # 示例 CVE 数据
├── tests/              # 测试用例
│   ├── __init__.py
│   ├── test_database.py
│   └── test_matcher.py
├── reports/            # 扫描报告输出（自动生成）
├── logs/               # 日志文件（自动生成）
├── cli.py              # 命令行接口
├── main.py             # 程序入口
├── requirements.txt    # Python 依赖
└── README.md           # 本文档
```

---

## 🔧 配置说明

配置文件位于 `config/settings.py`，主要配置项：

### 扫描配置

```python
SCAN = {
    'default_timeout': 300,        # 扫描超时时间（秒）
    'max_concurrent_hosts': 10,    # 最大并发主机数
    'max_concurrent_ports': 100,   # 最大并发端口数
    'version_detection': True,     # 版本检测
    'os_detection': True,          # 操作系统检测
}
```

### 报告配置

```python
REPORT = {
    'output_dir': './reports',     # 报告输出目录
    'formats': ['html', 'json'],   # 默认报告格式
}
```

### CVSS 阈值

```python
CVSS_THRESHOLDS = {
    'CRITICAL': (9.0, 10.0),
    'HIGH': (7.0, 8.9),
    'MEDIUM': (4.0, 6.9),
    'LOW': (0.1, 3.9),
    'INFO': (0.0, 0.0),
}
```

---

## 📊 输出示例

### 命令行输出

```
╔══════════════════════════════════════════════════════════╗
║     🔒  漏洞扫描系统 v1.0                                 ║
║     Vulnerability Scanner System                         ║
╚══════════════════════════════════════════════════════════╝

⚠️  法律免责声明
本工具仅用于授权的安全测试和漏洞评估。
...

是否同意上述条款并继续？(yes/no): yes

📊 数据库状态
✓ 漏洞库已加载
  总 CVE 数：50
  严重：15 | 高危：20 | 中危：15

✓ 扫描完成!

📈 扫描统计
┌──────────────┬───────┐
│ 指标         │ 数值  │
├──────────────┼───────┤
│ 扫描主机     │ 5     │
│ 发现服务     │ 12    │
│ 发现漏洞     │ 8     │
│ 严重漏洞     │ 2     │
│ 高危漏洞     │ 3     │
└──────────────┴───────┘
```

### HTML 报告

报告包含：
- 执行摘要卡片
- 按严重程度分组的漏洞列表
- 每个漏洞的详细信息（CVSS、描述、修复建议）
- 扫描主机和服务详情
- 参考链接

---

## 🧪 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 或使用 unittest
python -m unittest discover tests/
```

---

## 🛠️ 开发指南

### 添加新的 CVE 数据

1. 编辑 `data/cve_samples.json`
2. 按照以下格式添加：

```json
{
  "cve_id": "CVE-2024-XXXX",
  "name": "漏洞名称",
  "description": "漏洞描述",
  "affected_products": ["产品名称"],
  "affected_versions": ["版本 1", "版本 2"],
  "cvss_score": 9.8,
  "severity": "CRITICAL",
  "published_date": "2024-01-01",
  "modified_date": "2024-01-02",
  "references": ["https://..."],
  "fix_recommendation": "修复建议",
  "cwe_id": "CWE-XXX",
  "exploit_available": true,
  "patch_available": true
}
```

3. 重新初始化数据库

### 扩展扫描功能

在 `scanner/nmap_scanner.py` 中添加新的扫描技术：

```python
def scan_custom(self, host, arguments):
    """自定义扫描"""
    self.nm.scan(host, arguments=arguments)
    # ...
```

---

## ⚡ 性能优化建议

1. **并发控制**: 根据网络环境调整 `max_concurrent_hosts`
2. **端口范围**: 优先扫描常用端口，全端口扫描耗时较长
3. **超时设置**: 大型网络适当增加 `default_timeout`
4. **报告格式**: JSON 格式生成最快，PDF 最慢

---

## 🔐 安全注意事项

1. **授权扫描**: 始终确保有书面授权
2. **速率限制**: 避免对生产系统造成拒绝服务
3. **数据存储**: 妥善保存扫描报告，防止泄露
4. **日志管理**: 定期清理日志文件

---

## 📝 更新日志

### v1.0.0 (2024)
- ✨ 初始版本发布
- ✅ 漏洞库管理（50+ CVE 示例）
- ✅ 多 IP 并发扫描
- ✅ 智能漏洞匹配引擎
- ✅ HTML/JSON/PDF报告生成
- ✅ 命令行接口
- ✅ 单元测试

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 🙏 致谢

- [Nmap](https://nmap.org/) - 网络扫描工具
- [python-nmap](https://python-nmap.readthedocs.io/) - Python Nmap 库
- [Click](https://click.palletsprojects.com/) - 命令行框架
- [Rich](https://rich.readthedocs.io/) - 终端美化库
- [Jinja2](https://jinja.palletsprojects.com/) - 模板引擎

---

## 📧 联系方式

如有问题或建议，请提交 Issue 或联系开发团队。

---

**⚠️ 再次提醒：请合法使用本工具，仅对授权目标进行扫描！**
