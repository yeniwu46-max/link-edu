import json
import pytest
from evals.dataset import load_dataset
from evals.runner import compare_runs, load_records, run, summarize


def test_comparison_requires_matching_versions_and_preserves_errors():
    old = {'dataset_hash': 'a', 'rules_hash': 'b', 'judge_model': 'j',
           'results': [{'case_id': 'F01', 'variant': 'positive', 'stage': 'raw', 'metric': 'role', 'status': 'pass'}]}
    new = {**old, 'results': [{**old['results'][0], 'status': 'error'}]}
    result = compare_runs(new, old)
    assert result['comparable'] and result['changes'][0]['after'] == 'error'
    assert not compare_runs({**new, 'dataset_hash': 'c'}, old)['comparable']
    assert not compare_runs({**new, 'rules_hash': 'c'}, old)['comparable']


def test_summary_denominators_do_not_hide_errors_or_manual():
    summary = summarize([{'status': s} for s in ('pass', 'fail', 'error', 'not_evaluated', 'not_applicable')])
    assert summary['total'] == 5 and summary['judged'] == 2
    assert summary['pass_rate'] == 0.5 and summary['error'] == 1


def test_replay_rejects_unknown_and_duplicate_cases(tmp_path):
    data = load_dataset()
    path = tmp_path / 'replay.json'
    for records in ([{'case_id': 'F99', 'output': {}}],
                    [{'case_id': 'F01', 'variant': 'x', 'output': {}}] * 2):
        path.write_text(json.dumps({'dataset_hash': data['hash'], 'provenance': 'synthetic', 'records': records}), encoding='utf-8')
        with pytest.raises(ValueError):
            load_records(path, data)


def test_default_replay_does_not_call_judge_and_retains_raw(tmp_path):
    result = run('replay', output_root=tmp_path, case_ids=['F31'])
    assert result['judge_model'] is None
    assert any(r['status'] == 'not_evaluated' for r in result['results'])
    assert result['records'][1]['raw_output'] != result['records'][1]['validated_output']
    assert (tmp_path / result['run_id'] / 'summary.md').exists()
    assert all(r['case_id'] == 'F31' for r in result['results'])


def test_unpaid_replay_never_opens_database_or_network(tmp_path, monkeypatch):
    import socket
    from sqlalchemy.engine import Engine
    def blocked(*args, **kwargs):
        raise AssertionError('Unexpected external resource')
    monkeypatch.setattr(Engine, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    assert run('replay', output_root=tmp_path, case_ids=['F07'])['summary']['error'] == 0


def test_generate_requires_paid_before_any_app_or_network(tmp_path):
    with pytest.raises(ValueError, match='paid'):
        run('generate', output_root=tmp_path)


def test_paid_replay_mock_judge_end_to_end(tmp_path, monkeypatch):
    import httpx
    from evals import judge
    original = judge.JudgeModel
    def handler(request):
        request_json = json.loads(request.content)
        payload = json.loads(request_json['messages'][1]['content'])
        # Exercise two distinct metrics without a real model or paid request.
        verdict = {'passed': payload['criterion_id'] != 'leads_with_answer',
                   'reason': '先跑题，但后文回应了问题', 'event_ids': [1]}
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(verdict)}, 'finish_reason': 'stop'}],
                                        'usage': {'prompt_tokens': 20, 'completion_tokens': 10}})
    monkeypatch.setattr(judge, 'JudgeModel', lambda *a, **kw: original(*a, **kw, transport=httpx.MockTransport(handler)))
    for suffix, value in {'BASE_URL': 'https://judge.example/v1', 'MODEL': 'mock-model', 'API_KEY': 'never-real',
                          'INPUT_USD_PER_MILLION': '1', 'OUTPUT_USD_PER_MILLION': '2'}.items():
        monkeypatch.setenv('EVAL_JUDGE_' + suffix, value)
    result = run('replay', output_root=tmp_path, case_ids=['F01', 'F17'], paid=True, judge_limit=1)
    semantic = [r for r in result['results'] if r['stage'] in ('raw', 'validated')]
    assert any(r['metric'] == 'leads_with_answer' and r['status'] == 'fail' for r in semantic)
    assert all(r['status'] == 'pass' for r in semantic if r['metric'] == 'answered_anywhere' and r['case_id'] == 'F01')
    assert any(r['stage'] == 'validated' and r['status'] == 'pass' for r in semantic)
    assert result['summary']['error'] == 0 and result['costs']['judge']['spent_and_reserved'] > 0
    assert 'never-real' not in json.dumps(result)
