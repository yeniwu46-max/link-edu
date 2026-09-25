"""Per-dimension RAG theory evidence for classroom AI reports (six LINK dimensions)."""
from services.classroom_knowledge import search
from services.classroom_reports import DIMENSIONS, RAG_REPORT_QUERY


def _dimension_indicators():
    from services.classroom_reports import REVIEW_DIMENSION_FOCUS
    return [
        {'key': key, 'label': DIMENSIONS[key], 'description': REVIEW_DIMENSION_FOCUS.get(key, '')}
        for key in DIMENSIONS
    ]


def hit_to_report_source(hit):
    document = hit['document']
    return {
        'id': f"kb:{hit['chunk_id']}",
        'chunk_id': hit['chunk_id'],
        'document_id': document['id'],
        'title': document['title'],
        'text': hit['text'],
        'type': document.get('category_label') or document.get('category'),
        'source': document.get('source') or document['title'],
        'location': hit.get('section') or '',
        'relevance': hit.get('similarity'),
    }


def gather_classroom_theory_evidence(*, scene=None, top_k=3, legacy_query=RAG_REPORT_QUERY):
    """Legacy BM25 cards + per-dimension RAG pool. Returns (sources, theory_by_dimension)."""
    sources = list(search(legacy_query))
    seen = {item['id'] for item in sources}
    theory_by_dimension = {key: [] for key in DIMENSIONS}
    try:
        from rag.service import get_kb
        kb = get_kb()
        if not kb.settings.enabled:
            return sources, theory_by_dimension
        pool, refs = kb.evidence_for_indicators(_dimension_indicators(), scene=scene, top_k=top_k)
        by_ref = {hit['ref']: hit for hit in pool}
        for key in DIMENSIONS:
            dim_list = []
            for ref in refs.get(key) or []:
                hit = by_ref.get(ref)
                if hit is None:
                    continue
                src = hit_to_report_source(hit)
                dim_list.append(src)
                if src['id'] not in seen:
                    sources.append(src)
                    seen.add(src['id'])
            theory_by_dimension[key] = dim_list
    except Exception:
        pass
    return sources, theory_by_dimension
