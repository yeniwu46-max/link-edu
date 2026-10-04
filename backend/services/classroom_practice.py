"""Persisted, evidence-linked practice tasks and conservative retest comparison."""

from classroom_models import Classroom, ClassroomEvent, PracticePlan
from extensions import db
from services.classroom_behaviors import VERSION as BEHAVIOR_VERSION, analyze_behaviors


TASKS = {
    'questioning': ('teacher_followup', '在学生完整回答后，追问一次“为什么”或请其举例。'),
    'interaction': ('teacher_feedback', '听完学生的完整回答后，明确反馈或纠正其回答。'),
    'structure': ('teacher_summary', '在课末用自己的话回顾本节目标与关键概念。'),
    'pace': ('question_response', '提出明确问题，并留出一次能够完整播放的学生回应。'),
    'clarity': ('teacher_question', '解释概念后，提出一个可检验理解的具体问题。'),
}


def proposed_tasks(report, valid_event_ids=None):
    """Use only evidence-backed dimensions; otherwise mark a general practice."""
    dimensions = report.get('dimensions') if isinstance(report, dict) else []
    dimensions = dimensions if isinstance(dimensions, list) else []
    ranked = sorted((d for d in dimensions if isinstance(d, dict) and
                     d.get('key') in TASKS and type(d.get('score')) in (int, float) and
                     0 <= d['score'] <= 100 and isinstance(d.get('event_ids'), list) and
                     any(type(event_id) is int and (valid_event_ids is None or event_id in valid_event_ids)
                         for event_id in d['event_ids'])),
                    key=lambda d: (d['score'], d['key']))
    plans = []
    seen = set()
    for dimension in ranked:
        kind, text = TASKS[dimension['key']]
        if kind in seen:
            continue
        seen.add(kind)
        plans.append({'dimension': dimension['key'], 'target_kind': kind, 'task_text': text,
                      'basis': 'report_evidence', 'source_event_ids': list(dict.fromkeys(
                          event_id for event_id in dimension['event_ids'] if type(event_id) is int and
                          (valid_event_ids is None or event_id in valid_event_ids)))})
        if len(plans) == 3:
            break
    if not plans:
        plans.append({'dimension': 'general', 'target_kind': 'question_response',
                      'task_text': '提出一个关于平均分的具体问题，并完成一次学生回应。',
                      'basis': 'general', 'source_event_ids': []})
    return plans


def ensure_plans(room):
    """Create at most one task per target for this saved report version."""
    if room.report_state != 'completed' or not isinstance(room.report, dict):
        return []
    for old in PracticePlan.query.filter_by(source_session_id=room.session_id, status='suggested').all():
        if old.source_report_version != room.report_version:
            old.status = 'superseded'
    existing = {plan.target_kind: plan for plan in PracticePlan.query.filter_by(
        source_session_id=room.session_id, source_report_version=room.report_version).all()}
    valid_event_ids = {row.id for row in ClassroomEvent.query.filter_by(session_id=room.session_id)
                       .filter(ClassroomEvent.kind.in_(['transcript', 'student', 'pose', 'vision'])).all()}
    for candidate in proposed_tasks(room.report, valid_event_ids):
        kind = candidate['target_kind']
        if kind in existing:
            continue
        plan = PracticePlan(user_id=room.user_id, source_session_id=room.session_id,
                            source_report_version=room.report_version, **candidate,
                            criteria={'behavior_version': BEHAVIOR_VERSION, 'target_kind': kind,
                                      'minimum_observed': 1})
        db.session.add(plan)
        existing[kind] = plan
    return list(existing.values())


def compare_plan(plan):
    criteria = plan.criteria if isinstance(plan.criteria, dict) else {}
    if criteria.get('behavior_version') != BEHAVIOR_VERSION or criteria.get('target_kind') != plan.target_kind:
        return {'status': 'insufficient', 'reason': '行为识别规则版本或目标已变化，无法按原口径比较',
                'behavior_version': BEHAVIOR_VERSION}
    source = db.session.get(Classroom, plan.source_session_id)
    retest = db.session.get(Classroom, plan.retest_session_id) if plan.retest_session_id else None
    if not source or not retest or retest.state != 'ended' or source.topic != retest.topic:
        return {'status': 'insufficient', 'reason': '复练尚未结束或情境不一致'}
    def recorded(room):
        return [row.to_dict() for row in ClassroomEvent.query.filter_by(session_id=room.session_id)
                .order_by(ClassroomEvent.id).all()]
    before_events, after_events = recorded(source), recorded(retest)
    if not any(e['type'] == 'transcript' for e in after_events):
        return {'status': 'insufficient', 'reason': '复练缺少最终教师转写',
                'behavior_version': BEHAVIOR_VERSION}
    before = [s for s in analyze_behaviors(before_events)['segments'] if s['kind'] == plan.target_kind]
    after = [s for s in analyze_behaviors(after_events)['segments'] if s['kind'] == plan.target_kind]
    return {'status': 'observed' if after else 'not_observed', 'behavior_version': BEHAVIOR_VERSION,
            'target_kind': plan.target_kind, 'source_count': len(before), 'retest_count': len(after),
            'source_event_ids': [s['event_ids'] for s in before],
            'retest_event_ids': [s['event_ids'] for s in after],
            'notice': '仅比较同一规则下可观察到的目标行为；次数不是教学质量分数或因果改进证明。'}


def finish_retest_plans(room):
    if room.state != 'ended':
        return
    for plan in PracticePlan.query.filter_by(retest_session_id=room.session_id).all():
        if plan.status != 'completed':
            plan.comparison = compare_plan(plan)
            plan.status = 'completed'
