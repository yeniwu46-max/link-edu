# ADR-005：基于切片证据的轻量 GraphRAG

## 状态

采用；首轮以 feature flag 关闭，完成图谱评测后再启用。

## 决策

- 图谱实体、关系和 schema version 存入 `kb_chunks.extra.graph`，MySQL 仍是权威存储，不增加图数据库或表迁移。
- 受控词表和人工审核关系规则位于 `backend/rag/graph_vocabulary.json`。关系只有在承载切片包含精确 cue 时才能入图；检索索引再次校验 cue。
- 进程内 `KnowledgeGraphIndex` 与现有向量/BM25 索引采用同样的签名刷新思路，并过滤 inactive、过期及请求范围外的文档。
- 图候选与现有召回使用 RRF 融合并进入现有重排；向量相关性门槛和可信引用校验保持不变。每条返回关系包含来源切片 ID 和 cue。
- `RAG_GRAPH_ENABLED` 默认 `false`；检索/问答接口允许请求级 `graph` 布尔值。图索引或检索异常时记录日志并退回现有向量/BM25 链路。
- `graph-rebuild` 仅重建图 JSON，不调用 Embedding；Embedding 模型切换仍使用既有 `reindex` 命令。

## 验收

- 现有检索黄金集通过率至少 80%，直接问句通过率相对基线下降不超过 2 个百分点。
- `evals/rag_graph_golden.json` 多跳 Recall@5 至少 80%；每条返回关系的 cue 均存在于指定来源切片。
- 关闭图开关时旧请求和证据不足门控保持兼容；启用图检索时尊重分类、文档过滤和失效日期。

## 后果

- 图质量取决于受控词表和人工审核关系覆盖度；首轮不以自动 LLM 抽取扩大覆盖。
- 应用进程缓存图索引，规模增长后需观察内存和构建时间；超过当前单进程适用规模时另行评估外部图服务。
