## 更新说明（`gao/local-ui` / `4f6146d`）

### 概述
本次推送包含成长档案热力增强、AI 评课深色面板、训练录像与视觉证据，以及若干页面 UI 调整。  
远程分支：`origin/gao/local-ui`

---

### 1. 成长档案（热力 + 内容）

**文件**
- `frontend/src/views/GrowthView.vue`
- `frontend/src/styles.css`（`.growth-heat*` / `.growth-skill*` / `.growth-journal*`）

**改动**
- 训练日历独立面板：更大格子、日期角标、色阶图例
- 使用完整 `heatmap`，去掉 `slice(-28)` 截断
- 点选日期过滤「训练记录」，再点取消；展示当日场次 / 分钟
- 侧卡能力对比：末次 vs 区间均值（清晰 / 节奏 / 互动）
- 训练日志只读列表（`journals`）+ 空态引导  
- **未做**：写日志 POST、徽章墙、导出周报

---

### 2. AI 评课面板

**文件**
- `frontend/src/views/AiReviewView.vue`
- `frontend/src/styles.css`
- `frontend/tests/aiReviewFollowup.test.mjs`

**改动**
- 深色玻璃仪表盘布局（统计卡、主从列表、日历侧栏等）
- 限高 / 内部滚动，避免单栏过长

---

### 3. 训练录像 + 视觉证据

**新增**
- `backend/services/training_visual.py`
- `backend/tests/test_training_visual.py`
- `frontend/src/services/trainingReplayStore.js`
- `frontend/src/services/useTrainingRecorder.js`

**修改**
- `backend/routes.py`
- `backend/services/training.py`
- `backend/services/llm/deepseek.py`
- `frontend/src/views/TrainingView.vue`
- `frontend/src/services/dashboard.js`

**改动**
- 前端 MediaRecorder + IndexedDB 回放存储
- 后端视觉证据相关能力接入训练 / 评课链路

---

### 4. 其它 UI 微调

| 文件 | 说明 |
|------|------|
| `CoursesView.vue` | 课程中心布局微调 |
| `LandingView.vue` | 落地页调整 |
| `ProfileView.vue` / `ResourcesView.vue` | 页面小改 |
| `AppShell.vue` / `SplitTitle.vue` | 壳层与标题动效 |

---

### 文件统计
19 files changed, **+2859 / −420**

### 队友同步
```bash
git fetch origin
git checkout gao/local-ui
# 或
git pull origin gao/local-ui
```

开 PR：https://github.com/yeniwu46-max/link-edu/pull/new/gao/local-ui
