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

def test_insecure_endpoint_rejected_before_network_or_billing(app,monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-private-key')
    monkeypatch.setenv('DEEPSEEK_BASE_URL','http://example.invalid')
    with pytest.raises(p.ProviderError,match='HTTPS'):
        p.chat('test',{})
