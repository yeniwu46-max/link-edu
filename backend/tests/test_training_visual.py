import base64
import sys
import tempfile
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from flask_jwt_extended import create_access_token  # noqa: E402
from models import Course, TrainingSession, User  # noqa: E402
from services.llm.deepseek import build_review_messages  # noqa: E402


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    JWT_SECRET_KEY = 'test-secret'
    SEED_ON_STARTUP = False
    DEEPSEEK_API_KEY = 'test-key'


def jpeg_data_url():
    image = Image.new('RGB', (32, 24), color=(40, 80, 120))
    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/jpeg;base64,{encoded}'


class TrainingVisualEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.evidence_temp = tempfile.TemporaryDirectory(prefix='link-training-visual-test-')
        self.addCleanup(self.evidence_temp.cleanup)
        self.app.instance_path = self.evidence_temp.name
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(
            account='visual-1',
            password_hash=generate_password_hash('password'),
            name='视觉教师',
            role='student',
        )
        course = Course(title='导入技能', category='微格教学', stage='专项01 · 导入', is_active=True)
        db.session.add_all([self.user, course])
        db.session.flush()
        self.session = TrainingSession(
            user_id=self.user.id,
            course_id=course.id,
            status='completed',
            duration_minutes=8,
            progress_percent=100,
            last_trained_at=datetime.utcnow(),
        )
        db.session.add(self.session)
        db.session.commit()
        self.client = self.app.test_client()
        self.token = create_access_token(identity=str(self.user.id))
        self.headers = {'Authorization': f'Bearer {self.token}'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_upload_visual_evidence_saves_jpeg_files(self):
        response = self.client.post(
            f'/api/training/sessions/{self.session.id}/visual-evidence',
            headers=self.headers,
            json={'frames': [jpeg_data_url(), jpeg_data_url()]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['frame_count'], 2)
        folder = Path(self.app.instance_path) / 'training_evidence' / str(self.session.id)
        self.assertEqual(len(list(folder.glob('*.jpg'))), 2)

    def test_upload_rejects_non_jpeg_payload(self):
        response = self.client.post(
            f'/api/training/sessions/{self.session.id}/visual-evidence',
            headers=self.headers,
            json={'frames': ['data:image/png;base64,aaa']},
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_replacement_preserves_previous_evidence(self):
        from services.training_visual import save_visual_evidence, list_visual_frame_paths

        save_visual_evidence(self.user.id, self.session.id, [jpeg_data_url()])
        before = list_visual_frame_paths(self.session.id)
        response = self.client.post(
            f'/api/training/sessions/{self.session.id}/visual-evidence',
            headers=self.headers,
            json={'frames': [jpeg_data_url(), 'data:image/png;base64,aaa']},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list_visual_frame_paths(self.session.id), before)
        self.assertTrue(before[0].is_file())

    def test_upload_cannot_write_another_users_evidence(self):
        other = User(account='visual-other', name='Other', role='student',
                     password_hash=generate_password_hash('password'))
        db.session.add(other)
        db.session.commit()
        other_token = create_access_token(identity=str(other.id))
        response = self.client.post(
            f'/api/training/sessions/{self.session.id}/visual-evidence',
            headers={'Authorization': f'Bearer {other_token}'},
            json={'frames': [jpeg_data_url()]},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse((Path(self.app.instance_path) / 'training_evidence').exists())

    def test_generate_review_messages_include_visual_observations(self):
        messages = build_review_messages({
            'course_title': '导入技能',
            'scene': '导入',
            'mode': 'fragment',
            'transcript_text': '教师先提出问题，再等待学生回答并追问原因。',
            'visual_observations': '关帧1：教师面向镜头，右手指向黑板。',
        })
        self.assertIn('visual_observations', messages[1]['content'])
        self.assertIn('面向镜头', messages[1]['content'])
        self.assertIn('关帧', messages[0]['content'])

    @patch('services.classroom_providers.chat')
    def test_collect_visual_observations_summarizes_frames(self, chat_mock):
        from services.training_visual import collect_visual_observations, save_visual_evidence

        chat_mock.return_value = {'observations': '教师面向镜头站立', 'confidence': 0.8}
        save_visual_evidence(self.user.id, self.session.id, [jpeg_data_url()])
        notes = collect_visual_observations(self.session.id, '导入技能')
        self.assertIn('关帧1', notes)
        self.assertIn('面向镜头', notes)
        chat_mock.assert_called()


if __name__ == '__main__':
    unittest.main()
