# 步骤二十五：移动端前端（uni-app）

> 依据：《IT运维集中管控平台_软件设计方案.html》V1.0 定稿 · §8.6 阶段六 · §6.3/6.4 移动端
> 范围：uni-app（Vue3 + Vite + TS）一套代码多端（H5 / 小程序 / App），对接步骤二十四后端。

## 1. 目标

在 `mobile/` 建 uni-app 移动端，服务人员/管理员按角色裁剪：

1. **登录**：JWT 登录（复用 `POST /api/v1/auth/login`），token 持久化。
2. **工作台**：今日签到状态 + 我的工单汇总。
3. **工单**：列表（按状态筛选）+ 详情 + 状态流转。
4. **签到打卡**：GPS 定位（`uni.getLocation`）+ 拍照（`uni.chooseImage`）→ 上传 → 签到。
5. **我的**：用户信息 + 退出。

## 2. 技术方案

- 脚手架：`@dcloudio/uni-preset-vue#vite-ts`（Vue3 + Vite + TS）。
- 状态：Pinia（`stores/auth.ts` 存 token + 用户）。
- 请求：`src/api/index.ts` 封装 `uni.request`，统一 `Authorization: Bearer` + 响应解包。
- 路由：`pages.json`（uni-app 页面路由）。
- 生物识别：登录页预留「指纹/人脸快捷登录」（`uni.checkIsSupportSoterAuthentication`），失败回退密码登录。

## 3. 页面清单

| 页面 | 路径 | 说明 |
|---|---|---|
| 登录 | `pages/login/login` | 账号密码 + 生物识别预留 |
| 工作台 | `pages/index/index` | 今日签到 + 工单统计 |
| 工单列表 | `pages/workorder/list` | 状态筛选 + 分页 |
| 工单详情 | `pages/workorder/detail` | 详情 + 状态流转 |
| 签到打卡 | `pages/checkin/checkin` | GPS + 拍照 + 上传 + 提交 |
| 我的 | `pages/mine/mine` | 用户信息 + 退出 |

## 4. 对接端点

| 功能 | 端点 |
|---|---|
| 登录 | `POST /api/v1/auth/login` |
| 当前用户 | `GET /api/v1/auth/me` |
| 工单列表 | `GET /api/v1/work-orders` |
| 工单状态 | `PUT /api/v1/work-orders/{id}/status` |
| 今日签到 | `GET /api/v1/checkins/today` |
| 签到 | `POST /api/v1/checkins` |
| 上传照片 | `POST /api/v1/uploads` |

## 5. 验证

```bash
cd mobile && npm install
npm run build:h5        # H5 构建（可部署到 nginx 或本地预览）
npm run dev:h5          # 浏览器预览（默认 localhost:5173）
```

## 6. 说明

- 小程序/App 需 HBuilderX 编译（`manifest.json` 已配 `appid` 占位）；H5 端立即可验证。
- 生产 H5 部署：`dist/build/h5` 复制到 nginx，`/api` 与 `/uploads` 反代到后端（与 PC 前端一致）。
