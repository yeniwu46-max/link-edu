# 临客 LINK

## 2026-09-07 真实 AI 课堂开发版

先读 [技术交接与架构/接口](docs/技术沉淀.md)，再按 [新版启动说明](docs/classroom-runbook.md) 配置；真实入口为 `http://127.0.0.1:5188/classroom`，本机新版后端为 5001。

9月8日已接入讯飞识别/合成，真实语音探针有返回，完整真人课堂仍待验收。最新状态见 [讯飞联调记录](docs/classroom-xfyun.md)，另有 [历史验收记录](docs/classroom-validation.md)、[资料索引](docs/classroom-sources.md) 与 [架构决策](docs/decisions/002-xfyun-streaming-speech.md)。仓库已设私有，密钥仍只放本地忽略文件，不随仓库分享。

后续音频/设备回归、证据校验及隔离合成课堂结果见 [独立验收记录](docs/classroom-independent-validation.md)。这不替代真人课堂验收。

## 原版演示启动

请优先阅读 **交接说明.txt**，按步骤安装依赖并启动前后端。

- 演示账号：`demo` / `link123`
- 前端地址：http://127.0.0.1:5188
- 后端地址：http://127.0.0.1:5000
- 数据库：MySQL 8（见 `backend/.env.example`）

快捷启动：双击 `启动后端.bat` 和 `启动前端.bat`
