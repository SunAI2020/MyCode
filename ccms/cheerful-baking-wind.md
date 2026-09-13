# Claude Code Management System (CCMS) — 架构设计与实施计划

## 背景

设计一个完整的 Claude Code 管理系统，提供项目管理、文件编辑调试、终端输出、子 Agent 管理等功能，主界面为可视化中控台，以办公室场景拟人化展示各个子 Agent 的运行状态。

---

## 一、技术栈

### 后端
| 层级 | 技术 | 理由 |
|------|------|------|
| Web 框架 | **FastAPI** + uvicorn | 异步原生，WebSocket 一等支持，自动生成 OpenAPI 文档 |
| ORM | **SQLAlchemy 2.0** (async) + asyncpg | Python 生态标准，支持 Alembic 迁移 |
| 认证 | **python-jose (JWT)** + passlib + bcrypt | 标准 JWT 认证方案 |
| 实时通信 | **FastAPI WebSocket** + **Redis pub/sub** | 多 worker 解耦广播 |
| 任务队列 | **Celery** (Redis broker) + celery-beat | 持久化任务队列，支持重试、调度 |
| LLM SDK | **anthropic SDK** | 代码库中已有 13 个文件使用 |
| 系统监控 | **psutil** | 代码库已有使用 |

### 前端 (Web)
| 层级 | 技术 | 理由 |
|------|------|------|
| 框架 | **React 18 + TypeScript** + Vite | 组件化适合复杂仪表盘 |
| CSS | **Tailwind CSS** | 快速 UI 迭代 |
| 图表 | **Recharts** + D3.js | React 原生图表组件 |
| 办公室动画 | **PixiJS 8** (WebGL 2D) | 唯一能处理 16+ 角色独立动画的方案 |
| 终端 | **xterm.js** | VS Code 同款终端模拟器 |
| 代码编辑器 | **Monaco Editor** | VS Code 同款编辑器 |
| 状态管理 | **Zustand** | 轻量全局状态 |

### 移动端 (微信)
| 层级 | 技术 | 理由 |
|------|------|------|
| 小程序框架 | **Taro 4.x** (React) | 与 Web 前端共享 React 技术栈，组件可复用 |
| UI 组件库 | **Taro UI** + NutUI | 微信风格移动端组件 |
| 图表 | **ECharts for Taro** | 小程序端图表最佳方案 |
| 状态管理 | **Zustand** (同 Web 端) | 跨端共享状态管理模式 |
| HTTP 客户端 | **Taro.request** | 小程序原生请求封装 |
| WebSocket | **Taro.connectSocket** | 小程序原生 WebSocket |
| 公众号框架 | **werobot** (Python) | 微信消息处理标准库 |
| 推送服务 | 微信模板消息 + 客服消息 API | 官方消息推送通道 |

---

## 二、系统架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                         微信生态                                      │
│  ┌─────────────────────────┐    ┌──────────────────────────────┐    │
│  │   微信小程序 (Taro)      │    │   微信公众号                   │    │
│  │  ┌─────┐ ┌─────┐ ┌────┐│    │  ┌────────┐ ┌──────────────┐ │    │
│  │  │首页 │ │Agent│ │任务││    │  │模板消息│ │ 客服消息/指令 │ │    │
│  │  │概览 │ │列表 │ │管理││    │  │ 推送   │ │ 菜单交互     │ │    │
│  │  └─────┘ └─────┘ └────┘│    │  └────────┘ └──────────────┘ │    │
│  │  ┌─────┐ ┌─────┐       │    │                               │    │
│  │  │监控 │ │设置 │       │    │                               │    │
│  │  └─────┘ └─────┘       │    │                               │    │
│  └───────────┬─────────────┘    └──────────────┬───────────────┘    │
│              │ wx.request/ws                    │ XML/JSON 回调      │
└──────────────┼──────────────────────────────────┼────────────────────┘
               │                                  │
               ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    浏览器 (React + TypeScript)                         │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ 左侧边栏  │  │ 主内容区      │  │ 图表面板  │  │ 办公室场景    │    │
