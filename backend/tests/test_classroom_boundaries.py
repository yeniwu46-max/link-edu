import base64
import pytest
from classroom_models import ClassroomEvent
from services import classroom_runtime as runtime
from test_classroom_base import app
from test_classroom_runtime import live


@pytest.mark.parametrize('seconds,last,count,allowed', [(19.99,-45,0,False),(20,-45,0,True),
    (64.99,20,1,False),(65,20,1,True),(200,0,6,False)])
def test_proactive_exact_thresholds(seconds,last,count,allowed):
    assert runtime.proactive_allowed(seconds,last,count,True) is allowed


@pytest.mark.parametrize('name,sid',[('小明','ming'),('小雨','yu'),('小林','lin')])
def test_named_student_selection_and_no_wrong_student(app,monkeypatch,name,sid):
    obj=live(app); obj.last_final=f'{name}，每份是几分之一？'
    obj.worker=lambda fn:fn()
    captured=[]
    monkeypatch.setattr(runtime,'chat',lambda system,data,*a:captured.append(data) or {'action':'wait'})
    obj.generate()
    assert captured[0]['named_student']==sid
    obj.dispatch('decision',(obj.revision,sid,False,{'action':'answer','student_id':sid,'text':'一半。'}))
    assert obj.pending['student_id']==sid
    obj.pending=None
    wrong='yu' if sid!='yu' else 'ming'
    obj.dispatch('decision',(obj.revision,sid,False,{'action':'answer','student_id':wrong,'text':'一半。'}))
    assert obj.pending is None


def test_spoken_invitation_waits_for_teacher_and_deduplicates_final(app):
    obj=live(app); obj.pending={'action':'raise','student_id':'ming','text':'为什么要平均分？'}
    obj.teacher_speaking=True
    obj.incoming({'type':'select_student','event_id':'select','student_id':'ming'})
    assert obj.reply_id is None and obj.pending
    event={'type':'final','item_id':'invite','transcript':'小明你说','speech_seconds':1}
    obj.handle_asr(event); obj.handle_asr(event)
    assert obj.pending and obj.input_version==1
    obj.teacher_speaking=False
    obj.incoming({'type':'select_student','event_id':'select-2','student_id':'ming'})
    assert obj.reply_id and obj.pending is None


def test_vision_cooldown_inflight_and_cap_without_cloud(app):
    obj=live(app); obj.vision_enabled=True
    encoded='data:image/jpeg;base64,'+base64.b64encode(b'\xff\xd8\xffsynthetic-boundary').decode()
    obj.vision(encoded); assert obj.image_count==1 and obj.vision_busy
    obj.last_image=-100; obj.vision(encoded); assert obj.image_count==1
    obj.vision_busy=False; obj.last_image=obj.elapsed(); obj.vision(encoded); assert obj.image_count==1
    obj.last_image=-100; obj.image_count=40; obj.vision(encoded); assert obj.image_count==40


def test_unusable_pose_values_remain_unknown(app):
    obj=live(app)
    obj.incoming({'type':'pose','event_id':'pose','data':{'present':None,'confidence':float('nan'),
        'left_raised':'yes','movement':float('inf')}})
    data=ClassroomEvent.query.filter_by(kind='pose').one().payload
    assert data['present'] is None and data['confidence'] is None
    assert data['left_raised'] is None and data['movement'] is None


def test_asr_failure_closes_and_tts_failure_does_not_complete(app):
    obj=live(app); obj.reply_id='r'; obj.speaking=True
    obj.dispatch('audio_end',{'reply_id':'r','ok':False})
    assert obj.ws.messages[-1]['ok'] is False
    assert ClassroomEvent.query.filter_by(kind='playback').count()==0
    obj.dispatch('asr_failed','语音识别连接中断')
    assert obj.closed.is_set() and obj.ws.messages[-1]['type']=='error'
