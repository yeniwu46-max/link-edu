from datetime import datetime, timedelta

from typing import Optional

from models import AiFeedback, Course, Resource, TrainingSession, User
from services.studio import (
    build_ai_summaries,
    build_heatmap,
    build_replay,
    greeting_period,
    list_journals,
)
from services.training import feedback_is_scorable


ROLE_LABELS = {
    'student': '师范生',
    'teacher': '指导教师',
}

NAV_ITEMS = ['工作台', '课程中心', '教学训练', 'AI 评课', '成长档案', '资源库']


def build_dashboard_overview(user: User):
    now = datetime.utcnow()
    week_start = now - timedelta(days=7)
    prev_week_start = now - timedelta(days=14)

    weekly_sessions = (
        TrainingSession.query.filter(
            TrainingSession.user_id == user.id,
            TrainingSession.last_trained_at >= week_start,
        ).all()
    )
    prev_week_sessions = (
        TrainingSession.query.filter(
            TrainingSession.user_id == user.id,
            TrainingSession.last_trained_at >= prev_week_start,
            TrainingSession.last_trained_at < week_start,
        ).all()
    )

    weekly_count = len(weekly_sessions)
    weekly_minutes = sum(session.duration_minutes for session in weekly_sessions)
    prev_week_count = len(prev_week_sessions)
    trend_percent = 0
    if prev_week_count:
        trend_percent = round(((weekly_count - prev_week_count) / prev_week_count) * 100)

    continue_session = (
        TrainingSession.query.filter_by(user_id=user.id, status='in_progress')
        .order_by(TrainingSession.last_trained_at.desc())
        .first()
    )

    feedback_rows = (
        AiFeedback.query.filter_by(user_id=user.id)
        .order_by(AiFeedback.created_at.desc())
        .all()
    )
    scorable_feedbacks = [row for row in feedback_rows if feedback_is_scorable(row)]
    latest_feedback = scorable_feedbacks[0] if scorable_feedbacks else None

    growth_scores = [
        row.overall_score
        for row in scorable_feedbacks[:7]
    ][::-1]

    course_count = Course.query.filter_by(is_active=True).count()
    resource_count = Resource.query.filter_by(is_active=True).count()
    training_count = TrainingSession.query.filter_by(user_id=user.id).count()

    weekly_heatmap = build_heatmap(user, 7)
    sparkline = [min(72, cell['count'] * 12) for cell in weekly_heatmap]

    greet = greeting_period()
    return {
        'greeting': {
            'title': f"{greet['zh']}，{user.name}",
            'subtitle': '准备好开始今天的模拟课堂了吗？',
            'period': greet['en'],
            'period_zh': greet['zh'],
            'period_en': greet['en'],
            'name': user.name,
            'role': user.role,
            'role_label': ROLE_LABELS.get(user.role, user.role),
        },
        'nav': NAV_ITEMS,
        'weekly_training': {
            'sessions': weekly_count,
            'total_minutes': weekly_minutes,
            'trend_percent': trend_percent,
            'sparkline': sparkline,
            'heatmap': weekly_heatmap,
            'month_heatmap': build_heatmap(user, 30),
            'summaries': build_ai_summaries(user),
            'journals': list_journals(user),
        },
        'continue_training': continue_session.to_dict() if continue_session else None,
        'ai_feedback': latest_feedback.to_dict() if latest_feedback else None,
        'growth_records': build_replay(user, 30),
        'quick_entries': [
            {
                'title': '我的课程',
                'description': f'{course_count} 门课程',
                'icon': '▤',
                'route': '/courses',
            },
            {
                'title': '模拟课堂',
                'description': '创建训练场景',
                'icon': '◈',
                'route': '/training',
            },
            {
                'title': 'AI 评课',
                'description': '查看分析报告',
                'icon': '◔',
                'route': '/ai-review',
            },
            {
                'title': '资源中心',
                'description': f'{resource_count} 份教案与素材',
                'icon': '▣',
                'route': '/resources',
            },
        ],
        'growth_trajectory': growth_scores,
        'stats': {
            'course_count': course_count,
            'training_count': training_count,
            'resource_count': resource_count,
        },
    }


def list_courses(user: Optional[User] = None):
    courses = (
        Course.query.filter_by(is_active=True)
        .order_by(Course.stage.asc(), Course.id.asc())
        .all()
    )
    latest = {}
    if user:
        for session in TrainingSession.query.filter_by(user_id=user.id).all():
            previous = latest.get(session.course_id)
            current_stamp = session.last_trained_at or session.created_at
            previous_stamp = (previous.last_trained_at or previous.created_at) if previous else None
            if previous is None or (current_stamp and (previous_stamp is None or current_stamp > previous_stamp)):
                latest[session.course_id] = session

    items = []
    for course in courses:
        item = course.to_dict()
        session = latest.get(course.id)
        if session:
            item['progress_percent'] = session.progress_percent
            item['status'] = session.status
            item['status_label'] = session.to_dict()['status_label']
            item['session_id'] = session.id
        else:
            item['progress_percent'] = 0
            item['status'] = 'idle'
            item['status_label'] = '未开始'
            item['session_id'] = None
        items.append(item)
    return items


def list_resources():
    return [resource.to_dict() for resource in Resource.query.filter_by(is_active=True).order_by(Resource.id).all()]
