"""Retrieval evidence for legacy LINK dimensions and CLASS-S-aligned coaching domains."""
from services.classroom_knowledge import search
from services.classroom_reports import DIMENSIONS, RAG_REPORT_QUERY


def _dimension_indicators():
    from services.classroom_reports import REVIEW_DIMENSION_FOCUS
    return [
        {'key': key, 'label': DIMENSIONS[key], 'description': REVIEW_DIMENSION_FOCUS.get(key, '')}
        for key in DIMENSIONS
    ]


def _coaching_domain_indicators():
    return [
        {'key': 'emotional_support', 'label': '情感支持',
         'description': '课堂中的尊重、教师对学习者信号的回应、接纳学习者观点；必须基于可听见或可见的互动证据。'},
        {'key': 'classroom_organization', 'label': '课堂组织',
         'description': '课堂流程、活动转换、时间使用与教学形式；结合转写、视频和课堂事件，不从单一动作推断质量。'},
        {'key': 'instructional_support', 'label': '教学支持',
         'description': '概念理解、分析探究、反馈质量与教学对话；依据课堂原话和可核验的学习者回应。'},
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
    indicators = _dimension_indicators() + _coaching_domain_indicators()
    theory_by_dimension = {item['key']: [] for item in indicators}
    try:
        from rag.service import get_kb
        kb = get_kb()
        if not kb.settings.enabled:
            return sources, theory_by_dimension
        pool, refs = kb.evidence_for_indicators(indicators, scene=scene, top_k=top_k)
        by_ref = {hit['ref']: hit for hit in pool}
        for indicator in indicators:
            key = indicator['key']
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
