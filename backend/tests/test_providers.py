import pytest
from test_classroom_base import app
from services import classroom_providers as p


def test_missing_credentials_do_not_call_network(app, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with pytest.raises(p.ProviderError, match='尚未配置'):
        p.chat('test', {})


def test_provider_http_error_redacted(app, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-private-key')
    monkeypatch.setenv('AI_LLM_INPUT_CNY_PER_MILLION', '10')
    monkeypatch.setenv('AI_LLM_OUTPUT_CNY_PER_MILLION', '10')
    class Response:
        status_code = 401
    monkeypatch.setattr(p.httpx, 'post', lambda *a, **k: Response())
    with pytest.raises(p.ProviderError, match='401') as error:
        p.chat('system', {})
    assert 'test-private-key' not in str(error.value)
    assert '密钥鉴权失败' in str(error.value)
    assert 'DEEPSEEK_API_KEY' in str(error.value)


@pytest.mark.parametrize('code,hint', [(401, '密钥鉴权失败'), (403, '权限'),
    (429, '限流或额度不足'), (500, '暂时异常'), (400, '请求配置')])
def test_http_failure_gives_status_specific_action(code, hint):
    error = p.provider_http_error(code, 'OpenAI Next', 'OPENAI_NEXT_DIALOGUE_API_KEY')
    assert hint in str(error)
    assert f'HTTP {code}' in str(error)

def test_insecure_endpoint_rejected_before_network_or_billing(app,monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-private-key')
    monkeypatch.setenv('DEEPSEEK_BASE_URL','http://example.invalid')
    with pytest.raises(p.ProviderError,match='HTTPS'):
        p.chat('test',{})


@pytest.mark.parametrize('vision,test,profile,purpose', [
    (False, False, None, 'DIALOGUE'), (True, False, None, 'VISION'),
    (False, True, None, 'TEST'), (True, True, None, 'TEST'),
    (False, False, 'test', 'TEST'),
])
def test_deepseek_purpose_keys(app, monkeypatch, vision, test, profile, purpose):
    app.config['CLASSROOM_API_PROFILE'] = profile
    for name in ('DIALOGUE', 'VISION', 'TEST'):
        monkeypatch.setenv(f'DEEPSEEK_{name}_API_KEY', f'synthetic-{name}')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'stale-global-key')
    monkeypatch.setattr(p, 'price', lambda _: 1)
    monkeypatch.setattr(p, 'reserve', lambda *args: 1)
    calls = []
    class Response:
        status_code = 200
        def json(self): return {'choices': [{'message': {'content': '{"ok":true}'}}]}
    def post(url, **kwargs):
        calls.append(kwargs)
        return Response()
    monkeypatch.setattr(p.httpx, 'post', post)
    assert p.chat('JSON', {}, image='synthetic-image' if vision else None, test=test) == {'ok': True}
    assert len(calls) == 1
    assert calls[0]['headers']['Authorization'] == f'Bearer synthetic-{purpose}'


def test_blank_purpose_key_does_not_borrow_legacy_key(app, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_DIALOGUE_API_KEY', '')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'synthetic-legacy')
    monkeypatch.setattr(p.httpx, 'post', lambda *a, **k: pytest.fail('No request allowed'))
    with pytest.raises(p.ProviderError, match='DEEPSEEK_DIALOGUE_API_KEY'):
        p.chat('JSON', {})


def test_capabilities_use_purpose_credentials(app, monkeypatch):
    from services.classroom_speech import describe
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.setenv('DEEPSEEK_DIALOGUE_API_KEY', 'synthetic-dialogue')
    monkeypatch.setenv('DEEPSEEK_VISION_API_KEY', '')
    assert describe('dialogue')['configured'] is True
    assert describe('vision')['configured'] is False
