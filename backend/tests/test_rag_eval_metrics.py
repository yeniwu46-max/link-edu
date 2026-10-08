"""Evaluation must fail closed when a result has no valid source or violates a gate."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.rag_eval_graph import acceptance_checks, path_is_valid
from scripts.rag_eval_retrieval import evaluate_cases, summarize


def evidence_fixture():
    sources = {
        1: {'eligible': True, 'document_id': 10, 'category': 'theory', 'text': '平均分是基础',
            'graph': {'entities': [{'id': 'a'}, {'id': 'b'}],
                      'relations': [{'from': 'a', 'to': 'b', 'type': 'depends_on', 'cue': '平均分是基础'}]}},
        2: {'eligible': True, 'document_id': 20, 'category': 'theory', 'text': '知识点 b',
            'graph': {'entities': [{'id': 'b'}], 'relations': []}},
    }
    path = {'target_chunk_id': 2, 'entities': [{'id': 'a'}, {'id': 'b'}], 'depth': 1,
            'source_chunk_ids': [1],
            'relations': [{'type': 'depends_on', 'reverse': False, 'cue': '平均分是基础', 'source_chunk_id': 1}]}
    return {'chunk_id': 2}, path, sources


def test_path_requires_matching_edge_and_eligible_sources():
    hit, path, sources = evidence_fixture()
    assert path_is_valid(hit, path, sources)
    for change in ('missing', 'expired', 'wrong_relation', 'wrong_direction', 'wrong_target', 'cycle'):
        candidate, lookup = deepcopy(path), deepcopy(sources)
        if change == 'missing':
            del lookup[1]
        elif change == 'expired':
            lookup[1]['eligible'] = False
        elif change == 'wrong_relation':
            candidate['relations'][0]['type'] = 'unrelated'
        elif change == 'wrong_direction':
            candidate['relations'][0]['reverse'] = True
        elif change == 'wrong_target':
            candidate['target_chunk_id'] = 3
        else:
            candidate['entities'][1]['id'] = 'a'
        assert not path_is_valid(hit, candidate, lookup), change
    assert not path_is_valid(hit, path, sources, categories=['case'])
    assert not path_is_valid(hit, path, sources, document_ids=[20])


@pytest.mark.parametrize('failure', ['no_paths', 'invalid_path', 'irrelevant', 'data_error', 'fallback', 'regression'])
def test_acceptance_does_not_hide_failed_cases(failure):
    options = dict(min_recall=.8, max_regression=.02, min_pass_rate=.8, path_count=1,
                   valid_path_count=1, no_answer_ok=True, data_errors=[], errors=[])
    baseline = {'pass_rate': 1, 'direct_pass_rate': 1}
    graph = dict(baseline)
    if failure == 'no_paths':
        options.update(path_count=0, valid_path_count=0)
    elif failure == 'invalid_path':
        options['valid_path_count'] = 0
    elif failure == 'irrelevant':
        options['no_answer_ok'] = False
    elif failure == 'data_error':
        options['data_errors'] = ['no such source']
    elif failure == 'fallback':
        options['errors'] = ['graph failed']
    else:
        graph['direct_pass_rate'] = .95
    checks = acceptance_checks({'pass_rate': 1}, baseline, graph, **options)
    assert not all(checks.values())


def test_same_rank_cutoff_for_direct_comparison_and_no_empty_success():
    class KB:
        def retrieve(self, _query, **options):
            assert options['graph'] in (False, True)
            hits = [{'document': {'title': str(i)}, 'relevant': True} for i in range(1, 6)]
            return {'hits': hits, 'retrieval': {'relevant_count': 5}}

    cases = [{'query': 'test', 'check_top': 3, 'expect': {'title_contains': '4'}}]
    off, on = (evaluate_cases(KB(), cases, graph=enabled) for enabled in (False, True))
    assert not off[0]['passed'] and not on[0]['passed']
    assert summarize(off)['mrr_at_5'] == .25
    assert summarize([])['pass_rate'] == 0
