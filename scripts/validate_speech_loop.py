"""Paid synthetic TTS -> ASR probe. No microphone, no real classroom records."""
import argparse
import base64
import json
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
import websocket

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import app, init_db
from services.classroom_speech import ASR, speak, normalize
from services.classroom_budget import status


def matches_fraction_speech(text):
    # ASR may normalize spoken 二分之一 into 1/2; keep the raw transcript in the artifact.
    return '平均分' in text and ('二分之一' in text or '1/2' in text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=0, help='Repeat synthetic speech, 0=one phrase; maximum240s')
    args = parser.parse_args()
    if not 0 <= args.seconds <= 240:
        parser.error('--seconds must be between0 and240')
    init_db()
    output = ROOT / 'artifacts/private' / ('speech-probe-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    expected = '今天学习分数。同一个整体平均分成两份，每份是它的二分之一。没有平均分就不能这样表示。'
    chunks, events, errors = [], [], []
    asr = None
    stopped = threading.Event()
    started = time.monotonic()
    with app.app_context():
        try:
            def audio(data, sample_rate):
                if sample_rate != 16000:
                    raise ValueError('This probe expects XFYun PCM16000')
                chunks.append(base64.b64decode(data, validate=True))
            speak(expected, None, 'Cherry', stopped.is_set, audio)
            raw = b''.join(chunks)
            if not raw:
                raise ValueError('No synthesized audio')
            with wave.open(str(output / 'synthetic-teacher.wav'), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                wav.writeframes(raw)
            if args.seconds:
                cycle = raw + b'\0' * 6400
                raw = (cycle * (args.seconds*32000//len(cycle) + 1))[:args.seconds*32000]
            asr = ASR(None)
            def receive():
                try:
                    while not stopped.is_set():
                        try: event = normalize(asr.receive())
                        except websocket.WebSocketTimeoutException: continue
                        events.append(event)
                        if event['type'] == 'finished': return
                except Exception as exc:
                    errors.append(str(exc) if isinstance(exc, ValueError) else 'Speech receive failed')
            receiver = threading.Thread(target=receive, daemon=True)
            receiver.start()
            started = time.monotonic()
            for offset in range(0, len(raw), 6400):
                if errors:
                    raise ValueError(errors[0])
                asr.audio(base64.b64encode(raw[offset:offset+6400]).decode())
                time.sleep(max(0, started + min(len(raw), offset+6400)/32000 - time.monotonic()))
            asr.finish()
            receiver.join(timeout=32)
            final = [e for e in events if e['type'] == 'final']
            text = ''.join(e.get('transcript', '') for e in final)
            passed = not errors and bool(events) and events[-1]['type'] == 'finished' and matches_fraction_speech(text)
            result = {'kind':'synthetic_cloud_speech_probe_not_human_classroom', 'passed':passed,
                'expected':expected, 'audio_seconds':len(raw)/32000, 'final_segments':len(final),
                'transcript':text, 'errors':errors, 'seconds':round(time.monotonic()-started,3), 'budget':status()}
        except Exception as exc:
            result = {'kind':'synthetic_cloud_speech_probe_not_human_classroom', 'passed':False,
                      'error':str(exc) if isinstance(exc, ValueError) else 'Speech probe failed', 'budget':status()}
        finally:
            stopped.set()
            if asr: asr.close()
        result['transport'] = getattr(asr, 'stats', {})
        result['observed_final_segments'] = sum(e['type'] == 'final' for e in events)
        result['elapsed_seconds'] = round(time.monotonic()-started, 3)
        (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=True))
        print('Private output: ' + str(output))
        return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
