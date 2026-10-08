"""KnowledgeBase facade: the only entry point routes, CLI, and other LINK modules should call."""
import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from flask import current_app
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from extensions import db
from rag.chunking import Chunker
from rag.cleaning import clean_text
from rag.embeddings import EmbeddingError, build_embedder
from rag.generation import GenerationError, ProviderLLM, grounded_answer
from rag.graph_meta import build_graph_extra
from rag.graph_index import KnowledgeGraphIndex
from rag.governance import document_is_expired, log_audit
from rag.hybrid import ChunkBM25Index, rrf_merge
from rag.models import KnowledgeChunk, KnowledgeDocument
from rag.parent_chunks import section_summaries
from rag.parsing import ParseError, detect_file_type, parse_document
from rag.query_rewrite import expand_query, hyde_passage
from rag.rerank import rerank_hits
from rag.settings import CATEGORIES, load_settings
from rag.vector_store import build_store

MAX_QUERY_CHARS = 2000
logger = logging.getLogger(__name__)


class DuplicateDocument(ValueError):
    def __init__(self, document):
        super().__init__('该文件已在知识库中')
        self.document = document


def embedding_text(title, chunk, extra=None):
    """Title and section path are embedded with the body so short chunks keep their context."""
    extra = extra or {}
    parts = [title, chunk.section, extra.get('parent_summary'), chunk.text]
    return '\n'.join(part for part in parts if part)


def _document_brief(document):
    return {
        'id': document.id,
        'title': document.title,
        'category': document.category,
        'category_label': CATEGORIES.get(document.category, document.category),
        'file_type': document.file_type,
        'source': document.source,
    }


