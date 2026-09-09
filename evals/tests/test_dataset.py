from evals.dataset import load_dataset
from evals.rules import inspect_output


def test_all_acceptance_ids_and_unreviewed_examples():
    data = load_dataset()
    assert [c['id'] for c in data['cases']] == [f'F{i:02}' for i in range(1, 37)]
    assert all(c['checks'] and c['source'] for c in data['cases'])
    for case in data['cases']:
        if case['metrics']:
            assert {e['variant'] for e in case['examples']} >= {'positive', 'negative', 'boundary'}
            assert all(e['review_status'] == 'pending_human_review' for e in case['examples'])


def test_raw_and_validated_report_and_invalid_reference():
    case = next(c for c in load_dataset()['cases'] if c['id'] == 'F31')
    raw = {'dimensions': [{'key': 'posture', 'score': 99, 'reason': '很自信', 'event_ids': [999]}]}
    result = inspect_output(case, raw)
    assert result['raw_output'] == raw
    assert result['validated_output']['overall_score'] is None
    assert result['checks']['references_valid'] is False


def test_named_lin_and_student_parser():
    case = next(c for c in load_dataset()['cases'] if c['id'] == 'F22')
    raw = dict(case['examples'][0]['output'], student_id='ming')
    result = inspect_output(case, raw)
    assert result['checks']['named_student'] is False
    assert result['checks']['student_structure'] is True


def test_student_role_misconception_is_not_a_deterministic_math_failure():
    case = next(c for c in load_dataset()['cases'] if c['id'] == 'F07')
    result = inspect_output(case, case['examples'][0]['output'])
    assert all(result['checks'].values())
