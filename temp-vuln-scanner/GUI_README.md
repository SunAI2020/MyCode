# 漏洞扫描系统 - 图形化界面 (GUI)

## 🛡️ 版权所有

**© 2026 山西有信网安科技有限公司**

---

## 📦 安装 GUI 依赖

```bash
cd /home/admin/.openclaw/workspace/vuln-scanner

# 安装 GUI 所需依赖
pip3 install --user pillow

# tkinter 通常随 Python 一起安装，如果没有请运行:
# Ubuntu/Debian: sudo apt-get install python3-tk
# CentOS/RHEL: sudo yum install python3-tkinter
```

## 🖼️ 添加公司 Logo

将您的公司商标图片保存到以下位置：

```
assets/logo.png
```

**要求：**
- 格式：PNG（支持透明背景）
- 尺寸：建议 200x200 像素或更大（会自动缩放）
- 位置：`/home/admin/.openclaw/workspace/vuln-scanner/assets/logo.png`

**操作步骤：**

1. 将您的商标图片复制到 assets 目录：
```bash
mkdir -p /home/admin/.openclaw/workspace/vuln-scanner/assets
cp /path/to/your/logo.png /home/admin/.openclaw/workspace/vuln-scanner/assets/logo.png
```

2. 如果没有图片，GUI 会自动显示文字 Logo（盾牌图标）

## 🚀 启动 GUI

```bash
cd /home/admin/.openclaw/workspace/vuln-scanner

# 方法 1：使用启动脚本
python3 gui_app.py

# 方法 2：直接运行模块
python3 -m gui.main_window
```

## 📋 GUI 功能

### 主界面

- **扫描配置面板**（左侧）
  - 扫描目标输入（支持单个 IP、IP 范围、CIDR）
  - 端口范围配置
  - 扫描选项（版本检测、操作系统检测）
  - 开始/停止扫描按钮

- **结果显示面板**（右侧）
  - 实时扫描日志
  - 主机/服务/漏洞统计
  - 漏洞详情（按严重程度着色）

### 菜单栏

- **文件**
  - 导入目标列表（从 TXT 文件批量导入）
  - 导出报告（HTML/JSON 格式）
  - 退出

- **工具**
  - 漏洞库管理
  - CVE 搜索
  - 系统设置

- **帮助**
  - 使用文档
  - 关于（显示版权信息）

### 特色功能

1. **启动加载屏幕**
   - 显示公司 Logo
   - 产品名称和版本
   - 版权信息

2. **标题栏**
   - 公司 Logo（左上角）
   - 产品名称
   - **版权所有：山西有信网安科技有限公司**（底部）

3. **关于对话框**
   - 公司 Logo
   - 版本信息
   - **突出的版权信息框**
   - 免责声明

4. **法律免责声明**
   - 每次扫描前弹出确认对话框
   - 强调合法使用要求

## 🎨 界面主题

- **主色调**：科技蓝 (#00d9ff)
- **背景色**：深色主题 (#1a1a2e)
- **成功状态**：绿色 (#00ff88)
- **警告状态**：橙色 (#ffaa00)
- **危险状态**：红色 (#ff4444)

## ⚠️ 注意事项

1. **Python 版本**：需要 Python 3.6+
2. **显示环境**：需要在有图形界面的环境中运行（不支持纯命令行服务器）
3. **Logo 图片**：如果未提供 logo.png，会自动显示文字 Logo

## 📞 技术支持

- **公司**：山西有信网安科技有限公司
- **邮箱**：support@youxinwangan.com
- **网站**：www.youxinwangan.com

---

**© 2026 山西有信网安科技有限公司 版权所有**
