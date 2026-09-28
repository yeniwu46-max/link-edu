import json
import pytest
from services.classroom_stream import StudentDraft, StreamControl, StreamCancelled, partial_string, unique_object
from services import classroom_dialogue_stream as provider
from test_classroom_base import app
from test_classroom_runtime import live

OUTPUT = dict(action='answer', student_id='ming', text='平均分成两份。每份一样大！', understanding='平均分', open_question='', resolved=True)


def test_json_prefix_every_character_and_surrogates():
    parser = StudentDraft()
    value = dict(OUTPUT, text='中文"引号\\换行\n😀')
    source = json.dumps(value, ensure_ascii=True)
    seen = []
    for char in source:
        draft = parser.feed(char)
        if draft:
            seen.append(draft['text'])
    assert seen[-1] == value['text']
    assert all(b.startswith(a) for a, b in zip(seen, seen[1:]))
    assert partial_string('"\\uD83D') == ''


def test_no_metadata_or_unordered_fields_never_preview():
    assert StudentDraft().feed('{"text":"hello","action":"answer"') is None
    assert StudentDraft().feed('{"action":"answer", "student_id":') is None
    with pytest.raises(ValueError):
        json.loads('{"action":"answer","action":"wait"}', object_pairs_hook=unique_object)


class Response:
    status_code = 200
    def __init__(self, chunks): self.chunks, self.closed = chunks, False
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self): self.closed = True
    def iter_lines(self):
        for chunk in self.chunks:
            yield 'data: ' + (chunk if isinstance(chunk, str) else json.dumps(chunk))
            yield ''


def chunks_for(output=OUTPUT):
    return [{'choices':[{'index':0,'delta':{'content':char}}]} for char in json.dumps(output, ensure_ascii=False)] + [
        {'choices':[{'delta':{}, 'finish_reason':'stop'}], 'usage': {'prompt_tokens':100,'completion_tokens':20}},
        {'choices':[], 'usage':{'prompt_tokens':100,'completion_tokens':20}}, '[DONE]']


def fake_provider(monkeypatch, chunks):
    calls, reservations, settlements = [], [], []
    response = Response(chunks)
    monkeypatch.setattr(provider, 'key', lambda _: 'synthetic-only')
    monkeypatch.setattr(provider, 'price', lambda _: 1)
    monkeypatch.setattr(provider, 'reserve', lambda *args: reservations.append(args) or 1)
    monkeypatch.setattr(provider, 'settle', lambda *args: settlements.append(args))
    def stream(*args, **kwargs):
        calls.append(kwargs)
        return response
    monkeypatch.setattr(provider.httpx, 'stream', stream)
    return response, calls, reservations, settlements


def test_stream_one_request_one_reservation_one_settlement(app, monkeypatch):
    response, calls, reservations, settlements = fake_provider(monkeypatch, chunks_for())
    drafts = []
    output = provider.chat_stream('JSON', {}, None, StreamControl(), drafts.append)
    assert output == OUTPUT and drafts[-1]['text'] == OUTPUT['text']
    assert len(calls) == len(reservations) == len(settlements) == 1
    assert calls[0]['json']['stream'] is True and response.closed


def test_next_stream_uses_dialogue_key_and_usd_ledger(app, monkeypatch):
    from services import classroom_credits
    monkeypatch.setenv('CLASSROOM_LLM_PROVIDER', 'openai_next')
    response, calls, _, _ = fake_provider(monkeypatch, chunks_for())
    keys, reservations, settlements = [], [], []
    monkeypatch.setattr(provider, 'key', lambda name: keys.append(name) or 'synthetic')
    monkeypatch.setattr(classroom_credits, 'reserve', lambda *args: reservations.append(args) or 1)
    monkeypatch.setattr(classroom_credits, 'settle', lambda *args: settlements.append(args))
    provider.chat_stream('JSON', {}, None, StreamControl(), lambda _: None)
    assert keys == ['OPENAI_NEXT_DIALOGUE_API_KEY']
    assert reservations[0][:2] == ('dialogue', 'dialogue') and len(settlements) == 1


