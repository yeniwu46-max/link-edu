# B-01 登录 / 注册 / 会话最小执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 只完成 B-01 的关键闭环：认证接口能说清错误、登录页防重复提交、忘记密码有响应、token 失效自动退出。

**不做：** 真实短信/邮箱找回、Google/Apple/Facebook 登录、权限模型重构、模拟授课核心逻辑、B-02 至 B-10。

**当前实现范围：**

- 后端统一返回缺失、无效、过期 JWT 的 401 错误码。
- 登录空输入返回 400，注册重复账号继续返回 409。
- 前端在进入受保护路由前验证 `/api/auth/me`。
- 任意受保护 API 返回 401 时清理 token 并回到登录页。
- 网络故障不伪装成登录成功。
- 登录/注册按钮使用同一加载锁，忘记密码显示明确占位说明。

## 任务 1：后端认证错误

**文件：**

- 修改 `backend/app.py`
- 修改 `backend/routes.py`
- 新增 `backend/tests/test_auth_routes.py`

- [x] 为空登录、重复注册、连续 3 次登录、缺失/无效/过期 token 写测试。
- [x] 在 `app.py` 注册 `expired_token_loader`、`invalid_token_loader`、`unauthorized_loader`，返回 `code` 和中文 `message`。
- [x] 在 `routes.py@login` 增加空账号/密码的 400 校验。
- [x] 验证命令：

```powershell
Set-Location 'E:\link-edu-main\backend'
C:\Python314\python.exe -m pytest tests/test_auth_routes.py -q
```

## 任务 2：前端会话失效

**文件：**

- 修改 `frontend/src/stores/auth.js`
- 修改 `frontend/src/services/api.js`
- 修改 `frontend/src/main.js`
- 新增 `frontend/src/utils/authSession.js`
- 新增 `frontend/tests/authSession.test.mjs`

- [x] `auth.hydrate()` 成功时设置 `authenticated`；401 时清理 `link_token`；网络错误时返回 `offline` 并保留错误提示。
- [x] Axios 对非登录/注册请求的 401 派发 `link:auth-expired` 事件，避免把错误密码误判为 token 失效。
- [x] 路由守卫只允许已验证会话进入受保护页面；失效后回到 `/`。
- [x] 验证命令：

```powershell
Set-Location 'E:\link-edu-main\frontend'
node --test tests/authSession.test.mjs
```

## 任务 3：登录页交互

**文件：**

- 修改 `frontend/src/views/LandingView.vue`
- 新增 `frontend/src/utils/authValidation.js`
- 新增 `frontend/tests/authValidation.test.mjs`

- [x] 抽出最小表单校验：账号/密码、姓名、密码长度、确认密码。
- [x] 抽出认证错误映射：网络错误优先显示“无法连接服务”，接口 message 原样展示。
- [x] `submit()` 在 loading 时直接返回；注册成功只有在后续登录也成功后才显示成功文案。
- [x] “忘记密码？”显示“当前版本暂未接入短信/邮箱找回，请联系管理员重置密码。”。
- [x] 验证命令：

```powershell
Set-Location 'E:\link-edu-main\frontend'
node --test tests/authValidation.test.mjs
npm run build
```

## 任务 4：最小回归

- [x] 后端认证测试通过：3 passed。
- [x] 前端新增认证测试通过：3 passed。
- [x] 前端生产构建通过：Vite build 成功。
- [ ] 完整前端回归仍有 3 个既有导航测试失败：`navigationSource.test.mjs` 检查 AppShell 清理监听、CoursesView 搜索实现和未知路由 fallback；这些不属于 B-01，本次不扩展修复。

## 验收标准

1. 登录、注册、退出均可连续操作 3 次。
2. 错误密码、网络断开、JWT 过期分别显示真实提示。
3. 401 后 `localStorage.link_token` 被清除，受保护页面不再保持假登录态。
4. 忘记密码点击后有可见说明。

当前项目目录没有 `.git`，本计划不包含 commit 操作。
