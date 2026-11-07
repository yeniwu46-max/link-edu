import json
import time
from flask_jwt_extended import create_access_token
from test_classroom_base import app
from assistant_routes import AssistantRegistry, AssistantSession
from services.assistant_dialogue import AssistantDraft, validate_answer
from services.classroom_stream import StreamControl
from extensions import db
from models import User
from classroom_models import Classroom, ClassroomEvent
import pytest


def test_ticket_one_use_expiry_and_account_isolation(monkeypatch):
    r=AssistantRegistry();token=r.issue(1,'voice');other=r.issue(2,'text')
    assert r.consume(token)==(1,'voice') and r.consume(token) is None
    assert r.consume(other)==(2,'text')
    token=r.issue(1,'voice');now=time.monotonic();monkeypatch.setattr(time,'monotonic',lambda:now+46)
    assert r.consume(token) is None

def test_new_ticket_invalidates_previous_for_same_user():
    r=AssistantRegistry();old=r.issue(1,'text');new=r.issue(1,'voice')
    assert r.consume(old) is None and r.consume(new)==(1,'voice')

def test_assistant_json_handles_partial_unicode_and_rejects_bad_sources():
    draft=AssistantDraft();source=json.dumps({'text':'分数😀','source_ids':['kb:1']},ensure_ascii=True)
    for c in source: text=draft.feed(c)
    assert text=='分数😀'
    with pytest.raises(ValueError):validate_answer({'text':'a','source_ids':'kb:1'})


def test_routes_require_auth_and_configuration(app,monkeypatch):
    import assistant_routes as routes
    client=app.test_client()
    assert client.get('/api/assistant/capabilities').status_code==401
    user=User(account='assistant-test',password_hash='synthetic',name='Test');db.session.add(user);db.session.commit()
    header={'Authorization':'Bearer '+create_access_token(identity=str(user.id))}
    monkeypatch.setattr(routes,'capabilities_for',lambda uid:dict(text_available=True,voice_available=False,message='测试：语音未配置'))
    assert client.get('/api/assistant/capabilities',headers=header).json['text_available']
    assert client.post('/api/assistant/ticket',headers=header,json={'mode':'voice'}).status_code==503
    result=client.post('/api/assistant/ticket',headers=header,json={'mode':'text'})
    assert result.status_code==200 and result.headers['Cache-Control']=='no-store'
    assert app.extensions['assistant_registry'].consume(result.json['ticket'])==(user.id,'text')
    assert client.post('/api/assistant/ticket',headers=header,json=[]).status_code==400
    assert Classroom.query.count()==ClassroomEvent.query.count()==0

class Wire:
    def __init__(self):self.messages=[];self.closed=False
    def send(self,raw):self.messages.append(json.loads(raw))
    def close(self):self.closed=True


def session(app,mode='text'):
    w=Wire();s=AssistantSession(app,w,1,mode);s.turn='one';s.control=StreamControl();return s,w

def test_cancellation_blocks_late_audio_and_clears_control(app):
    s,w=session(app);control=s.control;s.cancel();s.send('audio','one',audio='AAAA')
    assert control.event.is_set() and s.turn is None
    assert [m['type'] for m in w.messages]==['cancel']
    s.close();assert w.closed


def test_disconnected_send_still_releases_asr_and_control(app):
    s,w=session(app,'voice');control=s.control
    class BrokenASR:
        closed=False
        def close(self): self.closed=True
    s.asr=BrokenASR()
    def disconnected(_): raise ConnectionError('synthetic disconnect')
    w.send=disconnected
    s.send('audio','one',audio='AAAA')
    assert s.transport_failed.is_set()
    s.close();s.close()
    assert control.event.is_set() and s.asr.closed and w.closed


@pytest.mark.parametrize('elapsed,silence',[(301,1),(61,61)])
def test_session_max_duration_and_silence_release_resources(app,monkeypatch,elapsed,silence):
    s,w=session(app)
    now=time.monotonic();s.started=now-elapsed;s.activity=now-silence
    s.run()
    assert any(m['type']=='closed' for m in w.messages)
    assert s.closed.is_set() and w.closed


def test_frontend_and_backend_use_same_function_guide():
    from pathlib import Path
    from assistant_routes import GUIDE
    path=Path(__file__).resolve().parents[2]/'frontend/src/data/systemGuide.json'
    assert GUIDE==json.loads(path.read_text(encoding='utf-8-sig'))


def test_playback_is_not_counted_as_silence(app):
    s,w=session(app);s.activity=time.monotonic()-61;s.playing=True
    w.receive=lambda **kwargs:json.dumps({'type':'stop','session_id':s.id})
    s.run()
    assert not any(m['type']=='closed' for m in w.messages)
    assert s.closed.is_set() and not s.playing

def test_answer_filters_citations_and_never_creates_classroom(app,monkeypatch):
    import rag.service
    import services.assistant_dialogue as dialogue
    monkeypatch.setattr(rag.service,'report_reference_sources',lambda *a,**k:[{'id':'kb:1','text':'平均分','title':'分数资料','source':'授权资料'}])
    monkeypatch.setattr(dialogue,'chat_stream',lambda *args:{'text':'平均分后的一份。','source_ids':['kb:1','invented']})
    s,w=session(app);s.generations.acquire();s.answer('one','什么是分数',s.control)
    answer=next(m for m in w.messages if m['type']=='answer')
    assert [r['id'] for r in answer['sources']]==['kb:1']
    assert len(s.history)==2 and Classroom.query.count()==ClassroomEvent.query.count()==0

