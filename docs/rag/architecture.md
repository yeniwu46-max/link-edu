# RAG 架构与存储设计

## 1. 目标与边界

**目标**：为 LINK 提供「有出处、可审计」的教学知识检索，支撑问答与评课，而不是替代教研判断或官方量表效力。

**边界**：

- 扫描 PDF 无文字层 → 拒绝入库（需 OCR 后再传）。
- 生产默认 **单 worker gunicorn + MySQL**；进程内向量索引，不引入额外向量库服务（见 ADR-004）。
- 远程 Embedding / LLM 走现有 **预算账本**（`rag_embedding`、课堂 `chat`）。

## 2. 端到端数据流

```text
                    ┌─────────────────────────────────────────┐
  multipart/API     │  parsing → cleaning → chunking        │
  CLI ingest   ────▶│  (PDF/DOCX/TXT/MD → Block 流)           │
                    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │  embeddings (local hash | DashScope v4) │
                    └──────────────────┬──────────────────────┘
                                       │ 同事务
                    ┌──────────────────▼──────────────────────┐
                    │  MySQL: kb_documents + kb_chunks        │
                    │  BLOB: float32[L2-normalized]           │
                    │  files/: SHA256 原文件 (RAG_STORAGE_DIR)│
                    └──────────────────┬──────────────────────┘
                                       │ 签名 (count,max_id,updated_at)
                    ┌──────────────────▼──────────────────────┐
  query/evaluate    │  vector_store: numpy | faiss (可选)     │
                    │  inner product ≈ cosine                 │
                    └──────────────────┬──────────────────────┘
                                       │ Top-K, min_score, filter
                    ┌──────────────────▼──────────────────────┐
                    │  generation (query) | evaluation (评课) │
                    │  引用校验 · 证据不足短路                │
                    └─────────────────────────────────────────┘
```

## 3. 模块职责

| 模块 | 文件 | 职责 |
| --- | --- | --- |
| 配置 | `settings.py` | `RAG_*` 环境变量；`embedding_signature = provider:model:dim` 防混向量 |
| 元数据 | `models.py` | `KnowledgeDocument` / `KnowledgeChunk` |
| 解析 | `parsing.py` | 结构化块：heading / text / table；页码 |
| 清洗 | `cleaning.py` | 零宽字符、PDF 字距、页眉页脚 |
| 分块 | `chunking.py` | 标题树分节；句边界切分；表格按行+表头重复；节内 overlap |
| 向量 | `embeddings.py` | `HashEmbedder`（测试/无密钥）；`OpenAICompatibleEmbedder`（百炼等） |
| 索引 | `vector_store.py` | 从 DB 加载矩阵；可选 FAISS；过滤 category/document_ids |
| 生成 | `generation.py` | 问答 prompt、`[ref]` 清洗、insufficient 统一文案 |
| 评课 | `evaluation.py` | 逐指标检索 + LLM-as-a-Judge 形态输出 |
| 门面 | `service.py` | `ingest` / `reindex` / `retrieve` / `query` / `evidence_for_indicators` / `report_reference_sources` |
| HTTP | `routes.py` | `/api/rag/*`；公网管理员白名单 |
| CLI | `cli.py` | 运维 ingest / reindex / stats / query |

**耦合规则**：`classroom_reports`、`training` 等业务模块 **不得** 直接 import `parsing`/`vector_store`；统一 `get_kb()` 或 `report_reference_sources()`。

## 4. 存储模型

### 4.1 关系库（权威数据源）

- **`kb_documents`**：资料级元数据、`status`（processing/ready/failed）、`embedding_model` 签名、`sha256` 去重。
- **`kb_chunks`**：切片正文 + **`embedding` BLOB**（float32 字节序）+ `heading_path` JSON + 页码 + `extra`（预留给图谱/标注）。

备份：**mysqldump 含 kb 表** + **卷上 `instance/rag/files/`**。仅备份 MySQL 不备份 files 则无法 reindex。

### 4.2 进程内索引（缓存）

