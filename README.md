# 临客 LINK

面向师范生与职前教师的 AI 微格教学训练平台。通过虚拟学生互动、语音转写与本地动作观察，形成可回溯课堂证据的教学反馈。

## 核心体验

- **模拟课堂**：摄像主画面、三名虚拟学生、流式气泡、语音回应与课堂控制栏。
- **AI 评课**：六维分析、证据时间线、教态观察与改进建议；数据不足时明确说明，不补造分数。
- **课程与资源**：九项教学技能研习、可拖动资料卡、PDF/Markdown 阅读与课程资源入口。
- **成长档案**：历史训练、热力图、日志与个人资料；不同评课口径分开呈现。
- **数字人助手与导览**：无框 Olivia 人物、带来源的文字 / 连续语音问答、可跳过的新手引导；授课采集中仅提供文字帮助。

当前模拟授课支持小学数学“分数的初步认识”。课程中心的其他技能资料不代表已接入对应的实时课堂情境。

## 本机启动

需要 Python 3.10+、Node.js 20+。使用 npm 锁文件，不混用旧 pnpm 锁文件。

```powershell
python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
node scripts/prepare-pose.mjs
# 先配置 backend/.env，保留已有数据库和密钥，不要整文件覆盖。
./scripts/start-classroom.ps1 -PythonPath C:/Python314/python.exe
```

前端：`http://127.0.0.1:5188`；后端：`http://127.0.0.1:5001`。

启动脚本不会结束已有服务，也不会默认创建演示数据库或登录演示账号。首次准备动作模型需联网；真实授课与生成报告会产生供应商费用，须先确认配置和预算。详细步骤见 [运行说明](docs/classroom-runbook.md)。

## 验证

```powershell
./scripts/run-regression.ps1 -PythonPath C:/Python314/python.exe
python scripts/evaluate_classroom.py check
```

第一条运行前后端测试与生产构建，结果默认保存到 `artifacts/private/`；第二条离线检查课堂用例与规则，默认不调用模型。DeepEval 单测使用独立评测环境，见 [离线评测说明](docs/classroom-offline-evaluation.md)。

## 本次交付 · 2026-10-08

**版本 `2026.10.08-immersive-assistant`：** [沉浸课堂、数字人助手与图检索技术更新](docs/技术更新-沉浸课堂与数字人助手-20261008.md)。包含课堂三名 3D 学生、直接交互模型、页面精简与布局、独立助手语音及新用户导览，汇总资产许可、接口、升级步骤、验收和回退。

- [当前数字人与新手导览实现 / 测量](docs/ui-assistant-onboarding.md)
- [VRM 与独立助手架构决策](docs/decisions/006-vrm-independent-assistant.md)
- [GraphRAG 验收与默认关闭原因](docs/rag/graphrag-local-acceptance-2026-10-08.md)

GraphRAG 功能提供可控试验开关，质量验收未达标，默认关闭；真实设备语音和长期性能仍有待验收。

## 历史交付 · 2026-09-25

**版本 `2026.09.25-rag`：** [RAG 纵深与可信评测技术更新说明](docs/技术更新-RAG与可信评测-20260925.md)（混合检索、知识库页、课堂六维 RAG、引用校验、证据互跳）。

## 本次交付 · 2026-09-10

2026-09-13 增量升级：[学习状态、有效计时与本机录像复盘](docs/classroom-learning-replay-20260913.md)。包括暂停/继续、版本化学生认知、取景校准、维度级拒评、真实报告阶段和本机录像证据回放；保留真人验收边界。

[两路合并与上线前整理](docs/integration-delivery-20260910.md)：已整合 `gao/dev` 和提供的 ZIP 更新，保留本机模拟授课及新版 AI 报告，精简无效入口和重复提示，记录冲突取舍与回归结果。

- [课堂播放器与学生形象](docs/classroom-player-refresh-20260910.md)
- [统一 AI 评课与证据可视化](docs/classroom-ai-review-20260910.md)
- [摄像课堂与报告证据门槛](docs/classroom-camera-first.md)
- [动作捕捉与教态评价](docs/classroom-motion-evaluation.md)
- [RAG 向量知识库（架构 / 运维 / 优化路线）](docs/rag/README.md)
- [历史技术交接](docs/classroom-handoff-20260910.md)

## 部署边界

本仓库目前使用单进程课堂及助手服务。GitHub 的代码合并与生产部署分别管理；本次整理不包含生产环境部署，验证范围和升级步骤见最新技术更新文档。

公开部署前仍须核对 JWT 强随机密钥、关闭演示账号和启动种子、限制 CORS、配置 HTTPS 与登录限流，并完成真机语音/摄像头和资料许可验收。不要提交 `.env`、真实课堂记录或私有截图。AI 反馈是教学反思辅助，不替代教师专业判断。