│  │ 项目管理  │  │ - 文件编辑器  │  │ - 进度   │  │ PixiJS WebGL │    │
│  │ 会话管理  │  │ - Agent详情  │  │ - Token  │  │ 角色动画      │    │
│  │ Agent设置│  │ - 会话消息   │  │ - CPU/内存│  │              │    │
│  │ 节点管理  │  │              │  │ - 存储   │  │              │    │
│  │ 技能管理  │  │              │  │          │  │              │    │
│  │ 定时任务  │  │              │  │          │  │              │    │
│  │ 设置     │  │              │  │          │  │              │    │
│  └──────────┘  └──────────────┘  └──────────┘  └──────────────┘    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              终端面板 (xterm.js + WebSocket)                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
               │  REST API (HTTPS)           │  WebSocket (wss://)
               ▼                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FastAPI 后端 (uvicorn)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ REST路由 │ │WebSocket │ │ Auth JWT │ │ 微信服务 │ │ 中间件   │  │
│  │ - 项目   │ │ Manager  │ │ - 登录   │ │ - 小程序 │ │ CORS     │  │
│  │ - Agent  │ │ - 终端   │ │ - 刷新   │ │ - 公众号 │ │ 限流     │  │
│  │ - 文件   │ │ - Agent  │ │ - 微信   │ │ - 推送   │ │ 日志     │  │
│  │ - 指标   │ │ - 指标   │ │   UnionID │ │ - 指令   │ │          │  │
│  │ - 技能   │ │          │ │          │ │          │ │          │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐   │
│  │项目服务  │ │Agent编排 │ │终端管理  │ │ 指标采集 (psutil)    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
               │                             │
               ▼                             ▼
┌──────────────────────┐    ┌──────────────────────────┐
│  PostgreSQL 16       │    │    Redis 7               │
│  (主数据库 + 微信表)  │    │  (pub/sub/缓存/会话)     │
└──────────────────────┘    └──────────────────────────┘
               │
               ▼
┌──────────────────────┐    ┌──────────────────────────┐
│  Celery Workers      │    │  文件系统                 │
│  - Agent 工作循环    │    │  - 项目文件               │
│  - 定时任务          │    │  - 报告输出               │
│  - 微信推送任务      │    │  - 日志归档               │
│  - 指标采集          │    │                          │
└──────────────────────┘    └──────────────────────────┘
```

### 2.2 微信端架构详解

```
┌─────────────────────────────────────────────────┐
│              微信小程序 (Taro 4.x)               │
│                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │  首页   │  │  Agent  │  │  任务   │         │
│  │ 概览卡片│  │ 状态列表│  │ 创建/审批│        │
│  │ 快捷操作│  │ 详情控制│  │ 结果查看│         │
│  └─────────┘  └─────────┘  └─────────┘         │
│  ┌─────────┐  ┌─────────┐                      │
│  │  监控   │  │  我的   │                      │
│  │ 实时图表│  │ 设置/绑定│                     │
│  │ 日志查看│  │ 通知偏好│                      │
│  └─────────┘  └─────────┘                      │
│                                                 │
│  底部 Tab: 🏠首页 🤖Agent 📋任务 🔔消息 👤我的  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│            微信公众号 (服务号)                    │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ 模板消息 │  │ 客服消息 │  │ 菜单交互      │  │
│  │          │  │          │  │              │  │
│  │• 任务完成│  │• 快捷指令│  │ 🤖 Agent状态 │  │
│  │• 异常告警│  │• NLP解析 │  │ 📊 今日统计  │  │
│  │• Token预警│ │• 语音转文│  │ ⚙️ 快捷操作  │  │
│  │• 日报周报│  │• 对话管理│  │ 📋 查看报告  │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────┘

---

## 三、数据库核心表 (PostgreSQL)

### 核心实体关系
```
users 1──* projects
users 1──* sub_agents
users 1──* sessions
projects 1──* agent_sessions
sub_agents 1──* agent_sessions
sub_agents 1──* agent_tasks
sub_agents 1──* agent_token_usage
sub_agents *──* skills
nodes 1──* agent_sessions
cron_jobs 1──* cron_executions
```

### 主要表（共 20 张表）

| 表名 | 用途 |
|------|------|
| `users` | 用户账户 |
| `refresh_tokens` | JWT 刷新令牌 |
| `projects` | 项目信息及根目录 |
| `project_members` | 项目成员权限 |
| `file_snapshots` | 文件版本快照 |
| `agent_role_presets` | 16 个内置角色预设 + 自定义 |
| `sub_agents` | 子 Agent 实例 |
| `agent_skills` | Agent 与技能多对多关联 |
| `agent_sessions` | Agent 工作会话 |
| `agent_tasks` | Agent 任务队列 |
| `agent_token_usage` | Token 用量记录 |
| `sessions` / `session_messages` | 用户会话与消息 |
| `nodes` | 计算节点注册 |
| `skills` | 技能定义 |
| `cron_jobs` / `cron_executions` | 定时任务与执行历史 |
| `terminal_sessions` | 终端会话记录 |
| `dashboard_layouts` | 用户仪表盘布局 |
| `metric_snapshots` | 系统指标时序数据（按月分区） |
| `system_events` | 系统事件日志 |
| `settings` | 用户设置 (key-value) |
| `wechat_users` | 微信用户绑定 (openid/unionid) |
| `wechat_messages` | 微信消息记录 |
| `wechat_notifications` | 微信推送记录 |

### 微信相关表 DDL

```sql
-- 微信用户绑定表
CREATE TABLE wechat_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    openid          VARCHAR(128) NOT NULL UNIQUE,     -- 小程序 openid
    unionid         VARCHAR(128),                     -- 公众号/小程序互通 ID
    mp_openid       VARCHAR(128),                     -- 公众号 openid (可能不同)
    nickname        VARCHAR(128),                     -- 微信昵称
    avatar_url      VARCHAR(512),                     -- 微信头像 URL
    phone           VARCHAR(20),                      -- 微信手机号
    notification_enabled BOOLEAN DEFAULT true,
    push_agent_complete  BOOLEAN DEFAULT true,        -- Agent 任务完成推送
    push_agent_error     BOOLEAN DEFAULT true,        -- Agent 异常推送
    push_token_alert     BOOLEAN DEFAULT true,        -- Token 超额预警
    push_daily_report    BOOLEAN DEFAULT false,       -- 日报推送
    push_weekly_report   BOOLEAN DEFAULT true,        -- 周报推送
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 微信消息记录表
CREATE TABLE wechat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    openid          VARCHAR(128),
    msg_type        VARCHAR(32) NOT NULL,             -- text | voice | image | event | mini_program
    content         TEXT,                              -- 用户发送的内容
    response        TEXT,                              -- 系统回复内容
    intent          VARCHAR(64),                      -- NLP 解析后的意图
    metadata        JSONB DEFAULT '{}',               -- 附加数据
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 微信推送记录表
CREATE TABLE wechat_notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    template_id     VARCHAR(128),                     -- 微信模板消息 ID
    title           VARCHAR(255),
    content         JSONB NOT NULL,                   -- 模板消息字段
    url             VARCHAR(512),                     -- 点击跳转链接
    status          VARCHAR(32) DEFAULT 'pending',    -- pending | sent | failed
    sent_at         TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_wechat_users_openid ON wechat_users(openid);
CREATE INDEX idx_wechat_users_unionid ON wechat_users(unionid);
CREATE INDEX idx_wechat_messages_user_time ON wechat_messages(user_id, created_at DESC);
CREATE INDEX idx_wechat_notifications_user_time ON wechat_notifications(user_id, created_at DESC);
```

---

## 四、模块结构与文件布局

```
D:\python files\ccms/
├── docker-compose.yml              # PostgreSQL + Redis + App
├── pyproject.toml                  # Poetry 依赖管理
├── .env                            # 环境变量
├── alembic.ini                     # 数据库迁移配置
│
├── backend/
│   ├── main.py                     # FastAPI 入口
│   ├── config.py                   # 配置管理 (pydantic-settings)
│   ├── database.py                 # 异步 SQLAlchemy 引擎
│   ├── deps.py                     # 依赖注入
│   │
│   ├── api/                        # REST + WebSocket 路由
│   │   ├── auth.py, projects.py, agents.py, sessions.py
│   │   ├── nodes.py, skills.py, cron_jobs.py, terminal.py
│   │   ├── file_editor.py, metrics.py, settings.py, dashboard.py
│   │   └── wechat/                 # 微信相关路由
│   │       ├── __init__.py
│   │       ├── mini_program.py     # 小程序 API (登录、数据接口)
│   │       └── official_account.py # 公众号回调处理
│   │
│   ├── ws/                         # WebSocket 管理
│   │   ├── manager.py              # 连接管理器 (Redis pub/sub 桥接)
│   │   ├── terminal_handler.py     # 终端 WS 处理
│   │   └── agent_handler.py        # Agent 状态 WS 处理
│   │
│   ├── services/                   # 业务逻辑层
│   │   ├── agent_orchestrator.py   # ★ 核心：Agent 生命周期编排
│   │   ├── project_service.py, file_service.py
│   │   ├── terminal_service.py, metrics_service.py
│   │   ├── cron_service.py, auth_service.py
│   │   ├── wechat_service.py       # 微信服务 (登录/推送/消息/指令)
│   │   └── notification_service.py # 统一通知服务 (微信推送 + 站内信)
│   │
│   ├── models/                     # SQLAlchemy ORM 模型
│   │   ├── base.py, user.py, project.py
│   │   ├── sub_agent.py, agent_session.py
│   │   ├── skill.py, node.py, cron_job.py
│   │   ├── wechat.py               # 微信用户绑定、消息、推送记录
│   │   └── notification.py         # 统一通知模型
│   │
│   ├── schemas/                    # Pydantic 请求/响应模式
│   │
│   ├── tasks/                      # Celery 任务
│   │   ├── celery_app.py
│   │   ├── agent_tasks.py          # Agent 工作循环
│   │   ├── cron_tasks.py, metrics_tasks.py
│   │
│   ├── agents/                     # 子 Agent 定义
│   │   ├── base.py                 # BaseSubAgent 抽象类
│   │   ├── registry.py             # Agent 注册表
│   │   ├── presets.py              # ★ 16 个内置角色中文系统提示词
│   │   └── roles/                  # 每个角色一个模块
│   │
│   └── core/                       # 横切关注点
│       ├── security.py             # JWT + 密码哈希
│       ├── redis.py                # Redis 客户端
│       └── events.py               # 事件总线
│
├── frontend/
│   ├── package.json, vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx
│       ├── api/                    # API 客户端层
│       ├── hooks/                  # useWebSocket, useAgentStream...
│       ├── store/                  # Zustand 状态管理
│       └── components/
│           ├── layout/             # AppShell, LeftSidebar, TopBar
│           ├── sidebar/            # ProjectPanel, AgentPanel...
│           ├── dashboard/
│           │   ├── OfficeScene.tsx # PixiJS 画布封装
│           │   ├── office/         # OfficeRenderer, CharacterSprite, AnimationManager
│           │   ├── ChartsPanel.tsx
│           │   └── charts/         # 各图表组件
│           ├── terminal/           # TerminalPanel (xterm.js)
│           ├── editor/             # FileEditor (Monaco), FileTree
│           └── common/             # 通用组件
│
├── mini-program/                    # 微信小程序 (Taro 4.x + React)
│   ├── package.json
│   ├── project.config.json          # 微信小程序配置
│   ├── src/
│   │   ├── app.tsx                  # 小程序入口
│   │   ├── app.config.ts            # 全局配置 (tabBar, window, 权限)
│   │   ├── app.scss                 # 全局样式
│   │   │
│   │   ├── api/                     # API 客户端 (与 Web 共享类型)
│   │   │   ├── client.ts            # Taro.request 封装 + JWT 拦截器
│   │   │   ├── agents.ts            # Agent API
│   │   │   ├── tasks.ts             # 任务 API
│   │   │   ├── projects.ts          # 项目 API
│   │   │   ├── metrics.ts           # 指标 API
│   │   │   ├── auth.ts              # 微信登录 API
│   │   │   └── types.ts             # 共享类型定义
│   │   │
│   │   ├── hooks/                   # 自定义 Hooks
│   │   │   ├── useWebSocket.ts      # Taro.connectSocket 封装
│   │   │   ├── useAgentStream.ts    # Agent 状态订阅
│   │   │   ├── useMetrics.ts        # 实时指标
│   │   │   └── useWechatLogin.ts    # 微信登录流程
│   │   │
│   │   ├── store/                   # Zustand 状态管理
│   │   │   ├── authStore.ts
│   │   │   ├── agentStore.ts
│   │   │   └── appStore.ts
│   │   │
│   │   ├── pages/
│   │   │   ├── index/               # 首页 - 概览仪表盘
│   │   │   │   └── 项目数/Agent在线/Token/健康分/今日统计
│   │   │   ├── agents/              # Agent 管理
│   │   │   │   ├── list/            # Agent 列表 (卡片 + 状态指示器)
│   │   │   │   ├── detail/         # Agent 详情 + 操作 (暂停/唤醒/分配)
│   │   │   │   └── create/         # 创建 Agent (角色选择 + 配置)
│   │   │   ├── tasks/               # 任务管理
│   │   │   │   ├── list/            # 任务列表 (筛选/搜索)
│   │   │   │   ├── create/         # 快速创建 (支持语音输入🎤)
│   │   │   │   └── detail/         # 任务详情与结果
│   │   │   ├── monitor/             # 实时监控
│   │   │   │   ├── dashboard/      # 核心指标图表
│   │   │   │   └── terminal/       # 终端日志 (只读)
│   │   │   ├── notifications/       # 消息中心
│   │   │   └── settings/            # 设置
│   │   │       ├── profile/         # 个人信息 + 微信绑定
│   │   │       └── preferences/     # 通知偏好
│   │   │
│   │   └── components/              # 小程序组件
│   │       ├── AgentCard.tsx         # Agent 状态卡片
│   │       ├── StatusBadge.tsx       # 状态徽章 (工作/休息/异常)
│   │       ├── ProgressBar.tsx       # 进度条
│   │       ├── QuickActions.tsx      # 快捷操作按钮组
│   │       ├── MetricCard.tsx        # 指标卡片
│   │       ├── VoiceInput.tsx        # 语音输入组件
│   │       └── EmptyState.tsx        # 空状态占位
│   │
│   └── assets/                       # 静态资源
│       ├── icons/                    # TabBar 图标
│       └── images/                   # 启动图、占位图
│
└── migrations/                     # Alembic 迁移
```

---

## 五、核心功能设计

### 5.1 16 个内置子 Agent 角色

| # | 角色键 | 中文名 | 类别 |
|---|--------|--------|------|
| 1 | `project_manager` | 项目经理 | 管理 |
| 2 | `architecture_designer` | 架构设计师 | 开发 |
| 3 | `solution_designer` | 方案设计师 | 开发 |
| 4 | `ui_designer` | UI设计师 | 开发 |
| 5 | `programmer` | 程序员 | 开发 |
| 6 | `code_reviewer` | 代码审查员 | 开发 |
| 7 | `function_verifier` | 功能验证员 | 开发 |
| 8 | `project_auditor` | 项目审计师 | 管理 |
| 9 | `budget_manager` | 预算管理员 | 财务 |
| 10 | `security_engineer` | 安全工程师 | 安全 |
| 11 | `penetration_test_engineer` | 渗透测试工程师 | 安全 |
| 12 | `code_audit_engineer` | 代码审计工程师 | 安全 |
| 13 | `financial_accountant` | 财务会计师 | 财务 |
| 14 | `business_assistant` | 业务助理 | 行政 |
| 15 | `archive_manager` | 档案管理员 | 行政 |
| 16 | `clerk` | 文员 | 行政 |
| — | `custom` | 自定义角色 | 自定义 |

### 5.2 办公室动画场景设计

使用 PixiJS 2D WebGL 渲染，层次结构：
- **BackgroundLayer**: 办公室地板、墙壁、窗户、植物（静态，视差滚动）
- **DeskLayer**: 15-20 个工位，含走道网格
- **CharacterLayer**: 所有子 Agent 角色精灵
- **UILayer**: 状态气泡、名称标签
- **InteractionLayer**: 点击/悬停交互

角色状态机（由 WebSocket 事件驱动）：
```
空闲(idle) → [新任务] → 走向工位(walk) → 工作(work)
工作(work) → [任务完成] → 走向休息区(walk) → 休息(rest)
休息(rest) → [新任务] → 走向工位(walk) → 工作(work)
工作(work) → [需要展示] → 走向白板(walk) → 演示(present)
```

角色使用分层精灵设计（4 种基础体型 × 16 种职业配饰 × 5 种动画状态）。

### 5.3 WebSocket 实时事件协议

连接: `ws://host/ws`

**Agent 事件**:
- `agent:status_change` — { agent_id, old_status, new_status }
- `agent:task_start/progress/complete/error` — 任务生命周期
- `agent:token_usage` — 实时 token 消耗
- `agent:character_action` — 驱动办公室动画

**系统事件**:
- `metrics:update` — CPU/内存/磁盘/网络（每 5 秒）
- `terminal:output/closed` — 终端 I/O
- `node:status_change` — 节点状态变更
- `system:event` — 系统事件日志

### 5.4 Agent 工作循环 (Celery Worker 内执行)

```
1. 加载 Agent 配置、角色预设、系统提示词
2. 加载项目上下文（文件、历史）
3. 轮询 agent_tasks 待处理任务
4. 调用 Anthropic API (system prompt + 任务描述)
5. 处理工具调用 (read_file, write_file, execute_command, search, delegate)
6. 保存结果到数据库
7. 更新 token 用量和成本
8. 通过 Redis pub/sub 发送进度事件
9. 无任务时转为 'resting' → 最终 'idle'
10. 暂停时休眠并定期检查标志位
```

### 5.5 微信小程序核心功能

#### 首页概览

```
┌──────────────────────────┐
│  🔵 项目: 3 个           │
│  🟢 Agent 在线: 8/12     │
│  🟡 Token: 125.6K/500K   │
│  📊 系统健康: 96%        │
├──────────────────────────┤
│  今日任务完成:  ████░░ 67%│
│  成本估算:      ¥23.50   │
│  CPU: 45% | 内存: 12.5GB │
└──────────────────────────┘
```

#### Agent 状态卡片（带状态指示器）

```
┌──────────────────────────────┐
│ 🟢 项目经理-小张    [工作中]  │
│ ▸ 任务: 需求分解-XX项目      │
│ ▸ 进度: ████████░░ 80%       │
│ ▸ Token: 12.3K | 耗时: 8min  │
│ [暂停] [查看详情] [分配任务]  │
├──────────────────────────────┤
│ 🟡 程序员-小李      [休息中]  │
│ ▸ 上次: Bug修复 #142 (完成)  │
│ ▸ 累计Token: 89.2K           │
│ [唤醒] [分配任务]            │
├──────────────────────────────┤
│ 🔴 安全工程师-大刘  [异常]    │
│ ▸ 错误: API超时，已重试3次   │
│ [重试] [查看日志] [暂停]     │
└──────────────────────────────┘
```

#### 快捷操作
- 🎤 **语音指令**: 「让程序员检查一下登录模块的安全漏洞」→ 自动转文本 → NLP 路由到对应 Agent
- 📝 **文本指令**: 自然语言描述任务，自动解析意图 → 分配 Agent
- ⚡ **预设指令**: 代码审查、安全扫描、生成报告、项目统计

### 5.6 微信公众号功能

#### 模板消息推送

| 推送场景 | 触发条件 | 消息示例 |
|----------|---------|---------|
| Agent 任务完成 | 任务状态 → completed | ✅ [程序员-小李] 完成「修复登录Bug」，耗时12min，Token:8.5K |
| Agent 异常 | 任务状态 → error | ⚠️ [安全工程师-大刘] 任务「漏洞扫描」失败：API连接超时 |
| Token 预警 | 用量达 85% | 📊 今日 Token 已使用 85%(425K/500K)，建议调整预算 |
| 日报推送 | 每日 18:00 | 📋 今日总结：完成12个任务，Token 消耗350K，成本¥52.30 |
| 周报推送 | 每周一 9:00 | 📈 本周总结：完成67个任务，发现3个安全漏洞，成本¥380.00 |
| 系统通知 | 维护/升级 | 🔧 系统将于 02:00-03:00 进行维护升级 |

#### 公众号菜单结构

```
底部菜单:
┌─────────┬─────────┬─────────┐
│ 🤖 Agent │ 📊 概览  │ ⚙️ 操作  │
├─────────┼─────────┼─────────┤
│ 查看状态 │ 今日统计 │ 快速任务 │
│ 唤醒Agent│ 本周报告 │ 暂停所有 │
│ 我的任务 │ 成本报表 │ 系统状态 │
└─────────┴─────────┴─────────┘
```

#### 对话指令交互

```
用户: @程序员 检查 main.py 的安全问题
系统: ✅ 已创建任务 #1287，程序员-小李开始处理...
      [3分钟后]
系统: ✅ 任务完成！发现 3 个安全隐患：
      1. SQL注入风险 (高) - line 45
      2. 硬编码密钥 (中) - line 102
      3. 未验证输入 (低) - line 78
      📄 [查看完整报告]
```

### 5.7 微信统一认证流程

```
用户 (微信)                    CCMS 后端                  微信服务器
    │                             │                         │
    │── wx.login() ──────────────▶│                         │
    │                             │── code2session(code) ──▶│
    │                             │◀── openid + session_key─│
    │                             │                         │
    │                             │── 查询 wechat_users      │
    │                             │   (openid 是否存在?)    │
    │                             │                         │
    │◀── 返回 JWT token ─────────│                         │
    │   (或要求绑定已有账户)       │                         │
    │                             │                         │
    │── 后续 API 请求 ──────────▶│                         │
    │   (Authorization: Bearer)  │                         │
    │                             │                         │

绑定已有账户时:
    │── wx.login() → 获取 code ──▶│
    │── POST /auth/login ────────▶│ (用户名+密码+wechat_code)
    │◀── JWT token + 绑定成功 ────│ INSERT INTO wechat_users
```

---

## 六、实施计划（渐进式交付）

### 交付策略

基于审计结果，采用**三阶段渐进交付**而非单次 24 周冲刺：

| 里程碑 | 范围 | 时间 | 核心功能 |
|--------|------|------|----------|
| **MVP** | Web 端最小可用版本 | 12 周 | 3 个 Agent 角色、基础文件编辑+终端、静态图表 |
| **V1.0** | 完整 Web 端 | 24 周 | 16 个 Agent 角色、办公室动画、定时任务、全功能侧边栏 |
| **V2.0** | Web + 微信全平台 | 36 周 | 小程序 + 公众号推送、三端通知同步 |

### MVP (1-12 周): 最小可用产品

**目标**: 跑通端到端流程 — 创建项目 → 创建 Agent → 分配任务 → 查看结果

**阶段 1-3（5 周）**: 基础设施 + 文件编辑 + 终端
- Poetry 项目 + Docker Compose (PG + Redis)
- 核心表迁移（users/projects/sub_agents/agent_tasks/agent_sessions/terminal_sessions）
- JWT 认证（httpOnly Cookie）
- React + Vite + Tailwind 前端骨架 + AppShell + 左侧边栏（静态）
- 项目 CRUD + Monaco 编辑器 + 文件树
- xterm.js 终端面板 + PTY 服务

**阶段 4 MVP（4 周）**: 3 个 Agent 角色（程序员 + 代码审查员 + 安全工程师）
- 3 个角色预设系统提示词
- Agent CRUD + Celery 工作循环
- Anthropic API 集成（含错误处理 + 重试 + 熔断器）
- Agent 任务分配 + 结果展示

**阶段 5 MVP（3 周）**: 基础监控
- psutil 指标采集
- 3 类图表（Agent 进度 + Token 消耗 + CPU/内存）
- WebSocket 实时推送

### V1.0 (13-24 周): 完整 Web 平台

**阶段 6（4 周）**: 办公室动画场景
**阶段 6-8（6 周）**: 扩展至 16 个 Agent 角色 + 侧边栏面板 + 定时任务
**阶段 9（2 周）**: Outbox 模式 + 错误处理完善 + 命令执行沙箱

### V2.0 (25-36 周): 微信平台

**阶段 10（4 周）**: 微信小程序
**阶段 11（2 周）**: 公众号 + 推送系统
**阶段 12（3 周）**: 端到端打磨、安全加固、三端联调测试

---

## 七、审计发现与改进措施

> 以下是对原始计划进行严格审核后发现的重大问题及改进方案。按严重程度分类：
> 🔴 CRITICAL — 必须修复才能开始实施 | 🟠 HIGH — 必须在对应阶段前修复

### 9.1 🔴 分布式事务一致性 — 增加 Outbox 模式

**问题**: Agent 任务完成时需同时写入 PostgreSQL、发布 Redis 事件、推微信通知，缺少事务边界保证。

**改进**: 引入 **Outbox 模式**：
- 新增 `outbox_events` 表，在同一个 PG 事务中写入领域数据 + outbox 事件
- 独立的后台进程轮询 outbox 表，将事件发布到 Redis pub/sub
- 确保至少一次投递语义（at-least-once）
- 微信通知也通过 outbox 发布，由 `notification_service` 消费

### 9.2 🔴 单点故障 — 增加高可用方案

**问题**: PostgreSQL、Redis、Celery Workers 均为单点，无故障转移。

**改进**:
- **PostgreSQL**: 使用 `pgbouncer` 连接池，配置 `pool_size=20, max_overflow=10, pool_pre_ping=True`，每日 pg_dump 备份 + WAL 归档
- **Redis**: 开发环境使用单实例，生产环境配置 Redis Sentinel（主从 + 自动故障转移）
- **Celery Workers**: Docker healthcheck + `supervisord` 自动重启，添加 worker 心跳监控

### 9.3 🔴 调试功能缺失 — 明确调试方案

**问题**: 需求明确要求"文件编辑调试"，计划中无调试器设计。

**改进**: 采用两层调试策略：
1. **Agent 辅助调试**: 将代码 + 错误日志发送给对应 Agent 进行分析（集成在 Agent 工作循环中）
2. **交互式调试**: 使用 `debugpy` (Python Debug Adapter Protocol) 通过终端 WebSocket 实现断点调试，在 Monaco Editor 中设置断点，终端面板显示变量值

### 9.4 🔴 JWT 存储安全 — 统一安全策略

**问题**: 未指定 JWT 在各平台的存储方式，默认 localStorage 存在 XSS 风险。

**改进**:
- **Web**: 使用 `httpOnly, Secure, SameSite=Strict` Cookie 存储 JWT，而非 localStorage
- **小程序**: Taro Storage（微信沙箱环境相对安全），额外绑定 openid 做 token 绑定
- **Refresh Token**: 实现轮换机制（每次使用发放新 token，旧 token 失效）
- 添加 `fastapi-csrf-protect` 中间件

### 9.5 🔴 微信消息加解密 — 完整实现

**问题**: 未涉及微信消息加密协议、签名验证、session_key 管理。

**改进**: 新增 `backend/core/wechat_crypto.py`：
- 消息签名验证（SHA1(token + timestamp + nonce + msg_encrypt)）
- AES-256-CBC 消息解密
- `encryptedData` 解密（使用 session_key 获取手机号/用户信息）
- `session_key` 加密存储于 `wechat_users` 表
- Access Token 自动刷新（过期前 5 分钟刷新）

### 9.6 🔴 错误处理与重试策略

**问题**: 分布式系统无统一错误处理策略，无重试/退避策略。

**改进**: 
- **错误分类**: 瞬态错误（网络超时/429）vs 致命错误（API Key 无效/400）vs 业务错误（项目不存在）
- **重试策略**: 使用 `tenacity` 库，指数退避（初始 1s，最大 60s，最多 5 次重试）
- **熔断器**: 外部 API 连续 5 次失败后熔断 30 秒，释放 worker 资源
- **错误传播**: Celery worker 错误 → Redis pub/sub → WebSocket → 前端错误提示
- **WebSocket 重连**: 指数退避 + 抖动（1s/2s/4s/8s，最大 30s），重连后全量状态刷新

### 9.7 🔴 时间线修正

**问题**: 24 周对单个开发者不现实，实际预估为 36-50 周。

**改进**: 采用**渐进式交付**策略：
1. **MVP (12 周)**: 仅 Web 端，2-3 个 Agent 角色（程序员 + 代码审查员 + 安全工程师），基础文件编辑 + 终端，静态图表
2. **V1.0 (24 周)**: 完整 Web 端，16 个 Agent 角色，办公室动画场景，定时任务
3. **V2.0 (36 周)**: 微信小程序 + 公众号推送，全功能

### 9.8 🟠 Agent 编排器依赖解耦

**问题**: `agent_orchestrator.py` 可能形成循环依赖。

**改进**: 明确定义依赖方向：
```
agent_orchestrator (编排层)
  ├── → anthropic_client (API 调用)
  ├── → file_service (文件读写)
  ├── → terminal_service (命令执行)
  ├── → event_bus (发布事件，不直接依赖通知服务)
  └── → token_budget_manager (预算检查)

notification_service ← event_bus (订阅事件)
wechat_service ← event_bus (订阅通知事件)
ws/manager.py ← event_bus (订阅 Agent 状态更新)
```

### 9.9 🟠 "节点"概念定义

**问题**: "节点管理"中的"节点"概念从未明确定义。

**改进**: 明确定义：**节点 = 运行 CCMS 后端的计算节点**（物理机/虚拟机/容器实例）。每个节点承载 Celery Workers 和系统资源。表结构包含：`hostname, ip_address, status, cpu_cores, memory_gb, disk_gb, agent_count, last_heartbeat`。

### 9.10 🟠 数据库索引补充

在原有 4 个索引基础上，增加以下 11 个索引：
- `users(email)` — 登录查询
- `agent_sessions(agent_id, status, created_at)` — Agent 状态查询
- `agent_tasks(agent_id, status)` — 任务轮询
- `agent_token_usage(agent_id, recorded_at)` — Token 报告
- `metric_snapshots(metric_type, recorded_at DESC)` — 时序查询（新增）
- `file_snapshots(project_id, file_path)` — 文件历史
- `cron_jobs(next_run_at, is_active)` — Celery Beat 调度查询
- `projects(user_id)` — 用户项目列表
- `agent_role_presets(category, is_builtin)` — 角色浏览
- `terminal_sessions(user_id, status)` — 用户终端历史
- `sub_agents(user_id, status)` — 用户 Agent 列表

### 9.11 🟠 Anthropic API 速率限制与 Token 预算

**改进**: 新增 `token_budget_manager` 服务：
- 跟踪 Anthropic API 分层限制（RPM/TPM）
- 各 Agent 每日 Token 配额
- 各项目成本上限
- 多级预警（50%/75%/90% 用量）
- 高优先级任务 Token 预留
- API 调用前预检（pre-flight check）

### 9.12 🟠 命令执行沙箱

**改进**: Agent 的 `execute_command` 工具添加安全限制：
- 命令白名单（仅允许 `python`, `npm`, `git`, `pip`, `ls`, `cat` 等）
- 路径严格校验（所有文件操作必须在项目目录内）
- 超时限制（单命令最长 5 分钟）
- 委托深度限制（Agent 间委托最多 3 层）
- Docker 容器内运行（只读文件系统，仅项目目录可写）

### 9.13 🟠 隐私合规 (PIPL)

**改进**:
- `wechat_users` 添加 `consent_granted_at, consent_purpose, consent_version` 字段
- 实现数据导出 API：`GET /api/v1/user/export-data`
- 实现账户删除 API：`DELETE /api/v1/user/me`（级联删除所有数据）
- 项目文件加密存储（使用用户密钥加密）
- Agent 输出数据保留策略（默认 90 天后归档，可配置）

### 9.14 🟠 生产部署与备份

**改进**:
- 分离 `docker-compose.dev.yml` 和 `docker-compose.prod.yml`
- 生产环境考虑 Kubernetes/Docker Swarm
- PostgreSQL: 每日全量备份 + WAL 连续归档，保留 30 天
- 备份恢复演练（每月一次）
- 结构化日志（`structlog`，JSON 格式）+ Prometheus 指标导出
- 微信小程序审核预留 2 周缓冲时间

### 9.15 🟠 小程序包体积控制

**改进**: 2MB 主包限制应对策略：
- 分包加载（每个 Tab 独立分包）
- 使用 `echarts-for-weixin`（~400KB）代替完整 ECharts（~1MB）
- 考虑 Taro Preact 模式（减少 ~120KB）
- 图片资源使用 CDN 外链
- Tree-shaking + 代码压缩

---

## 八、更新后的风险评估

| 风险等级 | 组件 | 风险描述 | 缓解措施 |
|----------|------|----------|----------|
| 🔴 极高 | Agent 编排器 | 最复杂组件，风险最高 | MVP 先做 3 个角色，验证后再扩展 |
| 🔴 极高 | 办公室动画场景 | 需要游戏开发技能 | 先用几何图形占位，渐进增强 |
| 🔴 极高 | 微信公众号集成 | 加解密复杂，审核门槛高 | 尽早搭建本地测试环境 |
| 🟠 高 | 分布式事务 | PG/Redis/Celery 数据一致性 | Outbox 模式 |
| 🟠 高 | Anthropic API 限流 | 16 Agent 并发可能超限 | Token 预算管理 + 熔断器 |
| 🟠 高 | 微信小程序体积 | 依赖库可能超 2MB | 分包 + 轻量替代 |
| 🟡 中 | WebSocket 扩展性 | 大量终端连接 | 消息批处理 + 连接限制 |
| 🟡 中 | 时间线 | 预估偏乐观 | MVP 渐进交付策略 |

---

## 九、验证方案

1. **单元测试**: pytest 覆盖所有 service 层函数（含 wechat_service, notification_service）
2. **API 测试**: httpx + pytest-asyncio 测试所有 REST 端点（含微信 API）
3. **WebSocket 测试**: 验证事件广播与接收
4. **前端测试**: Vitest + React Testing Library
5. **小程序测试**: Taro 官方测试工具 + 微信开发者工具真机调试
6. **公众号测试**: 微信公众平台接口调试工具 + ngrok 本地回调测试
7. **端到端测试**: Playwright 模拟 Web 端操作，微信开发者工具模拟移动端
8. **性能测试**: WebSocket 并发连接、Redis pub/sub 吞吐量、小程序首屏加载
9. **安全测试**: JWT 过期/刷新、微信消息加密/解密、SQL 注入、XSS 防护

---

## 十、关键文件

### 后端核心
- `backend/services/agent_orchestrator.py` — Agent 生命周期编排引擎（整个系统的核心）
- `backend/agents/presets.py` — 16 个角色中文系统提示词
- `backend/services/wechat_service.py` — 微信登录/推送/消息/指令解析
- `backend/services/notification_service.py` — 三端统一通知服务
- `backend/ws/manager.py` — WebSocket 连接管理 + Redis pub/sub 桥接

### Web 前端核心
- `frontend/src/components/dashboard/office/OfficeRenderer.ts` — PixiJS 渲染引擎
- `frontend/src/components/dashboard/office/CharacterSprite.ts` — 角色精灵与状态机

### 微信端核心
- `mini-program/src/pages/agents/list/index.tsx` — Agent 列表页（最常用页面）
- `mini-program/src/pages/tasks/create/index.tsx` — 快速创建任务（含语音输入）
- `mini-program/src/hooks/useWechatLogin.ts` — 微信登录流程封装
