# 步骤四：合同履约主干 API（客户→合同→子项→CI→接单→派单→工单→SLA→周期→提醒）

> 依据：《IT运维集中管控平台_软件设计方案.html》V1.0 定稿 · §6 核心表 / §8 API 面
> 范围：全链路 CRUD。周期拆分/定期工单/换岗分摊/SLA 预警等**算法**留步骤五。

## 1. 目标

在步骤三认证底座上，落地主干资源的增删改查与关键动作（创建工单、派单、状态流转），全部写接口挂 `require_role` + 审计，列表接口挂 `customer_scope_of` 行级隔离。

## 2. API 面（统一前缀 `/api/v1`，响应 `{"code","message","data"}`，分页 `?page=&size=`）

| 资源 | 方法 | 路径 | 角色 |
|---|---|---|---|
| 客户 | GET/POST | `/customers` | 读：登录即可（隔离）；写：sys_admin/sys_ops |
| 客户 | GET/PUT/DELETE | `/customers/{id}` | 写：sys_admin/sys_ops；删：sys_admin |
| 合同 | GET/POST | `/contracts` | 同上 |
| 合同 | GET/PUT/DELETE | `/contracts/{id}` | 同上 |
| 子项 | GET/POST | `/contract-items` | 同上 |
| 子项 | GET/PUT/DELETE | `/contract-items/{id}` | 同上 |
| CI | GET/POST | `/cmdb-cis` | 同上 |
| CI | GET/PUT/DELETE | `/cmdb-cis/{id}` | 同上 |
| 接单 | GET/POST | `/receives` | 写：sys_admin/sys_ops/ticket_mgr |
| 接单 | GET | `/receives/{id}` | 读：登录即可（隔离） |
| 工单 | GET/POST | `/work-orders` | 写：sys_admin/sys_ops/ticket_mgr |
| 工单 | GET | `/work-orders/{id}` | 读：登录即可（隔离） |
| 派单 | POST | `/work-orders/{id}/dispatch` | sys_admin/sys_ops/ticket_mgr |
| 状态流转 | PUT | `/work-orders/{id}/status` | sys_admin/sys_ops/ticket_mgr/cs_staff/sec_staff |
| SLA | GET/POST | `/sla-policies` | 写：sys_admin/sys_ops |
| SLA | GET/PUT/DELETE | `/sla-policies/{id}` | 写：sys_admin/sys_ops |
| 周期 | GET | `/cycles` | sys_admin/sys_ops/ticket_mgr（生成在步骤五） |
| 提醒 | GET | `/reminders` | sys_admin/sys_ops/ticket_mgr |

## 3. 新增文件

```
backend/app/
├── utils/pagination.py        # paginate(q, page, size, schema)
├── utils/wo_no.py             # 工单号 WO-YYYY-NNNN
├── schemas/customer.py        # CustomerCreate/Update/Out
├── schemas/contract.py        # Contract/CmdbCi/ContractItem 三组
├── schemas/work_order.py      # OrderReceive/WorkOrder/Dispatch/Assignee
├── schemas/service.py         # SlaPolicy/ServiceCycle/ServiceReminder
├── api/v1/customers.py
├── api/v1/contracts.py        # 合同 + 子项 + CI 三个 router
├── api/v1/work_orders.py      # 接单 + 工单 两个 router（含派单/状态流转）
└── api/v1/services.py         # SLA + 周期 + 提醒 三个 router
```

## 4. 关键设计

- **行级隔离**：`deps.scope_filter(q, model, scope)`——客户侧用户仅见本客户数据；`customer`/`contract`/`cmdb_ci`/`order_receive` 直接按 `customer_id` 过滤，`contract_item`/`work_order` 经 `contract` 关联过滤。
- **工单号**：`WO-YYYY-NNNN`，`utils/wo_no.py` 按年递增（MVP 单进程足够）。
- **派单校验**：执行人 `workload_ratio` 合计须为 100%（换岗分摊在步骤五做精确重算）。
- **状态机**：硬编码合法迁移表（待派单→已派单→计划中→进行中→待验收→已完成→已关闭；旁路已取消），非法迁移 400。
- **统一错误**：沿用步骤三 `HTTPException` 处理器。

## 5. 验证

```bash
cd backend && .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
# 登录拿 token 后，依次：
# 1) 建客户 → 2) 建合同 → 3) 建子项 → 4) 建 CI → 5) 接单 → 6) 创建工单 → 7) 派单(2人 60/40) → 8) 状态流转
# 全程返回 code=0；写操作后 sys_audit_log 应有记录；非法状态流转应 400
```

## 6. 后续衔接

步骤五基于本步骤：周期拆分算法、APScheduler 定期工单、换岗分摊重算、SLA 分级预警，配套 pytest 单测；换岗端点 `POST /work-orders/{id}/assignees/transfer` 在步骤五实现。
