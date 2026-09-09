import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db, jwt  # noqa: E402
from flask_jwt_extended import create_access_token  # noqa: E402
from models import AiFeedback, Course, TrainingSession, User  # noqa: E402
from services.llm.deepseek import DIMENSION_KEYS  # noqa: E402
from services import training as training_service  # noqa: E402
from services.llm.deepseek import DeepSeekReviewError  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    JWT_SECRET_KEY = 'test-secret'
    SEED_ON_STARTUP = False
    DEEPSEEK_API_KEY = 'test-key'


def fake_report(review_input, *, config=None):
    return {
        'demo': False,
        'source': 'deepseek',
        'mode': review_input.get('mode', 'fragment'),
        'mode_label': '片段练习',
        'scene': review_input.get('scene', '导入'),
        'duration_minutes': review_input.get('duration_minutes'),
        'overall_score': 82,
        'dimensions': [
            {'key': key, 'label': key, 'score': 82, 'evidence': '来自课堂材料', 'brief': 'brief'}
            for key in DIMENSION_KEYS
        ],
        'summary': '课堂主线清楚。',
        'strengths': ['主线清楚'],
        'problems': ['收束略快'],
        'fixes': ['增加总结停顿'],
        'next_action': '结尾增加一次目标回扣。',
        'suggestion': '结尾增加一次目标回扣。',
        'sections': [{'title': '综合判断', 'body': '课堂主线清楚。'}],
    }


