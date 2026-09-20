# AI-PTS 完善设计方案

> 基于「发布 PDF + 产品开发架构方案 + 专项工具集成方案」三份文档与**当前代码真相**的差距分析，结合国际前沿 AI 渗透测试系统的功能与设计理念，形成的 AI-PTS 深化设计方案。
>
> 编制日期：2026-09-19

---

## 一、执行摘要

AI-PTS 当前是一个**可运行的自包含 Python 桌面应用（PyQt GUI + CLI）**，已打通「端口/服务/版本/OS 扫描 → CVE 精确匹配 → Web 规则扫描 → AI 单次规划 → 工具执行 → 报告」的**单次流水线**，且 getshell/提权/横向三类专项执行器（impacket/msf/secretsdump/linpeas/netexec/bloodhound/mimikatz）已真实落地，安全护栏（白名单 fail-closed、人工确认、凭据打码）扎实。

但对照三份文档所宣称的目标，存在一条明确的**「愿景—方案—现状」三级落差**：

- **发布 PDF 宣称**：SecLLM + 多智能体（MAS）双引擎、攻击树模型、RAG 知识库 + AI 自纠正迭代、业务逻辑漏洞检测（六大场景）、语义级通用漏洞检测、全流程自主渗透、自然语言交互、7×24 多任务并行。
- **架构方案规划**：ReAct 推理引擎、知识图谱（Neo4j）、RAG（Milvus）、ML 模型（漏洞预测/资产识别/攻击链预测）、K8s 分布式部署。
- **代码真相**：AI 侧是**单次 LLM 调用 + JSON 输出**，无 RAG、无记忆、无多智能体、无攻击树、无自纠正、无 agentic 回馈环；漏洞检测是**规则/Payload 型 DAST**，非语义级；业务逻辑检测、自然语言交互、7×24 调度**完全缺失**。

本方案的核心结论：**AI-PTS 不缺"扫描"和"工具执行"，缺的是"会思考、能记忆、可迭代"的智能中枢**。完善方向应聚焦于把现有的单次编排升级为「多智能体 + 记忆 + RAG + 攻击树 + 安全护栏」的自主渗透闭环，并补齐业务逻辑与语义级检测这两块行业公认最难、也最有差异化的能力。

---

## 二、三份文档内容提炼

### 2.1 《AI-PTS 产品开发架构方案》（2026-03-08）

| 维度 | 规划内容 |
|---|---|
| 分层架构 | 表现层（Web 控制台/API 网关/CLI/报告）→ 业务逻辑层（AI 推理/扫描调度/漏洞分析/知识图谱/报告/权限）→ 核心引擎层（LLM + ML）→ 工具能力层（Nmap/SQLi/目录爆破/弱口令/XSS/CSRF/API/无线）→ 数据存储层（PostgreSQL/Redis/Milvus/对象存储） |
| AI 引擎 | ReAct（Reasoning + Acting）模式，`planner.create_plan` → `executor.execute_plan` → `analyzer.generate_report` |
| 知识图谱 | 实体层（漏洞/资产/攻击手段/工具）+ 关系层 + 应用层（攻击路径推荐/利用链生成/优先级排序/防御建议） |
| RAG | Milvus + BGE/M3E 向量化，检索 exploit 信息、攻击链建议 |
| ML 模型 | 漏洞预测、资产识别、攻击链预测 |
| 技术栈 | GPT-4/Claude-3/Qwen、Milvus/Qdrant、Neo4j/TuGraph、Nmap/Metasploit/Hydra/Semgrep/CodeQL |
| 部署 | Nginx + Kubernetes 集群（GPU 池、沙箱隔离、流式处理） |
| 路线图 | MVP(1-3月)→V1.0 RAG(4-6月)→V2.0 知识图谱(7-9月)→V3.0 自主学习(10-12月) |

### 2.2 《AI-PTS 渗透测试专项工具集成方案》（2026-09）

- **目标**：把 getshell、提权、横向移动三类专项能力集成，形成「扫描 → AI 规划攻击路径 → 工具执行 → 结果回喂 AI → 迭代/续接 → 报告」闭环。
- **安全线**：`require_confirmation` 人工确认闸门 + 目标白名单。
- **复用挂载点**：`core/workflow.py`（BaseExecutor/ExecutorRegistry/ExploitWorkflow）、`core/ai_analyzer.py`（plan_exploit_path→ExploitPlan）、`config.py`（exploit 安全闸门）。
- **新增模块**：`core/executors/`（base/getshell/privesc/lateral）+ `core/orchestrator.py`（agentic loop：每步输出回喂 AI 决策）。
- **工具选型**：impacket（首选）、Metasploit msfrpc（重）、LinPEAS/WinPEAS、secretsdump、netexec、BloodHound、Mimikatz（慎）。
- **分阶段**：Phase 0 架构基础 → Phase 1 getshell → Phase 2 提权 → Phase 3 横向。

