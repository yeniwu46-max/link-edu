"""ASR-final teacher turns, with synthetic model output and no cloud/audio calls."""
import queue
import pytest

from services import classroom_runtime as runtime
from test_classroom_base import app
from test_classroom_runtime import live


def final(obj, identity, text):
    obj.handle_asr({
        'type': 'conversation.item.input_audio_transcription.completed',
        'item_id': identity,
        'transcript': text,
    })


def generate_answer(obj, monkeypatch, student_id):
    """Exercise actual generation context and dispatch, faking only the LLM."""
    output = {
        'action': 'answer', 'student_id': student_id,
        'text': '要平均分成两份，每一份是二分之一。',
        'understanding': '平均分成两份', 'open_question': '', 'resolved': True,
    }
    captured = {}

    def chat(system, payload, session_id, control, on_draft):
        captured.update(payload)
        on_draft({**output, 'text': output['text'][:5]})
        on_draft(output)
        return output

    monkeypatch.setattr(runtime, 'chat_stream', chat)
    obj.worker = lambda work: work()
    obj.generate()
    while True:
        try:
            kind, data = obj.inbox.get_nowait()
        except queue.Empty:
            break
        obj.dispatch(kind, data)
    return captured


def test_named_student_split_across_asr_finals_still_receives_question(app, monkeypatch):
    obj = live(app)
    # A pause after the name is normal speech endpointing, not withdrawing the call.
    final(obj, 'call', '小林。')
    final(obj, 'question', '把一个蛋糕平均分成两份，每份是多少？')
    payload = generate_answer(obj, monkeypatch, 'lin')

    assert payload['named_student'] == 'lin'
    assert obj.pending and obj.pending['student_id'] == 'lin'
    assert any(message['type'] == 'reply_delta' for message in obj.ws.messages)


@pytest.mark.parametrize(('delay', 'expected'), [(14.99, 'lin'), (15, 'lin'), (15.01, None)])
def test_split_call_expires_after_fifteen_seconds(app, monkeypatch, delay, expected):
    obj = live(app)
    clock = [100.0]
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: clock[0])
    final(obj, 'call', '小林。')
    final(obj, 'question', '每份是多少？')
    clock[0] += delay

    assert obj.named_student() == expected


def test_split_call_expires_after_two_following_final_segments(app):
    obj = live(app)
    final(obj, 'call', '小林。')
    final(obj, 'context', '把蛋糕平均分成两份。')
    assert obj.named_student() == 'lin'
    final(obj, 'question', '每份是多少？')
    assert obj.named_student() == 'lin'
    # Duplicate delivery does not consume another segment of the call's window.
    final(obj, 'question', '每份是多少？')
    assert obj.named_student() == 'lin'
    final(obj, 'next-topic', '我们接下来看第二张图。')

    assert obj.named_student() is None


def test_new_student_name_replaces_previous_split_call(app):
    obj = live(app)
    final(obj, 'first-call', '小林。')
    final(obj, 'replace-call', '小雨，你来回答。')
    final(obj, 'question', '每份是多少？')

    assert obj.named_student() == 'yu'


def test_reply_consumes_split_call_before_next_teacher_turn(app, monkeypatch):
    obj = live(app)
    final(obj, 'call', '小林。')
    final(obj, 'question', '每份是多少？')
    generate_answer(obj, monkeypatch, 'lin')
    monkeypatch.setattr(runtime, 'speak', lambda *args: None)
    obj.start_reply(obj.pending)
    final(obj, 'next-question', '如果平均分成三份呢？')

    assert obj.named_student() is None


