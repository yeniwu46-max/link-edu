"""Knowledge-base settings. App config wins over environment so tests can override per app."""
import os
from dataclasses import dataclass
from pathlib import Path

from flask import current_app, has_app_context

BACKEND_ROOT = Path(__file__).resolve().parents[1]

CATEGORIES = {
    'theory': '教学理论',
    'curriculum_standard': '课程标准',
    'rubric': '教学评价量表',
    'case': '优秀教学案例',
    'microteaching_norm': '微格教学规范',
    'other': '其他资料',
}
FILE_TYPES = {'pdf': 'PDF', 'docx': 'Word', 'txt': 'TXT', 'md': 'Markdown'}
INSUFFICIENT_MESSAGE = '当前知识库暂无充分依据'


def _raw(name, default=None):
    if has_app_context() and current_app.config.get(name) is not None:
        return current_app.config[name]
    value = os.getenv(name)
    return default if value is None or value.strip() == '' else value.strip()


def _bool(name, default):
    value = _raw(name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def _int(name, default, low, high):
    try:
        value = int(_raw(name, default))
    except (TypeError, ValueError):
        raise ValueError(f'{name} 必须是整数') from None
    if not low <= value <= high:
        raise ValueError(f'{name} 必须在 {low} 到 {high} 之间')
    return value


def _float(name, default):
    value = _raw(name, default)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} 必须是数字') from None


@dataclass(frozen=True)
class RagSettings:
    enabled: bool
    storage_dir: Path
    embedding_provider: str
    embedding_model: str
    embedding_dim: int
    embedding_base_url: str
    embedding_api_key_name: str
    embedding_batch_size: int
    embedding_timeout: float
    vector_backend: str
    faiss_hnsw_m: int
    top_k: int
    max_top_k: int
    min_score: float
    chunk_target_chars: int
    chunk_max_chars: int
    chunk_overlap_chars: int
    chunk_min_chars: int
    max_upload_bytes: int
    max_chunks_per_document: int
    answer_max_tokens: int
    admin_accounts: frozenset
    hybrid_enabled: bool
    fetch_k: int
    rrf_k: int
    rerank_enabled: bool
    query_rewrite: str
    parent_context_enabled: bool
    graph_meta_enabled: bool
    async_ingest_default: bool

    @property
    def embedding_signature(self):
        """Vectors from different models or dimensions are never mixed in one index."""
        return f'{self.embedding_provider}:{self.embedding_model}:{self.embedding_dim}'

    @property
    def semantic(self):
        return self.embedding_provider != 'local'


def load_settings():
    public = str(_raw('PUBLIC_DEPLOYMENT', False)).lower() == 'true'
    provider = str(_raw('RAG_EMBEDDING_PROVIDER', 'local')).lower()
    if provider not in ('local', 'openai_compatible'):
        raise ValueError('RAG_EMBEDDING_PROVIDER 仅支持 local 或 openai_compatible')
    backend = str(_raw('RAG_VECTOR_BACKEND', 'numpy')).lower()
    if backend not in ('numpy', 'faiss'):
        raise ValueError('RAG_VECTOR_BACKEND 仅支持 numpy 或 faiss')
    storage = Path(_raw('RAG_STORAGE_DIR', BACKEND_ROOT / 'instance' / 'rag'))
    if not storage.is_absolute():
        storage = BACKEND_ROOT / storage
    # Hashed lexical vectors score lower than semantic embeddings for the same relevance.
    min_score = _float('RAG_MIN_SCORE', 0.12 if provider == 'local' else 0.40)
    target = _int('RAG_CHUNK_TARGET_CHARS', 500, 100, 4000)
    maximum = _int('RAG_CHUNK_MAX_CHARS', 900, target, 8000)
    admins = frozenset(v.strip() for v in str(_raw('RAG_ADMIN_ACCOUNTS', '')).split(',') if v.strip())
    rewrite = str(_raw('RAG_QUERY_REWRITE', 'expand')).lower()
    if rewrite not in ('off', 'expand', 'hyde'):
        raise ValueError('RAG_QUERY_REWRITE 仅支持 off、expand、hyde')
    return RagSettings(
        enabled=_bool('RAG_ENABLED', not public),
        storage_dir=storage,
        embedding_provider=provider,
        embedding_model=str(_raw('RAG_EMBEDDING_MODEL', 'local-hash-v1' if provider == 'local' else 'text-embedding-v4')),
        embedding_dim=_int('RAG_EMBEDDING_DIM', 1024, 64, 4096),
        embedding_base_url=str(_raw('RAG_EMBEDDING_BASE_URL',
                                    'https://dashscope.aliyuncs.com/compatible-mode/v1')).rstrip('/'),
        embedding_api_key_name='RAG_EMBEDDING_API_KEY' if _raw('RAG_EMBEDDING_API_KEY') else 'DASHSCOPE_API_KEY',
        embedding_batch_size=_int('RAG_EMBEDDING_BATCH_SIZE', 10, 1, 256),
        embedding_timeout=_float('RAG_EMBEDDING_TIMEOUT_SECONDS', 30),
        vector_backend=backend,
        faiss_hnsw_m=_int('RAG_FAISS_HNSW_M', 0, 0, 128),
        top_k=_int('RAG_TOP_K', 5, 1, 50),
        max_top_k=_int('RAG_MAX_TOP_K', 20, 1, 100),
        min_score=min_score,
        chunk_target_chars=target,
        chunk_max_chars=maximum,
        chunk_overlap_chars=_int('RAG_CHUNK_OVERLAP_CHARS', 80, 0, 1000),
        chunk_min_chars=_int('RAG_CHUNK_MIN_CHARS', 60, 0, 1000),
        max_upload_bytes=_int('RAG_MAX_UPLOAD_MB', 20, 1, 200) * 1024 * 1024,
        max_chunks_per_document=_int('RAG_MAX_CHUNKS_PER_DOCUMENT', 2000, 1, 50000),
        answer_max_tokens=_int('RAG_ANSWER_MAX_TOKENS', 1200, 200, 8000),
        admin_accounts=admins,
        hybrid_enabled=_bool('RAG_HYBRID_ENABLED', True),
        fetch_k=_int('RAG_FETCH_K', 20, 5, 100),
        rrf_k=_int('RAG_RRF_K', 60, 1, 200),
        rerank_enabled=_bool('RAG_RERANK_ENABLED', provider != 'local'),
        query_rewrite=rewrite,
        parent_context_enabled=_bool('RAG_PARENT_CONTEXT', True),
        graph_meta_enabled=_bool('RAG_GRAPH_META', True),
        async_ingest_default=_bool('RAG_ASYNC_INGEST', True),
    )
