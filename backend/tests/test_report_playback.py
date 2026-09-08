import pytest
from services.classroom_reports import validate_report


def evaluate(tail):
    events = [{'id':1, 'type':'student', 'data':{'reply_id':'r', 'text':'平均分'}}] + tail
    return validate_report({'dimensions':[{'key':'interaction','score':90,'event_ids':[1]}]},events,[])


@pytest.mark.parametrize('tail', [[],
    [{'id':2,'type':'playback','data':{'reply_id':'r','status':'playback_failed'}}],
    [{'id':2,'type':'interrupt','data':{'reply_id':'r'}}],
    [{'id':2,'type':'playback','data':{'reply_id':'other','status':'playback_completed'}}],
    [{'id':2,'type':'playback','data':{'reply_id':'r','status':'playback_completed'}},
     {'id':3,'type':'interrupt','data':{'reply_id':'r'}}],
])
def test_unconfirmed_student_speech_cannot_support_score(tail):
    assert evaluate(tail)['overall_score'] is None


def test_matching_completed_playback_can_support_score():
    assert evaluate([{'id':2,'type':'playback','data':{'reply_id':'r','status':'playback_completed'}}])['overall_score']==90
