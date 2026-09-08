import base64
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
import pytest
from test_classroom_base import app
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


def test_three_minute_segmentation_has_no_audio_gap_or_duplicate():
    from services.xfyun_segments import Segmenter
    commands, events = [], []
    segmenter = Segmenter(commands.append, events.append)
    frame = b'\x00\x20' * 3200  # synthetic non-speech energy; this is NOT ASR accuracy testing
    for _ in range(901):
        segmenter.feed(frame)
    segmenter.finish()
    sent = b''.join(c[2] for c in commands if c[0] == 'audio')
    assert sent == frame * 901
    ends = [c for c in commands if c[0] == 'end']
    assert len(ends) == 4 and all(c[2] <= 55.001 for c in ends)
    assert [e['type'] for e in events] == ['speech_started', 'speech_stopped']


def test_silence_ends_utterance_and_finish_is_idempotent():
    from services.xfyun_segments import Segmenter
    commands, events = [], []
    segmenter = Segmenter(commands.append, events.append)
    segmenter.feed(b'\x00\x00' * 16000)
    assert not commands
    segmenter.feed(b'\x00\x20' * 3200)
    segmenter.feed(b'\x00\x00' * 16000)
    assert [e['type'] for e in events] == ['speech_started', 'speech_stopped']
    segmenter.finish()
    n = len(commands)
    segmenter.finish()
    assert len(commands) == n


def test_stream_transport_finalizes_once(app, credentials, monkeypatch):
    import json
    import queue
    import time
    import websocket
    from services import xfyun_asr as asr_module
    charged = []
    monkeypatch.setattr(asr_module, 'rate', lambda service: 0.01)
    monkeypatch.setattr(asr_module, 'book', lambda *a: (1, 0.01))
    monkeypatch.setattr(asr_module, 'charge', lambda *a, **kw: charged.append(kw))
    class Socket:
        def __init__(self): self.events = queue.Queue()
        def settimeout(self, timeout): pass
        def send(self, raw):
            item = json.loads(raw)
            if item['header']['status'] == 2:
                result = {'sn':1, 'ws':[{'cw':[{'w':'必须平均分'}]}]}
                self.events.put(json.dumps({'header':{'status':2,'code':0},'payload':{'result':{
                    'text':base64.b64encode(json.dumps(result).encode()).decode()}}}))
        def recv(self):
            try: return self.events.get(timeout=0.1)
            except queue.Empty: raise websocket.WebSocketTimeoutException()
        def close(self): pass
    monkeypatch.setattr(wire, 'connect', lambda url: Socket())
    asr = asr_module.ASR(None)
    try:
        asr.audio(base64.b64encode(b'\x00\x20' * 3200).decode())
        asr.finish()
        events, until = [], time.monotonic() + 5
        while time.monotonic() < until:
            try: events.append(asr.receive())
            except websocket.WebSocketTimeoutException: continue
            if events[-1]['type'] == 'finished': break
        assert [e['transcript'] for e in events if e['type'] == 'final'] == ['必须平均分']
        assert events[-1]['type'] == 'finished' and len(charged) == 1
    finally:
        asr.close()


def test_out_of_order_segments_flush_in_order():
    from services.xfyun_asr import ASR
    asr = ASR.__new__(ASR)
    events = []
    asr.emit = events.append
    asr.next_final, asr.total_segments, asr.finished = 1, 2, False
    asr.completed = {2: {'type':'final', 'item_id':'two'}}
    asr._flush()
    assert not events
    asr.completed[1] = {'type':'final', 'item_id':'one'}
    asr._flush()
    assert events == [{'type':'final', 'item_id':'one'}, {'type':'final', 'item_id':'two'}, {'type':'finished'}]