### 2.3 《渗透测试新纪元——AI-PTS 新版本发布》（绿盟科技公众号，2026-04-16）

| 宣称能力 | 关键描述 |
|---|---|
| 技术底座 | 风云卫大模型（SecLLM）+ 多智能体系统（MAS）双引擎 |
| 多智能体架构 | 攻击树模型构建**任务决策智能体** + **工具调度智能体** + **环境感知分析智能体** = "AI 虚拟项目组" |
| 自主进化 | 借鉴 autoresearch 框架，持续自我迭代优化 |
| 核心能力一 | AI 驱动业务场景漏洞检测：功能测绘 → 攻击树威胁建模 → LLM+RAG 生成安全测试用例 → 端到端业务逻辑漏洞闭环；覆盖**登录认证/用户注册/密码管理/信息查询维护/用户注销/支付转账**六大场景 |
| 核心能力二 | RAG 知识库（漏洞样本/CWE/Web 测试用例/历史报告）+ AI 自纠正迭代：Web 搜索扩充、LLM 相关性过滤、测试用例评分迭代 |
| 核心能力三 | 语义级通用漏洞检测：Transformer 语义特征学习，**提取智能体/预验证智能体/防御机制检测智能体**，覆盖 SQLi/XSS/SSRF/XXE/路径遍历；参数生成智能体批量生成 Payload + 重放模块并行验证 |
| 全流程渗透 | 漏洞关联分析、渗透路径推理、动态对抗调整；信息收集→漏洞探测→漏洞利用→权限提升→横向移动 |
| 核心价值 | 自然语言交互、多任务并行 7×24、降本增效 |

---

## 三、当前系统现状盘点（代码真相）

通过逐文件审查，实际实现状态如下：

### 3.1 已实现（真实落地）

| 模块 | 文件 | 实际能力 |
|---|---|---|
| 扫描引擎（自包含 vendored） | `core/scanner.py` + `vendor/scanner_engine.py` | 端口/服务/版本/OS 扫描、CVE 精确匹配（23MB 库）、弱口令爆破（73K 字典）、蜜罐检测、设备指纹、供应链、风险评分、PoC 验证、去重、富化 |
| Web 规则扫描 | `vendor/web_vuln_scanner.py` | 约 30 类规则/Payload 型检测：SQLi/XSS/命令注入/SSRF/XXE/路径遍历/LFI/RFI/SSTI/CRLF/LDAP/XML/CSRF/CORS/开放重定向/JWT/IDOR/NoSQL 等 |
| AI 分析（单次） | `core/ai_analyzer.py` | Claude 单次调用：扫描结果分析、攻击路径规划（`plan_exploit_path`）、Payload 建议（仅防御性）、可利用性验证、影响评估；含 CC Switch 通道回退、JSON 容错解析 |
| 工作流引擎 | `core/workflow.py` | BaseExecutor/ExecutorRegistry/ExploitWorkflow 单次执行、暂停/恢复/取消、失败不中断链 |
| 专项执行器（真实 subprocess） | `core/executors/{base,getshell,privesc,lateral}.py` | impacket(wmiexec/psexec/smbexec/atexec)、msfconsole(Docker 回退)、secretsdump、LinPEAS、netexec、bloodhound、mimikatz |
| 编排器 | `core/orchestrator.py` | 扫描→规划→执行单次串联，注册真实执行器 + 人工验证占位（sql_injection/xss/auth_bypass/info_disclosure） |
| 安全护栏 | `config.py` + `core/executors/base.py` | 白名单 fail-closed、`require_confirmation`、凭据回调、命令打码（`_redact_cmd`）、主机名校验（防命令注入）、工具可用性检查 |
| 报告 | `core/report_builder.py` | HTML 渗透测试报告 |
| 工具库 | `core/tool_library.py` | **静态目录**（Nmap/sqlmap/Metasploit/BloodHound 等 30+ 工具的中文说明），仅供展示，未接入执行 |
| GUI | `gui/main_window.py` 等 | PyQt 三栏布局，扫描/攻击详情/漏洞库/工具库/人工复核/报告中心/设置菜单，扫描选项（版本/OS/Web/弱口令）、NVD API Key |

