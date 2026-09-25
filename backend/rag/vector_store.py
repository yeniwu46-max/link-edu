"""In-process vector indexes built from kb_chunks.embedding.

Production runs one gunicorn worker, and the knowledge base is expected to hold thousands to tens of thousands
of chunks: exact inner-product search over a float32 matrix (10k x 1024 ~ 40 MB) takes milliseconds and needs no
extra service. FAISS is an optional drop-in for larger corpora; pgvector/Milvus can implement the same interface.
"""
import threading
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func

from extensions import db
from rag.models import KnowledgeChunk, KnowledgeDocument


@dataclass(frozen=True)
class VectorHit:
    chunk_id: int
    score: float


@dataclass(frozen=True)
class _Snapshot:
    signature: tuple
    ids: np.ndarray
    document_ids: np.ndarray
    categories: np.ndarray
    matrix: np.ndarray
    index: object = None


class NumpyVectorStore:
    backend = 'numpy'

    def __init__(self, embedding_signature, dim):
        self.embedding_signature = embedding_signature
        self.dim = dim
        self._lock = threading.Lock()
        self._snapshot = None

    def _scope(self, query):
        return query.join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id).filter(
            KnowledgeChunk.embedding_model == self.embedding_signature,
            KnowledgeDocument.status == 'ready',
            KnowledgeDocument.is_active.is_(True))

    def _signature(self):
        # Cheap change detection that also sees writes from the CLI running in another process.
        row = self._scope(db.session.query(
            func.count(KnowledgeChunk.id), func.max(KnowledgeChunk.id),
            func.max(KnowledgeDocument.updated_at))).one()
        return tuple(str(value) for value in row)

    def invalidate(self):
        with self._lock:
            self._snapshot = None

    def _build_index(self, matrix):
        return None

    def _current(self):
        signature = self._signature()
        snapshot = self._snapshot
        if snapshot is not None and snapshot.signature == signature:
            return snapshot
        with self._lock:
            if self._snapshot is not None and self._snapshot.signature == signature:
                return self._snapshot
            rows = self._scope(db.session.query(
                KnowledgeChunk.id, KnowledgeChunk.document_id, KnowledgeDocument.category,
                KnowledgeChunk.embedding)).order_by(KnowledgeChunk.id).all()
            if rows:
                matrix = np.stack([np.frombuffer(row[3], dtype=np.float32) for row in rows])
            else:
                matrix = np.zeros((0, self.dim), dtype=np.float32)
            self._snapshot = _Snapshot(
                signature,
                np.asarray([row[0] for row in rows], dtype=np.int64),
                np.asarray([row[1] for row in rows], dtype=np.int64),
                np.asarray([row[2] for row in rows], dtype=object),
                matrix,
                self._build_index(matrix) if rows else None)
            return self._snapshot

    def size(self):
        return len(self._current().ids)

    def search(self, query_vector, top_k, categories=None, document_ids=None):
        snapshot = self._current()
        if not len(snapshot.ids):
            return []
        query = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        if query.shape[0] != snapshot.matrix.shape[1]:
            raise ValueError('查询向量维度与索引不一致，请重建知识库索引')
        mask = np.ones(len(snapshot.ids), dtype=bool)
        if categories:
            mask &= np.isin(snapshot.categories, list(categories))
        if document_ids:
            mask &= np.isin(snapshot.document_ids, list(document_ids))
        if not mask.any():
            return []
        if mask.all() and snapshot.index is not None:
            return self._search_index(snapshot, query, top_k)
        positions = np.flatnonzero(mask)
        scores = snapshot.matrix[positions] @ query
        k = min(top_k, len(positions))
        best = np.argpartition(-scores, k - 1)[:k]
        best = best[np.argsort(-scores[best], kind='stable')]
        return [VectorHit(int(snapshot.ids[positions[i]]), float(scores[i])) for i in best]

    def _search_index(self, snapshot, query, top_k):
        raise NotImplementedError


class FaissVectorStore(NumpyVectorStore):
    """Unfiltered queries go through FAISS (flat exact, or HNSW when RAG_FAISS_HNSW_M > 0);
    filtered queries fall back to exact search over the same matrix so filters never lose recall."""

    backend = 'faiss'

    def __init__(self, embedding_signature, dim, hnsw_m=0):
        try:
            import faiss
        except ImportError:
            raise RuntimeError('RAG_VECTOR_BACKEND=faiss 需要先安装 faiss-cpu') from None
        super().__init__(embedding_signature, dim)
        self._faiss = faiss
        self.hnsw_m = hnsw_m

    def _build_index(self, matrix):
        faiss = self._faiss
        if self.hnsw_m:
            index = faiss.IndexHNSWFlat(matrix.shape[1], self.hnsw_m, faiss.METRIC_INNER_PRODUCT)
        else:
            index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(np.ascontiguousarray(matrix))
        return index

    def _search_index(self, snapshot, query, top_k):
        k = min(top_k, len(snapshot.ids))
        scores, positions = snapshot.index.search(query.reshape(1, -1), k)
        return [VectorHit(int(snapshot.ids[p]), float(s)) for s, p in zip(scores[0], positions[0]) if p >= 0]


def build_store(settings, embedding_signature, dim):
    if settings.vector_backend == 'faiss':
        return FaissVectorStore(embedding_signature, dim, settings.faiss_hnsw_m)
    return NumpyVectorStore(embedding_signature, dim)
