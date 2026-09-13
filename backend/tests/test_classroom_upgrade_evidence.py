from test_classroom_base import app
from test_classroom_motion import sample
from test_classroom_readiness import sufficient_events
from services.classroom_motion import motion_evidence
from services.classroom_readiness import report_readiness
from services.classroom_reports import validate_report


def test_context_uses_completed_audio_time_and_rejects_failed_replies():
    events=[sample(i) for i in range(1,4)] + [
        {'id':10,'type':'transcript','at_ms':3000,'data':{'text':'请看这两份一样大'}},
        {'id':11,'type':'student','at_ms':1000,'data':{'text':'每份一样大','reply_id':'ok'}},
        {'id':12,'type':'playback','at_ms':4000,'data':{'reply_id':'ok','status':'playback_completed'}},
        {'id':13,'type':'student','at_ms':2000,'data':{'text':'没有说出来','reply_id':'bad'}},
        {'id':14,'type':'playback','at_ms':4000,'data':{'reply_id':'bad','status':'playback_failed'}}]
    result=motion_evidence(events)
    context=result['observations'][0]['context']
    assert {c['event_id'] for c in context} == {10,11}
    assert next(c for c in context if c['event_id']==11)['at_ms']==4000


def test_missing_scene_forces_posture_null_without_erasing_text_score():
    events=sufficient_events()
    readiness=report_readiness(events,30,cloud_vision=True)
    assert readiness['eligible'] and not readiness['dimension_eligibility']['posture']
    report=validate_report({'dimensions':[
        {'key':'clarity','score':80,'reason':'合成','event_ids':[1]},
        {'key':'posture','score':99,'reason':'不能据此评分','event_ids':[5,6,7]}]},events,[],readiness)
    assert next(d for d in report['dimensions'] if d['key']=='posture')['score'] is None
    assert report['overall_score']==80


def test_pause_wall_timestamps_do_not_invalidate_later_evidence():
    events=sufficient_events()
    for e in events:e['at_ms']+=60000
    assert report_readiness(events,90,active_elapsed=30)['eligible']
    assert not report_readiness(events,90,active_elapsed=9)['eligible']
