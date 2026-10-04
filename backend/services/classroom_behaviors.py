"""Versioned, evidence-linked observations of classroom interaction.

These labels describe recorded turns. They do not grade teaching quality or infer
student learning. In particular, a question-to-reply interval includes model and
audio latency and is never presented as a teacher's wait time.
"""

import math
import re

from services.classroom_learning import route_intent


VERSION = 'teaching-behavior-1'
FOLLOWUP = re.compile(r'为什么|怎么|如何|依据|理由|再说|再解释|能举|举个例|你是怎样')
FEEDBACK = re.compile(r'很好|说得对|答对|不对|补充|纠正|更准确|注意|刚才你|你的回答')
SUMMARY = re.compile(r'总结|小结|今天我们|这节课|最后回顾|回顾一下')
BOARD_POSITIVE = re.compile(r'(可见|看到|写有|展示|显示|呈现).{0,10}(板书|黑板|白板)|(板书|黑板|白板).{0,10}(可见|写有|显示|呈现)')
BOARD_NEGATIVE = re.compile(r'(未见|未能|没有|无|看不清|无法辨认|不可见|被遮挡).{0,8}(板书|黑板|白板)|(板书|黑板|白板).{0,4}(不可见|被遮挡|看不清)')


def _valid(event):
    return (isinstance(event, dict) and type(event.get('id')) is int and
            type(event.get('at_ms')) is int and event['at_ms'] >= 0 and
            isinstance(event.get('data'), dict))


def _segment(kind, events, *, detail='', limitations=None):
    events = sorted(events, key=lambda e: (e['at_ms'], e['id']))
    quality = ('approximate' if kind == 'post_question_silence' else
               'contextual' if kind in ('board_speech_context', 'motion_speech_context') else 'recorded')
    return {
        'kind': kind,
        'start_ms': min(e['at_ms'] for e in events),
        'end_ms': max(e['at_ms'] for e in events),
        'event_ids': [e['id'] for e in events],
        'basis': 'rule',
        'evidence_quality': quality,
        'version': VERSION,
        'detail': detail,
        'limitations': limitations or [],
    }


