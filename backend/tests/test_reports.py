from services.classroom_reports import validate_report


def test_missing_or_fabricated_evidence_not_scored():
    result = validate_report({'dimensions': [{'key': 'clarity', 'score': 99, 'event_ids': [999]}]}, [], [])
    assert result['overall_score'] is None
    assert result['coverage'] == '0/6'


def test_only_observed_dimensions_aggregate():
    raw = {'dimensions': [{'key': 'clarity', 'score': 80, 'event_ids': [1]},
                           {'key': 'posture', 'score': 90, 'event_ids': [1]}]}
    result = validate_report(raw, [{'id': 1, 'type': 'transcript'}], [])
    assert result['overall_score'] == 80
    assert result['coverage'] == '1/6'