- 每次检索前比对聚合签名；变更则全量加载匹配当前 `embedding_signature` 的 chunk。
- 默认 **NumpyVectorStore**：万级切片、1024 维，内存约数十 MB，毫秒级。
- **`RAG_VECTOR_BACKEND=faiss`**：切片量更大时可选；无 filter 时走 FAISS，有过滤回退精确矩阵。

### 4.3 Embedding 签名隔离

切换 `RAG_EMBEDDING_PROVIDER`、模型或 `RAG_EMBEDDING_DIM` 后，旧 chunk 的 `embedding_model` 与当前 embedder 不一致 → `stale_documents` > 0，**必须 `reindex`**，否则检索结果为空或不全。

## 5. 可信生成（架构约束）

1. **检索门控**：无片段 ≥ `RAG_MIN_SCORE` → 不调用 LLM，固定返回「当前知识库暂无充分依据」。
2. **编号闭包**：模型只能引用 prompt 中给出的 `ref`；越界 `[n]` 删除。
3. **提示注入**：`question` 与 `knowledge[]` 均声明为不可信数据，非系统指令。
4. **评课分轨**：`classroom_evidence`（课堂事实）与 `theory_refs`（知识库）分离校验；无理论引用则 `theory_status=insufficient_evidence`。

## 6. 检索流水线（已实现）

1. **问句改写**：`RAG_QUERY_REWRITE=expand|hyde|off`（术语扩展；HyDE 需 LLM 预算）。
2. **召回**：向量 Top-`RAG_FETCH_K`（默认 20）+ 可选 BM25（`RAG_HYBRID_ENABLED`），RRF 融合（`RAG_RRF_K`）。
3. **精排**：`RAG_RERANK_ENABLED` 时对候选 bi-encoder 重打分，输出 Top-`RAG_TOP_K`。
4. **门控**：`relevant` 依据向量余弦分与 `RAG_MIN_SCORE`；RRF 分仅用于排序（`fusion_score`）。
5. **入库增强**：节级 `parent_summary` 写入 `extra`；轻量实体/关系写入 `extra.graph`；`valid_until` 过期文档不参与检索。

### GraphRAG 检索（功能开关，默认关闭）

- `backend/rag/graph_vocabulary.json` 定义版本化实体、别名和人工审核的关系规则；每条规则须在当前切片中找到精确 cue 才能生成边。
- `extra.graph` 保存 `schema_version`、实体与关系。关系证据保留原文 cue；图索引加载时再次校验 cue，避免无来源的边进入召回。
- `KnowledgeGraphIndex` 从查询命中的实体及向量/BM25 种子实体出发，最多扩展 `RAG_GRAPH_MAX_DEPTH` 层和 `RAG_GRAPH_MAX_EXPANSIONS` 条边，过滤 inactive、过期和越界分类/文档。
- 图候选与向量/BM25 使用 RRF 融合，再交给现有重排。图分数不会代替向量相关性门槛；无足够相关证据仍拒答。命中会带 `graph_paths`，每条关系标明 `source_chunk_id` 与支持原文 cue。
- 设置 `RAG_GRAPH_ENABLED=true` 开启默认图检索，或在 `/api/rag/retrieve`、`/api/rag/query` 请求中传 `{"graph": true}` 单次试用。默认保持关闭。
- 更新图谱元数据无需重新计算向量：在 backend 目录运行 `python -m rag.cli graph-rebuild`。实体词表和人工审核关系调整后执行此命令。

异步入库：`RAG_ASYNC_INGEST` 或表单 `async=1`，后台线程执行 `finish_ingest`；前端 `/knowledge` 页可上传、预览切片、试检索。

语料治理字段：`content_version`、`license_note`、`valid_until`、`last_audited_at`；审计表 `kb_audit_logs`（`GET /api/rag/audit`）。

## 7. 预留扩展

| 扩展 | 挂载点 |
| --- | --- |
| 跨文档 GraphRAG 检索 | 在 `extra.graph` 上增加 `GraphRetriever` 与向量 RRF |
| 专用 Cross-Encoder Rerank | 替换 `rerank.py` 中 bi-encoder 精排 |
| 任务队列入库 | 将 `jobs.schedule_ingest` 换为 Celery/RQ |

详见 [优化路线图](roadmap-optimization.md)。
