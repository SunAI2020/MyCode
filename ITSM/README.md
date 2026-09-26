# IT运维集中管控平台（ITSM）

面向安服团队 / MSSP 的「合同履约 + 工单 + 服务」一体化集中管控平台。
以「合同 → 子项 → 工单」为主轴，统一承载客户合同履约、内部任务、外包协作、问题整改、交付、绩效、SLA 提醒、AI 增强与知识沉淀。

> 设计依据：《IT运维集中管控平台_软件设计方案.html》V1.0 定稿（主）+《安全运维集中管控平台_完整交付文档.html》V7.0（界面/权限补充）。
> 独立项目：自包含，不引用兄弟项目（ai-vuln / AI-EASM / AI-PTS / SSQ）的目录、模块或数据库。

## 技术栈

- 后端：Python 3.13 + FastAPI + SQLAlchemy 2.0 + Alembic + APScheduler
- 认证：JWT（PyJWT）+ bcrypt，七级 RBAC + 客户行级隔离
- 数据库：PostgreSQL 16（Docker Compose，宿主机端口 **5433**）
- 前端：Vue3 + Vite + Element Plus + Pinia + Vue Router + Axios + ECharts

## 目录结构

```
ITSM/
├── docker-compose.yml          # postgres:16-alpine（127.0.0.1:5433）
├── .env.example                # DATABASE_URL / SECRET_KEY / CORS
├── 01~06-*.md / .html          # 每步骤开发文档（md+html 双格式）
├── backend/                    # FastAPI 后端
│   ├── app/{main,core,db,models,schemas,api,services,scheduler,utils}
│   ├── alembic/                # 数据库迁移
│   └── tests/                  # pytest 单测
└── frontend/                   # Vue3 前端
    └── src/{api,stores,router,layouts,views}
```

## 快速启动

```bash
# 1. 启动数据库（端口 5433）
docker compose up -d

# 2. 后端
cd backend
python -m venv .venv && .venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp ../.env.example .env
alembic upgrade head                                  # 建表（18 张业务表）
python -m app.db.seed                                 # 写入角色/字典/管理员
uvicorn app.main:app --reload                         # http://localhost:8000/docs

# 3. 前端
cd ../frontend
npm install
npm run dev                                           # http://localhost:5173
```

**默认账号**：`admin`，初始密码取 `ADMIN_INITIAL_PASSWORD`；未设置时 seed 生成强随机口令并打印（登录后请立即修改）。

## 七级 RBAC

平台侧：系统管理员 `sys_admin` / 系统运维 `sys_ops` / 工单管理 `ticket_mgr` / 客服 `cs_staff` / 安服 `sec_staff`；
客户侧：客户系统管理员 `cust_admin` / 客户服务管理 `cust_service`（经 `sys_user_role.customer_id` 行级隔离）。

## 已实现功能（MVP 六步骤）

1. **工程骨架** — docker-compose + 后端/前端脚手架
2. **数据库建模** — 18 张表 + Alembic + 种子数据
3. **RBAC 认证** — JWT 登录 + `require_role` + 行级隔离 + 脱敏 + 审计
4. **合同履约主干 API** — 客户→合同→子项→CI→接单→派单→工单→SLA→周期→提醒 全链路 CRUD
5. **核心算法** — 周期拆分 / 定期工单(APScheduler) / 换岗分摊 / SLA 分级预警 + 单测
6. **Vue3 前端** — 三区布局 + 登录 + 客户/合同/工单/SLA 页面接通后端

## 测试

```bash
cd backend
python -m pytest tests -q     # 周期拆分 / 换岗分摊 / SLA 分级 / 定期工单幂等
```

## 开发约定

每一步开发前，工作详情以 md + html 双格式存档于项目根目录（`01-工程骨架.*` ~ `06-Vue3前端.*`）。
