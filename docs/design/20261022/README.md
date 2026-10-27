# LINK UI 设计交付

最终角色方向是统一的 2D 像素小人。页面保留备课桌与纸片字系统，可在顶栏切换回原版 UI。

## 最新实现 · 紧凑满屏版

最新实际效果在 [compact-implemented](compact-implemented/)：紧凑工作台、满屏备课桌、课程弹窗、桌面三席与手机横排、阿贝贝老师。新增 [连续动作录像](compact-implemented/pixel-actions-v2.webm) 和 [运行截图](compact-implemented/pixel-actions-v2.png)。这些来自运行代码与隔离模拟数据，不是设计生成图。

运行用学生 v2 图集与动作清单位于 `frontend/public/assets/characters/pixel/v2/`；旧 v1 图集和原版界面保留。详细实现、202 项前端与 74 项后端测试、真实设备未测边界见 [最新验收记录](../../compact-studio-ui-20261022.md)。下面 `implemented/` 中的滚动坐席与大标题属于上一轮历史截图。

## 设计参考

- [四人像素三视图](pixel/turnarounds.png)：正面、侧面、背面，最终造型参考。
- `01-courses-concept.png` 至 `08-knowledge-concept.png`：生成的页面概念稿，包含示例内容；不是运行截图，其中旧人物造型已被像素方案替代。
- `characters-reference.png`、`model-previews/`：已否决的 3D 探索，仅保留历史，不作为最终验收图。
- `prompts.json`、`pixel/prompts.json` 和 `pixel/turnaround-prompt.txt`：内置 image_gen 提示词；`pixel/ming-mouth-edit.txt` 记录发言嘴型修订。

## 已实现效果

`implemented/` 内均为实际浏览器截图，使用隔离的模拟数据：

- `pixel-cast-preview.png`：四人同屏，直接读取运行用透明图集。
- `pixel-default-layout.png`、`pixel-dialogue-classic.png`、`pixel-dialogue-academy.png`、`pixel-dialogue-mobile.png`：课堂布局和坐席。
- `studio-*-final.png`：八个主页面，经典/学院主题，桌面/手机尺寸。
- `studio-long-greeting.png`：动态长姓名换行。
- `original-courses-classic.png`、`original-courses-academy.png`：保留的原课程 UI。

运行图集位于 `frontend/public/assets/characters/pixel/`，每人 12 个姿态。开发预览：`http://127.0.0.1:5188/tests/pixel-cast-browser.html`。验收详情和真实设备未测范围见 [实现记录](../../pixel-studio-ui-20261022.md)。

`original-source/` 是本轮设计调整前的源码快照；当前实际原版课程入口使用 `OriginalCoursesView.vue`。
