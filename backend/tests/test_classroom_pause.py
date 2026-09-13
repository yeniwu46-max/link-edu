from datetime import datetime, timedelta
from test_classroom_base import app
from test_classroom_api import headers
from extensions import db
from models import User
from classroom_models import Classroom, ClassroomEvent


def test_pause_freezes_duration_and_is_idempotent(app):
    db.session.add(User(id=1, account='pause-test', name='test', password_hash='unused'))
    db.session.commit()
    client = app.test_client()
    sid = client.post('/api/classroom/sessions', headers=headers(1), json={
        'audio_consent': True, 'camera_consent': True}).json['session_id']
    room = db.session.get(Classroom, sid)
    room.started_at = datetime.utcnow() - timedelta(seconds=5)
    db.session.commit()
    url = f'/api/classroom/sessions/{sid}'
    result = client.post(url + '/pause', headers=headers(1), json={})
    assert result.status_code == 200
    assert result.json['state'] == 'paused'
    first = result.json['active_elapsed']
    assert client.post(url + '/pause', headers=headers(1), json={}).json['active_elapsed'] == first
    assert ClassroomEvent.query.filter_by(session_id=sid, kind='pause').count() == 1
    assert client.post(url + '/finish', headers=headers(1), json={}).status_code == 409
    assert client.post(url + '/resume', headers=headers(1), json={}).status_code == 200
    assert client.post(url + '/resume', headers=headers(1), json={}).status_code == 200
    assert ClassroomEvent.query.filter_by(session_id=sid, kind='resume').count() == 1
    assert client.post(url + '/pause', headers=headers(2), json={}).status_code == 404


def test_clock_keeps_wall_event_coordinates():
    from services.classroom_clock import active_seconds
    events = [dict(type='pause', at_ms=5000), dict(type='resume', at_ms=65000),
              dict(type='pause', at_ms=70000)]
    assert active_seconds(events, 100) == 10
    assert active_seconds([], 12) == 12
