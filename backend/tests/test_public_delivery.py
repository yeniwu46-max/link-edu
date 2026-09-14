"""Release acceptance. Synthetic providers; real HTTP/WebSocket and database."""
import base64
from datetime import datetime, timedelta
import json
import os
import queue
import threading
import time
import pytest
import websocket
from werkzeug.serving import make_server
from extensions import db
from models import User, Course, Resource
from classroom_models import Classroom, ClassroomEvent
from services import classroom_runtime as runtime, classroom_reports as reports
from services.classroom_budget import reserve, settle
from services.public_access import daily_quota
from test_classroom_base import app
from test_classroom_api import headers


def user(uid):
    db.session.add(User(id=uid, account=f'isolated-{uid}', name=f'合成用户{uid}', password_hash='unused'))
    db.session.commit()


def create_room(client, uid):
    return client.post('/api/classroom/sessions', headers=headers(uid),
                       json={'audio_consent': True, 'camera_consent': True})


def test_catalog_is_idempotent_without_users(app):
    from seed import ensure_demo_catalog
    ensure_demo_catalog()
    counts = (Course.query.count(), Resource.query.count())
    ensure_demo_catalog()
    assert counts == (Course.query.count(), Resource.query.count())
    assert min(counts) > 0 and User.query.count() == 0


def test_public_privacy_quota_origin_and_paid_entrypoints(app):
    app.config.update(PUBLIC_DEPLOYMENT=True, PUBLIC_ORIGINS=['https://demo.example'], CLASSROOM_DAILY_LIMIT=2)
    user(1)
    client = app.test_client()
    caps = client.get('/api/classroom/capabilities', headers=headers(1)).json
    assert caps['can_probe'] is False
    assert set(caps['budget']) == {'stopped', 'warning', 'pricing_confirmed'}
    assert client.post('/api/classroom/probe', headers=headers(1), json={'service': 'tts'}).status_code == 403
    assert client.post('/api/feedbacks/1/ask', headers=headers(1), json={'question': 'test'}).status_code == 403
    assert client.get('/api/classroom/capabilities', headers={**headers(1), 'Origin': 'https://bad.example'}).status_code == 403
    for _ in range(2):
        response = create_room(client, 1)
        assert response.status_code == 201
        room = db.session.get(Classroom, response.json['session_id'])
        room.state = 'ended'
        db.session.commit()
    assert create_room(client, 1).status_code == 429
    room.started_at -= timedelta(days=1)
    db.session.commit()
    assert daily_quota(1)['remaining_today'] == 1


def test_public_rate_limit_and_malformed_registration(app):
    app.config.update(PUBLIC_DEPLOYMENT=True)
    client = app.test_client()
    assert client.post('/api/auth/register', json={'account': {}, 'password': 'x'}).status_code == 400
    for _ in range(20):
        assert client.post('/api/auth/login', json={}).status_code == 400
    assert client.post('/api/auth/login', json={}).status_code == 429


def test_combined_currency_cap_preserves_old_ledger(app, monkeypatch):
    from services import classroom_credits as credits
    old = reserve('historical', 10)
    monkeypatch.setenv('DELIVERY_BUDGET_CNY', '30')
    monkeypatch.setenv('USD_CNY_BUDGET_RATE', '8')
    monkeypatch.setenv('DELIVERY_BUDGET_START', datetime.utcnow().isoformat())
    monkeypatch.setenv('OPENAI_NEXT_PRICING_CONFIRMED', 'true')
    reserve('synthetic-new', 10)
    credits.reserve('test', 'dialogue', 'synthetic', 2)  # 26 CNY total, old 10 not counted.
    with pytest.raises(ValueError, match='本轮'):
        reserve('over-limit', 2)
    with pytest.raises(ValueError, match='本轮'):
        credits.reserve('test', 'dialogue', 'synthetic', .2)
    with pytest.raises(ValueError):
        settle(old, float('nan'), {})


