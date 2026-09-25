# 步骤十七：客户侧自助门户 + RAG 问答（阶段五 · FR-19 / FR-17）

> 依据：《IT运维集中管控平台_软件设计方案.html》V1.0 定稿 · §4.16 / §4.18
> 范围：客户自助报障/概览（合同履约、工单进度、交付报告）+ 知识库 RAG 问答（可配置 LLM，无密钥降级检索）。

## 1. 目标

- **自助门户**：客户侧角色（`cust_admin`/`cust_service`）自助报障（建接单 + 工单）、一键概览合同履约/工单进度/交付报告；全程按 `customer_scope_of` 行级隔离，客户只能看/建本人客户数据。
- **RAG 问答**：知识库检索 + 可配置大模型摘要（统一 LLM 抽象层，OpenAI 兼容 API）；未配置密钥时降级为「检索片段」返回，绝不泄露未发布条目。

## 2. 改动

- **表**：`work_order` 新增 `description`（报障描述，Text 可空）——迁移 `0010`。
- **配置**：`LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL`（可选，空 = 未启用）。
- **后端**：`/portal/tickets`、`/portal/overview`、`/kb-articles/ask`。

## 3. 业务规则

- **报障**：客户侧 `customer_id` 强制取本人 scope；平台侧须显式传 `customer_id`。报障同时落 `order_receive`（source=客户报障）+ `work_order`（type=客户工单，status=待派单）。
- **概览**：返回本人客户合同列表、工单各状态计数、最近工单、最近交付（均 scope_filter）。
- **RAG**：仅检索 `status=已发布` 条目；LLM 配置时生成摘要，否则/异常时返回检索片段（`mode=retrieval`）；调用失败回退，不阻塞。

## 4. 文件清单

- `app/models/work_order.py` — 增 `description`
- `alembic/versions/0010_portal.py` — 迁移
- `app/core/config.py` — 增 LLM 三项
- `app/schemas/portal.py` — 报障/概览 schema
- `app/schemas/kb.py` — `KbAskIn`
- `app/services/rag_service.py` — 检索 + LLM 摘要 + 降级
- `app/api/v1/portal.py` — 自助报障 + 概览
- `app/api/v1/kb.py` — `POST /kb-articles/ask`
- `app/api/v1/router.py` — 挂载 portal
- `tests/test_rag_service.py` / `tests/test_portal.py` — 单测

## 5. API

- `POST /portal/tickets` 自助报障
- `GET /portal/overview` 门户概览
- `POST /kb-articles/ask` RAG 问答（`{"question": "..."}`）

## 6. 角色

- 报障/概览：`sys_admin / sys_ops / ticket_mgr / cust_admin / cust_service`（客户侧行级隔离）。
- RAG 问答：同上报障角色（客户自助问答可用），仅返回已发布条目。

## 7. 验证

```bash
cd backend && .venv/Scripts/activate
alembic upgrade head          # 建 work_order.description
python -m pytest tests -q
```