def analyze_behaviors(events):
    """Return conservative observations from recorded, timestamped events."""
    ordered = sorted((e for e in events if _valid(e)), key=lambda e: (e['at_ms'], e['id']))
    students = {e['data'].get('reply_id'): e for e in ordered
                if e.get('type') == 'student' and e['data'].get('reply_id')}
    invalid = {e['data'].get('reply_id') for e in ordered
               if e.get('type') == 'interrupt' or
               (e.get('type') == 'playback' and e['data'].get('status') in
                ('playback_failed', 'playback_cancelled', 'cancelled'))}
    completed = {}
    for event in ordered:
        reply_id = event['data'].get('reply_id')
        if (event.get('type') == 'playback' and event['data'].get('status') == 'playback_completed'
                and reply_id in students and reply_id not in invalid
                and students[reply_id]['at_ms'] <= event['at_ms']):
            completed.setdefault(reply_id, (students[reply_id], event))

    segments = []
    questions = []
    teacher_turns = []
    for event in ordered:
        if event.get('type') != 'transcript':
            continue
        content = str(event['data'].get('text') or '').strip()
        if not content:
            continue
        teacher_turns.append(event)
        intent = route_intent(content)['intent']
        if intent in ('named_question', 'class_question', 'invite'):
            questions.append(event)
            segments.append(_segment('teacher_question', [event], detail=content[:160]))
        if SUMMARY.search(content):
            segments.append(_segment('teacher_summary', [event], detail=content[:160]))

    speech_stops = [e for e in ordered if e.get('type') == 'teacher_speech_stop']
    speech_starts = [e for e in ordered if e.get('type') == 'teacher_speech_start']
    for question in questions:
        stops = [e for e in speech_stops if 0 <= question['at_ms'] - e['at_ms'] <= 8000]
        if not stops:
            continue
        stopped = stops[-1]
        starts = [e for e in speech_starts if e['at_ms'] > question['at_ms'] and
                  500 <= e['at_ms'] - stopped['at_ms'] <= 30000]
        if not starts:
            continue
        restarted = starts[0]
        if any(e.get('type') in ('student', 'playback') and
               stopped['at_ms'] < e['at_ms'] < restarted['at_ms'] for e in ordered):
            continue
        seconds = round((restarted['at_ms'] - stopped['at_ms']) / 1000, 1)
        segments.append(_segment('post_question_silence', [stopped, question, restarted],
            detail=f'教师提问后到再次发言约 {seconds} 秒',
            limitations=['这是两次教师语音活动之间的记录间隔，可能包含识别或系统延迟；不自动视作有效候答。']))

    completed_pairs = sorted(completed.values(), key=lambda pair: pair[1]['at_ms'])
    for student, playback in completed_pairs:
        segments.append(_segment('student_response', [student, playback],
                                 detail=str(student['data'].get('text') or '')[:160]))
        prior = [q for q in questions if q['at_ms'] <= student['at_ms'] and
                 student['at_ms'] - q['at_ms'] <= 120000]
        if prior:
            question = prior[-1]
            # A newer teacher turn between question and response makes the link ambiguous.
            intervening = [t for t in teacher_turns if question['at_ms'] < t['at_ms'] < student['at_ms']]
            if not intervening:
                segments.append(_segment('question_response', [question, student, playback],
                    limitations=['提问到回应的时间差包含模型生成与语音播放延迟，不是教师候答时间。']))

        later = [t for t in teacher_turns if playback['at_ms'] < t['at_ms'] <= playback['at_ms'] + 60000]
        if not later:
            continue
        teacher = later[0]
        text = str(teacher['data'].get('text') or '')
        if FOLLOWUP.search(text) and route_intent(text)['intent'] in ('named_question', 'class_question', 'invite'):
            segments.append(_segment('teacher_followup', [student, playback, teacher], detail=text[:160]))
        elif FEEDBACK.search(text):
            segments.append(_segment('teacher_feedback', [student, playback, teacher], detail=text[:160]))

    observed_motion = 0
    vision_samples = 0
    last_motion_at = -15000
    for event in ordered:
        if event.get('type') == 'vision':
            vision_samples += 1
            data = event['data']
            observation = str(data.get('observations') or '')
            confidence = data.get('confidence')
            if (type(confidence) in (int, float) and math.isfinite(confidence) and .7 <= confidence <= 1 and
                    data.get('scene_detected') is True and BOARD_POSITIVE.search(observation) and
                    not BOARD_NEGATIVE.search(observation)):
                segments.append(_segment('board_observation', [event], detail=observation[:160],
                    limitations=['画面描述只证明该采样点可见板书，不验证板书文字或教学正确性。']))
                nearby = [t for t in teacher_turns if abs(t['at_ms'] - event['at_ms']) <= 5000]
                if nearby:
                    teacher = min(nearby, key=lambda t: abs(t['at_ms'] - event['at_ms']))
                    segments.append(_segment('board_speech_context', [teacher, event],
                        detail=str(teacher['data'].get('text') or '')[:160],
                        limitations=['教师发言与板书采样仅时间邻近，不证明二者语义一致。']))
        elif event.get('type') == 'pose' and event['data'].get('motion_version') == 2:
            data = event['data']
            if not any(isinstance(data.get(name), dict) and data[name].get('status') == 'observed'
                       for name in ('body', 'hands')):
                continue
            observed_motion += 1
            if event['at_ms'] - last_motion_at < 15000:
                continue
            nearby = [t for t in teacher_turns if abs(t['at_ms'] - event['at_ms']) <= 5000]
            if nearby:
                teacher = min(nearby, key=lambda t: abs(t['at_ms'] - event['at_ms']))
                segments.append(_segment('motion_speech_context', [teacher, event],
                    detail=str(teacher['data'].get('text') or '')[:160],
                    limitations=['本地动作样本与发言仅时间邻近，不推断手势意图、目光对象或情绪。']))
                last_motion_at = event['at_ms']

    segments.sort(key=lambda s: (s['start_ms'], s['end_ms'], s['event_ids']))
    return {
        'version': VERSION,
        'segments': segments,
        'coverage': {'teacher_transcripts': len(teacher_turns),
                     'completed_student_replies': len(completed_pairs),
                     'vision_samples': vision_samples, 'observed_motion_samples': observed_motion},
        'limitations': ['仅描述有时间戳的已记录行为；缺失或识别错误的语音不会被补造。',
                        '课堂行为片段不是教学质量分数，学生回应须确认完整播放。'],
    }
