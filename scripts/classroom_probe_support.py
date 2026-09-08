"""Isolated probe bookkeeping: reserve in the real ledger before any paid call."""
import base64
import secrets
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / 'backend/.env')
sys.path.insert(0, str(ROOT / 'backend'))
from app import app as main_app, create_app
from config import Config
from extensions import db
from classroom_models import ApiUsage
from services.classroom_budget import reserve, settle, status
from services.classroom_speech import speak


def isolated_app(output, allowance=10):
    class ProbeConfig(Config):
        TESTING = True  # Separate localhost fixture, not a second production server.
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + (output / 'synthetic-classroom.db').as_posix()
        JWT_SECRET_KEY = secrets.token_hex(32)
        SEED_ON_STARTUP = False
    probe = create_app(ProbeConfig)
    probe.instance_path = str(output)
    with probe.app_context():
        db.create_all()
        # The normal 90-yuan guard now leaves only the allowance for this run.
        db.session.add(ApiUsage(service='probe_fence',reserved_cny=90-allowance,
                                charged_cny=90-allowance,state='settled',units={'synthetic_fence':True}))
        db.session.commit()
    return probe


def open_reservation():
    with main_app.app_context():
        return reserve('synthetic_probe', 10)


def close_reservation(probe, usage_id, output):
    with probe.app_context():
        cost = max(0, status()['spent_and_reserved_cny'] - 80)
    with main_app.app_context():
        settle(usage_id, cost, {'kind':'synthetic_cloud_classroom', 'artifact':output.name})
        return status()


def teacher_audio(text):
    chunks = []
    started = time.monotonic()
    def chunk(encoded, rate):
        if rate != 16000:
            raise ValueError('Probe requires XFYun 16kHz PCM')
        chunks.append(base64.b64decode(encoded, validate=True))
    try:
        speak(text, None, 'Cherry', lambda:False, chunk)
    except ValueError as exc:
        raise ValueError(f'{exc}; teacher_chars={len(text)}, elapsed={time.monotonic()-started:.2f}s, received_pcm_bytes={sum(map(len,chunks))}') from None
    raw = b''.join(chunks)
    if not raw:
        raise ValueError('No synthetic teacher audio returned')
    return raw


def verify_room(room):
    events = room.get('events', [])
    ids = {e['id'] for e in events}
    by_id = {e['id']:e for e in events}
    completed = {e['data'].get('reply_id') for e in events if e['type']=='playback' and e['data'].get('status')=='playback_completed'}
    incomplete = {e['data'].get('reply_id') for e in events if e['type']=='interrupt' or
                  (e['type']=='playback' and e['data'].get('status')=='playback_failed')}
    completed -= incomplete | {None, ''}
    report = room.get('report') or {}
    dimensions = report.get('dimensions', [])
    return {
        'final_transcript':any(e['type']=='transcript' for e in events),
        'student_reply':any(e['type']=='student' for e in events),
        'synthetic_playback_ack':any(e['type']=='student' and e['data'].get('reply_id') in completed for e in events),
        'report_completed':room.get('report_state')=='completed',
        'report_references':bool(dimensions) and all(set(d['event_ids']) <= ids and
            (d['score'] is None or (bool(d['event_ids']) and all(
                by_id[i]['type']!='student' or by_id[i]['data'].get('reply_id') in completed
                for i in d['event_ids']))) for d in dimensions),
    }


def automatic_end(item, seconds):
    return item.get('type') == 'ended' and item.get('at_ms', 0) >= seconds * 1000
