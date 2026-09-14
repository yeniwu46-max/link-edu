"""Real provider acceptance with synthetic teaching. Dedicated ledger capped at 70 CNY.
No microphone, camera, speaker or real participant claims. Requires --paid.
"""
import argparse, os, sys, json, secrets, time, threading
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paid', action='store_true')
    args = parser.parse_args()
    if not args.paid: parser.error('Use --paid to authorize budgeted cloud calls')
    output = ROOT/'artifacts/private/competition-cloud'
    output.mkdir(parents=True, exist_ok=True)
    startfile = output/'budget-start.txt'
    if not startfile.exists(): startfile.write_text(datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
    from dotenv import load_dotenv
    load_dotenv(ROOT/'backend/.env')
    os.environ.update(DATABASE_URL='sqlite:///'+(output/'ledger.db').as_posix(), SEED_ON_STARTUP='false',
        PUBLIC_DEPLOYMENT='false', JWT_SECRET_KEY=secrets.token_hex(32), DELIVERY_BUDGET_CNY='70',
        DELIVERY_BUDGET_START=startfile.read_text(), USD_CNY_BUDGET_RATE='8')
    sys.path.insert(0, str(ROOT/'backend'))
    from app import app, init_db
    from extensions import db
    from services.classroom_providers import chat
    from services.classroom_budget import status
    from services.classroom_speech import probe_asr
    from classroom_probe_support import teacher_audio, verify_room
    from validate_classroom_loop import stream_classroom, wait_report, LESSON
    import httpx
    from werkzeug.serving import make_server
    import wave
    init_db()
    app.config['TESTING'] = True
    result = {'kind': 'real_providers_synthetic_teaching', 'checks': []}
    clips = []
    with app.app_context():
        for name, fn in [('dialogue', lambda: chat('Return JSON with ok=true.', {'test': 'release synthetic'}, max_tokens=64)),
                         ('asr_handshake', probe_asr)]:
            started = time.monotonic()
            try: fn(); record = {'name': name, 'passed': True}
            except Exception as e: record = {'name': name, 'passed': False, 'error': str(e)[:160] if isinstance(e, ValueError) else type(e).__name__}
            record['seconds'] = round(time.monotonic()-started, 3)
            result['checks'].append(record)
            print(json.dumps(record, ensure_ascii=True), flush=True)
        try:
            for i, phrase in enumerate(LESSON):
                target = output/f'teacher-{i}.wav'
                if target.exists():
                    with wave.open(str(target), 'rb') as wav: raw = wav.readframes(wav.getnframes())
                else:
                    raw = teacher_audio(phrase)
                    with wave.open(str(target), 'wb') as wav:
                        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(raw)
                clips.append(raw)
            result['checks'].append({'name': 'tts', 'passed': True, 'clips': len(clips)})
        except Exception as e:
            result['checks'].append({'name':'tts', 'passed':False, 'error':str(e)[:160] if isinstance(e, ValueError) else type(e).__name__})
    if len(clips) == 4 and all(c['passed'] for c in result['checks']):
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}', timeout=60, trust_env=False) as client:
                account = 'release-'+secrets.token_hex(6); password = secrets.token_urlsafe(16)
                client.post('/api/auth/register', json=dict(account=account, password=password, name='合成验收账户'))
                client.headers['Authorization'] = 'Bearer '+client.post('/api/auth/login',json=dict(account=account,password=password)).json()['access_token']
                sid = client.post('/api/classroom/sessions',json=dict(audio_consent=True,camera_consent=True)).json()['session_id']
                result['stream'] = stream_classroom(client, sid, clips, 180)
                result['room'] = wait_report(client, sid)
                result['checks'].append({'name':'classroom_180s', **verify_room(result['room'])})
        except Exception as e:
            result['checks'].append({'name':'classroom_180s','passed':False,'error':str(e)[:160] if isinstance(e,ValueError) else type(e).__name__})
        finally: server.shutdown(); thread.join(timeout=3)
    with app.app_context(): result['budget'] = status()
    (output/('result-'+os.environ.get('CLASSROOM_LLM_PROVIDER','deepseek')+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'checks':result['checks'],'budget':result['budget']},ensure_ascii=True))

if __name__ == '__main__': main()
