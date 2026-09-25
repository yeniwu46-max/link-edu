# LINK 能力优化路线图（含 RAG 纵深）

本文档列出与 **RAG 同级或可组合** 的全盘优化方向，按「价值 × 与现有架构契合度」组织。实施前应像 ADR-001/004 一样写清边界与验收，避免与证据驱动评课原则冲突。

---

## A. 知识库与检索（RAG 纵深）

| 方向 | 现状 | 优化内容 | 预期收益 |
| --- | --- | --- | --- |
| **混合检索 Hybrid** | 向量 + 独立 BM25 JSON | 对同一 query 做 BM25∪向量 + RRF/加权；量表专有名词更稳 | 减少「语义近但条文不对」的误召 |
| **重排序 Rerank** | 仅 embedding 分数 | 百炼 rerank 或 cross-encoder Top20→Top5 | 提高 P0 问句 Top1 准确率 |
| **Query 改写** | 原问句直接 embed |  HyDE / 多 query 扩展（课标术语表） | 师范生口语问法更易命中条文 |
| **父子块 / 多粒度** | 单级 chunk | 小节摘要 + 段落双索引，检索命中父块返回子块 | 长课标 PDF 上下文更完整 |
| **GraphRAG** | `kb_chunks.extra` 预留 | 实体（课标条目、量表维度）与边；子图检索 + 向量 | 跨文档「依据链」可解释 |
| **语料治理** | manifest 手工 | 版本号、失效日、授权字段、审计日志 | 竞赛/商用合规 |
| **异步入库** | 同步 ingest 占 worker | 队列 + `status=processing` 轮询 | 大 PDF 不堵 gunicorn |
| **索引预热 / 快照** | 首查加载矩阵 | 启动时 `store.size()`；可选磁盘 snapshot | 冷启动延迟稳定 |
| **前端知识库** | 仅 API/CLI | 资源库或教师后台：上传、预览 chunk、试检索 | 教研自助运维 |

**验收建议**：延续 `evals/rag_retrieval_golden.json` + 语义 reindex 后 pass rate ≥80%；新增 hybrid 时单独一条 pytest 不回归。

---

## B. 可信生成与评测（与 RAG 并列的核心）

| 方向 | 现状 | 优化内容 |
| --- | --- | --- |
| **LLM-as-a-Judge** | RAG evaluate 初版 | 对 `grounding.uncited_sentences`、评课 `theory_status` 二次判别 |
| **片段训练评课 + RAG** | DeepSeek 六维 + 课堂文本 | `generate:false` 注入 `evidence_for_indicators` 再生成报告 |
| **统一证据模型** | 事件 id + source_ids + kb chunk | 报告 UI 一键跳转：时间线 ↔ 知识库原文 |
| **DeepEval / 规则集扩展** | classroom-offline-evaluation | 增加「错误引用」「无依据打分」用例 |
| **拒答与 abstention 指标** | 文案固定 | 统计 insufficient 比例，防模型「硬答」 |

与 [ADR-001 证据驱动课堂](../decisions/001-evidence-based-classroom.md) 一致：**无证据 null，不虚构课堂事实**。

---

## C. 多模态课堂（已有基础，可系统化）

| 方向 | 现状 | 优化内容 |
| --- | --- | --- |
| **动作 + 评课** | motion_evidence 六维 posture | 与 RAG「教态规范」条文对齐引用 |
| **视觉 + RAG** | 云视觉 JSON | 「板书可见性」类问题检索微格规范片段 |
| **ASR 质量** | 讯飞/百炼 | 热词（分数、平均分）、分段置信度进事件 |
| **学习回放** | 本地 replay | 回放页展示当次报告引用的 kb 片段 |

---

## D. 模型与成本（平台级）

| 方向 | 说明 |
| --- | --- |
| **供应商抽象** | 已有 deepseek / openai_next；Embedding 与 chat 统一 health probe |
| **缓存** | 相同 query embedding 短 TTL；相同 report 输入 hash 拒重复生成 |
| **分级模型** | 检索/分类用小模型，评课/report 用大模型 |
| **预算可视化** | `/api/rag/status` + 课堂 budget 合并仪表盘 |

---

## E. 产品与工作流

| 方向 | 说明 |
| --- | --- |
| **学科/学段维度** | manifest + 检索 filter：`stage=primary_math` |
| **教师自定义资料** | 个人库 vs 校级库（tenant 字段 + 权限） |
| **Agent 工具化** | 课堂中「查规范」工具：`retrieve` + 只读 citations |
| **竞赛交付** | 预置 P0 语料 docker 卷或 init 脚本，Demo 开箱有依据 |

---

## F. 工程与规模（非功能）

| 方向 | 触发条件 |
| --- | --- |
| **FAISS / HNSW** | 切片 > ~5 万 |
| **多 worker** | 需 Redis 索引失效 + 任务队列（与 ADR-001 冲突，需新 ADR） |
| **pgvector 副库** | MySQL 仅元数据，向量迁 PostgreSQL（运维成本↑） |
| **可观测性** | 检索 latency、embed token、insufficient 率进日志/metrics |

---

## 建议优先级（2026 季度视角）

1. **P0**：百炼语义 reindex 上线 + 黄金集校准 + 片段训练/课堂报告 **深度接 RAG 证据池**（非仅 merge references）。  
2. **P1**：混合检索 + 前端知识库管理 + 异步入库。  
3. **P2**：Rerank、GraphRAG 试点、LLM-as-a-Judge 闭环。  
4. **P3**：多 tenant、多 worker、独立向量库服务。

每启动一项，在 `docs/decisions/` 增加 ADR，并补充 `evals/` 或 pytest 验收，与 RAG 建设方式保持一致。
