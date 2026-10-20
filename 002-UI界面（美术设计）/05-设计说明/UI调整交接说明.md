# 临客 LINK 前端 UI 调整交接说明

## 1. 当前交付状态

- 项目仓库：`yeniwu46-max/link-edu`
- 当前本地分支：`gao/dev`
- 对比基线：`bc36379`（当前 `origin/main` 与 `origin/gao/dev` 均指向该提交）
- 当前状态：以下调整已在本地完成并通过构建，但尚未提交、推送或创建 Pull Request。
- 前端地址：`http://127.0.0.1:5188`
- 后端地址：`http://127.0.0.1:5001`

## 2. 调整目标

本轮调整统一了登录页、应用外壳、工作台、课程中心、教学训练、模拟课堂与资源库的视觉语言。整体采用深色沉浸式界面、圆角控制台布局、玻璃面板、橙紫渐变强调色和适量交互动效，同时补充移动端布局与减少动态效果设置。

## 3. 页面与功能调整

### 3.1 登录页

- 增加 `LiquidEther` 流体光效，支持鼠标交互与自动流动。
- 调整首屏内容退出、登录卡片进入的滚动动画，使两个阶段的切换更连贯。
- 为系统“减少动态效果”设置提供静态降级。
- 登录卡片的高度变化保留轻量过渡，避免与 GSAP 的位移动画相互干扰。

涉及文件：

- `frontend/src/views/LandingView.vue`
- `frontend/src/components/fx/LiquidEther.vue`
- `frontend/src/components/fx/liquidEtherEngine.js`
- `frontend/src/components/fx/liquidEtherFallback.js`

### 3.2 应用外壳与全局视觉

- 将桌面端改为固定高度的圆角控制台结构，左侧导航与右侧工作区形成一个完整应用窗口。
- 工作区使用独立滚动，顶部导航保持可见。
- 增加视频背景及暗色遮罩，统一各业务页面的空间层次。
- 统一玻璃面板、按钮、圆角、悬停、聚焦态与滚动条样式。
- 增加 1180px、900px、620px 三档响应式适配。
- 将 Naive UI 的配置与消息组件改为显式导入，保证生产构建解析一致。

涉及文件：

- `frontend/src/App.vue`
- `frontend/src/layouts/AppShell.vue`
- `frontend/src/styles.css`

### 3.3 工作台

- 重新组织工作台为更紧凑的模块化布局，统一训练、周进度、快捷入口、AI 评分和成长趋势卡片。
- “继续训练”卡片增加循环视频背景，并处理页面切换后的自动播放与资源释放。
- 优化卡片层级、悬停状态、数据图表和快捷入口的视觉表现。
- 重做 AI 评课校正选项，扩大可点击区域并补充键盘聚焦状态。

涉及文件：

- `frontend/src/views/DashboardView.vue`
- `frontend/src/styles.css`

### 3.4 课程中心

- 筛选栏、重点课程、普通课程和详情抽屉统一为玻璃面板样式。
- 优化课程卡片间距、标题截断、进度条、按钮与悬停反馈。
- 调整桌面端和移动端的栏目结构，窄屏下改为单列浏览。

涉及文件：

- `frontend/src/views/CoursesView.vue`
- `frontend/src/styles.css`

### 3.5 教学训练

- 将摄像头权限申请从页面进入阶段移到用户点击“开始训练”之后。
- 保留用户的默认摄像头设置，但避免用户尚未开始训练时浏览器立即弹出授权请求。

涉及文件：

- `frontend/src/views/TrainingView.vue`

### 3.6 模拟课堂

- 将“开始课堂”按钮替换为带高光折射效果的 `SpecularButton`。
- 保留原有禁用状态、准备状态、点击事件和按钮文案。
- 动效组件支持指针跟随、键盘操作、移动端与减少动态效果设置。

涉及文件：

- `frontend/src/views/ClassroomView.vue`
- `frontend/src/components/fx/SpecularButton.vue`

### 3.7 资源库

