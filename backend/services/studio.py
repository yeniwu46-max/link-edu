import json
from collections import defaultdict
from datetime import datetime, timedelta

from extensions import db
from models import AiFeedback, TrainingJournal, TrainingSession, User
from services.training import feedback_is_scorable

CORRECTION_OPTIONS = [
    {'id': 'pace_ok', 'label': '节奏其实正常，没有赶课', 'key': 'pace', 'delta': 6},
    {'id': 'waited', 'label': '提问后已经等够了', 'key': 'questioning', 'delta': 7},
    {'id': 'had_interaction', 'label': '互动其实发生了', 'key': 'interaction', 'delta': 7},
    {'id': 'board_clear', 'label': '板书分区是清楚的', 'key': 'structure', 'delta': 6},
    {'id': 'intro_enough', 'label': '导入并不短', 'key': 'clarity', 'delta': 5},
    {'id': 'posture_ok', 'label': '教态没有背对学生', 'key': 'posture', 'delta': 6},
]


def greeting_period(hour=None):
    if hour is None:
        hour = (datetime.utcnow() + timedelta(hours=8)).hour
    hour = int(hour)
    if 5 <= hour < 11:
        return {'zh': '早上好', 'en': 'GOOD MORNING'}
    if 11 <= hour < 14:
        return {'zh': '中午好', 'en': 'GOOD NOON'}
    if 14 <= hour < 18:
        return {'zh': '下午好', 'en': 'GOOD AFTERNOON'}
    return {'zh': '晚上好', 'en': 'GOOD EVENING'}


def _day_key(stamp):
    if not stamp:
        return None
    return stamp.strftime('%Y-%m-%d')


def build_heatmap(user: User, days=30):
    start = datetime.utcnow() - timedelta(days=days - 1)
    sessions = TrainingSession.query.filter(
        TrainingSession.user_id == user.id,
        TrainingSession.last_trained_at >= start,
    ).all()
    buckets = defaultdict(lambda: {'count': 0, 'minutes': 0, 'sessions': []})
    for session in sessions:
        key = _day_key(session.last_trained_at or session.created_at)
        if not key:
            continue
        buckets[key]['count'] += 1
        buckets[key]['minutes'] += session.duration_minutes or 0
        buckets[key]['sessions'].append(session.to_dict())

    cells = []
    today = datetime.utcnow().date()
    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        key = day.isoformat()
        item = buckets.get(key, {'count': 0, 'minutes': 0, 'sessions': []})
        cells.append({
            'date': key,
            'label': day.strftime('%m/%d'),
            'weekday': '一二三四五六日'[day.weekday()],
            'count': item['count'],
            'minutes': item['minutes'],
            'level': 0 if item['count'] == 0 else min(4, item['count']),
            'sessions': item['sessions'],
        })
    return cells


def build_replay(user: User, days=30):
    start = datetime.utcnow() - timedelta(days=days)
    rows = (
        AiFeedback.query.filter(
            AiFeedback.user_id == user.id,
            AiFeedback.created_at >= start,
        )
        .order_by(AiFeedback.created_at.desc())
        .all()
    )
    items = []
    for row in rows:
        if not feedback_is_scorable(row):
            continue
        payload = row.to_dict()
        stamp = row.created_at
        items.append({
            'id': row.id,
            'when': stamp.isoformat() if stamp else None,
            'date': stamp.strftime('%m月%d日') if stamp else '',
            'time': stamp.strftime('%H:%M') if stamp else '',
            'course_title': payload.get('course_title'),
            'overall_score': row.overall_score,
            'suggestion': row.suggestion,
            'mode_label': payload.get('mode_label'),
            'dimensions': payload.get('dimensions') or [],
        })
    return items


SCENE_CARDS = {
    'clarity': {
        'image': 'intro',
        'title': '导入与开场',
        'caption': '把问题先抛给学生',
        'accent': 'orange',
        'label': '表达清晰度',
    },
    'pace': {
        'image': 'ask',
        'title': '提问与候答',
        'caption': '停 8 秒再叫人',
        'accent': 'violet',
        'label': '教学节奏',
    },
    'questioning': {
        'image': 'ask',
        'title': '提问与候答',
        'caption': '停 8 秒再叫人',
        'accent': 'violet',
        'label': '提问质量',
    },
    'structure': {
        'image': 'board',
        'title': '板书与结构',
        'caption': '左结构，右例证',
        'accent': 'orange',
        'label': '课堂结构',
    },
    'interaction': {
        'image': 'interact',
        'title': '互动与回收',
        'caption': '分享后做全班回收',
        'accent': 'violet',
        'label': '互动设计',
    },
    'posture': {
        'image': 'interact',
        'title': '教态与站位',
        'caption': '肩线对学生，侧身写板',
        'accent': 'orange',
        'label': '教态与站位',
    },
}


