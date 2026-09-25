import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.judge import audit_eval_citations, citation_quote_valid, filter_dimension_kb_sources  # noqa: E402


def test_citation_quote_valid():
    hit = {'text': '教师提问后应留出三到五秒的候答时间，避免自问自答。'}
    assert citation_quote_valid(hit, '候答时间')
    assert not citation_quote_valid(hit, '完全不相关的条文')


def test_audit_eval_strips_bad_quotes():
    by_ref = {
        1: {'text': '候答时间应不少于三秒', 'ref': 1, 'chunk_id': 9, 'document': {'id': 1, 'title': 't', 'category': 'rubric'}},
    }
    results = [{
        'key': 'q',
        'label': '提问',
        'theory_status': 'grounded',
        'citations': [{'ref': 1, 'quote': '完全不相关的条文'}],
    }]
    out = audit_eval_citations(results, by_ref)
    assert out[0]['theory_status'] == 'insufficient_evidence'


def test_filter_dimension_kb_sources():
    theory = {'clarity': [{'id': 'kb:1'}], 'pace': [{'id': 'kb:2'}]}
    global_ids = {'kb:1', 'kb:2', 'fraction-equal'}
    kept = filter_dimension_kb_sources(['kb:2', 'kb:1', 'fraction-equal'], key='clarity',
                                       theory_by_dimension=theory, global_source_ids=global_ids)
    assert kept == ['kb:1', 'fraction-equal']
