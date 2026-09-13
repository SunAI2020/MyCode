# 🦞 PLC 数据采集与编程工具 v1.0

基于 PyQt6 + pyqtgraph 的多协议 PLC 数据采集、监控与编程桌面应用。

## 功能特性

| 模块 | 说明 |
|------|------|
| 🔌 多协议连接 | Modbus TCP / Modbus RTU / Siemens S7-1200/1500 |
| 📊 数据监控 | 实时寄存器读写、批量标签监控、CSV 导出 |
| 📈 实时曲线 | 多通道趋势图，支持暂停/清除/自动滚动 |
| 💻 梯形图编程 | IL 语法编辑 + 编译检查 + 模拟运行 |
| 🏷 标签管理 | 图形化标签配置、JSON 导入/导出 |

## 安装

```bash
pip install -r requirements.txt
```

## 启动

```bash
python main.py
```

## 使用流程

1. **导入示例标签** — 文件 → 导入标签配置 → 选择 `example_tags.json`
2. **连接 PLC** — 选择驱动类型 → 配置 IP/端口 → 点击「连接」
3. **监控数据** — 切换到「数据监控」Tab 查看实时值
4. **查看曲线** — 切换到「实时曲线」Tab 查看趋势
5. **编写逻辑** — 切换到「梯形图编程」Tab 编写和模拟

## 支持的驱动

| 驱动 | 库 | 说明 |
|------|------|------|
| Modbus TCP | pymodbus | 支持 01/02/03/04/05/06/15/16 功能码 |
| Modbus RTU | pymodbus | 串口 RS-485/RS-232 |
| Siemens S7 | snap7 (可选) | 无 snap7 时自动回退到模拟模式 |

## 梯形图语法 (IL)

```
; 启停控制
LD  I0.0     ; 启动按钮
O   Q0.0     ; 自锁
AN  I0.1     ; 停止按钮
=   Q0.0     ; 电机输出

; 定时器: TON 定时器号, 时间(100ms)
LD  Q0.0
TON T37, 50

; 比较
LDW> VW10, 500
=   Q0.1
```

## 项目结构

```
plc-driver/
├── driver_base.py      # 驱动抽象基类 + 数据模型
├── modbus_driver.py    # Modbus TCP/RTU 实现
├── s7_driver.py        # Siemens S7 实现
├── main.py             # 图形界面 (PyQt6)
├── example_tags.json   # 示例标签配置
├── requirements.txt    # Python 依赖
└── README.md
```

## 扩展

继承 `PLCDriver` 基类即可添加新协议：

```python
class MitsubishiDriver(PLCDriver):
    @property
    def driver_type(self) -> DriverType:
        return DriverType.MITSUBISHI_MC

    async def connect(self, config: ConnectionConfig) -> bool: ...
    async def read_register(self, address, count=1) -> list[int]: ...
    async def write_register(self, address, value) -> bool: ...
```
