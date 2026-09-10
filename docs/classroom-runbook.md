# LINK 真实 AI 课堂：启动与交付说明

2026-09-09 更新：本机文字、评课和视觉已走 OpenAI Next，按授课 $30 / 视觉 $40 / 测试 $30 分开记美元账，讯飞语音仍独立记人民币账。最新配置见 [活动额度接入](classroom-openai-next.md)，下方早期预算和直连供应商说明保留为历史参考。

首发《分数的初步认识》，8 分钟专项 / 10 分钟完整课堂。**这是可继续联调的实现，不是“全部能力已验收”。** 具体通过项见 [验收记录](classroom-validation.md)。

架构与接口见 [技术沉淀](技术沉淀.md)。9月8日本机已改讯飞，配置和最新验证以 [讯飞联调记录](classroom-xfyun.md) 为准；下方百炼配置保留用于显式选回 `SPEECH_PROVIDER=bailian`，不自动回退。旧校正固定加分入口已禁用，新真实报告校正不采用固定加分。

## 本机入口

- 前端：<http://127.0.0.1:5188/classroom>，沿用原登录账号。
- 新后端：<http://127.0.0.1:5001>；旧 5000 服务未停止。本机忽略文件 `frontend/.env.local` 已把 Vite 代理指向 5001。Git 中的默认代理仍为 5000，可用 `LINK_BACKEND_URL` 覆盖。
- 后端仅绑定本机，单进程、单场课堂连接。**不能开多个 WSGI workers**：服务器进程锁会拒绝第二个新版后端；活跃课堂和任务协调是进程内状态。预算额外使用本机文件锁和独立数据库事务，可保护本机诊断进程，不支持多机器部署。
- 代码未自动推送 GitHub。资料、截图、调用记录和密钥均不随 Git 分享。

## 安装与启动

需要 Python 3.10+、Node.js 20+；本机验证环境 Python 3.14、Node 24。不要使用项目遗留的 Python 2.7 `.venv`。

本轮以 npm / `package-lock.json` 为安装基准。本机 pnpm 全局配置读取失败，旧 `pnpm-lock.yaml` 未同步；团队请使用 `npm ci`，不要混用旧 pnpm 锁文件。本轮没有改动全局 pnpm 配置。

```powershell
# 在项目根目录；本机可用 C:\Python314\python.exe 替代 python
python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
node scripts/prepare-pose.mjs
```

动作模型约 5.8 MB，WASM 从安装的 npm 包复制，均放在 `frontend/public/models/`（Git 忽略）。浏览器运行阶段使用本地资源。开发环境的加载器从本地 node_modules 读取，构建产物从本地 models 读取。模型首次下载需联网，原始地址写在下载脚本中。

保留现有 `backend/.env` 数据库设置，按 `.env.classroom.example` 补充配置，**不要整文件覆盖现有密钥**。不要把密钥放入 `VITE_*`、URL、聊天或源代码。第一把 DeepSeek 密钥已本机配置；其余两把未使用。聊天中出现过的密钥建议在平台控制台轮换。

```dotenv
DEEPSEEK_CHAT_MODEL=deepseek-v4-flash
DEEPSEEK_VISION_MODEL=deepseek-v4-flash-vision-exp
DASHSCOPE_API_KEY=在本机填写，不提交Git
DASHSCOPE_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/realtime
DASHSCOPE_ASR_MODEL=qwen3-asr-flash-realtime
DASHSCOPE_TTS_MODEL=qwen3-tts-flash-realtime
AI_LLM_INPUT_CNY_PER_MILLION=3
AI_LLM_OUTPUT_CNY_PER_MILLION=9
AI_ASR_CNY_PER_MINUTE=0.0198
AI_TTS_CNY_PER_10K_CHARS=1
AI_PRICING_CONFIRMED=true
```

单价核对日期：2026-09-07。DeepSeek 文本与视觉按输入未命中缓存峰时 3 元/百万、输出峰时 9 元/百万保守计算；百炼为北京地域 ASR 0.00033 元/秒、TTS 1 元/万字符。不同地域、模型或价格调整后必须重新核对，不能直接沿用。

