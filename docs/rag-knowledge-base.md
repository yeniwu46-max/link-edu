# RAG 向量知识库（backend/rag）

> **完整技术文档**见 [`docs/rag/README.md`](rag/README.md)（架构、运维、API 接入、优化路线图、ADR-004）。下文为速查。

把教学理论、课程标准、评价量表、优秀案例、微格规范等资料建成可检索知识库，为 AI 评课、反馈生成和问答提供可追溯依据。模块独立于业务代码，其他模块只通过 `rag.service.get_kb()` 调用。

## 1. 架构

```
上传 ──▶ parsing ──▶ cleaning ──▶ chunking ──▶ embeddings ──▶ kb_chunks(MySQL, float32 BLOB)
                                                                   │  启动/变更时重建
问题 / 评价任务 ──▶ Query Embedding ──▶ vector_store(numpy | faiss) ◀┘
                                         │ Top-K + 阈值
                                         ▼
                         generation（问答）/ evaluation（逐指标评价）
                                         │ 只能引用给定编号，越界引用被删除
                                         ▼
                              回答 + citations（文档 / 章节 / 页码 / 相似度）
```

| 文件 | 职责 |
| --- | --- |
| `settings.py` | 读取 `RAG_*` 配置（app.config 优先于环境变量），知识分类定义 |
| `models.py` | `kb_documents`、`kb_chunks` 两张表 |
| `parsing.py` | PDF（pypdf，逐页）、Word（样式标题 + 表格）、TXT、Markdown → 有序的 heading/text/table 块 |
| `cleaning.py` | 零宽/控制字符、全角空格、PDF 字距空格、页眉页脚与页码 |
| `chunking.py` | 按标题树分节；段落整体打包；超长段落按句切；表格按行切并重复表头；节内句级重叠 |
| `embeddings.py` | `HashEmbedder`（离线词面）/ `OpenAICompatibleEmbedder`（百炼、OpenAI、本机 bge 等） |
| `vector_store.py` | `NumpyVectorStore`（默认，精确余弦）/ `FaissVectorStore`（可选） |
| `generation.py` | 可信问答提示词、引用校验、证据不足判定 |
| `evaluation.py` | 课堂行为 + 教师文本 + 评价指标 + 理论依据 → 逐指标评价（LLM-as-a-Judge 入口） |
| `service.py` | `KnowledgeBase` 门面：入库、重建、删除、检索、问答、指标证据 |
| `routes.py` | `/api/rag/*` 接口 |
| `cli.py` | 批量入库、重建索引、检索调试 |

### 为什么选“MySQL 存向量 + 进程内索引”

- 生产环境是单 worker gunicorn + MySQL，预期语料为数千到数万切片。1 万 × 1024 维 float32 约 40 MB，精确检索只需几毫秒，不需要再部署 Chroma/Milvus 等服务。
- 向量与元数据在同一事务里写入，现有 MySQL 备份天然覆盖知识库，不会出现“两个库不一致”。
- 每次检索先比较 `(切片数, 最大切片 ID, 文档最近更新时间)` 签名，CLI 在另一进程入库后也能自动刷新索引。
- 超过约 5 万切片时改用 `RAG_VECTOR_BACKEND=faiss`（`RAG_FAISS_HNSW_M>0` 启用 HNSW）；迁移 pgvector/Milvus 时，实现同样的 `search / invalidate / size` 接口即可。

## 2. 数据表

`kb_documents`：`title`、`filename`、`file_type`(pdf/docx/txt/md)、`category`、`tags`、`source`(出处)、`description`、`sha256`(去重)、`storage_path`、`status`(processing/ready/failed)、`error`、`page_count`、`chunk_count`、`embedding_model`、`is_active`、`uploaded_by`、`created_at`、`updated_at`。

`kb_chunks`：`document_id`、`ordinal`、`kind`(text/table)、`text`、`heading_path`(章节路径数组)、`page_start/page_end`、`char_count`、`content_hash`、`embedding`(float32 BLOB)、`embedding_model`(provider:model:dim 签名)、`embedding_dim`、`extra`(预留给知识图谱实体/关系、评审标注)。

知识分类：`theory` 教学理论、`curriculum_standard` 课程标准、`rubric` 教学评价量表、`case` 优秀教学案例、`microteaching_norm` 微格教学规范、`other` 其他资料。

原始文件保存在 `RAG_STORAGE_DIR/files/<sha256>.<ext>`（默认 `backend/instance/rag`，部署时是持久卷），用于重新切片。

## 3. 接口（均需 JWT）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/rag/status` | 文档/切片统计、Embedding 与后端信息、是否可管理 |
| GET | `/api/rag/categories` | 知识分类 |
| POST | `/api/rag/documents` | multipart：`file`，可选 `title`、`category`、`tags`、`source`、`description`（管理员） |
| GET | `/api/rag/documents` | `?category=&status=&q=&page=&page_size=` |
| GET/PATCH/DELETE | `/api/rag/documents/<id>` | 查看 / 修改元数据或 `is_active` / 删除（修改、删除需管理员） |
| POST | `/api/rag/documents/<id>/reindex` | 用原文件重新切片并向量化（管理员） |
| GET | `/api/rag/documents/<id>/chunks` | `?offset=&limit=` 查看切片 |
| POST | `/api/rag/retrieve` | 只检索、不调用 LLM，用于调试切片和阈值 |
| POST | `/api/rag/query` | 完整 RAG 问答 |
| POST | `/api/rag/evaluate` | 教学评价预留接口 |

`/query` 请求：

```json
{"query": "提问后应该留多长候答时间？", "top_k": 5, "categories": ["rubric", "theory"], "document_ids": [3], "generate": true}
```

响应（节选）：

