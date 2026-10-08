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

### GraphRAG

```bash
cd backend
python -m rag.cli graph-rebuild       # 仅刷新 extra.graph，不调用 Embedding
cd ..
python scripts/rag_eval_graph.py      # 对比 graph off/on，不调用 LLM
```

图谱词表和已审核关系规则位于 `backend/rag/graph_vocabulary.json`。评测未达标前保持 `RAG_GRAPH_ENABLED=false`；试检索请求可以单次传 `graph: true`，页面会显示图路径及可打开的来源切片。出现异常时，GraphRAG 会记录后端日志并退回向量/BM25 检索。

评测支持 `--report <本机私有路径.json>`，保存每题切片 ID、排名、相关性、路径、MRR@5 与耗时。基础黄金集脚本强制 `graph=False`；图谱脚本在同一黄金集、同一排名截断上比较直接问题，并把无答案失败、缺失预期来源、空路径及无效边计入最终判定。两者都拒绝启用会调用 LLM 的 HyDE 改写。

图缓存按实际图谱内容、分类和失效日期生成指纹，避免 MySQL 秒级时间戳漏掉连续重建。每次图检索会读取图谱输入以核对指纹；扩大语料规模前应测量这部分开销。来源原文接口会拒绝已停用、未就绪或过期的切片。异常回退时 `retrieval.graph.error=graph_retrieval_failed`、`fallback=true`，界面显示回退提示。

本机验收先确认实际生效的 `DATABASE_URL`（进程环境变量可能覆盖 `.env`），备份数据库与 `RAG_STORAGE_DIR`，在独立恢复库校验恢复结果，再执行重建。不要仅凭配置默认值推断当前使用 MySQL。图谱重建前后应比较切片正文、非图元数据与向量摘要，确保未被更改。

2026-10-08 本机验收尚未达到开启条件，见 [验收报告](graphrag-local-acceptance-2026-10-08.md)。关闭请求级开关可立即回退；保持环境配置 `RAG_GRAPH_ENABLED=false`，修改环境配置后重启对应进程。

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