来源：[DeepSeek 价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[百炼价格](https://help.aliyun.com/zh/model-studio/model-pricing)。台账记录估算，不冒充账单；失败且用量未知时保留预留，不自动退款或充值。

```powershell
# 一键启动：隐藏窗口，不自动停止占用端口的程序
./scripts/start-classroom.ps1

# 没有 backend/.env 时，脚本会为本机回归使用 loopback SQLite 和种子账号；
# 这不是生产配置。需要强制要求真实配置时使用：
./scripts/start-classroom.ps1 -RequireEnv

# 隔离验证可指定临时数据库目录和端口：
./scripts/start-classroom.ps1 -BackendPort 5011 -FrontendPort 5199 -RuntimeDataDirectory "$env:TEMP/link-classroom-runtime"

# 或在两个终端手动运行（方便停机/重启）
python scripts/run_classroom_backend.py --port 5001
# 另一个终端：
$env:LINK_BACKEND_URL='http://127.0.0.1:5001'
npm run dev --prefix frontend
```

改后端 `.env` 或 Python 代码后须重启**新版**后端；已有终端用 Ctrl+C 关闭，再启动。不要把“端口已占用”当成新版已加载。不要同时运行两个读取同一数据库并发付费的课堂后端。

## 课堂操作

1. Chrome / Edge、耳机、单摄像头。打开真实课堂页，四项分别点“验证接口”；ASR 验证只包含握手，识别内容需实机测试。
2. 阅读并勾选语音用途，再开始。摄像头可选；“云端截图”默认关闭，需要单独勾选。关闭摄像头仍能继续语音。
3. 先完整讲解平均分，积累至少 20 秒有效语音。明确点名或提问可以触发回答；主动问题先举手，安静 2 秒后发言。点举手学生或语音短句点名可邀请发言。
4. 教师讲话会通过 ASR VAD 打断学生；按钮也可打断。学生声音若被外放回收，可能影响 VAD，必须单独验证回声，首发使用耳机。
5. 结束时先提交末段音频，等待识别收尾与最后一个已发出的视觉请求，再请求报告。报告生成失败可以重试；刷新后在“历史课堂”继续查看。结束请求幂等，已完成报告不重复生成。
6. 报告点击时间戳跳转到证据；视觉证据可打开私有截图。教师异议会保存并重新请求模型，不固定加分。没有证据的维度为“暂不评分”。

## 数据与资料

数据库仅增加课堂、事件、单次凭证、用量表，沿用原用户、课程、TrainingSession；旧规则报告不改分，界面标为演示/规则评分。真实报告与旧分数分开查看。

- `backend/private/knowledge.json`：用户附件的 239 个私有检索片段。
- `backend/private/materials-manifest.json`：7 份文件的导入结果、SHA256、使用边界。
- `backend/data/classroom_knowledge.json`：可公开的自编知识卡、短摘要、来源索引。
- `backend/instance/classroom_evidence/<session_id>/`：云端分析截图；接口核对 JWT 与归属。
- `backend/data/fractions_acceptance.json`：36 项自编/合成验收场景，不是真实训练数据。
- `artifacts/private/`：本机合成探针结果；不计入真实课堂验收。

原始麦克风录音不落盘；最终文本、学生状态、动作事件和用量保留。无完整录像回放。DOC 使用本机 Word 只读解析并禁宏，PDF 文本提取，Markdown 保留段落位置；扫描型 PDF 提取为空时需补 OCR，不能默认为成功。本机附件 7/7 导入成功。重新导入命令：

```powershell
python scripts/ingest_classroom_resources.py '你的学习资源.zip绝对路径'
```

首发检索最多 5 段，过滤中学、幼儿园大纲和纯链接清单，优先当前小学情境。**没有微调模型权重**；未确认许可的公开视频/资料仅保留索引，不当作可训练数据。

## 验证命令

```powershell
python -m pip install pytest
python -m pytest backend/tests -q
npm run build --prefix frontend
# 以下会实际调用云接口，计入预算
python scripts/probe_classroom.py dialogue vision asr tts
python scripts/validate_pedagogy.py
```

开发页 `/diagnostics.html` 用合成空白帧验证真实 Worker，无摄像头、无云调用、无报告入档。构建版使用正式课堂摄像头测试，诊断页仅供开发。

## 发布限制与四人验收分工

- 当前遗留 JWT 演示签名密钥强度不足，登录 token 仍按用户要求沿用旧 localStorage 流程。**公开部署前必须更换强随机签名密钥、关闭演示账号与种子、限制 CORS，并评审 httpOnly Cookie/CSRF 迁移及登录限流。** 本轮未扩展到新的认证体系。
- 模型对话存在延迟波动；不能把简单探针的 1 秒延迟当成课堂语音 P95。至少 20 轮真语音测量才可判定。
- 学生理解、情绪表现和评分为 AI 推断，不是对真实儿童心理/教学资质的测量。
- 负责人 A：当前供应商配置、真实音频联调、记录延迟；B：上课与教案核验；C：摄像头/动作/页面故障测试；D：逐项验收、设备复核与录屏。交付前仍需三次完整 10 分钟课堂，录屏须经参与者同意。
- 本轮未生成“假装验收成功”的备用录屏。录屏与三次真实课堂未完成时，不得冻结为最终验收版。
