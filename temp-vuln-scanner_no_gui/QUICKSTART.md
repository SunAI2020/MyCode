# 🚀 快速开始指南

## 5 分钟快速上手

### 1️⃣ 安装依赖

```bash
cd vuln-scanner
pip install -r requirements.txt
```

### 2️⃣ 确保 Nmap 已安装

```bash
nmap --version
```

未安装请参考 README 中的安装说明。

### 3️⃣ 执行首次扫描

```bash
# 扫描本机（安全测试）
python main.py scan --target 127.0.0.1 --skip-license
```

### 4️⃣ 查看报告

扫描完成后，报告保存在 `reports/` 目录：

```bash
ls reports/
# 打开 HTML 报告
# Linux: xdg-open reports/*.html
# macOS: open reports/*.html
# Windows: start reports/*.html
```

---

## 📋 常用命令速查

### 扫描命令

```bash
# 单个 IP
python main.py scan -t 192.168.1.1

# IP 范围
python main.py scan -t 192.168.1.1-50

# 网段
python main.py scan -t 192.168.1.0/24

# 指定端口
python main.py scan -t 192.168.1.1 -p 1-1000,8080,443

# 生成多种格式报告
python main.py scan -t 192.168.1.1 -f html -f json

# 跳过许可确认（仅限自有设备）
python main.py scan -t 192.168.1.1 --skip-license
```

### 漏洞库命令

```bash
# 查看统计
python main.py stats

# 搜索漏洞
python main.py search -p Apache -s CRITICAL

# 查看 CVE 详情
python main.py detail -c CVE-2021-44228

# 导出数据
python main.py export -o cve_data.json -l 100
```

### 帮助命令

```bash
# 主帮助
python main.py --help

# 子命令帮助
python main.py scan --help
```

---

## 🎯 典型使用场景

### 场景 1: 内网安全评估

```bash
# 扫描整个内网段
python main.py scan \
  --target 192.168.1.0/24 \
  --ports 1-65535 \
  --format html \
  --output ./internal_scan
```

### 场景 2: Web 服务器专项检查

```bash
# 只扫描 Web 相关端口
python main.py scan \
  --target 10.0.0.1 \
  --ports 80,443,8080,8443,9000 \
  --format html,json
```

### 场景 3: 批量目标扫描

创建 `targets.txt`:
```
192.168.1.1
192.168.1.10
192.168.1.20-30
```

执行扫描:
```bash
python main.py scan --target targets.txt --output ./batch_scan
```

### 场景 4: 查找特定漏洞

```bash
# 查找所有 Log4j 相关漏洞
python main.py search --product "Log4j" --limit 20

# 查找 CVSS 9.0 以上的漏洞
python main.py search --min-cvss 9.0 --limit 50
```

---

## 📊 理解扫描结果

### 严重程度说明

| 级别 | CVSS 分数 | 说明 | 响应时间 |
|------|----------|------|----------|
| 🔴 CRITICAL | 9.0-10.0 | 严重，可被轻易利用 | 立即 |
| 🟣 HIGH | 7.0-8.9 | 高危，需要优先处理 | 24 小时内 |
| 🟡 MEDIUM | 4.0-6.9 | 中危，需要计划修复 | 1 周内 |
| 🟢 LOW | 0.1-3.9 | 低危，可择机修复 | 1 月内 |
| ⚪ INFO | 0.0 | 信息，无需立即处理 | - |

### 置信度说明

- **high**: 版本精确匹配，误报率低
- **medium**: 产品匹配，版本近似
- **low**: 仅服务名称匹配，需人工确认

---

## ⚡ 性能提示

### 加快扫描速度

```bash
# 减少并发主机数（网络拥堵时）
# 在 config/settings.py 中调整:
# 'max_concurrent_hosts': 5

# 只扫描常用端口
python main.py scan -t 192.168.1.1 -p 21,22,23,25,80,443,445,3389

# 缩短超时时间
# 在 config/settings.py 中调整:
# 'default_timeout': 120
```

### 提高检测准确率

```bash
# 启用版本检测（默认开启）
# 扫描时会自动进行 -sV

# 启用操作系统检测（需要 root）
sudo python main.py scan -t 192.168.1.1

# 全端口扫描（耗时长但全面）
python main.py scan -t 192.168.1.1 -p 1-65535
```

---

## 🐛 常见问题

### Q: 扫描失败 "nmap not found"
A: 安装 Nmap，参考 README 中的安装说明。

### Q: 权限不足
A: 某些扫描技术需要 root 权限，使用 `sudo` 运行。

### Q: 扫描速度慢
A: 减少并发数或端口范围，参考性能提示。

### Q: 报告为空
A: 可能目标没有开放端口，或防火墙阻止了扫描。

### Q: 如何更新漏洞库？
A: 编辑 `data/cve_samples.json` 添加新 CVE，然后重新运行扫描。

---

## 📚 下一步

- 阅读完整 [README.md](README.md)
- 查看 [config/settings.py](config/settings.py) 了解配置选项
- 运行测试：`python -m pytest tests/ -v`
- 贡献代码：Fork 项目并提交 PR

---

**⚠️ 合法使用：仅扫描您拥有或已授权的系统！**
