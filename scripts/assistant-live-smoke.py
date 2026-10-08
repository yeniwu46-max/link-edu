"""Explicit live check using synthetic PCM and existing budgeted providers."""
import argparse, base64, json, sys, time, urllib.request
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--live', action='store_true')
if not parser.parse_args().live:
    raise SystemExit('Use --live for budgeted provider calls')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import app
from services.classroom_speech import speak
import websocket
URL = 'http://127.0.0.1:5001'

def call(path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token: headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(URL+'/api/'+path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    return json.load(urllib.request.urlopen(req, timeout=12))

def run():
    token = call('auth/login', {'account':'demo','password':'link123','role':'student'})['access_token']
    cap = call('assistant/capabilities', token=token)
    if not cap['voice_available']: raise RuntimeError(cap['message'])
    pcm, rates = [], []
    with app.app_context():
        speak('请问如何开始一次微格训练？', None, 'Cherry', lambda:False, lambda audio,rate:(pcm.append(base64.b64decode(audio)),rates.append(rate)))
    if set(rates) != {16000}: raise RuntimeError('Smoke requires configured 16kHz TTS')
    audio = b''.join(pcm) + bytes(64000)
    ticket = call('assistant/ticket', {'mode':'voice'}, token)['ticket']
    sock = websocket.create_connection(URL.replace('http:','ws:')+'/api/assistant/live', timeout=35)
    try:
        sock.send(json.dumps({'ticket':ticket}))
        ready = json.loads(sock.recv()); sid = ready['session_id']
        start = time.monotonic(); first_audio = None; recognized = False; answered = False
        for pos in range(0,len(audio),3200):
            sock.send(json.dumps({'type':'audio','session_id':sid,'audio':base64.b64encode(audio[pos:pos+3200]).decode()})); time.sleep(.1)
        end_input = time.monotonic()
        while time.monotonic()-start < 70:
            event = json.loads(sock.recv()); kind = event.get('type')
            if kind == 'recognition' and event.get('final'): recognized = True
            if kind == 'answer': answered = True
            if kind == 'audio' and first_audio is None: first_audio = time.monotonic()
            if kind == 'error': raise RuntimeError(event.get('message','provider error'))
            if kind == 'audio_end': break
        print(json.dumps({'input_audio_seconds':round((len(audio)-64000)/32000,2),'recognized':recognized,'answer':answered,'audio':first_audio is not None,'audio_after_end_input_ms':round((first_audio-end_input)*1000) if first_audio else None,'end_to_end_seconds':round(time.monotonic()-start,2),'media':'synthetic PCM, real configured providers; no device recording'},ensure_ascii=False))
        sock.send(json.dumps({'type':'stop','session_id':sid}))
    finally: sock.close()

try: run()
except Exception as exc:
    print(json.dumps({'error':type(exc).__name__,'message':str(exc)[:180]},ensure_ascii=False)); sys.exit(1)
