# AI-PLC 智能控制系统 — 详尽技术方案

> **版本**: V2.0 | **日期**: 2026-07-30 | **密级**: 内部

---

## 目录

1. [项目概述与愿景](#1-项目概述与愿景)
2. [系统总体架构](#2-系统总体架构)
3. [核心功能模块详细设计](#3-核心功能模块详细设计)
4. [AI 智能引擎深度设计](#4-ai-智能引擎深度设计)
5. [数据库设计](#5-数据库设计)
6. [API接口设计](#6-api接口设计)
7. [前端架构与组件树](#7-前端架构与组件树)
8. [安全架构设计](#8-安全架构设计)
9. [技术选型详表](#9-技术选型详表)
10. [部署架构](#10-部署架构)
11. [测试策略](#11-测试策略)
12. [实施路线图](#12-实施路线图)
13. [竞争优势分析](#13-竞争优势分析)
14. [风险与应对](#14-风险与应对)
15. [参考文献](#15-参考文献)

---

## 1. 项目概述与愿景

### 1.1 项目背景

工业自动化领域长期面临以下痛点：

| 痛点 | 现状 | 影响 |
|------|------|------|
| **品牌壁垒** | 西门子、罗克韦尔、三菱等PLC使用互不兼容的编程软件 | 工程师需学习多套工具，切换成本高 |
| **电气设计与编程分离** | 电气CAD（E3、Capital X）和PLC IDE（TIA Portal、CODESYS）是独立工具 | 数据不同步，重复劳动，易出错 |
| **AI渗透率低** | 工业领域AI应用仍以"辅助建议"为主 | 未能实现端到端自动化 |
| **数据孤岛** | PLC数据分散在各设备中，缺乏统一采集分析平台 | 数据价值未被充分挖掘 |

### 1.2 产品愿景

构建**全球首个打通"电气设计 → PLC编程 → AI辅助 → 数据采集"全链路的统一智能平台**，让任何水平的工程师都能在数小时内完成传统需要数天的PLC工程项目。

### 1.3 核心指标

| 指标 | 目标值 | 当前行业基准 |
|------|--------|-------------|
| 主流PLC品牌兼容 | 6+ | 1（各品牌独立工具） |
| AI代码生成准确率 | ≥95% | ~85%（Wipro PARI基准） |
| 工程周期缩短 | 90%+ | — |
| 支持通信协议 | 20+ | 2-3（厂商工具） |
| 系统可用性 | 99.9% | — |
| 页面加载时间（P95） | <2s | — |
| 画布渲染帧率（1000元件） | ≥30fps | — |

---

## 2. 系统总体架构

### 2.1 四层分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     表现层 (Presentation Layer)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ 电路图    │ │ 梯形图    │ │ 数据仪表盘│ │ 项目管理         │   │
│  │ 编辑器    │ │ 编辑器    │ │ 可视化    │ │ 协同编辑         │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│                      React 18 + TypeScript + Canvas/SVG          │
├─────────────────────────────────────────────────────────────────┤
│                   核心服务层 (Core Service Layer)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ 项目管理  │ │ 编译服务  │ │ 协议网关  │ │ 用户权限         │   │
│  │ 服务      │ │ (IEC→IR)  │ │ (多协议)  │ │ (RBAC/ABAC)     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│                      Go (核心) + gRPC + NATS                      │
├─────────────────────────────────────────────────────────────────┤
│                     AI引擎层 (AI Engine Layer)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ 需求解析  │ │ 代码生成  │ │ 逻辑分析  │ │ 错误检测         │   │
│  │ 引擎      │ │ 引擎      │ │ 引擎      │ │ 修正引擎         │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│                Python + LangChain + vLLM + Milvus (RAG)           │
├─────────────────────────────────────────────────────────────────┤
│                   数据接入层 (Data Access Layer)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ OPC UA    │ │ MQTT      │ │ Modbus    │ │ 边缘计算         │   │
│  │ 客户端    │ │ Broker    │ │ TCP/RTU   │ │ 节点              │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│              PostgreSQL + TDengine + Redis + MinIO               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 架构设计原则

1. **模型无关的AI架构**：AI引擎通过抽象LLM接口层隔离具体模型，支持GPT-4o、Claude Opus 4、Gemini 2.5、Llama 4、Qwen 3等模型热切换
2. **插件化扩展**：PLC品牌驱动、通信协议、AI模型均以插件形式注册，第三方可通过gRPC插件SDK贡献
3. **事件驱动通信**：核心服务间使用NATS消息队列实现松耦合异步通信
4. **边缘-云协同**：边缘节点处理毫秒级实时任务，云端处理AI推理和长期存储
5. **安全纵深防御**：传输层TLS 1.3、应用层API签名、数据层字段级加密、访问层RBAC+ABAC混合模型

### 2.3 关键数据流

```
用户自然语言需求
        │
        ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 需求解析引擎  │────▶│ 电路生成引擎  │────▶│ 代码生成引擎  │
│ (NLP→结构化)  │     │ (符号匹配+布线)│     │ (IR→目标语言) │
└──────────────┘     └──────────────┘     └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 结构化需求    │     │ 电路图数据    │     │ IEC 61131-3  │
│ JSON Schema   │     │ Canvas JSON  │     │ 源代码        │
└──────────────┘     └──────────────┘     └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │ 三层验证      │
                                        │ 语法+逻辑+仿真 │
                                        └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │ 部署到PLC     │
                                        │ (OPC UA/      │
                                        │  厂商协议)    │
                                        └──────────────┘
```

---

## 3. 核心功能模块详细设计

### 3.1 多品牌PLC型号选择与管理

#### 3.1.1 PLC型号数据模型

```typescript
interface PlcModel {
  id: string;                    // UUID
  brand: PlcBrand;               // 品牌
  series: string;                 // 系列名称
  modelNumber: string;           // 完整型号
  cpuType: string;               // CPU型号
  specifications: {
    digitalInputs: number;       // 数字量输入点数
    digitalOutputs: number;      // 数字量输出点数
    analogInputs: number;        // 模拟量输入通道
    analogOutputs: number;       // 模拟量输出通道
    scanTime: number;            // 扫描周期 (μs)
    programMemory: number;       // 程序内存 (KB)
    dataMemory: number;          // 数据内存 (KB)
    communicationPorts: CommPort[]; // 通信接口列表
  };
  programmingLanguages: IecLanguage[]; // 支持的IEC 61131-3语言
  protocols: Protocol[];         // 原生支持协议
  lifecycle: {
    introduced: Date;
    endOfSale?: Date;
    endOfSupport?: Date;
  };
  certifications: string[];      // 认证（CE, UL, ATEX等）
}
```

#### 3.1.2 支持的PLC品牌矩阵

| 品牌 | 代表系列 | 编程语言 | 通信协议 | 编程软件 | AI就绪度 |
|------|---------|---------|---------|---------|---------|
| **Siemens** | S7-1200, S7-1500, ET 200SP | LD, FBD, ST, SCL, Graph | PROFINET, OPC UA, Modbus TCP | TIA Portal V21 | Copilot (2025) |
| **Rockwell** | ControlLogix 5580, CompactLogix 5380 | LD, FBD, ST, SFC | EtherNet/IP, OPC UA | Studio 5000 | AI-Orchestrated Eng (2026) |
| **Mitsubishi** | MELSEC iQ-R, iQ-F | LD, FBD, ST, SFC | CC-Link IE, Modbus TCP, OPC UA | GX Works3 | EcoStruxure (部分) |
| **Schneider** | Modicon M580, M340 | LD, FBD, ST, SFC, IL | Modbus TCP, OPC UA, EtherNet/IP | EcoStruxure Control Expert | Industrial Copilot |
| **Beckhoff** | CX系列, C60xx | LD, FBD, ST, SFC, CFC | EtherCAT, OPC UA, Modbus TCP | TwinCAT 3 | TwinCAT CoAgent |
| **Omron** | NJ/NX系列 | LD, FBD, ST, SFC | EtherCAT, OPC UA, Modbus TCP | Sysmac Studio | — |
| **B&R** | X20, X90 | LD, FBD, ST, CFC, ANSI C | POWERLINK, OPC UA | Automation Studio | — |
| **WAGO** | PFC200, PFC100 | LD, FBD, ST, SFC, CFC | Modbus TCP, OPC UA, EtherNet/IP | e!COCKPIT (CODESYS) | — |

#### 3.1.3 型号选择向导

系统提供**智能选型向导**：

```
Step 1: 输入需求参数
  ├─ I/O点数需求（DI/DO/AI/AO）
  ├─ 扫描周期要求
  ├─ 通信协议要求
  ├─ 环境条件（温度、防护等级）
  └─ 预算范围

Step 2: 系统推荐
  ├─ 匹配度评分（0-100）
  ├─ 多个品牌对比视图
  └─ 价格估算（集成供应商API）

Step 3: 确认并创建项目
  └─ 自动配置I/O映射模板
```

### 3.2 拖拽式PLC电路图设计

#### 3.2.1 画布引擎架构

```
┌──────────────────────────────────────────┐
│             Canvas Orchestrator           │
│        (协调渲染、交互、撤销/重做)          │
├──────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ 符号图层 │  │ 连线图层 │  │ 注释图层 │ │
│  │ (Canvas)  │  │ (SVG)     │  │ (DOM)    │ │
│  └──────────┘  └──────────┘  └─────────┘ │
├──────────────────────────────────────────┤
│  交互层 (dnd-kit + 自研电气约束引擎)      │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ 拖拽管理 │  │ 选择管理 │  │ 缩放手势 │ │
│  └──────────┘  └──────────┘  └─────────┘ │
├──────────────────────────────────────────┤
│  数据层 (Yjs CRDT 协同模型)               │
│  ┌──────────┐  ┌──────────┐             │
│  │ 文档模型 │  │ 冲突解决 │              │
│  └──────────┘  └──────────┘             │
└──────────────────────────────────────────┘
```

**混合渲染策略：**
- **Canvas 2D**：渲染2000+符号实例，利用离屏Canvas做脏矩形局部重绘
- **SVG 叠加层**：连线的贝塞尔曲线，支持精确点击检测和锚点编辑
- **DOM 叠加层**：元件标签、引脚编号、注释文字，利用CSS做动画效果

#### 3.2.2 电气符号库系统

```typescript
// 符号定义规范 (IEC 60617子集扩展)
interface SymbolDefinition {
  id: string;
  category: SymbolCategory;
  name: string;                   // 符号名称（中/英）
  iecCode: string;               // IEC 60617 编码
  tags: string[];                 // 搜索标签
  geometry: {
    boundingBox: Rect;           // 包围盒（标准化网格单位）
    paths: PathCommand[];        // 矢量路径
    texts: SymbolText[];         // 标注文字
  };
  pins: PinDefinition[];         // 接线端子
  properties: PropertySchema[];  // 可配置属性
  variants: SymbolVariant[];     // 变体（常开/常闭等）
  metadata: {
    manufacturer?: string;       // 厂商特定符号
    orderNumber?: string;
    datasheet?: string;
  };
}

enum SymbolCategory {
  CONTACTOR_RELAY = 'contactor_relay',
  SENSOR = 'sensor',
  CIRCUIT_BREAKER = 'circuit_breaker',
  PLC_MODULE = 'plc_module',
  TERMINAL_BLOCK = 'terminal_block',
  POWER_SUPPLY = 'power_supply',
  MOTOR = 'motor',
  BUTTON_SWITCH = 'button_switch',
  SIGNAL_LAMP = 'signal_lamp',
  CUSTOM = 'custom',
}
```

**符号库规模规划：**

| 类别 | 基础符号数 | 厂商扩展 | 合计（目标） |
|------|----------|---------|------------|
| 接触器/继电器 | 120 | 300+ | 420 |
| 传感器 | 80 | 150+ | 230 |
| 断路器/熔断器 | 90 | 200+ | 290 |
| PLC模块 | 60 | 400+ | 460 |
| 端子排/连接器 | 50 | 100+ | 150 |
| 电源/变压器 | 40 | 80+ | 120 |
| 电机/执行器 | 30 | 60+ | 90 |
| 按钮/开关/指示灯 | 70 | 150+ | 220 |
| 其他 | 40 | 80+ | 120 |
| **总计** | **580** | **1520+** | **2100+** |

#### 3.2.3 电气规则约束引擎

```typescript
// 电气规则引擎：在拖拽/连线时实时检查电气规则
class ElectricalRuleEngine {
  // 连线规则检查
  checkConnection(source: Pin, target: Pin): RuleCheckResult {
    const checks = [
      this.checkWireCapacity(source, target),     // 线径容量
      this.checkVoltageCompatibility(source, target), // 电压兼容
      this.checkSignalType(source, target),       // 信号类型（DI/DO/AI/AO）
      this.checkShortCircuit(source, target),     // 短路检测
      this.checkTerminalAssignment(source, target), // 端子分配
    ];
    return this.evaluate(checks);
  }

  // PLC I/O分配规则
  checkIOAllocation(pin: Pin, channel: IOChannel): RuleCheckResult { ... }

  // 安全回路完整性
  checkSafetyLoop(circuit: Circuit): RuleCheckResult { ... }

  // 电源容量校核
  checkPowerBudget(panel: Panel): RuleCheckResult { ... }
}
```

#### 3.2.4 自动布线算法

```
AutoRouter Pipeline:
1. 将画布栅格化为离散网格（分辨率可配）
2. 使用A*算法找最短路径（避免穿越元件）
3. 使用曼哈顿路由风格（工业标准）
4. 信号线分层：
   - Layer 1: 主回路（粗线，红色）
   - Layer 2: 控制回路（细线，蓝色）
   - Layer 3: 通信线（虚线，绿色）
5. 自动添加线号标注
6. 生成接线端子表
```

### 3.3 PLC控制程序编写

#### 3.3.1 IEC 61131-3 全语言支持

| 语言 | 缩写 | 类型 | 编辑器实现 | 应用场景 |
|------|------|------|-----------|---------|
| 梯形图 | LD | 图形 | Canvas拖拽编辑器 | 离散逻辑、维护人员 |
| 功能块图 | FBD | 图形 | Canvas连线编辑器 | 过程控制、PID |
| 结构化文本 | ST | 文本 | Monaco Editor | 复杂算法、数据处理 |
| 顺序功能图 | SFC | 图形 | Canvas步骤编辑器 | 顺序控制、批处理 |
| 指令表 | IL | 文本 | Monaco Editor | 简单逻辑（逐渐淘汰） |
| 连续功能图 | CFC | 图形 | Canvas自由连线编辑器 | DCS/过程控制 |

#### 3.3.2 统一中间表示（UIR）

所有IEC语言编译为统一的中间表示，实现跨语言、跨品牌转换：

```
                        ┌─────────────┐
   梯形图 (LD)  ──────▶ │             │
   功能块图 (FBD) ────▶ │             │
   结构化文本 (ST) ───▶ │ Unified IR  │ ──▶ 西门子 SCL
   顺序功能图 (SFC) ──▶ │   (UIR)     │ ──▶ AB Ladder
   指令表 (IL) ───────▶ │             │ ──▶ 三菱 ST
   连续功能图 (CFC) ──▶ │             │ ──▶ 倍福 ST
                        └─────────────┘ ──▶ CODESYS ST
                              │
                              ▼
                        ┌─────────────┐
                        │ 优化器       │
                        │ (死代码消除, │
                        │  常量折叠,    │
                        │  FBD→ST变换) │
                        └─────────────┘
```

```typescript
// UIR 核心数据结构
interface UirProgram {
  metadata: {
    name: string;
    version: string;
    targetPlc: PlcBrand;
    sourceLanguage: IecLanguage;
  };
  globalVariables: UirVariable[];
  pous: ProgramOrganizationUnit[];
}

interface ProgramOrganizationUnit {
  type: 'PROGRAM' | 'FUNCTION_BLOCK' | 'FUNCTION';
  name: string;
  interface: PouInterface;
  body: UirNode[];
}

type UirNode =
  | AssignmentNode
  | CallNode           // 功能块/函数调用
  | ConditionalNode    // IF/ELSIF/ELSE
  | CaseNode           // CASE
  | ForLoopNode
  | WhileLoopNode
  | RepeatLoopNode
  | ReturnNode
  | RungNode           // 梯形图横档
  | ContactNode        // 触点（常开/常闭）
  | CoilNode;          // 线圈
```

#### 3.3.3 Monaco编辑器定制

```
ST语言编辑器扩展：
├─ 语法高亮（IEC 61131-3关键字）
├─ 智能补全
│   ├─ 变量名补全
│   ├─ 功能块实例补全
│   ├─ 函数签名提示
│   └─ 品牌特定指令补全（通过RAG检索）
├─ 诊断（Diagnostics）
│   ├─ 实时语法检查
│   ├─ 类型检查
│   └─ 未初始化变量警告
├─ 代码片段（Snippets）
│   ├─ 电机启停模板
│   ├─ PID控制模板
│   └─ 通信配置模板
└─ AI 内联建议
    └─ 类似GitHub Copilot的Ghost Text
```

### 3.4 数据采集与控制信号输出

#### 3.4.1 多协议网关架构

```
                        ┌──────────────────┐
                        │   协议网关管理器   │
                        │  (Protocol Gateway │
                        │   Manager)         │
                        └──────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
    ┌─────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
    │ OPC UA    │      │ MQTT        │     │ Modbus      │
    │ Connector │      │ Connector   │     │ Connector   │
    └─────┬─────┘      └──────┬──────┘     └──────┬──────┘
          │                    │                    │
    ┌─────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
    │ NATS      │      │ EMQX        │     │ libmodbus   │
    │ Client    │      │ Broker       │     │ Wrapper      │
    └───────────┘      └─────────────┘     └─────────────┘

    其他协议：
    ├─ EtherNet/IP (CIP协议栈)
    ├─ PROFINET (西门子专用)
    ├─ EtherCAT (倍福专用)
    ├─ CC-Link IE (三菱专用)
    ├─ CANopen
    ├─ BACnet (楼宇自动化)
    └─ 自定义TCP/UDP协议 (用户可配置)
```

#### 3.4.2 数据采集配置模型

```typescript
interface DataAcquisitionConfig {
  id: string;
  name: string;
  protocol: Protocol;
  connection: {
    host: string;
    port: number;
    slaveId?: number;           // Modbus从站ID
    namespace?: string;          // OPC UA命名空间
    topic?: string;             // MQTT主题
  };
  tags: DataTag[];              // 数据点位
  sampling: {
    mode: 'polling' | 'event' | 'mixed';
    interval: number;           // 采样间隔(ms)
    deadband?: number;          // 死区值
  };
  preprocessing: {
    filters: Filter[];
    transforms: Transform[];
    aggregations: Aggregation[];
  };
  output: DataOutput[];         // 输出目标
}

interface DataOutput {
  type: 'file' | 'database' | 'mqtt' | 'opcua' | 'rest' | 'websocket' | 'kafka';
  config: Record<string, any>;
  format: 'json' | 'csv' | 'binary' | 'protobuf';
}
```

#### 3.4.3 边缘计算节点

```
边缘节点功能：
├─ 协议转换：南向200+协议 → 北向统一MQTT/OPC UA
├─ 数据预处理
│   ├─ 死区过滤（减少数据量）
│   ├─ 异常值检测（IQR/3σ法）
│   ├─ 数据插值（缺失值补全）
│   └─ 滑动窗口聚合（min/max/avg/stddev）
├─ 本地规则引擎
│   ├─ IF-THEN规则触发
│   ├─ 阈值报警
│   └─ 本地联动控制
├─ 断网续传
│   ├─ 本地SQLite缓存（最大7天数据）
│   └─ 网络恢复后自动同步
├─ 安全
│   ├─ 单向数据二极管（可选硬件）
│   └─ 数据脱敏（可选）
└─ 硬件平台
    ├─ ARM Cortex-A72（树莓派CM4）
    ├─ Intel Atom x6000（工业网关）
    └─ NVIDIA Jetson Orin（AI推理边缘）
```

---

## 4. AI 智能引擎深度设计

### 4.1 需求自动解析与电路设计

#### 4.1.1 AI管道详细架构

```
用户自然语言输入
        │
        ▼
┌──────────────────────────────────────────┐
│ Step 1: 需求规范化 (Requirement Normalizer)│
│  ├─ LLM: 提取关键实体与关系               │
│  ├─ NER: 识别设备类型、控制动作、条件      │
│  ├─ Coreference Resolution: 消解指代      │
│  └─ 输出: 规范化需求文本                  │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Step 2: 结构化提取 (Structure Extractor)   │
│  ├─ Schema-guided Generation             │
│  ├─ 输出: ControlSpec JSON               │
│  └─ 验证: JSON Schema + 业务规则          │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Step 3: 设备匹配 (Device Matcher)          │
│  ├─ RAG检索: 设备描述→符号库向量相似度     │
│  ├─ 参数推导: 从规格推导元器件参数         │
│  └─ 输出: 设备清单 + 符号分配              │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Step 4: 电路合成 (Circuit Synthesizer)     │
│  ├─ 主电路图生成（供电拓扑）               │
│  ├─ 控制电路图生成（信号流）               │
│  ├─ I/O接线图生成（PLC端子分配）           │
│  ├─ 自动布线（A* + 电气规则约束）          │
│  └─ 输出: Canvas JSON Document            │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Step 5: 人机协同 (Human-in-the-Loop)       │
│  ├─ 可视化呈现生成结果                    │
│  ├─ 用户拖拽微调                          │
│  ├─ 修改记录→强化学习反馈                 │
│  └─ 确认→锁定电路图版本                   │
└──────────────────────────────────────────┘
```

#### 4.1.2 ControlSpec结构化需求模型

```typescript
interface ControlSpec {
  metadata: {
    name: string;
    description: string;
    industry?: string;          // 行业（汽车/食品/化工等）
    safetyLevel: 'SIL1' | 'SIL2' | 'SIL3' | 'none';
  };
  devices: SpecDevice[];
  ioMapping: IOMapping[];
  controlLogic: ControlLogicItem[];
  sequences: Sequence[];
  alarms: Alarm[];
  interlocks: Interlock[];
}

interface SpecDevice {
  id: string;
  type: DeviceType;            // motor, valve, sensor, button, lamp, ...
  role: string;                // 功能描述
  specifications: Record<string, any>;
  quantity: number;
}

interface ControlLogicItem {
  condition: LogicExpression;  // 触发条件
  action: LogicAction;         // 执行动作
  timing?: TimingConstraint;   // 时序约束
  priority: number;
}

interface IOMapping {
  deviceId: string;
  signalType: 'DI' | 'DO' | 'AI' | 'AO';
  channelNumber?: number;
  plcModuleId?: string;
  tagName: string;
  description: string;
}
```

#### 4.1.3 多智能体协同（参考AutoPLC架构）

```
┌─────────────────────────────────────────────────────┐
│                  Orchestrator Agent                   │
│           (任务分解、工作流调度、结果合并)              │
└───┬──────────┬──────────┬──────────┬────────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ 需求    │ │ 电路    │ │ 程序    │ │ 验证    │
│ 分析    │ │ 设计    │ │ 生成    │ │ 代理    │
│ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │
└────────┘ └────────┘ └────────┘ └────────┘
    │          │          │          │
    └──────────┴──────────┴──────────┘
                    │
                    ▼
            ┌──────────────┐
            │ 人工审核节点  │
            │ (关键决策点)  │
            └──────────────┘
```

### 4.2 自动编写PLC控制程序

#### 4.2.1 代码生成策略

| 策略 | 适用场景 | 方法 | 准确率 |
|------|---------|------|--------|
| **模板匹配** | 标准控制模式（启停、正反转、星三角） | RAG检索→参数化→填充 | ~98% |
| **AST生成** | 中等复杂度逻辑 | LLM生成UIR AST→验证→编译 | ~92% |
| **多智能体协同** | 复杂系统 | 分解→多个Agent并行生成→合并 | ~88% |
| **混合策略（默认）** | 通用场景 | 模板优先→无法匹配时退化为AST生成 | ~95% |

#### 4.2.2 RAG增强生成流程

```
用户需求
    │
    ▼
┌──────────────┐     ┌───────────────────┐
│ Query Encoder │────▶│ Milvus Vector DB  │
│ (text-embedding│     │ (PLC指令库/模板库) │
│  -3-large)    │     └───────┬───────────┘
└──────────────┘             │
                             ▼
                    ┌───────────────┐
                    │ Top-K 相关     │
                    │ 指令/模板召回  │
                    └───────┬───────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       ▼                       │
    │              ┌───────────────┐                │
    │              │ Context Window │                │
    │              │ 组装           │                │
    │              └───────┬───────┘                │
    │                      │                        │
    │                      ▼                        │
    │              ┌───────────────┐                │
    │              │ LLM Generation │               │
    │              │ (GPT-4o/Claude │               │
    │              │  /Qwen 3)      │               │
    │              └───────┬───────┘                │
    │                      │                        │
    │                      ▼                        │
    │              ┌───────────────┐                │
    │              │ IEC 编译器验证 │               │
    │              │ (语法/语义)    │               │
    │              └───────┬───────┘                │
    │                      │                        │
    │              ┌───────▼───────┐                │
    │              │ 通过?  ──No──▶│ 错误反馈→重新生成│
    │              └───────┬───────┘ (最多重试3次)  │
    │                      │ Yes                    │
    │                      ▼                        │
    │              ┌───────────────┐                │
    │              │ 输出代码       │                │
    │              └───────────────┘                │
    └───────────────────────────────────────────────┘
```

#### 4.2.3 跨品牌代码转换

```
源品牌代码 (AB Ladder)
        │
        ▼
┌──────────────┐
│ 解析为 UIR    │  ← 品牌特定解析器（每个品牌维护一个）
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ UIR 优化      │  ← 品牌无关的优化遍（规范化/简化）
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 从 UIR 生成   │  ← 品牌特定代码生成器
│ 目标品牌代码  │
└──────┬───────┘
       │
       ▼
目标品牌代码 (Siemens SCL)
```

**指令映射表（片段示例）：**

| 功能 | AB (RSLogix 5000) | Siemens (TIA Portal) | Mitsubishi (GX Works3) |
|------|-------------------|---------------------|------------------------|
| 常开触点 | XIC | `--| |--` | LD |
| 常闭触点 | XIO | `--|/|--` | LDI |
| 输出线圈 | OTE | `--( )--` | OUT |
| 置位 | OTL | `--(S)--` | SET |
| 复位 | OTU | `--(R)--` | RST |
| 定时器 | TON | TON (IEC) | OUT T |
| 计数器 | CTU | CTU (IEC) | OUT C |
| 上升沿 | ONS | `--(P)--` | PLS |

### 4.3 PLC逻辑关系分析

#### 4.3.1 多维分析引擎

```
分析维度：
├─ 控制流分析
│   ├─ LD/FBD→Petri网模型转换
│   ├─ 状态空间枚举
│   ├─ 可达性图生成
│   └─ 死锁/活锁检测
├─ 数据流分析
│   ├─ Use-Define链构建
│   ├─ 变量生存期分析
│   ├─ 数据依赖图
│   └─ 扇入/扇出统计
├─ 时序分析
│   ├─ 定时器参数合理性检查
│   ├─ 时序冲突检测（两个输出竞争同一资源）
│   ├─ 扫描周期影响评估
│   └─ 响应时间上界计算（速率单调分析）
├─ 安全分析
│   ├─ 安全联锁完整性（SIL等级验证）
│   ├─ 故障树分析（FTA）
│   ├─ 事件树分析（ETA）
│   └─ HAZOP引导式审查
├─ 合规分析
│   ├─ PackML状态机完整性
│   ├─ ISA-88批处理模式
│   └─ 品牌最佳实践检查
└─ 复杂度度量
    ├─ 圈复杂度
    ├─ 霍尔斯特德度量
    └─ 可维护性指数
```

#### 4.3.2 Petri网转换算法

```
LD → Petri网转换规则：

1. 触点 → Place + Transition
   常开触点：Place有Token→Transition可触发
   常闭触点：Place无Token→Transition可触发

2. 线圈 → Place（标记输出状态）

3. 横档 → Transition连接
   串联触点 → Transition序列（AND关系）
   并联触点 → 多条输入弧到同一Transition（OR关系）

4. 定时器 → Timed Transition
   TON: 延时后触发
   TOF: 延时后关闭

5. 计数器 → Transition with Guard
   CTU: 计数达到预设值触发
```

### 4.4 PLC错误检测与修正

#### 4.4.1 三层验证体系

```
Layer 1: 静态分析 (Static Analysis)
├─ 工具: 自研IEC 61131-3 Linter
├─ 检测项:
│   ├─ 悬空线圈（写入但从未读取）
│   ├─ 未复位定时器（TON无RESET条件）
│   ├─ 锁存逻辑缺失解锁触点
│   ├─ 重复输出（两个线圈驱动同一地址）
│   ├─ 除零风险（运算中除数可能为0）
│   ├─ 数组越界
│   ├─ 隐式类型转换（可能精度丢失）
│   ├─ 未初始化变量
│   └─ 注释与代码不一致（NLP对比）
└─ 输出: Warning/Error + 定位信息

Layer 2: 形式化验证 (Formal Verification)
├─ 工具: Z3 Theorem Prover
├─ 步骤:
│   1. 提取关键安全属性（由AI辅助识别）
│   2. 将PLC程序转换为SMT公式
│   3. 将安全属性表达为断言
│   4. 使用Z3求解器验证（sat/unsat/unknown）
│   5. 若sat，生成反例执行路径
└─ 验证属性示例:
    ├─ "急停按钮按下后，所有电机必须停止"
    ├─ "互锁条件成立时，不允许同时启动"
    └─ "安全门开启时，机器人禁止运动"

Layer 3: 仿真测试 (Simulation Testing)
├─ 工具: 内置软PLC运行时
├─ 功能:
│   ├─ 虚拟I/O信号注入
│   ├─ 时序波形查看器
│   ├─ 断点/单步调试
│   ├─ 状态快照对比
│   └─ 覆盖率报告（语句/分支/MCDC）
└─ 数字孪生集成:
    ├─ 导入3D模型（STEP/IGES格式）
    ├─ 物理仿真（碰撞检测、运动学）
    └─ 闭环仿真→真实PLC输出比对
```

#### 4.4.2 AI错误修正流程

```
检测到错误
    │
    ▼
┌──────────────────┐
│ 错误分类          │
│ (语法/逻辑/安全)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ LLM 根因分析      │
│ (基于程序上下文    │
│  和错误信息)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 修正方案生成      │
│ (生成3个候选修正)  │
└────────┬─────────┘
         │
    ┌────▼────┐
    │ 候选排序 │
    │ (安全性 > │
    │  正确性 > │
    │  简洁性)  │
    └────┬────┘
         │
         ▼
┌──────────────────┐
│ 修正影响分析      │
│ (Affected Rungs/ │
│  Variables/Votes) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 差异对比展示      │
│ ├─ Top-1 建议    │
│ ├─ 修改前后对比  │
│ └─ 影响范围标注  │
└────────┬─────────┘
         │
         ▼
    ┌──────────┐
    │ 用户决策  │
    │ 一键应用/ │
    │ 手动调整/ │
    │ 拒绝      │
    └──────────┘
```

---

## 5. 数据库设计

### 5.1 核心表结构

#### 用户与组织

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(128),
    role VARCHAR(32) NOT NULL DEFAULT 'engineer', -- admin, engineer, viewer
    organization_id UUID REFERENCES organizations(id),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- 组织/企业
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(128),
    subscription_tier VARCHAR(32) DEFAULT 'free', -- free, pro, enterprise
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 项目
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    organization_id UUID REFERENCES organizations(id),
    target_plc_model_id UUID REFERENCES plc_models(id),
    status VARCHAR(32) DEFAULT 'draft', -- draft, in_progress, review, deployed, archived
    version INT DEFAULT 1,
    settings JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 项目成员
CREATE TABLE project_members (
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) DEFAULT 'editor', -- owner, editor, viewer
    PRIMARY KEY (project_id, user_id)
);
```

#### PLC型号库

```sql
-- PLC品牌
CREATE TABLE plc_brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL UNIQUE,
    full_name VARCHAR(255),
    country VARCHAR(64),
    website VARCHAR(255),
    logo_url VARCHAR(512)
);

-- PLC型号
CREATE TABLE plc_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID REFERENCES plc_brands(id),
    series VARCHAR(128) NOT NULL,
    model_number VARCHAR(128) NOT NULL UNIQUE,
    cpu_type VARCHAR(128),
    specifications JSONB NOT NULL,
    -- {di:16, do:16, ai:4, ao:2, scanTime:100, programMemory:512, ...}
    languages VARCHAR(32)[] NOT NULL,   -- {LD, FBD, ST, SFC, IL, CFC}
    protocols VARCHAR(64)[] NOT NULL,   -- {PROFINET, OPC_UA, Modbus_TCP, ...}
    lifecycle JSONB DEFAULT '{}',
    certifications VARCHAR(64)[],
    datasheet_url VARCHAR(512),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 电路图数据

```sql
-- 电路图文档（Yjs CRDT同步）
CREATE TABLE schematics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(32) NOT NULL,
    -- main_circuit, control_circuit, io_wiring, panel_layout
    page_number INT DEFAULT 1,
    canvas_data JSONB NOT NULL,     -- 完整画布状态（用于初始加载）
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Yjs增量更新（协同编辑）
CREATE TABLE schematic_updates (
    id BIGSERIAL PRIMARY KEY,
    schematic_id UUID REFERENCES schematics(id) ON DELETE CASCADE,
    update_data BYTEA NOT NULL,    -- Yjs编码的增量数据
    client_id BIGINT NOT NULL,
    clock INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 符号自定义实例
CREATE TABLE symbol_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schematic_id UUID REFERENCES schematics(id) ON DELETE CASCADE,
    symbol_def_id UUID REFERENCES symbol_definitions(id),
    position_x FLOAT NOT NULL,
    position_y FLOAT NOT NULL,
    rotation FLOAT DEFAULT 0,
    scale FLOAT DEFAULT 1.0,
    properties JSONB DEFAULT '{}',
    label VARCHAR(128),
    custom_svg TEXT
);

-- 连线
CREATE TABLE wires (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schematic_id UUID REFERENCES schematics(id) ON DELETE CASCADE,
    source_pin_id UUID NOT NULL,
    target_pin_id UUID NOT NULL,
    path_data TEXT NOT NULL,        -- SVG路径
    wire_number VARCHAR(32),
    wire_type VARCHAR(32) DEFAULT 'control',
    -- power, control, communication, ground
    color VARCHAR(16),
    cross_section FLOAT             -- mm²
);
```

#### PLC程序

```sql
-- 程序文件
CREATE TABLE program_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    language VARCHAR(8) NOT NULL,   -- LD, FBD, ST, SFC, IL, CFC
    source_code TEXT,               -- 源代码（ST/IL）
    graphical_data JSONB,           -- 图形化数据（LD/FBD/SFC/CFC）
    uir_data JSONB,                 -- 统一中间表示
    is_main BOOLEAN DEFAULT false,
    folder_path VARCHAR(512),       -- 项目内路径
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 变量/标签数据库
CREATE TABLE tag_database (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    data_type VARCHAR(64) NOT NULL, -- BOOL, INT, DINT, REAL, STRING, ...
    address VARCHAR(64),            -- %I0.0, %Q0.1, %MW100, ...
    scope VARCHAR(32) DEFAULT 'local', -- local, global, io
    io_channel_id UUID REFERENCES io_channels(id),
    initial_value TEXT,
    description TEXT,
    unit VARCHAR(32),
    range_low FLOAT,
    range_high FLOAT,
    retention BOOLEAN DEFAULT false,
    UNIQUE(project_id, name)
);
```

#### AI任务

```sql
-- AI任务记录
CREATE TABLE ai_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    task_type VARCHAR(64) NOT NULL,
    -- requirement_parse, circuit_gen, code_gen, logic_analyze, error_fix
    status VARCHAR(32) DEFAULT 'pending',
    -- pending, running, completed, failed, cancelled
    input JSONB NOT NULL,
    output JSONB,
    model_used VARCHAR(128),        -- gpt-4o, claude-opus-4-8, qwen3-235b
    tokens_used INT,
    latency_ms INT,
    error_message TEXT,
    user_feedback JSONB,
    -- {rating: 1-5, comments: "", accepted: true/false}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- AI反馈数据集（用于模型微调）
CREATE TABLE ai_feedback_dataset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES ai_tasks(id),
    input TEXT NOT NULL,
    ai_output TEXT NOT NULL,
    corrected_output TEXT NOT NULL, -- 人工修正后的版本
    feedback_type VARCHAR(32),      -- correction, refinement, rejection
    quality_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 数据采集

```sql
-- 采集配置
CREATE TABLE acquisition_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    protocol VARCHAR(32) NOT NULL,
    connection_config JSONB NOT NULL,
    sampling_config JSONB NOT NULL,
    is_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 数据标签
CREATE TABLE data_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID REFERENCES acquisition_configs(id) ON DELETE CASCADE,
    tag_name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    -- Modbus地址 / OPC UA NodeId / MQTT Topic
    data_type VARCHAR(32) NOT NULL,
    polling_interval_ms INT,
    deadband FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.2 时序数据（TDengine）

```sql
-- TDengine超级表：PLC时序数据
CREATE STABLE plc_telemetry (
    ts TIMESTAMP,
    project_id BINARY(36),
    tag_name VARCHAR(255),
    value DOUBLE,
    quality INT
) TAGS (
    project_tag BINARY(72),
    data_type VARCHAR(32)
);

-- 自动创建子表（每个数据标签一个子表）
CREATE TABLE t_{tag_id} USING plc_telemetry
    TAGS ('{project_id}:{tag_name}', '{data_type}');
```

---

## 6. API接口设计

### 6.1 REST API 概览

```
Base URL: /api/v1

认证方式: Bearer Token (JWT) + API Key

通用响应格式:
{
  "success": true/false,
  "data": { ... },
  "error": { "code": "ERROR_CODE", "message": "..." },
  "meta": { "page": 1, "pageSize": 20, "total": 100 }
}
```

### 6.2 核心API端点

#### 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/projects` | 创建项目 |
| `GET` | `/api/v1/projects` | 项目列表（分页、筛选） |
| `GET` | `/api/v1/projects/{id}` | 项目详情 |
| `PUT` | `/api/v1/projects/{id}` | 更新项目 |
| `DELETE` | `/api/v1/projects/{id}` | 删除项目（软删除） |
| `POST` | `/api/v1/projects/{id}/duplicate` | 复制项目 |
| `GET` | `/api/v1/projects/{id}/export` | 导出项目（ZIP） |

#### PLC型号

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/plc-models` | PLC型号列表（筛选brand/series/ioCount） |
| `GET` | `/api/v1/plc-models/{id}` | 型号详情 |
| `GET` | `/api/v1/plc-brands` | 品牌列表 |
| `POST` | `/api/v1/plc-models/compare` | 多型号对比 |
| `POST` | `/api/v1/plc-models/recommend` | AI选型推荐 |

#### 电路图

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/schematics` | 创建电路图 |
| `GET` | `/api/v1/schematics/{id}` | 获取电路图（全量） |
| `PUT` | `/api/v1/schematics/{id}` | 更新电路图 |
| `DELETE` | `/api/v1/schematics/{id}` | 删除电路图 |
| `WS` | `/ws/schematics/{id}` | WebSocket协同编辑 |
| `POST` | `/api/v1/schematics/{id}/auto-route` | 自动布线 |
| `POST` | `/api/v1/schematics/{id}/validate` | 电气规则检查 |
| `GET` | `/api/v1/schematics/{id}/export/{format}` | 导出（DXF/PDF/SVG） |
| `GET` | `/api/v1/symbols` | 符号库检索 |
| `POST` | `/api/v1/symbols` | 导入自定义符号 |

#### PLC程序

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/programs` | 创建程序文件 |
| `GET` | `/api/v1/programs/{id}` | 获取程序 |
| `PUT` | `/api/v1/programs/{id}` | 保存程序 |
| `POST` | `/api/v1/programs/{id}/compile` | 编译程序（→UIR） |
| `POST` | `/api/v1/programs/{id}/convert?target={brand}` | 跨品牌转换 |
| `POST` | `/api/v1/programs/{id}/validate` | 静态分析 |
| `POST` | `/api/v1/programs/{id}/simulate` | 仿真运行 |
| `GET` | `/api/v1/programs/{id}/download?format={format}` | 导出可下载文件 |

#### AI服务

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/ai/parse-requirements` | 需求解析→结构化控制需求 |
| `POST` | `/api/v1/ai/generate-circuit` | 从需求生成电路图 |
| `POST` | `/api/v1/ai/generate-code` | 从需求生成PLC程序 |
| `POST` | `/api/v1/ai/analyze-logic` | 逻辑关系分析 |
| `POST` | `/api/v1/ai/detect-errors` | 错误检测 |
| `POST` | `/api/v1/ai/fix-error` | 错误修正 |
| `POST` | `/api/v1/ai/complete` | 代码补全（流式SSE） |
| `POST` | `/api/v1/ai/chat` | AI助手对话（流式SSE） |
| `GET` | `/api/v1/ai/tasks/{id}` | AI任务状态查询 |

#### 数据采集

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/acquisition/configs` | 创建采集配置 |
| `GET` | `/api/v1/acquisition/configs` | 配置列表 |
| `POST` | `/api/v1/acquisition/configs/{id}/start` | 启动采集 |
| `POST` | `/api/v1/acquisition/configs/{id}/stop` | 停止采集 |
| `GET` | `/api/v1/acquisition/data/query` | 查询时序数据 |
| `WS` | `/ws/acquisition/live` | 实时数据推送 |
| `POST` | `/api/v1/acquisition/export` | 数据导出（CSV/Parquet） |

### 6.3 gRPC 服务定义

```protobuf
// 编译服务
service CompilerService {
  rpc CompileToUIR (CompileRequest) returns (CompileResponse);
  rpc GenerateCode (CodeGenRequest) returns (CodeGenResponse);
  rpc ValidateSyntax (ValidateRequest) returns (ValidateResponse);
  rpc ConvertBrand (ConvertRequest) returns (ConvertResponse);
}

// AI引擎服务
service AIEngineService {
  rpc ParseRequirements (ParseRequest) returns (ParseResponse);
  rpc GenerateCircuit (CircuitGenRequest) returns (CircuitGenResponse);
  rpc GenerateCode (AICodeGenRequest) returns (AICodeGenResponse);
  rpc AnalyzeLogic (LogicAnalyzeRequest) returns (LogicAnalyzeResponse);
  rpc DetectErrors (ErrorDetectRequest) returns (ErrorDetectResponse);
  rpc FixError (ErrorFixRequest) returns (ErrorFixResponse);
  rpc StreamCompletion (CompletionRequest) returns (stream CompletionChunk);
}

// 协议网关服务
service GatewayService {
  rpc ConnectDevice (ConnectRequest) returns (ConnectResponse);
  rpc ReadTags (ReadRequest) returns (ReadResponse);
  rpc WriteTags (WriteRequest) returns (WriteResponse);
  rpc SubscribeTags (SubscribeRequest) returns (stream TagUpdate);
}
```

### 6.4 WebSocket协议

#### 协同编辑（Yjs）

```
连接: ws://host/ws/schematics/{id}
协议: Yjs WebSocket Protocol
- 客户端发送: Yjs编码的增量更新
- 服务端: 广播给同文档的其他客户端 + 持久化到schematic_updates表
- 心跳: ping/pong 30s间隔
```

#### 实时数据推送

```
连接: ws://host/ws/acquisition/live?tags=tag1,tag2,tag3

推送格式:
{
  "timestamp": "2026-07-30T10:30:00.000Z",
  "values": {
    "tag1": { "value": 23.5, "quality": 192 },
    "tag2": { "value": 1, "quality": 192 }
  }
}
```

---

## 7. 前端架构与组件树

### 7.1 技术栈

```
前端技术栈：
├─ 核心框架: React 18.3 + TypeScript 5.5
├─ 状态管理: Zustand（编辑器状态）+ TanStack Query（服务端状态）
├─ 路由: React Router 6（项目管理/编辑器/仪表盘三大模块）
├─ UI组件库: 自研组件库（Tailwind CSS + shadcn/ui范式）
├─ 图形渲染:
│   ├─ Canvas 2D API（符号/连线渲染）
│   ├─ SVG（精确交互层）
│   └─ PixiJS（可选WebGL加速，超大规模电路图）
├─ 拖拽: dnd-kit + 自研电气约束引擎
├─ 代码编辑器: Monaco Editor
├─ 图表: ECharts 5（仪表盘可视化）
├─ 协同编辑: Yjs + y-websocket
├─ 构建: Vite 6
└─ 测试: Vitest + Playwright + Storybook
```

### 7.2 应用路由结构

```
/                            → 工作台（项目列表）
/project/:id                 → 项目概览（资源管理器）
/project/:id/schematic/:sid  → 电路图编辑器
/project/:id/program/:pid    → PLC程序编辑器
/project/:id/dashboard       → 数据仪表盘
/project/:id/settings        → 项目设置
/plc-models                  → PLC型号浏览
/symbols                     → 符号库管理
/settings                    → 用户设置
/admin                       → 管理面板
```

### 7.3 核心组件树

```
<App>
├─ <AppShell>
│   ├─ <Sidebar>                          // 侧边导航
│   │   ├─ <ProjectTree>                  // 项目文件树
│   │   ├─ <DevicePalette>                // 设备面板（电路图编辑时）
│   │   └─ <NavigationMenu>
│   └─ <MainContent>
│       ├─ [路由: /]
│       │   └─ <Workspace>
│       │       ├─ <ProjectList>           // 项目卡片列表
│       │       ├─ <QuickActions>          // 快速操作
│       │       └─ <RecentProjects>
│       │
│       ├─ [路由: /project/:id/schematic/:sid]
│       │   └─ <SchematicEditor>
│       │       ├─ <TopToolbar>
│       │       │   ├─ <DrawingTools>      // 绘图工具（选择、连线等）
│       │       │   ├─ <ZoomControls>      // 缩放控制
│       │       │   ├─ <UndoRedoButtons>   // 撤销/重做
│       │       │   └─ <SnapGridToggle>    // 网格/吸附开关
│       │       ├─ <CanvasArea>
│       │       │   ├─ <Canvas2DLayer>     // 元件渲染层
│       │       │   ├─ <SVGInteractionLayer> // 连线/交互层
│       │       │   └─ <DOMLabelLayer>     // 标签/注释层
│       │       ├─ <PropertiesPanel>       // 属性面板
│       │       │   ├─ <SymbolProperties>
│       │       │   ├─ <WireProperties>
│       │       │   └─ <PageProperties>
│       │       ├─ <SymbolBrowser>          // 符号浏览器（侧边抽屉）
│       │       │   ├─ <SymbolSearch>
│       │       │   ├─ <CategoryList>
│       │       │   └─ <SymbolGrid>
│       │       ├─ <AIAssistantPanel>       // AI助手面板
│       │       │   ├─ <ChatWindow>
│       │       │   ├─ <GeneratedPreview>
│       │       │   └─ <DiffViewer>
│       │       └─ <StatusBar>
│       │           ├─ <CursorPosition>
│       │           ├─ <ConnectionStatus>
│       │           └─ <ValidationBadge>
│       │
│       ├─ [路由: /project/:id/program/:pid]
│       │   └─ <ProgramEditor>
│       │       ├─ <EditorTabs>             // 多文件标签页
│       │       ├─ <LadderEditor>           // 梯形图编辑器（Canvas）
│       │       │   ├─ <RungEditor>
│       │       │   ├─ <InstructionPalette>
│       │       │   └─ <AddressAssignment>
│       │       ├─ <STEditor>               // ST编辑器（Monaco）
│       │       │   └─ <MonacoEditor>
│       │       │       ├─ <AIInlineCompletion>  // AI内联补全
│       │       │       └─ <DiagnosticsGutter>
│       │       ├─ <VariableTable>          // 变量表/标签数据库
│       │       ├─ <CompileOutput>          // 编译输出面板
│       │       └─ <SimulationPanel>        // 仿真面板
│       │           ├─ <SignalInjector>
│       │           ├─ <TimingDiagram>
│       │           └─ <WatchWindow>
│       │
│       └─ [路由: /project/:id/dashboard]
│           └─ <DataDashboard>
│               ├─ <LiveMetricsGrid>
│               ├─ <TimeSeriesChart>
│               ├─ <AlarmPanel>
│               ├─ <KPICards>
│               └─ <ReportGenerator>
```

### 7.4 状态管理架构

```typescript
// Zustand Store 设计
interface EditorStore {
  // 画布状态
  canvas: {
    offset: Point;
    zoom: number;
    gridSize: number;
    snapToGrid: boolean;
  };
  // 选择状态
  selection: {
    selectedIds: string[];
    selectionBox: Rect | null;
    clipboard: SymbolInstance[];
  };
  // 编辑状态
  editing: {
    activeTool: ToolType;       // select, wire, place, pan
    placingSymbol: SymbolDefinition | null;
    wireInProgress: WireDraft | null;
  };
  // 撤销/重做
  history: {
    undoStack: Command[];
    redoStack: Command[];
  };
  // 动作
  actions: {
    setTool: (tool: ToolType) => void;
    selectElement: (id: string, additive: boolean) => void;
    moveElements: (ids: string[], delta: Point) => void;
    deleteElements: (ids: string[]) => void;
    undo: () => void;
    redo: () => void;
  };
}

// 命令模式（撤销/重做）
interface Command {
  type: string;
  execute: () => void;
  undo: () => void;
  timestamp: number;
}
```

---

## 8. 安全架构设计

### 8.1 纵深防御模型

```
Layer 1 - 传输安全:
├─ TLS 1.3（强制，最低cipher: AES-256-GCM）
├─ mTLS（服务间通信，Istio Sidecar）
├─ WebSocket over TLS（WSS）
└─ 证书自动化（Let's Encrypt / 企业CA集成）

Layer 2 - 认证与授权:
├─ 用户认证: JWT (RS256, 15min access + 7d refresh)
├─ API密钥: 32字节随机，SHA-256存储
├─ MFA支持: TOTP / WebAuthn
├─ RBAC: admin > engineer > viewer
├─ ABAC: 基于项目/资源/操作属性的细粒度控制
└─ SSO集成: SAML 2.0 / OIDC（Enterprise版）

Layer 3 - 应用安全:
├─ API限流: Token Bucket算法（100 req/min/user）
├─ 输入验证: JSON Schema验证 + SQL注入防护
├─ XSS防护: CSP Header + React自动转义
├─ CSRF防护: SameSite Cookie + Double Submit Token
├─ 文件上传: 白名单类型 + 病毒扫描 + 大小限制
└─ 速率限制: 登录5次/分钟/账号

Layer 4 - 数据安全:
├─ 静态加密: AES-256-GCM（数据库TDE）
├─ 字段级加密: 敏感配置（如PLC密码）
├─ 密钥管理: HashiCorp Vault / KMS
├─ 数据脱敏: 导出时自动脱敏PII
├─ 审计日志: 所有操作记录（不可变日志）
└─ 备份加密: 异地备份 + AES-256

Layer 5 - 基础设施安全:
├─ 网络隔离: VPC + 安全组（最小权限）
├─ WAF: ModSecurity / Cloudflare
├─ DDoS防护: CDN + 流量清洗
├─ 容器安全: 非root运行 + 只读文件系统 + seccomp
├─ 镜像扫描: Trivy（CI管道中）
├─ 依赖扫描: Dependabot + Snyk
└─ 渗透测试: 季度第三方渗透测试
```

### 8.2 工业特有安全考量

```
PLC通信安全:
├─ OPC UA Security Policy: Basic256Sha256（强制）
├─ 单向数据二极管: 硬件隔离（SIL3场景可选）
├─ PLC程序签名: 数字签名防篡改
├─ 固件完整性: 安全启动 + 固件哈希验证
└─ 物理访问: 机柜门禁记录集成

数据主权:
├─ 数据分级: 公开/内部/机密/绝密
├─ 数据驻留: 按地域存储（GDPR/中国数据安全法合规）
├─ 数据导出: 审计审批流程
└─ 跨境传输: 加密 + 法律审查
```

### 8.3 审计日志设计

```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    actor_id UUID,
    actor_type VARCHAR(32),       -- user, api_key, service, system
    action VARCHAR(64) NOT NULL,  -- create, read, update, delete, execute, login, logout
    resource_type VARCHAR(64),    -- project, schematic, program, user, config
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    status VARCHAR(16),           -- success, failure, denied
    error_message TEXT
);

CREATE INDEX idx_audit_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX idx_audit_actor ON audit_logs (actor_id);
```

---

## 9. 技术选型详表

| 技术域 | 选型 | 版本 | 选型理由 |
|--------|------|------|---------|
| **前端框架** | React + TypeScript | 18.3 / 5.5 | 生态成熟，适合复杂编辑器场景 |
| **图形渲染** | Canvas + SVG + PixiJS(可选) | — | Canvas批量渲染，SVG精确交互 |
| **拖拽引擎** | dnd-kit + 自研电气规则 | 6.x | 基础拖拽+电气约束叠加 |
| **代码编辑器** | Monaco Editor | 0.47 | VS Code内核，ST语法高亮 |
| **协同编辑** | Yjs (CRDT) | 13.x | 无冲突复制数据类型 |
| **后端-核心** | Go | 1.23 | 高并发，低内存，单一二进制 |
| **后端-AI** | Python | 3.12 | 丰富ML/DL生态 |
| **API网关** | APISIX | 3.x | 高性能，插件化，gRPC代理 |
| **服务通信** | gRPC + NATS | — | 同步RPC + 异步事件 |
| **MQTT Broker** | EMQX | 5.x | 百万级连接 |
| **时序数据库** | TDengine | 3.x | 百万写入/s，10-20x压缩 |
| **关系数据库** | PostgreSQL | 16.x | JSONB支持，成熟稳定 |
| **缓存** | Redis | 7.2 | 实时缓存，会话管理 |
| **向量数据库** | Milvus | 2.4 | RAG检索，PLC指令库向量化 |
| **对象存储** | MinIO / S3 | — | 文件导出，备份 |
| **LLM框架** | LangChain / LangGraph | 0.3 | AI管道编排，多Agent工作流 |
| **LLM推理** | vLLM (私有化) | 0.6 | PagedAttention高效推理 |
| **形式化验证** | Z3 Theorem Prover | 4.13 | SMT求解，安全属性验证 |
| **容器编排** | Kubernetes + Helm | 1.30 | 弹性伸缩，灰度发布 |
| **边缘运行时** | K3s / Docker Compose | — | 轻量K8s适合边缘 |
| **CI/CD** | GitLab CI + ArgoCD | — | GitOps持续交付 |
| **监控** | Prometheus + Grafana + Loki | — | 指标+可视化+日志 |
| **追踪** | OpenTelemetry + Jaeger | — | 分布式链路追踪 |

---

## 10. 部署架构

### 10.1 SaaS云端部署（中小型企业）

```
                    ┌─────────────────────────────┐
                    │     CloudFront CDN           │
                    │  (静态资源 + WAF)             │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │   Application Load Balancer  │
                    │   (TLS Termination)          │
                    └──┬──────────┬──────────┬────┘
                       │          │          │
           ┌───────────▼──┐ ┌────▼──────┐ ┌▼──────────┐
           │  Web Frontend │ │ API Gateway │ │ WebSocket  │
           │  (S3+CF)      │ │ (APISIX)    │ │ Gateway    │
           └───────────────┘ └──┬──────┬──┘ └────────────┘
                                │      │
              ┌─────────────────▼──┐ ┌─▼──────────────────┐
              │  Go Core Services  │ │ Python AI Services  │
              │  (K8s Deployment)  │ │ (K8s Deployment)     │
              └────────────────────┘ └──────────────────────┘
                       │
              ┌────────▼──────────┐ ┌──────────────────────┐
              │  PostgreSQL RDS   │ │  TDengine Cloud       │
              │  (Multi-AZ)       │ │  (时序数据)           │
              └───────────────────┘ └──────────────────────┘
```

### 10.2 混合部署（中大型企业）

**边缘侧（工厂现场）：**
- K3s单节点 / ARM工控机
- NeuronEX协议网关（200+工业协议）
- TDengine Edge（本地时序缓存，7天）
- 本地规则引擎（紧急停机逻辑）
- 安全隧道：MQTT over TLS → 云端

**云端侧：**
- AI引擎（代码生成、逻辑分析）
- TDengine Cloud（长期数据湖）
- 可视化仪表盘、项目管理与协同

### 10.3 私有化部署（高安全行业）

**全本地部署包：**
- Docker Compose一键部署 / K8s Helm Chart
- vLLM + Qwen 3 / Llama 4 私有化AI引擎
- MinIO本地对象存储
- 完全离线：无需外网连接
- 支持国产化：ARM（鲲鹏/飞腾）+ 麒麟OS + 达梦数据库

---

## 11. 测试策略

### 11.1 测试金字塔

```
                    ╱─────╲
                   ╱  E2E  ╲            20-30个核心流程
                  ╱  测试   ╲           (Playwright)
                 ╱──────────╲
                ╱  集成测试   ╲         200+ API测试
               ╱  (API + DB)  ╲        (Go test + pytest)
              ╱────────────────╲
             ╱    单元测试       ╲      80%+ 覆盖率
            ╱  (函数/组件级别)   ╲     (Vitest + Go + pytest)
           ╱──────────────────────╲
```

### 11.2 专项测试

| 测试类型 | 工具 | 频率 | 目标 |
|---------|------|------|------|
| AI代码生成准确性 | 人工评估 + CodeBLEU | 每次模型更新 | ≥95% |
| 电路图渲染性能 | Lighthouse + 自研benchmark | 每次PR | 1000元件≥30fps |
| PLC通信可靠性 | 物理PLC测试台 | 每周 | 24h无丢包 |
| 安全渗透测试 | OWASP ZAP + 第三方 | 每季度 | 0高危漏洞 |
| 故障恢复 | Chaos Mesh | 每月 | RTO<5min, RPO<1min |
| 兼容性 | BrowserStack | 每次发布 | Chrome/Edge/Firefox/Safari |
| 负载测试 | k6 | 每次大版本 | 1000并发P95<2s |

### 11.3 AI模型评估体系

```
AI输出质量评估框架：

          ├──────────┬──────────┬──────────┬─────────────┤
          │          │ 自动化    │ 自动化    │ 人工评估     │
          │ 维度      │ 指标      │ 方法      │ (抽样)       │
          ├──────────┼──────────┼──────────┼─────────────┤
          │ 语法正确性│ PASS/FAIL │ IEC编译器  │ 代码审查    │
          │ 逻辑正确性│ BLEU-4   │ 仿真验证  │ 对错判定    │
          │ 代码风格  │ CodeBLEU │ Linter    │ 可读性评分  │
          │ 安全性    │ 规则通过率 │ 形式化验证│ 安全审查    │
          │ 效率      │ 指令数    │ 性能剖析  │ 优化建议    │
          │ 可维护性  │ 圈复杂度  │ 静态分析  │ 文档完整性  │
          └──────────┴──────────┴──────────┴─────────────┘

持续改进循环:
数据收集 → 标注 → 微调 → A/B测试 → 部署 → 监控 → 数据收集
```

---

## 12. 实施路线图

### 12.1 分阶段计划

```
Phase 1 ─── 基础平台搭建 (第1-4个月)
│
├─ Month 1-2: 前端框架 + Canvas引擎 MVP
│   ├─ React应用骨架 + 路由 + 主题系统
│   ├─ Canvas 2D渲染引擎（符号加载/渲染/选择）
│   ├─ dnd-kit集成 + 基础拖拽
│   └─ 项目管理CRUD + PostgreSQL Schema
│
├─ Month 3: 电路图编辑器核心功能
│   ├─ 连线工具（贝塞尔曲线 + 正交路由）
│   ├─ 属性面板 + 撤销/重做（命令模式）
│   ├─ 符号库浏览器（IEC 60617基础200符号）
│   └─ DXF导出
│
└─ Month 4: PLC编程编辑器 MVP
    ├─ LD梯形图编辑器（Canvas拖拽横档）
    ├─ ST结构化文本编辑器（Monaco集成）
    ├─ PLC型号数据库（6品牌核心型号）
    └─ 基础项目文件树

Phase 2 ─── AI引擎 v1.0 (第5-8个月)
│
├─ Month 5-6: AI基础架构 + 需求解析
│   ├─ Python AI服务部署（LangChain + LLM API）
│   ├─ RAG管道（Milvus + PLC指令库向量化）
│   ├─ 需求解析引擎（NLP→结构化ControlSpec）
│   └─ ControlSpec JSON Schema定义与验证
│
├─ Month 7: 代码自动生成
│   ├─ 自然语言→梯形图生成
│   ├─ 需求→结构化文本生成
│   ├─ 模板匹配引擎
│   └─ IEC编译器集成（语法验证）
│
└─ Month 8: AI辅助 + 反馈闭环
    ├─ AI代码补全（Monaco Ghost Text流式SSE）
    ├─ 静态代码分析（5类错误检测）
    ├─ AI Chat助手面板
    └─ 反馈收集系统（评分/修正记录）

Phase 3 ─── 数据平台与高级AI (第9-14个月)
│
├─ Month 9-10: 通信与数据平台
│   ├─ 协议网关（OPC UA / MQTT / Modbus）
│   ├─ TDengine集成 + 时序数据采集
│   ├─ 实时数据仪表盘（ECharts）
│   └─ 边缘计算节点v1
│
├─ Month 11-12: 高级AI能力
│   ├─ 逻辑关系分析（Petri网+依赖分析）
│   ├─ 形式化验证（Z3集成）
│   ├─ 仿真测试（软PLC运行时）
│   ├─ 错误自动修正引擎
│   └─ 跨品牌代码转换（AB↔Siemens↔三菱）
│
└─ Month 13-14: 协同编辑 + AI V2
    ├─ Yjs协同编辑（电路图+ST程序）
    ├─ AI需求→电路自动设计
    ├─ 多Agent协同代码生成
    ├─ 数字孪生基础集成
    └─ AI模型微调V1

Phase 4 ─── 产品化与生态建设 (第15-18个月)
│
├─ Month 15-16: 企业级功能
│   ├─ 权限管理（RBAC+ABAC）
│   ├─ 三种部署模式全支持
│   ├─ SSO集成 + 审计日志
│   └─ 安全认证准备
│
├─ Month 17: 生态与发布
│   ├─ 插件市场（驱动/Symbol/模板）
│   ├─ 开放API文档 + SDK
│   ├─ 用户文档 + 交互式教程
│   └─ 性能优化（P95<2s, 30fps+）
│
└─ Month 18: 发布与持续运营
    ├─ GA正式发布
    ├─ 社区建设（论坛/GitHub）
    ├─ 付费计划上线
    └─ 客户成功团队组建
```

### 12.2 团队配置

| 角色 | 人数 | 职责 |
|------|-----|------|
| 产品经理 | 1 | 需求定义、优先级、用户调研 |
| 技术架构师 | 1 | 总体架构设计、技术决策 |
| 前端高级 | 2 | React架构、Canvas/SVG渲染引擎 |
| 前端 | 2 | 编辑器UI、仪表盘 |
| 后端高级 (Go) | 2 | 核心服务、编译器、协议网关 |
| AI工程师 | 3 | LLM集成、代码生成、逻辑分析 |
| 嵌入式/边缘 | 1 | 边缘节点、协议驱动 |
| DevOps | 1 | CI/CD、部署、监控 |
| QA | 2 | 自动化测试、PLC硬件测试台 |
| 技术文档 | 1 | API文档、用户手册、教程 |
| 安全工程师 | 1 (兼职) | 安全审计、渗透测试 |
| **合计** | **17** | |

---

## 13. 竞争优势分析

| 能力维度 | 本系统 | Siemens TIA V21 | CODESYS | Rockwell Studio 5000 | PLC Copilot |
|---------|--------|-----------------|---------|---------------------|-------------|
| **跨品牌兼容** | ★★★★★ 6+品牌 | ★ 仅西门子 | ★★★ 硬件无关 | ★ 仅AB | ★★ 部分 |
| **拖拽电路图设计** | ★★★★★ | ★ | ★ | ★ | — |
| **AI需求解析** | ★★★★★ NL→电路+程序 | ★★ Copilot仅代码 | — | ★★★ AI工程化(2026) | — |
| **AI代码生成** | ★★★★★ 多语言 | ★★★ SCL | — | ★★★ LD/ST | ★★★ 梯形图 |
| **AI逻辑分析** | ★★★★★ Petri网+形式化 | ★★ 基础 | — | ★★ 基础 | ★★ 代码审查 |
| **AI错误修正** | ★★★★★ | ★ 仅检测 | — | ★★ 建议 | ★★ 检测+建议 |
| **数据采集** | ★★★★★ 20+协议 | ★★★ OPC+PROFINET | ★★ 第三方 | ★★★ OPC+EIP | — |
| **边缘计算** | ★★★★★ 内置 | ★★★ 另购 | — | ★★ 另购 | — |
| **协同编辑** | ★★★★ CRDT | ★★★ Multi-user | — | ★★ 有限 | — |
| **部署灵活性** | ★★★★★ SaaS/混合/私有 | ★★ 仅本地 | ★★ 仅本地 | ★★ 仅本地 | ★★★ SaaS |
| **开放性** | ★★★★★ API+SDK | ★ 封闭 | ★★★★ 开放 | ★ 封闭 | ★ 封闭 |
| **国产化适配** | ★★★★★ | ★★ 有限 | ★★ 有限 | ★ 受限 | — |

**核心差异化：** 唯一同时覆盖"电气原理图设计 + PLC编程 + AI辅助 + 数据采集"全链路的统一平台，填补了电气CAD工具与PLC编程软件之间的市场空白。

---

## 14. 风险与应对

| 风险 | 影响 | 概率 | 应对策略 | 缓解后 |
|------|------|------|---------|--------|
| AI代码准确率不足 | 高 | 中 | 三层验证+人工审核+持续微调+模板优先 | 中 |
| PLC厂商协议兼容 | 高 | 中 | 优先开放协议+逆向工程+厂商合作 | 中 |
| 实时性不满足 | 中 | 低 | 边缘计算处理实时任务+AI仅离线分析 | 低 |
| 数据安全合规 | 高 | 低 | 私有化部署+TLS 1.3+字段加密+SOC2/ISO27001 | 低 |
| 用户学习成本 | 中 | 中 | 交互式教程+模板库+AI向导+兼容操作习惯 | 低 |
| LLM供应商依赖 | 中 | 中 | 模型无关架构+开源私有化+缓存策略 | 低 |
| 市场规模不足 | 中 | 中 | MVP验证+细分切入+厂商合作+SaaS低门槛 | 中 |
| 竞品快速跟进 | 中 | 高 | 18月先发窗口+数据网络效应+专利布局 | 中 |

---

## 15. 参考文献

1. **Siemens, TIA Portal V21 Engineering Copilot** — 集成于TIA Portal的生成式AI工程助手
   https://controlbyte.tech/blog/tia-portal-v21-new-features/

2. **Schneider Electric, Industrial Copilot (2025)** — EcoStruxure平台AI代码生成，开发时间缩短30-50%
   https://blog.se.com/digital-transformation/artificial-intelligence/2025/11/14/

3. **Beckhoff, TwinCAT CoAgent** — 双版本AI代理，代码建议+I/O配置+故障诊断
   https://www.beckhoff.com.cn/zh-cn/company/news/

4. **Rockwell Automation, AI-Orchestrated Factory Engineering (2026)** — 数字孪生+AI代码生成+仿真验证
   https://www.rockwellautomation.com/en-tr/company/news/press-releases/

5. **CODESYS Development System** — 硬件无关IEC 61131-3开发平台
   https://us.codesys.com/products/engineering/development-system/

6. **OPC UA IEC 62541-1:2025** — 新一代工业通信标准

7. **EMQX + MQTT工业物联网方案** — 127台PLC部署，延迟500ms→50ms，可用性99.99%

8. **Spec2Control (ACM 2025)** — 自然语言→PLC/DCS控制逻辑，正确率超97%
   https://dl.acm.org/doi/10.1145/3786583.3786897

9. **AutoPLC (arXiv 2024)** — 多智能体框架，自然语言→IEC 61131-3 ST代码
   https://arxiv.org/pdf/2412.02410v1

10. **PLC Copilot** — 自然语言生成梯形图，代码审查，跨平台翻译
    https://plccopilot.com/blogs/ai-for-plc-programming

11. **Wipro PARI + AWS Bedrock** — PLC代码生成3-4天→10分钟，准确率85%
    https://aws.amazon.com/blogs/machine-learning/

12. **MuFBDTester & ST-Petri** — 基于变异的FBD测试生成，Petri网ST形式化语义

13. **NVIDIA Cosmos-Reason1-7B** — 多PLC协同场景安全逻辑推理

14. **PLCs.ai** — AI驱动PLC逻辑分析平台，PackML状态机分析
    https://www.plcs.ai/

15. **Snap PLC** — 图片到逻辑生成器，控制柜照片→梯形图
    https://www.snapplc.com/

16. **TDengine** — 国产高性能时序数据库，百万写入/s，10-20x压缩比

17. **IEC 61131-3:2013** — 可编程控制器编程语言国际标准

18. **IEC 60617** — 电气简图用图形符号国际标准

19. **ISA-88** — 批处理控制国际标准

20. **PackML (ISA-TR88.00.02)** — 包装机械语言标准

---

> **文档说明：** 本文档为AI-PLC智能控制系统V2.0详尽技术方案，涵盖系统架构、功能模块、AI引擎、数据库设计、API规范、安全架构、测试策略及实施路线图等完整技术内容。方案基于2026年7月最新行业态势和技术栈编写。

> **作者：** AI-PLC 技术团队 | **日期：** 2026-07-30
