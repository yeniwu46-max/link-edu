"""Small in-process graph index over source-grounded relations stored in kb_chunks.extra."""
from datetime import datetime, timezone
import hashlib
import json
import threading
import time

from extensions import db
from rag.graph_meta import GRAPH_SCHEMA_VERSION
from rag.governance import document_is_expired
from rag.models import KnowledgeChunk, KnowledgeDocument


def _signature(rows, embedding_signature):
    # MySQL DATETIME may only retain seconds. Count/max(updated_at) misses rewrites
    # in the same second, including a graph-only rebuild from another process.
    digest = hashlib.sha256()
    for chunk_id, text, extra, document_id, category, valid_until in rows:
        digest.update(json.dumps([chunk_id, text, (extra or {}).get('graph'), document_id,
                                  category, valid_until], sort_keys=True, ensure_ascii=False,
                                 default=str).encode('utf-8'))
    return embedding_signature, datetime.now(timezone.utc).date().isoformat(), digest.hexdigest()


class KnowledgeGraphIndex:
    """Build a cached entity/edge map and expand query/lexical seeds by at most two edges."""

    def __init__(self, embedding_signature, max_depth=2, max_expansions=32):
        self.embedding_signature = embedding_signature
        self.max_depth = max(1, min(int(max_depth), 3))
        self.max_expansions = max(1, min(int(max_expansions), 128))
        self._lock = threading.Lock()
        self._snapshot = None

    def invalidate(self):
        with self._lock:
            self._snapshot = None

    def _current(self):
        # Read only graph inputs; embeddings stay in the existing vector cache.
        rows = (db.session.query(KnowledgeChunk.id, KnowledgeChunk.text, KnowledgeChunk.extra,
                                 KnowledgeDocument.id, KnowledgeDocument.category,
                                 KnowledgeDocument.valid_until)
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .filter(KnowledgeDocument.status == 'ready', KnowledgeDocument.is_active.is_(True),
                        KnowledgeChunk.embedding_model == self.embedding_signature)
                .order_by(KnowledgeChunk.id).all())
        signature = _signature(rows, self.embedding_signature)
        if self._snapshot is not None and self._snapshot['signature'] == signature:
            return self._snapshot
        with self._lock:
            if self._snapshot is not None and self._snapshot['signature'] == signature:
                return self._snapshot
            chunks, entities, entity_chunks, aliases, adjacency = {}, {}, {}, {}, {}
            edge_count = 0
            for chunk_id, text, extra, document_id, category, valid_until in rows:
                document = type('GraphDocument', (), {'valid_until': valid_until})()
                if document_is_expired(document):
                    continue
                chunks[chunk_id] = {'document_id': document_id, 'category': category, 'text': text}
                graph = (extra or {}).get('graph') or {}
                chunk_entities = set()
                for entity in graph.get('entities', []):
                    entity_id = entity.get('id')
                    if not entity_id:
                        continue
                    entities.setdefault(entity_id, {key: entity.get(key) for key in ('id', 'label', 'kind')})
                    chunk_entities.add(entity_id)
                    entity_chunks.setdefault(entity_id, set()).add(chunk_id)
                    for alias in [entity.get('label'), *(entity.get('aliases') or [])]:
                        if alias and len(str(alias).strip()) >= 2:
                            aliases.setdefault(str(alias).casefold(), set()).add(entity_id)
                for relation in graph.get('relations', []):
                    source, target, kind = relation.get('from'), relation.get('to'), relation.get('type')
                    cue = relation.get('cue')
                    if (kind in ('contains', 'tagged') or source not in chunk_entities or target not in chunk_entities or not kind or not cue
                            or str(cue) not in text):
                        continue
                    edge = {'from': source, 'to': target, 'type': str(kind),
                            'evidence_chunk_id': chunk_id, 'cue': str(cue)}
                    adjacency.setdefault(source, []).append((target, edge, False))
                    adjacency.setdefault(target, []).append((source, edge, True))
                    edge_count += 1
            self._snapshot = {
                'signature': signature, 'chunks': chunks, 'entities': entities,
                'entity_chunks': entity_chunks, 'aliases': aliases, 'adjacency': adjacency,
                'entity_count': len(entities), 'edge_count': edge_count,
            }
            return self._snapshot

    @staticmethod
    def _allowed(chunk, categories, document_ids):
        return (chunk is not None
                and (not categories or chunk['category'] in categories)
                and (not document_ids or chunk['document_id'] in document_ids))

    def search(self, query, seed_chunk_ids=(), *, top_k=20, categories=None, document_ids=None):
        started = time.perf_counter()
        graph = self._current()
        seeds = set()
        lowered = str(query or '').casefold()
        for alias, entity_ids in graph['aliases'].items():
            if alias in lowered:
                seeds.update(entity_ids)
        for chunk_id in seed_chunk_ids:
            chunk = graph['chunks'].get(chunk_id)
            if not self._allowed(chunk, categories, document_ids):
                continue
            for entity_id, ids in graph['entity_chunks'].items():
                if chunk_id in ids:
                    seeds.add(entity_id)

        paths_by_chunk = {}
        queue = [(entity_id, [entity_id], [], set([entity_id])) for entity_id in sorted(seeds)]
        expansions = 0
        cursor = 0
        while cursor < len(queue) and expansions < self.max_expansions:
            current, entity_path, edge_path, visited = queue[cursor]
            cursor += 1
            depth = len(edge_path)
            if depth >= self.max_depth:
                continue
            for target, edge, reverse in graph['adjacency'].get(current, []):
                evidence_id = edge['evidence_chunk_id']
                evidence = graph['chunks'].get(evidence_id)
                if target in visited or not self._allowed(evidence, categories, document_ids):
                    continue
                expansions += 1
                next_entities = [*entity_path, target]
                next_edges = [*edge_path, {**edge, 'reverse': reverse}]
                candidate_ids = {evidence_id}
                candidate_ids.update(graph['entity_chunks'].get(target, set()))
                for candidate_id in candidate_ids:
                    candidate = graph['chunks'].get(candidate_id)
                    if not self._allowed(candidate, categories, document_ids):
                        continue
                    path = {
                        'target_chunk_id': candidate_id,
                        'entities': [{'id': node_id, 'label': graph['entities'].get(node_id, {}).get('label')}
                                     for node_id in next_entities],
                        'relations': [{'type': item['type'], 'reverse': item['reverse'], 'cue': item['cue'],
                                       'source_chunk_id': item['evidence_chunk_id']}
                                      for item in next_edges],
                        'source_chunk_ids': sorted({item['evidence_chunk_id'] for item in next_edges}),
                        'depth': len(next_edges),
                    }
                    current_paths = paths_by_chunk.setdefault(candidate_id, [])
                    if path not in current_paths:
                        current_paths.append(path)
                queue.append((target, next_entities, next_edges, visited | {target}))
                if expansions >= self.max_expansions:
                    break

        ranked = sorted(paths_by_chunk, key=lambda chunk_id: (
            min(path['depth'] for path in paths_by_chunk[chunk_id]),
            -len(paths_by_chunk[chunk_id]), chunk_id))[:max(1, int(top_k))]
        return {
            'ranked': [(chunk_id, 1.0 / min(path['depth'] for path in paths_by_chunk[chunk_id]))
                       for chunk_id in ranked],
            'paths': {chunk_id: paths_by_chunk[chunk_id][:3] for chunk_id in ranked},
            'diagnostics': {
                'seed_entity_count': len(seeds), 'expanded_entity_count': expansions,
                'candidate_count': len(paths_by_chunk),
                'elapsed_ms': round((time.perf_counter() - started) * 1000, 1),
            },
        }

    def stats(self):
        graph = self._snapshot
        return {
            'initialized': graph is not None,
            'entity_count': graph['entity_count'] if graph else None,
            'relation_count': graph['edge_count'] if graph else None,
            'indexed_chunks': len(graph['chunks']) if graph else None,
            'schema_version': GRAPH_SCHEMA_VERSION,
        }
