import sys
import unittest
from datetime import timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from flask_jwt_extended import create_access_token  # noqa: E402


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    JWT_SECRET_KEY = 'test-secret'
    SEED_ON_STARTUP = False


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_login_requires_account_and_password(self):
        response = self.client.post('/api/auth/login', json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], '请填写账号和密码')

    def test_register_duplicate_and_login_three_times(self):
        payload = {
            'name': '测试用户',
            'account': 'auth-1',
            'password': 'secret123',
            'role': 'student',
        }
        self.assertEqual(self.client.post('/api/auth/register', json=payload).status_code, 201)
        duplicate = self.client.post('/api/auth/register', json=payload)
        self.assertEqual(duplicate.status_code, 409)

        for _ in range(3):
            response = self.client.post('/api/auth/login', json=payload)
            self.assertEqual(response.status_code, 200)
            token = response.get_json()['access_token']
            self.assertEqual(
                self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code,
                200,
            )

    def test_missing_expired_and_invalid_tokens_have_stable_codes(self):
        missing = self.client.get('/api/auth/me')
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.get_json()['code'], 'token_missing')

        with self.app.test_request_context():
            expired = create_access_token(identity='1', expires_delta=timedelta(seconds=-1))
        expired_response = self.client.get(
            '/api/auth/me',
            headers={'Authorization': f'Bearer {expired}'},
        )
        self.assertEqual(expired_response.status_code, 401)
        self.assertEqual(expired_response.get_json()['code'], 'token_expired')

        invalid = self.client.get(
            '/api/auth/me',
            headers={'Authorization': 'Bearer invalid-token'},
        )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.get_json()['code'], 'token_invalid')


if __name__ == '__main__':
    unittest.main()
