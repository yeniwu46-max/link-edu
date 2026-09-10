import unittest
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from config import Config
from extensions import db
from flask_jwt_extended import create_access_token
from models import User
from werkzeug.security import generate_password_hash


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    JWT_SECRET_KEY = 'b08-test-secret'
    SEED_ON_STARTUP = False


class ProfilePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(
            account='b08-user',
            password_hash=generate_password_hash('password'),
            name='B08 测试用户',
            role='student',
        )
        db.session.add(self.user)
        db.session.commit()
        self.headers = {'Authorization': f'Bearer {create_access_token(identity=str(self.user.id))}'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_profile_update_survives_a_fresh_read(self):
        payload = {
            'name': '已保存姓名',
            'school': '已保存学校',
            'major': '小学教育',
            'grade': '本科三年级',
            'bio': '真实保存的个人简介',
            'role': 'teacher',
        }
        saved = self.app.test_client().patch('/api/profile', json=payload, headers=self.headers)
        self.assertEqual(saved.status_code, 200)

        db.session.remove()
        loaded = self.app.test_client().get('/api/profile', headers=self.headers)
        self.assertEqual(loaded.status_code, 200)
        profile = loaded.get_json()
        self.assertEqual(profile['name'], payload['name'])
        self.assertEqual(profile['school'], payload['school'])
        self.assertEqual(profile['role'], payload['role'])
        self.assertEqual(profile['bio'], payload['bio'])


if __name__ == '__main__':
    unittest.main()