def test_no_sources_produces_explicit_uncertainty(app,monkeypatch):
    import rag.service
    import services.assistant_dialogue as dialogue
    monkeypatch.setattr(rag.service,'report_reference_sources',lambda *a,**k:[])
    monkeypatch.setattr(dialogue,'chat_stream',lambda *args:{'text':'无法验证的回答','source_ids':['fake']})
    s,w=session(app);s.generations.acquire();s.answer('one','问题',s.control)
    assert '没有足够' in next(m for m in w.messages if m['type']=='answer')['text']

def test_audio_uses_existing_speech_and_cancellation(app,monkeypatch):
    import rag.service
    import services.assistant_dialogue as dialogue
    import assistant_routes as routes
    monkeypatch.setattr(rag.service,'report_reference_sources',lambda *a,**k:[])
    monkeypatch.setattr(dialogue,'chat_stream',lambda *args:{'text':'进入模拟课堂','source_ids':['system:start']})
    calls=[]
    def speak(text,sid,voice,cancelled,emit):
        calls.append((sid,voice));emit('AAAA',16000)
    monkeypatch.setattr(routes.speech,'speak',speak)
    s,w=session(app,'voice');s.generations.acquire();s.answer('one','如何开始',s.control)
    assert calls==[(None,'Cherry')]
    assert [m['type'] for m in w.messages][-2:]==['audio','audio_end']

def test_stream_reservation_is_independent_and_cancel_closes_transport(app,monkeypatch):
    from services import assistant_dialogue as p
    from test_classroom_stream import Response,chunks_for
    output={'text':'打开课前准备','source_ids':['system:start']};response=Response(chunks_for(output));reservations=[];settled=[]
    monkeypatch.setattr(p,'key',lambda _: 'synthetic');monkeypatch.setattr(p,'price',lambda _:1)
    monkeypatch.setattr(p,'reserve',lambda *args:reservations.append(args) or 1);monkeypatch.setattr(p,'settle',lambda *args:settled.append(args))
    monkeypatch.setattr(p.httpx,'stream',lambda *a,**k:response)
    assert p.chat_stream('JSON',{},StreamControl(),lambda _:None)==output
    assert len(reservations)==len(settled)==1 and reservations[0][-1] is None and response.closed

def test_real_assistant_socket_voice_turn_cancel_and_no_classroom_write(app,monkeypatch):
    import queue,threading,websocket
    from werkzeug.serving import make_server
    import assistant_routes as routes
    import rag.service
    import services.assistant_dialogue as dialogue
    user=User(account='socket-assistant',password_hash='synthetic',name='Test');db.session.add(user);db.session.commit()
    uid=user.id;streams=[]
    class ASR:
        def __init__(self,sid):self.events=queue.Queue();self.closed=False;streams.append(self)
        def receive(self):
            try:return self.events.get(timeout=.05)
            except queue.Empty:raise websocket.WebSocketTimeoutException()
        def audio(self,raw):
            self.events.put({'type':'speech_started'})
            self.events.put({'type':'final','item_id':str(time.monotonic()),'transcript':'如何开始训练'})
        def close(self):self.closed=True
    monkeypatch.setattr(routes,'capabilities_for',lambda uid:dict(voice_available=True,text_available=True))
    monkeypatch.setattr(routes.speech,'ASR',ASR)
    monkeypatch.setattr(routes.speech,'speak',lambda text,sid,voice,cancelled,emit:emit('AAAA',16000))
    monkeypatch.setattr(rag.service,'report_reference_sources',lambda *a,**k:[])
    monkeypatch.setattr(dialogue,'chat_stream',lambda *a:{'text':'进入课前准备','source_ids':['system:start']})
    token=app.extensions['assistant_registry'].issue(uid,'voice')
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();sock=None
    try:
        sock=websocket.create_connection(f'ws://127.0.0.1:{server.server_port}/api/assistant/live',timeout=3)
        sock.send(json.dumps({'ticket':token}));ready=json.loads(sock.recv());sid=ready['session_id'];assert ready['type']=='ready'
        start=time.monotonic();sock.send(json.dumps({'type':'audio','session_id':sid,'audio':'AAAA'}));events=[]
        for _ in range(12):
            event=json.loads(sock.recv());events.append(event)
            if event['type']=='audio_end':break
        assert any(e['type']=='answer' for e in events) and any(e['type']=='audio' for e in events)
        print('synthetic assistant roundtrip ms:',round((time.monotonic()-start)*1000))
        turn=next(e['turn_id'] for e in events if e['type']=='answer')
        sock.send(json.dumps({'type':'cancel','session_id':sid}));cancel=json.loads(sock.recv());assert cancel['cancelled_turn_id']==turn
        sock.send(json.dumps({'type':'stop','session_id':sid}));sock.close()
        deadline=time.monotonic()+3
        while uid in app.extensions['assistant_registry'].live and time.monotonic()<deadline:time.sleep(.01)
        assert streams[0].closed and uid not in app.extensions['assistant_registry'].live
        sock=websocket.create_connection(f'ws://127.0.0.1:{server.server_port}/api/assistant/live',timeout=3);sock.send(json.dumps({'ticket':token}));assert sock.recv()==''
        assert Classroom.query.count()==ClassroomEvent.query.count()==0
    finally:
        if sock:sock.close()
        server.shutdown();thread.join(timeout=3)
