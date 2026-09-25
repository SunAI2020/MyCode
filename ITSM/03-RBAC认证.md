# 步骤三：RBAC 认证（JWT + 角色校验 + 行级隔离 + 脱敏 + 审计）

> 依据：《IT运维集中管控平台_软件设计方案.html》V1.0 定稿 · §5.1 七级角色 / 权限矩阵
> 范围：打通 `/auth/login`、`/auth/me`，落地统一认证底座（依赖注入 + 审计 + 行级隔离锚点）。

## 1. 目标

在步骤二 18 张表基础上，实现 JWT 认证全链路：登录签发 Token、请求鉴权、七级角色校验、客户侧行级隔离锚点、字段脱敏工具、操作审计，为步骤四主干 API 复用。

## 2. 认证流程

1. `POST /auth/login`：校验用户名 + bcrypt 密码 → 签发 JWT（`sub=user_id`）→ 落审计 → 返回 token + 用户信息（含角色列表 + 客户 scope）。
2. 后续请求带 `Authorization: Bearer <token>` → `get_current_user` 解析并加载用户。
3. `require_role(*codes)` 依赖校验角色；客户侧角色经 `sys_user_role.customer_id` 得到行级隔离锚点。

## 3. 七级角色

| 侧 | 角色 | code | 行级隔离 |
|---|---|---|---|
| 平台 | 系统管理员 | sys_admin | 无（全量） |
| 平台 | 系统运维 | sys_ops | 无 |
| 平台 | 工单管理 | ticket_mgr | 无 |
| 平台 | 客服 | cs_staff | 无 |
| 平台 | 安服 | sec_staff | 无 |
| 客户 | 客户系统管理员 | cust_admin | customer_id |
| 客户 | 客户服务管理 | cust_service | customer_id |

## 4. 新增文件

```
backend/app/
├── core/deps.py              # get_db / get_current_user / require_role / role_rows_of / customer_scope_of
├── schemas/auth.py           # LoginRequest / RoleBrief / UserOut / TokenResponse
├── services/audit_service.py # record() 落 sys_audit_log
└── api/v1/auth.py            # POST /auth/login · GET /auth/me
```

## 5. 关键设计

- **统一错误**：`main.py` 注册 `HTTPException` 处理器，错误体统一为 `{"code":<status>,"message":...,"data":null}`，HTTP 状态码保留。
- **脱敏**：`core/security.py` 已有 `mask_phone/mask_ip/mask_amount`，本步骤在序列化层预留接入点，列表接口（步骤四）按角色应用。
- **审计**：登录即写 `sys_audit_log`（action=login, ip）。
- **行级隔离**：`customer_scope_of` 返回客户侧用户绑定的 `customer_id`（平台侧为 None），步骤四列表查询据此过滤。

## 6. 验证

```bash
cd backend && .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
# 另开终端：
curl -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'
# 拿 access_token 后：
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer <token>"
# 无 token 应返回 401；错误账号 401；停用账号 403
```

## 7. 后续衔接

步骤四基于本步骤：客户→合同→子项→CI→接单→派单→工单→周期→提醒→SLA 全链路 CRUD，所有写接口挂 `require_role` + 审计，客户侧查询挂 `customer_scope_of`。
