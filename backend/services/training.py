import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

from flask import current_app

from extensions import db
from models import AiFeedback, Course, TrainingSession, User
from services.llm.deepseek import (
    DeepSeekReviewError,
    answer_review_question,
    generate_review_report,
    has_insufficient_evidence,
)

FRAGMENT_MINUTES = 8
FULL_MINUTES = 10
AI_REVIEW_RATE_WINDOW_SECONDS = 10 * 60
AI_REVIEW_RATE_MAX_ATTEMPTS = 5
HISTORY_QUESTION_MARKERS = (
    '最近',
    '近30天',
    '近 30 天',
    '历史',
    '进步',
    '趋势',
    '相比',
    '上次',
    '变化',
    '长期',
)

_ai_review_guard = Lock()
_ai_review_inflight = set()
_ai_review_attempts = defaultdict(deque)

SCENE_TIPS = {
    '导入': '开场再慢半拍，把问题抛给学生后再讲概念。',
    '提问': '提问后增加等待时间，并用一次追问把回答挖深。',
    '板书': '板书分区更清楚：左侧结构、右侧例证。',
    '互动': '小组分享后请做 10 秒全班回收，避免互动散掉。',
    '完整': '四个环节都过一遍后，用 20 秒把目标、过程、作业收束到黑板上。',
}

SCENE_FOCUS = {
    '导入': '课堂导入',
    '提问': '提问设计',
    '板书': '板书与结构',
    '互动': '互动与回收',
    '完整': '完整微格课',
}


def _clamp(value, low=62, high=96):
    return max(low, min(high, int(value)))


def _mode_meta(mode, scene):
    is_full = mode == 'full'
    return {
        'mode': 'full' if is_full else 'fragment',
        'mode_label': '完整 10 分钟' if is_full else '片段练习',
        'scene': scene if scene in SCENE_TIPS else ('完整' if is_full else '导入'),
        'target_minutes': FULL_MINUTES if is_full else FRAGMENT_MINUTES,
    }


