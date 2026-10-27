# GitHub 交付布局修复 · 2026-10-27

## 原因与修复

复现基线：GitHub 分支 `codex/compact-studio-ui-20261027`，提交 `296886115f037fefd6a81d1e18e7d2788d29ac7a`。

原上传提交混入了另一轮未完成的 AppShell 和 Dashboard 模板修改，未包含它们依赖的样式。无定位样式的 `skip-content` 链接成为外层网格第一个子项：在 1280×720 下，链接占据第一列，侧栏移至 x=228、宽 1034px，正文被挤到 x=18、y=702、宽 210px。不是队友的操作问题。

恢复仓库内 `docs/design/20261022/pre-compact-source/` 保存的已验收页面结构，同时保留备课桌满屏标记和备课桌版隐藏面包屑的行为。不引入工作区中仍在进行的其他设计改动。额外修复手机端备课桌：浮动工具栏脱离文档流后，父容器需要明确的视口高度，否则桌面高度会塌缩为零。

## 验证

在独立 worktree 从上述远程提交开始，以 `npm ci` 安装依赖；未使用主工作区已有的依赖、构建产物或未提交源码。

- 前端单元测试：203 通过。
- `npm run build`：通过；保留既有大于 500kB 的构建分包提示。
- 实际应用入口（非模型页面夹具）：Vite 开发服务及生产 preview 均检查。
- 160 组布局组合：开发/生产 × 经典紫橙/银蓝学院 × 8 页 × 5 尺寸。
- 页面：资源库、工作台、课程中心、模拟授课、成长档案、知识库、个人中心、AI 评课。
- 尺寸：1280×720、1366×768、1440×900、1920×1080、390×844。
- 检查侧栏宽度、网格位置、正文宽度、桌面工作台无额外滚动、课程桌面高度。
- 两个服务中分别验证十个课程物件打开弹窗、Escape 关闭及焦点返回、原版 UI 切换。
- 页面运行异常 0；观察到的 assets/models HTTP 加载失败 0。

`production-*.png` 是修复后的真实浏览器截图，使用隔离 API 模拟数据；`github-before.png` 是修复前的实际复现。账号名称、课程进度等随真实用户数据变化；本轮没有测试真人摄像头、麦克风或真实模型调用，也没有改动后端和录像协议。

## 重跑浏览器检查

在项目根目录开两个终端分别运行：

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5193 --strictPort
```

```powershell
npm --prefix frontend run build
npm --prefix frontend run preview -- --host 127.0.0.1 --port 5194 --strictPort
```

第三个终端运行（需已安装 Edge）：

```powershell
New-Item -ItemType Directory -Force output/playwright
npx --yes --package @playwright/cli playwright-cli -s=github-verify open http://127.0.0.1:5193 --browser=msedge
npx --yes --package @playwright/cli playwright-cli -s=github-verify run-code --filename=frontend/tests/delivery-layout-browser.js
```

## 队友更新

以下命令以本地没有冲突改动为前提；如 Git 提示存在改动，请先保存自己的工作，不要强制覆盖。

```powershell
git fetch origin
git switch codex/compact-studio-ui-20261027
git pull --ff-only origin codex/compact-studio-ui-20261027
npm --prefix frontend ci
```

停止旧前端进程并重新运行原启动命令。部署 dist 的环境需重新 `npm --prefix frontend run build` 后部署新的整个 dist。浏览器选择“备课桌版”，需要与经典截图相同时选择“经典紫橙”；原版 UI 继续保留。不要从 main 或旧 ZIP 启动来验证本分支。