def _dimensions_from_row(row: AiFeedback):
    if row.report_json:
        try:
            payload = json.loads(row.report_json)
            dims = payload.get('dimensions') if isinstance(payload, dict) else None
            if dims:
                return dims
        except (TypeError, ValueError):
            pass
    return [
        {'key': 'clarity', 'label': '表达清晰度', 'score': row.clarity_score or 0},
        {'key': 'pace', 'label': '教学节奏', 'score': row.pace_score or 0},
        {'key': 'interaction', 'label': '互动设计', 'score': row.interaction_score or 0},
    ]


def build_ai_summaries(user: User):
    rows = (
        AiFeedback.query.filter_by(user_id=user.id)
        .order_by(AiFeedback.created_at.desc())
        .limit(12)
        .all()
    )
    rows = [row for row in rows if feedback_is_scorable(row)]
    if not rows:
        return []
    groups = []
    chunk = []
    for row in rows:
        chunk.append(row)
        if len(chunk) == 3:
            groups.append(list(reversed(chunk)))
            chunk = []
    if chunk:
        groups.append(list(reversed(chunk)))

    summaries = []
    for index, group in enumerate(groups[:4]):
        scores = [item.overall_score or 0 for item in group]
        avg = round(sum(scores) / len(scores))
        high = max(scores)
        spread = high - min(scores)
        if avg >= 84 and spread <= 8:
            mood = '稳住'
            pick = 'strong'
        elif high >= 86:
            mood = '高光'
            pick = 'strong'
        else:
            mood = '补练'
            pick = 'weak'

        totals = defaultdict(lambda: {'sum': 0, 'n': 0, 'label': ''})
        for row in group:
            for item in _dimensions_from_row(row):
                key = item.get('key') or 'clarity'
                totals[key]['sum'] += int(item.get('score') or 0)
                totals[key]['n'] += 1
                totals[key]['label'] = item.get('label') or SCENE_CARDS.get(key, {}).get('label') or key
        ranked = sorted(
            (
                {
                    'key': key,
                    'score': round(value['sum'] / value['n']) if value['n'] else 0,
                    'label': value['label'],
                }
                for key, value in totals.items()
            ),
            key=lambda item: item['score'],
        )
        focus = ranked[-1] if pick == 'strong' and ranked else (ranked[0] if ranked else {'key': 'clarity', 'label': '表达清晰度', 'score': avg})
        visual = SCENE_CARDS.get(focus['key'], SCENE_CARDS['clarity'])
        start = group[0].created_at.strftime('%m/%d') if group[0].created_at else ''
        end = group[-1].created_at.strftime('%m/%d') if group[-1].created_at else start
        if mood == '高光':
            body = (
                f'这 {len(group)} 次里打出了 {high} 分高光。{visual["label"]}最亮。'
                f'把「{visual["caption"]}」再练成肌肉记忆。'
            )
        elif mood == '稳住':
            body = (
                f'近 {len(group)} 次综合分约 {avg}，起伏不大。'
                f'{visual["label"]}已经能托住课堂，下一档把其余维度也拉齐。'
            )
        else:
            body = (
                f'近 {len(group)} 次综合约 {avg}。最该补的是{visual["label"]}。'
                f'下一阶段只做一件事：{visual["caption"]}。'
            )
        summaries.append({
            'id': f'sum-{index}',
            'range': f'{start} – {end}',
            'title': visual['title'],
            'caption': visual['caption'],
            'accent': visual['accent'],
            'image': visual['image'],
            'tag': f'近 {len(group)} 练战报',
            'highlight': f'{mood} {high}',
            'mood': mood,
            'avg_score': avg,
            'times': len(group),
            'body': body,
        })
    return summaries