def build_review_report(minutes, scene, mode='fragment', course_title=None):
    meta = _mode_meta(mode, scene)
    scene = meta['scene']
    target = meta['target_minutes']
    minutes = max(1, min(15, int(minutes or 1)))
    coverage = min(1.15, minutes / target)
    short = minutes < max(3, target * 0.4)
    complete_enough = minutes >= target * 0.75

    clarity = _clamp(74 + coverage * 18 + (2 if scene in {'导入', '板书', '完整'} else 0))
    pace = _clamp(78 + coverage * 14 - (10 if short else 0) - (4 if minutes > target + 1 else 0), 64, 96)
    interaction = _clamp(72 + coverage * 16 + (6 if scene in {'互动', '提问', '完整'} else 0))
    posture = _clamp(70 + coverage * 20 + (3 if complete_enough else -2), 64, 95)
    questioning = _clamp(71 + coverage * 17 + (7 if scene in {'提问', '完整'} else 1))
    structure = _clamp(73 + coverage * 16 + (6 if scene in {'板书', '完整'} else 0))
    overall = _clamp(round(
        clarity * 0.2 + pace * 0.18 + interaction * 0.18
        + posture * 0.14 + questioning * 0.15 + structure * 0.15
    ), 68, 96)

    focus = SCENE_FOCUS.get(scene, '片段教学')
    course_bit = f'「{course_title}」' if course_title else '本次微格'
    duration_note = (
        f'实际练习 {minutes} 分钟，对照 {target} 分钟目标'
        + ('，时长基本跑满。' if complete_enough else '，偏短，后半段技能还没展开。')
    )

    dimensions = [
        {
            'key': 'clarity',
            'label': '表达清晰度',
            'score': clarity,
            'brief': '指令和概念是否能被学生一次听懂。',
        },
        {
            'key': 'pace',
            'label': '教学节奏',
            'score': pace,
            'brief': '开场、等待、推进有没有挤在一起。',
        },
        {
            'key': 'interaction',
            'label': '互动设计',
            'score': interaction,
            'brief': '提问、讨论之后有没有全班回收。',
        },
        {
            'key': 'posture',
            'label': '教态与站位',
            'score': posture,
            'brief': '面向学生、板书与巡视是否分开。',
        },
        {
            'key': 'questioning',
            'label': '提问质量',
            'score': questioning,
            'brief': '问题是否具体，有没有追问。',
        },
        {
            'key': 'structure',
            'label': '课堂结构',
            'score': structure,
            'brief': '目标、过程、小结是否看得见。',
        },
    ]

    weak = sorted(dimensions, key=lambda item: item['score'])[0]
    strong = sorted(dimensions, key=lambda item: item['score'], reverse=True)[0]
    next_action = SCENE_TIPS.get(scene, SCENE_TIPS['导入'])

    sections = [
        {
            'title': '综合判断',
            'body': (
                f'{course_bit}按「{focus}」完成一次{meta["mode_label"]}。{duration_note}'
                f'综合分 {overall}。相对最稳的是{strong["label"]}（{strong["score"]}），'
                f'最该补的是{weak["label"]}（{weak["score"]}）。'
                '本期评课按时长、模式与训练环节计算，保证演示可复现；接入真实模型后仍沿用这六个字段。'
            ),
        },
        {
            'title': '表达与语言',
            'body': (
                '开场请先给出本节课要解决的问题，再展开概念。关键指令（看黑板、同桌讨论、请坐）只说一遍，'
                '说完停 1 秒。若连续讲述超过 40 秒，插入一个只要学生点头或举手就能完成的小确认。'
            ),
        },
        {
            'title': '节奏与时间',
            'body': (
                '导入控制在总时长的前 1/4，提问后至少等待 8 秒。'
                + ('完整课请在每个环节结束时口头报时，避免板书吃掉互动。' if meta['mode'] == 'full'
                   else '片段练习不必求全，把这一个技能做满即可。')
                + ('本次结束偏早，后半段的回收和小结几乎没有时间。' if short else '')
            ),
        },
        {
            'title': '互动与提问',
            'body': (
                '问题要能指向黑板结构，而不是「对不对」。学生回答后追问一次「为什么」，'
                '再请另一位同学用自己的话复述。小组活动结束必须做 10 秒全班回收，否则互动会散掉。'
            ),
        },
        {
            'title': '教态与板书',
            'body': (
                '讲解时肩线对学生，写板书时侧身而不是背对全班。'
                '板书建议左栏「目标 / 过程 / 结论」，右栏放例子。巡视时走下讲台一次，再回到板书收束。'
            ),
        },
    ]

    strengths = [
        f'{strong["label"]}这一项最高，下次训练可以把它当稳定盘。',
        '能够按选定模式把训练走完，主路径没有断。' if complete_enough else '已经愿意上台，下一步把时长跑满。',
    ]
    fixes = [
        f'优先改{weak["label"]}：{weak["brief"]}',
        next_action,
        '结束前用一句话重述学习目标，让这节课有收口。',
    ]

    return {
        **meta,
        'duration_minutes': minutes,
        'demo': True,
        'overall_score': overall,
        'clarity_score': clarity,
        'pace_score': pace,
        'interaction_score': interaction,
        'dimensions': dimensions,
        'sections': sections,
        'strengths': strengths,
        'fixes': fixes,
        'next_action': next_action,
        'suggestion': next_action,
    }


def report_from_feedback_row(row: AiFeedback):
    if row.report_json:
        try:
            payload = json.loads(row.report_json)
            if isinstance(payload, dict) and (payload.get('dimensions') or payload.get('generation_status')):
                if (
                    payload.get('source') == 'deepseek'
                    and 'insufficient_evidence' not in payload
                    and has_insufficient_evidence(payload.get('dimensions') or [])
                ):
                    payload['insufficient_evidence'] = True
                    payload['overall_score'] = None
                return payload
        except (TypeError, ValueError):
            pass

    suggestion = row.suggestion or SCENE_TIPS['导入']
    minutes = 8
    if row.session and row.session.duration_minutes:
        minutes = row.session.duration_minutes
    course_title = row.session.course.title if row.session and row.session.course else None
    report = build_review_report(minutes, '导入', 'fragment', course_title)
    report['overall_score'] = row.overall_score
    report['clarity_score'] = row.clarity_score or report['clarity_score']
    report['pace_score'] = row.pace_score or report['pace_score']
    report['interaction_score'] = row.interaction_score or report['interaction_score']
    report['suggestion'] = suggestion
    report['next_action'] = suggestion
    mapping = {
        'clarity': report['clarity_score'],
        'pace': report['pace_score'],
        'interaction': report['interaction_score'],
    }
    for item in report['dimensions']:
        if item['key'] in mapping:
            item['score'] = mapping[item['key']]
    report['sections'][0]['body'] = (
        f'历史场次综合分 {row.overall_score}。{suggestion} '
        '下方六个维度由当时的三维分数补全，便于对照新报告。'
    )
    return report


