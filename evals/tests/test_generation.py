import json
import httpx
import pytest
from evals.dataset import load_dataset
from evals.generation import generate_case, validate_generation_config
from test_classroom_base import app


def test_generation_rejects_non_test_provider(monkeypatch):
    monkeypatch.setenv('CLASSROOM_LLM_PROVIDER', 'deepseek')
    with pytest.raises(ValueError, match='openai_next'):
        validate_generation_config(1)
    with pytest.raises(ValueError, match='paid'):
        generate_case(load_dataset()['cases'][0])


def test_generation_uses_real_stream_parser_and_prompt(app, monkeypatch):
    from services import classroom_dialogue_stream as stream
    from services.classroom_runtime import STUDENT_SYSTEM
    case = load_dataset()['cases'][0]
    output = case['examples'][0]['output']
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fake')
    monkeypatch.setenv('AI_LLM_INPUT_CNY_PER_MILLION', '1')
    monkeypatch.setenv('AI_LLM_OUTPUT_CNY_PER_MILLION', '1')
    def handler(request):
        payload = json.loads(request.content)
        assert payload['stream'] is True
        assert payload['messages'][0]['content'] == STUDENT_SYSTEM
        chunks = [{'choices': [{'index': 0, 'delta': {'content': json.dumps(output, ensure_ascii=False)}, 'finish_reason': None}]},
                  {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                   'usage': {'prompt_tokens': 10, 'completion_tokens': 10}}]
        wire = ''.join('data: ' + json.dumps(c, ensure_ascii=False) + '\n\n' for c in chunks) + 'data: [DONE]\n\n'
        return httpx.Response(200, text=wire)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(stream.httpx, 'stream', client.stream)
    with app.app_context(), client:
        assert generate_case(case, paid=True) == output


def test_report_generation_reuses_prompt_and_payload(app, monkeypatch):
    from services import classroom_providers as providers
    from services.classroom_reports import REPORT_SYSTEM
    case = load_dataset()['cases'][16]
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fake')
    monkeypatch.setenv('AI_LLM_INPUT_CNY_PER_MILLION', '1')
    monkeypatch.setenv('AI_LLM_OUTPUT_CNY_PER_MILLION', '1')
    def handler(request):
        payload = json.loads(request.content)
        assert payload['messages'][0]['content'] == REPORT_SYSTEM
        assert json.loads(payload['messages'][1]['content'])['events'] == case['events']
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(case['examples'][0]['output'])}}]})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(providers.httpx, 'post', client.post)
    with app.app_context(), client:
        raw = generate_case(case, paid=True)
    from evals.rules import inspect_output
    assert inspect_output(case, raw)['validated_output']['coverage'] == '1/6'


def test_generate_records_uses_test_ledger_and_run_cap(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, select
    from classroom_models import CreditUsage
    from config import Config
    from evals.generation import generate_records
    from services import classroom_providers as providers
    for key, value in {'CLASSROOM_LLM_PROVIDER': 'openai_next', 'OPENAI_NEXT_TEST_API_KEY': 'test-only',
                       'OPENAI_NEXT_PRICING_CONFIRMED': 'true', 'OPENAI_NEXT_DIALOGUE_MODEL': 'deepseek-v4-flash',
                       'OPENAI_NEXT_DIALOGUE_INPUT_USD_PER_MILLION': '1',
                       'OPENAI_NEXT_DIALOGUE_OUTPUT_USD_PER_MILLION': '2'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('OPENAI_NEXT_BASE_URL', raising=False)
    url = 'sqlite:///' + (tmp_path / 'ledger.db').as_posix()
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', url)
    engine = create_engine(url)
    CreditUsage.__table__.create(engine)
    case = load_dataset()['cases'][16]
    def handler(request):
        assert request.headers['authorization'] == 'Bearer test-only'
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(case['examples'][0]['output'])}}],
                                        'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(providers.httpx, 'post', client.post)
    with client:
        records, cost = generate_records([case], tmp_path, 1, paid=True)
    assert 'generation_error' not in records[0]
    assert cost['spent_and_reserved'] == pytest.approx(0.00002)
    with engine.connect() as connection:
        rows = connection.execute(select(CreditUsage.__table__)).mappings().all()
        assert len(rows) == 1 and rows[0]['account'] == 'test' and rows[0]['session_id'] is None
    records, cost = generate_records([case, case], tmp_path, 0.00000001, paid=True)
    assert all('generation_error' in r for r in records)
    with engine.connect() as connection:
        assert len(connection.execute(select(CreditUsage.__table__)).all()) == 1
    engine.dispose()
