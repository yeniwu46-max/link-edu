from services.classroom_behaviors import analyze_behaviors


def event(number, kind, at_ms, **data):
    return {'id': number, 'type': kind, 'at_ms': at_ms, 'data': data}


def test_complete_question_response_and_followup_link_original_events():
    analysis = analyze_behaviors([
        event(1, 'transcript', 1000, text='小雨，为什么要平均分？'),
        event(2, 'student', 3200, reply_id='r1', text='因为每份要一样多。'),
        event(3, 'playback', 5200, reply_id='r1', status='playback_completed'),
        event(4, 'transcript', 7100, text='你能举个例子再解释一下吗？'),
    ])
    indexed = {(item['kind'], tuple(item['event_ids'])) for item in analysis['segments']}
    assert ('teacher_question', (1,)) in indexed
    assert ('student_response', (2, 3)) in indexed
    assert ('question_response', (1, 2, 3)) in indexed
    assert ('teacher_followup', (2, 3, 4)) in indexed
    assert any('不是教师候答时间' in note for item in analysis['segments']
               if item['kind'] == 'question_response' for note in item['limitations'])


def test_unplayed_or_interrupted_reply_never_becomes_complete_interaction():
    analysis = analyze_behaviors([
        event(1, 'transcript', 1000, text='小雨，什么是平均分？'),
        event(2, 'student', 2000, reply_id='r1', text='每份一样多。'),
        event(3, 'playback', 3200, reply_id='r1', status='playback_completed'),
        event(4, 'interrupt', 3300, reply_id='r1'),
        event(5, 'student', 4000, reply_id='r2', text='我不知道。'),
        event(6, 'playback', 5000, reply_id='r2', status='playback_failed'),
        event(7, 'transcript', 6000, text='为什么没有回答？'),
    ])
    assert not {'student_response', 'question_response', 'teacher_followup', 'teacher_feedback'} & {
        item['kind'] for item in analysis['segments']}


def test_rhetorical_question_and_missing_timestamp_do_not_create_false_chain():
    analysis = analyze_behaviors([
        event(1, 'transcript', 1000, text='难道不应该平均分吗？'),
        {'id': 2, 'type': 'transcript', 'at_ms': None, 'data': {'text': '小明，请解释平均分。'}},
        event(3, 'student', 2200, reply_id='r1', text='是。'),
        event(4, 'playback', 3000, reply_id='r1', status='playback_completed'),
    ])
    assert all(item['kind'] != 'question_response' for item in analysis['segments'])


def test_board_and_motion_context_require_observable_visual_evidence():
    analysis = analyze_behaviors([
        event(1, 'transcript', 10000, text='请看黑板，我们把圆平均分成四份。'),
        event(2, 'vision', 12000, confidence=.9, scene_detected=True,
              observations='画面可见板书，黑板上写有四分之一。'),
        event(3, 'pose', 13000, motion_version=2, body={'status': 'observed'}),
        event(4, 'vision', 18000, confidence=.95, scene_detected=True,
              observations='画面没有板书，教师在桌边。'),
        event(5, 'vision', 19000, confidence=.4, scene_detected=True,
              observations='可见板书但看不清文字。'),
        event(6, 'pose', 21000, motion_version=2, body={'status': 'multiple'}),
    ])
    indexed = {(item['kind'], tuple(item['event_ids'])) for item in analysis['segments']}
    assert ('board_observation', (2,)) in indexed
    assert ('board_speech_context', (1, 2)) in indexed
    assert ('motion_speech_context', (1, 3)) in indexed
    assert all(4 not in ids and 5 not in ids and 6 not in ids for kind, ids in indexed
               if kind in {'board_observation', 'board_speech_context', 'motion_speech_context'})


def test_post_question_silence_uses_vad_events_and_excludes_student_playback():
    recorded = [
        event(1, 'teacher_speech_start', 1000, source='asr_vad'),
        event(2, 'teacher_speech_stop', 2200, source='asr_vad'),
        event(3, 'transcript', 2500, text='小明，为什么要平均分？'),
        event(4, 'teacher_speech_start', 6500, source='asr_vad'),
    ]
    analysis = analyze_behaviors(recorded)
    pauses = [item for item in analysis['segments'] if item['kind'] == 'post_question_silence']
    assert len(pauses) == 1 and pauses[0]['event_ids'] == [2, 3, 4]
    recorded.insert(-1, event(5, 'student', 4000, reply_id='r', text='每份相等。'))
    assert not any(item['kind'] == 'post_question_silence'
                   for item in analyze_behaviors(recorded)['segments'])
