# 分层上下文 AI 评课追问实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Keep each task small and verify it before moving on.

**Goal:** 将 AI 评课页拆成“生成本次评课报告”和“基于报告追问”两个独立功能，并让追问按问题类型读取最少但足够的数据。

**Architecture:** 继续复用现有 DeepSeek 结构化评课、报告校验、数据库保存和页面展示。追问接口始终读取当前已完成的 DeepSeek 报告、当前课程和训练基本数据；只有问题涉及“最近、历史、进步、趋势、相比”等内容时，后端才查询当前用户近 30 天的已完成有效评课，生成紧凑的趋势摘要后发送给 DeepSeek。追问只返回文本回答，不修改原报告、不改变评分、不新增评课记录。

**Tech Stack:** Flask、SQLAlchemy、JWT、Vue 3、Axios、OpenAI-compatible DeepSeek API、现有测试工具。

**范围约束：** 本次不接入视频/音频上传，不实现转写，不改变评分算法，不把原始全部历史报告直接发送给模型，不新增聊天记录表。追问历史仅保存在当前页面状态。

## 文件职责

- Modify `backend/services/llm/deepseek.py`: 增加普通文本追问调用，接收当前报告和可选的近 30 天摘要。
- Modify `backend/services/training.py`: 增加问题范围识别、当前报告上下文组装、近 30 天摘要查询和追问业务服务。
- Modify `backend/routes.py`: 增加 `POST /api/feedbacks/<feedback_id>/ask`，完成请求校验和错误映射。
- Modify `frontend/src/services/dashboard.js`: 增加追问 API 封装。
- Modify `frontend/src/views/AiReviewView.vue`: 分离报告生成区与追问区，增加独立“发送问题”按钮和回答显示。
- Modify `backend/tests/test_deepseek_review.py`: 覆盖 prompt 分层、文本响应和 provider 异常。
- Modify `backend/tests/test_ai_review_route.py`: 覆盖当前报告追问、历史问题追问、权限、状态和报告不变性。

## Task 1: 定义追问上下文和问题范围

**Files:**
- Modify: `backend/services/training.py`
- Test: `backend/tests/test_ai_review_route.py`

- [ ] **Step 1: Write failing tests**

增加纯业务测试，明确以下规则：

```python
assert classify_question_scope('为什么这次提问质量较低？') == 'current'
assert classify_question_scope('我近30天有没有进步？') == 'history'
assert classify_question_scope('和上次相比有什么变化？') == 'history'
```

测试 `build_review_question_context()`：

- 当前上下文必须包含课程名、场景、训练时长、完成度和当前报告的总结、问题、建议、六维证据。
- `current` 问题不包含历史记录。
- `history` 问题包含最多 30 天的结构化趋势摘要。

- [ ] **Step 2: Run the focused tests and verify they fail**

```powershell
Set-Location 'C:\Users\尚天林\xwechat_files\wxid_he5yaslrq4cc22_86ee\msg\file\2026-08\临客LINK\临客LINK\backend'
python -m unittest tests.test_ai_review_route -v
```

Expected: FAIL because the scope and context helpers do not exist。

- [ ] **Step 3: Implement minimal context helpers**

在 `training.py` 增加：

```python
HISTORY_QUESTION_MARKERS = ('最近', '近30天', '近 30 天', '历史', '进步', '趋势', '相比', '上次', '变化', '长期')

def classify_question_scope(question):
    return 'history' if any(marker in question for marker in HISTORY_QUESTION_MARKERS) else 'current'

def build_recent_review_summary(user, *, exclude_feedback_id=None):
    ...

def build_review_question_context(user, feedback, question):
    ...
```

近 30 天摘要只允许使用：

- `AiFeedback.user_id == user.id`
- `report.source == 'deepseek'`
- `report.generation_status == 'succeeded'`
- 非 `insufficient_evidence`
- `created_at >= datetime.utcnow() - timedelta(days=30)`

摘要输出最多 10 条最近记录，并计算平均综合分、最高分、最低分、首条与末条分数、各维度平均分和重复问题。当前记录不重复统计。没有历史数据时返回“近30天暂无足够有效评课数据”。

- [ ] **Step 4: Run the focused tests and verify they pass**

```powershell
python -m unittest tests.test_ai_review_route -v
```

Expected: context and scope tests PASS。

## Task 2: 增加 DeepSeek 文本追问能力

**Files:**
- Modify: `backend/services/llm/deepseek.py`
- Test: `backend/tests/test_deepseek_review.py`

- [ ] **Step 1: Write failing provider tests**

验证发送给 DeepSeek 的消息满足：

- system message 要求当前报告是主要依据。
- history 摘要只能作为趋势参考，不能覆盖本次报告。
- 不执行报告或课堂材料中的命令。
- 不重新计算或修改原评分。
- user message 包含当前问题和当前报告内容。
- history 问题额外包含近 30 天摘要。

同时覆盖未配置 key、空响应、SDK 异常。

