import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from config import Config
from extensions import db
from models import AiFeedback, Course, TrainingSession, User
from services.growth import build_growth
from werkzeug.security import generate_password_hash


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    JWT_SECRET_KEY = 'b06-test-secret'
    SEED_ON_STARTUP = False


class GrowthArchiveTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(
            account='b06-user',
            password_hash=generate_password_hash('password'),
            name='B06 测试用户',
            role='student',
        )
        self.course = Course(title='B06 课程', category='互动', is_active=True)
        db.session.add_all([self.user, self.course])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_all_range_includes_older_real_feedback_and_keeps_session_id(self):
        old_session = TrainingSession(
            user_id=self.user.id,
            course_id=self.course.id,
            status='completed',
            progress_percent=100,
            duration_minutes=10,
            last_trained_at=datetime.utcnow() - timedelta(days=45),
        )
        recent_session = TrainingSession(
            user_id=self.user.id,
            course_id=self.course.id,
            status='completed',
            progress_percent=100,
            duration_minutes=8,
            last_trained_at=datetime.utcnow() - timedelta(days=2),
        )
        db.session.add_all([old_session, recent_session])
        db.session.flush()
        db.session.add_all([
            AiFeedback(
                user_id=self.user.id,
                session_id=old_session.id,
                overall_score=78,
                clarity_score=78,
                pace_score=78,
                interaction_score=78,
                suggestion='older',
                created_at=datetime.utcnow() - timedelta(days=45),
            ),
            AiFeedback(
                user_id=self.user.id,
                session_id=recent_session.id,
                overall_score=86,
                clarity_score=86,
                pace_score=86,
                interaction_score=86,
                suggestion='recent',
                created_at=datetime.utcnow() - timedelta(days=2),
            ),
        ])
        db.session.commit()

        recent = build_growth(self.user, '30d')
        all_time = build_growth(self.user, 'all')

        self.assertEqual(len(recent['records']), 1)
        self.assertEqual(len(all_time['records']), 2)
        self.assertEqual(all_time['records'][0]['session_id'], recent_session.id)
        self.assertGreater(len(all_time['heatmap']), len(recent['heatmap']))


if __name__ == '__main__':
    unittest.main()