def list_journals(user: User):
    rows = (
        TrainingJournal.query.filter_by(user_id=user.id)
        .order_by(TrainingJournal.created_at.desc())
        .limit(40)
        .all()
    )
    return [row.to_dict() for row in rows]


def add_journal(user: User, entry_date: str, body: str):
    text = (body or '').strip()
    day = (entry_date or datetime.utcnow().strftime('%Y-%m-%d')).strip()[:10]
    if not text:
        return None, '请先写一句训练日志'
    row = TrainingJournal(user_id=user.id, entry_date=day, body=text)
    db.session.add(row)
    db.session.commit()
    return row.to_dict(), None


def compute_badges(user: User):
    sessions = TrainingSession.query.filter_by(user_id=user.id).count()
    completed = TrainingSession.query.filter_by(user_id=user.id, status='completed').count()
    feedbacks = AiFeedback.query.filter_by(user_id=user.id).all()
    best = max((row.overall_score for row in feedbacks), default=0)
    full_runs = sum(1 for row in feedbacks if (row.session and (row.session.duration_minutes or 0) >= 10))
    badges = [
        {'id': 'first', 'name': '初次上台', 'earned': sessions >= 1, 'hint': '完成第一次微格训练'},
        {'id': 'habit', 'name': '勤练不辍', 'earned': sessions >= 5, 'hint': '累计 5 次训练'},
        {'id': 'closer', 'name': '完整收束', 'earned': full_runs >= 1, 'hint': '跑完一次 10 分钟课'},
        {'id': 'ask', 'name': '提问达人', 'earned': any((row.suggestion or '').find('提问') >= 0 for row in feedbacks), 'hint': '在提问技能上留下评课'},
        {'id': 'high', 'name': '高分片段', 'earned': best >= 86, 'hint': '单次综合分达到 86'},
        {'id': 'archive', 'name': '有迹可循', 'earned': completed >= 3, 'hint': '完成 3 次评课归档'},
    ]
    earned = sum(1 for item in badges if item['earned'])
    xp = sessions * 20 + completed * 30 + best
    level = min(9, 1 + earned + sessions // 4)
    return badges, xp, level


def build_profile(user: User):
    badges, xp, level = compute_badges(user)
    payload = user.to_dict()
    payload['badges'] = badges
    payload['xp'] = xp
    payload['level'] = level
    payload['level_label'] = f'Lv.{level} 微格学员'
    session_count = TrainingSession.query.filter_by(user_id=user.id).count()
    remain = 0 if level >= 9 else (4 - (session_count % 4) or 4)
    recent = (
        AiFeedback.query.filter_by(user_id=user.id)
        .order_by(AiFeedback.created_at.desc())
        .limit(3)
        .all()
    )
    payload['session_count'] = session_count
    payload['xp_percent'] = 100 if level >= 9 else round(((session_count % 4) / 4) * 100)
    payload['next_hint'] = '已达演示等级上限' if level >= 9 else f'再完成 {remain} 次训练可提升等级'
    payload['recent_feedbacks'] = [
        {
            'id': row.id,
            'overall_score': row.overall_score,
            'suggestion': row.suggestion,
            'course_title': row.session.course.title if row.session and row.session.course else '微格训练',
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        for row in recent
    ]
    if not payload.get('school'):
        payload['school'] = '师范学院（演示）'
    if not payload.get('major'):
        payload['major'] = '小学教育'
    if not payload.get('grade'):
        payload['grade'] = '本科三年级'
    if not payload.get('bio'):
        payload['bio'] = '关注课堂导入、提问候答与板书结构。目标是把 8 分钟片段练成可迁移的教学习惯。'
    return payload


def update_profile(user: User, data: dict):
    if 'name' in data and str(data.get('name') or '').strip():
        user.name = str(data.get('name')).strip()[:64]
    if 'bio' in data:
        user.bio = str(data.get('bio') or '').strip()[:500]
    if 'school' in data:
        user.school = str(data.get('school') or '').strip()[:128]
    if 'major' in data:
        user.major = str(data.get('major') or '').strip()[:128]
    if 'grade' in data:
        user.grade = str(data.get('grade') or '').strip()[:32]
    if data.get('role') in {'student', 'teacher'}:
        user.role = data.get('role')
    db.session.commit()
    return build_profile(user)
