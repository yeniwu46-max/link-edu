# 离线课堂评测

实现范围：DeepEval 自定义窄指标、36 个既有场景映射、合成正反例与边界例、代码契约检查、原始/校验后报告对照、历史运行比较。不修改在线课堂、提示词、报告评分、前端或业务数据库结构。

## 安装与默认检查

在项目根目录运行。评测使用独立虚拟环境，生产环境不安装 DeepEval。DeepEval 4.2.2 要求较新的 python-dotenv，因此评测清单与生产清单分开维护。

```powershell
python -m venv artifacts/private/eval-venv
$env:PIP_CACHE_DIR = "$PWD/artifacts/private/pip-cache"
artifacts/private/eval-venv/Scripts/python.exe -m pip install -r evals/requirements.lock.txt
artifacts/private/eval-venv/Scripts/python.exe scripts/evaluate_classroom.py
```

省略模式等同 `check`：校验数据、执行映射到实际后端代码的测试，禁止网络连接，不调用 Judge，不读取真实课堂内容。无需 API 密钥。报告中的“未评估”不是失败，也不是通过。

`requirements.lock.txt` 是已安装验证的 Windows / Python 3.14 完整版本快照；`requirements.txt` 是直接依赖清单，升级时在独立环境验证并重新生成锁定清单。若其他平台需要重新解析依赖，使用后者并重新运行测试，不假定跨平台已经验证。

完整测试（放行本机 WebSocket，仍禁止外网）：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONUTF8 = '1'
artifacts/private/eval-venv/Scripts/python.exe -m pytest -p evals.offline_guard --eval-allow-loopback evals/tests backend/tests -q
```

`check` 运行映射的代码契约和数据测试；完整测试命令还覆盖 mock Judge、预算、回放和生成通道。不自动执行付费测试。

## 三种模式

```powershell
# 1. 无网络代码检查，可缩小场景范围
artifacts/private/eval-venv/Scripts/python.exe scripts/evaluate_classroom.py check --cases F22 F24 F31

# 2. 回放内置合成输出；不加 --paid 只检查结构，语义标记未评估
artifacts/private/eval-venv/Scripts/python.exe scripts/evaluate_classroom.py replay --cases F07 F08 F17 F31

# 已显式配置 Judge 后，评审本地输出；下面金额仅示例上限，不是价格或质量承诺
artifacts/private/eval-venv/Scripts/python.exe scripts/evaluate_classroom.py replay --cases F07 F08 --paid --judge-max-usd 1