def test_streamed_reply_audio_requires_playback_ack_before_listening(app, monkeypatch):
    obj = live(app)
    final(obj, 'question', '小林，每份是多少？')
    payload = generate_answer(obj, monkeypatch, 'lin')
    assert payload['named_student'] == 'lin'
    generated = [m for m in obj.ws.messages if m['type'] == 'reply_delta']
    assert len(generated) == 2
    assert not any(m['type'] == 'audio' for m in obj.ws.messages)

    def synthetic_speech(text, session_id, voice, cancelled, on_audio):
        assert session_id == obj.sid and voice == 'Serena'
        assert not cancelled()
        on_audio('AAAA', 24000)
        on_audio('AQABAA==', 24000)

    monkeypatch.setattr(runtime, 'speak', synthetic_speech)
    obj.start_reply(obj.pending)
    while not obj.inbox.empty():
        obj.dispatch(*obj.inbox.get_nowait())

    reply = next(m for m in obj.ws.messages if m['type'] == 'reply')
    audio = [m for m in obj.ws.messages if m['type'] == 'audio']
    end = next(m for m in obj.ws.messages if m['type'] == 'audio_end')
    assert ''.join(m['delta'] for m in generated) == reply['text']
    assert all(m['student_id'] == 'lin' for m in generated)
    assert len(audio) == 2 and all(m['reply_id'] == reply['reply_id'] for m in audio)
    assert all(m['sample_rate'] == 24000 for m in audio)
    assert end['reply_id'] == reply['reply_id'] and end['ok'] is True
    assert obj.speaking and not any(m['type'] == 'listening' for m in obj.ws.messages)
    assert not any(e['type'] == 'playback' for e in obj.history)

    obj.incoming({'type': 'playback_done', 'reply_id': reply['reply_id'], 'event_id': 'played'})
    assert not obj.speaking and obj.reply_id is None
    assert obj.ws.messages[-1]['type'] == 'listening'
    playback = [e for e in obj.history if e['type'] == 'playback']
    assert len(playback) == 1 and playback[0]['data']['status'] == 'playback_completed'


def test_new_named_question_does_not_accept_an_older_raised_question(app):
    obj = live(app)
    obj.pending = {
        'action': 'raise', 'student_id': 'ming',
        'text': '老师，不同大小的蛋糕的一半一样多吗？',
    }
    final(obj, 'new-question', '小明，分母为什么是二？')

    assert obj.pending is None
    assert obj.needs_evaluation()


def test_brief_invitation_accepts_pending_question_without_regenerating(app):
    obj = live(app)
    pending = {
        'action': 'raise', 'student_id': 'ming',
        'text': '老师，不同大小的蛋糕的一半一样多吗？',
    }
    obj.pending = pending
    final(obj, 'accept', '小明，你说。')

    assert obj.pending == pending
    assert not obj.needs_evaluation()


def test_direct_question_can_stream_answer_before_proactive_budget(app, monkeypatch):
    obj = live(app)
    final(obj, 'question', '小林，把蛋糕平均分成两份，每份是多少？')
    assert obj.content_seconds < 20 and not obj.can_ask()
    payload = generate_answer(obj, monkeypatch, 'lin')

    assert payload['named_student'] == 'lin'
    assert obj.pending and obj.pending['action'] == 'answer'
    assert any(message['type'] == 'reply_delta' for message in obj.ws.messages)


def test_group_question_is_explicit_in_generation_context_without_proactive_permission(app, monkeypatch):
    obj = live(app)
    final(obj, 'group-question', '同学们，谁能说说什么是平均分？')
    payload = generate_answer(obj, monkeypatch, 'ming')
    assert payload['response_required'] is True
    assert payload['current_teacher_text'] == obj.last_final
    assert payload['allow_proactive'] is False
    assert obj.pending['action'] == 'answer'


def test_model_wait_on_direct_question_is_visible_failure_not_silent_discard(app):
    obj = live(app)
    final(obj, 'question', '小明，什么是平均分？')
    obj.worker = lambda work: None
    obj.generate()
    obj.dispatch('decision', (obj.revision, 'ming', False, {'action': 'wait', 'student_id': 'ming', 'text': ''}))
    assert obj.generation_failed is True
    assert obj.ws.messages[-1]['type'] == 'generation_failed'
