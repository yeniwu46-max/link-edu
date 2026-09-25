# 临客竞赛版本复现

最终运行状态、实际服务提供方及验收限制见交付包中的部署运维说明。

1. 安装 Python 3.12、Node.js 22+、npm、Linux Docker/Podman；Windows 可通过 Docker Desktop Linux 容器运行。
2. `cd frontend`，执行 `npm ci`、`npm test`、`npm run build`。源码包已含浏览器模型与 WASM。
3. 后端运行依赖用 `backend/requirements.lock.txt`。回归测试执行 `pip install -r backend/requirements-test.txt`（含 pytest 与生成测试图片的 Pillow），然后执行 `python -m pytest backend/tests -q`。
4. 在 `deploy/.env` 中设置两个不同的随机 `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`。按 `runtime.env.example` 创建 `deploy/runtime.env`；数据库 URL 的主机为 `db`，密码与上一步一致。实际 API 密钥只放私有配置。
5. `docker compose -f deploy/compose.yml up -d --build db`
6. `docker compose -f deploy/compose.yml run --rm app python release_admin.py init`
7. `docker compose -f deploy/compose.yml up -d app`
8. 静态前端由 Nginx 提供，参考 `link-demo.nginx.conf` 配置有效证书和实际域名/IP；浏览器设备能力必须使用可信 HTTPS 或本机 localhost。

没有云密钥时可验证账号、课程、资源和离线测试；不能把静态页面或假响应当成实时 AI 课堂成功。不要在生产环境使用弱密码或启用个人演示数据种子。

服务器生产部署使用 `install-server.sh`，前提是发布目录、私有环境文件、已下载的基础镜像和证书配置完成。基础镜像下载失败时可以从公开镜像站下载相同镜像并校验摘要。依赖安装镜像通过 PIP_INDEX_URL 指定。

`verify-database.sh` 只创建带时间戳的独立验证数据库，检查初始化和 SQL 恢复；不会删除生产数据库。`backup.sh` 输出私有备份，不能放入竞赛包。备份含用户密码哈希和云端配置，应受控存储。

备份内容包含 MySQL 全库（含 RAG 表 `kb_documents` / `kb_chunks` 中的向量 BLOB）以及 `instance/` 目录（含 `instance/rag/files/` 原始资料）。恢复后若切换了 Embedding 模型，需在后端容器内执行 `python -m rag.cli reindex --all`。

## RAG 向量库（语料 + 语义索引）

1. 在 `runtime.env` 中启用：`RAG_ENABLED=true`、`RAG_ADMIN_ACCOUNTS`（公网必填）、百炼 `RAG_EMBEDDING_PROVIDER=openai_compatible` 与 `RAG_EMBEDDING_*`，并核对 `RAG_EMBEDDING_CNY_PER_MILLION` 后设 `AI_PRICING_CONFIRMED=true`。
2. 在构建机或容器内按 [`sources/rag/README.md`](../sources/rag/README.md) 执行 `rag_export_knowledge_cards.py` 与 `rag_ingest_manifest.py`（或上传 API）。
3. 切换语义模型后：`docker compose -f deploy/compose.yml exec app python -m rag.cli reindex --all`。
4. 验收：`GET /api/rag/status`（`stale_documents=0`）、`python scripts/rag_eval_retrieval.py`（不调 LLM）。

公网预算固定总计 30 CNY，配套测试账本最多 70 CNY；保留开始时间和历史账本。不要通过删库、改开始时间、增加进程或换账本绕过限制。每个实例只运行一个 Gunicorn worker；扩到多进程需要引入跨进程容量/任务协调。