### 3.2 未实现（方案/愿景有，代码无）

| 能力 | 方案出处 | 现状 |
|---|---|---|
| 多智能体（MAS） | 发布 PDF / 架构方案 | ❌ 无。AI 是单次调用，无 Planner/Recon/Exploit/Validator 等角色 |
| ReAct / agentic loop | 架构方案 / 工具集成方案 | ❌ 无。`orchestrator.py` 明写"Phase 0 先打通单次闭环"，未实现"每步输出回喂 AI 决策" |
| RAG / 向量检索 | 架构方案 / 发布 PDF | ❌ 无。全局搜索 RAG/Milvus/embedding 无命中 |
| 知识图谱 | 架构方案 / 发布 PDF | ❌ 无 |
| 攻击树模型 | 发布 PDF | ❌ 无（仅有确定性关键词兜底路由 `ROUTE_TABLE`） |
| AI 自纠正迭代 | 发布 PDF | ❌ 无 |
| 业务逻辑漏洞检测（六大场景） | 发布 PDF | ❌ 无 |
| 语义级通用漏洞检测 | 发布 PDF | ❌ 无（当前是规则/Payload 型 DAST） |
| 自然语言交互 | 发布 PDF | ❌ 无（GUI 是表单式，CLI 是问答式） |
| 7×24 多任务并行调度 | 发布 PDF | ❌ 无（单任务同步） |
| ML 预测模型 | 架构方案 | ❌ 无 |
| 代码审计（Semgrep/CodeQL） | 架构方案 | ❌ 无（仅工具库文案） |
| SQLi/XSS/CSRF 等自动化利用 | 架构方案 | ⚠️ 部分（检测有规则引擎，利用靠"人工验证"占位） |
| 分布式/K8s 部署 | 架构方案 | ❌ 无（桌面单机应用，且需保持自包含） |

### 3.3 差距根因

1. **愿景超前于工程**：发布 PDF 描述的是绿盟 SecLLM+MAS 的企业级产品，而本仓库是**自包含桌面应用**，两者架构层级完全不同；架构方案里的 Milvus/Neo4j/K8s 重基础设施与"自包含、不引用兄弟项目、exe 打包部署"的实际约束冲突。
2. **AI 侧被当成"调用一次出结果"的黑盒**，而非"可循环决策的智能体"——这是最核心的落差。
3. **工具集成方案落地最好**（executors + orchestrator 均已实现），但它在 Phase 0 就停在了"单次闭环"，agentic loop 未继续推进。

---

## 四、国际先进 AI 渗透测试系统调研

> 调研聚焦 2024–2026 学术与产业前沿，提炼可复用的功能与设计理念。

### 4.1 学术前沿：多智能体 + 记忆 + 安全护栏已成标准范式

| 系统 | 架构要点 | 可借鉴设计 |
|---|---|---|
| **AgentPentestAI** | Recon/Knowledge/Exploit/Memory/Validator 五智能体 + 效用调度 | 子任务完成率 68%（vs PentestGPT 52%），幻觉 12%→5%；回滚验证、deny-list、沙箱 |
| **PenExpert** | 多智能体混合 LLM-专家，MITRE ATT&CK 能力矩阵 + RAG Payload 生成 | 打通五层网络端到端 |
| **AutoSecAgent** | 递归记忆嵌入（RME）+ 实时 RAG（NVD/CVE）+ Agent Zero 编排 | 上下文丢失错误降 34% |
| **AutoSec-Agent** | Planner-Summarizer-Validator（PSV）循环 + 动态记忆压缩 + **双层预执行安全校验** + 沙箱 | 不安全命令降 87%、幻觉降 62% |
| **Co-RedTeam** | 领域知识 + 代码分析 + 执行落地迭代推理 + 长期记忆 | 利用成功率 >60% |
| **层次化自主框架** | Planner 全局分解 + **MCP 有向无环图（DAG）记忆** | 解决长时域任务与上下文超载 |
| **PTFusion** | 半去中心化多智能体 + MCP 工具调用 + 动态知识图谱 | Web 渗透稳定性和性能优于 PentestGPT |

