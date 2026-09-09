import asyncio
import json
import httpx
import pytest
from pydantic import ValidationError
from evals.judge import Budget, BudgetExceeded, JudgeConfig, JudgeModel, Verdict, judge_case
from evals.dataset import load_dataset


def config():
    return JudgeConfig('https://judge.example/v1', 'separate-model', 'private-key', 1, 2)


def response(content=None, usage=True, status=200):
    body = {'choices': [{'message': {'content': content or json.dumps(
        {'passed': True, 'reason': '证据支持', 'event_ids': [1]})}, 'finish_reason': 'stop'}]}
    if usage:
        body['usage'] = {'prompt_tokens': 10, 'completion_tokens': 5}
    return httpx.Response(status, json=body)


def test_paid_gate_and_no_default_provider():
    with pytest.raises(ValueError, match='paid'):
        JudgeModel(config(), Budget(1), paid=False)
    with pytest.raises(ValueError):
        JudgeConfig.from_env({})
    with pytest.raises(ValueError):
        JudgeConfig('http://judge.example/v1', 'm', 'k', 1, 1)


@pytest.mark.parametrize('bad', [True, -1, float('nan'), float('inf'), 0])
def test_invalid_budget(bad):
    with pytest.raises(ValueError):
        Budget(bad)


def test_strict_verdict():
    for bad in ('true', 1, None):
        with pytest.raises(ValidationError):
            Verdict(passed=bad, reason='reason', event_ids=[])
    with pytest.raises(ValidationError):
        Verdict(passed=True, reason='reason', event_ids=[True])


def test_budget_reserves_settles_and_retains_unknown():
    budget = Budget(0.01)
    model = JudgeModel(config(), budget, paid=True, transport=httpx.MockTransport(lambda r: response()))
    assert model.generate('text', Verdict).passed is True
    assert budget.total == pytest.approx(0.00002)
    model = JudgeModel(config(), budget, paid=True, transport=httpx.MockTransport(lambda r: response(usage=False)))
    assert asyncio.run(model.a_generate('text', Verdict)).passed
    assert budget.entries[-1]['state'] == 'reserved'
    with pytest.raises(BudgetExceeded):
        budget.reserve(1)
    with pytest.raises(BudgetExceeded):
        budget.reserve(0.000001)  # Once stopped, smaller later calls must not sneak through.


@pytest.mark.parametrize('kind', ['malformed', 'string_bool', 'duplicate', 'reference', 'timeout', 'rate_limit'])
def test_evaluator_failure_is_error_not_fail(kind):
    def handler(request):
        if kind == 'timeout':
            raise httpx.ReadTimeout('secret-body', request=request)
        if kind == 'rate_limit':
            return response(status=429)
        content = {'malformed': '{', 'string_bool': '{"passed":"true","reason":"r","event_ids":[]}',
                   'duplicate': '{"passed":false,"passed":true,"reason":"r","event_ids":[]}',
                   'reference': '{"passed":true,"reason":"r","event_ids":[999]}'}[kind]
        return response(content)
    model = JudgeModel(config(), Budget(1), paid=True, transport=httpx.MockTransport(handler))
    case = load_dataset()['cases'][0]
    rows = judge_case(case, case['examples'][0]['output'], model)
    assert all(row['status'] == 'error' for row in rows if row['metric'] in case['metrics'])
    assert all(row['status'] == 'not_applicable' for row in rows if row['metric'] not in case['metrics'])
    assert 'secret-body' not in json.dumps(rows)


def test_deepeval_metric_path_and_inapplicable():
    model = JudgeModel(config(), Budget(1), paid=True, transport=httpx.MockTransport(lambda r: response()))
    case = load_dataset()['cases'][6]
    rows = judge_case(case, case['examples'][0]['output'], model)
    assert all(r['status'] == 'pass' for r in rows if r['metric'] in case['metrics'])
    assert next(r for r in rows if r['metric'] == 'teacher_correction')['status'] == 'not_applicable'
