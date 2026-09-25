import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from evals.rules import inspect_output  # noqa: E402


def test_no_score_without_events_rule():
    case = {
        'kind': 'report',
        'events': [{'id': 1, 'type': 'transcript', 'at_ms': 0, 'data': {}}],
        'references': [{'id': 'fraction-equal', 'title': 't'}],
    }
    raw = {'dimensions': [{'key': 'clarity', 'score': 88, 'reason': '很好', 'event_ids': [], 'source_ids': ['fraction-equal']}]}
    result = inspect_output(case, raw)
    assert result['checks']['no_score_without_events'] is False


def test_kb_refs_match_dimension_when_theory_provided():
    case = {
        'kind': 'report',
        'events': [{'id': 1, 'type': 'transcript', 'at_ms': 0, 'data': {}}],
        'references': [{'id': 'kb:1'}, {'id': 'kb:2'}],
        'theory_by_dimension': {'clarity': [{'id': 'kb:1'}]},
    }
    bad = {'dimensions': [{'key': 'clarity', 'score': None, 'event_ids': [1], 'source_ids': ['kb:2']}]}
    good = {'dimensions': [{'key': 'clarity', 'score': None, 'event_ids': [1], 'source_ids': ['kb:1']}]}
    assert inspect_output(case, bad)['checks']['kb_refs_match_dimension'] is False
    assert inspect_output(case, good)['checks']['kb_refs_match_dimension'] is True