def feedback_is_scorable(row: AiFeedback):
    return not report_from_feedback_row(row).get('insufficient_evidence')


def classify_question_scope(question):
    """Classify whether a follow-up needs the user's recent history."""
    question_text = str(question or '')
    return 'history' if any(marker in question_text for marker in HISTORY_QUESTION_MARKERS) else 'current'


def _compact_report(report):
    """Keep only report fields useful for a follow-up answer."""
    dimensions = []
    for item in report.get('dimensions') or []:
        if not isinstance(item, dict):
            continue
        dimensions.append({
            'key': item.get('key'),
            'label': item.get('label'),
            'score': item.get('score'),
            'evidence': item.get('evidence'),
            'brief': item.get('brief'),
        })
    return {
        'source': report.get('source'),
        'generation_status': report.get('generation_status'),
        'insufficient_evidence': bool(report.get('insufficient_evidence')),
        'overall_score': report.get('overall_score'),
        'summary': report.get('summary'),
        'strengths': report.get('strengths') or [],
        'problems': report.get('problems') or [],
        'fixes': report.get('fixes') or [],
        'next_action': report.get('next_action'),
        'dimensions': dimensions,
    }


def build_recent_review_summary(user, *, exclude_feedback_id=None):
    """Build a compact, recent-only summary without exposing full reports."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    rows = (
        AiFeedback.query
        .filter(
            AiFeedback.user_id == user.id,
            AiFeedback.created_at >= cutoff,
        )
        .order_by(AiFeedback.created_at.desc())
        .all()
    )
    valid_rows = []
    for row in rows:
        if exclude_feedback_id is not None and row.id == exclude_feedback_id:
            continue
        report = report_from_feedback_row(row)
        if report.get('source') != 'deepseek':
            continue
        if report.get('generation_status') != 'succeeded':
            continue
        if report.get('insufficient_evidence'):
            continue
        valid_rows.append((row, report))
        if len(valid_rows) >= 10:
            break

    records = []
    for row, report in valid_rows:
        records.append({
            'id': row.id,
            'date': row.created_at.isoformat() if row.created_at else None,
            'course_title': row.session.course.title if row.session and row.session.course else None,
            'scene': report.get('scene'),
            'overall_score': report.get('overall_score'),
            'dimensions': {
                item.get('key'): item.get('score')
                for item in report.get('dimensions') or []
                if isinstance(item, dict) and item.get('key')
            },
            'problems': (report.get('problems') or [])[:3],
        })

    scores = [item['overall_score'] for item in records if isinstance(item.get('overall_score'), (int, float))]
    chronological = sorted(
        [item for item in records if isinstance(item.get('overall_score'), (int, float))],
        key=lambda item: item.get('date') or '',
    )
    dimension_values = defaultdict(list)
    problem_counts = defaultdict(int)
    problem_labels = {}
    for row, report in valid_rows:
        for item in report.get('dimensions') or []:
            if not isinstance(item, dict) or not item.get('key'):
                continue
            score = item.get('score')
            if isinstance(score, (int, float)):
                dimension_values[item['key']].append(score)
        for problem in report.get('problems') or []:
            label = ' '.join(str(problem).split())
            if label:
                problem_counts[label] += 1
                problem_labels[label] = label

    recurring_problems = [
        problem_labels[label]
        for label, count in sorted(problem_counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ][:5]

    return {
        'period_days': 30,
        'record_count': len(records),
        'average_overall_score': round(sum(scores) / len(scores), 1) if scores else None,
        'highest_score': max(scores) if scores else None,
        'lowest_score': min(scores) if scores else None,
        'first_score': chronological[0]['overall_score'] if chronological else None,
        'latest_score': chronological[-1]['overall_score'] if chronological else None,
        'score_change': (
            chronological[-1]['overall_score'] - chronological[0]['overall_score']
            if len(chronological) >= 2 else None
        ),
        'dimension_averages': {
            key: round(sum(values) / len(values), 1)
            for key, values in sorted(dimension_values.items())
        },
        'recurring_problems': recurring_problems,
        'records': records,
    }


def build_review_question_context(user, feedback: AiFeedback, question):
    """Assemble current report context and optional recent trend context."""
    report = report_from_feedback_row(feedback)
    session = feedback.session
    course = session.course if session else None
    scope = classify_question_scope(question)
    current_report = _compact_report(report)
    current = {
        'feedback_id': feedback.id,
        'session_id': session.id if session else feedback.session_id,
        'course_title': course.title if course else None,
        'category': course.category if course else None,
        'scene': report.get('scene'),
        'mode': report.get('mode'),
        'duration_minutes': session.duration_minutes if session else report.get('duration_minutes'),
        'progress_percent': session.progress_percent if session else None,
        'status': session.status if session else None,
        'started_at': session.started_at.isoformat() if session and session.started_at else None,
        'last_trained_at': session.last_trained_at.isoformat() if session and session.last_trained_at else None,
        **{key: current_report[key] for key in (
            'summary',
            'strengths',
            'problems',
            'fixes',
            'next_action',
            'dimensions',
            'overall_score',
            'insufficient_evidence',
        )},
        'report': current_report,
    }
    context = {
        'scope': scope,
        'current': current,
    }
    if scope == 'history':
        context['recent_30_days'] = build_recent_review_summary(
            user,
            exclude_feedback_id=feedback.id,
        )
    return context


def start_session(user: User, course_id: int):
    course = db.session.get(Course, course_id)
    if not course or not course.is_active:
        return None, '课程不存在'

    session = TrainingSession(
        user_id=user.id,
        course_id=course.id,
        status='in_progress',
        progress_percent=8,
        duration_minutes=0,
        started_at=datetime.utcnow(),
        last_trained_at=datetime.utcnow(),
    )
    db.session.add(session)
    db.session.commit()
    return session, None


def update_session(user: User, session_id: int, progress_percent=None, duration_minutes=None):
    session = TrainingSession.query.filter_by(id=session_id, user_id=user.id).first()
    if not session:
        return None, '训练不存在'
    if progress_percent is not None:
        session.progress_percent = max(0, min(100, int(progress_percent)))
    if duration_minutes is not None:
        session.duration_minutes = max(0, int(duration_minutes))
    session.last_trained_at = datetime.utcnow()
    db.session.commit()
    return session, None


def complete_session(user: User, session_id: int, duration_minutes: int, scene: str, mode: str = 'fragment'):
    session = TrainingSession.query.filter_by(id=session_id, user_id=user.id).first()
    if not session:
        return None, None, '训练不存在'

    mode = 'full' if mode == 'full' else 'fragment'
    scene = scene if scene in SCENE_TIPS else ('完整' if mode == 'full' else '导入')
    minutes = max(1, min(15, int(duration_minutes or 1)))
    course_title = session.course.title if session.course else None
    report = build_review_report(minutes, scene, mode, course_title)

    session.status = 'completed'
    session.progress_percent = 100
    session.duration_minutes = minutes
    session.last_trained_at = datetime.utcnow()

    feedback = AiFeedback(
        user_id=user.id,
        session_id=session.id,
        overall_score=report['overall_score'],
        clarity_score=report['clarity_score'],
        pace_score=report['pace_score'],
        interaction_score=report['interaction_score'],
        suggestion=report['next_action'],
        report_json=json.dumps(report, ensure_ascii=False),
    )
    db.session.add(feedback)
    db.session.commit()
    return session, feedback, None


def generate_ai_review(
    user: User,
    session_id: int,
    transcript_text='',
    teacher_notes='',
    force_regenerate=False,
):
    """Generate and persist a real DeepSeek report for a completed session."""
    session = TrainingSession.query.filter_by(id=session_id, user_id=user.id).first()
    if not session:
        return None, '训练不存在'
    if session.status != 'completed':
        return None, '请先完成训练再生成评课'

    feedback = (
        AiFeedback.query.filter_by(user_id=user.id, session_id=session_id)
        .order_by(AiFeedback.created_at.desc())
        .first()
    )
    existing_report = report_from_feedback_row(feedback) if feedback else {}
    generation_status = existing_report.get('generation_status')
    if (
        existing_report.get('source') == 'deepseek'
        and not existing_report.get('insufficient_evidence')
        and generation_status in {None, 'succeeded'}
        and not force_regenerate
    ):
        return feedback, None

    gate_error = _begin_ai_review(user.id, session_id)
    if gate_error:
        return None, gate_error

    course = session.course
    review_input = {
        'course_title': course.title if course else None,
        'scene': existing_report.get('scene') or ('完整' if course and str(course.stage or '').startswith('综合') else '导入'),
        'mode': existing_report.get('mode') or ('full' if course and str(course.stage or '').startswith('综合') else 'fragment'),
        'duration_minutes': session.duration_minutes,
        'progress_percent': session.progress_percent,
        'status': session.status,
        'started_at': session.started_at.isoformat() if session.started_at else None,
        'last_trained_at': session.last_trained_at.isoformat() if session.last_trained_at else None,
        'transcript_text': transcript_text,
        'teacher_notes': teacher_notes,
    }
    try:
        if feedback is None:
            feedback = AiFeedback(user_id=user.id, session_id=session_id, overall_score=0)
            db.session.add(feedback)
        previous_report = dict(existing_report)
        generating_report = dict(previous_report)
        generating_report.update({
            'generation_status': 'generating',
            'generation_started_at': datetime.utcnow().isoformat(),
            'material_length': len(transcript_text) + len(teacher_notes),
        })
        generating_report.pop('generation_error', None)
        feedback.report_json = json.dumps(generating_report, ensure_ascii=False)
        db.session.commit()
        try:
            report = generate_review_report(review_input, config=current_app.config)
        except DeepSeekReviewError as error:
            current_app.logger.warning('DeepSeek review failed for session %s: %s', session_id, error)
            failed_report = dict(previous_report)
            failed_report.update({
                'generation_status': 'failed',
                'generation_error': 'AI 评课生成失败，请稍后重试',
                'generation_failed_at': datetime.utcnow().isoformat(),
                'material_length': len(transcript_text) + len(teacher_notes),
            })
            feedback.report_json = json.dumps(failed_report, ensure_ascii=False)
            db.session.commit()
            return None, 'AI 评课生成失败，请检查配置后重试'

        report['generation_status'] = 'succeeded'
        report['generation_completed_at'] = datetime.utcnow().isoformat()
        report['material_length'] = len(transcript_text) + len(teacher_notes)
        score_map = {item['key']: item['score'] for item in report.get('dimensions') or []}
        if not report.get('insufficient_evidence'):
            feedback.overall_score = report['overall_score']
            feedback.clarity_score = score_map.get('clarity')
            feedback.pace_score = score_map.get('pace')
            feedback.interaction_score = score_map.get('interaction')
        feedback.suggestion = report.get('next_action')
        feedback.report_json = json.dumps(report, ensure_ascii=False)
        db.session.commit()
        return feedback, None
    finally:
        _finish_ai_review(user.id, session_id)


def ask_ai_review_question(user: User, feedback_id: int, question):
    """Answer a question using an existing DeepSeek report without writing data."""
    question_text = str(question or '').strip()
    if not question_text:
        return None, '问题不能为空'

    feedback = AiFeedback.query.filter_by(id=feedback_id, user_id=user.id).first()
    if not feedback:
        return None, '评课不存在'

    report = report_from_feedback_row(feedback)
    if (
        report.get('source') != 'deepseek'
        or report.get('generation_status') != 'succeeded'
    ):
        return None, '请先生成 DeepSeek 评课报告'

    context = build_review_question_context(user, feedback, question_text)
    try:
        answer = answer_review_question(
            question_text,
            context,
            config=current_app.config,
        )
    except DeepSeekReviewError as error:
        current_app.logger.warning(
            'DeepSeek follow-up failed for feedback %s: %s',
            feedback_id,
            error,
        )
        return None, 'AI 评课追问失败，请检查配置后重试'

    return {
        'feedback_id': feedback.id,
        'scope': context['scope'],
        'answer': answer,
    }, None


def _begin_ai_review(user_id, session_id):
    now = time.monotonic()
    cutoff = now - AI_REVIEW_RATE_WINDOW_SECONDS
    key = (user_id, session_id)
    with _ai_review_guard:
        attempts = _ai_review_attempts[user_id]
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        if key in _ai_review_inflight:
            return 'AI 评课正在生成，请稍后查看'
        if len(attempts) >= AI_REVIEW_RATE_MAX_ATTEMPTS:
            return 'AI 评课请求过于频繁，请十分钟后再试'
        attempts.append(now)
        _ai_review_inflight.add(key)
    return None


def _finish_ai_review(user_id, session_id):
    with _ai_review_guard:
        _ai_review_inflight.discard((user_id, session_id))


def get_session(user: User, session_id: int):
    return TrainingSession.query.filter_by(id=session_id, user_id=user.id).first()


def regenerate_feedback(user: User, feedback_id: int, note_ids=None):
    from services.studio import CORRECTION_OPTIONS

    row = AiFeedback.query.filter_by(id=feedback_id, user_id=user.id).first()
    if not row:
        return None, '评课不存在'

    selected = set(note_ids or [])
    report = report_from_feedback_row(row)
    delta_map = {item['id']: item for item in CORRECTION_OPTIONS}
    applied = []
    for note_id in selected:
        option = delta_map.get(note_id)
        if not option:
            continue
        applied.append(option['label'])
        for item in report.get('dimensions') or []:
            if item.get('key') == option['key']:
                item['score'] = max(62, min(98, int(item.get('score') or 70) + option['delta']))
        if option['key'] == 'clarity':
            report['clarity_score'] = max(62, min(98, int(report.get('clarity_score') or 70) + option['delta']))
        if option['key'] == 'pace':
            report['pace_score'] = max(62, min(98, int(report.get('pace_score') or 70) + option['delta']))
        if option['key'] == 'interaction':
            report['interaction_score'] = max(62, min(98, int(report.get('interaction_score') or 70) + option['delta']))

    dims = report.get('dimensions') or []
    if dims:
        report['overall_score'] = max(68, min(96, round(sum(item.get('score') or 0 for item in dims) / len(dims))))
        for item in dims:
            if item.get('key') == 'clarity':
                report['clarity_score'] = item['score']
            if item.get('key') == 'pace':
                report['pace_score'] = item['score']
            if item.get('key') == 'interaction':
                report['interaction_score'] = item['score']

    note_text = '、'.join(applied) if applied else '你标记了校对不准，但没有勾选具体校正点'
    report['corrected'] = True
    report['corrections'] = applied
    if dims:
        weak = sorted(dims, key=lambda item: item.get('score') or 0)[0]
        strong = sorted(dims, key=lambda item: item.get('score') or 0, reverse=True)[0]
        next_action = (
            f'已吸收校正：{applied[0]}。优先改{weak.get("label")}：{weak.get("brief") or ""}'
            if applied
            else f'优先改{weak.get("label")}：{weak.get("brief") or ""}'
        )
        report['strengths'] = [
            f'{strong.get("label")}这一项最高，下次训练可以把它当稳定盘。',
            '已按你勾选的校正点调整了演示评分。' if applied else '能够按选定模式把训练走完，主路径没有断。',
        ]
        report['fixes'] = [
            f'优先改{weak.get("label")}：{weak.get("brief") or ""}',
            next_action,
            '结束前用一句话重述学习目标，让这节课有收口。',
        ]
        report['next_action'] = next_action
        report['suggestion'] = next_action
    else:
        report['next_action'] = f'已按勾选重写：{note_text}' if applied else report.get('next_action')
        report['suggestion'] = report.get('next_action')

    previous = [item for item in (report.get('sections') or []) if item.get('title') != '校正说明']
    report['sections'] = [
        {
            'title': '校正说明',
            'body': f'已按你的勾选重写本份报告：{note_text}。分数仍是可解释的演示评分，不是外部大模型。',
        },
        *previous,
    ]

    row.overall_score = report['overall_score']
    row.clarity_score = report.get('clarity_score')
    row.pace_score = report.get('pace_score')
    row.interaction_score = report.get('interaction_score')
    row.suggestion = report.get('next_action') or row.suggestion
    row.report_json = json.dumps(report, ensure_ascii=False)
    db.session.commit()
    return row, None
