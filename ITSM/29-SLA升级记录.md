# 步骤二十九：SLA 升级记录（完善方案 P0 · §14.3）

> 依据：V7.0 · §14.3 SLA 契约引擎「超时逐级上报」· §18.2 escalation 表
> 范围：补 `Escalation` 升级记录表 + 超时工单扫描生成升级记录 + 列表查询。

## 1. 目标

SLA 超时工单按 `escalation_chain`（执行人→经理→负责人）生成**升级记录**，形成可追溯的升级链历史。

1. `Escalation` 模型（工单/级别/from/to/时间/原因）。
2. `scan_sla_escalations`：扫描 SLA 超时未完工单，按升级链首级生成记录（去重）。
3. `GET /escalations` 查询端点。

## 2. 文件清单

| 文件 | 说明 |
|---|---|
| `models/escalation.py` | `Escalation` 模型 |
| `alembic/versions/0014_escalation.py` | 迁移 |
| `schemas/escalation.py` | `EscalationOut` |
| `services/sla_service.py` | `scan_sla_escalations` |
| `api/v1/escalations.py` | 列表查询 |
| `router.py` / `scheduler/jobs.py` | 注册 + 定时接入 |
| `tests/test_escalation.py` | 回归测试 |

## 3. 设计

- 升级链取自 `WorkOrder.contract_item_id → ContractItem.sla_policy_id → SlaPolicy.escalation_chain`（"执行人→经理→负责人"）。
- 超时判断：`sla_deadline < today` 且工单未完成；首级升级 `nodes[0] → nodes[1]`，同工单同级别去重。

## 4. 验证

```bash
cd backend && python -m pytest -q
```