# 3. 生成侧使用既有测试账户，随后由独立 Judge 评审
artifacts/private/eval-venv/Scripts/python.exe scripts/evaluate_classroom.py generate --cases F08 F17 --paid --generator-max-usd 1 --judge-max-usd 1
```

每个适用指标独立请求一次；报告会评审原始、校验后两个阶段。内置回放默认含正例、反例、边界例，出现语义失败可能是预期的反例表现，不代表线上模型退化。先用少量 `--cases` 人工核对。

退出码：`check` 的代码失败/运行错误为 1；参数、服务或 Judge 错误为 2；语义不合格只供人工审阅，不作为发布门禁。所有产物写入唯一的 `artifacts/private/classroom-eval/<run_id>/`，不覆盖其他运行。

## 独立 Judge 配置

使用当前进程环境变量，不提供默认模型、默认端点或生产密钥回退。下列值均须替换，单价按供应商核对后的 USD/百万 token 填写：

```powershell
$env:EVAL_JUDGE_BASE_URL = 'https://YOUR-PROVIDER/v1'
$env:EVAL_JUDGE_MODEL = 'YOUR-PINNED-MODEL'
$env:EVAL_JUDGE_API_KEY = 'YOUR-SEPARATE-KEY'
$env:EVAL_JUDGE_INPUT_USD_PER_MILLION = 'YOUR-VERIFIED-INPUT-PRICE'
$env:EVAL_JUDGE_OUTPUT_USD_PER_MILLION = 'YOUR-VERIFIED-OUTPUT-PRICE'
```

协议为 OpenAI-compatible Chat Completions：支持 `max_tokens`、JSON object 输出和标准 usage 字段；不自动适配不兼容协议、不跟随重定向、不重试、不回退模型。HTTPS 校验保留；Judge 不读取系统代理。`--paid` 表示允许将选定样本内容发送到显式配置的端点。

费用使用串行、逐请求预留；实际 usage 完整有效时结算，否则保留预留。首次预算不足后锁定停止，后续小请求也不会绕过停止线。Judge 与生成器分别限制，整次运行的上限为两者之和；估算依赖用户配置的正确价格，供应商实际计费仍以账单为准。预算台账在请求前落盘，异常中断可检查保留的预留记录。

DeepEval 只作为本地指标框架使用，禁用遥测、更新检查及自动 trace flush；不登录、不上传到 Confident AI。独立配置不等于不同模型家族，报告不会宣称独立验证或人工校准。

### 生成侧约束

首版只允许项目已经支持的独立测试账户：`CLASSROOM_LLM_PROVIDER=openai_next`、`OPENAI_NEXT_TEST_API_KEY`、已确认单价的 `deepseek-v4-flash` 和固定测试通道端点。保留原有 `OPENAI_NEXT_*` 单价、额度及 `OPENAI_NEXT_PRICING_CONFIRMED=true` 配置；不会借用 dialogue 密钥。DeepSeek 默认通道没有独立测试账户，因此不做静默复用。

生成侧必须能访问项目已初始化的预算账本，使用项目原有 DATABASE_URL 解析规则；只向 CreditUsage 写入 test 账户费用，不查询真实课堂事件，不新建或迁移该账本。其他业务数据放入临时 SQLite，结束后关闭并清理。生成调用不携带真实 session_id，不启动课堂服务、ASR、TTS 或摄像头。服务或账本失败停止当前生成批次。

学生生成调用真实 `chat_stream`、`STUDENT_SYSTEM` 与流式解析器；报告生成调用真实 `REPORT_SYSTEM` 与 `validate_report`。上下文与参考资料使用版本化场景快照，不实时检索知识库，避免比较过程中参考内容漂移；这不是完整课堂运行时或 RAG 验收。

## 数据、回放和比较

原始 `backend/data/fractions_acceptance.json` 保持不变。`evals/dataset.py` 将 F01–F36 映射到语义、代码、人工检查；`evals/fixtures.json` 保存语义输出正例、反例、边界例。数据版本和完整内容 hash 一起记录。

当前范围：分数知识与角色认知、教师/学生纠错、点名与安静角色、先跑题后回答、报告证据支持、播放失败、低置信度/缺失视觉、资料指令注入。动作和时序由既有代码测试验证；回声、摄像头识图、设备权限、完整故障恢复等未执行的部分显式列为人工/链路“未评估”。

将既有运行的 `results.json` 作为 `--input` 可重新评审，不重新生成。自定义回放支持与当前版本化输入上下文对应的合成或脱敏输出，格式如下：

```json
{
  "dataset_hash": "COPY_FROM_CURRENT_RESULTS_JSON",
  "provenance": "synthetic",
  "records": [
    {
      "case_id": "F22",
      "variant": "candidate-a",
      "generator_model": "model-version-or-unknown",
      "output": {
        "action": "answer", "student_id": "lin", "text": "平均分就是每份一样多。",
        "understanding": "每份一样多", "open_question": "", "resolved": true
      }
    }
  ]
}
```

`provenance` 也可为 `anonymized`；工具不自动脱敏，不能仅改标签就上传真实课堂资料。首版不接受任意新上下文，需先在版本化场景中加入对应输入，输出与该输入一致后再回放。case_id＋variant 不得重复。

```powershell
artifacts/private/eval-venv/Scripts/python.exe scripts/evaluate_classroom.py replay --input PATH/TO/results.json --baseline PATH/TO/baseline/results.json
```

只有用例 hash、规则 hash、Judge 身份一致才直接比较；缺失项与新增项标为未评估变化。生成记录的 `generation_prompt_hash` 保存实际生成提示词，手工输出为 null；运行级 `prompt_hashes` 是本次检出的运行时提示词，不冒充历史生成版本。允许比较候选生成提示词变化；学生角色资料变化会改变用例 hash。不把 Judge 变化造成的差异解释为生成质量变化。

JSON 明细保存原始输出、校验后输出、每项 verdict/reason/event_ids、模型身份、提示词/规则版本、耗时、费用及比较结果。Markdown 按 code/raw/validated/manual 分层展示分母，`error`、`not_evaluated`、`not_applicable` 分开列出。合法事件编号不等于结论有依据：前者由代码检查，后者由 `evidence_supported` 评审。

## 人工复核与研究对应

所有合成标签默认 `pending_human_review`，不是金标准。先审阅正反例的语境、角色和允许误解，再逐指标复核 Judge 结论。保留专家标签、复核人、日期及分歧理由，形成单独校准记录；若需要改变场景或预期标准，更新数据版本后重建基线。未校准前不设自动发布阈值，不自动改提示词或业务评分。

- `research_llm_eval_github_20260909.md` → DeepEval、本地评测、证据语义支持检查；Promptfoo/观测平台留待后续。
- `research_openmaic_fit_20260909.md` → 确定性与语义分层、`leads_with_answer`/`answered_anywhere`、严格布尔输出、真实提示词/解析路径、独立场景和报告、历史基线对比。本实现不复制 OpenMAIC 源码或运行框架。
- [DeepEval 自定义模型契约](https://deepeval.com/guides/guides-using-custom-llms)和[自定义指标](https://deepeval.com/docs/metrics-custom)用于适配接口；输出字符串布尔值、重复字段、无效引用等均为评审器错误。

## 本次交付验证（2026-09-09）

- Windows / Python 3.14 独立评测环境安装成功，`pip check` 无依赖冲突。
- 新增 30 项测试与既有 139 项后端测试合计 **169 项通过**。运行期间阻断外网，仅放行本机 WebSocket。
- 默认 check 命令通过；回放和版本匹配比较通过。内置负例会出现预期的代码规则失败，不把负例集合的通过率作为产品质量分数。
- 实际模型调用为零。Judge 质量、模型供应商兼容性、人工校准和真实课堂设备验收仍需按上述流程单独验证。
- 现有代码和 DeepEval 在 Python 3.14 下有弃用警告，本次没有扩大范围修改生产实现。