**共性设计理念**：① 角色分解（Planner/Recon/Exploit/Memory/Validator/Summarizer）；② 记忆与上下文管理（RAG、递归记忆、DAG 记忆、动态知识图谱）；③ 工具接地（MCP）；④ 安全治理（沙箱、deny-list、预执行校验、回滚、审计、速率限制）。

### 4.2 标志性开源系统

| 系统 | 架构 | 启示 |
|---|---|---|
| **PentestGPT**（USENIX Sec'24） | Reasoning（推导攻击树 PTT）+ Generation（生成工具调用）+ Parsing（解析输出）三模块 | 攻击树 PTT 是核心；半自主 |
| **HackSynth**（2024） | Planner-Summarizer 双模块闭环，容器化 Kali + 防火墙隔离 | 上下文压缩（Summarizer 不拼接全量输出）、CTF 基准 |
| **Vulnhuntr**（ProtectAI） | LLM+SAST：README 摘要→输入面分析→漏洞专项 prompt→**调用链重建**（Jedi 符号解析）→PoC+置信度 | 用静态分析锚定 LLM、降低幻觉，已挖出多个 0day |
| **PentAGI** | Docker 沙箱内多智能体调用 20+ 工具 | 沙箱隔离 + 工具编排 |
| **Strix** | AI 原生自主渗透，自动验证发现并生成可用 PoC | 发现→利用→验证闭环 |
| **HexStrike AI** | 把 LLM 接到 150+ 安全工具的 MCP 服务器 | MCP 是工具接入标准 |

### 4.3 商业平台：以「证据化攻击路径」为核心

| 平台 | 核心设计 | 启示 |
|---|---|---|
| **Horizon3 NodeZero** | 自主把「错误配置 + 弱凭据 + CVE」链成多步攻击路径，证明真实业务影响；CTEM「发现→验证→修复→再验证」循环；2026 扩展 Web 应用与跨域链式攻击 | 攻击路径链式化 + 可验证证据 + 修复闭环 |
| **Pentera** | 无代理真实利用，深耕内网横向/提权/凭据 | 全杀伤链真实利用 |

**关键区别**：BAS（Cymulate/Picus）验证"防御是否拦截"，自动渗透（Pentera/NodeZero）证明"暴露是否可被利用"。AI-PTS 定位应属于后者（自动渗透/验证暴露），应强调**证据化、可复现、修复闭环**。

### 4.4 业务逻辑与语义级检测（AI-PTS 的最大差异化机会）

| 研究/工具 | 方法 | 结论 |
|---|---|---|
| LLM+RAG 分析 HAR | 对 HTTP 流量语义分析业务逻辑漏洞 | PortSwigger BLV Labs 77.7% 覆盖，OWASP Juice Shop 45%，ZAP 约 0% |
| **SAGA**（ACM） | 神经-符号：LLM 语义理解 + AST/依赖/图遍历确定性锚定 | 文档-代码意图对齐 |
| **AUTHSENTRY**（IEEE） | LLM 提取授权敏感端点 + **确定性多角色差分验证**（owner/non-owner 重放） | 抑制幻觉误报，100% 精确/召回 |
| IDOR/BOLA 检测 | 多角色差分验证 | OWASP API Top10 首要风险 |
| Semgrep Agentic Workflows | 确定性污点追踪 + 前沿 LLM 可利用性推理 | 真阳性 3.5× |

**核心洞察**：**纯 LLM 会产生幻觉误报，纯规则无法发现语义/省略型逻辑漏洞；最优解是"LLM 语义理解 + 确定性验证锚定"的神经-符号架构**。这与发布 PDF 宣称的"提取智能体 + 预验证智能体 + 防御机制检测智能体"高度吻合，是 AI-PTS 应重点投入的方向。

### 4.5 评测与基准

- **HackSynth**：PicoCTF + OverTheWire 共 200 题 CTF 基准（含启发式求解脚本）。
- **Cybench**：40 题专业级 CTF；**AutoPenBench**、**SecureCTF-AgentBench**（300 题）、NYU CTF Bench。
- **关键指标**：检测率、利用成功率、多步攻击成功率、误报率、上下文丢失率、不安全命令率。

---

## 五、AI-PTS 完善设计方案（核心）

### 5.1 设计原则

