# 临客 LINK

请优先阅读 **交接说明.txt**，按步骤安装依赖并启动前后端。

- 演示账号：`demo` / `link123`
- 前端地址：http://127.0.0.1:5188
- 后端地址：http://127.0.0.1:5000
- 数据库：MySQL 8（见 `backend/.env.example`）

快捷启动：双击 `启动后端.bat` 和 `启动前端.bat`

AI 评课：在 `backend/.env` 填写 `DEEPSEEK_API_KEY`。训练结束后，系统会把课堂文字记录发送到后端的 DeepSeek 接口，生成六维评分、总结、问题和改进建议；密钥不会进入前端。

首次配置可直接复制 `backend/.env.example` 中的 DeepSeek 配置项到现有 `.env`，然后重启后端。
