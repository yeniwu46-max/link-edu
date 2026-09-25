"""RAG knowledge base for LINK.

Pipeline: upload -> parsing -> cleaning -> chunking -> embeddings -> kb_chunks (MySQL) -> vector_store
          -> retrieve Top-K -> generation (grounded, cited) / evaluation (per-indicator theory basis).

Other modules should depend on rag.service.get_kb() only, e.g.
    pool, refs = get_kb().evidence_for_indicators(indicators, scene='导入')
"""


def register_rag(app):
    from rag import models  # noqa: F401
    from rag.governance import KnowledgeAuditLog  # noqa: F401
    from rag.routes import bp
    app.register_blueprint(bp)
