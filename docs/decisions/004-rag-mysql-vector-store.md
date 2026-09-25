# ADR-004：RAG 向量存 MySQL BLOB + 进程内索引

## 状态

2026-09-25 已采用（`backend/rag` 已落地）。

## 背景

LINK 需要教学资料向量检索，支撑问答与评课依据。部署栈为 **MySQL 8 + 单 worker gunicorn + 持久卷 `instance/`**，团队规模小，不宜同时运维 Milvus/Chroma/第二套数据库。

备选：Chroma 嵌入式、FAISS 纯文件、pgvector（PostgreSQL）、Milvus 独立服务。

## 决策

1. **向量与切片元数据写入 MySQL `kb_chunks.embedding`（float32 BLOB）**，与 `kb_documents` 同一事务提交。
2. **检索在应用进程内**从 DB 加载 L2 归一化向量，默认 **numpy 精确内积**；可选 **faiss-cpu** 作为同接口后端。
3. **不引入**独立向量数据库服务；**不**为 RAG 单独增加 PostgreSQL。

## 理由

| 因素 | 说明 |
| --- | --- |
| 规模 | 预期 10³–10⁴ 切片；10k×1024 float32 ≈ 40MB，毫秒级精确检索 |
| 运维 | `backup.sh` 已 dump MySQL + `instance/`；向量与文件同源备份 |
| 一致性 | 无「向量库与业务库双写」问题 |
| 签名 | `embedding_model` 字段隔离不同 embedder，reindex 可渐进 |
| 扩展 | `vector_store.search/invalidate/size` 接口可换 pgvector/Milvus 实现 |

## 后果

- **冷启动/首查**需加载矩阵；万级可接受，十万级需 FAISS 或快照预热。
- **多 worker** 下每进程各持一份索引内存；水平扩展需 ADR 修订（共享索引或外置向量库）。
- **MySQL** 不原生 ANN；依赖全量或 FAISS 内存索引，非 DB 内近似最近邻。

## 相关文档

- [RAG 架构](../rag/architecture.md)
- [运维 Runbook](../rag/operations-runbook.md)
- [优化路线图](../rag/roadmap-optimization.md)（何时考虑 FAISS / 外置库）