1. **保持自包含**：沿用 SQLite + 嵌入式向量检索（sqlite-vec / FAISS）+ 轻量图（networkx 或自研），**不引入 Milvus/Neo4j/K8s** 等破坏 exe 打包的重依赖。
2. **智能中枢优先**：把投入集中在"会思考、能记忆、可迭代"的编排层，而非再堆扫描规则。
3. **神经-符号混合**：LLM 语义理解 + 确定性验证，抑制幻觉。
4. **安全护栏内建**：任何自主能力必须在白名单 + 确认 + 沙箱 + 审计的边界内运行。
5. **复用现有挂载点**：最大化复用 `workflow.py` / `executors/` / `capabilities.py` / `config.py`。

### 5.2 目标架构

```
┌────────────────────────────────────────────────────────────────────┐
│                        表现层（现有 GUI + 新增自然语言交互）          │
│    三栏 GUI  │  NL 对话框（"帮我测这个登录流程有无逻辑漏洞"）          │
├────────────────────────────────────────────────────────────────────┤
│                    多智能体编排层（核心新增，agentic loop）            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Planner   │ │ Recon     │ │ Exploit   │ │ Privesc/  │ │ Validator │  │
│  │ 任务决策  │ │ 信息收集  │ │ 漏洞利用  │ │ Lateral   │ │ 验证/评分 │  │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘  │
│        │            │            │            │            │        │
│        └────────────┴─── Memory/Summarizer（短期DAG记忆+长期RAG）────┘  │
│                    │ 攻击树引擎（PTT）│ 知识图谱（轻量）│ 安全护栏     │
├────────────────────────────────────────────────────────────────────┤
│                  能力执行层（复用现有，扩展 MCP/更多工具）              │
│  现有 executors（impacket/msf/secretsdump/linpeas/netexec/           │
│    bloodhound/mimikatz） + 新增（sqlmap/Nuclei/Semgrep/ffuf/         │
│    Burp-ZAP）统一走 ToolExecutor / MCP 接口                           │
├────────────────────────────────────────────────────────────────────┤
│                  检测层（规则引擎 + LLM 语义引擎 双引擎）              │
│  vendor/web_vuln_scanner（规则DAST） ⊕ ai_scan_enhancer（语义增强）    │
│  业务逻辑检测器（LLM 语义 + 多角色差分验证）                           │
├────────────────────────────────────────────────────────────────────┤
│                  数据层（自包含）                                     │
│  SQLite（任务/结果/历史）│ sqlite-vec（向量/RAG）│ 报告文件            │
└────────────────────────────────────────────────────────────────────┘
```

### 5.3 多智能体编排设计

以现有 `core/orchestrator.py` 为基座，从单次流水线升级为**有角色分工、可循环决策**的多智能体：

| 智能体 | 职责 | 复用/新增 | 触发方式 |
|---|---|---|---|
| **Planner（任务决策）** | 基于攻击树分解目标，选择下一步子任务，输出结构化 action | 改造 `ai_analyzer.plan_exploit_path` → 逐步规划 | 每轮循环 |
| **Recon（信息收集）** | 调度扫描/枚举工具，收集服务、指纹、目录、参数 | 复用 `scanner.py` + 新增工具 | Planner 决策 |
| **Exploit（利用）** | 调用 getshell/SQLi/XSS 等执行器 | 复用 `executors/` | Planner 决策 |
| **Privesc/Lateral** | 提权/横向移动 | 复用 `executors/privesc.py`、`lateral.py` | 利用成功后 |
| **Validator（验证/评分）** | 判定步骤是否成功、证据是否可靠、是否继续 | 复用 `validate_exploit` + 新增确定性校验 | 每步执行后 |
| **Summarizer（上下文压缩）** | 压缩历史输出，防上下文超载 | 新增（借鉴 HackSynth） | 记忆增长时 |
| **Memory（记忆）** | 读写短期 DAG 记忆与长期 RAG | 新增 | 全程 |
| **Guardian（安全护栏）** | 预执行校验、速率限制、越界拦截 | 复用 `base.py` 护栏 + 新增 | 每次工具调用前 |

### 5.4 Agentic Loop（核心改造）

把 `PenTestOrchestrator.run()` 的单次执行改为** ReAct 循环**（借鉴 HackSynth Planner-Summarizer + PentestGPT PTT）：

```
loop（设 max_steps 上限）：
  1. Memory 汇总当前状态 + Summarizer 压缩历史
  2. Planner 依据攻击树输出下一步 action（exploit_type/tool/参数/目标）
  3. capabilities.route_ai_steps() 确定性兜底路由（现有）
  4. Guardian 预执行校验（白名单/确认/deny-list/速率）
  5. 执行器执行 → StepOutput(result/evidence)
  6. Validator 判定成功/失败，回写 Memory
  7. 成功→Planner 续接（提权/横向/数据获取）；失败→Planner 换工具/参数重试或降级
```

