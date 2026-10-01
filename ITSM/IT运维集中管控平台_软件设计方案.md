# IT运维集中管控平台 · 软件设计方案

> **版本**：V1.0（定稿）
> **编制日期**：2026-09-10
> **适用对象**：安全运维团队 / MSSP（安全托管服务商）/ 政企信息中心
> **核心主轴**：客户多合同 → 合同多子项 → 子项多服务对象 → 定期工单，以工单贯通履约全链路
> **技术底座**：PostgreSQL + 开源 Linux + Go/FastAPI + 可配置 AI 大模型（DeepSeek/Qwen/GLM/Kimi/MiniMax） + 七级 RBAC + 多租户 + 脱敏加密 + AIOps

---

## 目录

1. [方案概述](#一方案概述)
2. [需求分析](#二需求分析)
3. [总体架构设计](#三总体架构设计)
4. [核心业务模块详细设计](#四核心业务模块详细设计)
5. [权限与安全设计](#五权限与安全设计)
6. [界面设计](#六界面设计)
7. [数据模型设计](#七数据模型设计)
8. [接口设计](#八接口设计)
9. [开发实施步骤](#九开发实施步骤)
10. [测试与质量保障](#十测试与质量保障)
11. [上线部署与验收](#十一上线部署与验收)
12. [风险与应对](#十二风险与应对)
13. [附录](#十三附录)

---

## 一、方案概述

### 1.1 项目背景与定位

安全服务团队 / MSSP 的核心痛点在于：**一份合同往往包含多个服务对象、多个服务项、多个服务频率**，履约义务零散分布在合同文本、Excel、邮件和人的记忆里，导致漏做、重做、超期无人知、绩效算不清、换岗交接混乱、外包不可控。

本平台定位为**面向安服团队 / MSSP 的「合同履约 + 工单 + 服务」一体化集中管控平台**，以「合同 → 子项 → 工单」为主轴，统一承载：

- 客户合同的全部履约义务（定频服务、驻场服务、临时工作、应急处置）
- 公司内部任务与外包协作
- 问题发现 → 多轮整改 → 效果验证的整改闭环
- 项目交付、绩效考核、SLA 提醒、AI 增强、知识沉淀

目标：**可追溯、可量化、可考核、可自动化**的完整交付闭环。

### 1.2 核心设计理念（融合前沿方法论）

本方案在传统「工单系统」之上，融合 ITIL 4、SRE、AIOps、MSSP 多租户等先进理念：

| 理念 | 来源 | 在本平台的落地 |
|---|---|---|
| **CMDB 为核心** | ServiceNow / 嘉为蓝鲸 | 服务对象升级为完整 CMDB（配置项 + 依赖拓扑 + 影响分析），工单/变更/问题均挂接 CI |
| **SLO / 错误预算** | Google SRE | SLA 契约引擎升级为 SLO 管理，分级预警 + 升级链 + 超时统计 |
| **感知—决策—执行闭环** | AIOps | AI 分类/派单/摘要/相似推荐 + 告警降噪 + 履约缺口洞察 |
| **低代码流程引擎** | 优云 / 嘉为蓝鲸 | 表单/流程/决策/视图/报表五大引擎，状态流转可配置、留痕 |
| **多租户数据隔离** | FortiSOAR / Sekoia | 客户侧角色按 `customer_id` 行级隔离，外包按工单隔离 |
| **知识管理 ROI 最高** | ServiceNow 最佳实践 | 知识库 + 工单转知识闭环 + RAG 问答 |
| **human-in-the-loop** | AIOps 治理 | AI 只做「建议 + 人工确认」，不替代关键决策 |

### 1.3 同类产品对标与差异化

| 能力 | ServiceNow | Jira SM | 嘉为蓝鲸/优云 | **本平台** |
|---|---|---|---|---|
| CMDB / 依赖拓扑 | ✅ 行业标杆 | ⚠️ 依赖 Insight | ✅ 深度联动 | ✅ 服务对象+依赖+影响分析 |
| 变更管理 | ✅ CAB/风险评分 | ✅ 快速 | ✅ 冲突检测 | ✅ 变更+冲突检测 |
| 多合同多子项履约 | ❌ 通用 IT 场景 | ❌ | ❌ | ✅ **核心差异化** |
| 驻场/外包/内部任务 | ❌ | ❌ | ❌ | ✅ 三类工单来源 |
| 换岗比例分摊绩效 | ❌ | ❌ | ❌ | ✅ **核心差异化** |
| 七级 RBAC（客户侧） | 部分 | 部分 | 部分 | ✅ 平台+客户双域七级 |
| 信创适配 | ❌ | ❌ | ✅ | ✅ 可选（达梦/金仓/麒麟/统信） |

**差异化结论**：ServiceNow/蓝鲸解决的是「通用 IT 服务管理」，本平台解决的是「安全运维服务合同的精细化履约管理」——多合同多子项排期、驻场日报、外包结算、换岗绩效分摊，是本平台独有的业务纵深。

### 1.4 术语表

| 术语 | 含义 |
|---|---|
| 合同 | 与客户签订的服务合同（安全服务/安全运维/设备升级/机房改造…） |
| 合同子项 | 合同内的一个服务项 = 服务对象 + 运维项目 + 服务频率 + 验收标准 |
| 服务对象 | 客户侧被服务的系统/设备（OA/XX/YY 系统），即 CMDB 配置项（CI） |
| 服务周期 | 合同子项按频率拆分出的一个履约周期（第 N 次服务） |
| 定期工单 | 服务周期到期自动生成的工单 |
| CI | Configuration Item，配置项，CMDB 最小管理单元 |

---

## 二、需求分析

### 2.1 目标用户与角色

平台分「平台侧」与「客户侧」两大域，共七级角色（详见第五章）：

- **平台侧**：系统管理员、系统运维人员、工单管理人员、客服人员、工程师
- **客户侧**：客户系统管理员、客户服务管理人员

### 2.2 核心业务场景

1. **多合同多子项履约**：一个客户同时有安全服务合同 + 设备升级合同，各自拆解为多个子项，各自独立排期、提醒、验收。
2. **定期工单自动生成**：OA 系统「漏洞扫描 1 次/季度」→ 每季度自动生成工单 → 派单 → 执行 → 交付。
3. **驻场服务**：客户要求派驻 X 人，驻场人员每日填报日报，汇总月报，异常转整改。
4. **外包协作**：能力/时间不足时外包，外包人员接单、汇报、验收、结算，数据强隔离。
5. **换岗分摊**：工单执行到一半换人，系统按「各人实际承担工作量」自动重算绩效。
6. **整改闭环**：执行中发现安全问题（漏洞、配置缺陷、基线不合规、风险隐患等）→ 多轮整改 → 效果验证通过 → 归档交付。

### 2.3 功能需求清单（FR）

> 以下为功能性需求编号，与第四章模块一一对应。

| 编号 | 需求 | 优先级 |
|---|---|---|
| FR-01 | 客户档案管理（多联系人、等级、服务对象清单） | P0 |
| FR-02 | 多合同登记（类型/金额/周期/状态） | P0 |
| FR-03 | 合同子项管理（服务对象+项目+频率+SLA+验收） | P0 |
| FR-04 | 接单（多来源：报障/商务/巡检/事件/续约/临时） | P0 |
| FR-05 | 派单（人工+智能+多人比例+换岗重算） | P0 |
| FR-06 | 工单生命周期管理（4 类型 + 状态机） | P0 |
| FR-07 | 驻场服务（配置 + 日报 + 月报聚合） | P1 |
| FR-08 | 内部任务（统一工单池） | P1 |
| FR-09 | 外包管理（接单/汇报/验收/结算/隔离） | P1 |
| FR-10 | 问题发现与多轮整改闭环 | P1 |
| FR-11 | 项目交付（四类报告 + 专项报告） | P1 |
| FR-12 | 绩效考核（加权 + 换岗分摊 + 外包成本） | P1 |
| FR-13 | CMDB 与资产依赖管理 | P1 |
| FR-14 | 变更管理（风险评估 + 冲突检测） | P2 |
| FR-15 | 服务频率与定期工单自动生成 | P0 |
| FR-16 | 服务提醒 + SLA 契约引擎（分级预警+升级链） | P0 |
| FR-17 | AI 智能增强（分类/派单/摘要/相似/履约洞察） | P2 |
| FR-18 | 工作流编排与审批（低代码） | P1 |
| FR-19 | 知识库与自助门户（服务目录） | P2 |
| FR-20 | 报告中心与数据看板 | P1 |
| FR-21 | 七级 RBAC 权限 + 多租户隔离 | P0 |
| FR-22 | 数据脱敏/加密/水印/审计 | P0 |

### 2.4 非功能需求（NFR）

| 类别 | 指标 |
|---|---|
| 性能 | 常规查询 P95 < 500ms；工单列表万级数据分页 < 1s |
| 可用性 | 全年可用性 ≥ 99.9%（RTO ≤ 1h，RPO ≤ 5min） |
| 并发 | 支持 500 并发在线，200 并发工单操作 |
| 安全 | 等保 2.0 三级；TLS 1.2+；敏感字段脱敏；操作全审计 |
| 数据 | 客户数据物理/逻辑隔离；备份加密；多租户行级隔离 |
| 兼容 | 开源 Linux + PostgreSQL 为主；信创可选适配（麒麟/统信 + 达梦/金仓） |
| 可维护 | 低代码配置化；接口文档化；全链路日志 |

---

## 三、总体架构设计

### 3.1 业务架构（合同 → 子项 → 工单 主轴）

```
客户(customer) 1──N 合同(contract) 1──N 合同子项(contract_item)
                                          │
                     ┌────────────────────┼─────────────────────┐
                     │                    │                     │
              服务对象(CI)         服务周期(cycle)          SLA契约
                     │                    │                     │
                     │            定期工单(自动生成)            │
                     └──────────► 工单(work_order) ◄───────────┘
                                          │
           ┌──────────┬──────────┬────────┼─────────┬──────────┐
       接单receive  派单dispatch  执行assignee  问题issue  交付delivery
                                    │                    │
                               换岗分摊(绩效)        整改(多轮)
```

### 3.2 应用架构（模块划分）

**二十大核心模块**，按领域拆分为 5 个子系统：

| 子系统 | 模块 |
|---|---|
| **合同域** | ① 客户与合同管理 ② 合同子项与服务对象 |
| **工单域** | ③ 接单 ④ 派单 ⑤ 工单管理 ⑥ 驻场 ⑦ 内部任务 ⑧ 外包 |
| **服务域** | ⑨ 问题与整改 ⑩ 项目交付 ⑪ 绩效 ⑫ 服务频率 ⑬ 提醒与SLA |
| **平台域** | ⑭ CMDB/资产 ⑮ 变更管理 ⑯ 报告中心 ⑰ 工作流 ⑱ 知识库/门户 ⑲ AI增强 |
| **基础域** | ⑳ 系统管理（七级RBAC/字典/审计/水印/脱敏）+ 部署与数据安全 |

### 3.3 技术架构（分层 + 技术选型）

| 层次 | 主推 | 备选 |
|---|---|---|
| 操作系统 | 开源 Linux（Ubuntu / CentOS / Debian） | 麒麟/统信（信创可选） |
| 后端 | Go（Gin）/ Python FastAPI | Java Spring Boot |
| 前端 | Vue 3 + Vite + Element Plus / Ant Design Vue + Pinia + ECharts | 同左 |
| 移动端 | uni-app（一套代码多端：小程序/App/H5，GPS+拍照+推送） | 同左 |
| 数据库 | PostgreSQL 16 | 达梦 / 金仓（信创可选） |
| 缓存/队列 | Redis + RabbitMQ/RocketMQ | Redis 兼容版 |
| 检索 | Elasticsearch（知识库全文检索） | OpenSearch |
| 工作流 | 自研规则引擎 / Temporal（Go） | Flowable 7 |
| AI | 可配置大模型：DeepSeek / Qwen / GLM / Kimi / MiniMax（统一 LLM 抽象层，系统设置可切换）+ RAG | 本地私有化 LLM |
| 定时调度 | APScheduler（Python）/ Quartz | XXL-Job |
| 对象存储 | 本地磁盘 / MinIO（本机部署） | OSS / 国产云存储 |
| 认证 | JWT + 多因子（人脸/短信） | 同左 |

### 3.4 部署架构（本地服务器部署 · 开发阶段本机）

```
浏览器（本机 / 局域网） ──► 前端（Vue3 静态资源 / Nginx）
                              │
        ┌─────────▼────────── 应用层（本机 · 开源 Linux）─────────┐
        │ 后端应用(Go/FastAPI) │ 工作流/规则引擎 │ AI服务(可配置大模型) │ 定时调度 │
        └─────────┬──────────────────────────────────────────────┘
                  │
        ┌─────────┬──────────┬──────────┬───────────┬──────────────┐
   PostgreSQL    Redis      ES         本地存储/MinIO   大模型API
    (本机)      (会话缓存)  (检索)      (附件/报告)   (DeepSeek/Qwen/GLM/Kimi/MiniMax)
```

- **本地部署为主**：开发阶段整套系统部署在本机（localhost）或局域网服务器，前端 + 后端 + PostgreSQL + Redis 同机运行
- **简化部署**：开发阶段采用单体/轻量部署，Docker Compose 一键拉起 PostgreSQL / Redis / Elasticsearch，不依赖云资源
- **可平滑上云**：架构预留水平扩展能力，后续可迁移至云服务器 / 容器编排（K8s）
- **多租户模型**：平台侧单实例 + 客户侧逻辑隔离（`customer_id` 行级过滤 + 视图/RLS）；对高合规客户可选独立 Schema / 独立实例（参考 Safeguard per-tenant schema）

### 3.5 架构演进路线

```
人工运维 → 自动化运维(定时工单/工作流) → 智能运维AIOps(分类/派单/洞察) → AI原生自治(受控自治+审批)
```

---

## 四、核心业务模块详细设计

### 4.1 客户与合同管理

**客户档案字段**：名称/简称、行业/规模、客户等级（金牌/银牌/普通，关联 SLA）、联系人/电话（脱敏）、服务对象清单。

**合同登记字段**：合同类型、名称/编号、金额、周期（起止）、服务对象、合同子项、是否含驻场、状态（草稿/执行中/已到期/已续约）。

> **多合同模型**：一个客户可同时有多个并行合同（如安全服务合同 + 设备升级合同 + 机房改造合同），系统按合同独立管理履约、结算与绩效。

### 4.2 合同子项与服务对象

**服务对象（= CMDB 配置项 CI）字段**：对象名称、对象类型（业务系统/网络设备/服务器/机房/数据库）、IP/位置、**依赖关系**（影响分析）。

**合同子项字段**：服务对象、运维项目、服务频率（数值+单位）、SLA、验收标准、子项价格。

> **关键设计**：服务频率从「工单级」下放到「子项级」，同一合同内不同系统、不同服务项各自独立排期、独立提醒、独立验收。

### 4.3 接单模块

**接单来源**：客户报障 / 商务拓展 / 巡检发现 / 安全事件 / 续约 / **临时新增**。

**接单表单**：来源、所属客户、关联合同（可空）、关联子项（可空）、服务对象、运维项目、服务频率（继承可覆盖）、合同价格、甲方联系人/电话（脱敏）、服务时间、验收标准。

> **临时工作快速开单**：外出检查、应付抽检、处置舆情等临时任务，支持快速模板一键开单，可不挂合同/子项。

### 4.4 派单模块（智能派单 + 换岗分摊）

**派单字段**：运维人员（单人/多人 + 工作量比例）、派单方式（内部/外包）、派单价格、服务时间、验收标准。

**智能派单建议（AI）**：基于 `技能矩阵 + 当前负载 + 历史绩效与评价`，推荐执行人并给出理由，项目经理可采纳或调整。

**换岗 / 比例分摊**：

```
个人绩效 = Σ ( 工作量 × 派单价格 × 分摊比例 × 质量系数 × 评价系数 )
分摊比例 = 个人实际承担工作量 / 工单总工作量
```

> 中途换岗时，原执行人登记已完成比例，剩余转新执行人，系统按「各人实际承担时长 × 派单价」自动重算，结算与绩效精确到人。

### 4.5 工单管理（核心）

**工单类型**：客户工单 / 驻场工单 / 内部任务 / 外包工单（统一工单池）。

**工单状态机**：

```
待派单 → 已派单/进行中 → 计划中 ↔ 进行中 → 待验收 → 已完成
                ↓
          (SLA 预警 / 催办 / 升级)
```

**状态流转（工作流驱动）**：整改通过 → 自动「待验收」；客户签字 → 自动「已关闭」+ 计绩效；外包验收通过 → 自动结算。

### 4.6 驻场服务模块

**驻场配置**：驻场客户/合同、驻场人数、驻场人员（可换岗）、驻场周期、驻场工作项（设备巡检/日志分析/漏洞打补丁/资产梳理/故障处置…）。

**驻场日报**：逐项记录当日工作 → 自动汇总周报/月报；发现的异常一键转「问题」进入整改闭环。

### 4.7 内部任务模块

**字段**：任务名称、任务类型（内部研发/制度建设/报告编写/培训准备/其他）、指派人员（可多人+比例）、优先级/截止时间、任务说明、关联客户（可空）。

> **统一工单池**：内部任务与客户工单共用状态机、SLA、提醒机制，员工一个视图处理所有待办。

### 4.8 外包管理模块

**外包流程**：内部工单 → 发起外包 → 外包派单 → 外包接单 → 工作汇报 → 验收 → 结算。

**字段**：外包类型（能力/时间/资质）、外包人员/单位、外包价格、保密协议/权限范围、工作进展、验收。

> **权限隔离（安全）**：外包账号**仅见被指派的外包工单**，数据脱敏，禁止访问客户其他合同/工单/内部数据，全程审计；外包可接单/拒单。

### 4.9 问题发现与整改闭环

**发现问题（安全问题）**：涵盖安全漏洞、配置缺陷、基线不合规、风险隐患等，记录类型、等级、描述、截图/日志，挂接工单下，支持**问题相似度推荐**。

**多轮整改**：第 1 轮整改中 → … → 第 N 轮整改中 → 整改完成（待验证）/ 整改不通过（自动下一轮）。

**整改效果**：成果式描述 + 验证三态（通过 / 不通过 / 部分完成继续整改）。

### 4.10 项目交付

**四类核心交付报告**：运维报告 / 发现问题报告 / 整改报告 / 验收报告。

**专项报告**：漏洞扫描 / 渗透测试 / 应急演练 / 安全评估 / 基线核查 / 等保测评 / 驻场服务月报。

> 交付可挂接合同/子项层级，支持按合同整体交付或按子项分别交付。

### 4.11 绩效考核（换岗分摊）

**构成要素**：工作量、派单价格、工作质量（0.6~1.2 打分）、用户评价（0.8~1.2）。

**统计维度**：按人员/客户/合同/子项/运维项目/时间（日/周/月/季/年），产出个人报表、团队排名、成本毛利核算（外包成本纳入）。

### 4.12 CMDB 与资产管理（本方案增强）

原方案「服务对象」升级为完整 CMDB：

| 能力 | 说明 |
|---|---|
| 配置项（CI）建模 | 服务对象/设备/服务器/数据库/机房 等 CI 类型 |
| 依赖拓扑 | CI 间依赖关系（影响分析：某服务器故障影响哪些系统） |
| 变更联动 | 工单/变更自动更新 CI 属性（IP、版本、状态） |
| 冲突检测 | 多个变更涉及同一 CI 或同一时间窗口时实时预警 |
| 资产生命周期 | 新增 → 在用 → 变更 → 下线 |

### 4.13 变更管理（本方案增强）

借鉴 ServiceNow / 蓝鲸：**变更风险评估（问卷+分值→高/中/低）+ 变更日历 + CAB 审批 + 回滚跟踪 + 审计留痕**。变更工单与 CMDB 联动，变更过程、日志全程可追溯。

### 4.14 服务频率与定期工单

**周期拆分规则**：

| 频率 | 示例 | 逻辑 |
|---|---|---|
| X 次/天 | 1 次/天 | 每日 1 次 |
| X 次/周 | 2 次/周 | 每周均匀分布 |
| X 次/月 | 4 次/月 | 每月均匀分布 |
| X 次/季度 | 1 次/季度 | 每季度 1 次 |
| X 次/半年 | 1 次/半年 | 每半年 1 次 |
| X 次/年 | 2 次/年 | 每半年 1 次 |
| 不定期 | 应急处置 | 不自动生成，按需手动派单 |

> 系统统一生成**日历视图**，直观展示全年履约计划与缺口。

### 4.15 服务提醒与 SLA 契约引擎

**服务启动提醒**：进入服务周期时 →「第 X 次服务已启动，请及时处理！」

**分级预警**（基准 = 本次服务周期结束日）：

| 等级 | 触发 | 颜色 |
|---|---|---|
| 黄色预警 | 距结束 ≤ 7 天 | 黄 |
| 橙色预警 | 距结束 ≤ 3 天 | 橙 |
| 红色紧急 | 距结束 ≤ 1 天 | 红 |

**SLA 契约引擎**：多级 SLA（按客户等级/紧急度）+ 工作日历（跳过非工作时段）+ **升级链**（执行人 → 项目经理 → 部门负责人）。

**提醒渠道**：站内 + 移动推送 + 企微/飞书/钉钉/短信。

### 4.16 AI 智能增强（AIOps）

| 能力 | 应用场景 | 落地原则 |
|---|---|---|
| 智能分类 | 报障/描述 → 推荐运维项目、服务对象、优先级 | 建议 + 人工确认 |
| 智能派单 | 技能矩阵 + 负载 + 绩效 → 推荐执行人（含外包） | 建议 + 人工确认 |
| 工单摘要 | 自动生成执行摘要，辅助交付报告 | 自动 |
| 问题相似推荐 | 相似问题与整改方案匹配 | 建议 |
| 合同履约洞察 | 识别履约缺口、临近到期项，提示补单 | 自动 + 提醒 |
| 告警降噪 | 同一故障树告警聚类为「事件风暴」 | 自动 |
| 工单转知识 | 高频工单 → 知识草稿 → 审核入库 | 建议 + 人工 |
| 知识问答 | 运维/客户 RAG 自助问答 | 自动 |

> **落地原则**：AI 均为「建议 + 人工确认」，不替代关键决策；涉敏数据走本地化/脱敏 LLM；决策可解释、证据可追溯。

**AI 大模型可配置**：系统提供统一 LLM 抽象层，在「系统设置」中配置并切换大模型服务商，无需改代码：

| 模型 | 厂商 | 接入方式 |
|---|---|---|
| DeepSeek | 深度求索 | OpenAI 兼容 API |
| Qwen（通义千问） | 阿里云 | OpenAI 兼容 / DashScope |
| GLM | 智谱 AI | OpenAI 兼容 API |
| Kimi | 月之暗面 | OpenAI 兼容 API |
| MiniMax | MiniMax | OpenAI 兼容 API |

- **统一配置项**：`api_base`、`api_key`、`model_name`，按场景路由（分类/摘要/问答可配不同模型）
- **本地私有化 LLM** 作为可选（数据不出域，涉敏场景）
- **降级策略**：主模型不可用时自动切换备用模型

### 4.17 工作流编排与审批（低代码）

借鉴优云/蓝鲸「低代码五大引擎」：

- **表单引擎**：拖拽式表单配置
- **流程引擎**：图形化状态流转 + 审批节点
- **决策引擎**：条件分支（金额阈值/类型/等级）
- **视图引擎**：列表/看板自定义
- **报表引擎**：可视化报表

**典型流程**：审批流（派单价超阈值审批）、状态自动流转、自动化动作（超时升级/定期工单/提醒/履约缺口提示）。

> 全量留痕：记录触发规则、时间、操作人。

### 4.18 知识库与自助门户（服务目录）

**知识库**：漏洞库、整改方案库、故障手册、SOP、驻场操作规范；全文检索 + RAG 问答；**高频问题 → 知识条目 → 自助解决**闭环。

**自助门户（服务目录化）**：客户自助报障、查进度、下报告、看合同履约情况；内部员工查知识、核对工作量；外包人员看被指派工单、提交汇报。

### 4.19 报告中心与数据看板

报告归档、数据看板（KPI：工单总数/进行中/即将超时/待验收/待结款/安全事件）、成本毛利核算、履约率、SLA 达成率、绩效排名。

---

## 五、权限与安全设计

### 5.1 七级 RBAC 模型

| 序号 | 角色 | 域 | 权限范围 |
|---|---|---|---|
| 1 | 系统管理员 | 平台 | 最高权限：用户/角色/权限/配置/字典/审计/全数据 |
| 2 | 系统运维人员 | 平台 | 监控、备份/恢复、日志、服务启停、性能（不碰业务数据） |
| 3 | 工单管理人员 | 平台 | 接单、派单、催单、变更时限/服务人员/价格 |
| 4 | 客服人员 | 平台 | 只读：仪表盘、工单进度、联系服务人员（不可改工单） |
| 5 | 客户系统管理员 | 客户 | 查看/管理己方合同工单进度；不可改履约中合同内容与价格 |
| 6 | 客户服务管理人员 | 客户 | 追加合同/系统/工单、临时工单、调时限、评价/投诉 |
| 7 | 工程师 | 平台 | 查看本人工单、接收任务与催单、填表单/日志 |

### 5.2 多租户与数据隔离

| 隔离层级 | 机制 |
|---|---|
| 行级隔离 | 客户侧角色 `customer_id` 过滤（应用层拦截 + PG RLS 双重保障） |
| 字段级权限 | 合同价格/联系方式按角色控制可读/可写/脱敏 |
| 外包隔离 | 外包账号仅见指派工单，跨合同/客户强隔离 |
| 可选物理隔离 | 高合规客户独立 Schema / 独立实例 |

### 5.3 数据安全（脱敏 + 加密 + 水印 + 审计）

| 类型 | 字段 | 脱敏方式 |
|---|---|---|
| 联系方式 | 电话/手机 | 138\*\*\*\*1234 |
| IP 地址 | 资产 IP | 10.1.\*.\* |
| 凭证/密码 | 系统口令 | 不可逆哈希，永不展示 |
| 金额 | 合同/派单价 | 低权限遮蔽或占位 |

**加密**：TLS 1.2+ 全链路；PostgreSQL 强制 SSL 连接；密钥管理系统（KMS）信封加密；`pgcrypto` 敏感列加密；TDE + 对象存储 SSE；备份加密。

**水印与审计**：屏幕/打印水印防拍照；操作审计全留痕（before/after + IP + 时间）。

---

## 六、界面设计

系统含 **11 套界面**（6 套 PC 端 + 5 套移动 APP），与七级 RBAC 角色一一对应，采用双品牌命名：平台侧「信息服务AI管控平台 V1.0」、客户侧「运维服务AI管控平台」。

### 6.1 界面体系总览

| 端 | 套数 | 界面 |
|---|---|---|
| PC 端 | 6 套 | ① 系统管理 ② 系统运维 ③ 工单管理 ④ 服务人员 ⑤ 客户系统管理 ⑥ 客户服务管理 |
| 移动 APP | 5 套 | ⑦ 服务人员APP ⑧ 系统管理员APP ⑨ 工单管理员APP ⑩ 客户系统管理APP ⑪ 客户服务管理APP |

### 6.2 PC 端各级界面设计

| 界面 | 角色 | 顶部菜单 | 左侧导航 | 标签页 |
|---|---|---|---|---|
| ① 系统管理 | 系统管理员 | 系统/接单/派单/修改工单/催单/进度/结单/帮助 | 汇总、各单位、各系统 | 仪表盘/工单/安全问题/整改/报告/验收/结款/评价 |
| ② 系统运维 | 系统运维人员 | 系统(仅服务人员)/帮助 | 汇总、各单位、各系统 | 同上 8 项 |
| ③ 工单管理 | 工单管理人员 | 系统/接单/派单/修改工单/催单/进度/结单/帮助 | 汇总、各单位、各系统 | 同上 8 项 |
| ④ 服务人员 | 工程师 | 系统/帮助 | 工单汇总/今日工作/催单/问题反馈 | 含「工作排期」9 项 |
| ⑤ 客户系统管理 | 客户系统管理员 | 系统/帮助 | 汇总、各系统 | 仪表盘/运维工作/安全问题/整改/报告/验收 |
| ⑥ 客户服务管理 | 客户服务管理人员 | 系统/派单/修改工单/催单/进度/结单/帮助 | 汇总、各系统 | 同上 + 评价与投诉 |

### 6.3 移动端 APP 界面设计

| 界面 | 角色 | 底部导航 |
|---|---|---|
| ⑦ 服务人员APP | 工程师(移动) | 工单汇总/今日工作/催单/反馈 |
| ⑧ 系统管理员APP | 系统管理员(移动) | 权限/接单/派单/修改工单/催单/进度/结单 |
| ⑨ 工单管理员APP | 工单管理员(移动) | 接单/派单/修改/催单/进度/结单 |
| ⑩ 客户系统管理APP | 客户系统管理员(移动) | 仪表盘/运维工作/安全问题/整改/报告/验收 |
| ⑪ 客户服务管理APP | 客户服务管理员(移动) | 派单/修改工单/催单/进度/结单/评价 |

### 6.4 界面设计原则

- **按角色裁剪**：菜单、数据范围、操作按钮严格按七级 RBAC 角色裁剪
- **敏感信息保护**：联系方式/金额等敏感字段脱敏显示，屏幕/打印水印
- **移动端特性**：服务人员 APP 支持人脸识别登录、GPS 定位签到、拍照打卡留证
- **统一布局**：PC 端「顶部菜单 + 左侧导航 + 标签页」三区布局；移动端底部 Tab 导航

---

## 七、数据模型设计

### 6.1 ER 关系（合同为中心，工单为纽带）

```
customer 1—N contract 1—N contract_item
contract_item 1—N cmdb_ci(服务对象)   [注: 实际经 contract_item 关联]
contract_item 1—N service_cycle → 1—N 定期工单
work_order 1—1 dispatch N—1 assignee(含比例)
work_order 类型: 客户/驻场/内部/外包
onsite_service → onsite_daily_report
outsourcing → outsource_user → 汇报/验收
work_order 1—N issue → 1—N rectification → 1—N rectification_record
work_order 1—N delivery
performance ← 工时×比例分摊
sla_policy → work_order → escalation
cmdb_ci(服务对象) + cmdb_relation(依赖) + change_order(变更)
sys_user / sys_role / sys_permission / sys_user_role / sys_role_permission
```

### 6.2 核心表清单

| 表名 | 关键字段 |
|---|---|
| `customer` 客户 | id, name, industry, level, contact |
| `contract` 合同 | id, customer_id, type, name, no, amount, start/end, has_onsite, status |
| `cmdb_ci` 配置项 | id, customer_id, name, type, ip, status, version, lifecycle |
| `cmdb_relation` 依赖 | id, from_ci_id, to_ci_id, relation_type |
| `contract_item` 合同子项 | id, contract_id, ci_id, project, frequency, unit, sla_policy_id, accept_standard, price |
| `order_receive` 接单 | id, source, customer_id, contract_id, contract_item_id, ci_id, project, contract_price, contact, service_start/end |
| `order_dispatch` 派单 | id, work_order_id, dispatch_type, dispatch_price, service_start/end, suggest_reason |
| `work_order` 工单 | id, no, type, receive_id, dispatch_id, contract_id, contract_item_id, ci_id, project, status, priority, sla_deadline, progress, current_cycle_no |
| `work_order_assignee` 执行人 | id, work_order_id, user_id, workload_ratio, actual_hours, started_at, ended_at, is_active |
| `service_cycle` 服务周期 | id, contract_item_id, cycle_no, service_start, service_end, status, auto_generated |
| `service_reminder` 提醒 | id, cycle_id, type, level, content, to_user_id, channel, sent_at |
| `onsite_service` 驻场 | id, contract_id, customer_id, headcount, period_start/end, work_items |
| `onsite_daily_report` 日报 | id, onsite_id, user_id, report_date, work_type, content, issue_ref |
| `outsourcing` 外包 | id, work_order_id, type, outsource_user_id, price, nda, status |
| `outsource_user` 外包人员 | id, name, org, qualification, settle_type, permissions |
| `outsourcing_report` 汇报 | id, outsourcing_id, report_date, progress, attachments, acceptance |
| `issue` 问题 | id, work_order_id, type, level, description, attachments, similar_ids |
| `rectification` 整改 | id, issue_id, plan, deadline, assignee, status |
| `rectification_record` 整改记录 | id, rectification_id, round_no, action, executor, effect |
| `change_order` 变更 | id, work_order_id, ci_id, risk_level, conflict_flag, rollback_plan, status |
| `delivery` 交付 | id, work_order_id, contract_id, contract_item_id, report_type, report_id, sign |
| `performance` 绩效 | id, user_id, work_order_id, contract_item_id, workload, dispatch_price, ratio, quality_score, customer_score, perf_score |
| `sla_policy` SLA契约 | id, name, customer_level, response_limit, resolve_limit, work_calendar_id, escalation_chain |
| `escalation` 升级 | id, work_order_id, level, from_user, to_user, triggered_at, reason |
| `workflow_rule` / `action_log` | 工作流规则 / 动作日志 |
| `kb_article` / `engineer_skill` | 知识库 / 技能矩阵 |
| `sys_user` | id, username, name, phone, dept, status, pwd_hash |
| `sys_role` | id, code, name, scope(平台/客户) |
| `sys_permission` | id, code, name, type(菜单/按钮/接口/字段) |
| `sys_user_role` | user_id, role_id, customer_id |
| `sys_role_permission` | role_id, permission_id |
| `sys_audit_log` | id, user_id, action, resource, before, after, ip, operated_at |

### 6.3 关键 DDL 示例（PostgreSQL）

```sql
-- 合同子项（履约核心）
CREATE TABLE contract_item (
  id            BIGSERIAL PRIMARY KEY,
  contract_id   BIGINT NOT NULL REFERENCES contract(id),
  ci_id         BIGINT REFERENCES cmdb_ci(id),      -- 服务对象
  project       VARCHAR(64) NOT NULL,               -- 运维项目枚举
  frequency     INT NOT NULL DEFAULT 1,             -- 频率数值
  unit          VARCHAR(16) NOT NULL DEFAULT '月',  -- 天/周/月/季度/半年/年/不定期
  sla_policy_id BIGINT REFERENCES sla_policy(id),
  accept_standard TEXT,
  price         NUMERIC(14,2),
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- 服务周期（定期工单生成依据）
CREATE TABLE service_cycle (
  id             BIGSERIAL PRIMARY KEY,
  contract_item_id BIGINT NOT NULL REFERENCES contract_item(id),
  cycle_no       INT NOT NULL,
  service_start  DATE NOT NULL,
  service_end    DATE NOT NULL,
  status         VARCHAR(16) DEFAULT 'pending',   -- pending/running/done
  auto_generated BOOLEAN DEFAULT true,
  UNIQUE(contract_item_id, cycle_no)
);

-- 工单
CREATE TABLE work_order (
  id            BIGSERIAL PRIMARY KEY,
  no            VARCHAR(32) UNIQUE NOT NULL,
  type          VARCHAR(16) NOT NULL,          -- 客户/驻场/内部/外包
  contract_id   BIGINT REFERENCES contract(id),
  contract_item_id BIGINT REFERENCES contract_item(id),
  ci_id         BIGINT REFERENCES cmdb_ci(id),
  status        VARCHAR(16) DEFAULT '待派单',
  priority      VARCHAR(8) DEFAULT '中',
  sla_deadline  TIMESTAMPTZ,
  current_cycle_no INT
);

-- 执行人（含换岗分摊）
CREATE TABLE work_order_assignee (
  id            BIGSERIAL PRIMARY KEY,
  work_order_id BIGINT NOT NULL REFERENCES work_order(id),
  user_id       BIGINT NOT NULL REFERENCES sys_user(id),
  workload_ratio NUMERIC(5,2) DEFAULT 100,     -- 分摊比例%
  actual_hours  NUMERIC(8,2),
  started_at    TIMESTAMPTZ,
  ended_at      TIMESTAMPTZ,
  is_active     BOOLEAN DEFAULT true
);
```

---

## 八、接口设计

### 7.1 RESTful API 规范

- 统一前缀 `/api/v1`；资源化 URI：`/customers`、`/contracts`、`/work-orders`
- 统一响应：`{ "code": 0, "message": "ok", "data": {} }`
- 统一鉴权：JWT Bearer Token；统一错误码；分页 `?page=1&size=20`
- OpenAPI 3.0 文档自动生成（Swagger）

### 7.2 关键接口示例

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/work-orders` | 创建工单（接单） |
| POST | `/api/v1/work-orders/{id}/dispatch` | 派单（含多人比例） |
| PUT | `/api/v1/work-orders/{id}/status` | 状态流转（工作流校验） |
| POST | `/api/v1/work-orders/{id}/assignees/transfer` | 换岗（触发绩效重算） |
| POST | `/api/v1/contract-items/{id}/cycles/generate` | 生成服务周期 |
| GET | `/api/v1/work-orders/suggest-dispatch` | AI 派单建议 |
| POST | `/api/v1/work-orders/{id}/issues` | 记录问题 |
| POST | `/api/v1/rectifications/{id}/rounds` | 提交整改轮次 |
| GET | `/api/v1/performance?user_id=&period=` | 绩效查询 |

---

## 九、开发实施步骤

### 8.1 阶段一：工程搭建与基础设施（第 1-2 周）

**任务分解：**

1. **初始化仓库与工程骨架**
   - 后端：Spring Boot 3 多模块工程（`common`/`contract`/`ticket`/`service`/`platform`/`auth`）
   - 前端：Vue 3 + Vite 工程，集成 Ant Design Vue + Pinia + ECharts
   - 移动端：uni-app 工程
2. **数据库建模**：编写完整 DDL（6.2 全部表）+ Flyway/Liquibase 迁移脚本
3. **部署环境**：本机/局域网服务器 + PostgreSQL + Redis + Elasticsearch 环境准备（Docker Compose 一键拉起）；Git 仓库 + CI 配置
4. **认证授权骨架**：Spring Security + JWT + 七级 RBAC 权限模型落地（用户/角色/权限/菜单）
5. **统一规范**：统一响应/异常/日志/审计切面

**交付物**：可运行的空壳系统（登录 + 权限校验通过）、数据库 Schema v1、CI/CD 跑通。

### 8.2 阶段二：合同履约主干（第 3-8 周，MVP）

**任务分解：**

1. **客户与合同管理**（FR-01/02）：客户 CRUD、合同 CRUD、状态流转
2. **合同子项与服务对象**（FR-03）：CMDB CI 基础建模、子项 CRUD、频率/验收配置
3. **接单**（FR-04）：接单表单 + 多来源 + 临时工单快速开单
4. **派单**（FR-05）：人工派单 + 多人比例 + 换岗重算
5. **工单管理**（FR-06）：状态机 + 列表 + 详情 + 4 类型
6. **服务频率与定期工单**（FR-15）：周期拆分算法 + Quartz/APScheduler 定时生成 + 日历视图
7. **服务提醒与 SLA**（FR-16）：启动提醒 + 分级预警 + 升级链 + 多渠道推送

**MVP 验收标准**：跑通「客户→合同→子项→接单→派单→工单→定期工单→提醒」主干，验证多合同多子项排期与履约闭环。

### 8.3 阶段三：问题整改与绩效（第 9-13 周）

1. **问题与整改闭环**（FR-10）：问题录入 → 多轮整改 → 效果验证 → 相似推荐
2. **绩效考核**（FR-12）：加权公式 + 换岗分摊 + 外包成本毛利
3. **项目交付**（FR-11）：四类报告 + 专项报告生成（模板引擎）

### 8.4 阶段四：驻场/内部/外包 + 交付（第 14-19 周）

1. **驻场服务**（FR-07）：驻场配置 + 日报 + 周/月报聚合
2. **内部任务**（FR-08）：统一工单池
3. **外包管理**（FR-09）：外包流程 + 权限隔离 + 结算
4. **报告中心与看板**（FR-20）

### 8.5 阶段五：AI + 工作流 + 知识库 + 变更（第 20-26 周）

1. **工作流编排**（FR-18）：低代码五大引擎 + 审批流
2. **AI 增强**（FR-17）：本地 LLM + RAG，分类/派单/摘要/相似/履约洞察/工单转知识
3. **知识库与自助门户**（FR-19）：服务目录 + RAG 问答
4. **变更管理**（FR-14）：风险评估 + 冲突检测 + 变更日历
5. **CMDB 增强**（FR-13）：依赖拓扑 + 变更联动

### 8.6 阶段六：移动端 + 安全加固 + 上线（第 27-30 周）

1. **移动端**：uni-app 服务人员/管理员/客户 APP（人脸识别 + GPS + 拍照打卡 + 推送）
2. **数据安全**（FR-22）：脱敏/加密/水印/审计全量落地
3. **部署演练**：本地部署 → 生产环境迁移演练（上云 / 容器化）
4. **性能压测 + 安全测试 + 等保测评**

### 8.7 里程碑与交付物汇总

| 里程碑 | 周 | 关键交付物 |
|---|---|---|
| M1 工程搭建 | 2 | 空壳系统 + DB Schema + CI/CD |
| M2 MVP | 8 | 合同履约主干闭环 |
| M3 整改绩效 | 13 | 整改闭环 + 绩效 |
| M4 驻场外包 | 19 | 三类工单 + 交付报告 |
| M5 AI/工作流 | 26 | AI 增强 + 低代码 + 知识库 |
| M6 上线 | 30 | 移动端 + 安全加固 + 上线验收 |

---

## 十、测试与质量保障

### 9.1 测试策略

| 层 | 工具 | 覆盖目标 |
|---|---|---|
| 单元测试 | JUnit 5 / pytest | 核心业务逻辑 ≥ 80%（派单分摊、周期拆分、状态机） |
| 集成测试 | Testcontainers + PG | 关键链路（接单→派单→工单→验收） |
| 接口测试 | Postman/Newman + REST Assured | 全部 API |
| 前端测试 | Vitest + Playwright | 核心页面 + 关键交互 |
| 性能测试 | JMeter | 并发 500，P95 < 500ms |
| 安全测试 | OWASP ZAP + 渗透 | 等保三级 |

### 9.2 关键测试用例

1. **周期拆分**：`2 次/周` 跨月 → 是否均匀分布、是否重复/遗漏
2. **换岗分摊**：A(60%)→B(40%) 换岗后绩效是否精确归属
3. **定期工单**：季度频率到点是否只生成 1 次（幂等防重）
4. **权限隔离**：客户侧角色是否只能访问本客户数据（行级）
5. **SLA 升级链**：超时是否逐级上报（执行人→经理→负责人）
6. **外包隔离**：外包账号能否访问其他客户工单（应禁止）

---

## 十一、上线部署与验收

### 10.1 上线部署步骤

1. **环境准备**：本机/局域网服务器环境准备（PostgreSQL/Redis/ES + 应用进程）
2. **数据库迁移**：迁移脚本（alembic / golang-migrate）+ 备份 + 回滚预案
3. **应用发布**：灰度发布（负载均衡流量切换）→ 全量
4. **监控接入**：日志（ELK/本地日志）、监控（Prometheus/Grafana）、告警（短信/钉钉）
5. **数据初始化**：角色权限、字典、SLA 模板、知识库种子数据

### 10.2 验收标准

| 维度 | 标准 |
|---|---|
| 功能 | FR-01~22 全部通过验收用例 |
| 性能 | P95 < 500ms；并发 500 稳定 |
| 安全 | 等保三级；脱敏/加密/审计生效 |
| 权限 | 七级 RBAC 矩阵逐项验证通过 |
| 数据 | 多租户隔离验证；备份恢复演练通过 |

---

## 十二、风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 多合同多子项排期算法复杂 | 漏单/重单 | 幂等防重 + 周期表唯一约束 + 充分测试 |
| 换岗分摊口径争议 | 绩效纠纷 | 明确「实际承担工作量」口径 + 换岗留痕 |
| 外包数据泄露 | 安全事件 | 强隔离 + 脱敏 + NDA + 全审计 |
| AI 幻觉误分类 | 派单错误 | human-in-the-loop，AI 仅建议 |
| AI 大模型服务不可用 | 功能降级 | 多模型可切换 + 降级策略，主模型故障自动切换备用模型 |
| 客户侧权限越权 | 数据泄露 | 行级 RLS + 应用层双重校验 + 定期渗透 |

---

## 十三、附录

### A. 运维项目枚举

漏洞扫描 / 渗透测试 / 应急演练 / 安全加固 / 安全培训 / 代码审计 / 基线核查 / 安全巡检 / 安全评估 / 应急处置 / 重保值守 / 攻防演练 / 安全防护 / 设备巡检 / 等保测评 / 故障排查

### B. 服务频率枚举

次/天 · 次/周 · 次/月 · 次/季度 · 次/半年 · 次/年 · 不定期

### C. 工单状态枚举

待派单 / 已派单 / 计划中 / 进行中 / 待验收 / 已完成 / 已关闭 / 已取消

### D. 合同类型枚举

安全服务 / 安全运维 / 设备升级 / 购买设备 / 机房改造 / 其他

### E. 双品牌命名

- 平台侧：**信息服务AI管控平台 V1.0**
- 客户侧：**运维服务AI管控平台**

---

> **参考来源（同类产品与理念）**：
> - [ServiceNow vs Jira Service Management: Detailed Comparison](https://www.getint.io/blog/servicenow-vs-jira-service-management-which-itsm-tool-is-better-for-you)
> - [ITSM Ticketing Tools: 8 Platforms Compared for 2026](https://supportbee.com/blog/itsm-ticketing-tools)
> - [优云 ITSM 解决方案](https://www.uyun.cn/solutions-ITSM.shtml)
> - [嘉为蓝鲸 IT 服务管理中心 V4.6](https://xie.infoq.cn/article/55b2692872bf5a65885402316)
> - [腾讯云 AI 运维云平台深度实践](https://cloud.tencent.com.cn/developer/article/2722812)
> - [Fortinet FortiSOAR MSSP 方案](https://www.fortinet.com/content/dam/fortinet/assets/solution-guides/sb-fortisoar-mssp.pdf)
> - [企业级全链路 SRE 稳定性工程体系建设方案](https://cloud.tencent.com.cn/developer/article/2709322)

---

*—— IT运维集中管控平台 · 软件设计方案 V1.0（定稿）· 完 ——*
