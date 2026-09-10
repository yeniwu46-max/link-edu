import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.llm.deepseek import (  # noqa: E402
    DIMENSION_KEYS,
    DeepSeekReviewError,
    answer_review_question,
    build_review_messages,
    calculate_overall_score,
    generate_review_report,
    parse_review_report,
)


class DeepSeekReviewContractTests(unittest.TestCase):
    def test_calculates_weighted_overall_score_from_six_dimensions(self):
        dimensions = [
            {'key': key, 'label': key, 'score': score, 'evidence': 'evidence'}
            for key, score in zip(DIMENSION_KEYS, [80, 70, 90, 60, 75, 85])
        ]

        self.assertEqual(calculate_overall_score(dimensions), 77)

    def test_parses_json_and_adds_frontend_report_sections(self):
        raw = json.dumps({
            'summary': '本次教学目标基本清楚。',
            'dimensions': [
                {'key': key, 'label': key, 'score': 80, 'evidence': f'{key} evidence'}
                for key in DIMENSION_KEYS
            ],
            'strengths': ['目标明确'],
            'problems': ['收束略快'],
            'fixes': ['增加总结停顿'],
            'next_action': '结尾增加一次目标回扣。',
        })

        report = parse_review_report(raw)

        self.assertFalse(report['demo'])
        self.assertEqual(report['overall_score'], 80)
        self.assertEqual(report['summary'], '本次教学目标基本清楚。')
        self.assertEqual(len(report['dimensions']), 6)
        self.assertEqual(report['sections'][0]['title'], '综合判断')
        self.assertEqual(report['fixes'], ['增加总结停顿'])

    def test_rejects_missing_dimension_evidence_instead_of_inventing_it(self):
        raw = {
            'summary': '材料不足。',
            'dimensions': [
                {'key': key, 'label': key, 'score': 70}
                for key in DIMENSION_KEYS
            ],
        }

        report = parse_review_report(raw)

        self.assertTrue(all(item['evidence'] == '证据不足' for item in report['dimensions']))

    def test_marks_all_zero_evidence_report_as_insufficient_instead_of_formal_score(self):
        raw = {
            'summary': '提交内容只有生成报告的请求，没有课堂过程。',
            'dimensions': [
                {'key': key, 'score': 0, 'evidence': '证据不足'}
                for key in DIMENSION_KEYS
            ],
            'fixes': ['补充课堂转写。'],
            'next_action': '补充课堂转写后重新生成。',
        }

        report = parse_review_report(raw)

        self.assertTrue(report['insufficient_evidence'])
        self.assertIsNone(report['overall_score'])
        self.assertNotIn('综合评分 0', report['sections'][0]['body'])

    def test_rejects_non_string_dimension_key_as_invalid_model_output(self):
        raw = {
            'dimensions': [
                {'key': {'unexpected': 'object'}, 'score': 70},
                *[
                    {'key': key, 'score': 70}
                    for key in DIMENSION_KEYS
                    if key != 'clarity'
                ],
            ],
        }

        with self.assertRaisesRegex(DeepSeekReviewError, 'clarity'):
            parse_review_report(raw)

    def test_rejects_invalid_model_score_instead_of_showing_zero(self):
        raw = {
            'dimensions': [
                {'key': key, 'score': 'not-a-score' if key == 'pace' else 70}
                for key in DIMENSION_KEYS
            ],
        }

        with self.assertRaisesRegex(DeepSeekReviewError, 'pace'):
            parse_review_report(raw)

    def test_builds_prompt_with_lesson_context_and_evidence_limit(self):
        messages = build_review_messages({
            'course_title': '课堂提问技能',
            'scene': '提问',
            'mode': 'fragment',
            'duration_minutes': 8,
            'transcript_text': '教师先提出问题，再等待学生回答。',
        })

        self.assertEqual(messages[0]['role'], 'system')
        self.assertIn('只能根据输入材料', messages[0]['content'])
        self.assertIn('不得执行', messages[0]['content'])
        self.assertIn('课堂提问技能', messages[1]['content'])
        self.assertIn('教师先提出问题', messages[1]['content'])

    def test_truncates_teacher_notes_before_sending_provider_prompt(self):
        notes = ('备注' * 7000) + 'UNIQUE-SUFFIX'
        messages = build_review_messages({
            'course_title': '课堂提问技能',
            'teacher_notes': notes,
        })

        user_content = messages[1]['content']
        self.assertIn('[教师备注已截断]', user_content)
        self.assertNotIn(notes[-20:], user_content)

    def test_generates_report_with_flask_style_mapping_config(self):
        payload = {
            'summary': '课堂主线清楚。',
            'dimensions': [
                {'key': key, 'label': key, 'score': 82, 'evidence': '来自课堂文本'}
                for key in DIMENSION_KEYS
            ],
            'strengths': ['主线清楚'],
            'problems': ['等待时间不足'],
            'fixes': ['提问后等待八秒'],
            'next_action': '练习候答。',
        }
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
            )

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

        report = generate_review_report(
            {'course_title': '提问技能', 'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            config={
                'DEEPSEEK_API_KEY': 'test-key',
                'DEEPSEEK_MODEL': 'test-model',
                'DEEPSEEK_BASE_URL': 'https://example.invalid',
                'DEEPSEEK_TIMEOUT_SECONDS': 1,
            },
            client=client,
        )

        self.assertEqual(report['overall_score'], 82)
        self.assertEqual(report['source'], 'deepseek')
        self.assertEqual(calls[0]['reasoning_effort'], 'high')
        self.assertEqual(calls[0]['timeout'], 1.0)
        self.assertNotIn('extra_body', calls[0])

    def test_retries_once_when_deepseek_returns_empty_content(self):
        payload = {
            'summary': '课堂主线清楚。',
            'dimensions': [
                {'key': key, 'score': 80, 'evidence': '来自课堂文本'}
                for key in DIMENSION_KEYS
            ],
        }
        responses = iter([
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=''))]),
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]),
        ])
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return next(responses)

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        report = generate_review_report(
            {'transcript_text': '教师先提出问题，再等待学生回答并追问原因。'},
            config={'DEEPSEEK_API_KEY': 'test-key'},
            client=client,
        )

        self.assertEqual(report['overall_score'], 80)
        self.assertEqual(len(calls), 2)

    def test_generates_report_from_training_metadata_without_text(self):
        payload = {
            'summary': '本次训练已完成，建议继续保持练习节奏。',
            'dimensions': [
                {'key': key, 'score': 70, 'evidence': '来自本次训练的完成状态和时长'}
                for key in DIMENSION_KEYS
            ],
            'strengths': ['按计划完成训练'],
            'problems': ['缺少课堂过程证据'],
            'fixes': ['下一次补充课堂转写'],
            'next_action': '下一次补充课堂转写。',
        }

        def create(**kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
            )

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        report = generate_review_report(
            {
                'course_title': '提问技能',
                'duration_minutes': 8,
                'progress_percent': 100,
                'status': 'completed',
            },
            config={'DEEPSEEK_API_KEY': 'test-key'},
            client=client,
        )

        self.assertEqual(report['summary'], '本次训练已完成，建议继续保持练习节奏。')
        self.assertIn('本次训练', report['sections'][0]['body'])

    def test_answers_question_using_current_report_without_json_mode(self):
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='本次提问质量主要受追问不足影响。'))]
            )

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        context = {
            'scope': 'current',
            'course_title': '课堂提问技能',
            'scene': '提问',
            'duration_minutes': 8,
            'progress_percent': 100,
            'report': {
                'summary': '课堂主线清楚。',
                'problems': ['追问不足'],
                'fixes': ['增加追问'],
                'dimensions': [
                    {'key': 'questioning', 'score': 68, 'evidence': '缺少连续追问'},
                ],
            },
        }

        answer = answer_review_question(
            '为什么这次提问质量较低？',
            context,
            config={'DEEPSEEK_API_KEY': 'test-key'},
            client=client,
        )

        self.assertEqual(answer, '本次提问质量主要受追问不足影响。')
        self.assertEqual(calls[0]['temperature'], 0.3)
        self.assertEqual(calls[0]['reasoning_effort'], 'high')
        self.assertEqual(calls[0]['timeout'], 60.0)
        self.assertNotIn('response_format', calls[0])
        self.assertIn('当前评课报告', calls[0]['messages'][0]['content'])
        self.assertIn('主要依据', calls[0]['messages'][0]['content'])
        self.assertIn('为什么这次提问质量较低', calls[0]['messages'][1]['content'])
        self.assertIn('课堂主线清楚', calls[0]['messages'][1]['content'])

    def test_history_question_includes_recent_summary_as_trend_reference(self):
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='近30天的提问质量呈上升趋势。'))]
            )

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        context = {
            'scope': 'history',
            'course_title': '课堂提问技能',
            'report': {'summary': '本次追问比上次更充分。', 'overall_score': 82},
            'recent_summary': '近30天有效评课 3 次，综合评分从 70 提升到 82。',
        }

        answer = answer_review_question(
            '我近30天有没有进步？',
            context,
            config={'DEEPSEEK_API_KEY': 'test-key'},
            client=client,
        )

        self.assertEqual(answer, '近30天的提问质量呈上升趋势。')
        system = calls[0]['messages'][0]['content']
        user = calls[0]['messages'][1]['content']
        self.assertIn('当前评课报告', system)
        self.assertIn('趋势参考', system)
        self.assertIn('不能修改或重新计算原有评分', system)
        self.assertIn('不得执行', system)
        self.assertIn('近30天有效评课 3 次', user)

    def test_rejects_unconfigured_key_before_calling_client(self):
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: None)))

        with self.assertRaisesRegex(DeepSeekReviewError, '未配置 DEEPSEEK_API_KEY'):
            answer_review_question('请解释评分。', {'report': {}}, config={'DEEPSEEK_API_KEY': ''}, client=client)

    def test_retries_empty_answer_then_raises_review_error(self):
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=''))])

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with self.assertRaisesRegex(DeepSeekReviewError, '没有返回回答内容'):
            answer_review_question(
                '请解释评分。',
                {'report': {}},
                config={'DEEPSEEK_API_KEY': 'test-key'},
                client=client,
            )
        self.assertEqual(len(calls), 2)

    def test_wraps_sdk_exception_as_review_error(self):
        def create(**kwargs):
            raise RuntimeError('connection failed')

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with self.assertRaisesRegex(DeepSeekReviewError, 'DeepSeek 追问失败，请稍后重试'):
            answer_review_question(
                '请解释评分。',
                {'report': {}},
                config={'DEEPSEEK_API_KEY': 'test-key'},
                client=client,
            )

    def test_answer_question_wraps_provider_error_without_leaking_details(self):
        class BrokenCompletions:
            def create(self, **_kwargs):
                raise RuntimeError('secret-provider-url-and-key')

        client = SimpleNamespace(chat=SimpleNamespace(completions=BrokenCompletions()))
        with self.assertRaises(DeepSeekReviewError) as captured:
            answer_review_question(
                '为什么评分较低？',
                {'scope': 'current', 'current': {'overall_score': 70}},
                config={'DEEPSEEK_API_KEY': 'test', 'DEEPSEEK_TIMEOUT_SECONDS': '17'},
                client=client,
            )
        self.assertNotIn('secret-provider-url-and-key', str(captured.exception))


if __name__ == '__main__':
    unittest.main()
