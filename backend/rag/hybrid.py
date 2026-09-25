"""BM25 over indexed kb_chunks + RRF fusion with vector hits."""
import logging
import threading

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import func

from extensions import db
from rag.models import KnowledgeChunk, KnowledgeDocument

jieba.setLogLevel(logging.WARNING)


def _tokenize(text):
    return [t for t in jieba.cut(text) if t.strip()]


class ChunkBM25Index:
    """Process-local BM25 over active chunks (rebuilt when chunk signature changes)."""

    def __init__(self, embedding_signature):
        self.embedding_signature = embedding_signature
        self._lock = threading.Lock()
        self._snapshot = None

    def _signature(self):
        row = (db.session.query(func.count(KnowledgeChunk.id), func.max(KnowledgeChunk.id),
                                func.max(KnowledgeDocument.updated_at))
               .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
               .filter(KnowledgeChunk.embedding_model == self.embedding_signature,
                       KnowledgeDocument.status == 'ready',
                       KnowledgeDocument.is_active.is_(True)).one())
        return tuple(str(v) for v in row)

    def invalidate(self):
        with self._lock:
            self._snapshot = None

    def _load(self):
        signature = self._signature()
        if self._snapshot is not None and self._snapshot[0] == signature:
            return self._snapshot[1]
        with self._lock:
            if self._snapshot is not None and self._snapshot[0] == signature:
                return self._snapshot[1]
            rows = (db.session.query(KnowledgeChunk.id, KnowledgeDocument.title, KnowledgeChunk.text,
                                     KnowledgeChunk.heading_path)
                    .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                    .filter(KnowledgeChunk.embedding_model == self.embedding_signature,
                            KnowledgeDocument.status == 'ready',
                            KnowledgeDocument.is_active.is_(True))
                    .order_by(KnowledgeChunk.id).all())
            if not rows:
                payload = {'ids': [], 'bm25': None}
            else:
                corpus = []
                for _cid, title, text, path in rows:
                    section = ' '.join(path or [])
                    corpus.append(_tokenize(f'{title} {section} {text}'))
                payload = {'ids': [r[0] for r in rows], 'bm25': BM25Okapi(corpus)}
            self._snapshot = (signature, payload)
            return payload

    def search(self, query, top_k, *, categories=None, document_ids=None):
        payload = self._load()
        if not payload['ids'] or payload['bm25'] is None:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scores = payload['bm25'].get_scores(q_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        hits = []
        id_set = set(payload['ids'])
        chunk_meta = {}
        if categories or document_ids:
            q = (db.session.query(KnowledgeChunk.id, KnowledgeDocument.category, KnowledgeChunk.document_id)
                 .join(KnowledgeDocument).filter(KnowledgeChunk.id.in_(payload['ids'])))
            chunk_meta = {row[0]: (row[1], row[2]) for row in q}
        for idx, score in ranked:
            if score <= 0:
                break
            chunk_id = payload['ids'][idx]
            if categories or document_ids:
                meta = chunk_meta.get(chunk_id)
                if meta is None:
                    continue
                if categories and meta[0] not in categories:
                    continue
                if document_ids and meta[1] not in document_ids:
                    continue
            hits.append((chunk_id, float(score)))
            if len(hits) >= top_k:
                break
        return hits


def rrf_merge(*ranked_lists, chunk_ids_key=0, k=60):
    """Reciprocal Rank Fusion. Each list: iterable of (chunk_id, score)."""
    scores = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            chunk_id = item[0] if isinstance(item, (tuple, list)) else item
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
