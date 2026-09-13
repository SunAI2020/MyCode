# AI-PTS (AI Penetration Testing System)

基于AI的渗透测试桌面工具

## 功能特性

- **端口扫描**: Nmap集成，支持TCP/UDP扫描
- **服务识别**: 自动识别服务版本
- **漏洞匹配**: 基于24万+CVE数据库匹配漏洞
- **AI分析**: Claude API驱动的智能漏洞分析和攻击路径规划
- **工作流执行**: 自动渗透测试工作流
- **报告生成**: HTML/PDF格式报告

## 安装

```bash
# 克隆或复制项目
cd ai-pts

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### GUI模式

```bash
python aipts.py
```

### CLI模式

```bash
# 扫描单个目标
python aipts.py cli -t 192.168.1.1

# 扫描网段
python aipts.py cli -t 192.168.1.0/24

# 带AI分析
python aipts.py cli -t 192.168.1.1 --analyze
```

## 配置

### API密钥

首次使用需要配置Anthropic API Key：

1. 在GUI中：`工具` -> `设置API密钥`
2. 或设置环境变量：`set ANTHROPIC_API_KEY=your-key`
3. 或在启动时：`python aipts.py -k your-key`

获取API Key: https://console.anthropic.com/

### 漏洞库

首次运行会自动初始化漏洞库，或手动导入：

```bash
python import_cve.py import -f "path/to/漏洞库.json"
```

## 项目结构

```
ai-pts/
├── aipts.py           # 启动入口
├── main.py            # CLI入口
├── config.py          # 配置管理
├── integrate.py       # 扫描器集成
├── import_cve.py      # CVE导入工具
├── requirements.txt   # 依赖
├── gui/
│   └── main_window.py  # GUI主窗口
├── core/
│   ├── ai_analyzer.py  # AI分析引擎
│   └── workflow.py     # 渗透工作流
├── data/
│   └── vuln.db         # 漏洞数据库
└── reports/           # 报告输出
```

## 使用说明

### 1. 扫描目标

在目标输入框中输入：
- 单个IP: `192.168.1.1`
- IP范围: `192.168.1.1-254`
- CIDR: `192.168.1.0/24`
- 域名: `example.com`

### 2. 查看结果

扫描完成后，在"扫描结果"标签页查看：
- 发现的服务列表
- 匹配的漏洞列表

### 3. AI分析

点击"AI分析"按钮，AI将：
- 评估漏洞优先级
- 规划攻击路径
- 提供利用建议

### 4. 导出报告

`文件` -> `导出报告`，支持JSON和HTML格式

## 依赖项

| 包 | 说明 |
|---|------|
| anthropic | Claude API |
| python-nmap | Nmap Python绑定 |
| PyQt5 | GUI框架 |
| jinja2 | 报告模板 |
| weasyprint | PDF生成 |

## 注意事项

1. **法律合规**: 只扫描授权目标
2. **API配额**: Claude API有使用限制
3. **扫描速度**: 大规模扫描请适当调整并发数

## 许可证

仅供安全研究和授权测试使用