**与现状差异**：现有是"一次规划 N 步、顺序执行完"；改造后是"每步执行后回喂 AI 决策下一步"，实现发布 PDF 宣称的"动态对抗调整"。**挂载点**：`core/orchestrator.py` 新增 `agentic_loop()`，`core/workflow.py` 的 `ExploitWorkflow.execute()` 保留为"单步执行器"复用。

### 5.5 记忆系统（短期 + 长期 + RAG）

| 层 | 实现 | 作用 |
|---|---|---|
| 短期记忆 | 会话内结构化状态（已探测服务、已获取凭据/权限、失败记录），用 DAG 记录攻击进度 | 支撑长时域任务、避免重复 |
| 长期记忆/RAG | `sqlite-vec` 向量库，灌入**历史报告 + CVE/CWE 知识 + 攻击案例 + 测试用例** | 规划时检索相似攻击模式（对应架构方案 RAG、发布 PDF 知识库） |
| 知识图谱（轻量） | networkx 构建「漏洞→利用条件→攻击技术→工具」关系图 | 攻击路径推荐、利用链生成 |

**RAG 数据源**（自包含，随 exe 打包）：本地 `vendor/cve_database.db`（已存在）、积累的 `reports/*.html` 历史报告、内置攻击用例库。**可选联网**：NVD API（已有 Key 配置）增量更新。

### 5.6 攻击树威胁建模

- 引入 PentestGPT 的 **PTT（Penetration Testing Tree）**：Planner 将目标拆解为攻击树节点（如"获取 Web 权限 → SQLi / 文件上传 / 弱口令 / 逻辑漏洞"），每个节点映射到 `capabilities.py` 的能力目录。
- 攻击树节点状态（未尝试/进行中/成功/失败）持久化到记忆，Planner 据此做"最可能成功的下一步"选择（对应发布 PDF"攻击优先级排序"）。
- 复用 `core/capabilities.py` 的 `CAPABILITIES` 目录作为攻击树叶子节点的能力注册表，避免词表漂移。

### 5.7 业务逻辑漏洞检测（差异化重点，借鉴 SAGA/AUTHSENTRY）

新增 `core/business_logic/` 模块，覆盖六大场景（登录认证/注册/密码管理/信息查询维护/注销/支付转账）：

1. **功能测绘**：爬取 + LLM 识别业务流程与授权敏感端点（借 Web 测绘 + 语义理解）。
2. **威胁建模**：LLM 对每场景做风险假设（如"密码找回流程是否可绕过"）。
3. **测试用例生成**：LLM+RAG 生成针对具体业务状态的测试用例（复用发布 PDF"功能测绘→威胁建模→测试用例"思路）。
4. **确定性多角色差分验证**（关键，抑制幻觉）：生成 owner/non-owner 双会话重放，用确定性判据（响应差异/资源归属）确认 IDOR/BOLA/越权/流程绕过，**不依赖 LLM 当"裁判"**。

### 5.8 语义级通用漏洞检测升级（规则 + LLM 双引擎）

现有 `vendor/web_vuln_scanner.py`（规则 DAST）保留为**高召回的第一引擎**，叠加 LLM 语义引擎做**降误报 + 补盲区**：

- **提取智能体**：LLM 从请求/响应中提取注入点、上下文、数据库/模板引擎线索。
- **预验证智能体**：对规则引擎命中项做语义判定（真漏洞/误报），降低误报率。
- **防御绕过检测**：识别编码混淆、语法变形、WAF 绕过空间（对应发布 PDF"语义泛化"）。
- **参数生成智能体**：批量生成多样化 Payload（编码/时间盲注/模板注入），重放模块并行验证。
- 落点：增强现有 `vendor/ai_scan_enhancer.py`，而非重写扫描器。

### 5.9 工具集成深化

- **补齐利用面**：在 `core/executors/` 新增 `sqli.py`（sqlmap）、`xss.py`、`web_exploit.py`（Nuclei/Burp 脚本）、`code_audit.py`（Semgrep，借鉴 Vulnhuntr 的"静态分析锚定 LLM + 调用链重建"做代码审计）。
- **统一接口**：保持 `ToolExecutor`（`base.py`）为唯一执行器基类；可选接入 **MCP** 作为工具接入标准（对应 HexStrike 范式，便于未来扩展 150+ 工具）。
- **能力目录同步扩展**：把 `core/capabilities.py` 中 `manual: true` 的 `sql_injection/xss/auth_bypass/info_disclosure` 逐步替换为真实执行器。

