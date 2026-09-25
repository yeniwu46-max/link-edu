# RAG 语料清单（sources/rag）

本目录存放**可入库**的教学资料路径与元数据，供 [`scripts/rag_ingest_manifest.py`](../scripts/rag_ingest_manifest.py) 批量写入 MySQL 向量库。

## 文件

| 文件 | 说明 |
| --- | --- |
| [`manifest.json`](manifest.json) | 入库清单：`path`、`title`、`category`、`source`、`tags`、`priority`（P0/P1） |
| [`corpus/classroom_knowledge/`](corpus/classroom_knowledge/) | 由 [`scripts/rag_export_knowledge_cards.py`](../scripts/rag_export_knowledge_cards.py) 从 `backend/data/classroom_knowledge.json` 导出的 Markdown |

## 分类（category）

`theory` · `curriculum_standard` · `rubric` · `case` · `microteaching_norm` · `other`

## 常用命令

```bash
# 1. 刷新课堂 JSON 知识卡
python scripts/rag_export_knowledge_cards.py

# 2. 仅入库 P0（默认 local 向量；生产前先配百炼再 reindex）
cd backend
python ../scripts/rag_ingest_manifest.py --priority P0

# 3. 切换百炼后全量重建语义向量（需 AI_PRICING_CONFIRMED + RAG_EMBEDDING_CNY_PER_MILLION）
python -m rag.cli reindex --all

# 4. 黄金问句检索验收（不调 LLM）
python ../scripts/rag_eval_retrieval.py

# 5. 切换百炼语义向量并全量重建（需 AI_PRICING_CONFIRMED 与 RAG_EMBEDDING_CNY_PER_MILLION）
python ../scripts/rag_reindex_semantic.py --dry-run
python ../scripts/rag_reindex_semantic.py
```

量表与课标优先 **.docx / .md**；扫描 PDF 需 OCR 后再加入 manifest。
