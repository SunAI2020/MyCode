# ITSM 性能压测（JMeter）

## 前置

1. 部署环境运行：`docker compose -f docker-compose.prod.yml up -d --build`（或本地 `uvicorn` + `npm run dev`）。
2. 完成迁移与种子：`docker compose -f docker-compose.prod.yml exec backend python -m app.db.seed`，获取管理员初始密码。

## 运行

```bash
# 非 GUI 模式（命令行）
jmeter -n -t perf/itsm-load.jmx \
  -Jhost=localhost -Jport=8000 \
  -Jadmin_password=<管理员密码> \
  -l results.jtl -e -o report/

# GUI 模式：jmeter 打开 perf/itsm-load.jmx，运行后查看「汇总报告」
```

## 场景与阈值

| 场景 | 接口 | 目标 |
|---|---|---|
| 登录 | `POST /api/v1/auth/login` | 提取 token |
| 工单列表 | `GET /api/v1/work-orders` | P95 < 500ms |
| 客户列表 | `GET /api/v1/customers` | P95 < 500ms |
| 合同列表 | `GET /api/v1/contracts` | P95 < 500ms |
| 门户概览 | `GET /api/v1/portal/overview` | P95 < 500ms |
| 知识库检索 | `GET /api/v1/kb-articles?q=登录` | P95 < 500ms |

**验收**：并发 500 稳定运行，错误率 0，聚合报告 P95 < 500ms（对应设计 §10.2）。

## 报告解读

- 汇总报告关注 `Average` / `P95(第95百分位)` / `Error%`。
- `Error% > 0` 时先看断言失败（响应码非 200）与后端日志；常见原因为 token 提取失败（密码错误 / 未 seed）。
- 若后端为单 worker，建议压测前确认 `ENABLE_SCHEDULER` 不影响请求路径。
