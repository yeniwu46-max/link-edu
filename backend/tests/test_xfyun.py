import base64
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
import pytest
from services import xfyun_wire as wire


@pytest.fixture
def credentials(monkeypatch):
    for name in ('XFYUN_APP_ID', 'XFYUN_API_KEY', 'XFYUN_API_SECRET'):
        monkeypatch.setenv(name, 'synthetic-test-value')


def test_signature_and_endpoint_allowlist(credentials):
    url = wire.signed_url(wire.ASR_URL, datetime(2026, 9, 8, tzinfo=timezone.utc))
    query = parse_qs(urlsplit(url).query)
    assert query['host'] == ['iat.xf-yun.com']
    assert 'hmac-sha256' in base64.b64decode(query['authorization'][0]).decode()
    with pytest.raises(ValueError, match='允许'):
        wire.signed_url('wss://example.invalid')


def test_dynamic_replacement_and_duplicate_sequence():
    transcript = wire.Transcript()
    def part(sn, text, **extra):
        return dict(sn=sn, ws=[{'cw':[{'w':text}]}], **extra)
    assert transcript.update(part(1, '不是')) == '不是'
    assert transcript.update(part(2, '平均')) == '不是平均'
    assert transcript.update(part(3, '必须平均分', pgs='rpl', rg=[1,2])) == '必须平均分'
    assert transcript.update(part(3, '必须平均分')) == '必须平均分'


def test_wire_error_does_not_expose_provider_message():
    class Socket:
        def recv(self): return '{"header":{"code":11200,"message":"secret-url-and-token"}}'
    with pytest.raises(ValueError, match='11200') as error:
        wire.receive(Socket(), 'asr')
    assert 'secret-url' not in str(error.value)


def test_tts_rate_accounting_and_cancel(credentials, monkeypatch):
    from services import xfyun_speech as speech
    monkeypatch.setenv('XFYUN_TTS_VOICE', 'test-voice')
    reserved, charged, received = [], [], []
    monkeypatch.setattr(speech, 'book', lambda *a: (reserved.append(a) or 1, 0.1))
    monkeypatch.setattr(speech, 'charge', lambda *a, **kw: charged.append((a, kw)))
    class Socket:
        def settimeout(self, timeout): pass
        def send(self, text): assert 'audio/L16;rate=16000' in text
        def recv(self): return '{"code":0,"data":{"audio":"AAAAAA==","status":2}}'
        def close(self): pass
    monkeypatch.setattr(wire, 'connect', lambda url: Socket())
    speech.speak('平均分', None, 'Cherry', lambda: False, lambda a, r: received.append(r))
    assert received == [16000] and len(charged) == 1
    speech.speak('取消', None, 'Cherry', lambda: True, lambda *a: pytest.fail('cancelled'))
    assert len(reserved) == 1


def test_xfyun_prices_fail_closed(monkeypatch):
    from services.xfyun_speech import rate
    monkeypatch.delenv('XFYUN_PRICING_CONFIRMED', raising=False)
    with pytest.raises(ValueError, match='讯飞'):
        rate('asr')
