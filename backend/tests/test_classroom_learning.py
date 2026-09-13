from services.classroom_learning import normalize_states, route_intent, apply_updates
from test_classroom_base import app


def test_routing_distinguishes_mentions_questions_and_resume():
    assert route_intent('小林很安静。')['intent'] == 'lecture'
    assert route_intent('小林，请说说为什么必须平均分？')['student_id'] == 'lin'
    assert route_intent('难道不应该平均分吗？')['intent'] == 'rhetorical'
    assert route_intent('我想想，应该怎么讲呢？')['intent'] == 'self_talk'
    assert route_intent('大家说说什么是平均分？')['intent'] == 'class_question'
    assert route_intent('继续', interrupted='yu')['student_id'] == 'yu'
    assert route_intent('请小林同学回答')['response_required']


def test_silent_update_and_interrupted_reply_do_not_resolve_question(app):
    from test_classroom_runtime import live
    from classroom_models import Classroom
    from extensions import db
    obj=live(app)
    obj.handle_asr({'type':'conversation.item.input_audio_transcription.completed','item_id':'explain',
                   'transcript':'平均分就是每份同样大，大小不一样不能表示二分之一。'})
    event=obj.history[-1]['id']
    obj.generate()
    obj.dispatch('decision',(obj.revision,None,False,{'action':'wait','state_updates':[
        {'student_id':'yu','understanding':'每份必须同样大','misconceptions':[], 'concepts':['平均分'],'correction_event_ids':[event]}]}))
    assert db.session.get(Classroom,obj.sid).students['yu']['understanding']=='每份必须同样大'
    obj.last_final='小雨，请解释什么是平均分？'
    obj.start_reply({'student_id':'yu','action':'answer','text':'每份同样大才是平均分。','resolved':True})
    assert obj.students['yu']['open_question'] == obj.last_final
    old=obj.reply_id
    obj.interrupt()
    assert obj.students['yu']['interrupted']['reply_id']==old
    obj.incoming({'event_id':'late-completion','type':'playback_done','reply_id':old})
    assert obj.students['yu']['interrupted'] is not None
    obj.last_final='继续'
    obj.generate()
    assert obj.turn_intent['student_id']=='yu'


def test_correction_on_silent_turn_requires_real_explanation_reference():
    states = normalize_states({})
    assert states['yu']['misconceptions']
    events = [{'id': 1, 'type': 'transcript', 'data': {'text': '不对'}},
              {'id': 2, 'type': 'transcript', 'data': {'text': '平均分就是每份同样大，大小不一样不能表示二分之一。'}}]
    update = {'student_id': 'yu', 'understanding': '每份必须同样大', 'misconceptions': [],
              'concepts': ['平均分'], 'correction_event_ids': [1]}
    assert apply_updates(states, [update], events)['yu'] == states['yu']
    update['correction_event_ids'] = [2]
    changed = apply_updates(states, [update], events)
    assert changed['yu']['understanding'] == '每份必须同样大'
    assert changed['yu']['misconceptions'] == []
    assert changed['yu']['correction_event_ids'] == [2]
    update['correction_event_ids'] = [999]
    assert apply_updates(states, [update], events) == states


def test_closed_runtime_ignores_late_generation_and_capture(app):
    from test_classroom_runtime import live
    obj = live(app)
    before = obj.students.copy()
    obj.closed.set()
    obj.dispatch('decision', (obj.revision, None, False, {'action': 'answer', 'student_id': 'lin', 'text': '迟到回答'}))
    obj.incoming({'type': 'audio', 'event_id': 'late-audio', 'audio': 'invalid'})
    assert obj.students == before and obj.reply_id is None
