"""Rule checks and optional LLM-as-a-Judge for grounded answers and lesson evaluation."""
import re

from rag.settings import INSUFFICIENT_MESSAGE

_QUOTE = re.compile(r'[\s，。；、：""\'\'\(\)（）\[\]【】…·\-—]+')


def normalize_quote(text):
    return _QUOTE.sub('', (text or '').strip().lower())


def citation_quote_valid(hit, quote, *, min_overlap=12):
    """Heuristic: cited quote should appear in chunk body (after normalization)."""
    body = normalize_quote(hit.get('text') or '')
    snippet = normalize_quote(quote or '')
    if not snippet:
        return True
    if len(snippet) < 6:
        return snippet in body
    return snippet in body or body.find(snippet[:min_overlap]) >= 0


def audit_eval_citations(results, by_ref):
    """Drop theory claims when refs are invalid or quotes do not match chunk text."""
    audited = []
    for item in results:
        row = dict(item)
        citations = []
        valid_refs = []
        for cite in row.get('citations') or []:
            ref = cite.get('ref')
            hit = by_ref.get(ref)
            if hit is None:
                continue
            quote = cite.get('quote') or ''
            if not citation_quote_valid(hit, quote):
                continue
            valid_refs.append(ref)
            citations.append(cite)
        grounded = bool(valid_refs)
        row['citations'] = citations
        row['theory_status'] = 'grounded' if grounded else 'insufficient_evidence'
        row['theory_basis'] = None if grounded else INSUFFICIENT_MESSAGE
        if not grounded:
            row['judgement'] = row.get('judgement') or '证据不足'
        audited.append(row)
    return audited


JUDGE_THEORY_SYSTEM = (
    '你是教学评价质检员。根据 classroom_evidence、judgement 与 citations（知识库片段摘要），'
    '判断 judgement 中的理论依据是否真正来自 citations，且与 classroom_evidence 相关。'
    '只返回 JSON：{"grounded": true/false, "reason": "一句中文说明"}。'
    '若 citations 为空、与指标无关，或 judgement 使用了片段外的常识，grounded 必须为 false。'
)


def judge_theory_support(llm, *, indicator, classroom_evidence, judgement, citations, max_tokens=400):
    if not citations or not (judgement or '').strip():
        return False, '无可用引用'
    payload = {
        'indicator': indicator,
        'classroom_evidence': classroom_evidence,
        'judgement': judgement,
        'citations': citations,
    }
    try:
        out = llm.complete_json(JUDGE_THEORY_SYSTEM, payload, max_tokens)
    except Exception as error:
        return False, str(error)[:120]
    if not isinstance(out, dict):
        return False, '质检返回无效'
    grounded = out.get('grounded') is True
    reason = str(out.get('reason') or '').strip()[:200]
    return grounded, reason


def judge_eval_results(llm, results, *, enabled=True):
    if not enabled or llm is None:
        return results
    judged = []
    for row in results:
        item = dict(row)
        if item.get('theory_status') != 'grounded':
            judged.append(item)
            continue
        ok, reason = judge_theory_support(
            llm,
            indicator={'key': item['key'], 'label': item['label']},
            classroom_evidence=item.get('classroom_evidence') or '',
            judgement=item.get('judgement') or '',
            citations=item.get('citations') or [],
        )
        if not ok:
            item['theory_status'] = 'insufficient_evidence'
            item['theory_basis'] = INSUFFICIENT_MESSAGE
            item['citations'] = []
            item['judge_note'] = reason
        judged.append(item)
    return judged


def filter_dimension_kb_sources(source_ids, *, key, theory_by_dimension, global_source_ids):
    """Remove kb: refs that were not retrieved for this dimension (wrong citation)."""
    allowed_kb = {s['id'] for s in (theory_by_dimension or {}).get(key, []) if str(s.get('id', '')).startswith('kb:')}
    filtered = []
    for sid in source_ids or []:
        if not isinstance(sid, str):
            continue
        if sid not in global_source_ids:
            continue
        if sid.startswith('kb:') and allowed_kb and sid not in allowed_kb:
            continue
        filtered.append(sid)
    return filtered
