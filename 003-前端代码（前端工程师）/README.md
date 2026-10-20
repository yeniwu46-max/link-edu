# 003-前端代码（前端工程师）

前端工程源码仍由仓库根目录下的 `frontend/` 维护，本目录不复制源码，避免出现两套不一致的前端实现。

## 源码入口

- 页面与路由：`frontend/src/main.js`、`frontend/src/views/`
- 应用框架与导航：`frontend/src/layouts/AppShell.vue`
- 样式：`frontend/src/styles.css`、`frontend/src/functional-ui.css`
- 静态素材：`frontend/public/`
- 测试：`frontend/tests/`

## 本机启动

在仓库根目录运行：

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
```

更完整的前后端配置和课堂启动方式见 `docs/classroom-runbook.md`。