```json
{
  "status": "answered",
  "grounded": true,
  "answer": "提问后应留出三到五秒的候答时间，避免自问自答[1]。",
  "citations": [{"ref": 1, "document_title": "提问技能评价量表", "category_label": "教学评价量表",
                 "section": "一、评价维度 > 提问设计", "page_start": 2, "page_end": 2,
                 "similarity": 0.62, "quote": "问题应指向教学目标……"}],
  "hits": [{"rank": 1, "ref": 1, "similarity": 0.62, "relevant": true, "text": "…", "section": "…",
            "page_start": 2, "document": {"id": 3, "title": "…", "category": "rubric"}}],
  "retrieval": {"top_k": 5, "min_score": 0.4, "relevant_count": 2, "embedding_model": "openai_compatible:text-embedding-v4:1024",
                "vector_backend": "numpy", "elapsed_ms": 85.3}
}
```

`status` 取值：`answered` / `insufficient_evidence` / `retrieval_only` / `generation_failed`（检索结果仍返回）。

### 可信生成规则

1. 没有片段达到 `RAG_MIN_SCORE` 时**不调用 LLM**，直接返回“当前知识库暂无充分依据。”
2. 提示词要求只依据编号片段作答、每个结论标注 `[ref]`，并把片段与问题都当作不可信数据（防提示注入）。
3. 模型输出的越界编号会被删除；模型声明不足，或没有任何有效引用时，统一改为“当前知识库暂无充分依据”。
4. `grounding.uncited_sentences` 统计没有标注引用的句子数，供后续 LLM-as-a-Judge 复核。

## 4. 教学评价接入

```json
POST /api/rag/evaluate
{
  "course_title": "分数的初步认识", "scene": "新授",
  "transcript": "老师：……",
  "behavior_observations": [{"label": "背对学生板书", "at_ms": 42000}],
  "indicators": [{"key": "questioning", "label": "提问质量", "description": "问题是否具体，是否有追问"}],
  "top_k_per_indicator": 3, "categories": ["rubric", "microteaching_norm"], "generate": true
}
```

- 不传 `indicators` 时使用现有 AI 评课的六个维度（`services/llm/deepseek.py`）。
- 每个指标单独检索理论依据，片段全局去重编号；每个指标只能引用为它检索到的编号。
- 每个指标返回 `classroom_evidence`、`judgement`、`suggestion`、`theory_status`(`grounded` / `insufficient_evidence`)、`citations`。
- `generate: false` 只返回 `indicators[].knowledge_refs` 与 `knowledge` 证据池，不产生模型费用，方便现有评课提示词直接拼接：

```python
from rag.service import get_kb
pool, refs = get_kb().evidence_for_indicators(indicators, scene='导入')
```

后续扩展位置：GraphRAG 可基于 `kb_chunks.extra` 存实体与关系，再实现一个与 `NumpyVectorStore.search` 同签名的图检索器并与向量结果融合；Agent 可以把 `retrieve` / `query` / `evaluate` 作为工具调用。

## 5. 配置与费用

完整说明见 `backend/.env.example` 的 RAG 段。要点：

- 默认 `RAG_EMBEDDING_PROVIDER=local`：离线、免费，只做词面匹配，**不是语义检索**，仅用于测试和无密钥演示；`/status` 会返回 `semantic: false`。
- 生产环境建议使用 `openai_compatible` + 百炼 `text-embedding-v4`（1024 维，每批 10 条）。远程调用会先在课堂人民币预算账本里预留（服务名 `rag_embedding`），需要 `AI_PRICING_CONFIRMED=true` 和 `RAG_EMBEDDING_CNY_PER_MILLION`；本机端点（127.0.0.1）不计费。
- 问答与评价复用 `classroom_providers.chat`，与课堂使用同一套供应商开关、密钥和预算上限。
- 更换 Embedding 模型或维度后，旧向量的签名不匹配，不会混入检索；执行 `python -m rag.cli reindex` 即可重建。
- 公网部署（`PUBLIC_DEPLOYMENT=true`）默认关闭知识库；开启后管理操作只允许 `RAG_ADMIN_ACCOUNTS` 中列出的账号（登录时可以自选角色，因此 role 不能作为权限依据）。上传单独使用 `RAG_MAX_UPLOAD_MB` 限制，不受全局 2 MB 请求上限约束。

## 6. 运维命令（在 backend/ 下）

语料清单与批量入库见 [`sources/rag/README.md`](../sources/rag/README.md) 与 [`evals/rag_retrieval_golden.json`](../evals/rag_retrieval_golden.json)（检索验收，不调 LLM）。运维细节见 [`docs/rag/operations-runbook.md`](../docs/rag/operations-runbook.md)。

```bash
python -m rag.cli ingest ./资料/评价量表 --category rubric --source "校内微格中心"
python -m rag.cli stats
python -m rag.cli query "如何设计有效的课堂导入" --top-k 5          # 只检索
python -m rag.cli query "如何设计有效的课堂导入" --answer           # 调用 LLM（产生费用）
python -m rag.cli reindex            # 仅重建模型签名过期的文档；--all 全部重建
python -m pytest tests/test_rag.py
```

## 7. 已知限制

- 扫描版 PDF 没有文字层时会拒绝入库，需要先做 OCR。
- pypdf 不能还原 PDF 中的表格结构，表格会作为普通文本行入库；评价量表建议上传 .docx 或 Markdown。
- 入库是同步执行的：百页 PDF 使用远程 Embedding 大约需要几十秒（在 gunicorn 180 秒超时之内）。资料量增大后可改为后台任务。
- `RAG_MIN_SCORE` 需要按实际语料和模型校准，可以先用 `/api/rag/retrieve` 观察相似度分布。
