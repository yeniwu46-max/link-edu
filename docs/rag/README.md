# RAG 向量知识库 · 技术文档索引

临客 LINK 的 **RAG（Retrieval-Augmented Generation）** 把教学理论、课程标准、评价量表、优秀案例、微格规范等资料建成**可检索、可引用、证据不足则拒答**的知识库，为 AI 问答、微格评课与后续 Agent 提供依据。

## 阅读顺序

| 文档 | 适合谁 | 内容 |
| --- | --- | --- |
| [架构与存储选型](architecture.md) | 后端 / 架构 | 流水线、模块表、MySQL+BLOB+进程内索引、扩展点 |
| [运维与语料 Runbook](operations-runbook.md) | 运维 / 教研资料管理员 | manifest、批量入库、百炼 reindex、黄金问句、部署备份 |
| [API 与业务接入](api-and-integration.md) | 全栈 / 产品 | `/api/rag/*`、可信生成、评课接口、课堂报告合并引用 |
| [优化路线图](roadmap-optimization.md) | 负责人 / 规划 | 与 RAG 同级的全盘能力优化方向（检索、GraphRAG、Agent、前端等） |
| [ADR-004：向量存储方案](../decisions/004-rag-mysql-vector-store.md) | 架构评审 | 为何不单独上 Milvus/Chroma/pgvector |

## 代码与数据入口

| 路径 | 说明 |
| --- | --- |
| `backend/rag/` | RAG 模块（业务侧只应调用 `rag.service.get_kb()`） |
| `backend/sql/schema.sql` | `kb_documents` / `kb_chunks` |
| `sources/rag/manifest.json` | 语料清单（P0/P1） |
| `sources/rag/README.md` | 语料目录说明与命令速查 |
| `evals/rag_retrieval_golden.json` | 检索黄金问句（不调 LLM） |
| `backend/tests/test_rag.py`、`test_rag_golden.py` | 自动化测试 |

## 与旧文档的关系

- 原单页说明 [`../rag-knowledge-base.md`](../rag-knowledge-base.md) 仍保留**接口与配置速查**；详细设计以本目录为准。
- 课堂 BM25 资料见 [`../classroom-sources.md`](../classroom-sources.md)；RAG 逐步承接并与之**双源合并**（见 [API 与业务接入](api-and-integration.md)）。

## 一分钟能力清单

- **管理**：上传 PDF/Word/TXT/Markdown，分类、标签、出处、去重、启停、删除、重建索引  
- **检索**：向量 Top-K + `RAG_MIN_SCORE`，返回章节/页码/相似度  
- **问答**：`POST /api/rag/query`，强制引用编号，证据不足不调用 LLM  
- **评课**：`POST /api/rag/evaluate`，按指标检索理论依据 + 逐指标 grounded 状态  
- **课堂报告**：`gather_report_references()` = JSON BM25 + `kb:<chunk_id>` 向量片段
- **GraphRAG（默认关闭）**：受控实体与原文 cue 关系扩展候选，返回可追溯路径；`python -m rag.cli graph-rebuild` 更新图元数据，不重算 Embedding
