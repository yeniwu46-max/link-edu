# RAG 运维与语料 Runbook

## 1. 环境检查清单

| 检查项 | 本机 | 公网 `deploy/compose.yml` |
| --- | --- | --- |
| 表结构 | `python init_db.py` 或 `schema.sql` | `release_admin.py init` |
| `RAG_ENABLED` | 默认开（非 PUBLIC） | 须 `RAG_ENABLED=true` |
| 管理权限 | `teacher` 可管（无白名单时） | **`RAG_ADMIN_ACCOUNTS`** 必填 |
| 持久目录 | `backend/instance/rag` | 卷 `link-runtime` → `/app/backend/instance` |
| 语义向量 | 见 `.env.example` 百炼段 | `runtime.env` 同步 |
|  Embedding 费用 | `AI_PRICING_CONFIRMED=true` + **`RAG_EMBEDDING_CNY_PER_MILLION`** | 与课堂账本共用停止阈值 |

验收：`python -m rag.cli stats` 或 `GET /api/rag/status`（JWT）→ `indexed_chunks`、`embedding.semantic`、`stale_documents`。

## 2. 语料 manifest

清单文件：**`sources/rag/manifest.json`**

字段：`path`、`title`、`category`、`source`、`tags`、`priority`（P0 评课必用 / P1 补充）、可选 `description`。

规范：

- 量表、课标：**优先 .docx / .md**（保留表格与标题）。
- PDF：需文字层；扫描件 OCR 后再入库。
- 课堂 JSON 知识卡：运行 `python scripts/rag_export_knowledge_cards.py` 生成 `sources/rag/corpus/classroom_knowledge/*.md` 并更新 manifest。

## 3. 批量入库

```bash
# 仓库根目录
python scripts/rag_export_knowledge_cards.py

cd backend
python ../scripts/rag_ingest_manifest.py --priority P0
python ../scripts/rag_ingest_manifest.py --priority P1   # 可选
python ../scripts/rag_ingest_manifest.py --dry-run       # 仅列出
```

单文件仍可用：

```bash
python -m rag.cli ingest "../path/量表.docx" --category rubric --source "出处"
```

失败文档：`status=failed`，`error` 字段说明原因；API 上传同理。

## 4. 切换百炼语义向量（生产关键步骤）

1. 配置 `RAG_EMBEDDING_PROVIDER=openai_compatible`、`text-embedding-v4`、`RAG_EMBEDDING_DIM=1024`、`DASHSCOPE_API_KEY`（或 `RAG_EMBEDDING_API_KEY`）。
2. 确认单价与 **`AI_PRICING_CONFIRMED=true`**。
3. 全量重建：

```bash
cd backend
python ../scripts/rag_reindex_semantic.py --dry-run
python ../scripts/rag_reindex_semantic.py
# 或: python -m rag.cli reindex --all
```

验收：`stale_documents=0`；`embedding.signature` 含 `openai_compatible:text-embedding-v4:1024`；抽样 `/api/rag/retrieve` 相似度合理。

**勿**在未配置 `RAG_EMBEDDING_CNY_PER_MILLION` 时对全库 reindex（预算预留会失败，可能半途中断）。

## 5. 检索校准（不调 LLM）

黄金集：**`evals/rag_retrieval_golden.json`**

```bash
cd backend
python ../scripts/rag_eval_retrieval.py
python ../scripts/rag_eval_retrieval.py --min-pass-rate 0.8
python -m pytest tests/test_rag_golden.py -q
```

根据 Top3 相似度分布调整 **`RAG_MIN_SCORE`**（语义默认约 0.40，local 约 0.12）。评课场景可对 `categories` / `document_ids` 限域。

## 6. 部署与备份

- 配置模板：`deploy/runtime.env.example`、`backend/.env.example`。
- 备份：`deploy/backup.sh` → MySQL dump + **`instance.tar.gz`**（含 `rag/files/`）。
- 恢复后若 Embedding 签名与库内不一致，执行 **reindex --all**。
- 文档：`deploy/README.md` RAG 小节。

## 7. 故障速查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 检索始终为空 | stale 签名 / 全库 local 向量未 reindex | `stats` 看 stale；语义 reindex |
| 503 知识库配置错误 | `RAG_*` 非法 | 查启动日志与 `/api/rag/status` 前 guard |
| 上传 413 | 超过 `RAG_MAX_UPLOAD_MB` | 调 env 或拆分 PDF |
| Embedding 502 | 密钥/限流/预算 | 查 `rag_embedding` 账本与 DashScope 控制台 |
| CLI 入库后 API 仍旧索引 | 跨进程 | 正常：签名检测会自动 reload；必要时重启 worker |
