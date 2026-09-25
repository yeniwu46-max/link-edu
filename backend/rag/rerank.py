"""Rerank fused candidates (default: bi-encoder rescore with existing embedder)."""
import numpy as np


def rerank_hits(query, hits, embedder, *, top_k):
    """hits: list of dicts with chunk_id, text, document; mutates similarity on copy."""
    if not hits or top_k <= 0:
        return hits[:top_k]
    k = min(len(hits), max(top_k, 1))
    texts = []
    for hit in hits:
        title = hit['document']['title']
        section = hit.get('section') or ''
        parent = (hit.get('extra') or {}).get('parent_summary') or ''
        body = hit['text'][:1200]
        texts.append('\n'.join(p for p in (title, section, parent, body) if p))
    qv = embedder.embed_query(query)
    dv = embedder.embed_documents(texts)
    scores = (dv @ qv).astype(float)
    order = np.argsort(-scores)[:k]
    out = []
    for i in order:
        item = dict(hits[int(i)])
        item['similarity'] = round(float(scores[int(i)]), 4)
        item['rerank_score'] = item['similarity']
        out.append(item)
    return out
