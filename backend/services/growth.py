from datetime import datetime, timedelta

from models import AiFeedback, TrainingSession, User
from services.studio import build_ai_summaries, build_heatmap, build_replay, list_journals


def serialize_feedback(row: AiFeedback):
    payload = row.to_dict()
    payload['id'] = row.id
    payload['session_id'] = row.session_id
    if row.session and row.session.course:
        payload['course_title'] = row.session.course.title
        payload['category'] = row.session.course.category
    return payload


def list_feedbacks(user: User):
    rows = (
        AiFeedback.query.filter_by(user_id=user.id)
        .order_by(AiFeedback.created_at.desc())
        .all()
    )
    return [serialize_feedback(row) for row in rows]


def get_feedback(user: User, feedback_id: int):
    row = AiFeedback.query.filter_by(id=feedback_id, user_id=user.id).first()
    return serialize_feedback(row) if row else None


def build_growth(user: User, range_key: str = 'all'):
    query = AiFeedback.query.filter_by(user_id=user.id)
    days = None
    if range_key == '7d':
        days = 7
        query = query.filter(AiFeedback.created_at >= datetime.utcnow() - timedelta(days=7))
    elif range_key == '30d':
        days = 30
        query = query.filter(AiFeedback.created_at >= datetime.utcnow() - timedelta(days=30))
    rows = query.order_by(AiFeedback.created_at.asc()).all()
    from services.training import report_from_feedback_row
    rows = [row for row in rows if not report_from_feedback_row(row).get('insufficient_evidence')]

    points = [
        {
            'date': row.created_at.strftime('%m/%d') if row.created_at else '',
            'time': row.created_at.strftime('%H:%M') if row.created_at else '',
            'score': row.overall_score,
            'clarity': row.clarity_score,
            'pace': row.pace_score,
            'interaction': row.interaction_score,
            'id': row.id,
            'course_title': row.session.course.title if row.session and row.session.course else '',
        }
        for row in rows
    ]

    sessions = TrainingSession.query.filter_by(user_id=user.id).all()
    first_at = None
    for session in sessions:
        stamp = session.started_at or session.created_at
        if stamp and (first_at is None or stamp < first_at):
            first_at = stamp

    week_start = datetime.utcnow() - timedelta(days=7)
    week_count = TrainingSession.query.filter(
        TrainingSession.user_id == user.id,
        TrainingSession.last_trained_at >= week_start,
    ).count()

    best = max((row.overall_score for row in rows), default=0)

    return {
        'range': range_key,
        'points': points,
        'heatmap': build_heatmap(user, days or 30),
        'records': build_replay(user, days or 30),
        'summaries': build_ai_summaries(user),
        'journals': list_journals(user),
        'milestones': [
            {
                'label': '首次训练',
                'value': first_at.strftime('%m/%d') if first_at else '—',
                'hint': '从第一次模拟课堂算起',
            },
            {
                'label': '最高分',
                'value': best or '—',
                'hint': 'AI 评课综合分',
            },
            {
                'label': '本周次数',
                'value': week_count,
                'hint': '近 7 日训练场次',
            },
        ],
    }