class AiReviewRouteTests(unittest.TestCase):
    def setUp(self):
        with training_service._ai_review_guard:
            training_service._ai_review_inflight.clear()
            training_service._ai_review_attempts.clear()
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(
            account='student-1',
            password_hash=generate_password_hash('password'),
            name='测试教师',
            role='student',
        )
        course = Course(title='提问技能', category='微格教学', is_active=True)
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
        db.session.flush()
        db.session.add(AiFeedback(
            user_id=self.user.id,
            session_id=self.session.id,
            overall_score=70,
            report_json=json.dumps({'demo': True, 'dimensions': []}),
        ))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _auth_headers(self):
        with self.app.test_request_context():
            token = create_access_token(identity=str(self.user.id))
        return {'Authorization': f'Bearer {token}'}

    def _save_real_report(self, feedback=None, *, created_at=None, score=82, problems=None):
        feedback = feedback or AiFeedback.query.filter_by(session_id=self.session.id).first()
        report = fake_report({'mode': 'fragment', 'scene': '提问'})
        report.update({
            'source': 'deepseek',
            'generation_status': 'succeeded',
            'overall_score': score,
            'problems': problems or ['收束略快'],
            'fixes': ['增加总结停顿'],
            'next_action': '结尾增加一次目标回扣。',
        })
        feedback.overall_score = score
        feedback.report_json = json.dumps(report, ensure_ascii=False)
        if created_at is not None:
            feedback.created_at = created_at
        db.session.commit()
        return feedback

    def test_classifies_current_and_history_questions(self):
        self.assertEqual(training_service.classify_question_scope('为什么这次提问质量较低？'), 'current')
        self.assertEqual(training_service.classify_question_scope('我近30天有没有进步？'), 'history')
        self.assertEqual(training_service.classify_question_scope('和上次相比有什么变化？'), 'history')

    def test_builds_current_context_without_history(self):
        feedback = self._save_real_report()
        context = training_service.build_review_question_context(
            self.user,
            feedback,
            '为什么这次提问质量较低？',
        )

        self.assertEqual(context['scope'], 'current')
        self.assertEqual(context['current']['course_title'], '提问技能')
        self.assertEqual(context['current']['scene'], '提问')
        self.assertEqual(context['current']['duration_minutes'], 8)
        self.assertEqual(context['current']['progress_percent'], 100)
        self.assertEqual(context['current']['summary'], '课堂主线清楚。')
        self.assertEqual(context['current']['problems'], ['收束略快'])
        self.assertEqual(context['current']['fixes'], ['增加总结停顿'])
        self.assertEqual(len(context['current']['dimensions']), len(DIMENSION_KEYS))
        self.assertNotIn('recent_30_days', context)

    def test_history_context_contains_compact_recent_summary_and_excludes_current(self):
        current_feedback = self._save_real_report()
        now = datetime.utcnow()
        for index, score in enumerate((76, 84, 90)):
            course = Course(title=f'历史课程{index}', category='微格教学', is_active=True)
            db.session.add(course)
            db.session.flush()
            session = TrainingSession(
                user_id=self.user.id,
                course_id=course.id,
                status='completed',
                duration_minutes=8,
                progress_percent=100,
                last_trained_at=now - timedelta(days=index + 1),
            )
            db.session.add(session)
            db.session.flush()
            report = fake_report({'mode': 'fragment'})
            report.update({
                'source': 'deepseek',
                'generation_status': 'succeeded',
                'overall_score': score,
                'problems': ['提问等待时间不足' if index < 2 else '结尾收束偏快'],
            })
            db.session.add(AiFeedback(
                user_id=self.user.id,
                session_id=session.id,
                overall_score=score,
                report_json=json.dumps(report, ensure_ascii=False),
                created_at=now - timedelta(days=index + 1),
            ))
        db.session.commit()

        context = training_service.build_review_question_context(
            self.user,
            current_feedback,
            '我近30天有没有进步？',
        )

        summary = context['recent_30_days']
        self.assertEqual(context['scope'], 'history')
        self.assertEqual(summary['record_count'], 3)
        self.assertEqual(summary['average_overall_score'], 83.3)
        self.assertEqual(summary['first_score'], 90)
        self.assertEqual(summary['latest_score'], 76)
        self.assertEqual(len(summary['records']), 3)
        self.assertNotIn(current_feedback.id, [item['id'] for item in summary['records']])
        self.assertIn('提问等待时间不足', summary['recurring_problems'])

    def test_asks_question_using_current_context_without_writing_feedback(self):
        feedback = self._save_real_report()
        original_report = feedback.report_json
        original_score = feedback.overall_score
        with patch('services.training.answer_review_question', return_value='本次提问后的解释。') as answer:
            response = self.client.post(
                f'/api/feedbacks/{feedback.id}/ask',
                headers=self._auth_headers(),
                json={'question': '为什么这次提问质量较低？'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'feedback_id': feedback.id,
            'scope': 'current',
            'answer': '本次提问后的解释。',
        })
        answer.assert_called_once()
        context = answer.call_args.args[1]
        self.assertNotIn('recent_30_days', context)
        db.session.refresh(feedback)
        self.assertEqual(feedback.report_json, original_report)
        self.assertEqual(feedback.overall_score, original_score)

    def test_asks_history_question_with_recent_context(self):
        feedback = self._save_real_report()
        with patch('services.training.answer_review_question', return_value='近30天总体有进步。') as answer:
            response = self.client.post(
                f'/api/feedbacks/{feedback.id}/ask',
                headers=self._auth_headers(),
                json={'question': '和上次相比有什么变化？'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['scope'], 'history')
        self.assertIn('recent_30_days', answer.call_args.args[1])

    def test_rejects_invalid_or_unready_question_requests(self):
        feedback = AiFeedback.query.filter_by(session_id=self.session.id).first()
        response = self.client.post(
            f'/api/feedbacks/{feedback.id}/ask',
            headers=self._auth_headers(),
            json={'question': '   '},
        )
        self.assertEqual(response.status_code, 400)

        with patch('services.training.answer_review_question') as answer:
            response = self.client.post(
                f'/api/feedbacks/{feedback.id}/ask',
                headers=self._auth_headers(),
                json={'question': '请解释评分。'},
            )
        self.assertEqual(response.status_code, 409)
        answer.assert_not_called()

    def test_question_endpoint_enforces_feedback_ownership_and_provider_failure(self):
        other_user = User(
            account='student-2',
            password_hash=generate_password_hash('password'),
            name='其他教师',
            role='student',
        )
        db.session.add(other_user)
        db.session.flush()
        other_feedback = AiFeedback(
            user_id=other_user.id,
            session_id=self.session.id,
            overall_score=80,
            report_json=json.dumps({
                'source': 'deepseek',
                'generation_status': 'succeeded',
                'dimensions': fake_report({})['dimensions'],
            }),
        )
        db.session.add(other_feedback)
        db.session.commit()

        with patch('services.training.answer_review_question') as answer:
            response = self.client.post(
                f'/api/feedbacks/{other_feedback.id}/ask',
                headers=self._auth_headers(),
                json={'question': '请解释评分。'},
            )
        self.assertEqual(response.status_code, 404)
        answer.assert_not_called()

        feedback = self._save_real_report()
        with patch(
            'services.training.answer_review_question',
            side_effect=DeepSeekReviewError('provider unavailable'),
        ):
            response = self.client.post(
                f'/api/feedbacks/{feedback.id}/ask',
                headers=self._auth_headers(),
                json={'question': '请解释评分。'},
            )
        self.assertEqual(response.status_code, 502)

    def test_generates_and_persists_real_report_for_owned_completed_session(self):
        with patch('services.training.generate_review_report', side_effect=fake_report):
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={
                    'transcript_text': '教师先提出问题，再等待学生回答并追问原因。',
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['feedback']['report']['source'], 'deepseek')
        self.assertEqual(body['feedback']['overall_score'], 82)
        saved = AiFeedback.query.filter_by(session_id=self.session.id).first()
        self.assertFalse(json.loads(saved.report_json)['demo'])

    def test_generates_report_from_owned_session_without_text_input(self):
        with patch('services.training.generate_review_report', side_effect=fake_report) as generate:
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['feedback']['report']['source'], 'deepseek')
        generate.assert_called_once()
        review_input = generate.call_args.args[0]
        self.assertEqual(review_input['course_title'], '提问技能')
        self.assertEqual(review_input['duration_minutes'], 8)
        self.assertEqual(review_input['progress_percent'], 100)
        self.assertEqual(review_input['status'], 'completed')

    def test_returns_existing_real_report_without_calling_deepseek_again(self):
        with patch('services.training.generate_review_report', side_effect=fake_report) as generate:
            first = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            )
            second = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '这是另一份足够长的课堂材料，但已经成功生成后不应再次调用模型计费。'},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json()['feedback']['id'], second.get_json()['feedback']['id'])
        generate.assert_called_once()

    def test_retries_stale_generating_report(self):
        feedback = AiFeedback.query.filter_by(session_id=self.session.id).first()
        feedback.overall_score = 0
        feedback.report_json = json.dumps({
            'source': 'deepseek',
            'demo': False,
            'generation_status': 'generating',
            'dimensions': [],
        })
        db.session.commit()

        with patch('services.training.generate_review_report', side_effect=fake_report) as generate:
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['feedback']['report']['generation_status'], 'succeeded')
        generate.assert_called_once()

    def test_explicit_regenerate_calls_deepseek_again(self):
        reports = [
            fake_report({'mode': 'fragment'}),
            {**fake_report({'mode': 'fragment'}), 'overall_score': 88},
        ]
        reports[1]['dimensions'] = [
            {**item, 'score': 88}
            for item in reports[1]['dimensions']
        ]

        with patch('services.training.generate_review_report', side_effect=reports) as generate:
            first = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            )
            second = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={
                    'transcript_text': '教师调整导入后再次提问，并让学生说明推理过程。',
                    'regenerate': True,
                },
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()['feedback']['overall_score'], 88)
        self.assertEqual(generate.call_count, 2)

    def test_persists_generating_status_before_calling_deepseek(self):
        observed_statuses = []

        def inspect_status(review_input, *, config=None):
            row = AiFeedback.query.filter_by(session_id=self.session.id).first()
            observed_statuses.append(json.loads(row.report_json).get('generation_status'))
            return fake_report(review_input, config=config)

        with patch('services.training.generate_review_report', side_effect=inspect_status):
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(observed_statuses, ['generating'])
        self.assertEqual(response.get_json()['feedback']['report']['generation_status'], 'succeeded')

    def test_persists_failed_status_when_deepseek_fails(self):
        with patch(
            'services.training.generate_review_report',
            side_effect=DeepSeekReviewError('provider unavailable'),
        ):
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            )

        self.assertEqual(response.status_code, 502)
        saved = AiFeedback.query.filter_by(session_id=self.session.id).first()
        report = json.loads(saved.report_json)
        self.assertEqual(report['generation_status'], 'failed')
        self.assertEqual(report['generation_error'], 'AI 评课生成失败，请稍后重试')

    def test_insufficient_report_does_not_replace_saved_score_with_zero(self):
        insufficient_report = {
            **fake_report({'mode': 'fragment'}),
            'overall_score': None,
            'insufficient_evidence': True,
            'dimensions': [
                {**item, 'score': 0, 'evidence': '证据不足'}
                for item in fake_report({'mode': 'fragment'})['dimensions']
            ],
        }

        with patch('services.training.generate_review_report', return_value=insufficient_report):
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '请帮我生成一份完整的 AI 评课报告和六维评分。'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()['feedback']['overall_score'])
        saved = AiFeedback.query.filter_by(session_id=self.session.id).first()
        self.assertEqual(saved.overall_score, 70)

    def test_insufficient_report_is_excluded_from_dashboard_history(self):
        feedback = AiFeedback.query.filter_by(session_id=self.session.id).first()
        feedback.overall_score = 0
        feedback.report_json = json.dumps({
            'source': 'deepseek',
            'demo': False,
            'dimensions': [
                {'key': key, 'score': 0, 'evidence': '证据不足'}
                for key in DIMENSION_KEYS
            ],
        })
        db.session.commit()

        overview = self.client.get('/api/dashboard/overview', headers=self._auth_headers())
        growth = self.client.get('/api/growth', headers=self._auth_headers())

        self.assertEqual(overview.status_code, 200)
        self.assertIsNone(overview.get_json()['ai_feedback'])
        self.assertEqual(overview.get_json()['growth_records'], [])
        self.assertEqual(growth.status_code, 200)
        self.assertEqual(growth.get_json()['points'], [])

    def test_rejects_non_boolean_regenerate_flag(self):
        with patch('services.training.generate_review_report', side_effect=fake_report) as generate:
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={
                    'transcript_text': '教师先提出问题，再等待学生回答并追问原因。',
                    'regenerate': 'yes',
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'regenerate 必须是布尔值')
        generate.assert_not_called()

    def test_rejects_non_object_json(self):
        with patch('services.training.generate_review_report') as generate:
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json=['课堂材料'],
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], '请求内容必须是 JSON 对象')
        generate.assert_not_called()

    def test_rejects_non_string_transcript(self):
        with patch('services.training.generate_review_report') as generate:
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': ['不是', '文本']},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], '课堂转写必须是文本')
        generate.assert_not_called()

    def test_allows_short_or_empty_material_before_calling_deepseek(self):
        with patch('services.training.generate_review_report', side_effect=fake_report) as generate:
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '太短'},
            )

        self.assertEqual(response.status_code, 200)
        generate.assert_called_once()

    def test_returns_not_found_for_session_not_owned_by_user(self):
        other_user = User(
            account='student-2',
            password_hash=generate_password_hash('password'),
            name='其他教师',
            role='student',
        )
        db.session.add(other_user)
        db.session.flush()
        other_session = TrainingSession(
            user_id=other_user.id,
            course_id=self.session.course_id,
            status='completed',
            duration_minutes=8,
            progress_percent=100,
        )
        db.session.add(other_session)
        db.session.commit()

        with patch('services.training.generate_review_report') as generate:
            response = self.client.post(
                f'/api/training/sessions/{other_session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            )

        self.assertEqual(response.status_code, 404)
        generate.assert_not_called()

    def test_rejects_session_that_is_not_completed(self):
        self.session.status = 'in_progress'
        db.session.commit()

        with patch('services.training.generate_review_report') as generate:
            response = self.client.post(
                f'/api/training/sessions/{self.session.id}/ai-review',
                headers=self._auth_headers(),
                json={'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            )

        self.assertEqual(response.status_code, 409)
        generate.assert_not_called()

    def test_rate_limits_repeated_failed_model_calls(self):
        with patch(
            'services.training.generate_review_report',
            side_effect=DeepSeekReviewError('provider unavailable'),
        ) as generate:
            responses = [
                self.client.post(
                    f'/api/training/sessions/{self.session.id}/ai-review',
                    headers=self._auth_headers(),
                    json={'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
                )
                for _ in range(6)
            ]

        self.assertTrue(all(response.status_code == 502 for response in responses[:5]))
        self.assertEqual(responses[5].status_code, 429)
        self.assertEqual(generate.call_count, 5)


if __name__ == '__main__':
    unittest.main()
