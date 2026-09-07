import json
from datetime import datetime, timedelta
from extensions import db
from models import User
from classroom_models import Classroom, ClassroomEvent
from services import classroom_runtime as runtime
from services.classroom_reports import validate_report
from test_classroom_base import app
from test_classroom_api import headers

class Socket:
    def __init__(self): self.messages = []
    def send(self, text): self.messages.append(json.loads(text))

def live(app):
    db.session.add(User(id=1,account='runtime-test',name='test',password_hash='unused'))
    db.session.commit()
    sid = app.test_client().post('/api/classroom/sessions',headers=headers(1),json={'audio_consent':True}).json['session_id']
    room = db.session.get(Classroom,sid)
    room.started_at = datetime.utcnow() - timedelta(seconds=60)
    db.session.commit()
    obj = runtime.LiveClassroom(app,Socket(),room)
    obj.worker = lambda fn: None  # Never invoke paid providers in unit tests.
    return obj

def test_only_final_transcript_and_dedup(app):
    obj = live(app)
    obj.handle_asr({'type':'conversation.item.input_audio_transcription.text','text':'平均','stash':'分'})
    assert ClassroomEvent.query.count() == 0
    event = {'type':'conversation.item.input_audio_transcription.completed','item_id':'one','transcript':'必须平均分'}
    obj.handle_asr(event); obj.handle_asr(event)
    assert ClassroomEvent.query.filter_by(kind='transcript').count() == 1
    assert obj.input_version == 1

def test_evaluate_once_per_final_or_proactive_transition(app):
    obj = live(app)
    obj.handle_asr({'type':'conversation.item.input_audio_transcription.completed','item_id':'one','transcript':'平均分成两份'})
    obj.generate()
    assert obj.evaluation_key() == obj.last_eval_key
    obj.content_seconds = 21
    assert obj.evaluation_key() != obj.last_eval_key
    obj.generate()
    assert obj.evaluation_key() == obj.last_eval_key
    # Speech start cancels output, but does not cause old content to be reevaluated.
    obj.interrupt()
    assert obj.evaluation_key() == obj.last_eval_key

def test_raising_constraints_stale_decisions_and_single_speaker(app):
    obj = live(app); obj.last_final = '平均分两份'; obj.content_seconds = 21
    decision = {'action':'raise','student_id':'ming','text':'老师，不一样大的蛋糕的一半一样多吗？'}
    obj.dispatch('decision',(obj.revision,None,True,decision))
    assert obj.question_count == 1 and obj.pending
    obj.pending = None
    obj.dispatch('decision',(obj.revision,None,True,decision))
    assert obj.pending is None and obj.question_count == 1
    obj.dispatch('decision',(obj.revision-1,None,False,dict(decision,action='answer')))
    assert obj.pending is None
    obj.dispatch('decision',(obj.revision,None,False,dict(decision,action='answer',student_id='lin')))
    assert obj.pending is None

def test_interrupt_discards_audio_and_records_actual_playback(app):
    obj=live(app); obj.reply_id='old'; obj.speaking=True
    token=obj.cancel; obj.interrupt()
    assert token.is_set() and obj.reply_id is None and not obj.speaking
    count=len(obj.ws.messages)
    obj.dispatch('audio',{'reply_id':'old','audio':'AAAA'})
    assert len(obj.ws.messages)==count
    obj.reply_id='new'; obj.speaking=True
    obj.incoming({'type':'playback_failed','reply_id':'new','event_id':'playback-1'})
    assert not obj.speaking
    assert ClassroomEvent.query.filter_by(kind='playback').first().payload['status']=='playback_failed'

def test_low_confidence_pose_never_scores():
    for data in ({'present':None,'confidence':0.2},{'present':False,'confidence':0},{'present':True,'confidence':None}):
        result=validate_report({'dimensions':[{'key':'posture','score':98,'event_ids':[1]}]},[{'id':1,'type':'pose','data':data}],[])
        assert result['overall_score'] is None

def test_image_consent_and_limits(app):
    obj=live(app)
    obj.vision('invalid')  # Disabled: no decoding, file write, or cloud call.
    assert not obj.vision_busy
    obj.vision_enabled=True; obj.image_count=40
    obj.vision('invalid')
    assert not obj.vision_busy

def test_evidence_and_report_cross_account_rejected(app):
    obj=live(app)
    db.session.add(User(id=2,account='second',name='test',password_hash='unused'));db.session.commit()
    client=app.test_client()
    for suffix,method in (('','get'),('/evidence/1','get'),('/finish','post'),('/report','post'),('/ticket','post')):
        assert getattr(client,method)(f'/api/classroom/sessions/{obj.sid}{suffix}',headers=headers(2)).status_code==404

def test_authored_acceptance_dataset_and_rag_limit():
    from pathlib import Path
    from services.classroom_knowledge import search
    cases=json.loads((Path(__file__).resolve().parents[1]/'data/fractions_acceptance.json').read_text(encoding='utf-8'))
    assert len(cases['cases'])>=30 and '合成' in cases['provenance']
    result=search('分数 平均分 二分之一',99)
    assert 0<len(result)<=5
    assert all(d.get('source') and d.get('location') for d in result)