- 将原有普通列表重做为可拖动的资源卡片墙。
- 右侧资料桌自适应当前窗口剩余高度，桌面端两排展示，避免页面继续向下溢出。
- 卡片采用统一设计的教育资料封面，不直接使用文件首页截图作为封面。
- 支持“全部、官方标准、实操清单、院校案例、外部资源”分类筛选。
- 筛选后卡片自动重新居中排布，并支持一键重置卡片位置。
- 区分拖动与点击：拖动用于整理位置，点击用于打开阅读器。
- PDF 文件在站内阅读器预览；Markdown 清单和链接在站内排版展示。
- 阅读器支持关闭、键盘 `Esc`、原文件下载和移动端全屏显示。
- 官方 Word 大纲额外生成 PDF 阅读版本，原 Word 文件仍保留下载入口。

涉及文件：

- `frontend/src/views/ResourcesView.vue`
- `frontend/src/components/DraggableResourceCard.vue`
- `frontend/src/components/MarkdownReader.vue`
- `frontend/src/data/libraryResources.js`
- `frontend/public/library/`

## 4. 已加入资源库的资料

| 分类 | 资料 | 阅读方式 | 下载格式 |
| --- | --- | --- | --- |
| 官方标准 | 小学教师资格面试大纲 | 站内 PDF | DOC |
| 官方标准 | 中学教师资格面试大纲 | 站内 PDF | DOC |
| 官方标准 | 幼儿园教师资格面试大纲 | 站内 PDF | DOC |
| 实操清单 | 教资面试着装与教姿实操清单 | 站内 Markdown | MD |
| 院校案例 | 普洱学院教资面试辅导案例 | 站内 PDF | PDF |
| 院校案例 | 师范生教师职业能力测试实施材料 | 站内 PDF | PDF |
| 外部资源 | 高校教资面试资源索引 | 站内 Markdown | MD |

资源文件目录：

- `frontend/public/library/original/`：原始下载文件
- `frontend/public/library/preview/`：站内 PDF 阅读版本
- `frontend/public/library/thumbs/`：文件首页缩略图备份

## 5. 新增前端依赖

| 依赖 | 用途 |
| --- | --- |
| `ogl` | 模拟课堂高光按钮的 WebGL 渲染 |
| `three` | 登录页流体光效渲染 |

对应文件：`frontend/package.json`、`frontend/package-lock.json`。

## 6. 验证结果

- `npm run build`：通过。
- `npm test`：44 项测试全部通过，0 项失败。
- 前端 `/resources`：可访问。
- PDF 预览资源：返回 `200 application/pdf`。
- Markdown 阅读资源：返回 `200 text/markdown`。
- 后端 `/api/health`：返回 `200`，数据库状态为 SQLite。

构建过程仍会提示现有主包体积超过 500 kB。该提示不影响本次构建成功，但后续可通过页面级动态加载拆分登录页 WebGL 和课堂相关模块。

## 7. 负责人验收建议

1. 在桌面端检查登录页流体光效、滚动进入登录区以及减少动态效果设置。
2. 检查工作台视频背景能否静音自动播放，切换页面后是否正常释放。
3. 在课程中心验证筛选、课程详情和响应式布局。
4. 在教学训练页面确认进入页面时不会立即申请摄像头权限，开始训练后才申请。
5. 在模拟课堂确认“开始课堂”按钮的点击、禁用和高光效果。
6. 在资源库拖动卡片，逐个打开 PDF 与 Markdown，并测试原文件下载。
7. 使用 900px 以下和 620px 以下窗口宽度检查侧栏、卡片墙与阅读器布局。

## 8. 提交前注意事项

- 建议提交前只纳入源码、依赖锁文件与 `frontend/public/library/` 正式资源。
- 本地 `artifacts/` 和 `output/` 目录包含生成或检查过程中的文件，应先确认内容，再决定是否提交。
- 当前所有改动尚未推送到远端，负责人无法仅通过 GitHub 分支直接看到这些本地变更。
