from datetime import datetime

import pytest
from flask_jwt_extended import create_access_token

from extensions import db
from models import Course, TrainingSession, User
from test_classroom_base import app
from werkzeug.security import generate_password_hash


def auth_headers(app, user_id):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def course_user(app):
    with app.app_context():
        user = User(
            account='b04-user',
            password_hash=generate_password_hash('password'),
            name='B04 测试用户',
            role='student',
        )
        active = Course(
            title='提问技能',
            category='微格教学 · 专项',
            stage='专项05 · 提问',
            source='测试大纲',
            source_url='https://example.test/course',
            lesson_count=8,
            is_active=True,
        )
        inactive = Course(
            title='已下线课程',
            category='微格教学 · 专项',
            stage='专项99 · 下线',
            lesson_count=8,
            is_active=False,
        )
        db.session.add_all([user, active, inactive])
        db.session.flush()
        session = TrainingSession(
            user_id=user.id,
            course_id=active.id,
            status='in_progress',
            progress_percent=42,
            duration_minutes=3,
            started_at=datetime.utcnow(),
            last_trained_at=datetime.utcnow(),
        )
        db.session.add(session)
        db.session.commit()
        return user.id, active.id, inactive.id


def test_courses_exposes_only_active_courses_with_user_progress_and_source(app, course_user):
    user_id, active_id, inactive_id = course_user
    response = app.test_client().get('/api/courses', headers=auth_headers(app, user_id))

    assert response.status_code == 200
    items = response.get_json()['items']
    ids = {item['id'] for item in items}
    assert active_id in ids
    assert inactive_id not in ids
    active = next(item for item in items if item['id'] == active_id)
    assert active['progress_percent'] == 42
    assert active['status'] == 'in_progress'
    assert active['source'] == '测试大纲'
    assert active['source_url'] == 'https://example.test/course'


def test_start_training_accepts_valid_course_and_rejects_invalid_course_id(app, course_user):
    user_id, active_id, _inactive_id = course_user
    client = app.test_client()
    headers = auth_headers(app, user_id)

    started = client.post(
        '/api/training/sessions',
        headers=headers,
        json={'course_id': active_id},
    )
    assert started.status_code == 201
    assert started.get_json()['session']['course_id'] == active_id

    malformed = client.post(
        '/api/training/sessions',
        headers=headers,
        json={'course_id': 'not-a-number'},
    )
    assert malformed.status_code == 400
    assert malformed.get_json()['message'] == '课程参数无效'

    non_positive = client.post(
        '/api/training/sessions',
        headers=headers,
        json={'course_id': 0},
    )
    assert non_positive.status_code == 400
    assert non_positive.get_json()['message'] == '课程参数无效'

    missing = client.post(
        '/api/training/sessions',
        headers=headers,
        json={'course_id': 999999},
    )
    assert missing.status_code == 404
    assert missing.get_json()['message'] == '课程不存在'