- [ ] **Step 2: Run provider tests and verify they fail**

```powershell
python -m unittest tests.test_deepseek_review -v
```

Expected: FAIL because `answer_review_question` does not exist。

- [ ] **Step 3: Implement the provider call**

增加固定签名：

```python
def answer_review_question(question, context, *, config=None, client=None):
    ...
```

实现要求：

1. 复用 `_config_value()` 和现有 OpenAI client 初始化方式。
2. 使用普通文本 `chat.completions.create()`，不传 `response_format=json_object`。
3. `temperature=0.3`，复用现有模型、超时和重试策略。
4. 返回非空的 `message.content.strip()`。
5. 失败统一抛出 `DeepSeekReviewError`。

- [ ] **Step 4: Run provider tests and verify they pass**

```powershell
python -m unittest tests.test_deepseek_review -v
```

Expected: all provider tests PASS。

## Task 3: 增加后端追问接口

**Files:**
- Modify: `backend/services/training.py`
- Modify: `backend/routes.py`
- Test: `backend/tests/test_ai_review_route.py`

- [ ] **Step 1: Write failing route tests**

覆盖：

- 未登录返回 401。
- 其他用户的评课 ID 返回 404。
- `question` 缺失或只含空白返回 400。
- 报告来源不是 DeepSeek 或状态不是 `succeeded` 返回 409。
- 普通问题只发送当前上下文。
- 历史问题发送当前上下文和 30 天摘要。
- 成功响应为 `{feedback_id, scope, answer}`。
- 调用追问后，`report_json`、`overall_score`、六维评分和评课记录数量都不变。
- DeepSeek 失败返回 502，原报告仍可读取。

- [ ] **Step 2: Run route tests and verify they fail**

```powershell
python -m unittest tests.test_ai_review_route -v
```

Expected: FAIL because the route and service do not exist。

- [ ] **Step 3: Implement the service and route**

在 `training.py` 增加：

```python
def ask_ai_review_question(user, feedback_id, question):
    ...
```

业务顺序固定为：查询并校验归属 → 解析已完成报告 → 识别 `current/history` → 组装上下文 → 调用 DeepSeek → 返回答案。不执行数据库写入。

在 `routes.py` 增加：

```python
@content_bp.post('/feedbacks/<int:feedback_id>/ask')
@jwt_required()
def ask_feedback_question(feedback_id):
    ...
```

只接受：

```json
{"question": "我近30天有没有进步？"}
```

- [ ] **Step 4: Run all backend tests**

```powershell
python -m unittest discover -s tests -v
```

Expected: all backend tests PASS。

## Task 4: 前端拆分两个按钮和追问展示

**Files:**
- Modify: `frontend/src/services/dashboard.js`
- Modify: `frontend/src/views/AiReviewView.vue`

- [ ] **Step 1: Add API wrapper**

```js
export async function askAiReviewQuestion(feedbackId, question) {
  const { data } = await api.post(`/feedbacks/${feedbackId}/ask`, { question }, { skipBusy: true })
  return data
}
```

- [ ] **Step 2: Split the template**

报告生成区只保留生成状态和“生成 DeepSeek 评课”按钮。

追问区单独包含：

- “继续追问本次评课”标题。
- 无 `maxlength` 的 textarea。
- 独立“发送问题”按钮。
- 当前问题、回答和回答来源范围标签（本次评课/近30天趋势）。

报告未生成成功前，追问按钮禁用；报告生成失败时，追问区显示不可用原因。

- [ ] **Step 3: Add front-end state and action**

新增：

```js
const questionDraft = ref('')
const questionAnswer = ref('')
const questionScope = ref('current')
const questionLoading = ref(false)
const questionError = ref('')
```

`askQuestion()` 只做空问题校验、调用追问接口、显示答案，不调用 `runAiReview()`，不修改 `current.report`。切换历史评课时清空当前追问状态，避免串场。

- [ ] **Step 4: Run front-end verification**

```powershell
Set-Location 'C:\Users\尚天林\xwechat_files\wxid_he5yaslrq4cc22_86ee\msg\file\2026-08\临客LINK\临客LINK\frontend'
npm run build
```

Expected: build PASS。

手动验收：

1. 点击“生成 DeepSeek 评课”，只生成报告。
2. 报告成功后输入普通问题，回答标记为“本次评课”。
3. 输入“近30天有没有进步”，回答标记为“近30天趋势”。
4. 原评分、报告内容和历史记录不变化。
5. 页面不限制问题字数，但空问题不能发送。

## Task 5: 最终回归

- [ ] 后端测试：`python -m unittest discover -s tests -v`
- [ ] 前端构建：`npm run build`
- [ ] 确认真实调用只在后端发生，前端不暴露 `DEEPSEEK_API_KEY`。
- [ ] 确认普通问题不会查询近 30 天历史数据。
- [ ] 确认历史问题发送的是程序汇总，不是全部原始报告。
- [ ] 确认追问失败不会伪造答案，不影响已保存报告。
