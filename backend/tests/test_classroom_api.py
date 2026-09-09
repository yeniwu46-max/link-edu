from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token
from extensions import db
from models import User
from classroom_models import ClassroomTicket
from classroom_routes import consume_ticket
from services.classroom_runtime import proactive_allowed
from test_classroom_base import app


def headers(uid):
    return {'Authorization': 'Bearer ' + create_access_token(identity=str(uid))}


def test_ownership_and_single_use_ticket(app):
    for i in (1, 2):
        db.session.add(User(id=i, account=str(i), name='test', password_hash='not-used'))
    db.session.commit()
    client = app.test_client()
    room = client.post('/api/classroom/sessions', headers=headers(1), json={'audio_consent': True, 'camera_consent': True}).json
    sid = room['session_id']
    assert client.get(f'/api/classroom/sessions/{sid}', headers=headers(2)).status_code == 404
    assert client.post(f'/api/classroom/sessions/{sid}/ticket', headers=headers(2)).status_code == 404
    token = client.post(f'/api/classroom/sessions/{sid}/ticket', headers=headers(1)).json['ticket']
    assert consume_ticket(token).session_id == sid
    assert consume_ticket(token) is None
    token = client.post(f'/api/classroom/sessions/{sid}/ticket', headers=headers(1)).json['ticket']
    ClassroomTicket.query.update({'expires_at': datetime.utcnow() - timedelta(seconds=1)})
    db.session.commit()
    assert consume_ticket(token) is None


def test_proactive_limits():
    assert not proactive_allowed(19, -45, 0, True)
    assert not proactive_allowed(40, 0, 0, True)
    assert proactive_allowed(60, 0, 0, True)
    assert not proactive_allowed(600, 0, 6, True)
    assert not proactive_allowed(600, 0, 0, False)


def test_legacy_correction_is_read_only_and_owned(app):
    from models import AiFeedback
    for i in (1, 2):
        db.session.add(User(id=i, account=str(i), name='test', password_hash='unused'))
    row = AiFeedback(user_id=1, overall_score=75, suggestion='原演示记录')
    db.session.add(row)
    db.session.commit()
    client = app.test_client()
    url = f'/api/feedbacks/{row.id}/regenerate'
    assert client.post(url, headers=headers(2), json={}).status_code == 404
    for _ in range(2):
        assert client.post(url, headers=headers(1), json={'notes':['pace_ok']}).status_code == 409
    db.session.refresh(row)
    assert row.overall_score == 75 and row.suggestion == '原演示记录'
