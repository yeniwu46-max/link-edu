import unittest
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from config import Config
from extensions import db
from models import Resource, User
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    JWT_SECRET_KEY = 'b07-test-secret'
    SEED_ON_STARTUP = False


class ResourceLibraryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(
            account='b07-user',
            password_hash=generate_password_hash('password'),
            name='B07 测试用户',
            role='student',
        )
        db.session.add(self.user)
        db.session.add_all([
            Resource(title='真实教案', category='教案', description='教案说明', file_url='/files/lesson-plan.pdf'),
            Resource(title='真实素材', category='素材', description='素材说明', file_url='https://example.com/materials'),
            Resource(title='真实报告', category='报告', description='报告说明'),
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_resource_api_keeps_real_file_url_and_required_categories(self):
        headers = {'Authorization': f'Bearer {create_access_token(identity=str(self.user.id))}'}
        response = self.app.test_client().get('/api/resources', headers=headers)

        self.assertEqual(response.status_code, 200)
        items = response.get_json()['items']
        self.assertEqual({item['category'] for item in items}, {'教案', '素材', '报告'})
        self.assertEqual(items[0]['file_url'], '/files/lesson-plan.pdf')
        self.assertEqual(items[1]['file_url'], 'https://example.com/materials')
        self.assertIsNone(items[2]['file_url'])


if __name__ == '__main__':
    unittest.main()