### 5.10 安全与合规护栏（内建）

在现有护栏（白名单 fail-closed、`require_confirmation`、命令打码、主机名校验）基础上增强：

1. **双层预执行校验**（借鉴 AutoSec-Agent）：确定性规则校验 + LLM 语义校验双通过才执行。
2. **deny-list + 危险命令拦截**：高危命令（rm -rf、mimikatz 等）单独评估，默认关闭。
3. **沙箱/隔离**：破坏性动作在容器/受限环境执行；工具路径可配置。
4. **速率限制 + 越界阻断**：对非白名单目标、内网敏感资产自动阻断（复用 `ssrf_guard.py` 思路扩展到执行层）。
5. **全量审计**：每步 action/工具/参数（打码后）/结果入库，可回溯（对应架构方案 AuditLogger）。

### 5.11 评测与基准（保证"智能"可度量）

- **本地靶场**：DVWA、OWASP Juice Shop、Vulhub、自搭 Windows 域环境（现有工具集成方案 Phase 3 已提及）。
- **指标**：检测率、利用成功率、多步攻击成功率、误报率/漏报率、上下文丢失率、不安全命令率、单任务成本/耗时。
- **回归基准**：用固定靶场跑 CI，每次智能层改动对比指标（借鉴 HackSynth/AutoPenBench 的标准化思路）。

### 5.12 报告与持续验证（CTEM 闭环）

- 报告从"漏洞清单"升级为**证据化攻击路径**：链式展示"弱口令 → 拿 shell → secretsdump → 域控"及每步证据（借鉴 NodeZero）。
- 增加**修复验证**：整改后重测，确认攻击路径已闭合（"hack → fix → verify"循环）。
- 支撑**7×24 调度**：内置任务调度器（本地 scheduler），支持定时/周期扫描（对应发布 PDF"全天候在线"）。

### 5.13 技术选型（自包含优先）

| 组件 | 选型 | 理由 |
|---|---|---|
| LLM | 现有 Anthropic/CC Switch 通道（多模型可切换） | 沿用，不新增依赖 |
| 向量检索 | `sqlite-vec` 或 FAISS | 轻量嵌入式，可随 exe 打包 |
| 图 | networkx（或自研邻接表） | 免 Neo4j 重依赖 |
| 任务调度 | APScheduler / 内置 asyncio | 轻量 |
| 工具接入 | 现有 `ToolExecutor` + 可选 MCP | 复用 + 扩展 |
| 沙箱 | Docker（可选，工具集成方案已含 msf Docker 回退） | 破坏性动作隔离 |

---

## 六、实施路线图

> 每阶段标注对现有代码的挂载点，按"智能中枢优先"排序，先打通信环再补能力面。

| 阶段 | 内容 | 挂载点 | 验收标准 |
|---|---|---|---|
| **Phase 0：记忆 + 单智能体 ReAct 闭环** | 短期记忆 + Summarizer；`orchestrator.py` 新增 `agentic_loop()`，把单次执行改为逐步回喂决策 | `core/orchestrator.py`、`core/workflow.py` | 本地靶场跑通"扫描→逐步决策→拿 shell"，每步证据入库 |
| **Phase 1：多智能体角色化** | Planner/Recon/Exploit/Validator/Guardian 分离；攻击树 PTT | `core/ai_analyzer.py` 拆分、新增 `core/agents/` | 多步攻击成功率 > 现有单次；不安全命令率 = 0 |
| **Phase 2：RAG + 知识图谱** | sqlite-vec 向量库灌入历史报告/知识；轻量图谱做路径推荐 | 新增 `core/memory/`、`core/knowledge/` | 规划能引用历史相似攻击模式，上下文丢失率显著下降 |
| **Phase 3：业务逻辑 + 语义检测** | 六大场景业务逻辑检测（多角色差分验证）；LLM 语义引擎增强规则 DAST | 新增 `core/business_logic/`、增强 `vendor/ai_scan_enhancer.py` | Juice Shop 逻辑漏洞覆盖率 > 45%，误报率低于纯 LLM |
| **Phase 4：工具补齐 + 持续验证** | sqlmap/Nuclei/Semgrep 执行器；自然语言交互；7×24 调度；证据化报告 + 修复验证 | `core/executors/`、`gui/`、`core/report_builder.py` | 全链条自主渗透 + 可复现证据 + 定时任务 |

