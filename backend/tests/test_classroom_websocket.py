"""Real local HTTP/WebSocket transport, explicitly fake speech/model providers."""
import json
import queue
import threading
import time
import websocket
from werkzeug.serving import make_server
from services import classroom_runtime as runtime, classroom_reports as reports
from test_classroom_base import app
from test_classroom_runtime import live
from test_classroom_api import headers

def test_real_websocket_auth_audio_events_finish_and_single_use(app,monkeypatch):
    obj=live(app)
    class FakeASR:
        def __init__(self,sid): self.events=queue.Queue(); self.closed=False
        def receive(self):
            try: return self.events.get(timeout=.05)
            except queue.Empty: raise websocket.WebSocketTimeoutException()
        def audio(self,encoded):
            self.events.put({'type':'conversation.item.input_audio_transcription.completed','item_id':'fixture-1','transcript':'合成协议测试：必须平均分。'})
        def send(self,kind):
            if kind=='session.finish': self.events.put({'type':'session.finished'})
        def settle(self): pass
        def close(self): self.closed=True
    monkeypatch.setattr(runtime,'ASR',FakeASR)
    monkeypatch.setattr(runtime,'chat',lambda *a,**k:{'action':'wait'})
    monkeypatch.setattr(reports,'chat',lambda *a,**k:{'dimensions':[{'key':'clarity','score':None,'event_ids':[]}]})
    ticket=app.test_client().post(f'/api/classroom/sessions/{obj.sid}/ticket',headers=headers(1)).json['ticket']
    server=make_server('127.0.0.1',0,app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    sock=None
    def until(kind):
        for _ in range(30):
            message=json.loads(sock.recv())
            if message['type']==kind: return message
        raise AssertionError(f'No {kind} event')
    try:
        sock=websocket.create_connection(f'ws://127.0.0.1:{server.server_port}/api/classroom/live',timeout=3)
        sock.send(json.dumps({'ticket':ticket}))
        assert until('connected')['session_id']==obj.sid
        until('ready')
        sock.send(json.dumps({'type':'audio','event_id':'audio-1','audio':'AAAA'}))
        transcript=until('event')['event']
        assert transcript['type']=='transcript' and '合成协议测试' in transcript['data']['text']
        sock.send(json.dumps({'type':'finish','event_id':'finish-1'}))
        until('ended')
        sock.close()
        sock=websocket.create_connection(f'ws://127.0.0.1:{server.server_port}/api/classroom/live',timeout=3)
        sock.send(json.dumps({'ticket':ticket}))
        assert sock.recv()==''
    finally:
        if sock: sock.close()
        server.shutdown();thread.join(timeout=3)
        deadline=time.monotonic()+3
        while obj.sid in reports.jobs and time.monotonic()<deadline: time.sleep(.01)
