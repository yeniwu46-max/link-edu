import os
import subprocess
import sys
from pathlib import Path
import pytest
from sqlalchemy import select
from test_classroom_base import app
from extensions import db
from classroom_models import CreditUsage
from services import classroom_credits as credits
from services import classroom_providers as providers
from services.classroom_fixtures import probe_image
from services.classroom_budget import reserve as reserve_cny, status as budget_status


@pytest.fixture
def next_config(app, monkeypatch):
    monkeypatch.setenv('CLASSROOM_LLM_PROVIDER', 'openai_next')
    monkeypatch.setenv('OPENAI_NEXT_PRICING_CONFIRMED', 'true')
    monkeypatch.setenv('OPENAI_NEXT_BASE_URL', 'https://api.openai-next.com/v1')
    for role, amount in [('dialogue', 30), ('vision', 40), ('test', 30)]:
        monkeypatch.setenv(f'OPENAI_NEXT_{role.upper()}_API_KEY', f'synthetic-{role}-private')
        monkeypatch.setenv(f'OPENAI_NEXT_{role.upper()}_LIMIT_USD', str(amount))
    for role in ('dialogue', 'vision'):
        monkeypatch.setenv(f'OPENAI_NEXT_{role.upper()}_MODEL',
            'deepseek-v4-flash-vision-exp' if role == 'vision' else 'deepseek-v4-flash')
        monkeypatch.setenv(f'OPENAI_NEXT_{role.upper()}_INPUT_USD_PER_MILLION', '0.44')
        monkeypatch.setenv(f'OPENAI_NEXT_{role.upper()}_OUTPUT_USD_PER_MILLION', '1.32')


def response(body=None, code=200):
    class Response:
        status_code = code
        def json(self):
            return body if body is not None else {'usage': {'prompt_tokens': 100, 'completion_tokens': 10},
                'choices': [{'message': {'content': '{"ok": true}'}}]}
    return Response()


@pytest.mark.parametrize('image,test,account', [(None,False,'dialogue'), (probe_image(),False,'vision'),
    (None,True,'test'), (probe_image(),True,'test')])
def test_purpose_routing_and_currency_separation(app, next_config, monkeypatch, image, test, account):
    requests = []
    def post(url, **kwargs):
        requests.append((url, kwargs))
        return response()
    monkeypatch.setattr(providers.httpx, 'post', post)
    reserve_cny('xfyun_asr', .5)
    assert providers.chat('JSON', {}, image=image, test=test)['ok'] is True
    assert requests[0][0] == 'https://api.openai-next.com/v1/chat/completions'
    assert requests[0][1]['headers']['Authorization'] == f'Bearer synthetic-{account}-private'
    assert requests[0][1]['json']['thinking'] == {'type': 'disabled'}
    record = db.session.execute(select(CreditUsage)).scalar_one()
    assert record.account == account
    assert record.charged_usd == pytest.approx(.0000572)
    assert budget_status()['spent_and_reserved_cny'] == .5


def test_exhausted_budget_does_not_borrow_another_key(app, next_config, monkeypatch):
    credits.reserve('dialogue', 'dialogue', 'test', 26.99999)
    monkeypatch.setattr(providers.httpx, 'post', lambda *a, **k: pytest.fail('Network must not be called'))
    with pytest.raises(ValueError, match='90%'):
        providers.chat('JSON', {})
    assert credits.status()['accounts']['test']['spent_and_reserved_usd'] == 0
    assert credits.status()['accounts']['vision']['spent_and_reserved_usd'] == 0


@pytest.mark.parametrize('code', [401,429,500])
def test_failure_preserves_reservation_and_redacts_response(app, next_config, monkeypatch, code):
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs)
        return response({'error': 'synthetic-dialogue-private'}, code)
    monkeypatch.setattr(providers.httpx, 'post', post)
    with pytest.raises(ValueError, match=str(code)) as error:
        providers.chat('JSON', {})
    assert len(calls) == 1
    assert 'private' not in str(error.value)
    assert credits.status()['accounts']['dialogue']['spent_and_reserved_usd'] > 0
    assert db.session.execute(select(CreditUsage)).scalar_one().charged_usd is None


def test_missing_usage_keeps_reservation(app, next_config, monkeypatch):
    monkeypatch.setattr(providers.httpx, 'post', lambda *a, **k: response({'choices':[{'message':{'content':'{"ok":true}'}}]}))
    assert providers.chat('JSON', {})['ok']
    assert db.session.execute(select(CreditUsage)).scalar_one().charged_usd is None


@pytest.mark.parametrize('name,value', [('OPENAI_NEXT_BASE_URL','https://example.invalid/v1'),
    ('OPENAI_NEXT_DIALOGUE_API_KEY',''), ('OPENAI_NEXT_PRICING_CONFIRMED','false'),
    ('OPENAI_NEXT_DIALOGUE_MODEL','unpriced-model'), ('OPENAI_NEXT_DIALOGUE_INPUT_USD_PER_MILLION','nan')])
def test_invalid_config_blocks_before_network_and_billing(app, next_config, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(providers.httpx, 'post', lambda *a, **k: pytest.fail('Network must not be called'))
    with pytest.raises(ValueError):
        providers.chat('JSON', {})
    assert credits.status()['spent_and_reserved_usd'] == 0


def test_settlement_frees_known_reserve_and_rejects_nan(app, next_config):
    usage = credits.reserve('test', 'dialogue', 'test', 20)
    with pytest.raises(ValueError):
        credits.settle(usage, float('nan'), {})
    assert credits.status()['accounts']['test']['spent_and_reserved_usd'] == 20
    credits.settle(usage, .1, {})
    credits.reserve('test', 'vision', 'test', 20)
    assert credits.status()['accounts']['test']['spent_and_reserved_usd'] == 20.1


def test_isolated_tests_share_main_usd_ledger(app, next_config, monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
    import classroom_probe_support as support
    monkeypatch.setattr(support, 'main_app', app)
    monkeypatch.setattr(providers.httpx, 'post', lambda *a, **k: response())
    isolated = support.isolated_app(tmp_path)
    with isolated.app_context():
        providers.chat('JSON', {})
        assert db.session.execute(select(CreditUsage)).scalars().all() == []
    record = db.session.execute(select(CreditUsage)).scalar_one()
    assert record.account == 'test'


def test_two_processes_cannot_overreserve_dollars(app, next_config):
    code = '''from app import app
from services.classroom_credits import reserve
with app.app_context():
    try:
        reserve('test', 'dialogue', 'test', 20)
        print('reserved')
    except ValueError:
        print('blocked')
'''
    environment = dict(os.environ, DATABASE_URL=app.config['SQLALCHEMY_DATABASE_URI'])
    commands = [subprocess.Popen([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1],
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    outcomes = [p.communicate(timeout=15)[0].strip() for p in commands]
    assert sorted(outcomes) == ['blocked', 'reserved']
    assert credits.status()['accounts']['test']['spent_and_reserved_usd'] == 20