---

## 七、风险与依赖

1. **LLM 幻觉导致误报/危险动作**：用神经-符号（确定性验证锚定）+ 双层预执行校验 + 白名单 fail-closed 兜底。
2. **自主渗透的合规/伦理边界**：仅限授权测试，破坏性动作默认关闭、只读预演，全量审计。
3. **上下文/成本**：长攻击链易超上下文、成本上升——Summarizer 压缩 + 记忆检索控制 token。
4. **自包含 vs 重依赖**：坚持 sqlite-vec/networkx 轻量方案，不引入 Milvus/Neo4j/K8s。
5. **评测可信度**：需持续维护本地靶场与回归基准，避免"演示成功、实战失效"。

---

## 八、结论

AI-PTS 的扫描与工具执行底座已相当扎实，**真正的差距不在"能打"，而在"会想"**。本方案的核心主张是：用**多智能体编排 + 记忆 + RAG + 攻击树**把现有的单次流水线升级为自主迭代的渗透闭环，用**神经-符号混合**补齐业务逻辑与语义级检测这两块最有差异化、也最难的能力，并在**安全护栏内建**的前提下，逐步对齐发布 PDF 所宣称的"AI 替人做渗透"目标。建议按 Phase 0 → 4 顺序推进，优先打通"记忆 + ReAct 闭环"，因为它是一切高阶能力（多智能体、RAG、自纠正）的共同基座。

---

## 参考资料

**学术/开源前沿**
- [HackSynth: LLM Agent and Evaluation Framework for Autonomous Penetration Testing (arXiv:2412.01778)](https://arxiv.org/abs/2412.01778)
- [PentestGPT (USENIX Security 2024)](https://github.com/GreyDGL/PentestGPT)
- [Vulnhuntr (Protect AI) — LLM+SAST 零样本漏洞发现](https://github.com/protectai/vulnhuntr)
- [PenExpert: multi-agent hybrid LLM–expert system](https://www.sciencedirect.com/science/article/abs/pii/S0957417426021937)
- [PTFusion: LLM-driven context-aware knowledge fusion for web pentesting](https://www.sciencedirect.com/science/article/abs/pii/S1566253525007936)
- [AutoSec-Agent: fully autonomous multi-agent pentesting framework](https://link.springer.com/content/pdf/10.1007/s40747-026-02447-5_reference.pdf)
- [Autosecagent: recursive memory + real-time RAG](https://link.springer.com/article/10.1007/s11227-026-08439-z)
- [A Hierarchically Autonomous Multi-Agent Framework with Target-Centered DAG Memory (IEEE)](https://ieeexplore.ieee.org/document/11659006)
- [LLM-Based Intelligent Agents for Cybersecurity: A Tutorial and Survey (IEEE)](https://ieeexplore.ieee.org/document/11580353)
- [SAGA: Detecting Business Logic Flaws by Aligning Documentation and Codebase (ACM)](https://dl.acm.org/doi/pdf/10.1145/3813822.3813855)
- [LLM-Agent Assisted Black-Box Detection of IDOR/BOLA via Multi-Role Differential Validation (IEEE)](https://ieeexplore.ieee.org/document/11634569)
- [Semgrep Agentic Workflows](https://app.semgrep.dev/blog/2026/introducing-semgrep-agentic-workflows-automate-deep-vulnerability-hunting-at-scale/)

**开源工具**
- [Strix — AI 原生自主渗透框架](https://github.com/usestrix/strix)
- [PentAGI — 自主多智能体渗透测试](https://github.com/vxsecurity/PentAGI)
- [HexStrike AI — 150+ 安全工具的 MCP 服务器](https://github.com/vsevex/hexstrike)

**商业平台 / 理念**
- [Horizon3 NodeZero — 自主渗透与 CTEM](https://horizon3.ai/news/press-release/nodezero-webapp-launch/)
- [Horizon3.ai 融资与自主渗透（2026-08）](https://siliconangle.com/2026/08/03/horizon3-ai-raises-250m-2b-plus-valuation-autonomous-pentesting/)
- [Pentera — 无代理真实利用](https://www.pentera.io)
- [Patrowl — 自动化渗透工具对比](https://patrowl.io/en/ressources/comparisons/best-automated-pentest-tools)
