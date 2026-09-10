# 临客 LINK

## 最新技术交接（2026-09-10）

评课更新：[统一 AI 评课与证据可视化](docs/classroom-ai-review-20260910.md)。历史课堂直达对应 AI 报告；六维剖面、事件时间线、可搜索证据与动作采样质量，支持打印 / PDF，明确区分 AI 判断、可观察数据和固定复盘提示。

上午更新：[课堂播放器与学生形象改版](docs/classroom-player-refresh-20260910.md)。训练入口直达模拟课堂，精简授权提示，播放器式图标控制栏，三组透明像素学生与轻动效，学生语音 1.2 倍速。

[本轮技术更新与收工交接](docs/classroom-handoff-20260910.md)：离线评测、动作与教态、课堂布局与互动、摄像头预览、启动禁用原因、后端 500 恢复及课堂保存核验。前端 78 项、后端及离线评测 208 项通过；完整录像、课后视频预览和保存选择仍待实现，当前保存的是课堂事件与报告。

## 2026-09-07 真实 AI 课堂开发版

2026-09-09：本机已接入 OpenAI Next 三用途额度（授课 $30 / 视觉 $40 / 测试 $30），讯飞语音独立计费。配置和美元预算说明见 [活动额度接入](docs/classroom-openai-next.md)。

先读 [技术交接与架构/接口](docs/技术沉淀.md)，再按 [新版启动说明](docs/classroom-runbook.md) 配置；真实入口为 `http://127.0.0.1:5188/classroom`，本机新版后端为 5001。

9月8日已接入讯飞识别/合成，真实语音探针有返回，完整真人课堂仍待验收。最新状态见 [讯飞联调记录](docs/classroom-xfyun.md)，另有 [历史验收记录](docs/classroom-validation.md)、[资料索引](docs/classroom-sources.md) 与 [架构决策](docs/decisions/002-xfyun-streaming-speech.md)。仓库已设私有，密钥仍只放本地忽略文件，不随仓库分享。

后续音频/设备回归、证据校验及隔离合成课堂结果见 [独立验收记录](docs/classroom-independent-validation.md)。这不替代真人课堂验收。

2026-09-09：模拟课堂新增本地身体、手势与面部几何检测，动作摘要接入最终评课的“教态与站位”维度，支持证据回溯；安装、评价边界及真人验收清单见 [动作捕捉与教态评价](docs/classroom-motion-evaluation.md)。

教师提问响应、全屏底部学生与流式气泡、居中字幕、画质和音量控制的修复说明见 [课堂互动与全屏](docs/classroom-interaction-fullscreen.md)。

最新布局：摄像主画面＋下方三位学生、双授权一键开始、设置与记录弹窗、NumberFlow 倒计时；授课至少 10 秒且证据足够才生成报告。门槛、隐私与验收说明见 [摄像课堂与报告数据检查](docs/classroom-camera-first.md)。

## 原版演示启动

请优先阅读 **交接说明.txt**，按步骤安装依赖并启动前后端。

- 演示账号：`demo` / `link123`
- 前端地址：http://127.0.0.1:5188
- 后端地址：http://127.0.0.1:5000
- 数据库：MySQL 8（见 `backend/.env.example`）

快捷启动：双击 `启动后端.bat` 和 `启动前端.bat`

AI 评课：在 `backend/.env` 填写 `DEEPSEEK_API_KEY`。在 AI 评课页主动点击生成后，系统把课堂文字材料发送到后端的 DeepSeek 接口，生成六维评分、总结、问题和改进建议；密钥不会进入前端。此入口使用独立 DeepSeek 配置，不走模拟课堂的三用途美元额度账本。

首次配置可直接复制 `backend/.env.example` 中的 DeepSeek 配置项到现有 `.env`，然后重启后端。
