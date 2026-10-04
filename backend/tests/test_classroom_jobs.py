import threading
import time
from extensions import db
from classroom_models import ClassroomEvent, Classroom, PracticePlan
from services import classroom_reports as reports
from test_classroom_base import app
from test_classroom_runtime import live
from test_classroom_api import headers

def wait_for_report(sid):
    until=time.monotonic()+4
    while time.monotonic()<until:
        if sid not in reports.jobs:
            db.session.expire_all()
            return db.session.get(Classroom,sid)
        time.sleep(.01)
    raise AssertionError('Report job did not finish')

def test_finish_is_idempotent_and_correction_has_no_fixed_bonus(app,monkeypatch):
    obj=live(app)
    from test_classroom_readiness import seed_sufficient
    seed_sufficient(obj.sid)
    row=ClassroomEvent(session_id=obj.sid,event_key='authored-fixture',kind='transcript',at_ms=20000,payload={'text':'测试场景：整体必须平均分'})
    db.session.add(row);db.session.commit(); eid=row.id
    started=threading.Event(); release=threading.Event(); calls=[]
    def fake_chat(*a,**kw):
        calls.append(1);started.set();release.wait(timeout=3)
        return {'dimensions':[{'key':'clarity','score':70,'reason':'合成单元测试','event_ids':[eid]}]}
    monkeypatch.setattr(reports,'chat',fake_chat)
    c=app.test_client();url=f'/api/classroom/sessions/{obj.sid}'
    assert c.post(url+'/finish',headers=headers(1)).status_code==202
    assert started.wait(timeout=2)
    assert c.post(url+'/finish',headers=headers(1)).status_code==202
    release.set()
    room=wait_for_report(obj.sid)
    assert len(calls)==1 and room.report_version==1 and room.report['overall_score']==70
    first_plan=PracticePlan.query.filter_by(source_session_id=obj.sid,source_report_version=1).one()
    assert first_plan.source_event_ids==[eid] and first_plan.status=='suggested'
    c.post(url+'/finish',headers=headers(1))
    assert len(calls)==1
    c.post(url+'/report',headers=headers(1),json={'objection':'请核对时间20秒'})
    room=wait_for_report(obj.sid)
    assert len(calls)==2 and room.report_version==2 and room.report['overall_score']==70
    db.session.refresh(first_plan)
    assert first_plan.status=='superseded'
    assert PracticePlan.query.filter_by(source_session_id=obj.sid,source_report_version=2).count()==1
    assert ClassroomEvent.query.filter_by(session_id=obj.sid,kind='correction').count()==1

def test_empty_classroom_fails_without_cloud_or_demo(app,monkeypatch):
    obj=live(app)
    monkeypatch.setattr(reports,'chat',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Must not call cloud')))
    app.test_client().post(f'/api/classroom/sessions/{obj.sid}/finish',headers=headers(1))
    room=wait_for_report(obj.sid)
    assert room.report_state=='insufficient' and room.report is None and room.report_version==0


def test_failed_report_needs_explicit_retry_not_repeated_finish(app, monkeypatch):
    obj = live(app)
    from test_classroom_readiness import seed_sufficient
    seed_sufficient(obj.sid)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise ValueError('合成评审失败')
    monkeypatch.setattr(reports, 'chat', fail)
    client = app.test_client()
    url = f'/api/classroom/sessions/{obj.sid}'
    client.post(url + '/finish', headers=headers(1))
    assert wait_for_report(obj.sid).report_state == 'failed'
    stages = [e.payload['stage'] for e in ClassroomEvent.query.filter_by(session_id=obj.sid, kind='report_stage').order_by(ClassroomEvent.id).all()]
    assert stages == ['checking', 'preparing', 'judging', 'failed']
    client.post(url + '/finish', headers=headers(1))
    wait_for_report(obj.sid)
    assert len(calls) == 1
    client.post(url + '/report', headers=headers(1), json={})
    wait_for_report(obj.sid)
    assert len(calls) == 2

def test_invalid_json_and_no_cache(app):
    obj=live(app); c=app.test_client()
    assert c.post('/api/classroom/sessions',headers=headers(1),json=[]).status_code==400
    assert c.get('/api/classroom/sessions',headers=headers(1)).headers['Cache-Control']=='no-store'
    assert c.get('/api/classroom/sessions').status_code==401

def test_finish_recovers_already_closed_runtime(app):
    from services.classroom_runtime import ACTIVE
    obj=live(app);obj.closed.set();ACTIVE[obj.sid]=obj
    try:
        response=app.test_client().post(f'/api/classroom/sessions/{obj.sid}/finish',headers=headers(1))
        assert response.status_code==202 and response.json.get('state')!='draining'
        assert wait_for_report(obj.sid).state=='ended'
    finally:
        ACTIVE.pop(obj.sid,None)
