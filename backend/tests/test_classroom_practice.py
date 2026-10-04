from datetime import datetime

from flask_jwt_extended import create_access_token

from classroom_models import Classroom, ClassroomEvent, PracticePlan
from extensions import db
from models import User
from services.classroom_practice import finish_retest_plans
from test_classroom_base import app


def auth(user_id):
    return {'Authorization': 'Bearer ' + create_access_token(identity=str(user_id))}


def test_practice_plan_is_owned_idempotent_and_compares_observed_events(app):
    db.session.add_all([User(id=i, account=f'practice-{i}', name='test', password_hash='unused') for i in (1, 2)])
    db.session.commit()
    client = app.test_client()
    source = client.post('/api/classroom/sessions', headers=auth(1),
                         json={'audio_consent': True, 'camera_consent': True}).json
    sid = source['session_id']
    room = db.session.get(Classroom, sid)
    room.state, room.ended_at = 'ended', datetime.utcnow()
    room.report_state, room.report_version = 'completed', 1
    event = ClassroomEvent(session_id=sid, event_key='source-summary', kind='transcript', at_ms=2000,
                           payload={'text': '这节课我们学习了平均分。'})
    db.session.add(event)
    db.session.flush()
    room.report = {'dimensions': [{'key': 'structure', 'score': 70, 'event_ids': [event.id]}]}
    db.session.commit()

    url = f'/api/classroom/sessions/{sid}/practice-plans'
    assert client.post(url, headers=auth(2), json={}).status_code == 404
    first = client.post(url, headers=auth(1), json={}).json['items']
    second = client.post(url, headers=auth(1), json={}).json['items']
    assert len(first) == len(second) == 1 and first[0]['id'] == second[0]['id']
    assert first[0]['target_kind'] == 'teacher_summary'
    assert first[0]['source_event_ids'] == [event.id]
    assert client.post('/api/classroom/sessions', headers=auth(2),
                       json={'audio_consent': True, 'camera_consent': True,
                             'practice_plan_id': first[0]['id']}).status_code == 404

    retest = client.post('/api/classroom/sessions', headers=auth(1),
                         json={'audio_consent': True, 'camera_consent': True,
                               'practice_plan_id': first[0]['id']})
    assert retest.status_code == 201
    retest_id = retest.json['session_id']
    assert client.post('/api/classroom/sessions', headers=auth(1),
                       json={'audio_consent': True, 'camera_consent': True,
                             'practice_plan_id': first[0]['id']}).status_code == 409
    db.session.add(ClassroomEvent(session_id=retest_id, event_key='retest-summary', kind='transcript',
                                  at_ms=3000, payload={'text': '最后回顾一下，平均分要求每份一样多。'}))
    retest_room = db.session.get(Classroom, retest_id)
    retest_room.state, retest_room.ended_at = 'ended', datetime.utcnow()
    db.session.commit()
    finish_retest_plans(retest_room)
    db.session.commit()
    plan = db.session.get(PracticePlan, first[0]['id'])
    assert plan.status == 'completed'
    assert plan.comparison['status'] == 'observed'
    assert plan.comparison['source_count'] == plan.comparison['retest_count'] == 1
    assert client.get('/api/classroom/practice-plans', headers=auth(2)).json['items'] == []


def test_missing_retest_transcript_is_insufficient_not_regression(app):
    db.session.add(User(id=1, account='practice', name='test', password_hash='unused'))
    db.session.commit()
    client = app.test_client()
    source = client.post('/api/classroom/sessions', headers=auth(1),
                         json={'audio_consent': True, 'camera_consent': True}).json
    room = db.session.get(Classroom, source['session_id'])
    room.state, room.ended_at = 'ended', datetime.utcnow()
    room.report_state, room.report_version = 'completed', 1
    room.report = {'dimensions': []}
    db.session.commit()
    plan = client.post(f'/api/classroom/sessions/{room.session_id}/practice-plans',
                       headers=auth(1), json={}).json['items'][0]
    retest_id = client.post('/api/classroom/sessions', headers=auth(1),
                            json={'audio_consent': True, 'camera_consent': True,
                                  'practice_plan_id': plan['id']}).json['session_id']
    retest = db.session.get(Classroom, retest_id)
    retest.state, retest.ended_at = 'ended', datetime.utcnow()
    finish_retest_plans(retest)
    db.session.commit()
    assert db.session.get(PracticePlan, plan['id']).comparison['status'] == 'insufficient'


def test_retest_rejects_changed_behavior_rule_version(app):
    db.session.add(User(id=1, account='practice-version', name='test', password_hash='unused'))
    db.session.commit()
    client = app.test_client()
    source_id = client.post('/api/classroom/sessions', headers=auth(1),
                            json={'audio_consent': True, 'camera_consent': True}).json['session_id']
    source = db.session.get(Classroom, source_id)
    source.state, source.ended_at = 'ended', datetime.utcnow()
    source.report_state, source.report_version = 'completed', 1
    source.report = {'dimensions': []}
    db.session.commit()
    plan_id = client.post(f'/api/classroom/sessions/{source_id}/practice-plans',
                          headers=auth(1), json={}).json['items'][0]['id']
    plan = db.session.get(PracticePlan, plan_id)
    plan.criteria = {**plan.criteria, 'behavior_version': 'teaching-behavior-old'}
    db.session.commit()
    retest_id = client.post('/api/classroom/sessions', headers=auth(1),
                            json={'audio_consent': True, 'camera_consent': True,
                                  'practice_plan_id': plan_id}).json['session_id']
    retest = db.session.get(Classroom, retest_id)
    retest.state, retest.ended_at = 'ended', datetime.utcnow()
    db.session.add(ClassroomEvent(session_id=retest_id, event_key='question', kind='transcript',
                                  at_ms=1000, payload={'text': '什么是平均分？'}))
    db.session.commit()
    finish_retest_plans(retest)
    db.session.commit()
    assert db.session.get(PracticePlan, plan_id).comparison['status'] == 'insufficient'
