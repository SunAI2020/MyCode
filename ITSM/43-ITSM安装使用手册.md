# ITSM 系统安装使用手册（新手超详细版）

> 面向：零基础用户（非程序员也能照着做）
> 覆盖：前端、后端、手机 APP、云服务器的安装 / 配置 / 端口 / 容器数据库 / 登录 / 脱敏 / 人脸识别 / 打卡拍照

---

## 目录

1. [系统是什么](#一系统是什么)
2. [安装前的准备（装 3 个软件）](#二安装前的准备)
3. [一键安装（最快，推荐）](#三一键安装)
4. [手动安装详解（看懂每一步）](#四手动安装详解)
5. [手机 APP 安装](#五手机-app-安装)
6. [云服务器部署（阿里云）](#六云服务器部署)
7. [日常使用操作](#七日常使用操作)
8. [常见问题 FAQ](#八常见问题)

---

## 一、系统是什么

IT运维集中管控平台（ITSM）是一套「合同 → 子项 → 工单」全链路运维管理系统。它由三部分组成：

| 部分 | 技术 | 作用 | 端口 |
|---|---|---|---|
| 前端（网页） | Vue3 | 管理员/员工在电脑浏览器操作 | 5173（开发）/ 8080（生产） |
| 后端（接口） | FastAPI | 业务逻辑，前端和 APP 都调它 | 8000 |
| 手机 APP | uni-app | 服务人员在手机上打卡/签到 | 与前端同端口 |
| 数据库 | PostgreSQL | 存数据 | 5433 |
| 缓存 | Redis | 加速 | 6379 |
| 全文检索 | Elasticsearch | 知识库搜索 | 9200 |

> 一句话理解：**数据库存数据 → 后端算逻辑 → 前端/APP 展示和操作**。

---

## 二、安装前的准备

无论用一键脚本还是手动安装，都需要先装 3 个软件：**Docker、Python、Node.js**。

### 2.1 Windows 用户

#### ① 安装 Docker Desktop

1. 打开 https://www.docker.com/products/docker-desktop/ ，下载 Windows 版。
2. 双击安装，一路「下一步」，**安装完成后重启电脑**。
3. 重启后双击桌面「Docker Desktop」图标，等它右下角图标变绿（鲸鱼图标不再转圈）。
4. 验证：按 `Win + R`，输入 `cmd` 回车，输入 `docker --version`，显示版本号即成功。

#### ② 安装 Python 3.13

1. 打开 https://www.python.org/downloads/ 下载 Python 3.13。
2. 双击安装，**务必勾选最下方的「Add python.exe to PATH」**，再点「Install Now」。
3. 验证：cmd 里输入 `python --version`，显示 `Python 3.13.x` 即成功。

#### ③ 安装 Node.js 20

1. 打开 https://nodejs.org/ 下载 LTS 版（长期支持版）。
2. 双击安装，一路「下一步」。
3. 验证：cmd 里输入 `node -v`，显示 `v20.x` 即成功。

### 2.2 Linux 用户（云服务器）

```bash
# Docker
curl -fsSL https://get.docker.com | bash
systemctl enable --now docker

# Python 3
apt install -y python3 python3-pip        # Ubuntu/Debian
yum install -y python3 python3-pip        # CentOS

# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

---

## 三、一键安装

> 前提：已装好 Docker、Python、Node.js（见第二节）。

### 3.1 Windows 一键安装

1. 把项目文件夹（`ITSM`）放到任意位置，比如 `D:\ITSM`。
2. 双击文件夹里的 **`install.bat`**。
3. 脚本会自动：检查环境 → 启动数据库 → 配置后端 → 安装依赖 → 建表 → 写入初始账号 → 装前端依赖。
4. 看到「安装完成」后，双击 **`start.bat`**，会自动弹出两个命令行窗口（后端 + 前端）。
5. 浏览器打开 **http://localhost:5173** 即可登录。

### 3.2 Linux 一键安装

```bash
cd /opt/ITSM
bash install.sh     # 首次安装
bash start.sh       # 启动
```

### 3.3 脚本做了什么（看懂不慌）

| 步骤 | 命令 | 含义 |
|---|---|---|
| 启动数据库 | `docker compose up -d` | 用 Docker 拉起 PostgreSQL/Redis/ES |
| 建表 | `alembic upgrade head` | 创建全部数据表 |
| 初始账号 | `python -m app.db.seed` | 写入 8 个角色 + 管理员 admin + 初始密码 |
| 启动后端 | `uvicorn app.main:app --port 8000` | 后端跑在 8000 端口 |
| 启动前端 | `npm run dev` | 前端跑在 5173 端口 |

---

## 四、手动安装详解

> 想理解每一步、或脚本失败时手动排查，请看这里。

### 4.1 启动数据库（容器）

```bash
# 在项目根目录 ITSM/ 下执行
docker compose up -d

# 查看是否都起来了（3 个容器都 healthy 即成功）
docker compose ps
```

- PostgreSQL：宿主机 **127.0.0.1:5433**（账号/密码/库名都是 `itsm`）
- Redis：**127.0.0.1:6379**
- Elasticsearch：**127.0.0.1:9200**

### 4.2 配置后端环境变量

```bash
cd backend
cp ../.env.example .env      # Linux/macOS
copy ..\.env.example .env    # Windows
```

关键配置（`backend/.env`）：

```
DATABASE_URL=postgresql+psycopg://itsm:itsm_password@localhost:5433/itsm
SECRET_KEY=请改成一段随机长字符串
CORS_ORIGINS=http://localhost:5173
```

> SECRET_KEY 生成方法：`python -c "import secrets;print(secrets.token_urlsafe(32))"`

### 4.3 安装后端依赖 + 建表 + 初始数据

```bash
cd backend
python -m pip install -r requirements.txt   # 安装依赖
python -m alembic upgrade head              # 建表
python -m app.db.seed                       # 写入角色/管理员/字典/SLA/知识
```

> seed 会打印管理员 admin 的初始密码（未设置时是随机生成，请记下来）。

### 4.4 启动后端

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 接口文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/v1/health

### 4.5 启动前端

```bash
cd frontend
npm install       # 首次安装依赖
npm run dev       # 启动（http://localhost:5173）
```

### 4.6 登录验证

浏览器打开 http://localhost:5173 ，账号 `admin`，密码是 seed 输出的初始密码。

---

## 五、手机 APP 安装

手机 APP 是 `mobile/` 目录下的 uni-app 工程，一套代码可跑 H5 / 小程序 / App。

### 5.1 方式一：H5 预览（最快，无需真机）

```bash
cd mobile
npm install
npm run dev:h5          # 浏览器打开手机模式即可预览
```

### 5.2 方式二：真机调试（HBuilderX）

1. 下载安装 HBuilderX：https://www.dcloud.io/hbuilderx.html
2. 菜单「文件 → 导入 → 从本地目录导入」，选 `mobile/` 目录。
3. 手机连电脑（开启 USB 调试），或用 HBuilderX 扫码。
4. 点「运行 → 运行到手机或模拟器」。

### 5.3 方式三：打包成 App / 小程序

1. HBuilderX 打开项目 → 菜单「发行」。
2. App：选「原生 App-云打包」（需注册 DCloud 账号 + 证书）。
3. 小程序：选对应平台（微信小程序需在 manifest.json 填 appid）。

### 5.4 APP 登录与后端地址

- APP 内 `src/api/index.ts` 的 `BASE_URL`：
  - H5 用空字符串（走 vite 代理 / nginx 反代）。
  - 真机/打包：改成后端完整地址，如 `http://你的服务器IP:8000`。

---

## 六、云服务器部署（阿里云）

### 6.1 开通服务器 + 安全组开端口

1. 购买一台 ECS（2核4G 起），系统选 Ubuntu 22.04。
2. 在「安全组」里放行端口：**22、80、443、8000、8080**（5433/6379/9200 不要对公网开放）。
3. SSH 登录服务器（Windows 用 Xshell/Putty，或 `ssh root@服务器IP`）。

### 6.2 上传代码 + 一键部署

```bash
# 本地把 ITSM 目录上传到服务器（或用 git）
scp -r ITSM root@服务器IP:/opt/

# 服务器上
cd /opt/ITSM
bash install.sh
```

### 6.3 用生产模式（容器 + nginx，对外 8080）

```bash
# 准备生产环境变量
cp .env.production.example .env.production   # 填 SECRET_KEY、POSTGRES_PASSWORD

# 一键构建并启动全部服务（含 nginx 前端）
docker compose -f docker-compose.prod.yml up -d --build

# 迁移 + 种子
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend python -m app.db.seed

# 访问 http://服务器IP:8080
```

### 6.4 绑定域名 + HTTPS（可选）

1. 域名解析 A 记录指向服务器 IP。
2. 用 nginx/certbot 配置 HTTPS 证书（`frontend/nginx.conf` 已留反代 `/api`、`/uploads`）。

---

## 七、日常使用操作

### 7.1 登录

- 地址：http://localhost:5173 （或生产 http://IP:8080）
- 账号：`admin`，密码：seed 时输出的初始密码。
- 首次登录后请立即改密码（后续版本会加改密页）。

### 7.2 七级角色与权限

| 角色 | 能看到/能做什么 |
|---|---|
| 系统管理员 sys_admin | 全部 |
| 系统运维 sys_ops | 监控/备份，不碰业务数据 |
| 工单管理 ticket_mgr | 接单/派单/改价改时限 |
| 客服 cs_staff | 只看进度 |
| 安服 sec_staff | 自己的工单 + 签到打卡 |
| 客户管理员 cust_admin | 本客户合同/工单 |
| 客户服务 cust_service | 本客户报障/评价 |
| 外包 outsource | 仅自己被指派的外包任务 |

> 前端/APP 菜单会按角色自动裁剪（不同角色看到的菜单不同）。

### 7.3 数据脱敏

系统对敏感字段自动脱敏，**客户侧 / 外包账号**看到的是遮蔽后的数据：

| 类型 | 原文 | 客户侧看到 |
|---|---|---|
| 电话 | 13812341234 | 138****1234 |
| IP | 10.1.2.3 | 10.1.*.* |
| 金额 | 10000 | *** |

平台管理员看到原文，客户/外包看到脱敏值，无需任何操作，系统自动完成。

### 7.4 人脸识别登录

- 当前为**预留接口**（`POST /api/v1/auth/biometric`，未接入人脸 SDK 时返回 501）。
- 客户端用手机自带的指纹/面容识别（设备级生物识别）保护本地登录态，无需后端人脸库。
- 若需真正的人脸比对，需接入阿里云实人认证/腾讯云人脸核身 SDK（见 `39-人脸识别预留.md`）。

### 7.5 打卡拍照（移动端签到）

1. 手机 APP 登录后，进入「签到」页。
2. 点「定位」→ 获取当前 GPS 位置（H5 需 HTTPS 授权）。
3. 点「拍照留证」→ 拍照或选图。
4. 选「签到」或「签退」，点提交。
5. 记录会带经纬度 + 照片 + 时间，可在后端 `/api/v1/checkins` 查询。

### 7.6 各功能模块入口

| 模块 | 前端路径 | 说明 |
|---|---|---|
| 仪表盘 | /dashboard | 数据看板 |
| 客户管理 | /customers | 客户 CRUD |
| 合同管理 | /contracts | 合同/子项/服务对象 |
| 工单管理 | /work-orders | 全生命周期 |
| 自助门户 | /portal | 客户报障/概览 |
| 知识库 | /knowledge | 检索/RAG/ES 回填 |
| 工作流 | /workflows | 流转规则配置 |
| SLA/周期 | /sla | 周期/预警/升级 |

---

## 八、常见问题 FAQ

**Q1：`docker compose up -d` 报错？**
→ 确认 Docker Desktop 已启动（图标变绿）。

**Q2：后端 8000 端口被占用？**
→ 换端口：`python -m uvicorn app.main:app --port 8001`，并同步改前端 `vite.config.ts` 的 proxy 和 `backend/.env` 的 CORS。

**Q3：登录提示「用户名或密码错误」？**
→ 密码是 seed 输出的随机口令，不是 admin123。忘记就重新 seed 或查数据库。

**Q4：数据库 5433 连不上？**
→ 确认 `docker compose ps` 里 postgres 容器是 running；5433 是本机专用端口，云服务器上不要对公网开放。

**Q5：手机 APP 连不上后端？**
→ 改 `mobile/src/api/index.ts` 的 `BASE_URL` 为后端实际地址；真机需与电脑同一局域网。

**Q6：ES/Redis 没装会不会出错？**
→ 不会。后端有优雅降级：无 Redis 用内存缓存，无 ES 用 SQL 检索，无 LLM 用规则降级。

**Q7：如何彻底卸载？**
→ `docker compose down -v`（连数据一起删），删除项目文件夹即可。

---

> 更多技术细节见 `26-差距分析与完善方案.md`、`41-阿里云部署方案.md`；每步开发文档 `01~42` 均在本目录。