def test_concurrent_currencies_share_one_reservation_cap(app, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from services import classroom_credits as credits, delivery_budget
    monkeypatch.setenv('DELIVERY_BUDGET_CNY', '10')
    monkeypatch.setenv('DELIVERY_BUDGET_START', datetime.utcnow().isoformat())
    monkeypatch.setenv('USD_CNY_BUDGET_RATE', '8')
    monkeypatch.setenv('OPENAI_NEXT_PRICING_CONFIRMED', 'true')
    barrier = threading.Barrier(20)
    def request(index):
        with app.app_context():
            barrier.wait(timeout=10)
            try:
                if index % 2:
                    credits.reserve('test', 'dialogue', 'synthetic', .125)
                else:
                    reserve('synthetic-race', 1)
                return True
            except ValueError as error:
                assert '本轮' in str(error)
                return False
    with ThreadPoolExecutor(max_workers=20) as pool:
        accepted = list(pool.map(request, range(20)))
    assert sum(accepted) == 9
    with db.engine.connect() as connection:
        assert delivery_budget.status(connection)['spent_and_reserved_cny'] == 9


def test_five_live_rooms_sixth_rejected_and_reports_isolated(app, monkeypatch):
    class FakeASR:
        def __init__(self, sid): self.sid, self.events, self.n = sid, queue.Queue(), 0
        def receive(self):
            try: return self.events.get(timeout=.05)
            except queue.Empty: raise websocket.WebSocketTimeoutException()
        def audio(self, encoded):
            self.n += 1
            text = (f'合成课堂{self.sid}第{self.n}段：我们把同一个圆平均分成两份，每份大小一样，才可以用二分之一表示其中一份。'
                    '如果不是同一个整体或者每一份大小不同，就不能直接比较这些分数。小明，请解释为什么一定要平均分？')
            self.events.put({'type': 'final', 'item_id': f'{self.sid}-{self.n}', 'transcript': text, 'speech_seconds': 5})
        def finish(self): self.events.put({'type': 'finished'})
        def drain_expired(self, started, now): return now-started > 2
        def settle(self): pass
        def close(self): pass
    def fake_chat(system, payload, sid, control, on_draft, **kwargs):
        return {'action': 'answer', 'student_id': 'ming', 'intent': 'named_question',
                'text': f'合成课堂{sid}的回答：因为每份必须同样大，才是平均分。', 'understanding': '每份同样大'}
    def fake_report(system, payload, sid, **kwargs):
        ids = [e['id'] for e in payload['events'] if e['type'] == 'transcript']
        return {'dimensions': [{'key': 'clarity', 'score': 75, 'reason': '合成传输验收，非教学成效', 'event_ids': ids}]}
    monkeypatch.setattr(runtime, 'ASR', FakeASR)
    monkeypatch.setattr(runtime, 'chat_stream', fake_chat)
    monkeypatch.setattr(runtime, 'speak', lambda text, sid, voice, cancelled, output: output(base64.b64encode(bytes(3200)).decode(), 16000))
    monkeypatch.setattr(reports, 'chat', fake_report)
    client = app.test_client()
    rooms, tickets, sockets, collected = [], [], [], {}
    for uid in range(1, 7):
        user(uid)
        sid = create_room(client, uid).json['session_id']
        rooms.append(sid)
        tickets.append(client.post(f'/api/classroom/sessions/{sid}/ticket', headers=headers(uid)).json['ticket'])
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def connect(ticket):
        ws = websocket.create_connection(f'ws://127.0.0.1:{server.server_port}/api/classroom/live', timeout=5)
        ws.send(json.dumps({'ticket': ticket}))
        return ws
    def receive_until(ws, kind, sid):
        received = []
        for _ in range(100):
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                raise AssertionError(f'Missing {kind}: {received}')
            assert raw, f'Unexpected close for {sid}'
            item = json.loads(raw)
            received.append(item)
            if item['type'] == 'event':
                assert item['event']['session_id'] == sid
                collected.setdefault(sid, []).append(item['event'])
            if item['type'] == 'audio_end' and item.get('ok'):
                ws.send(json.dumps({'type': 'playback_done', 'event_id': item['reply_id'], 'reply_id': item['reply_id']}))
            if item['type'] == kind: return item
        raise AssertionError(f'Missing {kind}')
    try:
        for sid, ticket in zip(rooms[:5], tickets[:5]):
            ws = connect(ticket); sockets.append(ws)
            assert receive_until(ws, 'connected', sid)['session_id'] == sid
            receive_until(ws, 'ready', sid)
        assert len(runtime.ACTIVE) == 5
        sixth = connect(tickets[5])
        assert json.loads(sixth.recv())['code'] == 'classroom_capacity'
        assert sixth.recv() == ''
        sixth.close()
        for ws in sockets:
            for n in (1, 2): ws.send(json.dumps({'type': 'audio', 'event_id': f'a{n}', 'audio': 'AAAA'}))
        for sid, ws in zip(rooms, sockets): receive_until(ws, 'listening', sid)
        duration = float(os.getenv('LINK_SOAK_SECONDS', '12'))
        deadline = time.monotonic() + duration
        # Real elapsed-time soak, bounded by the 10-minute classroom clock.
        ended = set()
        while time.monotonic() < deadline and len(ended) < 5:
            for sid, ws in zip(rooms, sockets):
                if sid in ended: continue
                ws.settimeout(.2)
                try:
                    raw = ws.recv()  # Also answers server pings during the 10-minute soak.
                    if raw and json.loads(raw)['type'] == 'ended': ended.add(sid)
                except websocket.WebSocketTimeoutException:
                    pass
        for sid, ws in zip(rooms, sockets):
            ws.settimeout(5)
            if sid not in ended:
                ws.send(json.dumps({'type': 'finish', 'event_id': 'end'}))
                receive_until(ws, 'ended', sid)
        for ws in sockets: ws.close()
        until = time.monotonic() + 10
        while (reports.jobs or runtime.ACTIVE) and time.monotonic() < until: time.sleep(.05)
        db.session.expire_all()
        for sid in rooms[:5]:
            room = db.session.get(Classroom, sid)
            assert room.report_state == 'completed', room.report_error
            events = ClassroomEvent.query.filter_by(session_id=sid, kind='transcript').all()
            assert len(events) == 2 and all(f'合成课堂{sid}' in e.payload['text'] for e in events)
            assert set(room.report['dimensions'][0]['event_ids']) == {e.id for e in events}
        assert not runtime.ACTIVE
        fresh = client.post(f'/api/classroom/sessions/{rooms[5]}/ticket', headers=headers(6)).json['ticket']
        ws = connect(fresh); sockets.append(ws)
        receive_until(ws, 'connected', rooms[5])
        ws.close()
    finally:
        for ws in sockets: ws.close()
        for obj in list(runtime.ACTIVE.values()): obj.closed.set()
        server.shutdown(); thread.join(timeout=3)
        until = time.monotonic() + 5
        while (runtime.ACTIVE or reports.jobs) and time.monotonic() < until: time.sleep(.05)