@pytest.mark.parametrize('profile,purpose', [(None, 'DIALOGUE'), ('test', 'TEST')])
def test_deepseek_stream_uses_purpose_key(app, monkeypatch, profile, purpose):
    app.config['CLASSROOM_API_PROFILE'] = profile
    monkeypatch.setenv(f'DEEPSEEK_{purpose}_API_KEY', 'synthetic-purpose')
    _, calls, _, _ = fake_provider(monkeypatch, chunks_for())
    keys = []
    monkeypatch.setattr(provider, 'key', lambda name: keys.append(name) or 'synthetic')
    assert provider.chat_stream('JSON', {}, None, StreamControl(), lambda _: None) == OUTPUT
    assert keys == [f'DEEPSEEK_{purpose}_API_KEY'] and len(calls) == 1


@pytest.mark.parametrize('selected,profile,credential', [
    ('deepseek', None, 'DEEPSEEK_API_KEY'),
    ('openai_next', None, 'OPENAI_NEXT_DIALOGUE_API_KEY'),
    ('openai_next', 'test', 'OPENAI_NEXT_TEST_API_KEY'),
])
def test_stream_401_identifies_credential_without_retry_or_key_fallback(app, monkeypatch, selected, profile, credential):
    from services import classroom_credits
    monkeypatch.setenv('CLASSROOM_LLM_PROVIDER', selected)
    app.config['CLASSROOM_API_PROFILE'] = profile
    response, calls, _, _ = fake_provider(monkeypatch, [])
    response.status_code = 401
    keys, settlements, drafts = [], [], []
    monkeypatch.setattr(provider, 'key', lambda name: keys.append(name) or 'synthetic-private-token')
    monkeypatch.setattr(classroom_credits, 'reserve', lambda *args: 1)
    monkeypatch.setattr(classroom_credits, 'settle', lambda *args: settlements.append(args))
    with pytest.raises(provider.ProviderError, match='密钥鉴权失败') as error:
        provider.chat_stream('JSON', {}, None, StreamControl(), drafts.append)
    assert credential in str(error.value)
    assert 'synthetic-private-token' not in str(error.value)
    assert '重新登录课堂无法解决' in str(error.value)
    assert keys == [credential] and len(calls) == 1
    assert response.closed and not drafts and not settlements


@pytest.mark.parametrize('chunks', [chunks_for()[:-3], [{'error':{'message':'do not leak'}}], ['not json'], chunks_for(dict(OUTPUT, student_id='intruder'))])
def test_invalid_or_disconnected_stream_never_retries(app, monkeypatch, chunks):
    response, calls, _, _ = fake_provider(monkeypatch, chunks)
    with pytest.raises(ValueError):
        provider.chat_stream('JSON', {}, None, StreamControl(), lambda _: None)
    assert len(calls) == 1 and response.closed


def test_cancel_closes_response_keeps_unknown_reserve(app, monkeypatch):
    response, calls, reservations, settlements = fake_provider(monkeypatch, chunks_for())
    control = StreamControl()
    with pytest.raises(StreamCancelled):
        provider.chat_stream('JSON', {}, None, control, lambda _: control.cancel())
    assert response.closed and len(reservations) == 1 and not settlements


def test_runtime_draft_constraints_cancel_and_no_evidence(app):
    obj = live(app)
    obj.last_final = '小明，怎样平均分？'
    obj.generate()
    gid, rev = obj.generation_id, obj.revision
    obj.dispatch('generation_draft', (gid, rev, 'ming', False, dict(OUTPUT, student_id='lin')))
    assert not any(m['type'] == 'reply_delta' for m in obj.ws.messages)
    obj.dispatch('generation_draft', (gid, rev, 'ming', False, OUTPUT))
    assert any(m['type'] == 'reply_delta' for m in obj.ws.messages)
    assert not obj.history
    obj.interrupt()
    count = len(obj.ws.messages)
    obj.dispatch('generation_draft', (gid, rev, 'ming', False, OUTPUT))
    obj.dispatch('generation_failed', (gid, 'late'))
    assert len(obj.ws.messages) == count


def test_runtime_wait_clears_thinking_without_reply(app):
    obj = live(app); obj.generate()
    obj.dispatch('decision', (obj.revision, None, False, {'action':'wait'}))
    assert obj.generation_id is None and obj.pending is None
    assert obj.ws.messages[-1]['type'] == 'generation_cancelled'


def test_reservation_failure_does_not_send_request(app, monkeypatch):
    _, calls, _, _ = fake_provider(monkeypatch, chunks_for())
    def blocked(*args): raise ValueError('额度不足')
    monkeypatch.setattr(provider, 'reserve', blocked)
    with pytest.raises(ValueError, match='额度不足'):
        provider.chat_stream('JSON', {}, None, StreamControl(), lambda _: None)
    assert not calls
