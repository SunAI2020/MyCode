# OWASP ZAP 安全扫描清单（ITSM）

## 1. 扫描目标与范围

- 目标：`http://localhost:8080`（nginx 入口，含前端 + `/api` 反代）。
- 认证：使用管理员账号做**已认证**主动扫描（`ZAP 上下文 → 认证 → 脚本/HTTP 登录`，登录 `POST /api/v1/auth/login`，提取 `data.access_token` 作为 `Authorization: Bearer`）。
- 另跑一轮**未认证**被动扫描，验证未登录无法访问业务数据。

## 2. ZAP 配置

1. **Context**：新建 `itsm`，包含 `http://localhost:8080`。
2. **认证**：HTTP 登录表单 / 或自定义脚本注入 `Authorization` 头。
3. **Session Management**：Cookie / Header（token）。
4. **主动扫描策略**：启用 SQL 注入、XSS、命令注入、路径遍历、CSRF、越权（需人工配合）。
5. **API 扫描**：对 `/api/v1/openapi.json` 做 OpenAPI 主动扫描。

## 3. OWASP Top 10（2021）关注点与本系统对照

| 风险 | 关注点 | 系统对应 |
|---|---|---|
| A01 失效访问控制 | IDOR / 越权 / 行级隔离 | `scope_filter` + `assert_scoped` + `require_role`；客户侧仅见本客户数据 |
| A02 加密失败 | TLS / 敏感字段加密 | 密码 bcrypt；`Outsourcing.nda` Fernet 加密；生产建议 TLS 反代 |
| A03 注入 | SQL / 命令 / 模板注入 | SQLAlchemy 参数化查询；无命令拼接 |
| A04 不安全设计 | 审计缺失 / 速率限制 | 写操作全审计（before/after/IP）；登录无速率限制（TODO） |
| A05 安全配置错误 | 调试暴露 / 默认口令 | 无弱默认口令；`docs` 可关（生产可禁） |
| A06 脆弱组件 | 依赖漏洞 | 依赖见 `requirements.txt` / `package.json`，需定期 `pip-audit`/`npm audit` |
| A07 认证失效 | JWT / 会话 | JWT 签名 + 过期；SECRET_KEY 生产固定 |
| A08 软件与数据完整性 | 反序列化 / 依赖投毒 | 无 pickle；依赖锁定 |
| A09 日志与监控失效 | 审计完整性 | `sys_audit_log` 含 IP/时间/before/after |
| A10 SSRF | 外部 URL 抓取 | LLM/ES 地址来自配置，无用户可控 URL（需复核） |

## 4. 关键断言（人工复核）

- 客户侧角色（`cust_service`）访问他人客户合同/工单 → 403 或 404（行级隔离生效）。
- 客户侧角色读取工单/合同响应，`contact`/`ip`/`amount` 已脱敏（`138****1234` / `10.1.*.*` / `***`）。
- 未认证请求 `GET /api/v1/work-orders` → 401。
- 审计日志（`sys_audit_log`）记录含 `ip` 字段（非空）。

## 5. 输出

- 导出 ZAP 报告（HTML/JSON）存档；高风险项闭环后方可上线。