class KnowledgeBase:
    def __init__(self, settings, embedder=None, store=None, llm=None):
        self.settings = settings
        self.embedder = embedder or build_embedder(settings)
        self.store = store or build_store(settings, self.embedder.signature, self.embedder.dim)
        self.llm = llm or ProviderLLM()
        self.chunker = Chunker(settings.chunk_target_chars, settings.chunk_max_chars,
                               settings.chunk_overlap_chars, settings.chunk_min_chars)
        self._bm25 = ChunkBM25Index(self.embedder.signature)
        self._graph = KnowledgeGraphIndex(self.embedder.signature, settings.graph_max_depth,
                                          settings.graph_max_expansions)

    def _invalidate_indexes(self):
        self.store.invalidate()
        self._bm25.invalidate()
        self._graph.invalidate()

    # ---------- ingestion ----------

    def _prepare(self, data, file_type, title):
        parsed = parse_document(data, file_type)
        chunks = self.chunker.split(parsed.blocks)
        if not chunks:
            raise ParseError('文档中没有可入库的正文内容')
        if len(chunks) > self.settings.max_chunks_per_document:
            raise ParseError(f'文档切片数 {len(chunks)} 超过上限 {self.settings.max_chunks_per_document}，请拆分后上传')
        summaries = section_summaries(chunks)
        vectors = self.embedder.embed_documents([
            embedding_text(title, chunk, {'parent_summary': summaries.get(tuple(chunk.heading_path or []))})
            for chunk in chunks
        ])
        return parsed, chunks, vectors, summaries

    def _write_chunks(self, document, parsed, chunks, vectors, summaries=None):
        KnowledgeChunk.query.filter_by(document_id=document.id).delete(synchronize_session=False)
        signature = self.embedder.signature
        summaries = summaries or section_summaries(chunks)
        tags = document.tags or []
        for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors)):
            extra = {}
            if self.settings.parent_context_enabled:
                extra['parent_summary'] = summaries.get(tuple(chunk.heading_path or []))
            if self.settings.graph_meta_enabled:
                extra.update(build_graph_extra(document.title, chunk.heading_path, tags, chunk.text,
                                               document_id=document.id))
            db.session.add(KnowledgeChunk(
                document_id=document.id, ordinal=ordinal, kind=chunk.kind, text=chunk.text,
                heading_path=chunk.heading_path, page_start=chunk.page_start, page_end=chunk.page_end,
                char_count=len(chunk.text), content_hash=hashlib.sha256(chunk.text.encode('utf-8')).hexdigest(),
                embedding=vector.astype('float32').tobytes(), embedding_model=signature,
                embedding_dim=int(vector.shape[0]), extra=extra))
        document.page_count = parsed.page_count
        document.chunk_count = len(chunks)
        document.embedding_model = signature
        document.status = 'ready'
        document.error = None

    def _file_path(self, sha, file_type):
        folder = self.settings.storage_dir / 'files'
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f'{sha}.{file_type}'

    def ingest(self, data, filename, *, title=None, category='other', tags=(), source=None,
               description=None, user_id=None):
        file_type = detect_file_type(filename)
        if not data:
            raise ParseError('上传文件为空')
        if len(data) > self.settings.max_upload_bytes:
            raise ParseError(f'文件超过 {self.settings.max_upload_bytes // 1024 // 1024} MB 上限')
        if category not in CATEGORIES:
            raise ParseError('知识分类无效')
        sha = hashlib.sha256(data).hexdigest()
        document = KnowledgeDocument.query.filter_by(sha256=sha).first()
        if document is not None and document.status != 'failed':
            raise DuplicateDocument(document)
        path = self._file_path(sha, file_type)
        if not path.exists():
            path.write_bytes(data)
        name = Path(filename).name[:255]
        document = document or KnowledgeDocument(sha256=sha)
        document.title = (title or Path(name).stem or '未命名资料')[:200]
        document.filename = name
        document.file_type = file_type
        document.category = category
        document.tags = [str(t)[:32] for t in tags][:20]
        document.source = (source or None) and source[:255]
        document.description = description or None
        document.size_bytes = len(data)
        document.storage_path = str(path.relative_to(self.settings.storage_dir))
        document.uploaded_by = user_id
        document.status = 'processing'
        document.is_active = True
        try:
            prepared = self._prepare(data, file_type, document.title)
        except (ParseError, EmbeddingError) as error:
            document.status, document.error, document.chunk_count = 'failed', str(error)[:255], 0
            db.session.add(document)
            db.session.commit()
            error.document = document
            raise
        db.session.add(document)
        db.session.flush()
        self._write_chunks(document, *prepared)
        db.session.commit()
        log_audit(document.id, 'ingest_complete', actor_id=user_id, chunks=document.chunk_count)
        db.session.commit()
        self._invalidate_indexes()
        return document

    def create_processing_document(self, data, filename, *, title=None, category='other', tags=(), source=None,
                                   description=None, user_id=None, content_version='1', license_note=None,
                                   valid_until=None):
        file_type = detect_file_type(filename)
        if not data:
            raise ParseError('上传文件为空')
        if len(data) > self.settings.max_upload_bytes:
            raise ParseError(f'文件超过 {self.settings.max_upload_bytes // 1024 // 1024} MB 上限')
        if category not in CATEGORIES:
            raise ParseError('知识分类无效')
        sha = hashlib.sha256(data).hexdigest()
        document = KnowledgeDocument.query.filter_by(sha256=sha).first()
        if document is not None and document.status not in ('failed', 'processing'):
            raise DuplicateDocument(document)
        path = self._file_path(sha, file_type)
        if not path.exists():
            path.write_bytes(data)
        name = Path(filename).name[:255]
        document = document or KnowledgeDocument(sha256=sha)
        document.title = (title or Path(name).stem or '未命名资料')[:200]
        document.filename = name
        document.file_type = file_type
        document.category = category
        document.tags = [str(t)[:32] for t in tags][:20]
        document.source = (source or None) and source[:255]
        document.description = description or None
        document.size_bytes = len(data)
        document.storage_path = str(path.relative_to(self.settings.storage_dir))
        document.uploaded_by = user_id
        document.content_version = (content_version or '1')[:32]
        document.license_note = (license_note or None) and str(license_note)[:255]
        document.valid_until = (valid_until or None) and str(valid_until)[:10]
        document.status = 'processing'
        document.is_active = True
        document.error = None
        db.session.add(document)
        db.session.flush()
        log_audit(document.id, 'ingest_queued', actor_id=user_id)
        return document

    def finish_ingest(self, document_id, data):
        document = db.session.get(KnowledgeDocument, document_id)
        if document is None:
            raise ValueError('资料不存在')
        try:
            prepared = self._prepare(data, document.file_type, document.title)
        except (ParseError, EmbeddingError) as error:
            document.status, document.error, document.chunk_count = 'failed', str(error)[:255], 0
            db.session.commit()
            self._invalidate_indexes()
            raise
        self._write_chunks(document, *prepared)
        db.session.commit()
        log_audit(document.id, 'ingest_complete', actor_id=document.uploaded_by, chunks=document.chunk_count)
        db.session.commit()
        self._invalidate_indexes()
        return document

    def reindex(self, document):
        path = self.settings.storage_dir / document.storage_path
        if not path.exists():
            raise ParseError('原始文件已丢失，请删除后重新上传')
        try:
            prepared = self._prepare(path.read_bytes(), document.file_type, document.title)
        except (ParseError, EmbeddingError) as error:
            document.status, document.error = 'failed', str(error)[:255]
            db.session.commit()
            self._invalidate_indexes()
            raise
        self._write_chunks(document, *prepared)
        db.session.commit()
        self._invalidate_indexes()
        return document

    def stale_documents(self):
        return KnowledgeDocument.query.filter(
            KnowledgeDocument.status == 'ready',
            (KnowledgeDocument.embedding_model != self.embedder.signature)
            | KnowledgeDocument.embedding_model.is_(None)).all()

    def rebuild_graph_metadata(self):
        """Refresh graph JSON only; this does not parse files or call the embedding provider."""
        documents = KnowledgeDocument.query.filter_by(status='ready').order_by(KnowledgeDocument.id).all()
        updated = 0
        for document in documents:
            chunks = KnowledgeChunk.query.filter_by(document_id=document.id).order_by(KnowledgeChunk.ordinal)
            for chunk in chunks:
                extra = dict(chunk.extra or {})
                if self.settings.graph_meta_enabled:
                    extra.update(build_graph_extra(document.title, chunk.heading_path, document.tags, chunk.text,
                                                   document_id=document.id))
                else:
                    extra.pop('graph', None)
                chunk.extra = extra
                updated += 1
            document.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        self._invalidate_indexes()
        return {'documents': len(documents), 'chunks': updated}

    def delete(self, document):
        path = self.settings.storage_dir / document.storage_path
        doc_id = document.id
        log_audit(doc_id, 'delete', actor_id=None, title=document.title, sha256=document.sha256)
        KnowledgeChunk.query.filter_by(document_id=doc_id).delete(synchronize_session=False)
        db.session.delete(document)
        db.session.commit()
        self._invalidate_indexes()
        path.unlink(missing_ok=True)

    def _hit_from_chunk(self, chunk, score, *, vector_score=None, bm25_score=None):
        extra = chunk.extra or {}
        return {
            'ref': None,
            'chunk_id': chunk.id,
            'similarity': round(float(score), 4),
            'vector_score': round(float(vector_score), 4) if vector_score is not None else None,
            'bm25_score': round(float(bm25_score), 4) if bm25_score is not None else None,
            'relevant': False,
            'kind': chunk.kind,
            'text': chunk.text,
            'section': chunk.section,
            'heading_path': chunk.heading_path or [],
            'page_start': chunk.page_start,
            'page_end': chunk.page_end,
            'extra': {'parent_summary': extra.get('parent_summary'), 'graph': (extra.get('graph') or {})},
            'document': _document_brief(chunk.document),
        }

    # ---------- retrieval & generation ----------

    def retrieve(self, query, *, top_k=None, categories=None, document_ids=None, min_score=None,
                 hybrid=None, rerank=None, rewrite=None, graph=None):
        raw = clean_text(query)[:MAX_QUERY_CHARS]
        if not raw:
            raise ValueError('检索内容不能为空')
        mode = rewrite if rewrite is not None else self.settings.query_rewrite
        text = expand_query(raw, mode='off' if mode == 'off' else 'expand')
        embed_text = text
        if mode == 'hyde':
            hyp = hyde_passage(self.llm, raw)
            embed_text = hyp or text
        k = max(1, min(int(top_k or self.settings.top_k), self.settings.max_top_k))
        fetch_k = max(k, min(self.settings.fetch_k, self.settings.max_top_k))
        threshold = self.settings.min_score if min_score is None else float(min_score)
        use_hybrid = self.settings.hybrid_enabled if hybrid is None else bool(hybrid)
        use_rerank = self.settings.rerank_enabled if rerank is None else bool(rerank)
        use_graph = self.settings.graph_enabled if graph is None else bool(graph)
        started = time.perf_counter()

        vector = self.embedder.embed_query(embed_text)
        vector_found = self.store.search(vector, fetch_k, categories, document_ids)
        vector_scores = {h.chunk_id: h.score for h in vector_found}
        vector_ranked = [(h.chunk_id, h.score) for h in vector_found]

        if use_hybrid:
            bm25_ranked = self._bm25.search(text, fetch_k, categories=categories, document_ids=document_ids)
            bm25_scores = {cid: sc for cid, sc in bm25_ranked}
            fused = rrf_merge(vector_ranked, bm25_ranked, k=self.settings.rrf_k)
        else:
            bm25_scores = {}
            bm25_ranked = []

        graph_result = {'ranked': [], 'paths': {}, 'diagnostics': {
            'seed_entity_count': 0, 'expanded_entity_count': 0, 'candidate_count': 0, 'elapsed_ms': 0.0}}
        if use_graph:
            try:
                graph_result = self._graph.search(
                    raw, [chunk_id for chunk_id, _ in [*vector_ranked, *bm25_ranked]],
                    top_k=fetch_k, categories=categories, document_ids=document_ids)
            except Exception:
                logger.exception('RAG graph retrieval failed; falling back to vector/BM25 retrieval')
                graph_result['diagnostics'].update(error='graph_retrieval_failed', fallback=True)
        fused = rrf_merge(vector_ranked, bm25_ranked, graph_result['ranked'], k=self.settings.rrf_k)

        ordered_ids = [cid for cid, _ in fused[:fetch_k]]
        if not ordered_ids:
            return self._empty_retrieval(raw, text, embed_text, k, threshold, use_hybrid, use_rerank,
                                         started, use_graph, graph_result['diagnostics'])

        rows = {c.id: c for c in KnowledgeChunk.query.options(joinedload(KnowledgeChunk.document))
                .filter(KnowledgeChunk.id.in_(ordered_ids))}
        hits = []
        for chunk_id in ordered_ids:
            chunk = rows.get(chunk_id)
            if chunk is None or not chunk.document.is_active:
                continue
            if document_is_expired(chunk.document):
                continue
            rrf_score = next((s for cid, s in fused if cid == chunk_id), vector_scores.get(chunk_id, 0))
            vector_score = vector_scores.get(chunk_id)
            if vector_score is None:
                stored = np.frombuffer(chunk.embedding, dtype=np.float32)
                if stored.shape[0] == vector.shape[0]:
                    vector_score = float(stored @ vector)
            gate_score = vector_score if vector_score is not None else 0.0
            hit = self._hit_from_chunk(
                chunk, gate_score,
                vector_score=vector_score,
                bm25_score=bm25_scores.get(chunk_id),
            )
            hit['fusion_score'] = round(float(rrf_score), 6)
            hit['graph_paths'] = graph_result['paths'].get(chunk_id, [])
            hits.append(hit)

        if use_rerank and hits:
            hits = rerank_hits(raw, hits, self.embedder, top_k=k)
        else:
            hits = hits[:k]

        for rank, hit in enumerate(hits, start=1):
            hit['rank'] = rank
            hit['relevant'] = hit['similarity'] >= threshold

        return {
            'query': raw,
            'rewritten_query': text if text != raw else None,
            'hyde_passage': embed_text if mode == 'hyde' and embed_text != text else None,
            'hits': hits,
            'retrieval': {
                'top_k': k,
                'fetch_k': fetch_k,
                'min_score': threshold,
                'relevant_count': sum(1 for h in hits if h['relevant']),
                'hybrid': use_hybrid,
                'rerank': use_rerank,
                'query_rewrite': mode,
                'graph': {'enabled': use_graph, **graph_result['diagnostics']},
                'embedding_model': self.embedder.signature,
                'semantic_embedding': self.embedder.semantic,
                'vector_backend': self.store.backend,
                'elapsed_ms': round((time.perf_counter() - started) * 1000, 1),
            },
        }

    def _empty_retrieval(self, raw, text, embed_text, k, threshold, hybrid, rerank, started,
                         graph=False, graph_diagnostics=None):
        return {
            'query': raw,
            'rewritten_query': text if text != raw else None,
            'hyde_passage': embed_text if embed_text != text else None,
            'hits': [],
            'retrieval': {
                'top_k': k,
                'fetch_k': self.settings.fetch_k,
                'min_score': threshold,
                'relevant_count': 0,
                'hybrid': hybrid,
                'rerank': rerank,
                'query_rewrite': self.settings.query_rewrite,
                'graph': {'enabled': graph, **(graph_diagnostics or {})},
                'embedding_model': self.embedder.signature,
                'semantic_embedding': self.embedder.semantic,
                'vector_backend': self.store.backend,
                'elapsed_ms': round((time.perf_counter() - started) * 1000, 1),
            },
        }

    def query(self, question, *, generate=True, **filters):
        result = self.retrieve(question, **filters)
        relevant = [hit for hit in result['hits'] if hit['relevant']]
        for ref, hit in enumerate(relevant, start=1):
            hit['ref'] = ref
        if not generate:
            result.update(status='retrieval_only', grounded=False, answer=None, citations=[])
            return result
        try:
            result.update(grounded_answer(self.llm, result['query'], relevant, self.settings.answer_max_tokens))
        except GenerationError as error:
            result.update(status='generation_failed', grounded=False, answer=None, citations=[], message=str(error))
        return result

    def evidence_for_indicators(self, indicators, *, scene=None, top_k=3, categories=None):
        """Retrieve theory evidence per evaluation indicator. Refs are global and de-duplicated,
        so a caller can put `pool` into one prompt and point each indicator at its refs."""
        pool, by_chunk, refs = [], {}, {}
        for indicator in indicators:
            query = f"{indicator['label']}：{indicator.get('description') or ''}"
            if scene:
                query += f'（教学环节：{scene}）'
            refs[indicator['key']] = []
            for hit in self.retrieve(query, top_k=top_k, categories=categories)['hits']:
                if not hit['relevant']:
                    continue
                if hit['chunk_id'] not in by_chunk:
                    hit['ref'] = len(pool) + 1
                    by_chunk[hit['chunk_id']] = hit
                    pool.append(hit)
                refs[indicator['key']].append(by_chunk[hit['chunk_id']]['ref'])
        return pool, refs

    def stats(self):
        by_category = dict(db.session.query(KnowledgeDocument.category, func.count(KnowledgeDocument.id))
                           .filter(KnowledgeDocument.status == 'ready').group_by(KnowledgeDocument.category).all())
        by_status = dict(db.session.query(KnowledgeDocument.status, func.count(KnowledgeDocument.id))
                         .group_by(KnowledgeDocument.status).all())
        return {
            'documents_by_status': by_status,
            'documents_by_category': {key: by_category.get(key, 0) for key in CATEGORIES},
            'indexed_chunks': self.store.size(),
            'stale_documents': len(self.stale_documents()),
            'embedding': {'provider': self.embedder.provider, 'model': self.embedder.model,
                          'dim': self.embedder.dim, 'signature': self.embedder.signature,
                          'semantic': self.embedder.semantic},
            'vector_backend': self.store.backend,
            'min_score': self.settings.min_score,
            'top_k': self.settings.top_k,
            'fetch_k': self.settings.fetch_k,
            'hybrid_enabled': self.settings.hybrid_enabled,
            'rerank_enabled': self.settings.rerank_enabled,
            'query_rewrite': self.settings.query_rewrite,
            'graph': {'enabled': self.settings.graph_enabled, **self._graph.stats()},
        }


def report_reference_sources(query, *, top_k=5, categories=None):
    """Top-K RAG hits formatted for classroom_reports (source_ids like kb:<chunk_id>)."""
    try:
        kb = get_kb()
    except (ValueError, RuntimeError):
        return []
    if not kb.settings.enabled:
        return []
    try:
        payload = kb.retrieve(query, top_k=top_k, categories=categories)
    except Exception:
        return []
    refs = []
    for hit in payload['hits']:
        if not hit.get('relevant'):
            continue
        document = hit['document']
        refs.append({
            'id': f"kb:{hit['chunk_id']}",
            'title': document['title'],
            'text': hit['text'],
            'type': document.get('category_label') or document.get('category'),
            'source': document.get('source') or document['title'],
            'location': hit.get('section') or '',
            'relevance': hit['similarity'],
        })
    return refs


def get_kb():
    """Process-wide instance; tests may replace current_app.extensions['rag'] with their own."""
    kb = current_app.extensions.get('rag')
    if kb is None:
        kb = current_app.extensions['rag'] = KnowledgeBase(load_settings())
    return kb
