import json
import time
import pytest
from test_classroom_base import app
from test_classroom_runtime import live
from classroom_models import ClassroomEvent, Classroom
from extensions import db
from services import classroom_runtime as runtime
from services.classroom_interaction import StudentInteractionQueue

def ready(app):
    obj=live(app);obj.asr=object();obj.last_voice=time.monotonic()-3
    room=db.session.get(Classroom,obj.sid);room.state='active';db.session.commit()
    return obj

def click(obj,sid='ming',key='click-1'):
    obj.incoming(dict(type='student_interact',student_id=sid,event_id=key))

def drain(obj):
    while not obj.inbox.empty():
        obj.dispatch(*obj.inbox.get_nowait())

@pytest.mark.parametrize('kind',['question','challenge'])
def test_random_branch_specific_person_latest_context_and_evidence(app,monkeypatch,kind):
    import services.classroom_interaction as q
    monkeypatch.setattr(q.random,'choice',lambda values: kind)
    obj=ready(app);obj.teacher_speaking=True
    click(obj,'lin');assert not obj.start_queued_interaction()
    obj.last_final='最新说明：平均分成两份';obj.teacher_speaking=False
    captures=[]
    def stream(system,payload,sid,control,draft):
        captures.append(payload)
        output=dict(action='followup',student_id='lin',text='老师，两份不一样大也行吗？',state_updates=[])
        draft(output);return output
    monkeypatch.setattr(runtime,'chat_stream',stream)
    obj.worker=lambda fn:fn()
    assert obj.start_queued_interaction();drain(obj)
    assert captures[0]['current_teacher_text']==obj.last_final
    assert captures[0]['named_student']=='lin'
    assert captures[0]['manual_interaction']['interaction_kind']==kind
    assert obj.pending['_manual']['trigger']=='manual_click'
    assert any(m['type']=='reply_delta' for m in obj.ws.messages)
    obj.worker=lambda fn:None;obj.start_reply(obj.pending)
    event=ClassroomEvent.query.filter_by(kind='student').one()
    assert event.payload['interaction_kind']==kind and event.payload['trigger']=='manual_click'
    assert event.payload['generation_id']
    assert ClassroomEvent.query.filter_by(kind='transcript').count()==0
    assert obj.question_count==0
    assert obj.speaking
    obj.incoming(dict(type='playback_done',reply_id=obj.reply_id,event_id='done'))
    assert not obj.speaking

def test_one_pending_replacement_dedup_cancel_waits_for_current_reply(app):
    obj=ready(app);obj.speaking=True
    click(obj);request=obj.manual_queue.pending
    click(obj,key='repeat');assert obj.manual_queue.pending is request
    click(obj,'yu','other');assert obj.manual_queue.pending['student_id']=='yu'
    click(obj,'lin','other');assert obj.manual_queue.pending['student_id']=='yu'
    assert not obj.start_queued_interaction() and not obj.busy
    obj.incoming(dict(type='cancel_student_interact',event_id='cancel'))
    assert obj.manual_queue.pending is None

def test_uninvited_raise_yields_priority_but_invited_response_does_not(app):
    obj=ready(app)
    obj.pending=dict(action='raise',student_id='ming',text='问题')
    click(obj,'yu')
    assert obj.start_queued_interaction() and obj.generation_manual['student_id']=='yu'
    assert any(m['type']=='raise_cleared' for m in obj.ws.messages)
    obj.busy=False;obj.pending=dict(action='raise',student_id='ming',text='问题',invited=True)
    click(obj,'lin','another')
    assert not obj.start_queued_interaction()

def test_no_trigger_when_paused_ended_or_not_connected(app):
    obj=ready(app);obj.asr=None;click(obj);assert obj.manual_queue.pending is None
    obj.asr=object();room=db.session.get(Classroom,obj.sid);room.state='paused';db.session.commit()
    click(obj,key='paused');assert obj.manual_queue.pending is None
    room.state='active';db.session.commit();obj.finish_requested=True
    click(obj,key='ended');assert obj.manual_queue.pending is None

def test_failure_consumes_request_without_automatic_retry(app,monkeypatch):
    obj=ready(app);calls=[]
    def fail(*args): calls.append(1);raise ValueError('synthetic failure')
    monkeypatch.setattr(runtime,'chat_stream',fail);obj.worker=lambda fn:fn()
    click(obj);obj.start_queued_interaction();drain(obj)
    assert obj.generation_failed and obj.manual_queue.pending is None
    assert not obj.start_queued_interaction()
    obj.incoming(dict(type='retry_generation',event_id='retry'))
    assert len(calls)==1
    assert any(m['type']=='student_interaction' and m['status']=='failed' for m in obj.ws.messages)

def test_disconnect_clears_queue(app):
    obj=ready(app);click(obj)
    obj.connect_asr=lambda:None
    class FakeASR:
        def close(self): pass
    obj.asr=FakeASR()
    def disconnect(**kwargs): raise ConnectionError('synthetic')
    obj.ws.receive=disconnect
    with pytest.raises(ConnectionError):obj.run()
    assert obj.manual_queue.pending is None

def test_invalid_student_rejected():
    with pytest.raises(ValueError):StudentInteractionQueue().enqueue('unknown','id')
